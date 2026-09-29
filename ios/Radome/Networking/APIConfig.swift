import Foundation

/// Where the radar view reads from. Pairing sets it to the radar's home
/// address (carried in the QR code). Before that, `radome.local` is the
/// factory image's own mDNS name, which works on most home networks. Away
/// from home, a Tailscale name can be entered in Settings.
enum APIConfig {
    private static let key = "flightradar.baseURL"
    static let defaultBaseURL = "http://radome.local"

    static var baseURL: String {
        get { UserDefaults.standard.string(forKey: key) ?? defaultBaseURL }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    static func url(_ path: String) -> URL {
        var base = baseURL
        if base.hasSuffix("/") { base.removeLast() }
        return URL(string: base + path)!
    }
}
