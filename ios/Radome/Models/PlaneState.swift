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
        airlineIcao = n.airlineIcao
        airlineLabel = n.airline?.name ?? AirlineTable.privateLabel
        badgeColor = n.airline?.color ?? AirlineTable.privateColor
        lastSeen = Date()
    }

    static func altColor(_ alt: Altitude) -> Color {
        switch alt {
        case .ground: return Color(hex: "#6b8087")
        case .unknown: return Color(hex: "#6b8087")
        case .feet(let ft):
            if ft < 10000 { return Color(hex: "#ffb020") }
            if ft < 25000 { return Color(hex: "#4fd6c8") }
            return Color(hex: "#a78bfa")
        }
    }

    static func altLabel(_ alt: Altitude) -> String {
        switch alt {
        case .ground: return "GND"
        case .unknown: return "----"
        case .feet(let ft): return "FL\(Int((ft / 100).rounded()))"
        }
    }
}
