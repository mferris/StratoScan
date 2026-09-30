import Foundation
import Network

/// Where the radar view and widget read from. Two addresses per radar:
///
/// - home: the radar on your WiFi (fast; filled in by pairing). Before
///   pairing, `stratoscan.local` is the factory image's own mDNS name.
/// - away: its public HTTPS address (Tailscale Funnel), when the owner has
///   turned that on. Learned from the pairing QR code, or from the radar
///   itself whenever the phone is home.
///
/// `Endpoint` picks between them automatically.
enum APIConfig {
    private static let homeKey = "flightradar.baseURL"
    private static let awayKey = "radome.awayURL"
    static let defaultBaseURL = "http://stratoscan.local"

    /// Shared with the widget (same App Group), so it reads the same radar.
    static let appGroup = "group.com.NelsonIndustries.radome"
    static let shared: UserDefaults = {
        let d = UserDefaults(suiteName: appGroup) ?? .standard
        // One-time move of settings saved before the widget existed.
        if d.string(forKey: homeKey) == nil, let old = UserDefaults.standard.string(forKey: homeKey) {
            d.set(old, forKey: homeKey)
        }
        return d
    }()

    /// The home address.
    static var baseURL: String {
        get { shared.string(forKey: homeKey) ?? defaultBaseURL }
        set { shared.set(newValue, forKey: homeKey); Endpoint.shared.invalidate() }
    }

    /// The public address, HTTPS only; nil when there is none.
    static var awayURL: String? {
        get { shared.string(forKey: awayKey) }
        set {
            if let v = newValue, v.hasPrefix("https://") { shared.set(v, forKey: awayKey) }
            else { shared.removeObject(forKey: awayKey) }
            Endpoint.shared.invalidate()
        }
    }

    /// A URL on whichever address is in use right now.
    static func url(_ path: String) -> URL {
        var base = Endpoint.shared.base
        if base.hasSuffix("/") { base.removeLast() }
        return URL(string: base + path)!
    }
}

/// Chooses home or away: home when it answers quickly, else away. The choice
/// is kept for a minute, and dropped at once when the phone's network changes
/// (WiFi to cellular and back) or a fetch fails.
final class Endpoint {
    enum Where: String { case home, away }

    static let shared = Endpoint()

    private let lock = NSLock()
    private var chosen: String?
    private var chosenWhere: Where = .home
    private var checkedAt = Date.distantPast
    private let monitor = NWPathMonitor()

    private init() {
        monitor.pathUpdateHandler = { [weak self] _ in self?.invalidate() }
        monitor.start(queue: DispatchQueue(label: "radome.endpoint.path"))
    }

    /// The address in use (the last choice; home until something is known).
    var base: String { lock.withLock { chosen } ?? APIConfig.baseURL }
    var whereNow: Where { lock.withLock { chosenWhere } }

    func invalidate() { lock.withLock { checkedAt = .distantPast } }

    @discardableResult
    func resolve(maxAge: TimeInterval = 60) async -> String {
        if let b = lock.withLock({ Date().timeIntervalSince(checkedAt) < maxAge ? chosen : nil }) { return b }
        let home = APIConfig.baseURL
        if await Self.answers(home, timeout: 1.5) {
            set(home, .home)
            await learnAway(from: home)
            return home
        }
        if let away = APIConfig.awayURL, await Self.answers(away, timeout: 8) {
            set(away, .away)
            return away
        }
        set(home, .home)        // nothing answered: stay on home, so the error shows
        return home
    }

    private func set(_ base: String, _ w: Where) {
        lock.withLock { chosen = base; chosenWhere = w; checkedAt = Date() }
    }

    private static func answers(_ base: String, timeout: TimeInterval) async -> Bool {
        guard let url = URL(string: base.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/tar1090/data/receiver.json") else { return false }
        var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: timeout)
        req.httpMethod = "GET"
        guard let (_, resp) = try? await URLSession.shared.data(for: req) else { return false }
        return (resp as? HTTPURLResponse)?.statusCode == 200
    }

    /// At home, ask the radar for its public address (the setup server's
    /// LAN-only hello), so an already-paired phone learns it with no typing.
    private func learnAway(from home: String) async {
        struct Hello: Decodable { let publicUrl: String? }
        guard let url = URL(string: home.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/setup/api/hello"),
              let (data, resp) = try? await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 3)),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let hello = try? JSONDecoder().decode(Hello.self, from: data) else { return }
        if let pub = hello.publicUrl, pub.hasPrefix("https://"), pub != APIConfig.awayURL {
            APIConfig.shared.set(pub, forKey: "radome.awayURL")
        }
    }
}
