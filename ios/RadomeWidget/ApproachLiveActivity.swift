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
        if let dir = context.state.dir { parts.append("from the \(dir)") }
        return parts.joined(separator: " · ")
    }

    private func lockScreen(_ context: ActivityViewContext<ApproachAttributes>) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon(context.attributes))
                .font(.title2).foregroundColor(teal)
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
