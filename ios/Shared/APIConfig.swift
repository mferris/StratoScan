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
    // Stored settings keep their "radome." keys (and the Keychain its
    // "radome.relay.identity" service) on purpose: renaming them would lose
    // every owner's settings and unpair their radars. The App Group and
    // bundle IDs keep "radome" until the company name is settled.
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
/// (WiFi to cellular and back) or a fetch fails. When home doesn't answer and
/// the phone is on a local network, the app's `finder` looks for the paired
/// radar there first (#76): a radar given a new address by the router is back
/// on its home address within a minute, with no typing.
final class Endpoint: @unchecked Sendable {     // its state is behind `lock`
    enum Where: String { case home, away }

    static let shared = Endpoint()

    private let lock = NSLock()
    private var chosen: String?
    private var chosenWhere: Where = .home
    private var checkedAt = Date.distantPast
    private var onLocalNetwork = false
    private var pathKnown = false       // until the monitor's first report, assume it may be local
    private var foundAt = Date.distantPast
    private let monitor = NWPathMonitor()

    /// Set by the app (not the widget or the Watch): finds a paired radar on
    /// the local network, returning its new home address.
    var finder: (@Sendable () async -> String?)? {
        get { lock.withLock { finderHook } }
        set { lock.withLock { finderHook = newValue } }
    }
    private var finderHook: (@Sendable () async -> String?)?
    /// How often the finder may look while home keeps not answering.
    private static let findEvery: TimeInterval = 120

    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            let local = path.status == .satisfied && (path.usesInterfaceType(.wifi) || path.usesInterfaceType(.wiredEthernet))
            self?.lock.withLock { self?.onLocalNetwork = local; self?.pathKnown = true; self?.foundAt = .distantPast }
            self?.invalidate()
        }
        monitor.start(queue: DispatchQueue(label: "stratoscan.endpoint.path"))
    }

    /// The address in use (the last choice; home until something is known).
    var base: String { lock.withLock { chosen } ?? APIConfig.baseURL }
    var whereNow: Where { lock.withLock { chosenWhere } }

    func invalidate() { lock.withLock { checkedAt = .distantPast } }

    @discardableResult
    func resolve(maxAge: TimeInterval = 60) async -> String {
        if let b = lock.withLock({ Date().timeIntervalSince(checkedAt) < maxAge ? chosen : nil }) { return b }
        let home = APIConfig.baseURL
        let away = APIConfig.awayURL
        // Home and the public address are asked at once (2026-10-25). One after
        // the other, away from home the app waited out the home address (1.5 s)
        // and its look round the local network (up to 4 s) before it asked the
        // public address at all, which answers in about a third of a second.
        // Home still wins whenever it answers within its 1.5 s.
        async let homeAnswers = Self.answers(home, timeout: 1.5)
        async let awayAnswers = Self.answersIfAny(away, timeout: 8)
        if await homeAnswers {
            set(home, .home)
            Task { await self.learnAway(from: home) }      // not in the way of the first look
            return home
        }
        let look: (@Sendable () async -> String?)? = lock.withLock {
            // Before the path monitor's first report (the app has just opened)
            // the network is unknown: look anyway, or the first look-up after
            // launch skipped the finder and the radar was found only a minute
            // later (owner's phone, 2026-10-23).
            guard let f = finderHook, onLocalNetwork || !pathKnown,
                  Date().timeIntervalSince(foundAt) > Self.findEvery else { return nil }
            foundAt = Date()
            return f
        }
        if let away, await awayAnswers {
            set(away, .away)
            // Through the public address now, and the finder behind it (#76):
            // if this is home and the router moved the radar, the next look-up
            // goes straight to its new address.
            if let look {
                Task { if await self.found(by: look, home: home) != nil { self.invalidate() } }
            }
            return away
        }
        if let look, let found = await found(by: look, home: home) {
            set(found, .home)
            Task { await self.learnAway(from: found) }
            return found
        }
        set(home, .home)        // nothing answered: stay on home, so the error shows
        return home
    }

    /// A paired radar the finder found at a new home address that answers
    /// there: remembered, so the next look-up goes straight to it.
    private func found(by look: @Sendable () async -> String?, home: String) async -> String? {
        guard let found = await look(), found != home, await Self.answers(found, timeout: 1.5) else { return nil }
        APIConfig.baseURL = found
        return found
    }

    private static func answersIfAny(_ base: String?, timeout: TimeInterval) async -> Bool {
        guard let base else { return false }
        return await answers(base, timeout: timeout)
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
