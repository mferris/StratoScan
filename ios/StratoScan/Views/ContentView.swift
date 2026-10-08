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
    @EnvironmentObject private var setup: RadarSetup
    @Environment(\.horizontalSizeClass) private var sizeClass
    /// iPad (#39): a full-screen radar with no controls, the screen kept awake.
    @AppStorage("stratoscan.wallMode") private var wallMode = false
    /// The colour theme (#43): Daylight unless chosen otherwise.
    @AppStorage(Palette.storageKey) private var themeID = Palette.daylight.id
    private var pal: Palette { Palette.named(themeID) }
    /// Weather on the map (#42): as the radar's defaults, storms on, lightning off.
    @AppStorage("stratoscan.storms") private var showStorms = true
    @AppStorage("stratoscan.lightning") private var showLightning = false

    /// An iPad, or any window wide enough to be treated like one.
    private var isPad: Bool { sizeClass == .regular }
    /// Text and controls, scaled up on the bigger screen.
    private var ui: CGFloat { isPad ? 1.4 : 1 }

    var body: some View {
        GeometryReader { geo in
            // The whole screen, edges and all: the map under everything, the
            // radar's ring a line on it, the aircraft, trails and labels over
            // it (roadmap 2.22). The iPad's details panel sits over the right
            // of the picture (#39).
            let panelW = min(420, geo.size.width * 0.42)
            let full = CGSize(width: geo.size.width + geo.safeAreaInsets.leading + geo.safeAreaInsets.trailing,
                              height: geo.size.height + geo.safeAreaInsets.top + geo.safeAreaInsets.bottom)
            let radius = Double(RadarView.radius(full))

            ZStack {
                pal.bg.ignoresSafeArea()

                MapBackgroundView(
                    center: viewModel.viewCentre,
                    zoom: Geo.zoomForRange(rangeNm: viewModel.rangeNm, lat: viewModel.viewCentre.lat, pixels: radius),
                    runwayGeoJSON: viewModel.runwayGeoJSON,
                    palette: pal,
                    showStorms: showStorms,
                    showLightning: showLightning
                )
                // The kiosk's --map-filter for the chosen theme (Palette).
                .mapFilter(pal.mapFilter)
                .ignoresSafeArea()

                RadarView(viewModel: viewModel, uiScale: ui)
                    .ignoresSafeArea()

                VStack {
                    hud
                    Spacer()
                    footer(geo)
                }
                .padding(.top, 8)

                if wallMode && nightNow {
                    // After dark the wall radar dims, as the kiosk does (its
                    // --night-dim, 55%): an overlay, not the iPad's brightness,
                    // which would stay changed after leaving the app.
                    Color.black.opacity(0.55).ignoresSafeArea().allowsHitTesting(false)
                }
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
                        // centres the view on it, and back on the radar. Away
                        // from the radar it is the switch between the sky
                        // around you and your radar's (roadmap 2.21).
                        Button {
                            location.start()
                            viewModel.centreOnMe.toggle()
                            if !viewModel.centreOnMe { viewModel.panCentre = nil }
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
                        .frame(width: panelW)
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
        .onAppear {
            syncHasRadar()
            viewModel.start()
            if viewModel.wantsLocation { location.start() }
        }
        .onChange(of: pairing.radars.count) { _, _ in syncHasRadar() }
        // The network's view of the sky around you needs the phone's location.
        .onChange(of: viewModel.wantsLocation) { _, wants in if wants { location.start() } }
        .onChange(of: viewModel.centreOnMe) { _, on in if on { location.start() } }
        // back from the background: say "connecting" until the radar answers
        .onChange(of: scenePhase) { _, phase in if phase == .active { viewModel.resume() } }
        .onReceive(location.$coordinate) { viewModel.me = $0 }
        // An alert was tapped (#61): its aircraft's details, and the view on it.
        .onReceive(PushManager.shared.$openHex) { hex in
            guard let hex else { return }
            PushManager.shared.openHex = nil
            showSky = false; showLogbook = false; showSettings = false
            if viewModel.plane(hex) != nil {
                viewModel.followHex = hex
                if viewModel.rangeNm > 5 { viewModel.setRange(5) }
            }
            viewModel.selectedHex = hex
        }
        .onDisappear { viewModel.stop() }
        .animation(.easeOut(duration: 0.2), value: viewModel.selectedHex)
        .onAppear { UIApplication.shared.isIdleTimerDisabled = wallMode }
        .onChange(of: wallMode) { _, on in UIApplication.shared.isIdleTimerDisabled = on }
        .task(id: wallMode) {
            while wallMode && !Task.isCancelled {
                checkNight()
                try? await Task.sleep(for: .seconds(60))
            }
        }
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
            LogbookView(noRadar: !viewModel.hasRadar).preferredColorScheme(pal.dark ? .dark : .light)
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
                .environmentObject(setup)
        }
        .confirmationDialog("Pair with this radar?", isPresented: Binding(
            get: { pairing.pendingLink != nil },
            set: { if !$0 { pairing.pendingLink = nil } }), titleVisibility: .visible) {
            Button("Pair") { pairing.confirmPending() }
            Button("Cancel", role: .cancel) { pairing.pendingLink = nil }
        } message: {
            Text("Only pair with a code shown on your own radar's screen. This phone will get that radar's alerts."
                 + (pairing.pendingLink?.name.map { "\nIt calls itself “\($0)”." } ?? "")
                 + (pairing.pendingLink?.host.map { "\nRadar at \($0)" } ?? ""))
        }
        // A new radar's setup link, opened from outside the app (2.18): it
        // joins a WiFi network and sends it the home WiFi password, so it
        // needs a yes first, the same as pairing.
        .confirmationDialog("Set up a new radar?", isPresented: Binding(
            get: { setup.pendingLink != nil },
            set: { if !$0 { setup.pendingLink = nil } }), titleVisibility: .visible) {
            Button("Set up") { setup.confirmPending() }
            Button("Cancel", role: .cancel) { setup.pendingLink = nil }
        } message: {
            Text("Only from the code on a radar's own first screen. "
                 + (setup.pendingLink?.ssid.map { "Your phone will join its setup network “\($0)” and send it your home WiFi password. " }
                    ?? (setup.pendingLink?.lan.map { "It will set up the radar at \($0) on this network. " } ?? "")))
        }
        .alert(pairing.message ?? "", isPresented: Binding(
            get: { pairing.message != nil && !showSettings },
            set: { if !$0 { pairing.message = nil } })) {
            Button("OK", role: .cancel) { pairing.message = nil }
        }
    }

    /// A radar is paired, or one was typed in by address.
    private func syncHasRadar() {
        viewModel.hasRadar = !pairing.radars.isEmpty || APIConfig.baseURL != APIConfig.defaultBaseURL
    }

    /// Between sunset and sunrise at the radar (Sun), checked once a minute
    /// while in wall mode.
    @State private var nightNow = false
    private func checkNight() {
        guard let h = viewModel.home else { nightNow = false; return }
        nightNow = Sun.isNight(lat: h.lat, lon: h.lon)
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
                    Label(viewModel.awayFromRadar && viewModel.hasRadar ? "BACK TO THE RADAR" : "RESET VIEW",
                          systemImage: "arrow.counterclockwise")
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
                .multilineTextAlignment(.center)
            Text(countText)
                .font(.system(size: 15 * ui, design: .monospaced))
                .tracking(1)
                .foregroundColor(pal.text)
        }
        .padding(.horizontal, 12)
    }

    private var countText: String {
        if viewModel.beyondRadar || !viewModel.hasRadar {
            let n = viewModel.networkCount + viewModel.allPlanes.filter { !$0.fromView && viewModel.distanceFromCentre($0) <= viewModel.rangeNm }.count
            return "\(n) AIRCRAFT"
        }
        return viewModel.notHeardCount > 0
            ? "\(viewModel.aircraftCount) AIRCRAFT · \(viewModel.notHeardCount) NOT HEARD"
            : "\(viewModel.aircraftCount) AIRCRAFT"
    }

    private var rangeText: String {
        viewModel.rangeNm >= 5 ? String(format: "%.0fNM", viewModel.rangeNm) : String(format: "%.1fNM", viewModel.rangeNm)
    }

    /// Where the view is, and what it is looking at.
    private var locationText: String {
        if let h = viewModel.followHex, let p = viewModel.plane(h) {
            return "FOLLOWING \(p.cs) · \(rangeText)"
        }
        if location.denied && viewModel.centreOnMe { return "LOCATION IS OFF FOR STRATOSCAN IN SETTINGS" }
        let points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        func fromRadar(_ br: Geo.BearingRange, _ who: String) -> String {
            let dir = points[Int((br.bearing / 45).rounded()) % 8]
            return br.range < 10 ? String(format: "%@ · %.1f NM %@ OF YOUR RADAR", who, br.range, dir)
                                 : String(format: "%@ · %.0f NM %@ OF YOUR RADAR", who, br.range, dir)
        }
        if viewModel.centreOnMe, viewModel.me != nil {
            if let br = viewModel.meFromRadar, viewModel.hasRadar { return fromRadar(br, "YOU") + " · " + rangeText }
            return "AROUND YOU · " + rangeText
        }
        if viewModel.panCentre != nil, let br = viewModel.viewFromRadar, viewModel.hasRadar, br.range > 1 {
            return fromRadar(br, "LOOKING") + " · " + rangeText
        }
        guard let home = viewModel.home else { return viewModel.hasRadar ? "LOCATING…" : "FINDING YOU…" }
        let ns = home.lat >= 0 ? "N" : "S"
        let ew = home.lon >= 0 ? "E" : "W"
        return String(format: "%.4f°%@ %.4f°%@ · ", abs(home.lat), ns, abs(home.lon), ew) + rangeText
    }

    /// The line at the bottom: where the aircraft are coming from, or what
    /// is needed for there to be any.
    @ViewBuilder
    private func footer(_ geo: GeometryProxy) -> some View {
        let mono = Font.system(size: 10 * ui, weight: .medium, design: .monospaced)
        let pad = geo.size.height * 0.06
        if viewModel.isDemo {
            Text("DEMO · TRAFFIC RECORDED NEAR RDU").font(mono).tracking(2).foregroundColor(pal.textDim).padding(.bottom, pad)
        } else if viewModel.connecting {
            HStack(spacing: 8) {
                ProgressView().controlSize(.small).tint(pal.textDim)
                Text(viewModel.hasRadar ? "CONNECTING TO YOUR RADAR…" : "FINDING AIRCRAFT AROUND YOU…")
                    .font(mono).tracking(2).foregroundColor(pal.textDim)
            }
            .padding(.bottom, pad)
        } else if viewModel.networkOn && (viewModel.beyondRadar || !viewModel.hasRadar || !viewModel.connected) && location.denied && viewModel.centreOnMe {
            // around me needs the phone's location
            VStack(spacing: 8) {
                Text("LOCATION IS OFF FOR STRATOSCAN").font(mono).tracking(2).foregroundColor(pal.bad)
                Button("Turn it on in Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                }
                .font(.system(size: 13 * ui, weight: .medium)).foregroundColor(pal.mid)
            }
            .padding(.bottom, pad)
        } else if viewModel.source == .network {
            // the network's data, and its licence's credit
            let why = !viewModel.hasRadar ? "AROUND YOU" : (!viewModel.connected && !viewModel.beyondRadar ? "YOUR RADAR IS OUT OF REACH" : "BEYOND YOUR RADAR")
            let reach = viewModel.rangeNm * 1.3 > Double(NetworkFeed.maxRadiusNm) ? " · WITHIN 250 NM OF THE MIDDLE" : ""
            Text("\(why) · DATA © ADSB.LOL (ODbL)\(reach)")
                .font(mono).tracking(2).foregroundColor(pal.textDim).multilineTextAlignment(.center)
                .padding(.horizontal, 24).padding(.bottom, pad)
        } else if viewModel.viaAway && !viewModel.isStale {
            Text("AWAY · VIA THE RADAR'S PUBLIC PAGE").font(mono).tracking(2).foregroundColor(pal.textDim).padding(.bottom, pad)
        } else if viewModel.hasRadar && viewModel.beyondRadar && !viewModel.networkOn {
            Text("NO RADAR DATA HERE · THE PUBLIC NETWORK IS OFF IN SETTINGS")
                .font(mono).tracking(2).foregroundColor(pal.textDim).multilineTextAlignment(.center)
                .padding(.horizontal, 24).padding(.bottom, pad)
        } else if viewModel.isStale {
            VStack(spacing: 10) {
                Text(viewModel.hasRadar ? "NO SIGNAL — CHECK RECEIVER" : "NO RADAR").font(mono).tracking(2).foregroundColor(pal.bad)
                if pairing.radars.isEmpty {
                    // No radar (#41): the sky around you, or the demo.
                    VStack(spacing: 10) {
                        Text("No StratoScan radar yet?").font(.system(size: 14 * ui, weight: .semibold)).foregroundColor(pal.text)
                        Button {
                            location.start()
                            viewModel.showAroundMe()
                        } label: {
                            Label("See aircraft around you", systemImage: "location.viewfinder")
                                .font(.system(size: 14 * ui, weight: .semibold))
                                .padding(.horizontal, 16).padding(.vertical, 9)
                                .foregroundColor(pal.mid)
                                .background(pal.mid.opacity(0.14), in: Capsule())
                                .overlay(Capsule().stroke(pal.mid.opacity(0.5), lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                        Text("Live, from the public adsb.lol network. To ask for them, the app sends adsb.lol your location rounded to about 5 km.")
                            .font(.system(size: 11 * ui)).foregroundColor(pal.textDim)
                            .multilineTextAlignment(.center).frame(maxWidth: 300 * ui)
                        Button("Or try the demo") { viewModel.setDemo(true) }
                            .font(.system(size: 13 * ui, weight: .medium))
                            .foregroundColor(pal.mid)
                    }
                }
            }
            .padding(.bottom, pad)
        }
    }
}

private struct SelectedAircraft: Identifiable { let id: String }

#Preview {
    ContentView().environmentObject(PairingStore()).environmentObject(RadarSetup())
}
