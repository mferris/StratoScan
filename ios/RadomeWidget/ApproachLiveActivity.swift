import ActivityKit
import SwiftUI
import WidgetKit

/// The lock-screen card and Dynamic Island for an approaching aircraft. The
/// countdown runs on the phone (Text timerInterval), so the relay only has
/// to start and end it.
struct ApproachLiveActivity: Widget {
    private let teal = Color(red: 0.31, green: 0.84, blue: 0.78)

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: ApproachAttributes.self) { context in
            lockScreen(context)
                .padding(16)
                .activityBackgroundTint(Color.black.opacity(0.85))
                .activitySystemActionForegroundColor(teal)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Label(context.attributes.callsign, systemImage: icon(context.attributes))
                        .font(.headline).lineLimit(1)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    countdown(context).font(.title3.monospacedDigit()).foregroundColor(teal)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text(detail(context)).font(.caption).foregroundColor(.secondary).lineLimit(1)
                }
            } compactLeading: {
                Image(systemName: icon(context.attributes)).foregroundColor(teal)
            } compactTrailing: {
                countdown(context).monospacedDigit().frame(maxWidth: 44)
            } minimal: {
                Image(systemName: icon(context.attributes)).foregroundColor(teal)
            }
        }
    }

    private func icon(_ a: ApproachAttributes) -> String {
        a.reason == "Helicopter" ? "fanblades.fill" : "airplane"
    }

    @ViewBuilder
    private func countdown(_ context: ActivityViewContext<ApproachAttributes>) -> some View {
        if context.state.passed || context.state.eta <= .now {
            Text("Overhead")
        } else {
            Text(timerInterval: Date.now...context.state.eta, countsDown: true)
        }
    }

    private func detail(_ context: ActivityViewContext<ApproachAttributes>) -> String {
        var parts = [context.attributes.reason]
        if !context.attributes.type.isEmpty { parts.append(context.attributes.type) }
        if let ft = context.state.altFt { parts.append("\(ft.formatted()) ft") }
        // dir is where the aircraft IS, seen from the radar; from/to are
        // which way it's travelling. "from the N" used to read as the latter.
        if let dir = context.state.dir { parts.append("\(dir) of the radar") }
        if let f = context.state.from, let t = context.state.to { parts.append("coming from the \(f), heading \(t)") }
        return parts.joined(separator: " · ")
    }

    /// A small north-up dial (widgets can't read the compass): a dot where the
    /// aircraft is, seen from the radar, and an arrow the way it's going.
    @ViewBuilder
    private func dial(_ context: ActivityViewContext<ApproachAttributes>) -> some View {
        let points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        let pos = context.state.dir.flatMap { points.firstIndex(of: $0) }.map { Double($0) * 45 }
        ZStack {
            Circle().stroke(teal.opacity(0.5), lineWidth: 1.5)
            Text("N").font(.system(size: 7, weight: .bold)).foregroundColor(teal).offset(y: -13)
            if let pos {
                Circle().fill(Color.white).frame(width: 5, height: 5)
                    .offset(y: -12).rotationEffect(.degrees(pos))
            }
            if let trk = context.state.trk {
                Image(systemName: "arrow.up").font(.system(size: 12, weight: .bold))
                    .foregroundColor(teal).rotationEffect(.degrees(Double(trk)))
            }
        }
        .frame(width: 34, height: 34)
    }

    private func lockScreen(_ context: ActivityViewContext<ApproachAttributes>) -> some View {
        HStack(spacing: 14) {
            if context.state.trk != nil {
                dial(context)
            } else {
                Image(systemName: icon(context.attributes))
                    .font(.title2).foregroundColor(teal)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text(context.attributes.callsign).font(.headline)
                Text(detail(context)).font(.caption).foregroundColor(.secondary).lineLimit(2)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                countdown(context).font(.title2.monospacedDigit()).foregroundColor(teal)
                Text(context.state.passed ? "passed" : "to overhead").font(.caption2).foregroundColor(.secondary)
            }
        }
        .foregroundColor(.white)
    }
}
