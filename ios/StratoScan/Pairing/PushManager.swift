import ActivityKit
import SwiftUI
import UIKit
import UserNotifications

/// Notifications from paired radars (roadmap 2.1). Apple gives this phone a
/// push token; the relay keeps it with the alert kinds chosen here, and
/// sends the radars' events to it. The token is only an address: the relay
/// never learns anything else about the phone.
@MainActor
final class PushManager: ObservableObject {
    static let shared = PushManager()

    /// The aircraft an alert was tapped for (#61): the radar opens on it.
    @Published var openHex: String?

    enum Kind: String, CaseIterable, Identifiable {
        case emergency, notable, low_overhead, helicopter, approach, approach_me
        var id: String { rawValue }
        var title: String {
            switch self {
            case .emergency: return "Emergencies"
            case .notable: return "Notable aircraft"
            case .low_overhead: return "Low overhead"
            case .helicopter: return "Helicopters"
            case .approach: return "Approaching aircraft"
            case .approach_me: return "Approaching me"
            }
        }
        var detail: String {
            switch self {
            case .emergency: return "Squawk 7500, 7600 or 7700, at any distance"
            case .notable: return "Military, rare and listed aircraft within 30 nm"
            case .low_overhead: return "Anything within 2 miles below 5,000 ft"
            case .helicopter: return "Within about 3 miles"
            case .approach: return "A live countdown on your lock screen when one of the above is about to pass over the radar"
            case .approach_me: return "The same countdown for wherever you are, within reach of your radar's antenna. Needs location set to Always; it's sent encrypted so only your radar can read it"
            }
        }
    }

    /// Where the nearby alerts -- notable, low overhead, helicopter -- are
    /// about (#44): the radar, where the phone is, or both. Sent to the
    /// relay as the 'near_radar' / 'near_me' choices.
    enum Place: String, CaseIterable, Identifiable {
        case radar, me, both
        var id: String { rawValue }
        var title: String {
            switch self {
            case .radar: return "My radar"
            case .me: return "Where I am"
            case .both: return "Both"
            }
        }
    }

    @Published var place: Place {
        didSet {
            UserDefaults.standard.set(place.rawValue, forKey: "stratoscan.alertPlace")
            effectiveChanged()
        }
    }

    /// The one switch over all of it (2026-11-17). Off, the relay is told to
    /// send this phone nothing, the lock-screen countdown included: iOS's
    /// own "Allow Notifications" doesn't stop a countdown, and with it off
    /// the app had no way to tell the relay anything. The choices below it
    /// are kept for when it goes back on.
    @Published var alertsOn: Bool {
        didSet {
            UserDefaults.standard.set(alertsOn, forKey: Self.alertsOnKey)
            effectiveChanged()
        }
    }

    /// What the relay is asked to send: nothing with the switch off or
    /// notifications refused in iOS, else the chosen kinds and where the
    /// nearby ones are about. Sorted, so the same choice always reads the same.
    var effectiveKinds: [String] {
        guard alertsOn, permission != .denied else { return [] }
        let where_: [String] = place == .radar ? ["near_radar"] : place == .me ? ["near_me"] : ["near_radar", "near_me"]
        return (kinds.map(\.rawValue) + where_).sorted()
    }

    /// A lock-screen countdown may be started on this phone.
    private var wantsCountdown: Bool {
        let sent = effectiveKinds
        return sent.contains(Kind.approach.rawValue) || sent.contains(Kind.approach_me.rawValue)
    }

    /// The phone's (encrypted) location is wanted by its radar: for
    /// "Approaching me", or nearby alerts about where it is. Never while
    /// nothing is sent to this phone.
    var needsLocation: Bool { !effectiveKinds.isEmpty && (kinds.contains(.approach_me) || place != .radar) }

    @Published private(set) var permission: UNAuthorizationStatus = .notDetermined
    @Published private(set) var registered = false
    /// The test button's result, and nothing else.
    @Published var message: String?
    /// The relay hasn't taken the current choices, and the last try failed.
    /// Stays until a try succeeds, whether or not Settings is open.
    @Published private(set) var syncFailed = false
    /// Why, when there is something worth saying.
    @Published private(set) var syncError: String?
    /// Apple gave no push token, and why.
    @Published private(set) var tokenProblem: String?
    @Published var kinds: Set<Kind> {
        didSet {
            UserDefaults.standard.set(kinds.map(\.rawValue), forKey: kindsKey)
            effectiveChanged()
        }
    }

    private let kindsKey = "radome.alertKinds"
    private static let alertsOnKey = "stratoscan.alertsOn"
    /// What the relay last accepted: the kinds, and whether they went with a
    /// push token. Kept across launches, so a change that never arrived is
    /// sent again the next time the app runs.
    private static let acceptedKey = "stratoscan.alertsAccepted"
    private var token: String?
    private var liveActivityToken: String?
    private var watchingActivities = false
    private let relay = RelayClient()

    /// Development builds (run from Xcode) get sandbox tokens; TestFlight and
    /// App Store builds get production ones. The relay must use the matching
    /// Apple server or the token is rejected.
    private var environment: String {
        #if DEBUG
        return "sandbox"
        #else
        return "production"
        #endif
    }

    private init() {
        let saved = UserDefaults.standard.stringArray(forKey: "radome.alertKinds")
        // Approaching aircraft is opt-in: near an airport it can be frequent.
        kinds = Set((saved ?? Kind.allCases.filter { $0 != .approach && $0 != .approach_me }.map(\.rawValue)).compactMap(Kind.init(rawValue:)))
        place = Place(rawValue: UserDefaults.standard.string(forKey: "stratoscan.alertPlace") ?? "") ?? .radar
        alertsOn = UserDefaults.standard.object(forKey: Self.alertsOnKey) as? Bool ?? true
    }

    func refreshPermission() async {
        let now = await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
        guard now != permission else { return }
        permission = now
        effectiveChanged()
    }

    /// The choices, or iOS's permission, changed what this phone should be
    /// sent: its location stops or starts with them, a countdown already on
    /// the lock screen comes down if none is wanted, and the relay is told.
    private func effectiveChanged() {
        let want = needsLocation
        if ApproachReporter.shared.enabled != want { ApproachReporter.shared.setEnabled(want) }
        if !wantsCountdown { endApproachActivities() }
        sync()
    }

    /// The app came to the front. Notifications may have been switched in
    /// iOS Settings meanwhile: off, the relay is told to send nothing; back
    /// on, Apple is asked for a token again.
    func becameActive() async {
        await refreshPermission()
        // a location the radars were to give back and the relay never heard
        ApproachReporter.shared.retryWithdrawal()
        guard !PairingStore.savedUnits().isEmpty else { return }
        if token == nil, allowed { askForToken() }
        sync()
    }

    private var allowed: Bool { permission == .authorized || permission == .provisional || permission == .ephemeral }

    private func askForToken() {
        // the kinds wait a moment for the token, to go in one request with it
        if token == nil { awaitingToken = true }
        askedForToken = true
        UIApplication.shared.registerForRemoteNotifications()
    }

    /// Asks once (after the first pairing, when the reason is obvious), then
    /// registers with Apple. Safe to call repeatedly: tokens can change.
    func enable() async {
        let center = UNUserNotificationCenter.current()
        if (await center.notificationSettings()).authorizationStatus == .notDetermined {
            _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        }
        await refreshPermission()
        refused = nil      // a radar may just have been paired
        if allowed { askForToken() }
        // Without permission there is no token, and the choices go on their own.
        sync()
    }

    func didRegister(token data: Data) {
        token = data.map { String(format: "%02x", $0) }.joined()
        awaitingToken = false
        tokenProblem = nil
        resend()
    }

    func didFailToRegister(_ error: Error) {
        awaitingToken = false
        tokenProblem = "Could not register for notifications: \(error.localizedDescription)"
        sync()
    }

    /// This phone's name was changed in Settings: its radars are told.
    func nameChanged() { Task { await syncName(paired: true) } }

    /// The name the relay last took from this phone.
    private static let sentNameKey = "stratoscan.phoneNameSent"
    /// Tells the relay this phone's name when it hasn't the current one. With
    /// a token it goes with the registration; without one (notifications
    /// off) on its own, or such a phone stayed "iPhone" on its radar for
    /// good (review, 2026-11-15). Asked at each opening of the app, and sent
    /// only when the name is not the one last taken.
    func syncName(paired: Bool) async {
        guard paired else { return }
        let name = PhoneName.current
        guard UserDefaults.standard.string(forKey: Self.sentNameKey) != name else { return }
        if token != nil { resend(); return }
        if (try? await relay.setName(name)) != nil { UserDefaults.standard.set(name, forKey: Self.sentNameKey) }
    }

    // ---- telling the relay (2026-11-17) ----
    //
    // Every change goes through sync(). It used to be a task per flip of a
    // switch, in no order, so two quick flips could land the wrong way
    // round; a failure was shown once and never tried again; and with no
    // push token (notifications off in iOS) nothing was sent at all, so the
    // relay kept sending to a phone that had said no.

    private var sending = false
    private var changedWhileSending = false
    /// Counts what a registration carries besides the kinds (the tokens, the
    /// name), so one that changed during a send is not taken as sent.
    private var revision = 0
    private var awaitingToken = false
    /// Apple has been asked for a token since the app started.
    private var askedForToken = false
    /// Keeps the app running long enough to finish a send after it leaves
    /// the screen.
    private var sendTask = UIBackgroundTaskIdentifier.invalid
    /// The choices the relay turned away because this phone has no pairing
    /// there: nothing to try again until a radar is paired.
    private var refused: String?
    private var retry: Task<Void, Never>?
    private var failures = 0
    private static let retryDelays: [UInt64] = [5, 15, 60]

    private var accepted: String? {
        get { UserDefaults.standard.string(forKey: Self.acceptedKey) }
        set {
            // Settings shows whether the relay has the choices
            objectWillChange.send()
            UserDefaults.standard.set(newValue, forKey: Self.acceptedKey)
        }
    }

    /// The kinds, and whether they go with a push token. With notifications
    /// allowed they do, and that holds before Apple has handed this launch
    /// its token: what went with a token last time is not sent again, alone,
    /// just because the app started (a launch in the background for a
    /// location change never asks for one). A new token sends the
    /// registration again by itself (resend).
    private var desired: String { effectiveKinds.joined(separator: ",") + (token != nil || allowed ? "|token" : "|kinds") }

    /// The relay doesn't have the current choices yet.
    var pending: Bool {
        guard !PairingStore.savedUnits().isEmpty else { return false }
        let want = desired
        return want != accepted && want != refused
    }

    /// The token or the name changed: the registration goes again whatever
    /// the kinds are.
    private func resend() {
        revision += 1
        accepted = nil
        sync()
    }

    /// Brings the relay in line with the choices. One request at a time: a
    /// change made during a send causes exactly one more, with the state as
    /// it then is, so the last word always wins.
    func sync() {
        if sending { changedWhileSending = true; return }
        sending = true
        // An "off" sent as the phone is locked or the app left must still
        // arrive: left alone, iOS suspends the app within a few seconds,
        // mid-request on a slow connection, and the relay goes on sending.
        // Asked, iOS gives about half a minute, as for a location report.
        if sendTask == .invalid {
            sendTask = UIApplication.shared.beginBackgroundTask(withName: "alert-choices") { [weak self] in
                self?.endSendTask()
            }
        }
        Task {
            repeat {
                changedWhileSending = false
                await attempt()
            } while changedWhileSending
            sending = false
            scheduleRetry()
            // Held through the first try again, and no longer.
            if retry == nil || failures > 1 { endSendTask() }
        }
    }

    private func endSendTask() {
        guard sendTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(sendTask)
        sendTask = .invalid
    }

    private func attempt() async {
        await refreshPermission()
        guard pending else { syncFailed = false; syncError = nil; return }
        // Notifications are allowed and Apple hasn't been asked for a token
        // since the app started: ask, and wait for it, whichever of the
        // app's openings got here first. Otherwise each launch sent the
        // kinds alone and then the registration, two requests for one.
        if token == nil, allowed, !askedForToken { askForToken() }
        if token == nil, awaitingToken { return }
        let sent = effectiveKinds, want = desired, at = revision, name = PhoneName.current
        do {
            if let token {
                try await relay.register(token: token, environment: environment, kinds: sent,
                                         liveActivityToken: liveActivityToken, name: PhoneName.current)
                UserDefaults.standard.set(name, forKey: Self.sentNameKey)
                registered = true
            } else {
                // No token (notifications off in iOS): the kinds alone, so
                // "nothing" still reaches the relay.
                registered = try await relay.setKinds(sent)
            }
            if at == revision { accepted = want }
            syncFailed = false
            syncError = nil
        } catch let no as RelayClient.Failure where no.status == 403 && no.message == "pair with a radar first" {
            // Expected before the first pairing, and nothing to try again.
            refused = want
            registered = false
            syncFailed = false
            syncError = nil
        } catch {
            if token != nil { registered = false }
            syncFailed = true
            // A relay from before this route answers 404; that says nothing
            // the owner can use.
            syncError = (error as? RelayClient.Failure)?.status == 404 ? nil : error.localizedDescription
        }
    }

    /// While the relay hasn't the choices, or still holds a location it was
    /// to give up, try again: after 5 s, 15 s, 60 s, then every minute.
    /// Nothing runs once it has the one and has dropped the other.
    private func scheduleRetry() {
        retry?.cancel()
        retry = nil
        guard pending || ApproachReporter.shared.withdrawalOwed else { failures = 0; return }
        let delay = Self.retryDelays[min(failures, Self.retryDelays.count - 1)]
        failures += 1
        retry = Task {
            try? await Task.sleep(nanoseconds: delay * 1_000_000_000)
            guard !Task.isCancelled else { return }
            awaitingToken = false      // Apple has had long enough
            ApproachReporter.shared.retryWithdrawal()
            sync()
        }
    }

    /// A withdrawal failed with the location still owed. The tries above
    /// are set going again if they had stopped; one already waiting, or a
    /// send whose end will look, is left alone, so the delays keep their
    /// order.
    func withdrawalStillOwed() {
        if retry == nil, !sending { scheduleRetry() }
    }

    /// Live Activities for approaching aircraft. Set up at every launch: the
    /// relay can start one while the app is not running, and iOS then wakes
    /// the app briefly so it can report that activity's token.
    func watchLiveActivities() {
        guard !watchingActivities else { return }
        watchingActivities = true
        // The token that lets the relay start an activity on this phone.
        Task {
            for await data in Activity<ApproachAttributes>.pushToStartTokenUpdates {
                liveActivityToken = data.map { String(format: "%02x", $0) }.joined()
                // it goes with the push token; without one yet, when that comes
                if token != nil { resend() } else { revision += 1 }
            }
        }
        // Each activity the relay starts: report its own token, used to end it.
        // Ones that already exist (started while the app was not running)
        // as well as new ones.
        for activity in Activity<ApproachAttributes>.activities { report(activity) }
        Task {
            for await activity in Activity<ApproachAttributes>.activityUpdates {
                report(activity)
                // A countdown the relay starts wakes the app where it lay,
                // and this loop is all that then runs. iOS tells nobody when
                // "Allow Notifications" is switched, so this is the first
                // chance to notice, with the app not opened since: the
                // countdown comes down if none is wanted, and the relay is
                // told, so this one is the last.
                await refreshPermission()
                if !wantsCountdown { endApproachActivities() }
                sync()
            }
        }
        endFinishedActivities()
    }

    private func report(_ activity: Activity<ApproachAttributes>) {
        Task {
            for await data in activity.pushTokenUpdates {
                let hex = data.map { String(format: "%02x", $0) }.joined()
                try? await relay.reportActivity(unit: activity.attributes.unit,
                                                hex: activity.attributes.hex, token: hex)
            }
        }
    }

    /// A backstop for the relay's end: any card whose pass is over by more
    /// than two minutes is taken down whenever the app runs.
    func endFinishedActivities() {
        let cutoff = Date().addingTimeInterval(-120)
        for activity in Activity<ApproachAttributes>.activities where activity.content.state.eta < cutoff {
            Task {
                var done = activity.content.state
                done.passed = true
                await activity.end(ActivityContent(state: done, staleDate: nil), dismissalPolicy: .immediate)
            }
        }
    }

    /// No countdown is wanted any more: any on the lock screen comes down
    /// now, not when its aircraft has passed.
    private func endApproachActivities() {
        for activity in Activity<ApproachAttributes>.activities {
            Task { await activity.end(nil, dismissalPolicy: .immediate) }
        }
    }

    func sendTest() async {
        do {
            try await relay.testPush()
            message = "Sent. It should arrive in a few seconds."
        } catch {
            message = error.localizedDescription
        }
    }
}

/// Receives the push token from iOS, and lets alerts show while the app is open.
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        Task { @MainActor in
            PushManager.shared.watchLiveActivities()
            // Approaching me: iOS may have relaunched the app for a location
            // update. Not before iOS has said whether notifications are
            // allowed: refused, the phone's location isn't sent.
            await PushManager.shared.refreshPermission()
            ApproachReporter.shared.resumeIfEnabled()
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        Task { @MainActor in PushManager.shared.didRegister(token: deviceToken) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        Task { @MainActor in PushManager.shared.didFailToRegister(error) }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async
        -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    /// Tapped: the app opens on the aircraft the alert is about (#61). The
    /// relay puts its hex in the payload (stratoscan.hex).
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard let info = response.notification.request.content.userInfo["stratoscan"] as? [String: Any],
              let hex = info["hex"] as? String, !hex.isEmpty else { return }
        await MainActor.run { PushManager.shared.openHex = hex.lowercased() }
    }
}
