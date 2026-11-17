import CoreLocation
import CryptoKit
import Foundation
import UIKit

/// "Approaching me" (roadmap 2.7): keeps each paired radar told where this
/// phone is, so the radar can warn of aircraft about to pass over it.
///
/// Only while the owner has it on. iOS's significant-change service wakes
/// the app when the phone has moved roughly 500 m or more -- low power, and
/// it works with the app closed, which is why it needs "Always". Each update
/// is sealed to each radar's own box key (LocationBox), checked against the
/// radar's id as this phone recorded it when pairing, so the relay that
/// carries it can't read it. Turning it off withdraws the location from
/// every radar.
@MainActor
final class ApproachReporter: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = ApproachReporter()

    @Published private(set) var needsAlways = false
    /// Radars the relay lists for this phone that it never paired with
    /// (2026-10-26). A radar is paired only here: its code, scanned or opened
    /// with a yes, or setting it up from this phone. While the relay lists
    /// any other, no radar gets the location, and Settings says so.
    @Published private(set) var strangers: [String] = []
    private static let strangersKey = "stratoscan.strangerRadars"
    private let manager = CLLocationManager()
    private let relay = RelayClient()
    private let enabledKey = "stratoscan.approachMe"
    private let boxKeysKey = "stratoscan.boxKeys"      // unit id -> verified box key (base64url)
    private var lastSent: Date = .distantPast
    /// The location being taken back from the radars, while that is under way.
    private var withdrawing: Task<Void, Never>?
    /// Withdrawals asked for and not yet finished, so a try again isn't
    /// queued behind one still running.
    private var withdrawalsQueued = 0
    /// Counts the times a withdrawal was wanted: one that finishes after a
    /// later one was asked for doesn't settle the debt on its behalf.
    private var withdrawalsWanted = 0
    /// The location is to be taken back from the radars and the relay hasn't
    /// yet said it is gone from every one (2026-11-17). Kept across launches:
    /// a withdrawal that failed (no signal as the switch went off) used to be
    /// given up in silence, and with reporting already off nothing tried
    /// again, so the sealed location lay at the relay until it aged out.
    private static let owedKey = "stratoscan.withdrawalOwed"
    private(set) var withdrawalOwed: Bool {
        get { UserDefaults.standard.bool(forKey: Self.owedKey) }
        set { UserDefaults.standard.set(newValue, forKey: Self.owedKey) }
    }

    var enabled: Bool { UserDefaults.standard.bool(forKey: enabledKey) }

    private override init() {
        super.init()
        manager.delegate = self
        strangers = UserDefaults.standard.stringArray(forKey: Self.strangersKey) ?? []
    }

    /// At launch: carry on if it was on (iOS relaunches the app in the
    /// background for a significant change, and this picks the update up).
    func resumeIfEnabled() {
        // Only what the alerts need now decides it (2026-11-17): with alerts
        // off, or notifications refused in iOS, a setting left on from
        // before is turned off and the location withdrawn.
        if PushManager.shared.needsLocation {
            // wanted again: nothing is owed, before any report (see setEnabled)
            withdrawalOwed = false
            UserDefaults.standard.set(true, forKey: enabledKey)
            begin()
        } else if enabled {
            setEnabled(false)
        } else {
            // a withdrawal an earlier run of the app never finished
            retryWithdrawal()
        }
    }

    func setEnabled(_ on: Bool) {
        UserDefaults.standard.set(on, forKey: enabledKey)
        if on {
            // Nothing is owed any more, and that is settled before the report
            // below is started: a withdrawal still queued finds nothing owed
            // and does nothing, one already running is waited for by the
            // report, and no try again can start after it and take the fresh
            // location back.
            withdrawalOwed = false
            // Off and straight back on: the report that follows must go,
            // however recent the last one, or the radars are left with
            // nothing until the phone next moves.
            lastSent = .distantPast
            begin()
        } else {
            manager.stopMonitoringSignificantLocationChanges()
            oweWithdrawal()
        }
    }

    /// The location is wanted back from every radar: noted first, so it is
    /// still owed if the app is stopped or the relay can't be reached, then
    /// tried.
    private func oweWithdrawal() {
        withdrawalOwed = true
        withdrawalsWanted += 1
        queueWithdrawal()
    }

    /// A withdrawal that hasn't gone through is tried again: when the app
    /// comes to the front, at launch, and with PushManager's own tries. Not
    /// while reporting is on, and not behind one still under way.
    func retryWithdrawal() {
        guard withdrawalOwed, !enabled, withdrawalsQueued == 0 else { return }
        queueWithdrawal()
    }

    private func queueWithdrawal() {
        // one after another, and a report waits for them (see report)
        let before = withdrawing
        withdrawalsQueued += 1
        withdrawing = Task {
            await before?.value
            defer { withdrawalsQueued -= 1 }
            // looked at only now: reporting may have gone back on meanwhile,
            // or an earlier withdrawal may have settled it
            guard withdrawalOwed, !enabled else { return }
            let wanted = withdrawalsWanted
            let gone = await withdraw()
            // Settled only if nothing asked for another since this one began.
            if gone, wanted == withdrawalsWanted, !enabled { withdrawalOwed = false }
            // Still owed: PushManager's tries carry it from here. They are
            // set going only as a send to the relay ends, and this one may
            // have begun with none to follow (a report that landed after the
            // switch went off, or no radar paired on this phone).
            if withdrawalOwed, !enabled { PushManager.shared.withdrawalStillOwed() }
        }
    }

    private func begin() {
        switch manager.authorizationStatus {
        case .notDetermined:
            manager.requestAlwaysAuthorization()
        case .authorizedWhenInUse:
            // iOS offers the step up to Always once, later, on its own terms.
            manager.requestAlwaysAuthorization()
            needsAlways = true
        case .denied, .restricted:
            needsAlways = true
            return
        default:
            needsAlways = false
        }
        manager.startMonitoringSignificantLocationChanges()
        if let l = manager.location { Task { await report(l) } }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        let status = m.authorizationStatus
        Task { @MainActor in
            needsAlways = status != .authorizedAlways
            if enabled, status == .authorizedAlways || status == .authorizedWhenInUse {
                manager.startMonitoringSignificantLocationChanges()
            }
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let l = locations.last else { return }
        Task { @MainActor in await report(l) }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {}

    /// Seal this position to every radar paired here and leave it at the relay.
    private func report(_ l: CLLocation) async {
        // iOS woke the app for a move, perhaps with the app not opened since
        // notifications were switched off in iOS Settings, which iOS tells
        // nobody about. Looked at here, so the location stops (enabled goes
        // false) and the relay is told to send nothing.
        await PushManager.shared.refreshPermission()
        PushManager.shared.sync()
        guard enabled, Date().timeIntervalSince(lastSent) > 30, backgroundTask == .invalid else { return }
        lastSent = Date()
        // Woken in the background for a move, the app has a few seconds before
        // iOS suspends it, often mid-way through the relay's calls; asked, iOS
        // gives it about half a minute to finish (#86, 2026-10-26). Each call
        // is 30 s at most (URLSession.bounded), and one report runs at a time.
        backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "approach-report") { [weak self] in
            self?.endBackgroundTask()
        }
        defer { endBackgroundTask() }
        // Off and straight back on while this is on its way: the withdrawal
        // that the off began doesn't wait for this report, and may reach the
        // relay after it; the report the on began finds this one still
        // running and gives way. So this one goes round once more, behind
        // that withdrawal, or the radars are left with nothing until the
        // phone next moves.
        var wanted = withdrawalsWanted
        repeat {
            wanted = withdrawalsWanted
            // A withdrawal still on its way goes first, or it could land after
            // this report and take the location back.
            await withdrawing?.value
            guard enabled else { return }
            guard let phone = try? RelayIdentity.id(), let units = try? await relay.units(),
                  let recipients = vet(units.map(\.unit)) else { return }
            let ts = Int(l.timestamp.timeIntervalSince1970)
            // not to a radar the owner keeps it from (2026-11-15): one set up
            // from this phone, until they turn it on for that radar
            let withheld = PairingStore.locationWithheld()
            for unit in recipients where !withheld.contains(unit) {
                guard let box = await boxKey(for: unit),
                      let blob = try? LocationBox.seal(lat: l.coordinate.latitude, lon: l.coordinate.longitude,
                                                       ts: ts, to: box, phone: phone) else { continue }
                try? await relay.location(unit: unit, blob: blob)
            }
            // Switched off while this was on its way: the withdrawal may have
            // reached the relay before the report did, so it is owed once more.
            if !enabled { oweWithdrawal() }
        } while enabled && wanted != withdrawalsWanted
    }

    /// The relay's list of radars for this phone, against the phone's own
    /// (2026-10-26): those that may have its location, or nil when the relay
    /// lists one this phone never paired with. Notes any such radar for
    /// Settings, and forgets box keys kept for radars no longer paired here.
    @discardableResult
    func vet(_ listed: [String]) -> [String]? {
        // read after the relay's answer: a pairing that finished meanwhile counts
        let paired = PairingStore.savedUnits()
        let now = listed.filter { !paired.contains($0) }
        if now != strangers {
            strangers = now
            UserDefaults.standard.set(now, forKey: Self.strangersKey)
        }
        if var cache = UserDefaults.standard.dictionary(forKey: boxKeysKey) as? [String: String],
           cache.keys.contains(where: { !paired.contains($0) }) {
            cache = cache.filter { paired.contains($0.key) }
            UserDefaults.standard.set(cache, forKey: boxKeysKey)
        }
        return LocationBox.recipients(listed: listed, paired: paired)
    }

    /// A radar just paired on this phone is no stranger.
    func forgetStranger(_ unit: String) {
        guard strangers.contains(unit) else { return }
        strangers.removeAll { $0 == unit }
        UserDefaults.standard.set(strangers, forKey: Self.strangersKey)
    }

    /// The owner switched one radar's share of the location (2026-11-15).
    /// Off takes back what the relay holds for it; on sends the position
    /// now, when the alerts that need it are on.
    func sharingChanged(unit: String, on: Bool) {
        if on {
            lastSent = .distantPast
            if enabled, let l = manager.location { Task { await report(l) } }
        } else {
            Task { try? await relay.location(unit: unit, blob: nil) }
        }
    }

    private var backgroundTask = UIBackgroundTaskIdentifier.invalid
    private func endBackgroundTask() {
        guard backgroundTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTask)
        backgroundTask = .invalid
    }

    private var withdrawTask = UIBackgroundTaskIdentifier.invalid
    private func endWithdrawTask() {
        guard withdrawTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(withdrawTask)
        withdrawTask = .invalid
    }

    /// From every radar the relay lists, paired here or not (2026-10-26): a
    /// withdrawal carries no location, so it may go wider than a report.
    /// Answers whether the location is now gone from all of them; anything
    /// less stays owed and is tried again (2026-11-17).
    private func withdraw() async -> Bool {
        // The switch usually goes off as the app is being left, and iOS
        // suspends it within a few seconds, mid-request on a slow
        // connection; asked, it gives about half a minute, as for a report.
        // Withdrawals run one at a time, so one task is enough.
        withdrawTask = UIApplication.shared.beginBackgroundTask(withName: "approach-withdraw") { [weak self] in
            self?.endWithdrawTask()
        }
        defer { endWithdrawTask() }
        let units: [RelayClient.PairedUnit]
        do {
            units = try await relay.units()
        } catch {
            // With no radar paired on this phone there is nowhere a location
            // was sent, and nothing to keep trying for.
            return PairingStore.savedUnits().isEmpty
        }
        // An empty list is the relay saying this phone is paired with nothing.
        var gone = true
        for u in units {
            do {
                try await relay.location(unit: u.unit, blob: nil)
            } catch let no as RelayClient.Failure where no.status == 403 {
                // unpaired from that radar meanwhile: the relay holds nothing for it
            } catch {
                gone = false
            }
        }
        return gone
    }

    /// A radar's box key: remembered once its signature has checked out.
    /// Only for a radar paired here (2026-10-26).
    private func boxKey(for unit: String) async -> Curve25519.KeyAgreement.PublicKey? {
        guard PairingStore.savedUnits().contains(unit) else { return nil }
        var cache = UserDefaults.standard.dictionary(forKey: boxKeysKey) as? [String: String] ?? [:]
        if let raw = cache[unit], let data = Data(base64url: raw),
           let key = try? Curve25519.KeyAgreement.PublicKey(rawRepresentation: data) {
            return key
        }
        guard let r = try? await relay.boxKey(unit: unit),
              let key = LocationBox.verifiedBoxKey(unit: unit, key: r.key, sig: r.sig) else { return nil }
        cache[unit] = r.key
        UserDefaults.standard.set(cache, forKey: boxKeysKey)
        return key
    }
}
