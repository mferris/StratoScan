import Foundation

/// The public network's aircraft around a point, from adsb.lol (ODbL):
/// around the phone when it is away from the radar or has none, and around
/// wherever the view has been panned to (roadmap 2.13, 2.21, 2.23).
///
/// The point asked for is rounded to about 5 km first: enough to find the
/// sky's aircraft, not enough to find a house. Nothing else about the phone
/// is sent.
///
/// A phone paired with a radar asks the relay's shared cache first (#68):
/// the radars' discs of the world, of which it gets only the aircraft in its
/// view. A phone may only take what a radar has fetched, so on a miss it
/// asks adsb.lol itself, as before, and leaves that disc alone for a while.
enum NetworkFeed {
    /// adsb.lol answers point queries up to this radius.
    static let maxRadiusNm = 250
    static let minRadiusNm = 25

    static func rounded(_ c: Coordinate) -> Coordinate {
        Coordinate(lat: (c.lat * 20).rounded() / 20, lon: (c.lon * 20).rounded() / 20)
    }

    // A view wider than one disc (the owner's ask, 2026-10-08): several discs on
    // a square grid spaced so they leave no gap, at most 3 x 3 of them covering
    // the middle of the view; the rest of a continent stays empty, and the
    // footer says how far the picture reaches. Asked for less often than one
    // disc, since it is up to nine questions to adsb.lol at once.
    static let singleUpToNm = 190.0          // a view this far out still fits one disc (x1.3 <= 250)
    static let tileNm = Double(maxRadiusNm)
    static let tileSpacingNm = Double(maxRadiusNm) * 2.0.squareRoot()
    static let tileMaxN = 3

    /// Where to ask for a view `halfNm` out from `centre`: one disc round the
    /// middle while it fits, else an n x n grid of 250 nm discs (n <= 3)
    /// covering the middle; and the radius that covers.
    static func discs(around centre: Coordinate, halfNm: Double) -> (discs: [(Coordinate, Double)], coveredNm: Double) {
        if halfNm <= singleUpToNm {
            let r = max(Double(minRadiusNm), min(Double(maxRadiusNm), halfNm * 1.3))
            return ([(centre, r)], r)
        }
        let n = max(2, min(tileMaxN, Int((2 * halfNm / tileSpacingNm).rounded(.up))))
        var out: [(Coordinate, Double)] = []
        for j in 0..<n {
            for i in 0..<n {
                let east = (Double(i) - Double(n - 1) / 2) * tileSpacingNm
                let north = (Double(j) - Double(n - 1) / 2) * tileSpacingNm
                out.append((Geo.moved(centre, east: east, north: north), tileNm))
            }
        }
        return (out, Double(n) * tileSpacingNm / 2)
    }

    /// Between questions, and before one more try after a refusal: adsb.lol
    /// refuses a burst (420 and 429, measured), and wants about one a second.
    static let paceSeconds = 1.2
    static let retrySeconds = 2.5
    /// A view of several discs gets this long in all (#86, 2026-10-26): nine
    /// discs answer in about 20 s, and with adsb.lol silent the nine, each
    /// tried twice, took about three minutes. Discs not asked by then are
    /// left out of this look.
    static let viewBudgetSeconds = 25.0

    /// The aircraft over a view: every disc of `discs`, one after another,
    /// merged by hex. A disc that is refused twice is left out; nil only when
    /// none answered.
    static func fetchView(around centre: Coordinate, halfNm: Double) async -> [(RawAircraft, Extra?)]? {
        let (discs, _) = self.discs(around: centre, halfNm: halfNm)
        if discs.count == 1 { return await fetch(around: discs[0].0, radiusNm: discs[0].1) }
        let deadline = Date().addingTimeInterval(viewBudgetSeconds)
        var merged: [String: (RawAircraft, Extra?)] = [:]
        var answered = false
        for (i, d) in discs.enumerated() {
            if i > 0 { try? await Task.sleep(for: .seconds(paceSeconds)) }
            if Date() >= deadline || Task.isCancelled { break }
            var list = await fetch(around: d.0, radiusNm: d.1)
            if list == nil, Date().addingTimeInterval(retrySeconds) < deadline {
                try? await Task.sleep(for: .seconds(retrySeconds))
                list = await fetch(around: d.0, radiusNm: d.1)
            }
            guard let got = list else { continue }
            answered = true
            for item in got where merged[item.0.hex] == nil { merged[item.0.hex] = item }
        }
        return answered ? Array(merged.values) : nil
    }

    private struct Response: Decodable { let ac: [RawAircraft]? }
    struct Extra: Decodable { let hex: String; let r: String?; let t: String? }
    private struct ExtraResponse: Decodable { let ac: [Extra]? }

    /// The aircraft within `radiusNm` of `centre` (clamped to what adsb.lol
    /// serves), with the registration and type the network knows: from the
    /// relay's cache when it has them, else from adsb.lol.
    static func fetch(around centre: Coordinate, radiusNm: Double = Double(minRadiusNm)) async -> [(RawAircraft, Extra?)]? {
        let at = rounded(centre)
        let radius = max(minRadiusNm, min(maxRadiusNm, Int(radiusNm.rounded())))
        if let data = await fromRelay(at: at, radius: radius), let got = decode(data, within: (at, Double(radius))) {
            return got
        }
        guard let url = URL(string: String(format: "https://api.adsb.lol/v2/point/%.2f/%.2f/%d", at.lat, at.lon, radius)) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("StratoScan/1.0 (iOS app)", forHTTPHeaderField: "User-Agent")
        guard let (data, resp) = try? await URLSession.bounded.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return decode(data, within: nil)
    }

    /// adsb.lol's answer, with each aircraft's registration and type; only
    /// those within `within` (a relay that sent a whole disc).
    private static func decode(_ data: Data, within: (Coordinate, Double)?) -> [(RawAircraft, Extra?)]? {
        guard var list = try? JSONDecoder().decode(Response.self, from: data).ac else { return nil }
        if let (at, nm) = within {
            list = list.filter { a in
                guard let lat = a.lat, let lon = a.lon else { return false }
                return NetLattice.nm(at.lat, at.lon, lat, lon) <= nm
            }
        }
        let extras = (try? JSONDecoder().decode(ExtraResponse.self, from: data).ac) ?? []
        let byHex = Dictionary(extras.map { ($0.hex, $0) }, uniquingKeysWith: { a, _ in a })
        return list.map { ($0, byHex[$0.hex]) }
    }

    // ---- the relay's shared cache (#68) ----

    /// Set by the app (not the widget or the Watch: only the app holds the
    /// phone's relay key), and only answers while a radar is paired: for a
    /// lattice disc and a view inside it (the middle, already rounded, and
    /// its reach), adsb.lol's answer for that view as the relay has it, or
    /// nil when it hasn't.
    typealias RelayDisc = @Sendable (_ disc: NetLattice.Centre, _ near: Coordinate, _ nm: Int) async -> Data?
    static var relay: RelayDisc? {
        get { lock.withLock { relayHook } }
        set { lock.withLock { relayHook = newValue } }
    }
    /// A disc the relay didn't have is left alone this long, adsb.lol asked
    /// directly meanwhile: today most of the sky is a disc no radar is
    /// looking at, and a phone asking the relay first every few seconds
    /// would only double its questions.
    static let relayMissSeconds: TimeInterval = 30
    private static let lock = NSLock()
    private static var relayHook: RelayDisc?
    private static var missedAt: [String: Date] = [:]

    /// The view from the relay, when one disc holds it and the relay has it.
    private static func fromRelay(at: Coordinate, radius: Int) async -> Data? {
        guard let ask = relay, let disc = NetLattice.holding(at.lat, at.lon, wantNm: Double(radius)) else { return nil }
        let key = "\(disc.lat),\(disc.lon)"
        let recentMiss = lock.withLock { missedAt[key].map { Date().timeIntervalSince($0) < relayMissSeconds } ?? false }
        if recentMiss { return nil }
        if let data = await ask(disc, at, radius) { return data }
        lock.withLock {
            if missedAt.count > 64 { missedAt.removeAll() }
            missedAt[key] = Date()
        }
        return nil
    }
}
