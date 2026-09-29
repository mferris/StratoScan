import Foundation

/// Demo mode: plays back a few minutes of real traffic recorded near RDU
/// airport (Resources/demo-traffic.json), centred on the airport, so the app
/// can be seen working without a radar -- for App Review, screenshots, and
/// anyone curious before they have one.
enum DemoFeed {
    private static let key = "radome.demoMode"

    static var isOn: Bool {
        get { UserDefaults.standard.bool(forKey: key) }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    private struct Recording: Decodable {
        struct Home: Decodable { let lat: Double; let lon: Double }
        struct Frame: Decodable { let t: Double; let aircraft: [RawAircraft] }
        let home: Home
        let frames: [Frame]
    }

    private static let recording: Recording? = {
        guard let url = Bundle.main.url(forResource: "demo-traffic", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Recording.self, from: data)
    }()

    private static let started = Date()

    static var home: Coordinate? {
        recording.map { Coordinate(lat: $0.home.lat, lon: $0.home.lon) }
    }

    /// The recorded frame for now, looping.
    static func aircraft(now: Date = Date()) -> [RawAircraft] {
        guard let frames = recording?.frames, let last = frames.last, last.t > 0 else { return [] }
        let t = now.timeIntervalSince(started).truncatingRemainder(dividingBy: last.t)
        let i = frames.lastIndex { $0.t <= t } ?? 0
        return frames[i].aircraft
    }
}
