import CoreLocation
import CryptoKit
import Foundation
import NetworkExtension
import UIKit

/// Setting up a new radar from the app (roadmap 2.18).
///
/// A new radar's first-run screen shows one QR code:
///   stratoscan://setup?c=<claim code>&w=<setup network>&k=<password>&a=<address>
///   stratoscan://setup?c=<claim code>&h=<LAN address>     (already on a network)
/// Everything in it is on the screen in words too; the code saves typing it.
///
/// The flow, all from the phone:
/// 1. Join the radar's setup network (NEHotspotConfiguration), unless it's
///    already on the home network.
/// 2. Claim it with the code, with an admin password the app makes and keeps
///    in the Keychain.
/// 3. Location (the phone's: it is standing next to the radar), the nearest
///    airport, the time zone and region, and a name.
/// 4. The home WiFi. The radar joins it in the background and confirms once
///    it is really online: the setup network goes when it leaves, and the
///    phone with it, so the phone can't confirm (deploy/setup-server.py,
///    join_in_background).
/// 5. Pairing, with no second QR code: the phone made a one-time secret and
///    gave the radar only its SHA-256, which the radar offers to the relay
///    once online. Back on its own WiFi, the phone pairs with the secret.
/// 6. Find the radar on the home network by name (<hostname>.local).
@MainActor
final class RadarSetup: ObservableObject {
    struct Link: Equatable {
        let code: String
        let ssid: String?
        let psk: String?
        let address: String?
        let lan: String?
        /// SHA-256 (hex) of the radar's own certificate, from the link on its
        /// screen: then the flow runs over https and accepts only that
        /// certificate (security review 2026-10-04, item 9). A radar made
        /// before certificates has none, and keeps plain http.
        var fingerprint: String? = nil
        /// Where the radar answers during setup.
        var base: String { "\(fingerprint == nil ? "http" : "https")://\(address ?? lan ?? "10.42.0.1")" }
        var onSetupNetwork: Bool { ssid != nil }
    }

    enum Step: Equatable {
        case joining, claiming, details, name, wifi, switching, pairing, finding, done
        case failed(String)
    }

    struct Network: Decodable, Identifiable, Hashable {
        let ssid: String
        let signal: Int?
        let secured: Bool?
        var id: String { ssid }
    }

    @Published var link: Link?
    /// A setup link waiting for the owner's yes. Anything can open a
    /// stratoscan:// link, and this flow joins a WiFi network and sends it a
    /// WiFi password, so nothing starts from a link without an explicit tap.
    /// A code scanned on purpose from Settings skips this (start directly).
    @Published var pendingLink: Link?
    @Published private(set) var step: Step = .joining
    @Published private(set) var detail = ""
    @Published var name = ""
    @Published private(set) var networks: [Network] = []
    @Published var ssid = ""
    @Published var psk = ""
    @Published private(set) var busy = false

    private var token: String?
    private var unit: String?
    private var hostname: String?
    private var secret: String?
    private var pairing: PairingStore?

    var active: Bool { link != nil }

    // MARK: - The link

    /// Only a home-network address: a private IPv4 address, with an optional
    /// port, or a .local name. The setup flow sends a WiFi password and makes
    /// an admin password for whatever answers here, so a link must not be able
    /// to point it at a host on the internet.
    nonisolated static func isPrivateHost(_ v: String) -> Bool {
        let host = v.split(separator: ":", maxSplits: 1).first.map(String.init) ?? ""
        let port = v.contains(":") ? String(v.split(separator: ":", maxSplits: 1).last ?? "") : nil
        if let p = port, Int(p).map({ !(1...65535).contains($0) }) ?? true { return false }
        if host.hasSuffix(".local") {
            return host.count <= 64 && host.range(of: #"^[a-z0-9]([a-z0-9-]*[a-z0-9])?\.local$"#, options: [.regularExpression, .caseInsensitive]) != nil
        }
        let segs = host.split(separator: ".", omittingEmptySubsequences: false)
        let parts = segs.compactMap { Int($0) }
        // every segment a number: "10.0.0.1.evil.com" is not an address
        guard segs.count == 4, parts.count == 4, parts.allSatisfy({ (0...255).contains($0) }) else { return false }
        return parts[0] == 10 || (parts[0] == 192 && parts[1] == 168) || (parts[0] == 172 && (16...31).contains(parts[1]))
    }

    nonisolated static func parse(_ url: URL) -> Link? {
        guard ["stratoscan", "radome"].contains(url.scheme?.lowercased() ?? ""), url.host?.lowercased() == "setup",
              let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems else { return nil }
        func q(_ n: String) -> String? { items.first { $0.name == n }?.value }
        guard let c = q("c"), (4...32).contains(c.count) else { return nil }
        func addr(_ v: String?) -> String? { v.flatMap { isPrivateHost($0) ? $0 : nil } }
        let w = q("w").flatMap { (1...32).contains($0.utf8.count) ? $0 : nil }
        let k = q("k").flatMap { (8...63).contains($0.count) ? $0 : nil }
        let a = addr(q("a")), h = addr(q("h"))
        let f = q("f").flatMap { $0.count == 64 && $0.allSatisfy(\.isHexDigit) ? $0.lowercased() : nil }
        guard (w != nil && k != nil) || h != nil else { return nil }
        return Link(code: c, ssid: w, psk: k, address: w != nil ? a : nil, lan: w == nil ? h : nil, fingerprint: f)
    }

    /// Handles an opened link. Returns false when it is not a setup link. The
    /// flow waits for confirmPending(): see pendingLink.
    @discardableResult
    func handle(_ url: URL, pairing: PairingStore) -> Bool {
        guard let l = Self.parse(url) else { return false }
        self.pairing = pairing
        pendingLink = l
        return true
    }

    func confirmPending() {
        guard let l = pendingLink, let p = pairing else { return }
        pendingLink = nil
        start(l, pairing: p)
    }

    func start(_ l: Link, pairing: PairingStore) {
        self.pairing = pairing
        link = l
        session = l.fingerprint.map { URLSession(configuration: .ephemeral, delegate: Pinned($0), delegateQueue: nil) } ?? .shared
        token = nil; unit = nil; hostname = nil; secret = nil
        networks = []; ssid = ""; psk = ""; name = ""
        Task { await connect() }
    }

    func cancel() {
        if let s = link?.ssid { NEHotspotConfigurationManager.shared.removeConfiguration(forSSID: s) }
        link = nil
    }

    // MARK: - Steps

    /// 1-3: join, claim, and everything that needs no typing.
    private func connect() async {
        guard let l = link else { return }
        step = .joining
        detail = l.onSetupNetwork ? "Joining the radar's setup network…" : "Looking for the radar…"
        if let s = l.ssid, let k = l.psk {
            let cfg = NEHotspotConfiguration(ssid: s, passphrase: k, isWEP: false)
            cfg.joinOnce = true          // iOS goes back to the home WiFi by itself afterwards
            do {
                try await NEHotspotConfigurationManager.shared.apply(cfg)
            } catch let e as NSError where e.domain == NEHotspotConfigurationErrorDomain
                        && e.code == NEHotspotConfigurationError.alreadyAssociated.rawValue {
                // already on it
            } catch {
                return fail("Couldn't join \(s): \(error.localizedDescription). Join it in Settings › WiFi, then try again.")
            }
        }
        guard let first = await waitForHello(l.base, seconds: 40) else {
            return fail("The radar didn't answer at \(l.base). Is its screen showing the setup code?")
        }
        guard first.claimed != true else {
            return fail("This radar is already set up. To get its alerts, pair from its screen: Settings › Phone & Watch.")
        }
        unit = first.unit
        hostname = first.hostname

        step = .claiming
        detail = "Claiming the radar…"
        let password = Self.randomToken(18)
        do {
            struct Claimed: Decodable { let token: String }
            let r: Claimed = try await api("POST", "claim", ["claimCode": l.code, "password": password])
            token = r.token
            if let u = unit { AdminPassword.save(password, unit: u) }
        } catch {
            return fail("The radar didn't accept the setup code: \(error.localizedDescription)")
        }

        step = .details
        await sendDetails()
        if let h = try? await hello(l.base) { name = h.name ?? "" }
        step = .name
    }

    /// Location, home airport, time zone and region: from the phone.
    private func sendDetails() async {
        detail = "Setting the location and time zone…"
        let tz = TimeZone.current.identifier
        let country = Locale.current.region?.identifier
        var locale: [String: Any] = ["timezone": tz]
        if let c = country, c.count == 2 { locale["country"] = c }
        _ = try? await apiRaw("POST", "locale", locale)

        guard let loc = await Self.oneLocation(timeout: 15) else { return }   // set later on the radar's screen
        struct Located: Decodable {
            struct Airport: Decodable { let code: String }
            let nearestAirports: [Airport]?
        }
        if let r: Located = try? await api("POST", "location", ["lat": loc.latitude, "lon": loc.longitude]),
           let code = r.nearestAirports?.first?.code {
            _ = try? await apiRaw("POST", "airport", ["code": code])
        }
    }

    /// 3, the name, then on to the WiFi (or straight to pairing).
    func saveName() async {
        guard let l = link else { return }
        busy = true
        defer { busy = false }
        let t = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty { _ = try? await apiRaw("POST", "name", ["name": t]) }
        if let h = try? await hello(l.base), let n = h.name { name = n }
        if l.onSetupNetwork {
            step = .wifi
            await scan()
        } else {
            await offerAndPair()
        }
    }

    func scan() async {
        busy = true
        defer { busy = false }
        struct Scan: Decodable { let result: [Network]? }
        if let r: Scan = try? await api("POST", "wifi/scan", [:]) {
            networks = (r.result ?? []).filter { !$0.ssid.isEmpty }
        }
    }

    /// 4: the radar joins the home WiFi, and the phone goes back to it.
    func join() async {
        guard let l = link, !ssid.isEmpty else { return }
        let s = Self.randomToken(16)
        secret = s
        busy = true
        do {
            _ = try await apiRaw("POST", "setup/join", ["ssid": ssid, "psk": psk, "secretHash": Self.sha256(s)])
        } catch {
            busy = false
            return fail("The radar didn't take that: \(error.localizedDescription)")
        }
        busy = false
        step = .switching
        detail = "The radar is joining \(ssid). Your phone goes back to its own WiFi…"
        if let w = l.ssid { NEHotspotConfigurationManager.shared.removeConfiguration(forSSID: w) }
        try? await Task.sleep(for: .seconds(8))
        await pair()
    }

    /// Already online (Ethernet): offer the code now, then pair.
    private func offerAndPair() async {
        let s = Self.randomToken(16)
        secret = s
        do {
            _ = try await apiRaw("POST", "setup/offer", ["secretHash": Self.sha256(s)])
        } catch {
            return fail("The radar couldn't reach the StratoScan service: \(error.localizedDescription)")
        }
        await pair()
    }

    /// 5: pair with the secret only this phone holds. The radar offers its
    /// hash once it's online, so until then the relay says "not yet".
    private func pair() async {
        guard let u = unit, let s = secret, let store = pairing else {
            return fail("Something went missing during setup. Start again from the radar's screen.")
        }
        step = .pairing
        detail = "Waiting for the radar to come online…"
        let relay = RelayClient()
        let deadline = Date().addingTimeInterval(240)
        var lastError = ""
        while Date() < deadline {
            do {
                try await relay.pair(unit: u, secret: s, name: UIDevice.current.name)
                store.adopt(unit: u, name: PairingStore.cleanName(name) ?? "StratoScan", host: nil)
                await find()
                return
            } catch {
                lastError = error.localizedDescription
                try? await Task.sleep(for: .seconds(5))
            }
        }
        let net = ssid.isEmpty ? "the network" : ssid
        fail("The radar didn't come online on \(net). If the password was wrong it goes back to its setup network after a minute or two: scan its code again to retry. (\(lastError))")
    }

    /// 6: find it on the home network, so the radar view can use it.
    private func find() async {
        step = .finding
        detail = "Finding the radar on your WiFi…"
        let candidates = [hostname.map { $0.hasSuffix(".local") ? $0 : "\($0).local" }, link?.lan].compactMap { $0 }
        let deadline = Date().addingTimeInterval(60)
        while Date() < deadline {
            for host in candidates {
                if let h = try? await hello("\(scheme)://\(host)", timeout: 3), h.unit == unit {
                    pairing?.setHost(host, unit: unit ?? "")
                    if APIConfig.baseURL == APIConfig.defaultBaseURL { APIConfig.baseURL = "http://\(host)" }
                    Endpoint.shared.invalidate()
                    step = .done
                    return
                }
            }
            try? await Task.sleep(for: .seconds(3))
        }
        // Paired anyway: alerts work. The radar view can be pointed at it later.
        step = .done
        detail = "Paired, but your phone couldn't find the radar on this WiFi yet. Alerts will still come; the radar view finds it next time it's on the same network."
    }

    private func fail(_ why: String) {
        busy = false
        step = .failed(why)
    }

    // MARK: - The radar's setup API

    struct Hello: Decodable {
        let claimed: Bool?
        let name: String?
        let unit: String?
        let hostname: String?
    }

    /// Accepts the radar's own certificate and nothing else when the link
    /// named one, whatever the system makes of a self-signed certificate; a
    /// link without one leaves the system to judge (it never sees https).
    private final class Pinned: NSObject, URLSessionDelegate {
        let fingerprint: String
        init(_ fingerprint: String) { self.fingerprint = fingerprint }
        func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge) async
            -> (URLSession.AuthChallengeDisposition, URLCredential?) {
            guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
                  let trust = challenge.protectionSpace.serverTrust else { return (.performDefaultHandling, nil) }
            guard let leaf = (SecTrustCopyCertificateChain(trust) as? [SecCertificate])?.first else {
                return (.cancelAuthenticationChallenge, nil)
            }
            let got = SHA256.hash(data: SecCertificateCopyData(leaf) as Data).map { String(format: "%02x", $0) }.joined()
            return got == fingerprint ? (.useCredential, URLCredential(trust: trust)) : (.cancelAuthenticationChallenge, nil)
        }
    }
    private var session = URLSession.shared
    private var scheme: String { link?.fingerprint == nil ? "http" : "https" }

    private func hello(_ base: String, timeout: TimeInterval = 4) async throws -> Hello {
        guard let url = URL(string: base + "/setup/api/hello") else { throw URLError(.badURL) }
        let (data, resp) = try await session.data(for: URLRequest(url: url, timeoutInterval: timeout))
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try JSONDecoder().decode(Hello.self, from: data)
    }

    private func waitForHello(_ base: String, seconds: TimeInterval) async -> Hello? {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if let h = try? await hello(base, timeout: 3) { return h }
            try? await Task.sleep(for: .seconds(2))
        }
        return nil
    }

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    @discardableResult
    private func apiRaw(_ method: String, _ path: String, _ body: [String: Any]) async throws -> Data {
        guard let l = link, let url = URL(string: l.base + "/setup/api/" + path) else { throw URLError(.badURL) }
        var req = URLRequest(url: url, timeoutInterval: 60)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let t = token { req.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization") }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, resp) = try await session.data(for: req)
        let status = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            struct E: Decodable { struct M: Decodable { let message: String? }; let error: M? }
            let msg = (try? JSONDecoder().decode(E.self, from: data))?.error?.message
            throw Failure(message: msg ?? "HTTP \(status)")
        }
        return data
    }

    private func api<T: Decodable>(_ method: String, _ path: String, _ body: [String: Any]) async throws -> T {
        try JSONDecoder().decode(T.self, from: try await apiRaw(method, path, body))
    }

    // MARK: - Helpers

    nonisolated static func randomToken(_ bytes: Int) -> String {
        var b = [UInt8](repeating: 0, count: bytes)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes, &b)
        return Data(b).base64urlString
    }

    nonisolated static func sha256(_ s: String) -> String {
        SHA256.hash(data: Data(s.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    /// One position, or nil if it isn't allowed or doesn't come in time.
    private static func oneLocation(timeout: TimeInterval) async -> CLLocationCoordinate2D? {
        let m = CLLocationManager()
        if m.authorizationStatus == .notDetermined { m.requestWhenInUseAuthorization() }
        return await withTaskGroup(of: CLLocationCoordinate2D?.self) { group in
            group.addTask {
                do {
                    for try await u in CLLocationUpdate.liveUpdates() {
                        if let l = u.location, l.horizontalAccuracy >= 0, l.horizontalAccuracy < 200 { return l.coordinate }
                    }
                } catch {}
                return nil
            }
            group.addTask {
                try? await Task.sleep(for: .seconds(timeout))
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
    }
}

/// The radar's admin password, made by the app at setup and kept on this
/// phone, so the owner can sign in to its setup page later.
enum AdminPassword {
    private static let service = "stratoscan.radar.admin"

    static func save(_ password: String, unit: String) {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                   kSecAttrService as String: service,
                                   kSecAttrAccount as String: unit]
        SecItemDelete(base as CFDictionary)
        var item = base
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        item[kSecValueData as String] = Data(password.utf8)
        SecItemAdd(item as CFDictionary, nil)
    }

    static func load(unit: String) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                kSecAttrService as String: service,
                                kSecAttrAccount as String: unit,
                                kSecReturnData as String: true]
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }
}
