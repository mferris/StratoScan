import CoreLocation
import Foundation

/// Where this phone is, for the radar's "You" marker and "centre on me"
/// (roadmap 2.7, the map part). Used on the phone only: nothing here is sent
/// anywhere -- not to the radar, not to the relay. Starts only when the owner
/// first asks to be shown, which is when iOS asks for permission.
@MainActor
final class PhoneLocation: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var coordinate: Coordinate?
    /// The owner said no (or restrictions apply): say so rather than spin.
    @Published private(set) var denied = false
    /// Which way the top of the phone points, in degrees (roadmap 3.4's
    /// compass). True north when iOS knows it, magnetic otherwise.
    @Published private(set) var heading: Double?
    @Published private(set) var headingIsTrue = false
    /// Worse than this many degrees and the compass says it needs calibrating.
    @Published private(set) var headingAccuracy: Double?

    private let manager = CLLocationManager()
    private var started = false

    override init() {
        super.init()
        manager.delegate = self
        // A street's worth is plenty for "which side of the house", and far
        // kinder to the battery than best-for-navigation.
        manager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        manager.distanceFilter = 20
    }

    func start() {
        guard !started else { return }
        started = true
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .denied, .restricted: denied = true
        default: manager.startUpdatingLocation()
        }
    }

    func stop() {
        started = false
        manager.stopUpdatingLocation()
    }

    func startHeading() {
        start()
        guard CLLocationManager.headingAvailable() else { return }
        manager.headingFilter = 1
        manager.startUpdatingHeading()
    }

    func stopHeading() { manager.stopUpdatingHeading() }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateHeading h: CLHeading) {
        let isTrue = h.trueHeading >= 0
        let value = isTrue ? h.trueHeading : h.magneticHeading
        let accuracy = h.headingAccuracy
        Task { @MainActor in
            heading = value
            headingIsTrue = isTrue
            headingAccuracy = accuracy >= 0 ? accuracy : nil
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        let status = m.authorizationStatus
        Task { @MainActor in
            switch status {
            case .authorizedWhenInUse, .authorizedAlways:
                denied = false
                if started { manager.startUpdatingLocation() }
            case .denied, .restricted:
                denied = true
            default: break
            }
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let l = locations.last else { return }
        let c = Coordinate(lat: l.coordinate.latitude, lon: l.coordinate.longitude)
        Task { @MainActor in coordinate = c }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {}
}
