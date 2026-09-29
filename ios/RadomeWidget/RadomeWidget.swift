import SwiftUI
import WidgetKit

/// Home- and lock-screen widget: how many aircraft your radar sees, and the
/// nearest. iOS refreshes widgets on its own budget (about every 15 minutes);
/// the app asks for a refresh whenever it is opened. For a plane approaching
/// right now, the notification (and later the Live Activity) is the tool.
struct Entry: TimelineEntry {
    let date: Date
    let nearby: Nearby?
    let demo: Bool
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> Entry {
        Entry(date: .now, nearby: Nearby(count: 5, planes: [
            .init(callsign: "AAL174", altitudeText: "7,000 ft", distanceNm: 3.4, direction: "NE"),
            .init(callsign: "EDV5222", altitudeText: "6,300 ft", distanceNm: 5.1, direction: "S"),
        ]), demo: false)
    }

    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        if context.isPreview { completion(placeholder(in: context)); return }
        Task { completion(await load()) }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        Task {
            let entry = await load()
            completion(Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(15 * 60))))
        }
    }

    private func load() async -> Entry {
        let nearby = try? await Nearby.load()
        return Entry(date: .now, nearby: nearby, demo: DemoFeed.isOn)
    }
}

struct RadomeWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: Entry

    private func line(_ p: Nearby.Plane) -> String {
        "\(p.callsign) · \(p.altitudeText) · \(String(format: "%.0f", p.distanceNm * 1.15078)) mi \(p.direction)"
    }

    var body: some View {
        switch family {
        case .accessoryInline:
            if let n = entry.nearby {
                Text(n.planes.first.map { "✈︎ \(n.count) · \($0.callsign) \(String(format: "%.0f", $0.distanceNm * 1.15078)) mi \($0.direction)" }
                     ?? "✈︎ Quiet sky")
            } else {
                Text("✈︎ Radar not reachable")
            }
        case .accessoryCircular:
            VStack(spacing: 0) {
                Image(systemName: "airplane")
                Text(entry.nearby.map { "\($0.count)" } ?? "–").font(.title2.bold())
            }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                Text(entry.nearby.map { "✈︎ \($0.count) aircraft" } ?? "✈︎ Radar not reachable").font(.headline)
                if let p = entry.nearby?.planes.first {
                    Text(line(p)).font(.caption)
                }
            }
        default:
            homeScreen
        }
    }

    private var homeScreen: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(entry.demo ? "RADOME · DEMO" : "RADOME")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(Color(red: 0.36, green: 0.45, blue: 0.47))
                Spacer()
                Text(entry.date, style: .time).font(.system(size: 10)).foregroundColor(.secondary)
            }
            if let n = entry.nearby {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("\(n.count)").font(.system(size: 34, weight: .bold, design: .monospaced))
                    Text(n.count == 1 ? "aircraft" : "aircraft").font(.caption).foregroundColor(.secondary)
                }
                let shown = family == .systemSmall ? 1 : 3
                ForEach(Array(n.planes.prefix(shown).enumerated()), id: \.offset) { _, p in
                    Text(line(p)).font(.system(size: 11, design: .monospaced)).lineLimit(1).minimumScaleFactor(0.8)
                }
                if n.planes.isEmpty { Text("Quiet sky").font(.caption).foregroundColor(.secondary) }
            } else {
                Text("Radar not reachable").font(.callout)
                Text("Works on your home WiFi").font(.caption).foregroundColor(.secondary)
            }
            Spacer(minLength: 0)
        }
        .foregroundColor(Color(red: 0.81, green: 0.91, blue: 0.92))
    }
}

@main
struct RadomeWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "RadomeNearby", provider: Provider()) { entry in
            if #available(iOS 17.0, *) {
                RadomeWidgetView(entry: entry).containerBackground(.black, for: .widget)
            } else {
                RadomeWidgetView(entry: entry).padding().background(Color.black)
            }
        }
        .configurationDisplayName("Aircraft overhead")
        .description("How many aircraft your Radome radar sees, and the nearest.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryInline, .accessoryCircular, .accessoryRectangular])
    }
}
