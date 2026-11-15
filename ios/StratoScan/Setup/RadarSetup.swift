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
/// 3. The time zone and region, and a name. The radar's location and nearest
///    airport come from this phone's position only when the owner turns that
///    on, on the name screen (2026-11-15); otherwise they are set on the
///    radar's own screen.
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
    /// A code scanned on purpose from Settings skips this (see scanned()).
    @Published var pendingLink: Link?
    /// A code scanned in the app that names no certificate, waiting for the
    /// owner's yes to sending the setup unprotected (2026-11-15).
    @Published var unprotectedLink: Link?
    @Published private(set) var step: Step = .joining
    @Published private(set) var detail = ""
    @Published var name = ""
    /// The owner's choice on the name screen: send this phone's position to
    /// the radar as the radar's own. Off until they turn it on, for every
    /// setup (security review 2026-11-03, SR-06): the flow used to send it
    /// straight after the claim, to whatever had answered.
    @Published var usePhoneLocation = false
    /// The radar took a location from this phone during this setup. False
    /// with the switch off, the permission refused, no fix in time or the
    /// request failed: the Done step then says where to set it (2026-11-15).
    @Published private(set) var radarLocated = false
    /// Whether the radar just set up is told where this phone is, for the
    /// Done step's switch. Read from the pairing once it is recorded: a
    /// radar new to the phone starts off, one already paired keeps its choice.
    @Published private(set) var sharingWithRadar = false
    @Published private(set) var networks: [Network] = []
    @Published var ssid = ""
    @Published var psk = ""
    @Published private(set) var busy = false

    private var token: String?
    private var unit: String?
    /// The radar's host name from its hello, kept only when it is a single
    /// DNS label (hostLabel).
    private var hostname: String?
    private var secret: String?
    private var pairing: PairingStore?
    /// The flow's work in hand, stopped by Cancel (#86, 2026-10-26): a
    /// cancelled setup went on asking the relay and looking for the radar for
    /// up to five minutes, and could still adopt it and change the radar
    /// view's address.
    private var work: Task<Void, Never>?
    /// Counts the setups begun and cancelled, so a step still waiting when its
    /// setup was cancelled (the name step can wait 15 s for a location) finds
    /// it is no longer its turn, and neither moves the next setup on nor
    /// sends this phone's location to the next radar (review, 2026-11-15).
    private var run = 0

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
        // A certificate that is named but not written as one makes the whole
        // link no link (2026-11-15). It used to count as naming none, which
        // let a damaged or altered code fall back to plain http.
        var f: String? = nil
        if let v = q("f") {
            guard let named = certificate(v) else { return nil }
            f = named
        }
        guard (w != nil && k != nil) || h != nil else { return nil }
        return Link(code: c, ssid: w, psk: k, address: w != nil ? a : nil, lan: w == nil ? h : nil, fingerprint: f)
    }

    /// A certificate's SHA-256 as a link writes it: 64 hex digits.
    nonisolated static func certificate(_ v: String) -> String? {
        v.count == 64 && v.allSatisfy({ $0.isASCII && $0.isHexDigit }) ? v.lowercased() : nil
    }

    /// A setup link whose f= is there but is not a certificate's SHA-256.
    /// parse() gives nil for it; this is so the owner can be told why.
    nonisolated static func namesBadCertificate(_ url: URL) -> Bool {
        guard ["stratoscan", "radome"].contains(url.scheme?.lowercased() ?? ""), url.host?.lowercased() == "setup",
              let f = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == "f" })
        else { return false }
        return certificate(f.value ?? "") == nil
    }

    /// What a link opened from outside the app is told when it names no
    /// certificate. It says what the rule is, and not that a certificate
    /// would show whose radar it is: it doesn't.
    nonisolated static let unpinnedRefusal = "A setup link opened from outside the app must name a radar's certificate, and that one doesn't. To set up a radar without one, scan the code on its own first screen from here: Settings › Paired radars › Scan a radar's code."

    /// What a link or scanned code is told when its certificate is not
    /// written as one.
    nonisolated static let badCertificateRefusal = "That setup code is damaged: the certificate in it isn't written as one, so nothing was sent. Scan the code on the radar's own first screen again."

    /// The question before setting up a radar that has no certificate, from
    /// a code scanned in the app.
    nonisolated static func unprotectedQuestion(onSetupNetwork: Bool) -> String {
        "Your WiFi password and the setup details will be sent to it unprotected, "
            + (onSetupNetwork ? "on its own setup network." : "on this network.")
    }

    /// A link opened from outside the app may start a setup only when it
    /// names a certificate (SR-06, 2026-11-15). Any page or message can open
    /// one, and without a certificate the setup would go in the clear to
    /// whatever answered at the address in it. The certificate keeps the
    /// setup private to whatever holds it; it does not show whose radar that
    /// is, which is why the question before it says so. A code scanned in the
    /// app's own scanner is read off a radar's screen on purpose, so a radar
    /// made before certificates can still be set up that way (scanned()).
    nonisolated static func mayStartFromOutside(_ l: Link) -> Bool { l.fingerprint != nil }

    /// Handles a link opened from outside the app. Returns false when it is
    /// not a setup link. One that names no certificate, or one not written
    /// as a certificate, is refused, in words; the rest wait for
    /// confirmPending(): see pendingLink.
    @discardableResult
    func handle(_ url: URL, pairing: PairingStore) -> Bool {
        guard let l = Self.parse(url) else {
            guard Self.namesBadCertificate(url) else { return false }
            pairing.message = Self.badCertificateRefusal
            return true
        }
        guard Self.mayStartFromOutside(l) else {
            pairing.message = Self.unpinnedRefusal
            return true
        }
        self.pairing = pairing
        pendingLink = l
        return true
    }

    func confirmPending() {
        guard let l = pendingLink, let p = pairing else { return }
        pendingLink = nil
        start(l, pairing: p)
    }

    /// A code read in the app's own scanner. Naming a certificate, it starts
    /// at once: scanning it was the yes. Naming none (a radar made before
    /// certificates), the owner is asked first, because the WiFi password
    /// then goes unprotected (2026-11-15). One whose certificate is not
    /// written as one is refused.
    func scanned(_ url: URL, pairing: PairingStore) {
        guard let l = Self.parse(url) else {
            if Self.namesBadCertificate(url) { pairing.message = Self.badCertificateRefusal }
            return
        }
        self.pairing = pairing
        if l.fingerprint == nil {
            unprotectedLink = l
        } else {
            start(l, pairing: pairing)
        }
    }

    func confirmUnprotected() {
        guard let l = unprotectedLink, let p = pairing else { return }
        unprotectedLink = nil
        start(l, pairing: p)
    }

    func start(_ l: Link, pairing: PairingStore) {
        self.pairing = pairing
        link = l
        session.finishTasksAndInvalidate()      // a session lets go of its delegate only then
        session = Self.session(pinnedTo: l.fingerprint)
        token = nil; unit = nil; hostname = nil; secret = nil
        networks = []; ssid = ""; psk = ""; name = ""
        usePhoneLocation = false
        radarLocated = false
        sharingWithRadar = false
        work?.cancel()
        run += 1
        work = Task { await connect() }
    }

    func cancel() {
        run += 1
        work?.cancel()
        work = nil
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
        // A radar with a certificate is spoken to over https or not at all:
        // a link that failed to name it (as the first cut's permissions made
        // every link do, 2026-10-09) must not quietly send the passwords in
        // the clear.
        if l.fingerprint == nil && first.tls == true {
            return fail("This radar expects a secure setup, but the code didn't name its certificate. Scan the code on its screen again.")
        }
        guard !Task.isCancelled else { return }     // never claim for a setup that was cancelled
        unit = first.unit
        hostname = Self.hostLabel(first.hostname)

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
        guard !Task.isCancelled else { return }
        step = .name
    }

    /// Time zone and region: from the phone's settings. Nothing here says
    /// where the phone is.
    private func sendDetails() async {
        detail = "Setting the time zone…"
        let tz = TimeZone.current.identifier
        let country = Locale.current.region?.identifier
        var locale: [String: Any] = ["timezone": tz]
        if let c = country, c.count == 2 { locale["country"] = c }
        _ = try? await apiRaw("POST", "locale", locale)
    }

    /// The radar's location and home airport, from this phone's position.
    /// Only from saveName(), and only when the owner turned it on there
    /// (SR-06): iOS isn't asked for the position before that either. True
    /// when the radar took the location; the Done step tells the owner when
    /// it didn't (2026-11-15), where this used to fail without a word.
    private func sendPhoneLocation(stillWanted: () -> Bool) async -> Bool {
        detail = "Getting this phone's location…"
        defer { if stillWanted() { detail = "" } }
        guard let loc = await Self.oneLocation(timeout: 15) else { return false }
        // the wait can be long: a setup cancelled meanwhile sends nothing, and
        // never to whichever radar a new setup has turned to since
        guard stillWanted() else { return false }
        guard let data = try? await apiRaw("POST", "location", ["lat": loc.latitude, "lon": loc.longitude]) else { return false }
        guard stillWanted() else { return false }
        struct Located: Decodable {
            struct Airport: Decodable { let code: String }
            let nearestAirports: [Airport]?
        }
        if let code = (try? JSONDecoder().decode(Located.self, from: data))?.nearestAirports?.first?.code {
            _ = try? await apiRaw("POST", "airport", ["code": code])
        }
        return true
    }

    /// 3, the name, then on to the WiFi (or straight to pairing).
    func saveName() async {
        guard let l = link else { return }
        let mine = run
        busy = true
        defer { if mine == run { busy = false } }
        detail = ""
        let t = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty { _ = try? await apiRaw("POST", "name", ["name": t]) }
        guard mine == run else { return }
        if usePhoneLocation {
            let located = await sendPhoneLocation(stillWanted: { [weak self] in self?.run == mine })
            guard mine == run else { return }
            radarLocated = located
        }
        let h = try? await hello(l.base)
        guard mine == run else { return }
        if let n = h?.name { name = n }
        if l.onSetupNetwork {
            step = .wifi
            await scan()
        } else {
            let t = Task { await offerAndPair() }
            work = t
            await t.value
        }
    }

    /// The Done step's switch: whether the radar just set up is told where
    /// this phone is. It is the per-radar setting in Settings › Paired radars.
    func sharePhoneLocation(_ on: Bool) {
        guard let u = unit, let store = pairing else { return }
        store.setShareLocation(on, unit: u)
        sharingWithRadar = store.radars.first(where: { $0.unit == u })?.shareLocation != false
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
        let t = Task {
            try? await Task.sleep(for: .seconds(8))
            await pair()
        }
        work = t
        await t.value
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
        while Date() < deadline, !Task.isCancelled {
            do {
                try await relay.pair(unit: u, secret: s, name: PhoneName.current)
                // paired at the relay: the phone keeps it even if cancelled now
                store.adopt(unit: u, name: PairingStore.cleanName(name) ?? "StratoScan", host: nil)
                sharingWithRadar = store.radars.first(where: { $0.unit == u })?.shareLocation != false
                if !Task.isCancelled { await find() }
                return
            } catch {
                lastError = error.localizedDescription
                try? await Task.sleep(for: .seconds(5))
            }
        }
        let net = ssid.isEmpty ? "the network" : ssid
        fail("The radar didn't come online on \(net). If the password was wrong it goes back to its setup network after a minute or two: scan its code again to retry. (\(lastError))")
    }

    /// A host name as a radar's hello may give it: one DNS label, which is
    /// letters, digits and hyphens, 1 to 63 of them, not starting or ending
    /// with a hyphen. Anything else is dropped (2026-11-15): the name is put
    /// into an address the phone then asks and keeps, and the hello comes
    /// from whatever answered, so a name with a dot, a slash, an @ or a colon
    /// could have pointed the phone somewhere else.
    nonisolated static func hostLabel(_ v: String?) -> String? {
        guard let v, (1...63).contains(v.utf8.count), !v.hasPrefix("-"), !v.hasSuffix("-"),
              v.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) || $0 == 45 })
        else { return nil }
        return v
    }

    /// Where the radar may be looked for on the home network once paired:
    /// "<host label>.local" from its hello, and the link's own LAN address.
    /// Each is that .local name or passes isPrivateHost; nothing else is
    /// asked, or kept as the radar's address.
    nonisolated static func homeCandidates(hostname: String?, lan: String?) -> [String] {
        let local = hostLabel(hostname).map { "\($0).local" }
        return [local, lan].compactMap { $0 }.filter { $0 == local || isPrivateHost($0) }
    }

    /// 6: find it on the home network, so the radar view can use it. With
    /// nowhere allowed to look (homeCandidates), the home address stays
    /// unset and the radar is paired all the same.
    private func find() async {
        step = .finding
        detail = "Finding the radar on your WiFi…"
        // The Done step says what the pairing's own message would, and that
        // message is an alert under these screens: not left to come up after.
        pairing?.message = nil
        let candidates = Self.homeCandidates(hostname: hostname, lan: link?.lan)
        let deadline = Date().addingTimeInterval(candidates.isEmpty ? 0 : 60)
        while Date() < deadline, !Task.isCancelled {
            for host in candidates {
                if let h = try? await hello("\(scheme)://\(host)", timeout: 3), h.unit == unit, !Task.isCancelled {
                    pairing?.setHost(host, unit: unit ?? "")
                    if APIConfig.baseURL == APIConfig.defaultBaseURL { APIConfig.baseURL = "http://\(host)" }
                    Endpoint.shared.invalidate()
                    detail = ""
                    step = .done
                    return
                }
            }
            try? await Task.sleep(for: .seconds(3))
        }
        guard !Task.isCancelled else { return }
        // Paired anyway: alerts work. The radar view can be pointed at it later.
        step = .done
        detail = "Paired, but your phone couldn't find the radar on this WiFi yet. Alerts will still come; the radar view finds it next time it's on the same network."
    }

    private func fail(_ why: String) {
        busy = false
        guard !Task.isCancelled else { return }     // cancelled: nothing to say
        step = .failed(why)
    }

    // MARK: - The radar's setup API

    struct Hello: Decodable {
        let claimed: Bool?
        let name: String?
        let unit: String?
        let hostname: String?
        /// The radar has a certificate for the setup flow (2026-10-09).
        let tls: Bool?
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
    private var session = RadarSetup.session(pinnedTo: nil)
    private var scheme: String { link?.fingerprint == nil ? "http" : "https" }

    /// Every setup call is given up in the end (#86, 2026-10-26), not only
    /// when it goes quiet: 75 s in all, past the slowest call's own limit.
    nonisolated private static func session(pinnedTo fingerprint: String?) -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForResource = 75
        return URLSession(configuration: c, delegate: fingerprint.map { Pinned($0) }, delegateQueue: nil)
    }

    private func hello(_ base: String, timeout: TimeInterval = 4) async throws -> Hello {
        guard let url = URL(string: base + "/setup/api/hello") else { throw URLError(.badURL) }
        let (data, resp) = try await session.data(for: URLRequest(url: url, timeoutInterval: timeout))
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try JSONDecoder().decode(Hello.self, from: data)
    }

    private func waitForHello(_ base: String, seconds: TimeInterval) async -> Hello? {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline, !Task.isCancelled {
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
        // A WiFi scan takes the radar up to about 50 s. Everything else takes
        // a few seconds; 30 at most, or a setup network that has gone (iOS
        // drops it when the app is put away) held each step a minute (#86).
        var req = URLRequest(url: url, timeoutInterval: path == "wifi/scan" ? 60 : 30)
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

    /// iOS's question about location, and the owner's answer to it.
    private final class PermissionWait: NSObject, CLLocationManagerDelegate {
        private let manager = CLLocationManager()
        private var waiting: CheckedContinuation<Void, Never>?

        /// The permission as it stands, after asking when it was never asked.
        @MainActor func answer() async -> CLAuthorizationStatus {
            if manager.authorizationStatus == .notDetermined {
                await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
                    waiting = c
                    manager.delegate = self
                    manager.requestWhenInUseAuthorization()
                }
            }
            return manager.authorizationStatus
        }

        nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
            Task { @MainActor in
                guard self.manager.authorizationStatus != .notDetermined, let c = self.waiting else { return }
                self.waiting = nil
                c.resume()
            }
        }
    }

    /// One position, or nil if it isn't allowed or doesn't come in time.
    /// The time allowed starts once the owner has answered iOS's question
    /// (2026-11-15): it used to run while the question was still on screen,
    /// so a slow answer gave no position.
    private static func oneLocation(timeout: TimeInterval) async -> CLLocationCoordinate2D? {
        let status = await PermissionWait().answer()
        guard status == .authorizedWhenInUse || status == .authorizedAlways else { return nil }
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
