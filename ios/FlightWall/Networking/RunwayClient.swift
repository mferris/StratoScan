import Foundation

/// One-time fetch (home location never changes at runtime) of real runway/
/// taxiway geometry from OSM's public Overpass API, covering the same
/// RANGE_NM box the radar shows. Purely additive — if this fails the
/// map/radar keep working without runway outlines. Mirrors the web
/// version's loadRunways()/overpassToGeoJSON().
enum RunwayClient {
    private static let overpassURL = URL(string: "https://overpass-api.de/api/interpreter")!

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
        let bb = Geo.rangeBBox(lat: center.lat, lon: center.lon, rangeNm: rangeNm)
        let query = """
        [out:json][timeout:25];(way["aeroway"="runway"](\(bb.south),\(bb.west),\(bb.north),\(bb.east));\
        way["aeroway"="taxiway"](\(bb.south),\(bb.west),\(bb.north),\(bb.east)););out body;>;out skel qt;
        """

        var req = URLRequest(url: overpassURL)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = "data=\(query)".addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed).map { Data($0.utf8) }

        do {
            let (data, response) = try await URLSession.shared.data(for: req)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
            let parsed = try JSONDecoder().decode(OverpassResponse.self, from: data)
            return buildGeoJSON(parsed.elements)
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
