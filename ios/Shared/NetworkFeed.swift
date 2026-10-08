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

    // A view wider than one disc (the owner's ask, 2026-10-08): several discs on
    // a square grid spaced so they leave no gap, at most 3 x 3 of them covering
    // the middle of the view; the rest of a continent stays empty, and the
    // footer says how far the picture reaches. Asked for less often than one
    // disc, since it is up to nine questions to adsb.lol at once.
    static let singleUpToNm = 190.0          // a view this far out still fits one disc (x1.3 <= 250)
    static let tileNm = Double(maxRadiusNm)
    static let tileSpacingNm = Double(maxRadiusNm) * 2.0.squareRoot()
    static let tileMaxN = 3

    /// Where to ask for a view `halfNm` out from `centre`: one disc round the
    /// middle while it fits, else an n x n grid of 250 nm discs (n <= 3)
    /// covering the middle; and the radius that covers.
    static func discs(around centre: Coordinate, halfNm: Double) -> (discs: [(Coordinate, Double)], coveredNm: Double) {
        if halfNm <= singleUpToNm {
            let r = max(Double(minRadiusNm), min(Double(maxRadiusNm), halfNm * 1.3))
            return ([(centre, r)], r)
        }
        let n = max(2, min(tileMaxN, Int((2 * halfNm / tileSpacingNm).rounded(.up))))
        var out: [(Coordinate, Double)] = []
        for j in 0..<n {
            for i in 0..<n {
                let east = (Double(i) - Double(n - 1) / 2) * tileSpacingNm
                let north = (Double(j) - Double(n - 1) / 2) * tileSpacingNm
                out.append((Geo.moved(centre, east: east, north: north), tileNm))
            }
        }
        return (out, Double(n) * tileSpacingNm / 2)
    }

    /// Between questions, and before one more try after a refusal: adsb.lol
    /// refuses a burst (420 and 429, measured), and wants about one a second.
    static let paceSeconds = 1.2
    static let retrySeconds = 2.5

    /// The aircraft over a view: every disc of `discs`, one after another,
    /// merged by hex. A disc that is refused twice is left out; nil only when
    /// none answered.
    static func fetchView(around centre: Coordinate, halfNm: Double) async -> [(RawAircraft, Extra?)]? {
        let (discs, _) = self.discs(around: centre, halfNm: halfNm)
        if discs.count == 1 { return await fetch(around: discs[0].0, radiusNm: discs[0].1) }
        var merged: [String: (RawAircraft, Extra?)] = [:]
        var answered = false
        for (i, d) in discs.enumerated() {
            if i > 0 { try? await Task.sleep(for: .seconds(paceSeconds)) }
            var list = await fetch(around: d.0, radiusNm: d.1)
            if list == nil {
                try? await Task.sleep(for: .seconds(retrySeconds))
                list = await fetch(around: d.0, radiusNm: d.1)
            }
            guard let got = list else { continue }
            answered = true
            for item in got where merged[item.0.hex] == nil { merged[item.0.hex] = item }
        }
        return answered ? Array(merged.values) : nil
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
