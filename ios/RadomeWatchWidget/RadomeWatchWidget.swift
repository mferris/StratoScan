import SwiftUI
import WidgetKit

/// Watch complications (roadmap 3.1): how many aircraft the radar hears, and
/// the nearest one. Same data as the iPhone widget, read from the same radar.
struct WatchEntry: TimelineEntry {
    let date: Date
    let nearby: Nearby?
}

struct WatchProvider: TimelineProvider {
    func placeholder(in context: Context) -> WatchEntry { WatchEntry(date: .now, nearby: nil) }
    func getSnapshot(in context: Context, completion: @escaping (WatchEntry) -> Void) {
        Task { completion(WatchEntry(date: .now, nearby: try? await Nearby.load())) }
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<WatchEntry>) -> Void) {
        Task {
            let entry = WatchEntry(date: .now, nearby: try? await Nearby.load())
            // The Watch budgets complication refreshes; every 15 minutes is its norm.
            completion(Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(15 * 60))))
        }
    }
}

struct WatchComplicationView: View {
    @Environment(\.widgetFamily) private var family
    let entry: WatchEntry

    var body: some View {
        switch family {
        case .accessoryCircular:
            VStack(spacing: 0) {
                Image(systemName: "airplane").font(.caption2)
                Text(entry.nearby.map { "\($0.count)" } ?? "–").font(.system(.title3, design: .rounded)).bold()
            }
        case .accessoryInline:
            Text(inline)
        default:
            VStack(alignment: .leading, spacing: 1) {
                Text(entry.nearby.map { "\($0.count) AIRCRAFT" } ?? "STRATOSCAN").font(.headline)
                if let p = entry.nearby?.planes.first {
                    Text("\(p.callsign) · \(p.altitudeText)").font(.caption)
                    Text(String(format: "%.1f NM %@", p.distanceNm, p.direction)).font(.caption2)
                } else {
                    Text("Nothing nearby").font(.caption)
                }
            }
        }
    }

    private var inline: String {
        guard let n = entry.nearby else { return "StratoScan" }
        if let p = n.planes.first { return "\(n.count) ✈ · \(p.callsign)" }
        return "\(n.count) aircraft"
    }
}

@main
struct RadomeWatchWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "StratoScanWatchNearby", provider: WatchProvider()) { entry in
            WatchComplicationView(entry: entry).containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("StratoScan")
        .description("Aircraft your StratoScan radar hears, and the nearest.")
        .supportedFamilies([.accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}
