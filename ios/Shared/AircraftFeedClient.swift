import Foundation

enum AircraftFeedClient {
    /// Whether to include aircraft a public network reports that the radar's
    /// own antenna didn't hear (roadmap 2.8). On by default, as on the kiosk.
    static var showNetwork: Bool {
        get { UserDefaults.standard.object(forKey: "stratoscan.showNetwork") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "stratoscan.showNetwork") }
    }

    /// Set when the radar answered /api/aircraft with 404: it hasn't got the
    /// core feed yet, so use aircraft.json and ask again in a few minutes.
    private static var coreMissingUntil = Date.distantPast

    static func fetchAircraft() async throws -> [RawAircraft] {
        try await fetchFeed(network: false).aircraft
    }

    /// The radar's labelled core feed (/api/aircraft), or readsb's plain
    /// aircraft.json from a radar that doesn't have it yet.
    /// Marks the app's own requests, so the radar's public-page visitor
    /// counts (roadmap 1.12) show its owner's app apart from visitors.
    static let appHeader = "X-StratoScan-App"

    static func fetchFeed(network: Bool) async throws -> AircraftFeedResponse {
        if DemoFeed.isOn { return AircraftFeedResponse(aircraft: DemoFeed.aircraft(), now: nil) }
        await Endpoint.shared.resolve()
        if Date() >= coreMissingUntil {
            var req = URLRequest(url: APIConfig.url("/api/aircraft" + (network ? "?network=1" : "")))
            req.setValue("1", forHTTPHeaderField: Self.appHeader)
            req.cachePolicy = .reloadIgnoringLocalCacheData
            req.timeoutInterval = 8
            let data: Data
            let response: URLResponse
            do {
                (data, response) = try await URLSession.shared.data(for: req)
            } catch {
                Endpoint.shared.invalidate()   // perhaps we just left (or came) home
                throw error
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            if status == 200, let feed = try? JSONDecoder().decode(AircraftFeedResponse.self, from: data) {
                return feed
            }
            if status == 404 { coreMissingUntil = Date().addingTimeInterval(300) }
            // anything else: fall back to aircraft.json for this poll
        }
        return AircraftFeedResponse(aircraft: try await fetchReadsb(), now: nil)
    }

    private static func fetchReadsb() async throws -> [RawAircraft] {
        var req = URLRequest(url: APIConfig.url("/tar1090/data/aircraft.json"))
        req.setValue("1", forHTTPHeaderField: Self.appHeader)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.timeoutInterval = 8
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            Endpoint.shared.invalidate()   // perhaps we just left (or came) home
            throw error
        }
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            Endpoint.shared.invalidate()
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(AircraftFeedResponse.self, from: data).aircraft
    }

    static func fetchReceiver() async throws -> Coordinate? {
        if DemoFeed.isOn { return DemoFeed.home }
        await Endpoint.shared.resolve()
        var req = URLRequest(url: APIConfig.url("/tar1090/data/receiver.json"))
        req.setValue("1", forHTTPHeaderField: Self.appHeader)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.timeoutInterval = 8      // not iOS's default 60 s: the widget must not hang
        let (data, response) = try await URLSession.shared.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        let r = try JSONDecoder().decode(ReceiverResponse.self, from: data)
        guard let lat = r.lat, let lon = r.lon else { return nil }
        return Coordinate(lat: lat, lon: lon)
    }
}

/// What the widget shows: how many aircraft are in range, nearest first.
struct Nearby {
    struct Plane {
        let callsign: String
        let altitudeText: String
        let distanceNm: Double
        let direction: String
        /// Degrees from the radar, for drawing it on a radar (the StandBy widget).
        var bearing: Double = 0
        var isNetwork = false
    }
    let count: Int
    let planes: [Plane]

    static let rangeNm = 20.0   // the radar's outer ring, as on the kiosk and in the app

    static func from(_ aircraft: [RawAircraft], home: Coordinate) -> Nearby {
        let points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        let planes: [Plane] = aircraft.compactMap { a in
            guard let lat = a.lat, let lon = a.lon else { return nil }
            let br = Geo.haversineBearingRange(lat1: home.lat, lon1: home.lon, lat2: lat, lon2: lon)
            guard br.range <= rangeNm else { return nil }
            let cs = (a.flight ?? "").trimmingCharacters(in: .whitespaces)
            let alt: String
            switch a.altBaro ?? a.altGeom ?? .unknown {
            case .ground: alt = "ground"
            case .unknown: alt = "—"
            case .feet(let ft): alt = ft >= 18000 ? "FL\(Int((ft / 100).rounded()))" : "\(Int(ft).formatted()) ft"
            }
            let dir = points[Int(((br.bearing.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360) / 45).rounded()) % 8]
            return Plane(callsign: cs.isEmpty ? a.hex.uppercased() : cs, altitudeText: alt, distanceNm: br.range, direction: dir,
                         bearing: br.bearing, isNetwork: a.isNetwork)
        }
        .sorted { $0.distanceNm < $1.distanceNm }
        return Nearby(count: planes.count, planes: planes)
    }

    static func load() async throws -> Nearby {
        guard let home = try await AircraftFeedClient.fetchReceiver() else { throw URLError(.cannotParseResponse) }
        return from(try await AircraftFeedClient.fetchAircraft(), home: home)
    }
}
