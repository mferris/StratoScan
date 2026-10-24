import Foundation

/// The StratoScan relay (relay/ in this repository): pairing now, notifications
/// from roadmap 2.1. Someone running their own relay changes `baseURL`.
struct RelayClient {
    #if DEBUG
    /// A development build can be pointed at a local relay (`wrangler dev`)
    /// from the simulator: `SIMCTL_CHILD_STRATOSCAN_RELAY=http://127.0.0.1:8787`.
    static let baseURL = ProcessInfo.processInfo.environment["STRATOSCAN_RELAY"].flatMap(URL.init(string:))
        ?? URL(string: "https://relay.stratoscan.io")!
    #else
    static let baseURL = URL(string: "https://relay.stratoscan.io")!
    #endif

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    struct PairedUnit: Decodable {
        let unit: String
        let created: Int
    }

    func pair(unit: String, secret: String, name: String) async throws {
        _ = try await send("POST", "/v1/pair", ["unit": unit, "secret": secret, "name": name])
    }

    func units() async throws -> [PairedUnit] {
        struct Reply: Decodable { let units: [PairedUnit] }
        let data = try await send("GET", "/v1/phone/units", nil)
        return try JSONDecoder().decode(Reply.self, from: data).units
    }

    func unpair(unit: String) async throws {
        _ = try await send("POST", "/v1/phone/unpair", ["unit": unit])
    }

    func register(token: String, environment: String, kinds: [String], liveActivityToken: String?) async throws {
        var body: [String: Any] = ["token": token, "env": environment, "kinds": kinds]
        if let la = liveActivityToken { body["la_start_token"] = la }
        _ = try await send("POST", "/v1/phone/register", body)
    }

    /// The update token of a Live Activity the relay just started, so it can end it.
    func reportActivity(unit: String, hex: String, token: String) async throws {
        _ = try await send("POST", "/v1/phone/activity", ["unit": unit, "hex": hex, "token": token])
    }

    /// A paired radar's box key and its signature (roadmap 2.7); the caller
    /// checks the signature against the radar's id (LocationBox).
    func boxKey(unit: String) async throws -> (key: String, sig: String) {
        struct Reply: Decodable { let key: String; let sig: String }
        let r = try JSONDecoder().decode(Reply.self, from: try await send("POST", "/v1/phone/boxkey", ["unit": unit]))
        return (r.key, r.sig)
    }

    /// This phone's location for one radar, sealed (LocationBox); nil withdraws it.
    func location(unit: String, blob: String?) async throws {
        let value: Any = blob ?? NSNull()      // JSON null withdraws it
        _ = try await send("POST", "/v1/phone/location", ["unit": unit, "blob": value])
    }

    func testPush() async throws {
        _ = try await send("POST", "/v1/phone/test", [:])
    }

    // ---- the shared cache (#68): what the radars fetch, for a paired phone ----

    /// One lattice disc, only the aircraft within `nm` of `near` (the view's
    /// middle, already rounded to 0.05 degrees): adsb.lol's answer when the
    /// relay has it, nil on a miss or any failure.
    func netDisc(_ disc: NetLattice.Centre, near: Coordinate, nm: Int) async -> Data? {
        await ask("GET", String(format: "/v1/net/disc/%.4f/%.4f", disc.lat, disc.lon),
                  query: String(format: "near=%.2f,%.2f,%d", near.lat, near.lon, nm), body: Data())
    }

    /// Flights' routes, asked for as adsb.im takes them ({"planes": [...]})
    /// and answered as it does; nil on any failure.
    func netRoutes(_ body: Data) async -> Data? {
        await ask("POST", "/v1/net/routes", query: nil, body: body)
    }

    /// A signed request whose failure is only "no": the caller then asks the
    /// public service itself. The signature covers the path, not the query.
    private func ask(_ method: String, _ path: String, query: String?, body: Data) async -> Data? {
        guard var parts = URLComponents(url: Self.baseURL, resolvingAgainstBaseURL: false) else { return nil }
        parts.path = path
        parts.percentEncodedQuery = query
        guard let url = parts.url, let headers = try? RelayIdentity.headers(method: method, path: path, body: body) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 6)
        req.httpMethod = method
        if method != "GET" {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return data
    }

    private func send(_ method: String, _ path: String, _ payload: [String: Any]?) async throws -> Data {
        let body = try payload.map { try JSONSerialization.data(withJSONObject: $0) } ?? Data()
        var req = URLRequest(url: Self.baseURL.appendingPathComponent(String(path.dropFirst())))
        req.httpMethod = method
        req.timeoutInterval = 15
        if method != "GET" {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        for (k, v) in try RelayIdentity.headers(method: method, path: path, body: body) {
            req.setValue(v, forHTTPHeaderField: k)
        }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            throw Failure(message: "Could not reach the StratoScan service. Check your connection.")
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
            throw Failure(message: msg ?? "The StratoScan service said no (HTTP \(status)).")
        }
        return data
    }
}
