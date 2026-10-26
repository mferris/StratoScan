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
                (data, response) = try await URLSession.radar.data(for: req)
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
            (data, response) = try await URLSession.radar.data(for: req)
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

    /// Where each aircraft has already been, from the radar (#84), for a screen
    /// that has just opened: points as [seconds ago, lat, lon, altitude in
    /// feet or null], oldest first. Nil from a radar without it yet, or on any
    /// failure: the trails then start from now, as they always did.
    struct Trails: Decodable { let trails: [String: [[Double?]]] }

    static func fetchTrails() async -> Trails? {
        if DemoFeed.isOn { return nil }
        await Endpoint.shared.resolve()
        var req = URLRequest(url: APIConfig.url("/api/trails"))
        req.setValue("1", forHTTPHeaderField: Self.appHeader)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.timeoutInterval = 10
        guard let (data, resp) = try? await URLSession.bounded.data(for: req),     // nothing waits on it
              (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(Trails.self, from: data)
    }

    static func fetchReceiver() async throws -> Coordinate? {
        if DemoFeed.isOn { return DemoFeed.home }
        await Endpoint.shared.resolve()
        let radar = radarNow        // whose position this is, as asked
        var req = URLRequest(url: APIConfig.url("/tar1090/data/receiver.json"))
        req.setValue("1", forHTTPHeaderField: Self.appHeader)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.timeoutInterval = 8      // not iOS's default 60 s: the widget must not hang
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.radar.data(for: req)
        } catch {
            // As the feed does (#86, 2026-10-26): without this the next look
            // went to the same dead address, and the Watch never left it.
            Endpoint.shared.invalidate()
            throw error
        }
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            Endpoint.shared.invalidate()
            throw URLError(.badServerResponse)
        }
        let r = try JSONDecoder().decode(ReceiverResponse.self, from: data)
        guard let lat = r.lat, let lon = r.lon else { return nil }
        let c = Coordinate(lat: lat, lon: lon)
        keepHome(c, of: radar)
        return c
    }

    // ---- the radar's position, kept --------------------------------------------
    // A radar that cannot be reached (the phone is away and the public page
    // is off) still has a known place: the rings, the "N nm from your radar"
    // and the away test all need it. Kept in the App Group, so the widget
    // reads the app's copy (2026-10-26).
    private static let homeCacheKey = "stratoscan.homeCache"

    /// Which radar a kept position is for: the addresses it is read from.
    /// Changed in Settings (an owner with a second radar), or paired with
    /// another radar's public address, and the copy is not this radar's: the
    /// widgets and the Watch measured its aircraft from the other radar's
    /// place for up to a day (#86, 2026-10-26).
    private static var radarNow: String { APIConfig.baseURL + " " + (APIConfig.awayURL ?? "") }

    /// The radar's position as last read, and when (nil from before that was
    /// kept); none when it was read from another radar. One kept before that
    /// was noted is taken, as it always was, until the radar is read again.
    static var cachedHome: (home: Coordinate, at: Date?)? {
        guard let d = APIConfig.shared.dictionary(forKey: homeCacheKey),
              let lat = d["lat"] as? Double, let lon = d["lon"] as? Double else { return nil }
        if let radar = d["radar"] as? String, radar != radarNow { return nil }
        return (Coordinate(lat: lat, lon: lon), (d["at"] as? Double).map(Date.init(timeIntervalSince1970:)))
    }

    private static func keepHome(_ c: Coordinate, of radar: String) {
        APIConfig.shared.set(["lat": c.lat, "lon": c.lon, "at": Date().timeIntervalSince1970, "radar": radar],
                             forKey: homeCacheKey)
    }

    /// The radar's position for a widget or the Watch: the copy kept, while
    /// it is under a day old and this radar's, else the radar's own (#86,
    /// 2026-10-26). A radar doesn't move, and every look used to ask for it
    /// first, in series with the aircraft.
    static func home() async throws -> Coordinate? {
        if DemoFeed.isOn { return DemoFeed.home }
        if let kept = cachedHome, let at = kept.at, Date().timeIntervalSince(at) < 86400 { return kept.home }
        return try await fetchReceiver()
    }
}

/// What the widget shows: how many aircraft are in range, nearest first.
struct Nearby {
    struct Plane {
        /// Which aircraft (for the Watch to pick out the one an alert was about, #61).
        var hex: String = ""
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
            return Plane(hex: a.hex, callsign: cs.isEmpty ? a.hex.uppercased() : cs, altitudeText: alt, distanceNm: br.range, direction: dir,
                         bearing: br.bearing, isNetwork: a.isNetwork)
        }
        .sorted { $0.distanceNm < $1.distanceNm }
        return Nearby(count: planes.count, planes: planes)
    }

    static func load() async throws -> Nearby {
        guard let home = try await AircraftFeedClient.home() else { throw URLError(.cannotParseResponse) }
        return from(try await AircraftFeedClient.fetchAircraft(), home: home)
    }

    /// load(), given up after `seconds` (#86, 2026-10-26). WidgetKit gives a
    /// widget little time, and one that overran was stopped with its old
    /// entry still showing, never saying the radar can't be reached.
    static func load(within seconds: TimeInterval) async -> Nearby? {
        await withTaskGroup(of: Nearby?.self) { g in
            g.addTask { try? await load() }
            g.addTask { try? await Task.sleep(for: .seconds(seconds)); return nil }
            let first = await g.next() ?? nil
            g.cancelAll()
            return first
        }
    }
    /// What a widget or a complication gives it.
    static let widgetSeconds: TimeInterval = 10
}
