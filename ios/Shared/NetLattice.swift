import Foundation

/// The relay's fixed world lattice of 250 nm discs (relay/src/netcache.js,
/// deploy/network-compare.py), so the app asks for the same discs the radars
/// fetch and share (#68). The relay refuses a disc that is not on its
/// lattice, so the formulas here are kept identical to its own; the test
/// (tests/test_app_netcache.py) compiles this file and checks it lands on
/// the relay's centres.
///
/// Rows of centres every 180/rows degrees of latitude (about 348 nm), and
/// in each row as many as fit `spacingNm` apart, so every point on Earth is
/// inside at least one disc and never more than ~248 nm from its nearest
/// centre.
enum NetLattice {
    struct Centre: Equatable { let lat: Double; let lon: Double }

    static let discNm = 250.0
    static let spacingNm = discNm * 2.0.squareRoot()
    static let rows = Int((10800 / spacingNm).rounded(.up))     // 31, pole to pole
    static let rowStep = 180 / Double(rows)
    /// A view is "inside" a disc with this to spare, never on its rim.
    static let slackNm = 2.0

    static func cols(_ lat: Double) -> Int {
        max(1, Int((21600 * cos(lat * .pi / 180) / spacingNm).rounded(.up)))
    }

    /// The centre whose cell holds (lat, lon).
    static func centre(_ lat: Double, _ lon: Double) -> Centre {
        let k = min(rows - 1, max(0, Int(floor((lat + 90) / rowStep))))
        let clat = -90 + (Double(k) + 0.5) * rowStep
        let n = cols(clat), dlon = 360 / Double(n)
        let j = ((Int(floor((lon + 180) / dlon)) % n) + n) % n
        return Centre(lat: round4(clat), lon: round4(-180 + (Double(j) + 0.5) * dlon))
    }

    /// Centres within `withinNm` of a point, nearest first.
    static func centres(_ lat: Double, _ lon: Double, within withinNm: Double) -> [(nm: Double, centre: Centre)] {
        var out: [(nm: Double, centre: Centre)] = []
        var seen = Set<String>()
        let span = Int(withinNm / 60 / rowStep) + 2
        let k0 = Int(floor((lat + 90) / rowStep))
        for k in max(0, k0 - span)..<min(rows, k0 + span + 1) {
            let clat = -90 + (Double(k) + 0.5) * rowStep
            let n = cols(clat), dlon = 360 / Double(n)
            let across = Int(withinNm / (60 * max(0.05, cos(clat * .pi / 180))) / dlon) + 2
            let j0 = Int(floor((lon + 180) / dlon))
            for j in (j0 - across)...(j0 + across) {
                let c = Centre(lat: round4(clat), lon: round4(-180 + (Double(((j % n) + n) % n) + 0.5) * dlon))
                guard seen.insert("\(c.lat),\(c.lon)").inserted else { continue }
                let d = nm(lat, lon, c.lat, c.lon)
                if d <= withinNm { out.append((d, c)) }
            }
        }
        // ties (at a pole) as the unit breaks them, so both pick the same disc
        return out.sorted { ($0.nm, $0.centre.lat, $0.centre.lon) < ($1.nm, $1.centre.lat, $1.centre.lon) }
    }

    /// The one disc that holds a whole view `wantNm` round (lat, lon), with
    /// `slackNm` to spare, or nil when no single disc does (a wide view, or
    /// one near the edge of its cell).
    static func holding(_ lat: Double, _ lon: Double, wantNm: Double) -> Centre? {
        guard let nearest = centres(lat, lon, within: wantNm + discNm).first,
              nearest.nm <= discNm - slackNm - wantNm else { return nil }
        return nearest.centre
    }

    /// As the relay's `Number(x.toFixed(4))` and the unit's `round(x, 4)`.
    static func round4(_ x: Double) -> Double { (x * 10000).rounded() / 10000 }

    /// Great-circle distance in nm, as the relay measures it.
    static func nm(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double {
        let r = Double.pi / 180, p1 = lat1 * r, p2 = lat2 * r
        let a = pow(sin((p2 - p1) / 2), 2) + cos(p1) * cos(p2) * pow(sin((lon2 - lon1) * r / 2), 2)
        return 3440.065 * 2 * asin(min(1, a.squareRoot()))
    }
}
