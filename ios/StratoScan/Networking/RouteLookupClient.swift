import Foundation

/// An aircraft's route as the kiosk words it (#77): the core feed's text,
/// or this lookup's in the same form -- every stop's city joined with " → ",
/// "(unconfirmed)" when the route doesn't fit where the aircraft is.
struct RouteText { let text: String; let plausible: Bool }

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

    private(set) var cache: [String: FeedRoute?] = [:]

    /// The relay's shared cache of routes (#68), set by the app while a
    /// radar is paired: one lookup per flight for every radar and phone,
    /// kept six hours. Nil, or no answer, and adsb.im is asked directly.
    static var relay: (@Sendable (Data) async -> Data?)?

    /// The route to show for an aircraft: the core feed's, else this lookup's.
    func route(for p: PlaneState) -> RouteText? {
        guard let r = p.feedRoute ?? (cache[p.cs] ?? nil) else { return nil }
        let plausible = r.plausible != false
        return RouteText(text: plausible ? r.text : "\(r.text) (unconfirmed)", plausible: plausible)
    }
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
        struct Airport: Decodable { let location: String? }     // the relay passes a missing one on as null
        struct RouteResponse: Decodable {
            let callsign: String?
            let plausible: Bool?
            let _airports: [Airport]?
        }

        do {
            // Through the relay, positions to 0.1 degrees: all a route check needs.
            var data: Data? = nil
            if let relay = Self.relay {
                let rounded = RequestBody(planes: batch.map {
                    PlaneQuery(callsign: $0.callsign, lat: ($0.lat * 10).rounded() / 10, lng: ($0.lon * 10).rounded() / 10)
                })
                let body = try JSONEncoder().encode(rounded)
                data = await relay(body)
            }
            if data == nil {
                var req = URLRequest(url: routeAPIURL)
                req.httpMethod = "POST"
                req.timeoutInterval = 10      // not iOS's 60 s: the batch's callsigns wait on it (#86)
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                req.httpBody = try JSONEncoder().encode(RequestBody(planes: batch.map { PlaneQuery(callsign: $0.callsign, lat: $0.lat, lng: $0.lon) }))
                let (direct, response) = try await URLSession.bounded.data(for: req)
                guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
                data = direct
            }
            let routes = try JSONDecoder().decode([RouteResponse].self, from: data ?? Data())

            var found: Set<String> = []
            for r in routes {
                guard let cs = r.callsign else { continue }
                found.insert(cs)
                // As the core feed words it (core-feed.py): every stop, and an
                // implausible route kept but marked, as the kiosk shows it.
                if let airports = r._airports?.compactMap(\.location), airports.count >= 2 {
                    cache[cs] = FeedRoute(text: airports.joined(separator: " → "),
                                          plausible: r.plausible != false)
                } else {
                    cache[cs] = FeedRoute?.none
                }
            }
            for e in batch where !found.contains(e.callsign) {
                cache[e.callsign] = FeedRoute?.none
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
