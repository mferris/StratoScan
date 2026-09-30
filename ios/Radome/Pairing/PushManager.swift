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

    enum Kind: String, CaseIterable, Identifiable {
        case emergency, notable, low_overhead, helicopter, approach
        var id: String { rawValue }
        var title: String {
            switch self {
            case .emergency: return "Emergencies"
            case .notable: return "Notable aircraft"
            case .low_overhead: return "Low overhead"
            case .helicopter: return "Helicopters"
            case .approach: return "Approaching aircraft"
            }
        }
        var detail: String {
            switch self {
            case .emergency: return "Squawk 7500, 7600 or 7700, at any distance"
            case .notable: return "Military, rare and listed aircraft within 30 nm"
            case .low_overhead: return "Anything within 2 miles below 5,000 ft"
            case .helicopter: return "Within about 3 miles"
            case .approach: return "A live countdown on your lock screen when one of the above is about to pass over"
            }
        }
    }

    @Published private(set) var permission: UNAuthorizationStatus = .notDetermined
    @Published private(set) var registered = false
    @Published var message: String?
    @Published var kinds: Set<Kind> {
        didSet {
            UserDefaults.standard.set(kinds.map(\.rawValue), forKey: kindsKey)
            Task { await sendRegistration() }
        }
    }

    private let kindsKey = "radome.alertKinds"
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
        kinds = Set((saved ?? Kind.allCases.filter { $0 != .approach }.map(\.rawValue)).compactMap(Kind.init(rawValue:)))
    }

    func refreshPermission() async {
        permission = await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    /// Asks once (after the first pairing, when the reason is obvious), then
    /// registers with Apple. Safe to call repeatedly: tokens can change.
    func enable() async {
        let center = UNUserNotificationCenter.current()
        if (await center.notificationSettings()).authorizationStatus == .notDetermined {
            _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        }
        await refreshPermission()
        if permission == .authorized || permission == .provisional || permission == .ephemeral {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    func didRegister(token data: Data) {
        token = data.map { String(format: "%02x", $0) }.joined()
        Task { await sendRegistration() }
    }

    func didFailToRegister(_ error: Error) {
        message = "Could not register for notifications: \(error.localizedDescription)"
    }

    private func sendRegistration() async {
        guard let token else { return }
        do {
            try await relay.register(token: token, environment: environment, kinds: kinds.map(\.rawValue),
                                     liveActivityToken: liveActivityToken)
            registered = true
        } catch {
            // Not paired yet is expected before the first pairing; anything
            // else is worth showing.
            registered = false
            message = error.localizedDescription
        }
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
                await sendRegistration()
            }
        }
        // Each activity the relay starts: report its own token, used to end it.
        // Ones that already exist (started while the app was not running)
        // as well as new ones.
        for activity in Activity<ApproachAttributes>.activities { report(activity) }
        Task {
            for await activity in Activity<ApproachAttributes>.activityUpdates { report(activity) }
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
        Task { @MainActor in PushManager.shared.watchLiveActivities() }
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
}
