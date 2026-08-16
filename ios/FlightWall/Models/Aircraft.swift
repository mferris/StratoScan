import Foundation

/// readsb reports altitude as either a number (feet) or the literal string
/// "ground" — mirrors the `alt === 'ground' ? 'ground' : ...` check in the
/// web version's normalizeAircraft().
enum Altitude: Equatable {
    case feet(Double)
    case ground
    case unknown

    var isGround: Bool { self == .ground }

    var feetValue: Double? {
        if case .feet(let v) = self { return v }
        return nil
    }
}

struct AircraftFeedResponse: Decodable {
    let aircraft: [RawAircraft]
    let now: Double?
}

/// Raw shape of one entry in aircraft.json, decoded permissively — most
/// fields are optional since readsb omits whatever it hasn't received yet.
struct RawAircraft: Decodable {
    let hex: String
    let flight: String?
    let lat: Double?
    let lon: Double?
    let altBaro: Altitude?
    let altGeom: Altitude?
    let gs: Double?
    let track: Double?
    let trueHeading: Double?
    let magHeading: Double?
    let calcTrack: Double?
    let rDst: Double?
    let rDir: Double?

    enum CodingKeys: String, CodingKey {
        case hex, flight, lat, lon, gs, track
        case altBaro = "alt_baro"
        case altGeom = "alt_geom"
        case trueHeading = "true_heading"
        case magHeading = "mag_heading"
        case calcTrack = "calc_track"
        case rDst = "r_dst"
        case rDir = "r_dir"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        hex = try c.decode(String.self, forKey: .hex)
        flight = try c.decodeIfPresent(String.self, forKey: .flight)
        lat = try c.decodeIfPresent(Double.self, forKey: .lat)
        lon = try c.decodeIfPresent(Double.self, forKey: .lon)
        gs = try c.decodeIfPresent(Double.self, forKey: .gs)
        track = try c.decodeIfPresent(Double.self, forKey: .track)
        trueHeading = try c.decodeIfPresent(Double.self, forKey: .trueHeading)
        magHeading = try c.decodeIfPresent(Double.self, forKey: .magHeading)
        calcTrack = try c.decodeIfPresent(Double.self, forKey: .calcTrack)
        rDst = try c.decodeIfPresent(Double.self, forKey: .rDst)
        rDir = try c.decodeIfPresent(Double.self, forKey: .rDir)
        altBaro = try Self.decodeAltitude(c, .altBaro)
        altGeom = try Self.decodeAltitude(c, .altGeom)
    }

    private static func decodeAltitude(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) throws -> Altitude? {
        if let v = try? c.decodeIfPresent(Double.self, forKey: key) {
            return .feet(v)
        }
        if let s = try? c.decodeIfPresent(String.self, forKey: key), s == "ground" {
            return .ground
        }
        return nil
    }
}

struct ReceiverResponse: Decodable {
    let lat: Double?
    let lon: Double?
}
