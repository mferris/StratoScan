import Foundation
import SwiftUI

@MainActor
final class RadarViewModel: ObservableObject {
    // Overrides the receiver's actual configured position for DISPLAY
    // purposes only (readsb keeps using its own real antenna position
    // internally for signal-range/MLAT math — this only changes what
    // FlightWall centers on). nil auto-detects the receiver's real position
    // from receiver.json instead ([address redacted]). Kept in sync
    // with HOME_OVERRIDE in the web version's index.html.
    static let homeOverride: Coordinate? = nil

    let rangeNm: Double = 40
    let fetchInterval: TimeInterval = 1.0
    let staleInterval: TimeInterval = 15
    let dropInterval: TimeInterval = 45

    @Published private(set) var home: Coordinate?
    @Published private(set) var connected: Bool = false
    @Published private(set) var aircraftCount: Int = 0
    @Published private(set) var runwayGeoJSON: Data?

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
            let raw = try await AircraftFeedClient.fetchAircraft()
            lastGoodFetch = Date()
            connected = true
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

            if n.airlineIcao != nil {
                let lat = n.lat ?? home?.lat ?? 0
                let lon = n.lon ?? home?.lon ?? 0
                routeClient.queueLookup(callsign: n.cs, lat: lat, lon: lon)
            }

            let hex = n.hex
            if planes[hex]?.typeLabel == nil {
                Task {
                    if let label = await typeClient.lookupType(hex: hex) {
                        self.planes[hex]?.typeLabel = label
                    }
                }
            }
        }

        planes = planes.filter { seen.contains($0.key) }
        aircraftCount = planes.values.filter { $0.range <= rangeNm }.count
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
