import SwiftUI

enum LabelSide { case left, right }

/// Mutable per-plane render state — the Swift equivalent of the JS `planes`
/// Map's value objects. A reference type so RadarViewModel/RadarView can
/// update fields in place every frame without rebuilding the whole
/// dictionary (matches the mutation-in-place pattern the web version uses).
final class PlaneState: Identifiable {
    let hex: String
    var id: String { hex }

    var cs: String = ""
    var bearing: Double = 0
    var range: Double = 0
    var targetBearing: Double = 0
    var targetRange: Double = 0
    var alt: Altitude = .unknown
    var hdg: Double = 0
    var speed: Double?
    var lat: Double?
    var lon: Double?
    var airlineIcao: String?
    var airlineLabel: String = AirlineTable.privateLabel
    var badgeColor: Color = AirlineTable.privateColor
    var typeLabel: String?
    var lastSeen: Date = Date()
    /// Reported by a public network, not heard by this radar (roadmap 2.8).
    var isNetwork = false
    /// Route, registration and owner as the core feed has them, if it does.
    var feedRoute: FeedRoute?
    var reg: String?
    var owner: FeedOwner?
    /// True when the core feed labelled this aircraft, so the app needn't.
    var fromFeed = false

    /// Where it has been: its reported positions over the last couple of
    /// minutes, for Sky view's tracks across the sky (#40). Kept on the
    /// phone, from the moment the app opened.
    struct Fix { let lat: Double; let lon: Double; let altFt: Double; let at: Date }
    private(set) var history: [Fix] = []
    static let historySeconds: TimeInterval = 120

    // Screen-space layout state, recomputed every frame by RadarView.
    var anchorX: CGFloat = 0
    var anchorY: CGFloat = 0
    var color: Color = .gray
    var labelX: CGFloat?
    var labelY: CGFloat?
    var labelW: CGFloat = 0
    var labelH: CGFloat = 0
    var labelSide: LabelSide = .right

    init(hex: String, from n: NormalizedAircraft) {
        self.hex = hex
        apply(n)
        bearing = n.bearing
        range = n.range
        targetBearing = n.bearing
        targetRange = n.range
    }

    func apply(_ n: NormalizedAircraft) {
        targetBearing = n.bearing
        targetRange = n.range
        cs = n.cs
        alt = n.alt
        hdg = n.hdg
        speed = n.speed
        lat = n.lat
        lon = n.lon
        if let la = n.lat, let lo = n.lon {
            let now = Date()
            if history.last.map({ $0.lat != la || $0.lon != lo }) ?? true {
                let ft: Double = n.alt == .ground ? 0 : (n.alt.feetValue ?? history.last?.altFt ?? 0)
                history.append(Fix(lat: la, lon: lo, altFt: ft, at: now))
            }
            if let keep = history.firstIndex(where: { now.timeIntervalSince($0.at) <= Self.historySeconds }), keep > 0 {
                history.removeFirst(keep)
            }
            if history.count > 150 { history.removeFirst(history.count - 150) }
        }
        airlineIcao = n.airlineIcao
        isNetwork = n.raw.isNetwork
        fromFeed = n.raw.feedOperator != nil
        feedRoute = n.raw.feedRoute
        if let r = n.raw.reg { reg = r }
        owner = n.raw.owner
        if let name = n.raw.feedType?.name ?? n.raw.feedType?.code { typeLabel = name }
        if let op = n.raw.feedOperator {
            // The radar's own label (deploy/labels.py): the same rules as below,
            // but one copy, shared with the kiosk and the alerts.
            airlineLabel = op.label
            badgeColor = Color(hex: op.color)
        } else if let military = n.military {
            airlineLabel = military
            badgeColor = AirlineTable.militaryColor
        } else {
            airlineLabel = n.airline?.name ?? AirlineTable.privateLabel
            badgeColor = n.airline?.color ?? AirlineTable.privateColor
        }
        lastSeen = Date()
    }

    /// The chosen theme's altitude colour (see Palette).
    static func altColor(_ alt: Altitude) -> Color { Palette.current.altColor(alt) }

    static func altLabel(_ alt: Altitude) -> String {
        switch alt {
        case .ground: return "GND"
        case .unknown: return "----"
        case .feet(let ft): return "FL\(Int((ft / 100).rounded()))"
        }
    }
}
