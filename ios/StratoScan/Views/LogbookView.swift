import Charts
import SwiftUI

/// The logbook (roadmap 2.5): what this radar has seen, from the history it
/// keeps itself (deploy/sighting-store.py, /sightings/stats and
/// /sightings/year). Read-only, and readable from away too: the radar's
/// public page serves it.
struct LogbookView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var stats: LogStats?
    @State private var year: LogYear?
    @State private var failed = false

    var body: some View {
        NavigationStack {
            Group {
                if let stats {
                    List {
                        header(stats)
                        today(stats)
                        totals(stats)
                        records(stats)
                        overhead(stats)
                        hours(year?.hours ?? stats.hours)
                        regulars(stats)
                        if let year, year.ready == true { thisYear(year) }
                    }
                } else if failed {
                    ContentUnavailableView("Can't reach your radar",
                                           systemImage: "antenna.radiowaves.left.and.right.slash",
                                           description: Text("The logbook is kept on the radar itself. Try again on your home WiFi, or once the radar is online."))
                } else {
                    ProgressView("Opening the logbook…")
                }
            }
            .navigationTitle("Logbook")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .refreshable { await load() }
        }
        .task { await load() }
    }

    // MARK: sections

    private func header(_ s: LogStats) -> some View {
        Section {
            VStack(spacing: 8) {
                StratoScanLogo(height: 30)
                if let since = s.since {
                    Text("Keeping watch since \(Date(timeIntervalSince1970: since).formatted(date: .long, time: .omitted)) · \(s.days ?? 0) days")
                        .font(.caption).foregroundColor(.secondary)
                }
            }
            .frame(maxWidth: .infinity)
        }
        .listRowBackground(Color.clear)
    }

    private func today(_ s: LogStats) -> some View {
        Section("Today") {
            HStack {
                // the radar's daily tally counts visits, not distinct aircraft
                tile(Self.count(s.today?.total), "visits")
                tile(Self.count(s.today?.nearby), "close passes")
            }
        }
    }

    private func totals(_ s: LogStats) -> some View {
        Section("All time") {
            HStack {
                tile(Self.count(s.aircraft), "aircraft")
                tile(Self.count(s.visits), "visits")
                tile(Self.count(s.nearby), "close passes")
            }
            if let only = s.networkOnly, only > 0 {
                Text("Plus \(Self.count(only)) aircraft only the network saw, which the antenna didn't hear.")
                    .font(.caption).foregroundColor(.secondary)
            }
        }
    }

    private func records(_ s: LogStats) -> some View {
        Section("Records") {
            if let r = s.records?["far"] { record("Farthest heard", String(format: "%.1f nm", r.v), r) }
            if let r = s.records?["near"] { record("Closest pass", String(format: "%.1f nm", r.v), r) }
            if let r = s.records?["high"] { record("Highest", "\(Self.count(Int(r.v))) ft", r) }
            if let r = s.records?["fast"] { record("Fastest", "\(Int(r.v.rounded())) kt", r) }
        }
    }

    private func overhead(_ s: LogStats) -> some View {
        Section("What flies over") {
            let ops: [(String, String)] = [("com", "Airlines"), ("pri", "Private"), ("mil", "Military"), ("unk", "Unknown")]
            let kinds: [(String, String)] = [("jet", "Jets"), ("heavy", "Heavies"), ("prop", "Propeller"), ("heli", "Helicopters"), ("lta", "Airships")]
            breakdown(ops.compactMap { key, name in s.byOp?[key].map { (name, $0.ac) } })
            breakdown(kinds.compactMap { key, name in s.byKind?[key].flatMap { $0.ac > 0 ? (name, $0.ac) : nil } })
        }
    }

    private func hours(_ h: [Int]?) -> some View {
        Section("When they fly") {
            if let h, h.count == 24 {
                Chart(Array(h.enumerated()), id: \.offset) { hour, n in
                    BarMark(x: .value("Hour", hour), y: .value("Arrivals", n))
                        .foregroundStyle(Color(hex: "#5ee7ff").gradient)
                }
                .chartXAxis { AxisMarks(values: [0, 6, 12, 18]) { v in
                    AxisValueLabel { if let i = v.as(Int.self) { Text(Self.hourName(i)) } }
                } }
                .chartYAxis(.hidden)
                .frame(height: 120)
                if let busiest = h.indices.max(by: { h[$0] < h[$1] }) {
                    Text("Busiest around \(Self.hourName(busiest)).").font(.caption).foregroundColor(.secondary)
                }
            }
        }
    }

    private func regulars(_ s: LogStats) -> some View {
        Section("The regulars") {
            ForEach(s.top ?? [], id: \.hex) { t in
                HStack {
                    Text(t.cs ?? t.hex.uppercased()).font(.system(.body, design: .monospaced))
                    Text(Self.kindName(t.k)).font(.caption).foregroundColor(.secondary)
                    Spacer()
                    Text("\(t.visits) visits").foregroundColor(.secondary)
                }
            }
        }
    }

    private func thisYear(_ y: LogYear) -> some View {
        Section("\(String(y.year ?? 0))") {
            HStack {
                tile(Self.count(y.newAircraft), "first-time visitors")
                tile(Self.count(y.visits), "visits")
            }
            if let m = y.busiestMonth, (0..<12).contains(m) {
                Text("Busiest month: \(Calendar.current.monthSymbols[m]).").font(.caption).foregroundColor(.secondary)
            }
        }
    }

    // MARK: pieces

    private func tile(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.system(.title2, design: .monospaced)).bold()
            Text(label).font(.caption).foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func record(_ title: String, _ value: String, _ r: LogRecord) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                Text("\(r.cs ?? r.hex?.uppercased() ?? "") · \(r.at.map { Date(timeIntervalSince1970: $0).formatted(date: .abbreviated, time: .omitted) } ?? "")")
                    .font(.caption).foregroundColor(.secondary)
            }
            Spacer()
            Text(value).font(.system(.body, design: .monospaced))
        }
    }

    private func breakdown(_ parts: [(String, Int)]) -> some View {
        let total = max(1, parts.reduce(0) { $0 + $1.1 })
        return VStack(alignment: .leading, spacing: 6) {
            ForEach(parts, id: \.0) { name, n in
                HStack {
                    Text(name).frame(width: 96, alignment: .leading)
                    GeometryReader { g in
                        Capsule().fill(Color(hex: "#274a86"))
                            .frame(width: max(3, g.size.width * CGFloat(n) / CGFloat(total)))
                    }
                    .frame(height: 8)
                    Text(Self.count(n)).font(.system(.caption, design: .monospaced)).frame(width: 56, alignment: .trailing)
                }
            }
        }
        .padding(.vertical, 4)
    }

    static func count(_ n: Int?) -> String { (n ?? 0).formatted(.number) }
    static func hourName(_ h: Int) -> String {
        var c = DateComponents(); c.hour = h
        return Calendar.current.date(from: c).map { $0.formatted(.dateTime.hour()) } ?? "\(h)"
    }
    static func kindName(_ k: String?) -> String {
        ["jet": "jet", "heavy": "heavy", "prop": "propeller", "heli": "helicopter", "lta": "airship"][k ?? ""] ?? ""
    }

    // MARK: loading

    private func load() async {
        if DemoFeed.isOn { stats = .demo; year = nil; return }
        await Endpoint.shared.resolve()
        async let s: LogStats? = Self.get("/sightings/stats")
        async let y: LogYear? = Self.get("/sightings/year")
        let (st, yr) = await (s, y)
        if let st { stats = st; year = yr; failed = false } else if stats == nil { failed = true }
    }

    private static func get<T: Decodable>(_ path: String) async -> T? {
        var req = URLRequest(url: APIConfig.url(path), timeoutInterval: 10)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }
}

// The shapes /sightings/stats and /sightings/year return.
struct LogStats: Decodable {
    var since: Double?
    var days: Int?
    var aircraft: Int?
    var visits: Int?
    var nearby: Int?
    var networkOnly: Int?
    var byOp: [String: LogCount]?
    var byKind: [String: LogCount]?
    var hours: [Int]?
    var records: [String: LogRecord]?
    var today: LogToday?
    var top: [LogTop]?

    /// For demo mode, so the screen can be seen without a radar.
    static let demo = LogStats(
        since: Date().addingTimeInterval(-26 * 86400).timeIntervalSince1970, days: 26,
        aircraft: 9860, visits: 48831, nearby: 4122, networkOnly: 867,
        byOp: ["com": .init(ac: 4948), "pri": .init(ac: 3901), "mil": .init(ac: 229), "unk": .init(ac: 783)],
        byKind: ["jet": .init(ac: 6369), "heavy": .init(ac: 778), "prop": .init(ac: 2557), "heli": .init(ac: 126)],
        hours: [428, 198, 81, 121, 152, 288, 1211, 1691, 2404, 2343, 2597, 2608, 2540, 2904, 2587, 2898, 2562, 2367, 2315, 2110, 2038, 1814, 1354, 1049],
        records: ["far": .init(v: 79.5, cs: "UAL2054", at: Date().timeIntervalSince1970 - 86400 * 9),
                  "near": .init(v: 0.1, cs: "N752LA", at: Date().timeIntervalSince1970 - 86400 * 20),
                  "high": .init(v: 49025, cs: "LXJ660", at: Date().timeIntervalSince1970 - 86400 * 11),
                  "fast": .init(v: 559.5, cs: "KOW102", at: Date().timeIntervalSince1970 - 86400)],
        today: .init(total: 1444, nearby: 188),
        top: [.init(hex: "a00001", cs: "TRAINER1", visits: 152, k: "prop"),
              .init(hex: "a00002", cs: "DAL2026", visits: 97, k: "jet")])
}
struct LogCount: Decodable { var ac: Int }
struct LogRecord: Decodable { var v: Double; var hex: String? = nil; var cs: String?; var at: Double? }
struct LogToday: Decodable { var total: Int; var nearby: Int }
struct LogTop: Decodable { var hex: String; var cs: String?; var visits: Int; var k: String? }
struct LogYear: Decodable {
    var year: Int?
    var ready: Bool?
    var visits: Int?
    var newAircraft: Int?
    var hours: [Int]?
    var busiestMonth: Int?
}
