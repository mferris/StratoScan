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

    var enabled: Bool { UserDefaults.standard.bool(forKey: enabledKey) }

    private override init() {
        super.init()
        manager.delegate = self
        strangers = UserDefaults.standard.stringArray(forKey: Self.strangersKey) ?? []
    }

    /// At launch: carry on if it was on (iOS relaunches the app in the
    /// background for a significant change, and this picks the update up).
    func resumeIfEnabled() {
        // the setting predates #44; nearby alerts about the phone need it too
        if enabled || PushManager.shared.needsLocation {
            UserDefaults.standard.set(true, forKey: enabledKey)
            begin()
        }
    }

    func setEnabled(_ on: Bool) {
        UserDefaults.standard.set(on, forKey: enabledKey)
        if on {
            begin()
        } else {
            manager.stopMonitoringSignificantLocationChanges()
            Task { await withdraw() }
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
        guard let phone = try? RelayIdentity.id(), let units = try? await relay.units(),
              let recipients = vet(units.map(\.unit)) else { return }
        let ts = Int(l.timestamp.timeIntervalSince1970)
        for unit in recipients {
            guard let box = await boxKey(for: unit),
                  let blob = try? LocationBox.seal(lat: l.coordinate.latitude, lon: l.coordinate.longitude,
                                                   ts: ts, to: box, phone: phone) else { continue }
            try? await relay.location(unit: unit, blob: blob)
        }
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

    private var backgroundTask = UIBackgroundTaskIdentifier.invalid
    private func endBackgroundTask() {
        guard backgroundTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTask)
        backgroundTask = .invalid
    }

    /// From every radar the relay lists, paired here or not (2026-10-26): a
    /// withdrawal carries no location, so it may go wider than a report.
    private func withdraw() async {
        guard let units = try? await relay.units() else { return }
        for u in units { try? await relay.location(unit: u.unit, blob: nil) }
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
