import Foundation

/// Real runway/taxiway geometry from OpenStreetMap, covering the box the
/// radar shows. Purely additive — if this fails the map/radar keep working
/// without runway outlines.
///
/// Runways don't move, so a copy is kept on the phone and used at once, and
/// asked for again only once a month (2026-10-25). The public Overpass
/// service is often overloaded (502s and refusals that day), and the app used
/// to wait on it, with no timeout of its own, so up to iOS's 60 s default,
/// before its first look at the radar: over a minute of "connecting" at
/// every launch.
///
/// The radar keeps the outlines for its ring too (#87, 2026-10-26), built
/// once a month by deploy/offline-map.py, and hands the same file to the
/// kiosk, its public page and the app, so the app asks it first. Overpass
/// is asked directly, as the web version's loadRunways()/overpassToGeoJSON()
/// did, only when the radar can't answer and the phone has no copy at all.
enum RunwayClient {
    private static let overpassURL = URL(string: "https://overpass-api.de/api/interpreter")!
    static let keepFor: TimeInterval = 30 * 86400
    /// The box is centred on the radar rounded to 0.05° (about 5 km), as every
    /// other place the app asks about is, and widened to cover the ring
    /// anyway: centred exactly, it gave Overpass the radar's position.
    static let roundingPadNm = 2.5

    private static func rounded(_ c: Coordinate) -> Coordinate {
        Coordinate(lat: (c.lat * 20).rounded() / 20, lon: (c.lon * 20).rounded() / 20)
    }

    private static func cacheFile(_ centre: Coordinate, _ rangeNm: Double) -> URL? {
        guard let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else { return nil }
        return dir.appendingPathComponent(String(format: "runways-%.2f_%.2f_%.0f.geojson", centre.lat, centre.lon, rangeNm))
    }

    /// The phone's copy, if it has one, and whether it is still fresh.
    static func cachedRunwayGeoJSON(center: Coordinate, rangeNm: Double) -> (data: Data, fresh: Bool)? {
        guard let url = cacheFile(rounded(center), rangeNm), let data = try? Data(contentsOf: url) else { return nil }
        let when = (try? url.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
        return (data, when.map { Date().timeIntervalSince($0) < keepFor } ?? false)
    }

    private struct OverpassElement: Decodable {
        let type: String
        let id: Int64
        let lat: Double?
        let lon: Double?
        let nodes: [Int64]?
        let tags: [String: String]?
    }
    private struct OverpassResponse: Decodable {
        let elements: [OverpassElement]
    }

    /// Returns raw GeoJSON `Data` (a FeatureCollection of LineStrings, each
    /// with an "aeroway" property of "runway" or "taxiway") ready to hand
    /// to MLNShape(data:encoding:): the radar's copy, else Overpass's
    /// answer, but only when the phone has none (a copy past its month is
    /// still the right runways).
    static func fetchRunwayGeoJSON(center: Coordinate, rangeNm: Double) async -> Data? {
        if let kept = await fromRadar(center: center, rangeNm: rangeNm) { return kept }
        guard cachedRunwayGeoJSON(center: center, rangeNm: rangeNm) == nil, !Task.isCancelled else { return nil }
        return await fromOverpass(center: center, rangeNm: rangeNm)
    }

    /// The radar's copy (/api/runways, core-feed.py), through whichever of
    /// its addresses answers: for its position rounded to 0.05°, and 2.5 nm
    /// past the ring. Taken when its centre is within 0.05° of this one: the
    /// position the app has is rounded to 0.01° away from home, and rounding
    /// that again can land one step over. Kept on the phone as Overpass's
    /// answer was. Nil when the radar hasn't one (a radar before #87, or one
    /// still building it) or can't be reached.
    private static func fromRadar(center: Coordinate, rangeNm: Double) async -> Data? {
        if DemoFeed.isOn { return nil }     // the radar's runways are not the recording's
        let centre = rounded(center)
        await Endpoint.shared.resolve()
        var req = URLRequest(url: APIConfig.url("/api/runways"), timeoutInterval: 4)
        req.setValue("1", forHTTPHeaderField: AircraftFeedClient.appHeader)
        guard let (data, response) = try? await URLSession.radar.data(for: req),
              (response as? HTTPURLResponse)?.statusCode == 200,
              let doc = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              doc["type"] as? String == "FeatureCollection",
              let c = doc["centre"] as? [Double], c.count == 2,
              abs(c[0] - centre.lat) <= 0.05 + 1e-9, abs(c[1] - centre.lon) <= 0.05 + 1e-9,
              let features = doc["features"] as? [[String: Any]], !features.isEmpty,
              // only what the map needs; the radar's notes (when, the licence) stay behind
              let geojson = try? JSONSerialization.data(withJSONObject: ["type": "FeatureCollection", "features": features])
        else { return nil }
        if let url = cacheFile(centre, rangeNm) { try? geojson.write(to: url, options: .atomic) }
        return geojson
    }

    private static func fromOverpass(center: Coordinate, rangeNm: Double) async -> Data? {
        let centre = rounded(center)
        let bb = Geo.rangeBBox(lat: centre.lat, lon: centre.lon, rangeNm: rangeNm + roundingPadNm)
        let query = """
        [out:json][timeout:25];(way["aeroway"="runway"](\(bb.south),\(bb.west),\(bb.north),\(bb.east));\
        way["aeroway"="taxiway"](\(bb.south),\(bb.west),\(bb.north),\(bb.east)););out body;>;out skel qt;
        """

        var req = URLRequest(url: overpassURL)
        req.httpMethod = "POST"
        req.timeoutInterval = 15
        req.setValue("StratoScan/1.0 (iOS app; +https://github.com/mferris/StratoScan)", forHTTPHeaderField: "User-Agent")
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = "data=\(query)".addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed).map { Data($0.utf8) }

        do {
            let (data, response) = try await URLSession.bounded.data(for: req)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
            let parsed = try JSONDecoder().decode(OverpassResponse.self, from: data)
            let geojson = buildGeoJSON(parsed.elements)
            if let geojson, let url = cacheFile(centre, rangeNm) { try? geojson.write(to: url, options: .atomic) }
            return geojson
        } catch {
            return nil // offline or Overpass unavailable
        }
    }

    private static func buildGeoJSON(_ elements: [OverpassElement]) -> Data? {
        var nodeCoords: [Int64: [Double]] = [:]
        for el in elements where el.type == "node" {
            if let lat = el.lat, let lon = el.lon { nodeCoords[el.id] = [lon, lat] }
        }

        var features: [[String: Any]] = []
        for el in elements where el.type == "way" {
            guard let tags = el.tags, let aeroway = tags["aeroway"],
                  aeroway == "runway" || aeroway == "taxiway",
                  let nodeIds = el.nodes else { continue }
            let coords = nodeIds.compactMap { nodeCoords[$0] }
            guard coords.count >= 2 else { continue }
            features.append([
                "type": "Feature",
                "properties": ["aeroway": aeroway],
                "geometry": ["type": "LineString", "coordinates": coords],
            ])
        }
        guard !features.isEmpty else { return nil }

        let collection: [String: Any] = ["type": "FeatureCollection", "features": features]
        return try? JSONSerialization.data(withJSONObject: collection)
    }
}
