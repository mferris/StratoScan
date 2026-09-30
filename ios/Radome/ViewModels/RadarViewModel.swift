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
    // and the radar count the same aircraft.
    let rangeNm: Double = 20
    let fetchInterval: TimeInterval = 1.0
    let staleInterval: TimeInterval = 15
    let dropInterval: TimeInterval = 45

    @Published private(set) var home: Coordinate?
    @Published private(set) var connected: Bool = false
    @Published private(set) var aircraftCount: Int = 0
    /// In the ring, reported by a public network but not heard by this radar.
    @Published private(set) var notHeardCount: Int = 0
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

    private(set) var planes: [String: PlaneState] = [:]
    private var lastGoodFetch: Date = .distantPast

    // Plain (non-Published) render-loop state, mutated directly from
    // RadarView's Canvas draw closure every frame — mirrors sweepAngle/
    // lastFrameTs living outside SwiftUI's diffing in the web version too.
    var sweepAngle: Double = 0
    var lastFrameTime: Date?

    let routeClient = RouteLookupClient()
    let typeClient = AircraftTypeClient()

    private var pollTask: Task<Void, Never>?

    func start() {
        guard pollTask == nil else { return }
        Task { await typeClient.warmUp() }

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
        planes.removeAll()
        aircraftCount = 0
        selectedHex = nil
        home = nil
        runwayGeoJSON = nil
        Task { await loadHome() }
    }

    func stop() {
        pollTask?.cancel()
        pollTask = nil
    }

    private func loadHome() async {
        if let override = Self.homeOverride {
            home = override
            await loadRunways()
            return
        }
        do {
            if let coord = try await AircraftFeedClient.fetchReceiver() {
                home = coord
                await loadRunways()
            }
        } catch {
            // retried on the next poll cycle below
        }
    }

    private func loadRunways() async {
        guard let home else { return }
        runwayGeoJSON = await RunwayClient.fetchRunwayGeoJSON(center: home, rangeNm: rangeNm)
    }

    private func pollOnce() async {
        if home == nil { await loadHome() }
        do {
            let raw = try await AircraftFeedClient.fetchFeed(network: AircraftFeedClient.showNetwork).aircraft
            lastGoodFetch = Date()
            connected = true
            let away = !DemoFeed.isOn && Endpoint.shared.whereNow == .away
            if away != viaAway { viaAway = away }
            applyUpdate(raw)
        } catch {
            connected = false
        }
        checkStale()
    }

    private func applyUpdate(_ list: [RawAircraft]) {
        var seen = Set<String>()

        for raw in list {
            guard let n = NormalizedAircraft.normalize(raw, home: home, trustPrecomputed: trustPrecomputed) else { continue }
            seen.insert(n.hex)

            if let existing = planes[n.hex] {
                existing.apply(n)
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
        aircraftCount = planes.values.filter { $0.range <= rangeNm && !$0.isNetwork }.count
        notHeardCount = planes.values.filter { $0.range <= rangeNm && $0.isNetwork }.count
    }

    /// The aircraft under a tap: its label first (the big target), then the
    /// nearest blip within a finger's width. Positions are the ones RadarView
    /// drew last frame, in the same coordinate space as the tap.
    func plane(at point: CGPoint) -> PlaneState? {
        let visible = planes.values.filter { $0.range <= rangeNm }
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
        }
    }

    var isStale: Bool {
        !connected || Date().timeIntervalSince(lastGoodFetch) > staleInterval
    }
}
