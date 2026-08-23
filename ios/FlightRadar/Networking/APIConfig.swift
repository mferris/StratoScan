import Foundation

/// Where the Pi is reached. `raspberrypi.local` is Raspberry Pi OS's own
/// default mDNS hostname, so this works out of the box on most home
/// networks without editing anything -- override it in Settings with your
/// own Tailscale MagicDNS hostname (resolves privately over the tailnet, and
/// over plain internet too if Funnel is enabled on it) or a direct LAN
/// address for lower latency at home.
enum APIConfig {
    private static let key = "flightradar.baseURL"
    static let defaultBaseURL = "http://raspberrypi.local"

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
