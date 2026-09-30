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
