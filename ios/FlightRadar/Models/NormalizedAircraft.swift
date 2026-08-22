import Foundation

/// Pure, stateless computation from a raw aircraft.json entry — mirrors
/// normalizeAircraft() in the web version exactly, including the decision
/// of when to trust readsb's precomputed r_dst/r_dir vs. deriving bearing/
/// range via haversine ourselves.
struct NormalizedAircraft {
    let hex: String
    let cs: String
    let bearing: Double
    let range: Double
    let alt: Altitude
    let hdg: Double
    let speed: Double?
    let lat: Double?
    let lon: Double?
    let airlineIcao: String?
    let airline: Airline?

    /// - Parameter trustPrecomputed: false when a HOME_OVERRIDE is active —
    ///   r_dst/r_dir are relative to the receiver's real antenna position,
    ///   not an override display center, and must not be used in that case.
    static func normalize(_ a: RawAircraft, home: Coordinate?, trustPrecomputed: Bool) -> NormalizedAircraft? {
        var bearing: Double
        var range: Double

        if trustPrecomputed, let rDst = a.rDst, let rDir = a.rDir {
            range = rDst
            bearing = rDir
        } else if let home, let lat = a.lat, let lon = a.lon {
            let hb = Geo.haversineBearingRange(lat1: home.lat, lon1: home.lon, lat2: lat, lon2: lon)
            bearing = hb.bearing
            range = hb.range
        } else {
            return nil
        }

        let alt = a.altBaro ?? a.altGeom ?? .unknown
        let hdg = a.track ?? a.trueHeading ?? a.magHeading ?? a.calcTrack ?? bearing
        let cs = (a.flight?.trimmingCharacters(in: .whitespaces)).flatMap { $0.isEmpty ? nil : $0 } ?? a.hex.uppercased()

        // scheduled/charter flights are 3 letters + a number (e.g. DAL1234);
        // GA tail numbers (N1182D) and hex-fallback callsigns won't match,
        // and correctly get labeled "Private Aircraft" with no route lookup
        var airlineIcao: String? = nil
        if let range3 = cs.range(of: #"^[A-Z]{3}\d"#, options: .regularExpression) {
            airlineIcao = String(cs[cs.startIndex..<range3.upperBound].dropLast())
        }
        let airline = airlineIcao.flatMap { AirlineTable.byICAO[$0] }

        return NormalizedAircraft(
            hex: a.hex, cs: cs, bearing: bearing, range: range, alt: alt, hdg: hdg,
            speed: a.gs, lat: a.lat, lon: a.lon, airlineIcao: airlineIcao, airline: airline
        )
    }
}

struct Coordinate {
    let lat: Double
    let lon: Double
}
