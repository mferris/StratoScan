import ARKit
import SceneKit
import SwiftUI

/// Sky view (roadmap 2.5): hold the phone up and see each aircraft's label
/// over the camera image, where the aircraft actually is.
///
/// ARKit is set to align its world with gravity and compass heading
/// (x = east, y = up, z = south), so an aircraft's direction from here -- its
/// bearing and elevation, from its position and altitude -- becomes a point
/// in that world. Labels sit on a sphere 60 m out along that direction rather
/// than at true range (kilometres away, far too small to read), and always
/// face the camera. Positions come from the radar's feed, aimed from the
/// phone's location when allowed, the radar's otherwise. Nothing leaves the
/// phone; the camera image is never recorded or sent.
struct SkyView: View {
    @ObservedObject var viewModel: RadarViewModel
    @ObservedObject var location: PhoneLocation
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack(alignment: .top) {
            if ARWorldTrackingConfiguration.isSupported {
                SkyARView(viewModel: viewModel, location: location).ignoresSafeArea()
            } else {
                Text("Sky view needs a phone with ARKit.").padding(.top, 120)
            }
            HStack {
                Text(location.coordinate == nil ? "Aimed from the radar. Allow location to aim from where you stand."
                                                : "Point the phone at the sky.")
                    .font(.caption).padding(8).background(.black.opacity(0.5)).clipShape(Capsule())
                Spacer()
                Button { dismiss() } label: {
                    Image(systemName: "xmark.circle.fill").font(.title)
                }
            }
            .padding()
        }
        .onAppear { location.start() }
    }
}

private struct SkyARView: UIViewRepresentable {
    let viewModel: RadarViewModel
    let location: PhoneLocation

    func makeCoordinator() -> Coordinator { Coordinator(viewModel: viewModel, location: location) }

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView()
        view.scene = SCNScene()
        view.automaticallyUpdatesLighting = false
        let config = ARWorldTrackingConfiguration()
        config.worldAlignment = .gravityAndHeading
        view.session.run(config)
        context.coordinator.view = view
        context.coordinator.startUpdating()
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}

    static func dismantleUIView(_ uiView: ARSCNView, coordinator: Coordinator) {
        coordinator.timer?.invalidate()
        uiView.session.pause()
    }

    @MainActor
    final class Coordinator {
        let viewModel: RadarViewModel
        let location: PhoneLocation
        weak var view: ARSCNView?
        var timer: Timer?
        private var nodes: [String: SCNNode] = [:]
        private let radius: Float = 60

        init(viewModel: RadarViewModel, location: PhoneLocation) {
            self.viewModel = viewModel
            self.location = location
        }

        func startUpdating() {
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
                Task { @MainActor in self?.update() }
            }
            update()
        }

        private func update() {
            guard let root = view?.scene.rootNode, let from = location.coordinate ?? viewModel.home else { return }
            var seen = Set<String>()
            for p in viewModel.planes.values where p.range <= viewModel.ringNm {
                guard let lat = p.lat, let lon = p.lon else { continue }
                let br = Geo.haversineBearingRange(lat1: from.lat, lon1: from.lon, lat2: lat, lon2: lon)
                let groundM = br.range * 1852
                let upM = (p.alt.feetValue ?? 0) * 0.3048
                let elev = atan2(upM, max(groundM, 1))
                let b = br.bearing * .pi / 180
                // gravityAndHeading: x east, y up, z south
                let dir = SCNVector3(Float(cos(elev) * sin(b)), Float(sin(elev)), Float(-cos(elev) * cos(b)))
                let node = nodes[p.hex] ?? makeLabel()
                if nodes[p.hex] == nil { nodes[p.hex] = node; root.addChildNode(node) }
                node.position = SCNVector3(dir.x * radius, dir.y * radius, dir.z * radius)
                (node.geometry as? SCNText)?.string =
                    "\(p.cs)\n\(PlaneState.altLabel(p.alt)) · \(String(format: "%.1f", br.range)) nm"
                node.opacity = p.isNetwork ? 0.55 : 1
                seen.insert(p.hex)
            }
            for (hex, node) in nodes where !seen.contains(hex) {
                node.removeFromParentNode()
                nodes[hex] = nil
            }
        }

        private func makeLabel() -> SCNNode {
            let text = SCNText(string: "", extrusionDepth: 0)
            text.font = UIFont.monospacedSystemFont(ofSize: 10, weight: .bold)
            text.flatness = 0.2
            text.firstMaterial?.diffuse.contents = UIColor(red: 1, green: 0.69, blue: 0.13, alpha: 1)
            text.firstMaterial?.isDoubleSided = true
            let node = SCNNode(geometry: text)
            node.scale = SCNVector3(0.15, 0.15, 0.15)
            node.constraints = [SCNBillboardConstraint()]   // always faces the camera
            return node
        }
    }
}
