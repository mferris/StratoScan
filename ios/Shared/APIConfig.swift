import Foundation

/// Where the radar view reads from. Pairing sets it to the radar's home
/// address (carried in the QR code). Before that, `radome.local` is the
/// factory image's own mDNS name, which works on most home networks. Away
/// from home, a Tailscale name can be entered in Settings.
enum APIConfig {
    private static let key = "flightradar.baseURL"
    static let defaultBaseURL = "http://radome.local"

    /// Shared with the widget (same App Group), so it reads the same radar.
    static let appGroup = "group.com.NelsonIndustries.radome"
    static let shared: UserDefaults = {
        let d = UserDefaults(suiteName: appGroup) ?? .standard
        // One-time move of settings saved before the widget existed.
        if d.string(forKey: key) == nil, let old = UserDefaults.standard.string(forKey: key) {
            d.set(old, forKey: key)
        }
        return d
    }()

    static var baseURL: String {
        get { shared.string(forKey: key) ?? defaultBaseURL }
        set { shared.set(newValue, forKey: key) }
    }

    static func url(_ path: String) -> URL {
        var base = baseURL
        if base.hasSuffix("/") { base.removeLast() }
        return URL(string: base + path)!
    }
}
