import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel = RadarViewModel()
    @StateObject private var location = PhoneLocation()
    @State private var showSky = false
    /// The aircraft Sky view was opened to find, if any.
    @State private var skyFocus: String?
    @State private var showLogbook = false
    @State private var showSettings = false
    @EnvironmentObject private var pairing: PairingStore
    @Environment(\.horizontalSizeClass) private var sizeClass
    /// iPad (#39): a full-screen radar with no controls, the screen kept awake.
    @AppStorage("stratoscan.wallMode") private var wallMode = false
    /// The colour theme (#43): Daylight unless chosen otherwise.
    @AppStorage(Palette.storageKey) private var themeID = Palette.daylight.id
    private var pal: Palette { Palette.named(themeID) }

    /// An iPad, or any window wide enough to be treated like one.
    private var isPad: Bool { sizeClass == .regular }
    /// Text and controls, scaled up on the bigger screen.
    private var ui: CGFloat { isPad ? 1.4 : 1 }

    var body: some View {
        GeometryReader { geo in
            let side = min(geo.size.width, geo.size.height) * 0.94

            ZStack {
                pal.bg.ignoresSafeArea()

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
                        runwayGeoJSON: viewModel.runwayGeoJSON,
                        palette: pal
                    )
                    // The kiosk's --map-filter for the chosen theme (Palette).
                    .mapFilter(pal.mapFilter)
                    .frame(width: side, height: side)
                    .clipShape(Circle())
                    .position(x: geo.size.width / 2, y: geo.size.height / 2)
                }
                Circle()
                    .stroke(pal.ringBright.opacity(0.5), lineWidth: 2)
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
                            .foregroundColor(pal.textDim)
                            .padding(.bottom, geo.size.height * 0.08)
                    } else if viewModel.isDemo {
                        Text("DEMO · TRAFFIC RECORDED NEAR RDU")
                            .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                            .tracking(2)
                            .foregroundColor(pal.textDim)
                            .padding(.bottom, geo.size.height * 0.08)
                    } else if viewModel.connecting {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small).tint(pal.textDim)
                            Text("CONNECTING TO YOUR RADAR…")
                                .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(pal.textDim)
                        }
                        .padding(.bottom, geo.size.height * 0.08)
                    } else if viewModel.isStale {
                        VStack(spacing: 10) {
                            Text("NO SIGNAL — CHECK RECEIVER")
                                .font(.system(size: 10 * ui, weight: .medium, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(pal.bad)
                            if pairing.radars.isEmpty {
                                Button("No radar yet? Try the demo") { viewModel.setDemo(true) }
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(pal.mid)
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
                                    .foregroundColor(pal.textDim.opacity(0.5))
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
                                .foregroundColor(pal.textDim)
                                .padding(10)
                        }
                        .accessibilityLabel("Labels: \(viewModel.labelMode.rawValue)")
                        // Centre on me, as in Apple Maps: the "YOU" dot shows
                        // whenever location is on (this, the compass, Sky view
                        // or "Approaching me" can turn it on); this button
                        // centres the view on it, and back on the radar.
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
                        Button { skyFocus = nil; showSky = true } label: {
                            Image(systemName: "binoculars")
                                .foregroundColor(pal.textDim)
                                .padding(10)
                        }
                        .accessibilityLabel("Sky view")
                        Spacer()
                        // The logbook: what this radar has seen (roadmap 2.5).
                        Button { showLogbook = true } label: {
                            Image(systemName: "book.closed")
                                .foregroundColor(pal.textDim)
                                .padding(10)
                        }
                        .accessibilityLabel("Logbook")
                        if isPad {
                            // Wall mode: an iPad as a second radar screen.
                            Button { wallMode = true } label: {
                                Image(systemName: "arrow.up.left.and.arrow.down.right")
                                    .foregroundColor(pal.textDim)
                                    .padding(10)
                            }
                            .accessibilityLabel("Wall mode")
                        }
                        Button {
                            showSettings = true
                        } label: {
                            Image(systemName: "gearshape")
                                .foregroundColor(pal.textDim)
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
                            AircraftDetailView(viewModel: viewModel, location: location, hex: hex,
                                               findInSky: { findInSky(hex) })
                        }
                        .frame(width: min(420, geo.size.width * 0.42))
                        .background(Color(.systemBackground).opacity(0.96))
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .padding(.top, 64)          // below the controls, which stay usable
                        .padding([.horizontal, .bottom], 16)
                        .environment(\.colorScheme, pal.dark ? .dark : .light)
                    }
                    .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
        }
        .background(pal.bg)
        // sheets, settings and the details panel follow the theme
        .preferredColorScheme(pal.dark ? .dark : .light)
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
            AircraftDetailView(viewModel: viewModel, location: location, hex: sel.id,
                               findInSky: { findInSky(sel.id) })
                .presentationDetents([.medium, .large])
                .preferredColorScheme(pal.dark ? .dark : .light)
        }
        .sheet(isPresented: $showLogbook) {
            LogbookView().preferredColorScheme(pal.dark ? .dark : .light)
        }
        .fullScreenCover(isPresented: $showSky) {
            SkyView(viewModel: viewModel, location: location, focus: skyFocus, backToRadar: { hex in
                showSky = false
                // after the cover has gone, so the details can open over the radar
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { viewModel.selectedHex = hex }
            })
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

    /// From an aircraft's details to Sky view, looking for it.
    private func findInSky(_ hex: String) {
        skyFocus = hex
        viewModel.selectedHex = nil
        // after the details sheet has gone: one presentation at a time
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { showSky = true }
    }

    private var hud: some View {
        VStack(spacing: 2) {
            StratoScanLogo(height: 32 * ui, onLight: !pal.dark)
                .opacity(0.9)
                .padding(.bottom, 6)
            if viewModel.isZoomed {
                // A real button: it was small text, easy to miss and to miss tapping.
                Button { viewModel.resetView() } label: {
                    Label("RESET VIEW", systemImage: "arrow.counterclockwise")
                        .font(.system(size: 13 * ui, weight: .semibold, design: .monospaced))
                        .tracking(1)
                        .padding(.horizontal, 16 * ui)
                        .padding(.vertical, 9 * ui)
                        .foregroundColor(pal.mid)
                        .background(pal.mid.opacity(0.16), in: Capsule())
                        .overlay(Capsule().stroke(pal.mid.opacity(0.55), lineWidth: 1))
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .padding(.bottom, 8)
            }
            Text(locationText)
                .font(.system(size: 10 * ui, design: .monospaced))
                .tracking(1.5)
                .foregroundColor(pal.textDim)
                .textCase(.uppercase)
            Text(viewModel.notHeardCount > 0
                 ? "\(viewModel.aircraftCount) AIRCRAFT · \(viewModel.notHeardCount) NOT HEARD"
                 : "\(viewModel.aircraftCount) AIRCRAFT")
                .font(.system(size: 15 * ui, design: .monospaced))
                .tracking(1)
                .foregroundColor(pal.text)
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
