import Foundation
import SwiftUI

@MainActor
final class RadarViewModel: ObservableObject {
    // Overrides the receiver's actual configured position for DISPLAY
    // purposes only (readsb keeps using its own real antenna position
    // internally for signal-range/MLAT math — this only changes what
    // StratoScan centers on). nil auto-detects the receiver's real position
    // from receiver.json instead. Kept in sync with HOME_OVERRIDE in the
    // web version's index.html.
    static let homeOverride: Coordinate? = nil

    // The same outer ring as the kiosk (index.html RANGE_NM), so the phone
    // and the radar count the same aircraft -- whatever the view is zoomed to.
    let ringNm: Double = 20
    /// How far the view reaches from its centre: pinch from about a mile, to
    /// see which street an aircraft is over, out to a continent (roadmap 2.9,
    /// 2.23). Past the radar's ring the aircraft come from the public network.
    @Published var rangeNm: Double = 20
    static let minRangeNm = 1.0
    static let maxRangeNm = 2000.0
    /// An aircraft to keep in the middle of the view, chosen from its details.
    @Published var followHex: String? { didSet { if followHex != nil { centreOnMe = false } } }
    /// Centre the view on this phone instead of the radar (roadmap 2.7).
    @Published var centreOnMe = false { didSet { if centreOnMe { followHex = nil } } }
    /// Where this phone is, when the owner has asked to be shown. Stays on the phone.
    @Published var me: Coordinate?
    /// Where the owner has dragged or pinched the view to; nil means the
    /// radar (or the phone, when there is no radar). Anywhere in the world
    /// (roadmap 2.23): the view is a map, the radar's own aircraft cover its
    /// ring and the public network covers the rest.
    @Published var panCentre: Coordinate?
    /// A radar is paired or configured. Without one the view is the sky
    /// around the phone from the public network (roadmap 2.13).
    @Published var hasRadar = true
    var isZoomed: Bool { abs(rangeNm - ringNm) > 0.01 || panCentre != nil || followHex != nil || centreOnMe }
    /// Following an aircraft or the phone: the centre is theirs, not the owner's.
    var centreIsLocked: Bool { followHex != nil || (centreOnMe && me != nil) }

    func setRange(_ nm: Double) { rangeNm = min(Self.maxRangeNm, max(Self.minRangeNm, nm)) }
    func resetView() { rangeNm = ringNm; panCentre = nil; followHex = nil; centreOnMe = false }

    /// Zoom to `nm`, keeping the spot at `anchor` where it is on screen, the
    /// way Maps does. `anchor` is measured from the middle of the view in
    /// radii (x right, y down); `from` is the range and centre when the pinch
    /// began. Around the middle when the view is following something.
    func zoom(to nm: Double, anchor: CGPoint, from: (range: Double, centre: Coordinate)) {
        let newRange = min(Self.maxRangeNm, max(Self.minRangeNm, nm))
        guard !centreIsLocked else { rangeNm = newRange; return }
        let spot = Geo.moved(from.centre, east: Double(anchor.x) * from.range, north: -Double(anchor.y) * from.range)
        rangeNm = newRange
        panCentre = Geo.moved(spot, east: -Double(anchor.x) * newRange, north: Double(anchor.y) * newRange)
    }

    /// Move the view's centre: a drag lets go of anything it was following.
    func pan(to c: Coordinate) {
        followHex = nil
        centreOnMe = false
        panCentre = c
    }

    /// The view's centre on the ground: the followed aircraft, the phone, the
    /// spot the owner moved to, or the radar.
    var viewCentre: Coordinate {
        if let h = followHex, let p = planes[h] ?? viewNetwork[h], let c = p.displayCoordinate { return c }
        if centreOnMe, let m = me { return m }
        return panCentre ?? home ?? me ?? Coordinate(lat: 0, lon: 0)
    }

    /// Where a plane is relative to the middle of the view, in nm east and
    /// north on the view's own flat map (Geo.localOffset).
    func offset(_ p: PlaneState) -> (east: Double, north: Double)? {
        guard let c = p.displayCoordinate else { return nil }
        return Geo.localOffset(of: c, from: viewCentre)
    }
    /// How far a plane is from the middle of the view, in nm.
    func distanceFromCentre(_ p: PlaneState) -> Double {
        guard let o = offset(p) else { return .infinity }
        return hypot(o.east, o.north)
    }
    /// This phone and the radar, relative to the middle of the view.
    var meOffset: (east: Double, north: Double)? { me.map { Geo.localOffset(of: $0, from: viewCentre) } }
    var radarOffset: (east: Double, north: Double)? { home.map { Geo.localOffset(of: $0, from: viewCentre) } }
    /// Where the phone is from the radar (bearing and nm), when both are known.
    var meFromRadar: Geo.BearingRange? {
        guard let me, let home else { return nil }
        return Geo.haversineBearingRange(lat1: home.lat, lon1: home.lon, lat2: me.lat, lon2: me.lon)
    }
    /// Where the middle of the view is from the radar.
    var viewFromRadar: Geo.BearingRange? {
        guard let home else { return nil }
        return Geo.haversineBearingRange(lat1: home.lat, lon1: home.lon, lat2: viewCentre.lat, lon2: viewCentre.lon)
    }
    /// The view looks past the radar's own picture: its middle is well out of
    /// the ring, or it is zoomed out past it. There the public network fills
    /// in (roadmap 2.23).
    var beyondRadar: Bool {
        guard hasRadar, home != nil else { return true }
        return (viewFromRadar?.range ?? 0) > ringNm * 0.5 || rangeNm > ringNm * 1.5
    }
    /// The phone is beyond the radar's ring (or there is no radar).
    var awayFromRadar: Bool {
        guard hasRadar else { return true }
        guard let d = meFromRadar?.range else { return false }
        return d > ringNm
    }
    /// The public network's aircraft are wanted: the one switch (roadmap 2.21).
    @Published var networkOn: Bool = AircraftFeedClient.showNetwork {
        didSet {
            AircraftFeedClient.showNetwork = networkOn
            if !networkOn { viewNetwork = [:]; networkCount = 0; awayCentred = false }
        }
    }
    /// What is under the view: the radar's own aircraft, the public
    /// network's, or the demo recording. For the screen's status line.
    enum Source { case radar, network, demo, none }
    var source: Source {
        if isDemo { return .demo }
        if hasRadar && !beyondRadar && connected { return .radar }
        return networkOn ? .network : (hasRadar && connected ? .radar : .none)
    }
    /// Away from the radar with the network on, the view moved itself onto
    /// the phone (roadmap 2.21). Remembered so the owner can look back at the
    /// radar from away without the app pulling the view home again; cleared
    /// when the phone is back within the ring.
    @Published private(set) var awayCentred = false
    /// The app would like to know where the phone is: with the network on,
    /// it is what tells "away" from "home" and centres the view on you. Not
    /// while the first fetch is still being waited for, so a launch at home
    /// never asks for location.
    var wantsLocation: Bool {
        networkOn && !isDemo && (!hasRadar || viaAway || (!connecting && !connected) || centreOnMe)
    }

    let fetchInterval: TimeInterval = 1.0
    let staleInterval: TimeInterval = 15
    let dropInterval: TimeInterval = 45
    /// The network's aircraft around the view are asked for this often while
    /// the view rests there (adsb.lol's data changes about this often).
    let networkInterval: TimeInterval = 5
    /// A view wider than one disc is up to nine questions, a second apart,
    /// and several megabytes: asked less often.
    let networkTiledInterval: TimeInterval = 30

    @Published private(set) var home: Coordinate?
    @Published private(set) var connected: Bool = false
    /// Opening, or back from the background, and the radar hasn't answered
    /// yet. Said as "connecting", not "no signal": the app opened with NO
    /// SIGNAL for a few seconds every time, before its first fetch.
    @Published private(set) var connecting = true
    private var connectingSince = Date()
    /// How long the first answer may take (home, then the away address)
    /// before "connecting" turns into "no signal".
    private let connectGrace: TimeInterval = 8
    @Published private(set) var aircraftCount: Int = 0
    /// In the ring, reported by a public network but not heard by this radar.
    @Published private(set) var notHeardCount: Int = 0
    /// Around the view, from the public network (roadmap 2.23).
    @Published private(set) var networkCount: Int = 0
    @Published private(set) var runwayGeoJSON: Data?
    @Published private(set) var isDemo = DemoFeed.isOn
    /// True while the radar is being read through its public (away) address.
    @Published private(set) var viaAway = false

    /// The aircraft whose details are open, by hex.
    @Published var selectedHex: String?

    /// How much each label says. Tapping a plane shows everything, so the
    /// default keeps the map readable.
    enum LabelMode: String, CaseIterable {
        case compact, full, off
        var next: LabelMode { Self.allCases[(Self.allCases.firstIndex(of: self)! + 1) % Self.allCases.count] }
        var symbol: String {
            switch self {
            case .compact: return "tag"
            case .full: return "tag.fill"
            case .off: return "tag.slash"
            }
        }
    }
    @Published var labelMode: LabelMode =
        LabelMode(rawValue: UserDefaults.standard.string(forKey: "radome.labelMode") ?? "") ?? .compact {
        didSet { UserDefaults.standard.set(labelMode.rawValue, forKey: "radome.labelMode") }
    }

    /// True when bearing/range should come from readsb's own r_dst/r_dir.
    /// Always false while a HOME_OVERRIDE is active — see NormalizedAircraft.
    private var trustPrecomputed: Bool { Self.homeOverride == nil }

    /// The radar's aircraft (its own, and the network's within its ring).
    private(set) var planes: [String: PlaneState] = [:]
    /// The network's aircraft around the view, when it looks beyond the radar
    /// or there is no radar (roadmap 2.23). An aircraft the radar also has is
    /// the radar's.
    private(set) var viewNetwork: [String: PlaneState] = [:]
    private var viewNetworkFetchedAt = Date.distantPast
    private var viewNetworkCentre: Coordinate?
    /// Every aircraft to draw.
    var allPlanes: [PlaneState] { Array(planes.values) + Array(viewNetwork.values) }
    /// Aircraft around the phone when it is away from the radar, from
    /// adsb.lol, for Sky view (roadmap 2.5). Kept apart from `planes` so the
    /// radar, its counts and its alerts never mix them in.
    @Published var nearMe: [String: PlaneState] = [:]
    /// An aircraft by hex, wherever it came from.
    func plane(_ hex: String) -> PlaneState? { planes[hex] ?? viewNetwork[hex] ?? nearMe[hex] }
    private var lastGoodFetch: Date = .distantPast

    // Plain (non-Published) render-loop state, mutated directly from
    // RadarView's Canvas draw closure every frame — mirrors sweepAngle/
    // lastFrameTs living outside SwiftUI's diffing in the web version too.
    var sweepAngle: Double = 0
    var lastFrameTime: Date?

    let routeClient = RouteLookupClient()
    let typeClient = AircraftTypeClient()

    private var pollTask: Task<Void, Never>?

    /// The app is opening or coming back to the foreground: until the radar
    /// answers, the screen says it is connecting.
    func resume() {
        if Date().timeIntervalSince(lastGoodFetch) > staleInterval {
            connecting = true
            connectingSince = Date()
        }
    }

    func start() {
        resume()
        guard pollTask == nil else { return }
        Task { await typeClient.warmUp() }
        if home == nil, let cached = Self.cachedHome { home = cached }

        pollTask = Task { [weak self] in
            guard let self else { return }
            await self.loadHome()
            while !Task.isCancelled {
                await self.pollOnce()
                try? await Task.sleep(nanoseconds: UInt64(self.fetchInterval * 1_000_000_000))
            }
        }
    }

    /// Switch between the owner's radar and the demo recording.
    func setDemo(_ on: Bool) {
        DemoFeed.isOn = on
        isDemo = on
        WatchSync.shared.push()
        planes.removeAll()
        viewNetwork.removeAll()
        aircraftCount = 0
        notHeardCount = 0
        networkCount = 0
        selectedHex = nil
        home = nil
        runwayGeoJSON = nil
        resetView()
        Task { await loadHome() }
    }

    /// No radar: the sky around the phone from the public network, centred on
    /// you (roadmap 2.13). The one switch, on, and the view on the phone.
    func showAroundMe() {
        if DemoFeed.isOn { setDemo(false) }
        networkOn = true
        centreOnMe = true
        resume()
    }

    func stop() {
        pollTask?.cancel()
        pollTask = nil
    }

    // ---- home: the radar's position, remembered across launches -------------
    // A radar that cannot be reached (the phone is away and the public page
    // is off) still has a known place: the rings, the "N nm from your radar"
    // and the away test all need it.
    private static let homeCacheKey = "stratoscan.homeCache"
    private static var cachedHome: Coordinate? {
        get {
            guard let d = APIConfig.shared.dictionary(forKey: homeCacheKey),
                  let lat = d["lat"] as? Double, let lon = d["lon"] as? Double else { return nil }
            return Coordinate(lat: lat, lon: lon)
        }
        set {
            if let c = newValue { APIConfig.shared.set(["lat": c.lat, "lon": c.lon], forKey: homeCacheKey) }
            else { APIConfig.shared.removeObject(forKey: homeCacheKey) }
        }
    }

    private func loadHome() async {
        if let override = Self.homeOverride {
            home = override
            await loadRunways()
            return
        }
        guard hasRadar || DemoFeed.isOn else { return }
        do {
            if let coord = try await AircraftFeedClient.fetchReceiver() {
                home = coord
                if !DemoFeed.isOn { Self.cachedHome = coord }
                await loadRunways()
            }
        } catch {
            // retried on the next poll cycle below
        }
    }

    private func loadRunways() async {
        guard let home else { return }
        runwayGeoJSON = await RunwayClient.fetchRunwayGeoJSON(center: home, rangeNm: ringNm)
    }

    private func pollOnce() async {
        if hasRadar || DemoFeed.isOn {
            if home == nil { await loadHome() }
            await pollRadar()
        } else {
            connected = false
            connecting = false
            if !planes.isEmpty { planes.removeAll(); aircraftCount = 0; notHeardCount = 0 }
        }
        // The public network around the view, wherever the radar's own
        // picture does not reach: beyond its ring, when it cannot be reached,
        // or when there is none.
        if networkOn && !DemoFeed.isOn && (!hasRadar || beyondRadar || !connected) {
            await pollNetworkAroundView()
        } else if !viewNetwork.isEmpty {
            viewNetwork.removeAll()
            networkCount = 0
        }
        autoCentre()
        checkStale()
    }

    private func pollRadar() async {
        do {
            let raw = try await AircraftFeedClient.fetchFeed(network: networkOn).aircraft
            lastGoodFetch = Date()
            connected = true
            connecting = false
            let away = !DemoFeed.isOn && Endpoint.shared.whereNow == .away
            if away != viaAway { viaAway = away }
            applyUpdate(raw)
        } catch {
            connected = false
            if Date().timeIntervalSince(connectingSince) > connectGrace { connecting = false }
        }
    }

    /// Away from the radar with the network on, put the view on the phone,
    /// once; back within the ring, put it back on the radar, once. In
    /// between the owner can move it wherever they like.
    private func autoCentre() {
        guard networkOn, !DemoFeed.isOn, hasRadar, let m = me, let h = home else { return }
        let far = Geo.haversineBearingRange(lat1: h.lat, lon1: h.lon, lat2: m.lat, lon2: m.lon).range > ringNm
        if far && !awayCentred {
            awayCentred = true
            if panCentre == nil && followHex == nil { centreOnMe = true }
        } else if !far && awayCentred {
            awayCentred = false
            if centreOnMe { centreOnMe = false }
        }
    }

    /// The network's aircraft around the middle of the view, every few
    /// seconds while it rests there; at once when it has moved.
    private func pollNetworkAroundView() async {
        let centre = viewCentre
        let tiled = rangeNm > NetworkFeed.singleUpToNm
        // One disc follows the middle closely; a tiled view only once the middle
        // has moved a good way (a quarter of a disc), or the time is up.
        let moved: Bool
        if let prev = viewNetworkCentre {
            if tiled {
                let o = Geo.localOffset(of: centre, from: prev)
                moved = (o.east * o.east + o.north * o.north).squareRoot() > NetworkFeed.tileSpacingNm / 4
            } else {
                moved = NetworkFeed.rounded(prev) != NetworkFeed.rounded(centre)
            }
        } else {
            moved = true
        }
        guard moved || Date().timeIntervalSince(viewNetworkFetchedAt) >= (tiled ? networkTiledInterval : networkInterval) else { return }
        viewNetworkFetchedAt = Date()
        viewNetworkCentre = centre
        guard let list = await NetworkFeed.fetchView(around: centre, halfNm: rangeNm) else {
            if Date().timeIntervalSince(connectingSince) > connectGrace { connecting = false }
            return
        }
        connecting = false
        // bearing and range are from the radar when there is one, else from
        // the phone: what the labels and the ring count read
        let origin = home ?? me ?? centre
        var next: [String: PlaneState] = [:]
        for (raw, extra) in list {
            guard planes[raw.hex] == nil,
                  let n = NormalizedAircraft.normalize(raw, home: origin, trustPrecomputed: false) else { continue }
            let p = viewNetwork[raw.hex] ?? PlaneState(hex: raw.hex, from: n)
            p.apply(n)
            p.isNetwork = true
            p.fromView = true
            if let r = extra?.r { p.reg = r }
            if p.typeLabel == nil, let t = extra?.t { p.typeLabel = t }
            next[raw.hex] = p
        }
        viewNetwork = next
        networkCount = next.count
        if let h = followHex, plane(h) == nil { followHex = nil }
    }

    private func applyUpdate(_ list: [RawAircraft]) {
        var seen = Set<String>()

        for raw in list {
            guard let n = NormalizedAircraft.normalize(raw, home: home, trustPrecomputed: trustPrecomputed) else { continue }
            seen.insert(n.hex)

            if let existing = planes[n.hex] {
                existing.apply(n)
            } else if let fromNetwork = viewNetwork.removeValue(forKey: n.hex) {
                // the radar now hears what the network reported: keep its trail
                fromNetwork.apply(n)
                fromNetwork.fromView = false
                planes[n.hex] = fromNetwork
            } else {
                planes[n.hex] = PlaneState(hex: n.hex, from: n)
            }

            // The core feed has already looked these up, once, on the radar.
            let fromFeed = raw.feedOperator != nil
            if n.airlineIcao != nil && !fromFeed {
                let lat = n.lat ?? home?.lat ?? 0
                let lon = n.lon ?? home?.lon ?? 0
                routeClient.queueLookup(callsign: n.cs, lat: lat, lon: lon)
            }

            let hex = n.hex
            if planes[hex]?.typeLabel == nil && !fromFeed {
                Task {
                    if let label = await typeClient.lookupType(hex: hex) {
                        self.planes[hex]?.typeLabel = label
                    }
                }
            }
        }

        planes = planes.filter { seen.contains($0.key) }
        aircraftCount = planes.values.filter { $0.range <= ringNm && !$0.isNetwork }.count
        notHeardCount = planes.values.filter { $0.range <= ringNm && $0.isNetwork }.count
        // A followed aircraft that has left the picture: back to the radar.
        if let h = followHex, plane(h) == nil { followHex = nil }
    }

    /// The aircraft under a tap: its label first (the big target), then the
    /// nearest blip within a finger's width. Positions are the ones RadarView
    /// drew last frame, in the same coordinate space as the tap.
    func plane(at point: CGPoint) -> PlaneState? {
        let visible = allPlanes.filter { $0.labelX != nil || hypot($0.anchorX - point.x, $0.anchorY - point.y) < 60 }
        if let hit = visible.first(where: {
            guard let x = $0.labelX, let y = $0.labelY else { return false }
            return CGRect(x: x, y: y, width: $0.labelW, height: $0.labelH).insetBy(dx: -6, dy: -6).contains(point)
        }) { return hit }
        let nearest = visible.min { hypot($0.anchorX - point.x, $0.anchorY - point.y) < hypot($1.anchorX - point.x, $1.anchorY - point.y) }
        if let n = nearest, hypot(n.anchorX - point.x, n.anchorY - point.y) < 30 { return n }
        return nil
    }

    private func checkStale() {
        let now = Date()
        if now.timeIntervalSince(lastGoodFetch) > dropInterval, !planes.isEmpty {
            planes.removeAll()
            aircraftCount = 0
            notHeardCount = 0
        }
        if now.timeIntervalSince(viewNetworkFetchedAt) > dropInterval, !viewNetwork.isEmpty {
            viewNetwork.removeAll()
            networkCount = 0
        }
    }

    /// The radar has not answered for a while (the network's aircraft, when
    /// they are what the view shows, keep it from reading as "no signal").
    var isStale: Bool {
        !connecting && (!connected || Date().timeIntervalSince(lastGoodFetch) > staleInterval)
    }
    /// Nothing at all under the view.
    var isEmptyView: Bool { isStale && viewNetwork.isEmpty }
}
