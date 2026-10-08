import SwiftUI

struct Airline {
    let name: String
    let iata: String
    let color: Color
    /// The airline's own web domain: where its logo mark is fetched from at
    /// run time (#60). Logos are trademarks, so none ships in the app.
    var domain: String? = nil
}

/// ICAO airline designators (ICAO Doc 8585, a public standard) mapped to a
/// display name, IATA code, and a badge color loosely associated with the
/// carrier — not an attempt at exact brand colors, just visual distinction.
/// Scoped to carriers plausible near a US East Coast receiver; unmapped
/// codes (private GA, unlisted operators) simply get no badge. Kept in sync
/// with the AIRLINES table in the web version's index.html.
enum AirlineTable {
    static let byICAO: [String: Airline] = [
        "AAL": Airline(name: "American Airlines", iata: "AA", color: Color(hex: "#a5342a"), domain: "aa.com"),
        "DAL": Airline(name: "Delta Air Lines", iata: "DL", color: Color(hex: "#9c1238"), domain: "delta.com"),
        "UAL": Airline(name: "United Airlines", iata: "UA", color: Color(hex: "#1f5fa8"), domain: "united.com"),
        "SWA": Airline(name: "Southwest Airlines", iata: "WN", color: Color(hex: "#b5860f"), domain: "southwest.com"),
        "JBU": Airline(name: "JetBlue Airways", iata: "B6", color: Color(hex: "#146fa0"), domain: "jetblue.com"),
        "ASA": Airline(name: "Alaska Airlines", iata: "AS", color: Color(hex: "#0f766e"), domain: "alaskaair.com"),
        "NKS": Airline(name: "Spirit Airlines", iata: "NK", color: Color(hex: "#a68a00"), domain: "spirit.com"),
        "FFT": Airline(name: "Frontier Airlines", iata: "F9", color: Color(hex: "#1a7a3c"), domain: "flyfrontier.com"),
        "AAY": Airline(name: "Allegiant Air", iata: "G4", color: Color(hex: "#1a3a6b"), domain: "allegiantair.com"),
        "HAL": Airline(name: "Hawaiian Airlines", iata: "HA", color: Color(hex: "#6a1b4d"), domain: "hawaiianairlines.com"),
        "SCX": Airline(name: "Sun Country Airlines", iata: "SY", color: Color(hex: "#0e5c3a"), domain: "suncountry.com"),
        "SKW": Airline(name: "SkyWest Airlines", iata: "OO", color: Color(hex: "#3a4a5a"), domain: "skywest.com"),
        "ENY": Airline(name: "Envoy Air", iata: "MQ", color: Color(hex: "#3a4a5a"), domain: "envoyair.com"),
        "RPA": Airline(name: "Republic Airways", iata: "YX", color: Color(hex: "#3a4a5a"), domain: "rjet.com"),
        "PDT": Airline(name: "Piedmont Airlines", iata: "PT", color: Color(hex: "#3a4a5a"), domain: "piedmont-airlines.com"),
        "JIA": Airline(name: "PSA Airlines", iata: "OH", color: Color(hex: "#3a4a5a"), domain: "psaairlines.com"),
        "EDV": Airline(name: "Endeavor Air", iata: "9E", color: Color(hex: "#3a4a5a"), domain: "endeavorair.com"),
        "ASH": Airline(name: "Mesa Airlines", iata: "YV", color: Color(hex: "#3a4a5a"), domain: "mesa-air.com"),
        "AWI": Airline(name: "Air Wisconsin", iata: "ZW", color: Color(hex: "#3a4a5a"), domain: "airwis.com"),
        "MXY": Airline(name: "Breeze Airways", iata: "MX", color: Color(hex: "#1d4f91"), domain: "flybreeze.com"),
        "VXP": Airline(name: "Avelo Airlines", iata: "XP", color: Color(hex: "#5b2c83"), domain: "aveloair.com"),
        "GJS": Airline(name: "GoJet Airlines", iata: "G7", color: Color(hex: "#3a4a5a"), domain: "gojetairlines.com"),
        "FDX": Airline(name: "FedEx Express", iata: "FX", color: Color(hex: "#4b1f7a"), domain: "fedex.com"),
        "UPS": Airline(name: "UPS Airlines", iata: "5X", color: Color(hex: "#4a3510"), domain: "ups.com"),
        "GTI": Airline(name: "Atlas Air", iata: "5Y", color: Color(hex: "#43494f"), domain: "atlasair.com"),
        "ABX": Airline(name: "ABX Air", iata: "GB", color: Color(hex: "#43494f"), domain: "abxair.com"),
        "BAW": Airline(name: "British Airways", iata: "BA", color: Color(hex: "#1a2a5e"), domain: "britishairways.com"),
        "DLH": Airline(name: "Lufthansa", iata: "LH", color: Color(hex: "#0d3a5c"), domain: "lufthansa.com"),
        "ACA": Airline(name: "Air Canada", iata: "AC", color: Color(hex: "#7a1420"), domain: "aircanada.com"),
        "AFR": Airline(name: "Air France", iata: "AF", color: Color(hex: "#1a3a7a"), domain: "airfrance.com"),
        "KLM": Airline(name: "KLM Royal Dutch Airlines", iata: "KL", color: Color(hex: "#0a5c9e"), domain: "klm.com"),
        "VIR": Airline(name: "Virgin Atlantic", iata: "VS", color: Color(hex: "#7a1030"), domain: "virginatlantic.com"),
        "QTR": Airline(name: "Qatar Airways", iata: "QR", color: Color(hex: "#5a1030"), domain: "qatarairways.com"),
        "UAE": Airline(name: "Emirates", iata: "EK", color: Color(hex: "#a3151e"), domain: "emirates.com"),
        "EJA": Airline(name: "NetJets", iata: "EJ", color: Color(hex: "#43494f"), domain: "netjets.com"),
        "LXJ": Airline(name: "Flexjet", iata: "LX", color: Color(hex: "#43494f"), domain: "flexjet.com"),
    ]

    static let privateLabel = "Private Aircraft"
    static let privateColor = Color(hex: "#44494e")
    static let militaryColor = Color(hex: "#4b5a3c")

    /// ICAO address blocks allocated to military/government airframes — a copy
    /// of MILITARY_HEX_RANGES in the web version's index.html; keep the two in
    /// sync. Deliberately a conservative subset: a missing range costs a
    /// missed label, a wrong one mislabels a civil aircraft.
    static let militaryHexRanges: [(lo: UInt32, hi: UInt32, who: String)] = [
        (0x33ff00, 0x33ffff, "Italian military"),
        (0x350000, 0x37ffff, "Spanish military"),
        (0x3aa000, 0x3affff, "French military"),
        (0x3b7000, 0x3bffff, "French military"),
        (0x3ea000, 0x3ebfff, "German military"),
        (0x3f4000, 0x3fbfff, "German military"),
        (0x400000, 0x40003f, "UK military"),
        (0x43c000, 0x43cfff, "UK military"),
        (0x480000, 0x480fff, "Dutch military"),
        (0x4b7000, 0x4b7fff, "Swiss military"),
        (0xadf7c8, 0xafffff, "US military"),
        (0xc20000, 0xc3ffff, "Canadian military"),
        (0xe40000, 0xe41fff, "Brazilian military"),
    ]

    /// The military operator an ICAO address belongs to, if any. Keys off the
    /// hex block, which a crew cannot change by typing a different callsign.
    static func militaryOperator(hex: String) -> String? {
        guard let v = UInt32(hex, radix: 16) else { return nil }
        return militaryHexRanges.first { v >= $0.lo && v <= $0.hi }?.who
    }
}

extension Color {
    init(hex: String) {
        var s = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        s.removeAll { $0 == "#" }
        var value: UInt64 = 0
        Scanner(string: s).scanHexInt64(&value)
        let r = Double((value >> 16) & 0xFF) / 255
        let g = Double((value >> 8) & 0xFF) / 255
        let b = Double(value & 0xFF) / 255
        self = Color(red: r, green: g, blue: b)
    }
}
