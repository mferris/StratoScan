import Foundation

enum AircraftFeedClient {
    static func fetchAircraft() async throws -> [RawAircraft] {
        if DemoFeed.isOn { return DemoFeed.aircraft() }
        await Endpoint.shared.resolve()
        var req = URLRequest(url: APIConfig.url("/tar1090/data/aircraft.json"))
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
            return Plane(callsign: cs.isEmpty ? a.hex.uppercased() : cs, altitudeText: alt, distanceNm: br.range, direction: dir)
        }
        .sorted { $0.distanceNm < $1.distanceNm }
        return Nearby(count: planes.count, planes: planes)
    }

    static func load() async throws -> Nearby {
        guard let home = try await AircraftFeedClient.fetchReceiver() else { throw URLError(.cannotParseResponse) }
        return from(try await AircraftFeedClient.fetchAircraft(), home: home)
    }
}
