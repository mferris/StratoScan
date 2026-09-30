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
    /// Only from the core feed (/api/aircraft): the 20 nm ring's counts,
    /// worked out on the radar exactly as the kiosk counts.
    var counts: FeedCounts? = nil
}

// ---- The core feed's labels (roadmap 1.8 / 2.8) -----------------------------
// /api/aircraft carries these alongside readsb's fields, worked out once on
// the radar (deploy/labels.py) so the app, the kiosk and the alerts label an
// aircraft the same way. From plain aircraft.json they are all nil and the
// app labels for itself, as before.
struct FeedCounts: Decodable { let heard: Int?; let notHeard: Int? }
struct FeedOperator: Decodable { let kind: String; let label: String; let color: String }
struct FeedRoute: Decodable { let text: String; let plausible: Bool? }
struct FeedType: Decodable { let code: String?; let name: String?; let desc: String? }
struct FeedOwner: Decodable { let name: String; let country: String? }

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
    // Core feed only; see FeedOperator above.
    let source: String?          // "antenna" or "network"
    let feedOperator: FeedOperator?
    let feedRoute: FeedRoute?
    let feedType: FeedType?
    let reg: String?
    let owner: FeedOwner?

    var isNetwork: Bool { source == "network" }

    enum CodingKeys: String, CodingKey {
        case hex, flight, lat, lon, gs, track, source, reg, owner, alt
        case feedOperator = "operator"
        case feedRoute = "route"
        case feedType = "type"
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
        altBaro = try Self.decodeAltitude(c, .altBaro) ?? Self.decodeAltitude(c, .alt)   // the core feed says "alt"
        altGeom = try Self.decodeAltitude(c, .altGeom)
        source = try? c.decodeIfPresent(String.self, forKey: .source)
        feedOperator = try? c.decodeIfPresent(FeedOperator.self, forKey: .feedOperator)
        feedRoute = try? c.decodeIfPresent(FeedRoute.self, forKey: .feedRoute)
        feedType = try? c.decodeIfPresent(FeedType.self, forKey: .feedType)   // readsb's "type" is a string: nil
        reg = try? c.decodeIfPresent(String.self, forKey: .reg)
        owner = try? c.decodeIfPresent(FeedOwner.self, forKey: .owner)
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
