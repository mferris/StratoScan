import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel = RadarViewModel()
    @StateObject private var location = PhoneLocation()
    @State private var showSky = false
    @State private var showLogbook = false
    @State private var showSettings = false
    @EnvironmentObject private var pairing: PairingStore
    @Environment(\.horizontalSizeClass) private var sizeClass
    /// iPad (#39): a full-screen radar with no controls, the screen kept awake.
    @AppStorage("stratoscan.wallMode") private var wallMode = false

    /// An iPad, or any window wide enough to be treated like one.
    private var isPad: Bool { sizeClass == .regular }
    /// Text and controls, scaled up on the bigger screen.
    private var ui: CGFloat { isPad ? 1.4 : 1 }

    var body: some View {
        GeometryReader { geo in
            let side = min(geo.size.width, geo.size.height) * 0.94

            ZStack {
                Color.black.ignoresSafeArea()

                // The map is clipped to a circle for the kiosk-bezel look.
                // RadarView's rings/sweep/blips are already bounded within
                // that same circle by construction (their polar math never
                // exceeds radius r), so they need no explicit clip — and
                // critically, its *labels* must NOT be clipped: they need
                // the full rectangular frame below to roam in, exactly like
                // the web version's separate, unclipped #tags layer.
                if let home = viewModel.home {
                    MapBackgroundView(
                        center: mapCentre(home),
                        zoom: Geo.zoomForRange(rangeNm: viewModel.rangeNm, lat: home.lat, pixels: side * 0.44),
                        runwayGeoJSON: viewModel.runwayGeoJSON
                    )
                    // Web version darkens #mapbg via CSS `filter: brightness(0.36)
                    // saturate(1.5)`. SwiftUI's own .brightness() is additive, not
                    // multiplicative, so it doesn't reproduce that look — .colorMultiply
                    // against a 36%-white gray is the actual multiplicative equivalent
                    // (mathematically identical to what CSS brightness(0.36) computes).
                    .saturation(1.5)
                    .colorMultiply(Color(white: 0.36))
                    .frame(width: side, height: side)
                    .clipShape(Circle())
                    .position(x: geo.size.width / 2, y: geo.size.height / 2)
                }
                Circle()
                    .stroke(Color(hex: "#14201f"), lineWidth: 2)
                    .frame(width: side, height: side)
                    .position(x: geo.size.width / 2, y: geo.size.height / 2)
                    .shadow(color: .black.opacity(0.6), radius: 20)

                RadarView(viewModel: viewModel, diameter: side, uiScale: ui)
                    .frame(width: geo.size.width, height: geo.size.height)

                VStack {
                    hud
                    Spacer()
                    if viewModel.viaAway && !viewModel.isStale {
                        Text("AWAY · VIA THE RADAR'S PUBLIC PAGE")
                            .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                            .tracking(2)
                            .foregroundColor(Color(hex: "#5b7278"))
                            .padding(.bottom, geo.size.height * 0.08)
                    } else if viewModel.isDemo {
                        Text("DEMO · TRAFFIC RECORDED NEAR RDU")
                            .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                            .tracking(2)
                            .foregroundColor(Color(hex: "#5b7278"))
                            .padding(.bottom, geo.size.height * 0.08)
                    } else if viewModel.connecting {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small).tint(Color(hex: "#5b7278"))
                            Text("CONNECTING TO YOUR RADAR…")
                                .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(Color(hex: "#5b7278"))
                        }
                        .padding(.bottom, geo.size.height * 0.08)
                    } else if viewModel.isStale {
                        VStack(spacing: 10) {
                            Text("NO SIGNAL — CHECK RECEIVER")
                                .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(Color(hex: "#ff5d5d"))
                            if pairing.radars.isEmpty {
                                Button("No radar yet? Try the demo") { viewModel.setDemo(true) }
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Color(hex: "#4fd6c8"))
                            }
                        }
                        .padding(.bottom, geo.size.height * 0.08)
                    }
                }
                .padding(.top, geo.safeAreaInsets.top + 8)

                if wallMode {
                    // Wall mode: only a faint way out, top right.
                    VStack {
                        HStack {
                            Spacer()
                            Button { wallMode = false } label: {
                                Image(systemName: "arrow.down.right.and.arrow.up.left")
                                    .foregroundColor(Color(hex: "#5b7278").opacity(0.5))
                                    .padding(14)
                            }
                            .accessibilityLabel("Leave wall mode")
                        }
                        Spacer()
                    }
                } else {
                VStack {
                    HStack {
                        // Labels: compact → full → off.
                        Button {
                            viewModel.labelMode = viewModel.labelMode.next
                        } label: {
                            Image(systemName: viewModel.labelMode.symbol)
                                .foregroundColor(Color(hex: "#5b7278"))
                                .padding(10)
                        }
                        .accessibilityLabel("Labels: \(viewModel.labelMode.rawValue)")
                        // Centre on me: shows this phone on the radar. The
                        // location stays on the phone.
                        Button {
                            location.start()
                            viewModel.centreOnMe.toggle()
                        } label: {
                            Image(systemName: viewModel.centreOnMe ? "location.fill" : "location")
                                .foregroundColor(Color(hex: viewModel.centreOnMe ? "#93c5fd" : "#5b7278"))
                                .padding(10)
                        }
                        .accessibilityLabel(viewModel.centreOnMe ? "Centre on the radar" : "Centre on me")
                        // Sky view: the aircraft over the camera image (roadmap 2.5).
                        Button { showSky = true } label: {
                            Image(systemName: "binoculars")
                                .foregroundColor(Color(hex: "#5b7278"))
                                .padding(10)
                        }
                        .accessibilityLabel("Sky view")
                        Spacer()
                        // The logbook: what this radar has seen (roadmap 2.5).
                        Button { showLogbook = true } label: {
                            Image(systemName: "book.closed")
                                .foregroundColor(Color(hex: "#5b7278"))
                                .padding(10)
                        }
                        .accessibilityLabel("Logbook")
                        if isPad {
                            // Wall mode: an iPad as a second radar screen.
                            Button { wallMode = true } label: {
                                Image(systemName: "arrow.up.left.and.arrow.down.right")
                                    .foregroundColor(Color(hex: "#5b7278"))
                                    .padding(10)
                            }
                            .accessibilityLabel("Wall mode")
                        }
                        Button {
                            showSettings = true
                        } label: {
                            Image(systemName: "gearshape")
                                .foregroundColor(Color(hex: "#5b7278"))
                                .padding(10)
                        }
                    }
                    .font(.system(size: 17 * ui))
                    Spacer()
                }
                }

                // iPad: an aircraft's details beside the radar, not over it,
                // so the radar keeps moving next to them (#39).
                if isPad, let hex = viewModel.selectedHex {
                    HStack {
                        Spacer()
                        VStack(spacing: 0) {
                            HStack {
                                Spacer()
                                Button { viewModel.selectedHex = nil } label: {
                                    Image(systemName: "xmark.circle.fill").font(.title2)
                                        .foregroundStyle(.white, .gray.opacity(0.4))
                                }
                                .accessibilityLabel("Close details")
                            }
                            .padding([.top, .horizontal], 12)
                            AircraftDetailView(viewModel: viewModel, location: location, hex: hex)
                        }
                        .frame(width: min(420, geo.size.width * 0.42))
                        .background(Color(white: 0.08).opacity(0.96))
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .padding(.top, 64)          // below the controls, which stay usable
                        .padding([.horizontal, .bottom], 16)
                        .environment(\.colorScheme, .dark)
                    }
                    .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
        }
        .background(Color.black)
        .statusBarHidden(true)
        .onAppear { viewModel.start() }
        // back from the background: say "connecting" until the radar answers
        .onChange(of: scenePhase) { _, phase in if phase == .active { viewModel.resume() } }
        .onReceive(location.$coordinate) { viewModel.me = $0 }
        .onDisappear { viewModel.stop() }
        .animation(.easeOut(duration: 0.2), value: viewModel.selectedHex)
        .onAppear { UIApplication.shared.isIdleTimerDisabled = wallMode }
        .onChange(of: wallMode) { _, on in UIApplication.shared.isIdleTimerDisabled = on }
        .sheet(item: Binding(
            // the iPad shows details in its side panel instead
            get: { isPad ? nil : viewModel.selectedHex.map(SelectedAircraft.init) },
            set: { viewModel.selectedHex = $0?.id })) { sel in
            AircraftDetailView(viewModel: viewModel, location: location, hex: sel.id)
                .presentationDetents([.medium, .large])
                .preferredColorScheme(.dark)
        }
        .sheet(isPresented: $showLogbook) {
            LogbookView().preferredColorScheme(.dark)
        }
        .fullScreenCover(isPresented: $showSky) {
            SkyView(viewModel: viewModel, location: location)
        }
        .sheet(isPresented: $showSettings) {
            SettingsView(viewModel: viewModel).environmentObject(pairing).environmentObject(PushManager.shared)
        }
        .confirmationDialog("Pair with this radar?", isPresented: Binding(
            get: { pairing.pendingLink != nil },
            set: { if !$0 { pairing.pendingLink = nil } }), titleVisibility: .visible) {
            Button("Pair") { pairing.confirmPending() }
            Button("Cancel", role: .cancel) { pairing.pendingLink = nil }
        } message: {
            Text("Only pair with a code shown on your own radar's screen. This phone will get that radar's alerts."
                 + (pairing.pendingLink?.host.map { "\nRadar at \($0)" } ?? ""))
        }
        .alert(pairing.message ?? "", isPresented: Binding(
            get: { pairing.message != nil && !showSettings },
            set: { if !$0 { pairing.message = nil } })) {
            Button("OK", role: .cancel) { pairing.message = nil }
        }
    }

    private var hud: some View {
        VStack(spacing: 2) {
            StratoScanLogo(height: 32 * ui)
                .opacity(0.9)
                .padding(.bottom, 6)
            if viewModel.isZoomed {
                Button("RESET VIEW") { viewModel.resetView() }
                    .font(.system(size: 10 * ui, weight: .semibold, design: .monospaced))
                    .tracking(1.5)
                    .padding(.bottom, 4)
            }
            Text(locationText)
                .font(.system(size: 10 * ui, design: .monospaced))
                .tracking(1.5)
                .foregroundColor(Color(hex: "#5b7278"))
                .textCase(.uppercase)
            Text(viewModel.notHeardCount > 0
                 ? "\(viewModel.aircraftCount) AIRCRAFT · \(viewModel.notHeardCount) NOT HEARD"
                 : "\(viewModel.aircraftCount) AIRCRAFT")
                .font(.system(size: 15 * ui, design: .monospaced))
                .tracking(1)
                .foregroundColor(Color(hex: "#cfe8ea"))
        }
    }

    private var locationText: String {
        guard let home = viewModel.home else { return "LOCATING…" }
        let ns = home.lat >= 0 ? "N" : "S"
        let ew = home.lon >= 0 ? "E" : "W"
        let range = viewModel.rangeNm >= 5 ? String(format: "%.0fNM", viewModel.rangeNm)
                                           : String(format: "%.1fNM", viewModel.rangeNm)
        if let h = viewModel.followHex, let p = viewModel.planes[h] {
            return "FOLLOWING \(p.cs) · \(range)"
        }
        if location.denied && viewModel.centreOnMe { return "LOCATION IS OFF FOR STRATOSCAN IN SETTINGS" }
        if viewModel.centreOnMe, let m = viewModel.meOffset {
            let d = hypot(m.east, m.north)
            let points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
            let bearing = (atan2(m.east, m.north) * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)
            let dir = points[Int((bearing / 45).rounded()) % 8]
            return String(format: "YOU · %.1f NM %@ OF THE RADAR · ", d, dir) + range
        }
        return String(format: "%.4f°%@ %.4f°%@ · ", abs(home.lat), ns, abs(home.lon), ew) + range
    }

    /// The map follows the view: the radar, a followed aircraft, the phone,
    /// or wherever the owner has pinched or dragged to.
    private func mapCentre(_ home: Coordinate) -> Coordinate {
        if let h = viewModel.followHex, let p = viewModel.planes[h], let lat = p.lat, let lon = p.lon {
            return Coordinate(lat: lat, lon: lon)
        }
        if viewModel.centreOnMe, let me = viewModel.me { return me }
        // nm to degrees: flat is plenty within the 20 nm ring
        let p = viewModel.pan
        return Coordinate(lat: home.lat + p.north / 60,
                          lon: home.lon + p.east / (60 * cos(home.lat * .pi / 180)))
    }
}

private struct SelectedAircraft: Identifiable { let id: String }

#Preview {
    ContentView().environmentObject(PairingStore())
}
