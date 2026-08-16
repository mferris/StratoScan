import Foundation

/// Where the Pi is reached. Defaults to the Tailscale MagicDNS hostname —
/// resolves privately over the tailnet if Tailscale is connected on this
/// device (no public exposure), and also works over plain internet since
/// Funnel is enabled on the same hostname. Override in Settings for a
/// direct LAN address (e.g. http://<radar>) when on home WiFi.
enum APIConfig {
    private static let key = "flightwall.baseURL"
    static let defaultBaseURL = "https://[funnel-hostname-redacted]"

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
