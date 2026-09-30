import Foundation

/// The StratoScan relay (relay/ in this repository): pairing now, notifications
/// from roadmap 2.1. Someone running their own relay changes `baseURL`.
struct RelayClient {
    static let baseURL = URL(string: "https://relay.stratoscan.io")!

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

    func testPush() async throws {
        _ = try await send("POST", "/v1/phone/test", [:])
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
