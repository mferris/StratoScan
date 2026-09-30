import SwiftUI
import UIKit

/// A compass that points at one aircraft (roadmap 3.4, the phone's half).
///
/// The needle turns with the phone: it points at the aircraft whichever way
/// the phone faces. Around it: which way the aircraft is travelling, how
/// high to look, how far away it is, and a tap on the wrist -- a haptic --
/// when the phone is pointing right at it. Uses the phone's own position when
/// the owner has allowed it, the radar's otherwise (and says so); neither
/// leaves the phone.
struct CompassView: View {
    @ObservedObject var viewModel: RadarViewModel
    @ObservedObject var location: PhoneLocation
    let hex: String
    @Environment(\.dismiss) private var dismiss
    @State private var onTarget = false

    private static let points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    private static func compassPoint(_ deg: Double) -> String {
        points[Int(((deg.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360) / 45).rounded()) % 8]
    }

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.2)) { _ in
            let p = viewModel.planes[hex]
            let from = location.coordinate ?? viewModel.home
            VStack(spacing: 18) {
                Text(p?.cs ?? hex.uppercased())
                    .font(.system(size: 30, weight: .semibold, design: .monospaced))
                if let p, let from, let lat = p.lat, let lon = p.lon {
                    let br = Geo.haversineBearingRange(lat1: from.lat, lon1: from.lon, lat2: lat, lon2: lon)
                    let heading = location.heading ?? 0
                    let needle = br.bearing - heading
                    dial(needle: needle, track: p.hdg - heading, heading: heading)
                        .frame(width: 280, height: 280)
                        .onChange(of: Int(needle)) { _, _ in haptic(needle) }
                    details(p, bearing: br.bearing, rangeNm: br.range)
                    if location.heading == nil {
                        Text("Hold the phone flat to use its compass.").font(.caption).foregroundColor(.orange)
                    } else if let acc = location.headingAccuracy, acc > 25 {
                        Text("Compass needs calibrating: move the phone in a figure eight.").font(.caption).foregroundColor(.orange)
                    } else if !location.headingIsTrue {
                        Text("Pointing to magnetic north.").font(.caption).foregroundColor(.secondary)
                    }
                    if location.coordinate == nil {
                        Text("Measured from the radar, not from you. Allow location to aim from where you stand.")
                            .font(.caption).foregroundColor(.secondary).multilineTextAlignment(.center)
                    }
                } else {
                    Text(p == nil ? "Out of range now." : "No position yet.").foregroundColor(.secondary)
                }
                Spacer()
                Button("Done") { dismiss() }.buttonStyle(.bordered)
            }
            .padding(24)
        }
        .onAppear { location.startHeading() }
        .onDisappear { location.stopHeading() }
    }

    /// The dial: north mark (turns with the phone), the needle to the
    /// aircraft (gold), and a thin arrow for the way it is travelling.
    private func dial(needle: Double, track: Double, heading: Double) -> some View {
        ZStack {
            Circle().stroke(Color(hex: "#2a4a4f"), lineWidth: 2)
            Text("N").font(.system(size: 14, weight: .bold)).foregroundColor(Color(hex: "#4fd6c8"))
                .offset(y: -122).rotationEffect(.degrees(-heading))
            // which way the aircraft is going
            Capsule().fill(Color(hex: "#a78bfa").opacity(0.7))
                .frame(width: 3, height: 70).offset(y: -35)
                .rotationEffect(.degrees(track))
            // the needle: where the aircraft is
            Image(systemName: "location.north.fill")
                .resizable().scaledToFit().frame(width: 34)
                .foregroundColor(onTarget ? Color(hex: "#3ddc97") : Color(hex: "#ffb020"))
                .offset(y: -96)
                .rotationEffect(.degrees(needle))
            Circle().fill(Color(hex: "#ffb020")).frame(width: 8, height: 8)
        }
    }

    private func details(_ p: PlaneState, bearing: Double, rangeNm: Double) -> some View {
        let altFt = p.alt.feetValue
        let groundM = rangeNm * 1852
        let lookUp = altFt.map { atan2($0 * 0.3048, max(groundM, 1)) * 180 / .pi }
        let reciprocal = (p.hdg + 180).truncatingRemainder(dividingBy: 360)
        return VStack(spacing: 6) {
            Text(String(format: "%.1f NM %@", rangeNm, Self.compassPoint(bearing)))
                .font(.system(size: 20, design: .monospaced))
            if let lookUp {
                Text(String(format: "Look up %.0f°", lookUp)).font(.headline)
            }
            Text("Coming from the \(Self.compassPoint(reciprocal)), heading \(Self.compassPoint(p.hdg))")
                .foregroundColor(.secondary)
            Text(PlaneState.altLabel(p.alt) + (p.speed.map { " · \(Int($0))kt" } ?? ""))
                .font(.system(.caption, design: .monospaced)).foregroundColor(.secondary)
        }
    }

    /// One tap when the phone swings onto the aircraft (within 10 degrees),
    /// not a constant buzz while it stays there.
    private func haptic(_ needle: Double) {
        let off = abs((needle.truncatingRemainder(dividingBy: 360) + 540).truncatingRemainder(dividingBy: 360) - 180)
        let now = off < 10
        if now && !onTarget { UIImpactFeedbackGenerator(style: .medium).impactOccurred() }
        onTarget = now
    }
}
