import Foundation
import UIKit

/// The radars this phone is paired with. A radar's own screen shows a QR code
/// holding `radome://pair?u=<unit>&s=<one-time secret>&h=<LAN address>`;
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
    }

    /// A pairing link, or nil for anything else. Strict about shapes: the
    /// unit id is an Ed25519 key (43 base64url chars), the secret 16-64 chars.
    nonisolated static func parse(_ url: URL) -> Link? {
        guard url.scheme?.lowercased() == "radome", url.host?.lowercased() == "pair",
              let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems else { return nil }
        func q(_ n: String) -> String? { items.first { $0.name == n }?.value }
        let b64url = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        guard let u = q("u"), u.count == 43, u.unicodeScalars.allSatisfy(b64url.contains),
              let s = q("s"), (16...64).contains(s.count), s.unicodeScalars.allSatisfy(b64url.contains)
        else { return nil }
        let hostChars = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
        let h = q("h").flatMap { $0.count <= 253 && $0.unicodeScalars.allSatisfy(hostChars.contains) ? $0 : nil }
        return Link(unit: u, secret: s, host: h)
    }

    /// Handles a scanned or opened link. Returns false when it is not ours.
    @discardableResult
    func handle(_ url: URL) -> Bool {
        guard let link = Self.parse(url) else { return false }
        Task { await pair(link) }
        return true
    }

    func pair(_ link: Link) async {
        busy = true
        defer { busy = false }
        do {
            try await relay.pair(unit: link.unit, secret: link.secret, name: UIDevice.current.name)
            let name = "Radar \(radars.count + 1)"
            if let i = radars.firstIndex(where: { $0.unit == link.unit }) {
                radars[i].host = link.host ?? radars[i].host
            } else {
                radars.append(Radar(unit: link.unit, name: name, host: link.host, pairedAt: Date()))
            }
            save()
            if let h = link.host, APIConfig.baseURL == APIConfig.defaultBaseURL {
                APIConfig.baseURL = "http://\(h)"
            }
            message = "Paired. Alerts from this radar will come to this phone."
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

    func rename(_ radar: Radar, to name: String) {
        guard let i = radars.firstIndex(of: radar) else { return }
        let t = name.trimmingCharacters(in: .whitespacesAndNewlines)
        radars[i].name = t.isEmpty ? radar.name : String(t.prefix(40))
        save()
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
