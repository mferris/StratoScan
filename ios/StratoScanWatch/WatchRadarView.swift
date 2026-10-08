import SwiftUI

/// The glance: a small radar with the aircraft as dots, the count, and the
/// nearest few. Refreshes every five seconds while it's on screen -- the
/// Watch's battery matters more than the kiosk's smoothness.
struct WatchRadarView: View {
    @State private var home: Coordinate?
    @State private var aircraft: [RawAircraft] = []
    @State private var nearby: Nearby?
    @State private var failed = false
    @ObservedObject private var receiver = WatchReceiver.shared

    private let rangeNm = Nearby.rangeNm

    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                StratoScanLogo(height: 18)
                radar.frame(width: 130, height: 130)
                if let nearby {
                    Text("\(nearby.count) AIRCRAFT").font(.system(.headline, design: .monospaced))
                    // the alert's aircraft first, when there is one (#61)
                    let listed = nearby.planes.sorted { a, b in (a.hex == receiver.highlightHex) && b.hex != receiver.highlightHex }
                    ForEach(Array(listed.prefix(3).enumerated()), id: \.offset) { _, p in
                        HStack {
                            Text(p.callsign).font(.system(.caption, design: .monospaced)).bold()
                                .foregroundColor(p.hex == receiver.highlightHex ? .yellow : .primary)
                            Spacer()
                            Text(String(format: "%.1f %@", p.distanceNm, p.direction)).font(.caption2)
                        }
                        Text(p.altitudeText).font(.caption2).foregroundColor(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                } else if failed {
                    Text("Can't reach the radar. Open StratoScan on your iPhone once to set it up.")
                        .font(.caption2).multilineTextAlignment(.center).foregroundColor(.secondary)
                } else {
                    ProgressView()
                }
            }
            .padding(.horizontal, 4)
        }
        .task {
            while !Task.isCancelled {
                await refresh()
                try? await Task.sleep(nanoseconds: 5_000_000_000)
            }
        }
    }

    private var radar: some View {
        Canvas { ctx, size in
            let c = CGPoint(x: size.width / 2, y: size.height / 2)
            let r = min(size.width, size.height) / 2 - 2
            for f in [0.5, 1.0] {
                ctx.stroke(Path(ellipseIn: CGRect(x: c.x - r * f, y: c.y - r * f, width: 2 * r * f, height: 2 * r * f)),
                           with: .color(Color(red: 0.16, green: 0.29, blue: 0.31)), lineWidth: 1)
            }
            ctx.fill(Path(ellipseIn: CGRect(x: c.x - 2, y: c.y - 2, width: 4, height: 4)), with: .color(.orange))
            guard let home else { return }
            for a in aircraft {
                guard let lat = a.lat, let lon = a.lon else { continue }
                let br = Geo.haversineBearingRange(lat1: home.lat, lon1: home.lon, lat2: lat, lon2: lon)
                guard br.range <= rangeNm else { continue }
                let ang = (br.bearing - 90) * .pi / 180
                let d = CGFloat(br.range / rangeNm) * r
                let p = CGPoint(x: c.x + d * cos(ang), y: c.y + d * sin(ang))
                let dot = Path(ellipseIn: CGRect(x: p.x - 3, y: p.y - 3, width: 6, height: 6))
                if a.hex == receiver.highlightHex {
                    ctx.stroke(Path(ellipseIn: CGRect(x: p.x - 7, y: p.y - 7, width: 14, height: 14)), with: .color(.yellow), lineWidth: 1.5)
                }
                if a.isNetwork { ctx.stroke(dot, with: .color(.gray), lineWidth: 1) }
                else { ctx.fill(dot, with: .color(Color(red: 0.65, green: 0.55, blue: 0.98))) }
            }
        }
    }

    private func refresh() async {
        do {
            if home == nil { home = try await AircraftFeedClient.fetchReceiver() }
            let list = try await AircraftFeedClient.fetchAircraft()
            aircraft = list
            if let home { nearby = Nearby.from(list, home: home) }
            failed = false
        } catch {
            failed = nearby == nil
        }
    }
}
