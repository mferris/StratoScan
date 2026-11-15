import SwiftUI
import WidgetKit

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel = RadarViewModel()
    @StateObject private var location = PhoneLocation()
    @State private var showSky = false
    /// The aircraft Sky view was opened to find, if any.
    @State private var skyFocus: String?
    @State private var showLogbook = false
    @State private var showSettings = false
    @State private var showInvite = false
    /// The addresses the radar view last read, to notice when they change.
    @State private var radarRead: String?
    /// The invitation on the radar screen, put away by its owner. What a
    /// radar adds stays in Settings and behind the logbook's button.
    @AppStorage("stratoscan.inviteDismissed") private var inviteDismissed = false
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
    /// Wall mode is for an iPad on a wall, so it goes by the device, not the
    /// window: a large iPhone turned sideways is also "regular" width, and a tap
    /// on the wall-mode button there left the phone with no controls at all
    /// (seen 2026-10-12: only a faint way out, top right, easy to miss).
    private var canWallMode: Bool { UIDevice.current.userInterfaceIdiom == .pad }
    private var inWallMode: Bool { wallMode && canWallMode }
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
            // Read when a sheet closes (#101): see RadarViewModel.detailsInPanel.
            let _ = (viewModel.detailsInPanel = isPad)

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

                // The logo and the lines under it move with the buttons, and
                // fit the room the buttons leave (ClearOfScreenCorners).
                let corners = ClearOfScreenCorners.extra(geo.safeAreaInsets)
                VStack {
                    hud(geo.size.width - corners.leading - corners.trailing)
                    Spacer()
                    if wantsInvite { invitePill }
                    footer(geo)
                }
                .padding(.top, 8)
                .clearOfScreenCorners()

                if inWallMode && nightNow {
                    // After dark the wall radar dims, as the kiosk does (its
                    // --night-dim, 55%): an overlay, not the iPad's brightness,
                    // which would stay changed after leaving the app.
                    Color.black.opacity(0.55).ignoresSafeArea().allowsHitTesting(false)
                }
                if inWallMode {
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
                    .clearOfScreenCorners()
                } else {
                VStack {
                    HStack(spacing: ContentView.barSpacing) {
                        // Labels: compact → full → off.
                        Button {
                            viewModel.labelMode = viewModel.labelMode.next
                        } label: {
                            Image(systemName: viewModel.labelMode.symbol)
                                .topBarIcon(pal)
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
                                .topBarIcon(pal, tint: viewModel.centreOnMe ? Color(hex: "#93c5fd") : nil)
                        }
                        .accessibilityLabel(viewModel.centreOnMe ? "Centre on the radar" : "Centre on me")
                        // Sky view: the aircraft over the camera image (roadmap 2.5).
                        Button { skyFocus = nil; showSky = true } label: {
                            Image(systemName: "binoculars")
                                .topBarIcon(pal)
                        }
                        .accessibilityLabel("Sky view")
                        Spacer()
                        // The logbook: what this radar has seen (roadmap 2.5).
                        Button { showLogbook = true } label: {
                            Image(systemName: "book.closed")
                                .topBarIcon(pal)
                        }
                        .accessibilityLabel("Logbook")
                        if canWallMode {
                            // Wall mode: an iPad as a second radar screen.
                            Button { wallMode = true } label: {
                                Image(systemName: "arrow.up.left.and.arrow.down.right")
                                    .topBarIcon(pal)
                            }
                            .accessibilityLabel("Wall mode")
                        }
                        Button {
                            showSettings = true
                        } label: {
                            Image(systemName: "gearshape")
                                .topBarIcon(pal)
                        }
                    }
                    .font(.system(size: 17 * ui))
                    Spacer()
                }
                .clearOfScreenCorners()
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
                                               findInSky: { findInSky(hex) }, inPanel: true)
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
        .onChange(of: scenePhase) { _, phase in if phase == .active { syncHasRadar(); viewModel.resume() } }
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
        .onAppear {
            if wallMode && !canWallMode { wallMode = false }   // a phone left in wall mode by an older build
            UIApplication.shared.isIdleTimerDisabled = inWallMode
        }
        .onChange(of: wallMode) { _, on in UIApplication.shared.isIdleTimerDisabled = on && canWallMode }
        .task(id: wallMode) {
            while inWallMode && !Task.isCancelled {
                checkNight()
                try? await Task.sleep(for: .seconds(60))
            }
        }
        .sheet(item: Binding(
            // the iPad shows details in its side panel instead
            // (and not under Sky view: folding there waits till it closes)
            get: { isPad || showSky ? nil : viewModel.selectedHex.map(SelectedAircraft.init) },
            set: { sel in
                // Closed because the iPhone Duo unfolded: the same aircraft
                // stays selected and its details move to the side panel (#101).
                if sel == nil && (viewModel.detailsInPanel || showSky) { return }
                viewModel.selectedHex = sel?.id
            })) { sel in
            AircraftDetailView(viewModel: viewModel, location: location, hex: sel.id,
                               findInSky: { findInSky(sel.id) }, inPanel: false)
                .presentationDetents([.medium, .large])
                .preferredColorScheme(pal.dark ? .dark : .light)
        }
        .sheet(isPresented: $showLogbook) {
            // the demo has a logbook of its own, radar or no radar
            LogbookView(noRadar: !viewModel.hasRadar && !viewModel.isDemo, tryDemo: { viewModel.setDemo(true) })
                .preferredColorScheme(pal.dark ? .dark : .light)
        }
        .fullScreenCover(isPresented: $showSky) {
            SkyView(viewModel: viewModel, location: location, focus: skyFocus, backToRadar: { hex in
                showSky = false
                // after the cover has gone, so the details can open over the radar
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { viewModel.selectedHex = hex }
            })
        }
        .sheet(isPresented: $showInvite) {
            RadarInviteSheet(viewModel: viewModel, pair: {
                showInvite = false
                // after this sheet has gone: one presentation at a time
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { showSettings = true }
            })
            .preferredColorScheme(pal.dark ? .dark : .light)
        }
        // an address typed or cleared in Settings is a radar gained or lost
        .sheet(isPresented: $showSettings, onDismiss: syncHasRadar) {
            SettingsView(viewModel: viewModel).environmentObject(pairing).environmentObject(PushManager.shared)
                .environmentObject(setup)
        }
        .confirmationDialog("Pair with this radar?", isPresented: Binding(
            get: { pairing.pendingLink != nil },
            set: { if !$0 { pairing.pendingLink = nil } }), titleVisibility: .visible) {
            Button("Pair") { pairing.confirmPending() }
            Button("Cancel", role: .cancel) { pairing.pendingLink = nil }
        } message: {
            Text(pairingMessage)
        }
        // A new radar's setup link, opened from outside the app (2.18): it
        // joins a WiFi network, sends it the home WiFi password and pairs
        // this phone with the radar, so it needs a yes first, the same as
        // pairing. Only a link naming a certificate gets this far
        // (RadarSetup.handle, 2026-11-15). The certificate keeps the setup
        // private to whatever holds it; it doesn't say whose radar that is.
        .confirmationDialog("Set up a new radar?", isPresented: Binding(
            get: { setup.pendingLink != nil },
            set: { if !$0 { setup.pendingLink = nil } }), titleVisibility: .visible) {
            Button("Set up") { setup.confirmPending() }
            Button("Cancel", role: .cancel) { setup.pendingLink = nil }
        } message: {
            Text(setupMessage)
        }
        // A code scanned in the app that names no certificate (a radar made
        // before certificates): asked once before anything is sent
        // (2026-11-15).
        .confirmationDialog("This radar has no certificate", isPresented: Binding(
            get: { setup.unprotectedLink != nil },
            set: { if !$0 { setup.unprotectedLink = nil } }), titleVisibility: .visible) {
            Button("Continue") { setup.confirmUnprotected() }
            Button("Cancel", role: .cancel) { setup.unprotectedLink = nil }
        } message: {
            Text(RadarSetup.unprotectedQuestion(onSetupNetwork: setup.unprotectedLink?.onSetupNetwork ?? true))
        }
        .alert(pairing.message ?? "", isPresented: Binding(
            get: { pairing.message != nil && !showSettings },
            set: { if !$0 { pairing.message = nil } })) {
            Button("OK", role: .cancel) { pairing.message = nil }
        }
    }

    // The two dialogs' messages, built step by step: as one expression they
    // took GitHub's Swift compiler past its type-checking limit (CodeQL).
    // Pairing's says what the radar gets, and whether the radar view moves
    // to it (2026-10-26): a link can come from any page or message.
    private var pairingMessage: String {
        guard let link = pairing.pendingLink else { return "" }
        var text = "Only pair with a code shown on your own radar's screen. This phone will get that radar's alerts."
        // What the radar is told of this phone's location, as it will be
        // (2026-11-15): a radar new to this phone by a link starts without it,
        // and one already paired keeps the owner's choice.
        if let known = pairing.radars.first(where: { $0.unit == link.unit }) {
            text += known.shareLocation == false
                ? " It stays as you set it: not told where this phone is."
                : " As now, while Approaching me, or nearby alerts about where you are, is on, that radar gets this phone's location."
        } else {
            text += " It won't get this phone's location unless you turn that on afterwards, on its page under Settings › Paired radars; Approaching me and nearby alerts about where you are need it."
        }
        if let name = link.name {
            text += "\nIt calls itself “\(name)”."
            if pairing.radars.contains(where: { $0.name == name && $0.unit != link.unit }) {
                text += " You already have a radar by that name: this is a different one."
            }
        }
        if let host = link.host { text += "\nRadar at \(host)" }
        if link.host != nil || link.publicURL != nil {
            text += PairingStore.radarViewUnset ? "\nThe radar view will read it." : "\nThe radar view stays on the radar it reads now."
        }
        return text
    }

    // Says only what the app knows (2026-11-15): the link names the radar,
    // and nothing in it shows whose radar that is.
    private var setupMessage: String {
        var text = "The link names the radar; the app can't tell whose it is. Continue only if you just scanned the code on your own new radar's screen. "
        if let ssid = setup.pendingLink?.ssid {
            text += "Your phone will join its setup network “\(ssid)” and send it your home WiFi password. "
        } else if let lan = setup.pendingLink?.lan {
            text += "It will set up the radar at \(lan) on this network. "
        }
        // what else a yes does (SR-06, 2026-11-15)
        text += "This phone will pair with that radar and get its alerts. "
        text += "The radar gets this phone's location only if you choose that."
        return text
    }

    /// A radar is paired, or one was typed in by address.
    private func syncHasRadar() {
        viewModel.hasRadar = !pairing.radars.isEmpty || APIConfig.baseURL != APIConfig.defaultBaseURL
        // another radar's addresses, or none: the last one's place isn't this one's
        let reads = APIConfig.baseURL + "|" + (APIConfig.awayURL ?? "") + "|" + (viewModel.hasRadar ? "1" : "0")
        if let was = radarRead, was != reads {
            viewModel.radarChanged()
            WatchSync.shared.push()
            WidgetCenter.shared.reloadAllTimelines()
        }
        radarRead = reads
        // for the widgets, which can't see the pairing: "no radar yet" is
        // not "your radar can't be reached"
        if APIConfig.hasRadar != viewModel.hasRadar {
            APIConfig.hasRadar = viewModel.hasRadar
            WidgetCenter.shared.reloadAllTimelines()
            WatchSync.shared.push()
        }
    }

    /// Without a radar, on the sky around the phone, until its owner puts it
    /// away: the way to what a radar adds. Not over the demo, wall mode, or
    /// the words about location being off.
    private var wantsInvite: Bool {
        !viewModel.hasRadar && !viewModel.isDemo && !inviteDismissed && !inWallMode
            && viewModel.networkOn && viewModel.hasViewCentre
    }

    private var invitePill: some View {
        HStack(spacing: 0) {
            Button { showInvite = true } label: {
                Label("See what a StratoScan radar adds", systemImage: "antenna.radiowaves.left.and.right")
                    .font(.system(size: 13 * ui, weight: .semibold))
                    .lineLimit(1).minimumScaleFactor(0.8)
                    .padding(.leading, 14).padding(.vertical, 10)
            }
            Button { withAnimation { inviteDismissed = true } } label: {
                Image(systemName: "xmark").font(.system(size: 11 * ui, weight: .bold))
                    .frame(minWidth: 44, minHeight: 44)
                    .contentShape(Rectangle())
                    .foregroundColor(pal.textDim)
            }
            .accessibilityLabel("Don't show this again")
        }
        .buttonStyle(.plain)
        .foregroundColor(pal.mid)
        .background(pal.bg.opacity(0.9), in: Capsule())
        .overlay(Capsule().stroke(pal.mid.opacity(0.5), lineWidth: 1))
        .padding(.horizontal, 16).padding(.bottom, 8)
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

    /// The logo sits centred between the top bar's two groups of buttons. On
    /// an iPhone the left group (labels, location, Sky view: three buttons on
    /// discs, 44 pt each) reached into it (2026-10-13: "the binoculars
    /// overlaps the StratoScan icon"). So it is sized to the gap that is left
    /// on both sides of the centre, and on a phone so narrow that it would be
    /// too small to read, it moves below the buttons instead.
    /// The gap between the top bar's buttons.
    static let barSpacing: CGFloat = 8

    private func logoLayout(_ width: CGFloat) -> (height: CGFloat, below: Bool) {
        let full = 32 * ui
        if inWallMode { return (full, false) }        // no buttons up there
        // the wider group: three discs and the two gaps between them (the
        // gaps were left out, and the binoculars covered the logo's edge)
        let group: CGFloat = 3 * 44 + 2 * Self.barSpacing
        let gap = width - 2 * (group + 8)              // centred: clear of it on both sides
        let fit = gap / StratoScanLogo.widthPerHeight
        if fit >= full { return (full, false) }
        if fit >= 22 { return (fit, false) }        // the wordmark still about 9 pt high
        return (full, true)
    }

    private func hud(_ width: CGFloat) -> some View {
        let logo = logoLayout(width)
        return VStack(spacing: 2) {
            StratoScanLogo(height: logo.height, onLight: !pal.dark)
                .opacity(0.9)
                .padding(.top, logo.below ? 44 : 0)
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
                .foregroundColor(pal.text.opacity(0.85))
                .shadow(color: pal.bg.opacity(0.9), radius: 2)
                .textCase(.uppercase)
                .multilineTextAlignment(.center)
            Text(countText)
                .font(.system(size: 15 * ui, design: .monospaced))
                .tracking(1)
                .foregroundColor(pal.text)
                .shadow(color: pal.bg.opacity(0.9), radius: 2)
            // At home, while the radar's own check finds its public web
            // address down (#82): said before the owner leaves and needs it.
            if !pairing.publicAddressDown.isEmpty, viewModel.connected, Endpoint.shared.whereNow == .home {
                Text("PUBLIC ADDRESS DOWN · REPAIRING")
                    .font(.system(size: 10 * ui, weight: .semibold, design: .monospaced))
                    .tracking(1.2)
                    .foregroundColor(.orange)
                    .shadow(color: pal.bg.opacity(0.9), radius: 2)
                    .padding(.top, 2)
                    .accessibilityLabel("Your radar's public web address is down. The radar is repairing it; away from home it can't be reached until then.")
            }
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
        func place(_ c: Coordinate) -> String {
            String(format: "%.4f°%@ %.4f°%@ · ", abs(c.lat), c.lat >= 0 ? "N" : "S", abs(c.lon), c.lon >= 0 ? "E" : "W") + rangeText
        }
        if !viewModel.hasRadar && !viewModel.isDemo {
            // Without a radar the view rests on the phone. It said "FINDING
            // YOU…" for as long as the centre-on-me button was untouched,
            // with the map already on the phone (2026-11-15).
            if let moved = viewModel.panCentre { return place(moved) }
            if viewModel.me != nil { return "AROUND YOU · " + rangeText }
            return location.denied ? "LOCATION IS OFF FOR STRATOSCAN IN SETTINGS" : "FINDING YOU…"
        }
        guard let home = viewModel.home else { return "LOCATING…" }
        return place(home)
    }

    /// The line at the bottom: where the aircraft are coming from, or what
    /// is needed for there to be any.
    @ViewBuilder
    private func footer(_ geo: GeometryProxy) -> some View {
        let mono = Font.system(size: 10 * ui, weight: .medium, design: .monospaced)
        let pad = geo.size.height * 0.06
        if viewModel.isDemo {
            Text("DEMO · TRAFFIC RECORDED NEAR RDU").font(mono).tracking(2).foregroundColor(pal.textDim).padding(.bottom, pad)
        } else if viewModel.networkOn && !viewModel.hasViewCentre && (!viewModel.hasRadar || (!viewModel.connecting && !viewModel.connected)) {
            // Without a radar (or with one that can't be reached and whose
            // place was never read) the view is the sky around the phone, and
            // this is before the phone's location: asked for and not here yet,
            // or refused. Refused, the screen was an empty sea with no word of
            // why (2026-11-15).
            if location.denied {
                VStack(spacing: 8) {
                    Text("LOCATION IS OFF FOR STRATOSCAN").font(mono).tracking(2).foregroundColor(pal.bad)
                    Text("The aircraft around you are found from where you are.")
                        .font(.system(size: 11 * ui)).foregroundColor(pal.textDim).multilineTextAlignment(.center)
                    Button("Turn it on in Settings") {
                        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                    }
                    .font(.system(size: 13 * ui, weight: .medium)).foregroundColor(pal.mid)
                    Button("Or try the demo") { viewModel.setDemo(true) }
                        .font(.system(size: 13 * ui, weight: .medium)).foregroundColor(pal.mid)
                }
                .padding(.horizontal, 24).padding(.bottom, pad)
            } else {
                VStack(spacing: 8) {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small).tint(pal.textDim)
                        Text("FINDING YOU…").font(mono).tracking(2).foregroundColor(pal.textDim)
                    }
                    // a way on if the phone is never found (indoors, a simulator)
                    if !viewModel.hasRadar {
                        Button("Or try the demo") { viewModel.setDemo(true) }
                            .font(.system(size: 13 * ui, weight: .medium)).foregroundColor(pal.mid)
                    }
                }
                .padding(.bottom, pad)
            }
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
            // Said first, and in a word: whose aircraft these are. Without a
            // radar they are the public network's, around the phone or
            // wherever the map was moved to.
            let why = !viewModel.hasRadar ? (viewModel.panCentre == nil ? "PUBLIC NETWORK · AROUND YOU" : "PUBLIC NETWORK")
                : (!viewModel.connected && !viewModel.beyondRadar ? "YOUR RADAR IS OUT OF REACH" : "BEYOND YOUR RADAR")
            let covered = NetworkFeed.discs(around: viewModel.viewCentre, halfNm: viewModel.rangeNm).coveredNm
            let reach = covered < viewModel.rangeNm ? " · WITHIN \(Int(covered)) NM OF THE MIDDLE" : ""
            // read as easily as the header's lines: in the dim colour it
            // was lost on a dark map
            Text("\(why) · DATA © ADSB.LOL (ODbL)\(reach)")
                .font(mono).tracking(2).foregroundColor(pal.text.opacity(0.85)).shadow(color: pal.bg.opacity(0.9), radius: 2)
                .multilineTextAlignment(.center)
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
        } else if viewModel.source == .radar && !inWallMode {
            // and with one, at home, they are its own: nothing said so
            // "live" only while its receiver is writing its list: the radar's
            // web side answers with the receiver stopped too
            Text(viewModel.receiverReporting ? "YOUR RADAR · LIVE" : "YOUR RADAR · ITS RECEIVER HAS STOPPED REPORTING")
                .font(mono).tracking(2)
                .foregroundColor(viewModel.receiverReporting ? pal.text.opacity(0.85) : pal.bad)
                .shadow(color: pal.bg.opacity(0.9), radius: 2)
                .multilineTextAlignment(.center).padding(.horizontal, 24).padding(.bottom, pad)
        }
    }
}

private struct SelectedAircraft: Identifiable { let id: String }

#Preview {
    ContentView().environmentObject(PairingStore()).environmentObject(RadarSetup())
}


/// A control on the map's top bar. It used to be the theme's dim text colour
/// straight on the map, and on a grey map (the Classic theme over the map's
/// own colour filter) the icons and the location line vanished altogether
/// (2026-10-12: "the buttons across the top are gone"). A disc of the theme's
/// background behind each one, and the theme's full text colour, keep them
/// visible on any map in any theme.
private struct TopBarIcon: ViewModifier {
    let pal: Palette
    let tint: Color?
    func body(content: Content) -> some View {
        content
            .foregroundColor(tint ?? pal.text)
            .frame(width: 38, height: 38)
            .background(Circle().fill(pal.bg.opacity(0.72)))
            .overlay(Circle().stroke(pal.textDim.opacity(0.35), lineWidth: 0.5))
            .padding(3)
    }
}

extension View {
    func topBarIcon(_ pal: Palette, tint: Color? = nil) -> some View {
        modifier(TopBarIcon(pal: pal, tint: tint))
    }
}

/// Keeps a screen's top controls off its rounded corners (#101). Where
/// something already sits across the top (an iPhone's Dynamic Island or
/// notch, upright), the safe area puts the controls below it, well clear of
/// the corners. Where nothing does, the safe area reaches the very top and
/// sides: the iPhone Duo unfolded, with the status bar hidden, put the
/// outermost buttons right into its large rounded corners, half out of
/// sight (2026-11-14). There they come in from the top and the sides.
struct ClearOfScreenCorners: ViewModifier {
    /// Less than this across the top: nothing there, the corners are bare.
    static let bare: CGFloat = 20
    static let top: CGFloat = 12
    static let side: CGFloat = 22
    /// What the controls need beyond the safe area, given its insets.
    static func extra(_ i: EdgeInsets) -> EdgeInsets {
        guard i.top < bare else { return EdgeInsets() }
        return EdgeInsets(top: max(0, top - i.top), leading: max(0, side - i.leading),
                          bottom: 0, trailing: max(0, side - i.trailing))
    }
    func body(content: Content) -> some View {
        // Inside the safe area, the reader is told the screen's insets
        // (ignoring the safe area would tell it none), and the controls only
        // need what the safe area doesn't already give.
        GeometryReader { g in
            content.padding(Self.extra(g.safeAreaInsets))
                // a reader puts what it holds at its top left: the logo,
                // narrower than the screen, stays centred
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        }
    }
}

extension View {
    func clearOfScreenCorners() -> some View { modifier(ClearOfScreenCorners()) }
}
