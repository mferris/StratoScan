import AVFoundation
import CoreMotion
import SwiftUI

/// Sky view (roadmap 2.5): hold the phone up and see each aircraft's label
/// over the camera picture, where the aircraft actually is. Tap a label for
/// its details.
///
/// The camera is only a picture here; where the phone points comes from its
/// motion sensors (gravity plus compass, CMDeviceMotion), and each aircraft's
/// bearing and elevation -- from its position and altitude -- is projected
/// onto the screen. The first version used ARKit world tracking, which never
/// started on a real phone (no picture, labels frozen), and needs visual
/// features that a blank sky doesn't have anyway.
///
/// Aimed from the phone's location when allowed, the radar's otherwise. Away
/// from the radar, and only if the owner turns it on here, it also shows the
/// aircraft around the phone from adsb.lol -- the one time the phone's
/// location leaves it, rounded to about 5 km first. The camera picture is
/// never recorded or sent.
struct SkyView: View {
    @ObservedObject var viewModel: RadarViewModel
    @ObservedObject var location: PhoneLocation
    @StateObject private var motion = SkyMotion()
    @StateObject private var camera = SkyCamera()
    @State private var cameraDenied = false
    @State private var selected: String?
    @State private var sideways: SidewaysDetail?
    @AppStorage("stratoscan.skyNearMe") private var nearMeOn = false
    @Environment(\.dismiss) private var dismiss
    /// Opened from an aircraft's details ("Find in the sky"): that aircraft
    /// is always shown -- label, track, or an arrow to it -- and picked out.
    var focus: String? = nil
    /// Back to the radar with the focused aircraft selected there again.
    var backToRadar: ((String) -> Void)? = nil

    /// Further than this from the radar, its own aircraft no longer cover
    /// the sky overhead, so Sky view offers the ones around the phone.
    private static let awayNm = 3.0
    /// A label's frame (room for callsign, type, altitude and range); its
    /// ring's centre sits 11 pt below the top.
    private static let labelSize = CGSize(width: 180, height: 88)
    private static let ringAnchor = UnitPoint(x: 0.5, y: 11 / 88)

    var body: some View {
        GeometryReader { geo in
            ZStack {
                Color.black
                CameraPreview(session: camera.session)
                // redrawn 30 times a second, so labels glide between reports
                TimelineView(.animation(minimumInterval: 1.0 / 30)) { _ in
                    ZStack {
                        tracks(in: geo.size)
                        labels(in: geo.size)
                    }
                }
                VStack(spacing: 12) {
                    HStack(alignment: .top) {
                        if let focus, let back = backToRadar {
                            Button { back(focus) } label: {
                                Label("Back to the radar", systemImage: "chevron.left")
                                    .font(.callout.weight(.semibold))
                                    .padding(.horizontal, 12).padding(.vertical, 8)
                                    .background(.black.opacity(0.6), in: Capsule())
                                    .foregroundStyle(.white)
                            }
                        } else {
                            Text(status)
                                .font(.caption).padding(8).background(.black.opacity(0.55)).clipShape(Capsule())
                        }
                        Spacer()
                        Button { dismiss() } label: {
                            Image(systemName: "xmark.circle.fill").font(.title).foregroundStyle(.white, .black.opacity(0.5))
                        }
                        .accessibilityLabel("Close Sky view")
                    }
                    Spacer()
                    if let focus, let p = viewModel.plane(focus) {
                        Text("Finding \(p.cs)").font(.caption.weight(.semibold))
                            .padding(8).background(.black.opacity(0.55)).clipShape(Capsule()).foregroundStyle(.white)
                    }
                    if cameraDenied { settingsPrompt("Allow the camera to see the sky behind the labels.") }
                    if location.denied { settingsPrompt("Allow location to aim from where you stand.") }
                    if isAway && !nearMeOn { nearMePrompt }
                    if isAway && nearMeOn {
                        Button("Stop showing aircraft around me") { nearMeOn = false }
                            .font(.caption).padding(8).background(.black.opacity(0.6)).clipShape(Capsule())
                    }
                }
                .padding(.horizontal).padding(.top, 56).padding(.bottom, 40)
                // whose view this is
                VStack {
                    Spacer()
                    StratoScanLogo(height: 26, onLight: false).opacity(0.85).padding(.bottom, 14)
                }
                .allowsHitTesting(false)
                if let d = sideways { sidewaysPanel(d, in: geo.size) }
            }
            .ignoresSafeArea()
        }
        .onAppear {
            location.start()
            motion.start()
            camera.start { granted in cameraDenied = !granted }
        }
        .onDisappear {
            motion.stop()
            camera.stop()
            viewModel.nearMe = [:]
        }
        // Aircraft around the phone, every 5 s, while away and turned on.
        .task(id: nearMeKey) {
            guard nearMeOn, isAway, let me = location.coordinate else { viewModel.nearMe = [:]; return }
            while !Task.isCancelled {
                if let list = await NearMeFeed.fetch(around: me) { NearMeFeed.apply(list, from: me, to: viewModel) }
                try? await Task.sleep(for: .seconds(5))
            }
        }
        .sheet(item: Binding(get: { selected.map(SkySelection.init) }, set: { selected = $0?.id })) { sel in
            AircraftDetailView(viewModel: viewModel, location: location, hex: sel.id)
                .preferredColorScheme(.dark)
        }
    }

    /// How far the phone is from the radar, when both are known.
    private var distanceFromRadar: Double? {
        guard let me = location.coordinate, let home = viewModel.home else { return nil }
        return Geo.haversineBearingRange(lat1: home.lat, lon1: home.lon, lat2: me.lat, lon2: me.lon).range
    }
    private var isAway: Bool { (distanceFromRadar ?? 0) > Self.awayNm }
    /// Restarts the near-me polling when it is switched, or the phone moves
    /// to a different ~5 km square.
    private var nearMeKey: String {
        guard nearMeOn, isAway, let me = location.coordinate else { return "off" }
        let r = NearMeFeed.rounded(me)
        return "\(r.lat),\(r.lon)"
    }

    /// Where the aircraft is now, not where it was at its last report.
    /// Reports come once a second from the radar, and every 5 s from
    /// adsb.lol; placed at each report, labels jumped from one to the next.
    /// In between, each moves along its own speed and track, at most 10 s
    /// ahead, so a stale report can't fly a label off into the distance.
    static func estimatedPosition(_ p: PlaneState, at now: Date) -> Coordinate? {
        guard let lat = p.lat, let lon = p.lon else { return nil }
        let age = min(10, max(0, now.timeIntervalSince(p.lastSeen)))
        guard let gs = p.speed, gs > 30, age > 0 else { return Coordinate(lat: lat, lon: lon) }
        let nm = gs * age / 3600
        let t = p.hdg * .pi / 180
        return Coordinate(lat: lat + nm * cos(t) / 60,
                          lon: lon + nm * sin(t) / (60 * cos(lat * .pi / 180)))
    }

    private var status: String {
        if !motion.available { return "This phone can't tell which way it's pointing." }
        if location.coordinate == nil { return "Aimed from the radar." }
        if isAway && nearMeOn { return "Aircraft around you, from adsb.lol." }
        return "Point the phone at the sky."
    }

    /// An aircraft's details, turned a quarter to read upright with the phone
    /// held sideways. Tap outside it, or the close button, to go back.
    @ViewBuilder
    private func sidewaysPanel(_ d: SidewaysDetail, in size: CGSize) -> some View {
        let close = { withAnimation(.easeOut(duration: 0.2)) { sideways = nil } }
        Color.black.opacity(0.35).onTapGesture(perform: close).transition(.opacity)
        // Turned by UIKit, not .rotationEffect: on a real phone SwiftUI drew
        // the turned panel as a flattened picture and its text came out soft
        // (the photo, already a picture, didn't). A view transform keeps the
        // text drawn at full resolution.
        TurnedHost(angle: d.angle.radians, content:
            VStack(spacing: 0) {
                HStack {
                    Spacer()
                    Button(action: close) {
                        Image(systemName: "xmark.circle.fill").font(.title2).foregroundStyle(.white, .gray.opacity(0.4))
                    }
                    .accessibilityLabel("Close details")
                }
                .padding([.top, .horizontal], 12)
                AircraftDetailView(viewModel: viewModel, location: location, hex: d.hex)
                    .noScrollEdgeBlur()
            }
            .background(Color.black.opacity(0.9))
            .environment(\.colorScheme, .dark)
            .clipShape(RoundedRectangle(cornerRadius: 16)))
        // the screen space it takes, upright; inside, it runs along the long side
        .frame(width: size.width - 24, height: size.height - 100)
        .position(x: size.width / 2, y: size.height / 2)
        .transition(.opacity)
    }

    private func settingsPrompt(_ text: String) -> some View {
        HStack {
            Text(text).font(.caption)
            Spacer()
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
            }
            .font(.caption.bold())
        }
        .padding(10).background(.black.opacity(0.7)).clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var nearMePrompt: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(String(format: "You're %.0f nm from the radar. Show the aircraft around you instead?", distanceFromRadar ?? 0))
                .font(.callout)
            Text("They come from adsb.lol, a public network. To ask for them the app sends adsb.lol your location, rounded to about 5 km. Nothing else leaves the phone, and you can turn it off here at any time.")
                .font(.caption).foregroundColor(.secondary)
            Button("Show aircraft around me") { nearMeOn = true }
                .buttonStyle(.borderedProminent)
        }
        .padding(12).background(.black.opacity(0.75)).clipShape(RoundedRectangle(cornerRadius: 12))
    }

    /// The aircraft Sky view shows: the radar's, and around the phone when
    /// that is on. The radar's copy wins when both have one.
    private var shown: [PlaneState] {
        var list = viewModel.planes.values.filter { $0.range <= viewModel.ringNm }
        let have = Set(list.map(\.hex))
        list += viewModel.nearMe.values.filter { !have.contains($0.hex) }
        return list
    }

    /// Where a point in the sky lands on the screen, or nil when it's behind
    /// the phone. The same projection as the labels: bearing and elevation
    /// from `from`, turned into the phone's axes by its attitude.
    private static func project(lat: Double, lon: Double, altFt: Double, from: Coordinate,
                                m: simd_double3x3, size: CGSize, f: CGFloat) -> CGPoint? {
        let br = Geo.haversineBearingRange(lat1: from.lat, lon1: from.lon, lat2: lat, lon2: lon)
        let el = atan2(altFt * 0.3048, max(br.range * 1852, 1))
        let b = br.bearing * .pi / 180
        let d = m * SIMD3(cos(el) * cos(b), -cos(el) * sin(b), sin(el))
        guard d.z < -0.05 else { return nil }
        return CGPoint(x: size.width / 2 + CGFloat(d.x / -d.z) * f, y: size.height / 2 - CGFloat(d.y / -d.z) * f)
    }

    /// Each aircraft's path across the sky (#40), under the labels: a fading
    /// line through where it has been, and a dotted one along where it's
    /// going for the next minute. For the nearest few and the one tapped
    /// open -- more than that and the sky fills with lines.
    private func tracks(in size: CGSize) -> some View {
        Canvas { ctx, _ in
            guard let from = location.coordinate ?? viewModel.home, let m = motion.deviceFromWorld else { return }
            let f = (size.height / 2) / tan(camera.fieldOfView * .pi / 360)
            let now = Date()
            let near = shown.compactMap { p -> (PlaneState, Coordinate, Double)? in
                guard let fix = Self.estimatedPosition(p, at: now) else { return nil }
                return (p, fix, Geo.haversineBearingRange(lat1: from.lat, lon1: from.lon, lat2: fix.lat, lon2: fix.lon).range)
            }
            .sorted { $0.2 < $1.2 }
            let picked = Set(near.prefix(5).map { $0.0.hex } + [selected, sideways?.hex, focus].compactMap { $0 })
            for (p, fix, _) in near where picked.contains(p.hex) {
                let colour = Palette.classic.altColor(p.alt)
                let fade = p.isNetwork ? 0.5 : 1.0
                let altNow = p.alt == .ground ? 0 : (p.alt.feetValue ?? p.history.last?.altFt ?? 0)
                // where it's been: segment by segment, older ones fainter
                let past = p.history + [PlaneState.Fix(lat: fix.lat, lon: fix.lon, altFt: altNow, at: now)]
                var prev: CGPoint? = nil
                for pt in past {
                    let here = Self.project(lat: pt.lat, lon: pt.lon, altFt: pt.altFt, from: from, m: m, size: size, f: f)
                    if let a = prev, let b = here {
                        let age = now.timeIntervalSince(pt.at)
                        var seg = Path(); seg.move(to: a); seg.addLine(to: b)
                        ctx.stroke(seg, with: .color(colour.opacity(fade * max(0.12, 0.75 * (1 - age / PlaneState.historySeconds)))),
                                   style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    }
                    prev = here
                }
                // where it's going: along its track and speed, a minute ahead
                guard let gs = p.speed, gs > 30 else { continue }
                var ahead = Path()
                var started = false
                for k in 0...6 {
                    let nm = gs * Double(k * 10) / 3600
                    let t = p.hdg * .pi / 180
                    let la = fix.lat + nm * cos(t) / 60
                    let lo = fix.lon + nm * sin(t) / (60 * cos(fix.lat * .pi / 180))
                    guard let q = Self.project(lat: la, lon: lo, altFt: altNow, from: from, m: m, size: size, f: f) else { started = false; continue }
                    if started { ahead.addLine(to: q) } else { ahead.move(to: q); started = true }
                }
                ctx.stroke(ahead, with: .color(colour.opacity(fade * 0.6)),
                           style: StrokeStyle(lineWidth: 2, lineCap: .round, dash: [3, 7]))
            }
        }
        .allowsHitTesting(false)
    }

    /// Each aircraft's label where it is on screen; for the nearest few that
    /// are out of view, an arrow at the edge pointing the way to turn.
    private func labels(in size: CGSize) -> some View {
        let from = location.coordinate ?? viewModel.home
        var offscreen: [(PlaneState, CGPoint, Angle, Double)] = []
        let placed: [(PlaneState, CGPoint, Double)] = {
            guard let from, let m = motion.deviceFromWorld else { return [] }
            // Portrait, aspect-fill: the screen's height spans the camera's
            // full wide field of view (its long side).
            let f = (size.height / 2) / tan(camera.fieldOfView * .pi / 360)
            let now = Date()
            return shown.compactMap { p in
                guard let fix = Self.estimatedPosition(p, at: now) else { return nil }
                let br = Geo.haversineBearingRange(lat1: from.lat, lon1: from.lon, lat2: fix.lat, lon2: fix.lon)
                let upM = (p.alt.feetValue ?? 0) * 0.3048
                let el = atan2(upM, max(br.range * 1852, 1))
                let b = br.bearing * .pi / 180
                // world: x north, y west, z up (CoreMotion's xTrueNorthZVertical)
                let w = SIMD3(cos(el) * cos(b), -cos(el) * sin(b), sin(el))
                let d = m * w   // device: x right, y up the screen, z out of the screen
                let onScreen: CGPoint? = {
                    guard d.z < -0.05 else { return nil }   // the back camera looks along -z
                    let pt = CGPoint(x: size.width / 2 + CGFloat(d.x / -d.z) * f,
                                     y: size.height / 2 - CGFloat(d.y / -d.z) * f)
                    return pt.x > -60 && pt.x < size.width + 60 && pt.y > -60 && pt.y < size.height + 60 ? pt : nil
                }()
                if let pt = onScreen { return (p, pt, br.range) }
                // Out of view: which way across the screen it lies (behind
                // the phone too: the arrow then says which way to turn).
                let ux = CGFloat(d.x), uy = CGFloat(-d.y)
                let len = hypot(ux, uy)
                if len > 0.02 {
                    let margin: CGFloat = 44
                    let t = min((size.width / 2 - margin) / max(abs(ux / len), 0.001),
                                (size.height / 2 - margin) / max(abs(uy / len), 0.001))
                    let edge = CGPoint(x: size.width / 2 + ux / len * t, y: size.height / 2 + uy / len * t)
                    offscreen.append((p, edge, .radians(atan2(ux, -uy)), br.range))
                }
                return nil
            }
        }()
        // only the nearest few, or the edges fill with arrows
        // the focused aircraft always gets its arrow, first
        let arrows = offscreen.sorted { ($0.0.hex == focus ? -1 : $0.3) < ($1.0.hex == focus ? -1 : $1.3) }.prefix(5)
        return ZStack {
            ForEach(placed, id: \.0.hex) { p, pt, range in
                Button {
                    // Held sideways, the details open sideways too: a panel
                    // turned to face the viewer, as the labels are. Turning
                    // the whole app instead showed it portrait first, then
                    // swung round -- and swung the camera picture with it.
                    if let angle = motion.sidewaysAngle {
                        withAnimation(.easeOut(duration: 0.2)) { sideways = SidewaysDetail(hex: p.hex, angle: angle) }
                    } else {
                        selected = p.hex
                    }
                } label: {
                    // The ring sits on the aircraft; the text hangs below it,
                    // and the pair turns about the ring to stay upright
                    // however the phone is held (the app itself is portrait).
                    ZStack(alignment: .top) {
                        // the aircraft being found: a white double ring
                        if p.hex == focus {
                            Circle().stroke(.white, lineWidth: 2).frame(width: 34, height: 34).offset(y: -6)
                        }
                        Circle().stroke(Palette.classic.altColor(p.alt), lineWidth: 2).frame(width: 22, height: 22)
                        VStack(spacing: 1) {
                            Text(p.cs).font(.system(size: 14, weight: .bold, design: .monospaced))
                            // What it is, when known: "Boeing 737-900", or
                            // just the code ("P32R") for aircraft around you
                            if let type = p.typeLabel {
                                Text(type).font(.system(size: 11)).lineLimit(1).truncationMode(.tail)
                                    .frame(maxWidth: Self.labelSize.width - 12)
                            }
                            Text("\(PlaneState.altLabel(p.alt)) · \(String(format: "%.1f", range)) nm")
                                .font(.system(size: 11, design: .monospaced))
                        }
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 6).padding(.vertical, 3)
                        .background(.black.opacity(0.4)).clipShape(RoundedRectangle(cornerRadius: 6))
                        .padding(.top, 26)
                    }
                    .foregroundColor(Palette.classic.altColor(p.alt))
                    .frame(width: Self.labelSize.width, height: Self.labelSize.height, alignment: .top)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .opacity(p.isNetwork ? 0.65 : 1)
                .rotationEffect(motion.upright, anchor: Self.ringAnchor)
                // put the ring's centre, not the frame's, on the aircraft
                .offset(y: Self.labelSize.height / 2 - 11)
                .position(pt)
                .accessibilityLabel("\(p.cs), \(p.typeLabel.map { "\($0), " } ?? "")\(PlaneState.altLabel(p.alt)), \(String(format: "%.1f", range)) nautical miles")
            }
            ForEach(Array(arrows), id: \.0.hex) { p, edge, angle, range in
                Button { selected = p.hex } label: {
                    VStack(spacing: 2) {
                        Image(systemName: "chevron.up")
                            .font(.system(size: 22, weight: .bold))
                            .rotationEffect(angle - motion.upright)
                        Text(p.cs).font(.system(size: 11, weight: .semibold, design: .monospaced))
                        Text(String(format: "%.0f nm", range)).font(.system(size: 10, design: .monospaced))
                    }
                    .foregroundColor(Palette.classic.altColor(p.alt))
                    .padding(6)
                    .background(.black.opacity(0.35), in: RoundedRectangle(cornerRadius: 8))
                    .rotationEffect(motion.upright)
                }
                .buttonStyle(.plain)
                .opacity(p.isNetwork ? 0.65 : 1)
                .position(edge)
                .accessibilityLabel("\(p.cs), out of view, \(String(format: "%.0f", range)) nautical miles")
            }
        }
    }
}

private struct SkySelection: Identifiable { let id: String }
private struct SidewaysDetail: Equatable { let hex: String; let angle: Angle }

private extension View {
    /// iOS 26 blurs scrolling content where it meets a bar or the edge of the
    /// screen. In the turned panel there is no bar, and that blur lay over
    /// the top of the details: text and photo went soft as they scrolled up.
    @ViewBuilder func noScrollEdgeBlur() -> some View {
        if #available(iOS 26, *) {
            scrollEdgeEffectHidden(true, for: .all)
        } else {
            self
        }
    }
}

/// Shows SwiftUI content turned a quarter, by giving it the swapped bounds
/// and a UIKit transform.
private struct TurnedHost<Content: View>: UIViewControllerRepresentable {
    let angle: Double
    let content: Content

    func makeUIViewController(context: Context) -> TurnedController<Content> {
        TurnedController(root: content, angle: angle)
    }
    func updateUIViewController(_ vc: TurnedController<Content>, context: Context) {
        vc.host.rootView = content
    }
}

private final class TurnedController<Content: View>: UIViewController {
    let host: UIHostingController<Content>
    private let angle: CGFloat

    init(root: Content, angle: Double) {
        host = UIHostingController(rootView: root)
        self.angle = angle
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("not used") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear
        host.view.backgroundColor = .clear
        host.safeAreaRegions = []   // the phone's safe areas are the wrong way round in here
        addChild(host)
        view.addSubview(host.view)
        host.didMove(toParent: self)
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        let b = view.bounds
        host.view.transform = .identity
        host.view.bounds = CGRect(x: 0, y: 0, width: b.height, height: b.width)
        host.view.center = CGPoint(x: b.midX, y: b.midY)
        host.view.transform = CGAffineTransform(rotationAngle: angle)
    }
}


/// Aircraft around the phone, from adsb.lol's public API -- the same source
/// the radar's network comparison uses.
enum NearMeFeed {
    static let radiusNm = 25

    /// About 5 km: enough to find the sky's aircraft, not enough to find a house.
    static func rounded(_ c: Coordinate) -> Coordinate {
        Coordinate(lat: (c.lat * 20).rounded() / 20, lon: (c.lon * 20).rounded() / 20)
    }

    private struct Response: Decodable { let ac: [RawAircraft]? }
    struct Extra: Decodable { let hex: String; let r: String?; let t: String? }
    private struct ExtraResponse: Decodable { let ac: [Extra]? }

    static func fetch(around me: Coordinate) async -> [(RawAircraft, Extra?)]? {
        let at = rounded(me)
        guard let url = URL(string: String(format: "https://api.adsb.lol/v2/point/%.2f/%.2f/%d", at.lat, at.lon, radiusNm)) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("StratoScan/1.0 (iOS app; Sky view)", forHTTPHeaderField: "User-Agent")
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let list = try? JSONDecoder().decode(Response.self, from: data).ac else { return nil }
        let extras = (try? JSONDecoder().decode(ExtraResponse.self, from: data).ac) ?? []
        let byHex = Dictionary(extras.map { ($0.hex, $0) }, uniquingKeysWith: { a, _ in a })
        return list.map { ($0, byHex[$0.hex]) }
    }

    @MainActor
    static func apply(_ list: [(RawAircraft, Extra?)], from me: Coordinate, to vm: RadarViewModel) {
        var next: [String: PlaneState] = [:]
        for (raw, extra) in list {
            guard let n = NormalizedAircraft.normalize(raw, home: me, trustPrecomputed: false) else { continue }
            let p = vm.nearMe[raw.hex] ?? PlaneState(hex: raw.hex, from: n)
            p.apply(n)
            p.isNetwork = true
            if let r = extra?.r { p.reg = r }
            if let t = extra?.t { p.typeLabel = t }
            next[raw.hex] = p
        }
        vm.nearMe = next
    }
}

/// Which way the phone points, 30 times a second.
@MainActor
final class SkyMotion: ObservableObject {
    /// Turns a direction in the world (north, west, up) into the phone's own
    /// axes (right, up the screen, out of the screen).
    @Published private(set) var deviceFromWorld: simd_double3x3?
    /// How far to turn a label so it reads upright, however the phone is held.
    @Published private(set) var upright: Angle = .zero
    private let manager = CMMotionManager()
    var available: Bool { manager.isDeviceMotionAvailable }
    /// Which way round CoreMotion's matrix goes, settled from gravity (below).
    private var transposed: Bool?
    /// Gravity across the screen, last reading.
    private var lastGravity = SIMD2<Double>(0, -1)

    /// When the phone is held sideways, the quarter turn that makes a panel
    /// read upright: gravity toward the phone's right edge means it has been
    /// turned clockwise, so the panel turns back the other way.
    var sidewaysAngle: Angle? {
        if lastGravity.x > 0.6 { return .degrees(-90) }
        if lastGravity.x < -0.6 { return .degrees(90) }
        return nil
    }

    func start() {
        guard manager.isDeviceMotionAvailable, !manager.isDeviceMotionActive else { return }
        let frames = CMMotionManager.availableAttitudeReferenceFrames()
        let frame: CMAttitudeReferenceFrame = frames.contains(.xTrueNorthZVertical) ? .xTrueNorthZVertical : .xMagneticNorthZVertical
        manager.deviceMotionUpdateInterval = 1.0 / 30
        manager.startDeviceMotionUpdates(using: frame, to: .main) { [weak self] motion, _ in
            guard let self, let motion else { return }
            self.update(motion)
        }
    }

    func stop() { manager.stopDeviceMotionUpdates() }

    private func update(_ motion: CMDeviceMotion) {
        let r = motion.attitude.rotationMatrix
        let a = simd_double3x3(rows: [SIMD3(r.m11, r.m12, r.m13), SIMD3(r.m21, r.m22, r.m23), SIMD3(r.m31, r.m32, r.m33)])
        // Whether this matrix takes world to device or device to world is easy
        // to get backwards and can't be tested off a real phone, so the phone
        // settles it: gravity, measured in the phone's own axes, must equal
        // "down" in the world turned by the right one. Only decidable while
        // the phone is tilted -- flat, both agree -- so it is fixed the first
        // time they clearly differ, and the usual reading is assumed till then.
        let g = SIMD3(motion.gravity.x, motion.gravity.y, motion.gravity.z)
        let down = SIMD3<Double>(0, 0, -1)
        let errA = simd_length(a * down - g), errB = simd_length(a.transpose * down - g)
        if transposed == nil, abs(errA - errB) > 0.5 { transposed = errB < errA }
        deviceFromWorld = (transposed ?? false) ? a.transpose : a

        // Upright on screen is against gravity's pull across the screen. Held
        // almost flat (pointing straight up) that pull is too small to say,
        // so the last angle stands.
        lastGravity = SIMD2(g.x, g.y)
        if hypot(g.x, g.y) > 0.3 {
            upright = .radians(atan2(-g.x, -g.y))
        }
    }
}

/// The back camera, as a picture only.
final class SkyCamera: ObservableObject {
    let session = AVCaptureSession()
    /// The camera's field of view across its long side, in degrees.
    private(set) var fieldOfView: Double = 65
    private var configured = false

    func start(_ done: @escaping @MainActor (Bool) -> Void) {
        AVCaptureDevice.requestAccess(for: .video) { granted in
            Task { @MainActor in done(granted) }
            guard granted else { return }
            DispatchQueue.global(qos: .userInitiated).async { [self] in
                if !configured, let cam = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                   let input = try? AVCaptureDeviceInput(device: cam), session.canAddInput(input) {
                    session.beginConfiguration()
                    session.sessionPreset = .high
                    session.addInput(input)
                    session.commitConfiguration()
                    fieldOfView = Double(cam.activeFormat.videoFieldOfView)
                    configured = true
                }
                if !session.isRunning { session.startRunning() }
            }
        }
    }

    func stop() {
        DispatchQueue.global(qos: .userInitiated).async { [session] in session.stopRunning() }
    }
}

private struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }

    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.preview.session = session
        v.preview.videoGravity = .resizeAspectFill
        return v
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}
}
