import SwiftUI

/// The radar's colour themes, in the app (#43). The same four as the kiosk,
/// with its colours: each is index.html's `[data-theme]` block. Daylight is
/// the default, as on the kiosk, and first in the list. Chosen in Settings and
/// kept on the phone; the Watch and widgets stay dark.
struct Palette: Identifiable, Equatable {
    let id: String
    let name: String
    let detail: String
    /// Sheets, settings and the details panel follow this.
    let dark: Bool
    let bg, ring, ringBright, ringLabel, crosshair, compass, sweep: Color
    let textDim, text, low, mid, high, ground, bad, panel: Color
    /// The map under the radar: the kiosk's `--map-filter`.
    let mapFilter: MapFilter
    /// Place-name labels on the map: dark-on-light for Daylight, the other
    /// way round on the darkened maps (the kiosk's recolorLabels).
    let mapLabel, mapHalo, mapWater: Color

    enum MapFilter: Equatable {
        /// brightness multiplied, saturation scaled
        case tone(brightness: Double, saturation: Double)
        /// the Retro Radar's green phosphor: inverted, grey, tinted green
        case phosphor
    }

    static let storageKey = "stratoscan.theme"

    static let daylight = Palette(
        id: "daylight", name: "Daylight", detail: "Light background, dark text, for a bright room", dark: false,
        bg: Color(hex: "#eaf3f1"), ring: Color(hex: "#bfdcd6"), ringBright: Color(hex: "#93bfb6"),
        ringLabel: Color(hex: "#4b6066"), crosshair: Color(hex: "#a9c9c2"), compass: Color(hex: "#33484c"),
        sweep: Color(hex: "#c97a00"), textDim: Color(hex: "#4b6066"), text: Color(hex: "#10181a"),
        low: Color(hex: "#b45f06"), mid: Color(hex: "#0f7a6c"), high: Color(hex: "#6b3fa0"),
        ground: Color(hex: "#5c6b6e"), bad: Color(hex: "#c0202e"), panel: Color.white.opacity(0.85),
        mapFilter: .tone(brightness: 1.0, saturation: 0.9),
        mapLabel: Color(hex: "#1a2426"), mapHalo: Color(hex: "#f3f8f6"), mapWater: Color(hex: "#1d5fa8"))

    static let classic = Palette(
        id: "classic", name: "Classic", detail: "The original look: dark background, warm accent colours", dark: true,
        bg: Color(hex: "#0a0d0f"), ring: Color(hex: "#1c3236"), ringBright: Color(hex: "#2a4a4f"),
        // brighter than the kiosk's #3d5a5f: zoomed in, the app's ring labels sit over busy streets
        ringLabel: Color(hex: "#7d9ca1"), crosshair: Color(hex: "#16282b"), compass: Color(hex: "#4a6b70"),
        sweep: Color(hex: "#ffb020"), textDim: Color(hex: "#5b7278"), text: Color(hex: "#cfe8ea"),
        low: Color(hex: "#ffb020"), mid: Color(hex: "#4fd6c8"), high: Color(hex: "#a78bfa"),
        ground: Color(hex: "#6b8087"), bad: Color(hex: "#ff5d5d"), panel: Color(hex: "#05080a").opacity(0.78),
        // the kiosk's brightness(0.44) saturate(1.5); the app had 0.36, darker than the kiosk
        mapFilter: .tone(brightness: 0.44, saturation: 1.5),
        mapLabel: Color(hex: "#e8e2d5"), mapHalo: Color(hex: "#05080a"), mapWater: Color(hex: "#9fc4e8"))

    static let highContrast = Palette(
        id: "highcontrast", name: "High Contrast",
        detail: "For low vision and colour blindness: true black, colour-blind-safe accents (Okabe–Ito)", dark: true,
        bg: .black, ring: Color(hex: "#3a3a3a"), ringBright: Color(hex: "#6e6e6e"),
        ringLabel: Color(hex: "#cfcfcf"), crosshair: Color(hex: "#4a4a4a"), compass: Color(hex: "#f2f2f2"),
        sweep: Color(hex: "#ffd400"), textDim: Color(hex: "#d8d8d8"), text: .white,
        low: Color(hex: "#e69f00"), mid: Color(hex: "#56b4e9"), high: Color(hex: "#cc79a7"),
        ground: Color(hex: "#999999"), bad: Color(hex: "#ff4d4d"), panel: Color.black.opacity(0.92),
        mapFilter: .tone(brightness: 0.15, saturation: 0.4),
        mapLabel: Color(hex: "#e8e2d5"), mapHalo: Color(hex: "#05080a"), mapWater: Color(hex: "#9fc4e8"))

    static let radar = Palette(
        id: "radar", name: "Retro Radar", detail: "An old CRT radar screen: black, phosphor green", dark: true,
        bg: .black, ring: Color(hex: "#0b3d0b"), ringBright: Color(hex: "#1f7a1f"),
        ringLabel: Color(hex: "#4ee44e"), crosshair: Color(hex: "#145214"), compass: Color(hex: "#6dff6d"),
        sweep: Color(hex: "#39ff14"), textDim: Color(hex: "#45d645"), text: Color(hex: "#8cff8c"),
        low: Color(hex: "#b6ff3d"), mid: Color(hex: "#33ff33"), high: Color(hex: "#33ffc4"),
        ground: Color(hex: "#2f6b2f"), bad: Color(hex: "#ff3b3b"), panel: Color(hex: "#000c00").opacity(0.8),
        mapFilter: .phosphor,
        mapLabel: Color(hex: "#e8e2d5"), mapHalo: Color(hex: "#05080a"), mapWater: Color(hex: "#9fc4e8"))

    static let all = [daylight, classic, highContrast, radar]

    static func named(_ id: String?) -> Palette { all.first { $0.id == id } ?? daylight }

    /// The chosen theme. Read where drawing happens, so a change shows at once.
    static var current: Palette { named(UserDefaults.standard.string(forKey: storageKey)) }

    /// Altitude colours, as on the radar: low, middle, high, and the ground.
    func altColor(_ alt: Altitude) -> Color {
        switch alt {
        case .ground, .unknown: return ground
        case .feet(let ft): return ft < 10000 ? low : ft < 25000 ? mid : high
        }
    }
}

extension View {
    /// The map under the radar, treated as the kiosk's `--map-filter` does.
    @ViewBuilder func mapFilter(_ f: Palette.MapFilter) -> some View {
        switch f {
        case .tone(let brightness, let saturation):
            if brightness < 1 {
                self.saturation(saturation).colorMultiply(Color(white: brightness))
            } else {
                self.saturation(saturation)
            }
        case .phosphor:
            // dark land and bright roads after the invert, then tinted green
            colorInvert().grayscale(1).colorMultiply(Color(red: 0.22, green: 0.95, blue: 0.28))
        }
    }
}
