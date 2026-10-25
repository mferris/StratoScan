import Foundation

/// Real runway/taxiway geometry from OSM's public Overpass API, covering the
/// box the radar shows. Purely additive — if this fails the map/radar keep
/// working without runway outlines. Mirrors the web version's
/// loadRunways()/overpassToGeoJSON().
///
/// Runways don't move, so a copy is kept on the phone and used at once, and
/// Overpass is asked again only once a month (2026-10-25). The public
/// Overpass service is often overloaded (502s and refusals that day), and the
/// app used to wait on it, with no timeout of its own, so up to iOS's 60 s
/// default, before its first look at the radar: over a minute of
/// "connecting" at every launch.
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
    /// to MLNShape(data:encoding:).
    static func fetchRunwayGeoJSON(center: Coordinate, rangeNm: Double) async -> Data? {
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
            let (data, response) = try await URLSession.shared.data(for: req)
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
