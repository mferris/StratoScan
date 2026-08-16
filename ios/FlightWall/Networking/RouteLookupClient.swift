import Foundation

struct FlightRoute {
    let from: String
    let to: String
}

/// Batched/cached/throttled the same way tar1090 itself queries this API,
/// and the same way the web version's queueRouteLookup/flushRouteQueue do:
/// collect callsigns as they're seen, flush a batch periodically, cache
/// results (including negative ones) for the rest of the session.
///
/// @MainActor (not a separate actor) so RadarView's Canvas draw loop —
/// which runs on the main thread every frame — can read `cache` directly
/// without an async hop, matching how the web version reads routeCache
/// synchronously inside its own per-frame draw loop.
@MainActor
final class RouteLookupClient {
    private let routeAPIURL = URL(string: "https://adsb.im/api/0/routeset")!
    private let batchInterval: UInt64 = 4_000_000_000 // 4s, in nanoseconds
    private let batchMax = 50

    private(set) var cache: [String: FlightRoute?] = [:]
    private var pending: Set<String> = []
    private var queue: [(callsign: String, lat: Double, lon: Double)] = []
    private var flushTask: Task<Void, Never>?

    func queueLookup(callsign: String, lat: Double, lon: Double) {
        guard cache[callsign] == nil, !pending.contains(callsign) else { return }
        guard !queue.contains(where: { $0.callsign == callsign }) else { return }
        queue.append((callsign, lat, lon))
        if flushTask == nil {
            flushTask = Task { [weak self] in
                try? await Task.sleep(nanoseconds: self?.batchInterval ?? 4_000_000_000)
                await self?.flush()
            }
        }
    }

    private func flush() async {
        flushTask = nil
        guard !queue.isEmpty else { return }
        let batch = Array(queue.prefix(batchMax))
        queue.removeFirst(batch.count)
        for e in batch { pending.insert(e.callsign) }

        struct PlaneQuery: Encodable { let callsign: String; let lat: Double; let lng: Double }
        struct RequestBody: Encodable { let planes: [PlaneQuery] }
        struct Airport: Decodable { let location: String }
        struct RouteResponse: Decodable {
            let callsign: String?
            let plausible: Bool?
            let _airports: [Airport]?
        }

        do {
            var req = URLRequest(url: routeAPIURL)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONEncoder().encode(RequestBody(planes: batch.map { PlaneQuery(callsign: $0.callsign, lat: $0.lat, lng: $0.lon) }))

            let (data, response) = try await URLSession.shared.data(for: req)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
            let routes = try JSONDecoder().decode([RouteResponse].self, from: data)

            var found: Set<String> = []
            for r in routes {
                guard let cs = r.callsign else { continue }
                found.insert(cs)
                // skip routes the API itself flags implausible for this
                // flight's current position, rather than showing a
                // possibly-wrong city pair
                let airports = (r.plausible != false) ? r._airports : nil
                if let airports, airports.count == 2 {
                    cache[cs] = FlightRoute(from: airports[0].location, to: airports[1].location)
                } else {
                    cache[cs] = FlightRoute?.none
                }
            }
            for e in batch where !found.contains(e.callsign) {
                cache[e.callsign] = FlightRoute?.none
            }
        } catch {
            // network hiccup — don't cache anything, so these get retried later
        }

        for e in batch { pending.remove(e.callsign) }
        if !queue.isEmpty {
            flushTask = Task { [weak self] in
                try? await Task.sleep(nanoseconds: self?.batchInterval ?? 4_000_000_000)
                await self?.flush()
            }
        }
    }
}
