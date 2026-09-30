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
    @AppStorage("stratoscan.skyNearMe") private var nearMeOn = false
    @Environment(\.dismiss) private var dismiss

    /// Further than this from the radar, its own aircraft no longer cover
    /// the sky overhead, so Sky view offers the ones around the phone.
    private static let awayNm = 3.0
    /// A label's frame; its ring's centre sits 11 pt below the top.
    private static let labelSize = CGSize(width: 150, height: 72)
    private static let ringAnchor = UnitPoint(x: 0.5, y: 11 / 72)

    var body: some View {
        GeometryReader { geo in
            ZStack {
                Color.black
                CameraPreview(session: camera.session)
                labels(in: geo.size)
                VStack(spacing: 12) {
                    HStack(alignment: .top) {
                        Text(status)
                            .font(.caption).padding(8).background(.black.opacity(0.55)).clipShape(Capsule())
                        Spacer()
                        Button { dismiss() } label: {
                            Image(systemName: "xmark.circle.fill").font(.title).foregroundStyle(.white, .black.opacity(0.5))
                        }
                        .accessibilityLabel("Close Sky view")
                    }
                    Spacer()
                    if cameraDenied { settingsPrompt("Allow the camera to see the sky behind the labels.") }
                    if location.denied { settingsPrompt("Allow location to aim from where you stand.") }
                    if isAway && !nearMeOn { nearMePrompt }
                    if isAway && nearMeOn {
                        Button("Stop showing aircraft around me") { nearMeOn = false }
                            .font(.caption).padding(8).background(.black.opacity(0.6)).clipShape(Capsule())
                    }
                }
                .padding(.horizontal).padding(.top, 56).padding(.bottom, 40)
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

    private var status: String {
        if !motion.available { return "This phone can't tell which way it's pointing." }
        if location.coordinate == nil { return "Aimed from the radar." }
        if isAway && nearMeOn { return "Aircraft around you, from adsb.lol." }
        return "Point the phone at the sky."
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

    /// Each aircraft's label where it is on screen, or nothing when it's
    /// behind the phone or off the edges.
    private func labels(in size: CGSize) -> some View {
        let from = location.coordinate ?? viewModel.home
        let placed: [(PlaneState, CGPoint, Double)] = {
            guard let from, let m = motion.deviceFromWorld else { return [] }
            // Portrait, aspect-fill: the screen's height spans the camera's
            // full wide field of view (its long side).
            let f = (size.height / 2) / tan(camera.fieldOfView * .pi / 360)
            return shown.compactMap { p in
                guard let lat = p.lat, let lon = p.lon else { return nil }
                let br = Geo.haversineBearingRange(lat1: from.lat, lon1: from.lon, lat2: lat, lon2: lon)
                let upM = (p.alt.feetValue ?? 0) * 0.3048
                let el = atan2(upM, max(br.range * 1852, 1))
                let b = br.bearing * .pi / 180
                // world: x north, y west, z up (CoreMotion's xTrueNorthZVertical)
                let w = SIMD3(cos(el) * cos(b), -cos(el) * sin(b), sin(el))
                let d = m * w   // device: x right, y up the screen, z out of the screen
                guard d.z < -0.05 else { return nil }   // the back camera looks along -z
                let pt = CGPoint(x: size.width / 2 + CGFloat(d.x / -d.z) * f,
                                 y: size.height / 2 - CGFloat(d.y / -d.z) * f)
                guard pt.x > -60, pt.x < size.width + 60, pt.y > -60, pt.y < size.height + 60 else { return nil }
                return (p, pt, br.range)
            }
        }()
        return ZStack {
            ForEach(placed, id: \.0.hex) { p, pt, range in
                Button { selected = p.hex } label: {
                    // The ring sits on the aircraft; the text hangs below it,
                    // and the pair turns about the ring to stay upright
                    // however the phone is held (the app itself is portrait).
                    ZStack(alignment: .top) {
                        Circle().stroke(PlaneState.altColor(p.alt), lineWidth: 2).frame(width: 22, height: 22)
                        VStack(spacing: 1) {
                            Text(p.cs).font(.system(size: 14, weight: .bold, design: .monospaced))
                            Text("\(PlaneState.altLabel(p.alt)) · \(String(format: "%.1f", range)) nm")
                                .font(.system(size: 11, design: .monospaced))
                        }
                        .fixedSize()
                        .padding(.horizontal, 6).padding(.vertical, 3)
                        .background(.black.opacity(0.4)).clipShape(RoundedRectangle(cornerRadius: 6))
                        .padding(.top, 26)
                    }
                    .foregroundColor(PlaneState.altColor(p.alt))
                    .frame(width: Self.labelSize.width, height: Self.labelSize.height, alignment: .top)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .opacity(p.isNetwork ? 0.65 : 1)
                .rotationEffect(motion.upright, anchor: Self.ringAnchor)
                // put the ring's centre, not the frame's, on the aircraft
                .offset(y: Self.labelSize.height / 2 - 11)
                .position(pt)
                .accessibilityLabel("\(p.cs), \(PlaneState.altLabel(p.alt)), \(String(format: "%.1f", range)) nautical miles")
            }
        }
    }
}

private struct SkySelection: Identifiable { let id: String }

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
