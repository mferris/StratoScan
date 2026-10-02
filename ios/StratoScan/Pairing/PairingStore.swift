import Foundation
import UIKit

/// The radars this phone is paired with. A radar's own screen shows a QR code
/// holding `stratoscan://pair?u=<unit>&s=<one-time secret>&h=<LAN address>`
/// (`radome://` from units before 2026.10.01.2, still accepted);
/// scanning it (Camera app or in-app) lands here. The secret goes to the
/// relay once and is never stored; the LAN address, when present, points the
/// radar view at this radar if it has not been pointed anywhere yet.
@MainActor
final class PairingStore: ObservableObject {
    struct Radar: Codable, Identifiable, Equatable {
        let unit: String
        var name: String
        var host: String?
        var pairedAt: Date
        /// True once the owner names it on this phone; the radar's own name
        /// (roadmap 2.17) then no longer replaces it. Optional so radars
        /// saved before this decode.
        var ownName: Bool?
        var id: String { unit }
    }

    @Published private(set) var radars: [Radar] = []
    @Published var busy = false
    @Published var message: String?

    private let storeKey = "radome.pairedRadars"
    private let relay = RelayClient()

    init() {
        if let data = UserDefaults.standard.data(forKey: storeKey),
           let saved = try? JSONDecoder().decode([Radar].self, from: data) {
            radars = saved
            // Paired before 2.17, nothing recorded whether the owner named it.
            // The app's own default was "Radar N"; anything else they typed.
            var migrated = false
            for i in radars.indices where radars[i].ownName == nil {
                radars[i].ownName = radars[i].name.range(of: #"^Radar \d+$"#, options: .regularExpression) == nil
                migrated = true
            }
            if migrated { save() }
        }
    }

    private func save() {
        if let data = try? JSONEncoder().encode(radars) {
            UserDefaults.standard.set(data, forKey: storeKey)
        }
    }

    struct Link: Equatable {
        let unit: String
        let secret: String
        let host: String?
        var publicURL: String? = nil
        /// The radar's own name, from its setup ("Raleigh"), when the link has one.
        var name: String? = nil
    }

    /// A pairing link, or nil for anything else. Strict about shapes: the
    /// unit id is an Ed25519 key (43 base64url chars), the secret 16-64 chars.
    nonisolated static func parse(_ url: URL) -> Link? {
        guard ["stratoscan", "radome"].contains(url.scheme?.lowercased() ?? ""), url.host?.lowercased() == "pair",
              let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems else { return nil }
        func q(_ n: String) -> String? { items.first { $0.name == n }?.value }
        let b64url = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        guard let u = q("u"), u.count == 43, u.unicodeScalars.allSatisfy(b64url.contains),
              let s = q("s"), (16...64).contains(s.count), s.unicodeScalars.allSatisfy(b64url.contains)
        else { return nil }
        let hostChars = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
        let h = q("h").flatMap { $0.count <= 253 && $0.unicodeScalars.allSatisfy(hostChars.contains) ? $0 : nil }
        // The radar's public address (its Tailscale Funnel), HTTPS only.
        let p = q("p").flatMap { v -> String? in
            guard v.count <= 200, let u = URL(string: v), u.scheme == "https", u.host != nil else { return nil }
            return v
        }
        return Link(unit: u, secret: s, host: h, publicURL: p, name: q("n").flatMap(Self.cleanName))
    }

    /// A radar's name as the radar gives it: 1-32 characters, no control
    /// characters, whitespace tidied. Mirrors setup-server.py's clean_name.
    nonisolated static func cleanName(_ v: String) -> String? {
        let t = v.split(whereSeparator: \.isWhitespace).joined(separator: " ")
        guard (1...32).contains(t.count),
              !t.unicodeScalars.contains(where: { $0.properties.generalCategory == .control
                                                  || $0.properties.generalCategory == .format })
        else { return nil }
        return t
    }

    /// A link waiting for the owner to confirm. Any web page or message can
    /// open a stratoscan:// link, so nothing pairs without an explicit yes.
    @Published var pendingLink: Link?

    /// Handles a scanned or opened link. Returns false when it is not ours.
    @discardableResult
    func handle(_ url: URL) -> Bool {
        guard let link = Self.parse(url) else { return false }
        pendingLink = link
        return true
    }

    func confirmPending() {
        guard let link = pendingLink else { return }
        pendingLink = nil
        Task { await pair(link) }
    }

    func pair(_ link: Link) async {
        busy = true
        defer { busy = false }
        do {
            try await relay.pair(unit: link.unit, secret: link.secret, name: UIDevice.current.name)
            let name = link.name ?? "Radar \(radars.count + 1)"
            if let i = radars.firstIndex(where: { $0.unit == link.unit }) {
                radars[i].host = link.host ?? radars[i].host
                if radars[i].ownName != true, let n = link.name { radars[i].name = n }
            } else {
                radars.append(Radar(unit: link.unit, name: name, host: link.host, pairedAt: Date(), ownName: false))
            }
            save()
            if let h = link.host, APIConfig.baseURL == APIConfig.defaultBaseURL {
                APIConfig.baseURL = "http://\(h)"
            }
            if let p = link.publicURL { APIConfig.awayURL = p }
            message = "Paired. Alerts from this radar will come to this phone."
            // Now the reason for notifications is obvious; ask (once) and register.
            await PushManager.shared.enable()
        } catch {
            message = error.localizedDescription
        }
    }

    func unpair(_ radar: Radar) async {
        busy = true
        defer { busy = false }
        do {
            try await relay.unpair(unit: radar.unit)
            radars.removeAll { $0.unit == radar.unit }
            save()
            message = "Unpaired from \(radar.name)."
        } catch {
            message = error.localizedDescription
        }
    }

    /// Names the radar on this phone. Empty goes back to the radar's own
    /// name, picked up by refreshNames(); unchanged changes nothing.
    func rename(_ radar: Radar, to name: String) {
        guard let i = radars.firstIndex(where: { $0.unit == radar.unit }) else { return }
        let t = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty {
            guard radars[i].ownName == true else { return }
            radars[i].ownName = false
            save()
            Task { await refreshNames() }
            return
        }
        guard t != radars[i].name else { return }
        radars[i].name = String(t.prefix(40))
        radars[i].ownName = true
        save()
    }

    /// Follow a rename made on the radar: ask each radar on the home network
    /// for its name (its setup server's hello, which is LAN-only, so this
    /// only works at home; away, the last name stays). A name set on this
    /// phone wins.
    func refreshNames() async {
        struct Hello: Decodable { let name: String? }
        for radar in radars where radar.ownName != true {
            guard let host = radar.host, let url = URL(string: "http://\(host)/setup/api/hello"),
                  let (data, resp) = try? await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 3)),
                  (resp as? HTTPURLResponse)?.statusCode == 200,
                  let name = (try? JSONDecoder().decode(Hello.self, from: data))?.name.flatMap(Self.cleanName),
                  let i = radars.firstIndex(where: { $0.unit == radar.unit }),
                  radars[i].name != name, radars[i].ownName != true
            else { continue }
            radars[i].name = name
            save()
        }
    }

    /// The relay is the authority: a radar that unpaired this phone from its
    /// own screen (or was factory reset) disappears here too.
    func refresh() async {
        do {
            let live = Set(try await relay.units().map(\.unit))
            let before = radars.count
            radars.removeAll { !live.contains($0.unit) }
            if radars.count != before { save() }
        } catch {
            // Offline: keep what we know; the next refresh settles it.
        }
    }
}
