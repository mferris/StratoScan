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

struct StratoScanWidgetView: View {
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
            HStack(spacing: 5) {
                StratoScanMark(small: true).frame(width: 14, height: 14)
                Text(entry.demo ? "STRATOSCAN · DEMO" : "STRATOSCAN")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .lineLimit(1).minimumScaleFactor(0.7)
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
struct StratoScanWidgets: WidgetBundle {
    var body: some Widget {
        StratoScanWidget()
        RadarWidget()
        ApproachLiveActivity()
    }
}

/// The radar as a widget (roadmap 2.4): the aircraft as dots around the
/// radar, and the count. Made for StandBy -- an iPhone charging on its side
/// at night -- where iOS shows it large and tints it red in the dark; it
/// works on the home screen too. Refreshes on iOS's widget budget, so it's a
/// picture of the last few minutes, not a live radar.
struct RadarWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "StratoScanRadar", provider: Provider()) { entry in
            RadarWidgetView(entry: entry).containerBackground(.black, for: .widget)
        }
        .configurationDisplayName("Radar")
        .description("The aircraft around your StratoScan radar, as a radar. Good in StandBy.")
        .supportedFamilies([.systemSmall, .systemLarge])
        .notInCarPlay()
    }
}

private extension WidgetConfiguration {
    /// CarPlay (iOS 26) offers small widgets on the car's screen. A moving
    /// radar is not something to put in front of a driver, so this one is
    /// kept off it; "Aircraft overhead" -- a count and the nearest, in words
    /// -- is the one for the car (roadmap 2.20).
    func notInCarPlay() -> some WidgetConfiguration {
        if #available(iOS 26.0, *) {
            return disfavoredLocations([.carPlay], for: [.systemSmall, .systemLarge])
        } else {
            return self
        }
    }
}

struct RadarWidgetView: View {
    let entry: Entry
    private let teal = Color(red: 0.31, green: 0.84, blue: 0.78)
    private let amber = Color(red: 1.0, green: 0.69, blue: 0.13)

    var body: some View {
        ZStack {
            Canvas { ctx, size in
                let c = CGPoint(x: size.width / 2, y: size.height / 2)
                let r = min(size.width, size.height) / 2 - 2
                for f in [0.5, 1.0] {
                    ctx.stroke(Path(ellipseIn: CGRect(x: c.x - r * f, y: c.y - r * f, width: 2 * r * f, height: 2 * r * f)),
                               with: .color(teal.opacity(0.35)), lineWidth: 1)
                }
                ctx.fill(Path(ellipseIn: CGRect(x: c.x - 2.5, y: c.y - 2.5, width: 5, height: 5)), with: .color(amber))
                for p in entry.nearby?.planes ?? [] {
                    let ang = (p.bearing - 90) * .pi / 180
                    let d = CGFloat(p.distanceNm / Nearby.rangeNm) * r
                    let pt = CGPoint(x: c.x + d * cos(ang), y: c.y + d * sin(ang))
                    let dot = Path(ellipseIn: CGRect(x: pt.x - 3.5, y: pt.y - 3.5, width: 7, height: 7))
                    ctx.fill(dot, with: .color(Color(red: 0.65, green: 0.55, blue: 0.98)))
                }
            }
            VStack {
                Spacer()
                Text(entry.nearby.map { "\($0.count) AIRCRAFT" } ?? "STRATOSCAN")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(teal)
            }
        }
    }
}

struct StratoScanWidget: Widget {
    var body: some WidgetConfiguration {
        // "RadomeNearby": the kind iOS knows placed widgets by -- renaming it would
        // silently remove every one already on someone's home screen. Kept.
        StaticConfiguration(kind: "RadomeNearby", provider: Provider()) { entry in
            if #available(iOS 17.0, *) {
                StratoScanWidgetView(entry: entry).containerBackground(.black, for: .widget)
            } else {
                StratoScanWidgetView(entry: entry).padding().background(Color.black)
            }
        }
        .configurationDisplayName("Aircraft overhead")
        .description("How many aircraft your StratoScan radar sees, and the nearest.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryInline, .accessoryCircular, .accessoryRectangular])
    }
}
