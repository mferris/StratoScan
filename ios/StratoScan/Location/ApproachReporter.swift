import CoreLocation
import CryptoKit
import Foundation

/// "Approaching me" (roadmap 2.7): keeps each paired radar told where this
/// phone is, so the radar can warn of aircraft about to pass over it.
///
/// Only while the owner has it on. iOS's significant-change service wakes
/// the app when the phone has moved roughly 500 m or more -- low power, and
/// it works with the app closed, which is why it needs "Always". Each update
/// is sealed to each radar's own box key (LocationBox), checked against the
/// radar's id first, so the relay that carries it can't read it. Turning it
/// off withdraws the location from every radar.
@MainActor
final class ApproachReporter: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = ApproachReporter()

    @Published private(set) var needsAlways = false
    private let manager = CLLocationManager()
    private let relay = RelayClient()
    private let enabledKey = "stratoscan.approachMe"
    private let boxKeysKey = "stratoscan.boxKeys"      // unit id -> verified box key (base64url)
    private var lastSent: Date = .distantPast

    var enabled: Bool { UserDefaults.standard.bool(forKey: enabledKey) }

    private override init() {
        super.init()
        manager.delegate = self
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

    /// Seal this position to every paired radar and leave it at the relay.
    private func report(_ l: CLLocation) async {
        guard enabled, Date().timeIntervalSince(lastSent) > 30 else { return }
        lastSent = Date()
        guard let phone = try? RelayIdentity.id(), let units = try? await relay.units() else { return }
        let ts = Int(l.timestamp.timeIntervalSince1970)
        for u in units {
            guard let box = await boxKey(for: u.unit),
                  let blob = try? LocationBox.seal(lat: l.coordinate.latitude, lon: l.coordinate.longitude,
                                                   ts: ts, to: box, phone: phone) else { continue }
            try? await relay.location(unit: u.unit, blob: blob)
        }
    }

    private func withdraw() async {
        guard let units = try? await relay.units() else { return }
        for u in units { try? await relay.location(unit: u.unit, blob: nil) }
    }

    /// A radar's box key: remembered once its signature has checked out.
    private func boxKey(for unit: String) async -> Curve25519.KeyAgreement.PublicKey? {
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
