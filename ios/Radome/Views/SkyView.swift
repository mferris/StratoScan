import AVFoundation
import CoreMotion
import SwiftUI

/// Sky view (roadmap 2.5): hold the phone up and see each aircraft's label
/// over the camera picture, where the aircraft actually is.
///
/// The camera is only a picture here; where the phone points comes from its
/// motion sensors (gravity plus compass, CMDeviceMotion), and each aircraft's
/// bearing and elevation -- from its position and altitude -- is projected
/// onto the screen. The first version used ARKit world tracking, which never
/// started on a real phone (no picture, labels frozen), and needs visual
/// features that a blank sky doesn't have anyway. Positions are aimed from the
/// phone's location when allowed, the radar's otherwise. Nothing leaves the
/// phone; the camera picture is never recorded or sent.
struct SkyView: View {
    @ObservedObject var viewModel: RadarViewModel
    @ObservedObject var location: PhoneLocation
    @StateObject private var motion = SkyMotion()
    @StateObject private var camera = SkyCamera()
    @State private var cameraDenied = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        GeometryReader { geo in
            ZStack {
                Color.black
                CameraPreview(session: camera.session)
                if cameraDenied {
                    Text("Allow the camera in Settings › StratoScan to see the sky behind the labels.")
                        .font(.caption).foregroundColor(.secondary).multilineTextAlignment(.center).padding(40)
                }
                labels(in: geo.size)
                VStack {
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
                }
                .padding()
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
        }
    }

    private var status: String {
        if !motion.available { return "This phone can't tell which way it's pointing." }
        if location.coordinate == nil { return "Aimed from the radar. Allow location to aim from where you stand." }
        return "Point the phone at the sky."
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
            return viewModel.planes.values.compactMap { p in
                guard p.range <= viewModel.ringNm, let lat = p.lat, let lon = p.lon else { return nil }
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
                guard pt.x > -60, pt.x < size.width + 60, pt.y > -30, pt.y < size.height + 30 else { return nil }
                return (p, pt, br.range)
            }
        }()
        return ZStack {
            ForEach(placed, id: \.0.hex) { p, pt, range in
                VStack(spacing: 2) {
                    Circle().stroke(PlaneState.altColor(p.alt), lineWidth: 2).frame(width: 18, height: 18)
                    Text(p.cs).font(.system(size: 14, weight: .bold, design: .monospaced))
                    Text("\(PlaneState.altLabel(p.alt)) · \(String(format: "%.1f", range)) nm")
                        .font(.system(size: 11, design: .monospaced))
                }
                .foregroundColor(PlaneState.altColor(p.alt))
                .padding(.horizontal, 6).padding(.vertical, 3)
                .background(.black.opacity(0.35)).clipShape(RoundedRectangle(cornerRadius: 6))
                .opacity(p.isNetwork ? 0.6 : 1)
                .position(x: pt.x, y: pt.y + 22)   // the ring sits on the aircraft, the text under it
            }
        }
    }
}

/// Which way the phone points, 30 times a second.
@MainActor
final class SkyMotion: ObservableObject {
    /// Turns a direction in the world (north, west, up) into the phone's own
    /// axes (right, up the screen, out of the screen).
    @Published private(set) var deviceFromWorld: simd_double3x3?
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
