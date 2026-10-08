import Foundation

/// The public network's aircraft around a point, from adsb.lol (ODbL):
/// around the phone when it is away from the radar or has none, and around
/// wherever the view has been panned to (roadmap 2.13, 2.21, 2.23).
///
/// The point asked for is rounded to about 5 km first: enough to find the
/// sky's aircraft, not enough to find a house. Nothing else about the phone
/// is sent.
enum NetworkFeed {
    /// adsb.lol answers point queries up to this radius.
    static let maxRadiusNm = 250
    static let minRadiusNm = 25

    static func rounded(_ c: Coordinate) -> Coordinate {
        Coordinate(lat: (c.lat * 20).rounded() / 20, lon: (c.lon * 20).rounded() / 20)
    }

    private struct Response: Decodable { let ac: [RawAircraft]? }
    struct Extra: Decodable { let hex: String; let r: String?; let t: String? }
    private struct ExtraResponse: Decodable { let ac: [Extra]? }

    /// The aircraft within `radiusNm` of `centre` (clamped to what adsb.lol
    /// serves), with the registration and type the network knows.
    static func fetch(around centre: Coordinate, radiusNm: Double = Double(minRadiusNm)) async -> [(RawAircraft, Extra?)]? {
        let at = rounded(centre)
        let radius = max(minRadiusNm, min(maxRadiusNm, Int(radiusNm.rounded())))
        guard let url = URL(string: String(format: "https://api.adsb.lol/v2/point/%.2f/%.2f/%d", at.lat, at.lon, radius)) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("StratoScan/1.0 (iOS app)", forHTTPHeaderField: "User-Agent")
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let list = try? JSONDecoder().decode(Response.self, from: data).ac else { return nil }
        let extras = (try? JSONDecoder().decode(ExtraResponse.self, from: data).ac) ?? []
        let byHex = Dictionary(extras.map { ($0.hex, $0) }, uniquingKeysWith: { a, _ in a })
        return list.map { ($0, byHex[$0.hex]) }
    }
}
