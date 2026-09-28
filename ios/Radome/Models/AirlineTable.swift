import SwiftUI

struct Airline {
    let name: String
    let iata: String
    let color: Color
}

/// ICAO airline designators (ICAO Doc 8585, a public standard) mapped to a
/// display name, IATA code, and a badge color loosely associated with the
/// carrier — not an attempt at exact brand colors, just visual distinction.
/// Scoped to carriers plausible near a US East Coast receiver; unmapped
/// codes (private GA, unlisted operators) simply get no badge. Kept in sync
/// with the AIRLINES table in the web version's index.html.
enum AirlineTable {
    static let byICAO: [String: Airline] = [
        "AAL": Airline(name: "American Airlines", iata: "AA", color: Color(hex: "#a5342a")),
        "DAL": Airline(name: "Delta Air Lines", iata: "DL", color: Color(hex: "#9c1238")),
        "UAL": Airline(name: "United Airlines", iata: "UA", color: Color(hex: "#1f5fa8")),
        "SWA": Airline(name: "Southwest Airlines", iata: "WN", color: Color(hex: "#b5860f")),
        "JBU": Airline(name: "JetBlue Airways", iata: "B6", color: Color(hex: "#146fa0")),
        "ASA": Airline(name: "Alaska Airlines", iata: "AS", color: Color(hex: "#0f766e")),
        "NKS": Airline(name: "Spirit Airlines", iata: "NK", color: Color(hex: "#a68a00")),
        "FFT": Airline(name: "Frontier Airlines", iata: "F9", color: Color(hex: "#1a7a3c")),
        "AAY": Airline(name: "Allegiant Air", iata: "G4", color: Color(hex: "#1a3a6b")),
        "HAL": Airline(name: "Hawaiian Airlines", iata: "HA", color: Color(hex: "#6a1b4d")),
        "SCX": Airline(name: "Sun Country Airlines", iata: "SY", color: Color(hex: "#0e5c3a")),
        "SKW": Airline(name: "SkyWest Airlines", iata: "OO", color: Color(hex: "#3a4a5a")),
        "ENY": Airline(name: "Envoy Air", iata: "MQ", color: Color(hex: "#3a4a5a")),
        "RPA": Airline(name: "Republic Airways", iata: "YX", color: Color(hex: "#3a4a5a")),
        "PDT": Airline(name: "Piedmont Airlines", iata: "PT", color: Color(hex: "#3a4a5a")),
        "JIA": Airline(name: "PSA Airlines", iata: "OH", color: Color(hex: "#3a4a5a")),
        "EDV": Airline(name: "Endeavor Air", iata: "9E", color: Color(hex: "#3a4a5a")),
        "ASH": Airline(name: "Air Wisconsin", iata: "ZW", color: Color(hex: "#3a4a5a")),
        "GJS": Airline(name: "GoJet Airlines", iata: "G7", color: Color(hex: "#3a4a5a")),
        "FDX": Airline(name: "FedEx Express", iata: "FX", color: Color(hex: "#4b1f7a")),
        "UPS": Airline(name: "UPS Airlines", iata: "5X", color: Color(hex: "#4a3510")),
        "GTI": Airline(name: "Atlas Air", iata: "5Y", color: Color(hex: "#43494f")),
        "ABX": Airline(name: "ABX Air", iata: "GB", color: Color(hex: "#43494f")),
        "BAW": Airline(name: "British Airways", iata: "BA", color: Color(hex: "#1a2a5e")),
        "DLH": Airline(name: "Lufthansa", iata: "LH", color: Color(hex: "#0d3a5c")),
        "ACA": Airline(name: "Air Canada", iata: "AC", color: Color(hex: "#7a1420")),
        "AFR": Airline(name: "Air France", iata: "AF", color: Color(hex: "#1a3a7a")),
        "KLM": Airline(name: "KLM Royal Dutch Airlines", iata: "KL", color: Color(hex: "#0a5c9e")),
        "VIR": Airline(name: "Virgin Atlantic", iata: "VS", color: Color(hex: "#7a1030")),
        "QTR": Airline(name: "Qatar Airways", iata: "QR", color: Color(hex: "#5a1030")),
        "UAE": Airline(name: "Emirates", iata: "EK", color: Color(hex: "#a3151e")),
        "EJA": Airline(name: "NetJets", iata: "EJ", color: Color(hex: "#43494f")),
        "LXJ": Airline(name: "Flexjet", iata: "LX", color: Color(hex: "#43494f")),
    ]

    static let privateLabel = "Private Aircraft"
    static let privateColor = Color(hex: "#44494e")
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
