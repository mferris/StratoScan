import SwiftUI

struct SettingsView: View {
    @ObservedObject var viewModel: RadarViewModel
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var pairing: PairingStore
    @EnvironmentObject private var setup: RadarSetup
    @State private var scanning = false
    @State private var baseURL: String = APIConfig.baseURL
    @State private var awayURL: String = APIConfig.awayURL ?? ""

    var body: some View {
        NavigationView {
            Form {
                Section {
                    StratoScanLogo(height: 36)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 4)
                }
                .listRowBackground(Color.clear)
                PairedRadarsSection(scanning: $scanning)
                if !pairing.radars.isEmpty { AlertsSection() }
                ThemeSection()
                WeatherSection()

                Section {
                    LabeledContent("At home") {
                        TextField("http://192.168.4.77", text: $baseURL)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.URL).autocapitalization(.none).disableAutocorrection(true)
                    }
                    if let host = pairedHost, baseURL != "http://\(host)" {
                        Button("Use this radar's home address (\(host))") { baseURL = "http://\(host)" }
                    }
                    LabeledContent("Away") {
                        TextField("https://… (optional)", text: $awayURL)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.URL).autocapitalization(.none).disableAutocorrection(true)
                    }
                    LabeledContent("Using now", value: viewModel.isDemo ? "Demo" : (viewModel.viaAway ? "Away address" : "Home address"))
                } header: {
                    Text("Radar view")
                } footer: {
                    Text("The app reads your radar at its home address on your WiFi, and through its public HTTPS page (the away address) from anywhere else. The away address is filled in by itself when the radar has one: turn on its public page in the radar's setup under Remote access. Alerts don't depend on either; they arrive wherever you are.")
                }

                Section {
                    Toggle(isOn: $viewModel.networkOn) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Aircraft from the public network")
                            Text("adsb.lol, the same network your radar feeds").font(.caption).foregroundColor(.secondary)
                        }
                    }
                } header: {
                    Text("Public network")
                } footer: {
                    Text("One switch for everything the network adds. At home it fills in the aircraft your radar didn't hear, drawn half-filled with an outline so you can tell them from the ones it heard. Away from your radar, beyond its 20 nm, or with no radar at all, the view centres on you and shows the aircraft around you; the centre button switches between that and your radar's view. Pan the map anywhere and it shows the network's aircraft there, within 250 nm of the middle. To ask for aircraft around a place the app sends adsb.lol that place rounded to about 5 km — when that place is you, that is the only thing about you that leaves the phone. Alerts and the logbook come from your radar only.")
                }

                Section {
                    Toggle("Demo mode", isOn: Binding(get: { viewModel.isDemo }, set: { viewModel.setDemo($0) }))
                } footer: {
                    Text("Plays a few minutes of traffic recorded near RDU airport, with no radar and no network.")
                }

                Section {
                    NavigationLink("About & credits") { CreditsView() }
                }
            }
            // Saved however the sheet closes, Done or a swipe down.
            .onDisappear { save() }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .fullScreenCover(isPresented: $scanning) {
            ZStack(alignment: .topTrailing) {
                PairingScannerView { url in
                    scanning = false
                    // Scanned on purpose from this screen: that is the confirmation.
                    if let link = PairingStore.parse(url) {
                        Task { await pairing.pair(link) }
                    } else {
                        // A new radar's setup code. Settings closes so the
                        // setup screens (presented from the root) can show.
                        dismiss()
                        Task {
                            // after Settings has gone: one screen can't present over another closing
                            try? await Task.sleep(for: .milliseconds(700))
                            if let l = RadarSetup.parse(url) { setup.start(l, pairing: pairing) }   // scanned on purpose: that's the yes
                        }
                    }
                }
                .ignoresSafeArea()
                Button {
                    scanning = false
                } label: {
                    Image(systemName: "xmark").font(.headline).padding(14)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .padding()
                .accessibilityLabel("Close")
            }
            .overlay(alignment: .bottom) {
                Text("Point at the code on the radar's screen")
                    .font(.callout).padding(.horizontal, 16).padding(.vertical, 10)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.bottom, 40)
            }
        }
    }
}

extension SettingsView {
    /// The home address learned when the first radar was paired (its QR code carries it).
    private var pairedHost: String? { pairing.radars.compactMap(\.host).first }

    private func save() {
        let t = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty {
            let v = t.hasPrefix("http://") || t.hasPrefix("https://") ? t : "http://\(t)"
            if v != APIConfig.baseURL { APIConfig.baseURL = v }
        }
        let a = awayURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let away = a.isEmpty ? nil : (a.hasPrefix("https://") ? a : "https://\(a)")
        if away != APIConfig.awayURL { APIConfig.awayURL = away }
        WatchSync.shared.push()
    }
}

#Preview {
    SettingsView(viewModel: RadarViewModel()).environmentObject(PairingStore()).environmentObject(PushManager.shared)
        .environmentObject(RadarSetup())
}


/// The colour theme (#43): the radar's four, Daylight first and by default.
private struct ThemeSection: View {
    @AppStorage(Palette.storageKey) private var themeID = Palette.daylight.id

    var body: some View {
        Section {
            ForEach(Palette.all) { p in
                Button { themeID = p.id } label: {
                    HStack(spacing: 12) {
                        // a small preview: the theme's background, ring and sweep
                        ZStack {
                            Circle().fill(p.bg)
                            Circle().stroke(p.ringBright, lineWidth: 2)
                            Circle().trim(from: 0, to: 0.12).stroke(p.sweep, lineWidth: 6).rotationEffect(.degrees(-90))
                        }
                        .frame(width: 30, height: 30)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name).foregroundColor(.primary)
                            Text(p.detail).font(.caption).foregroundColor(.secondary)
                        }
                        Spacer()
                        if p.id == themeID { Image(systemName: "checkmark").foregroundColor(.accentColor) }
                    }
                }
            }
        } header: {
            Text("Colour theme")
        } footer: {
            Text("The same themes as the radar's screen. The Watch and widgets stay dark.")
        }
    }
}


/// Weather on the map (#42), as on the radar's screen.
private struct WeatherSection: View {
    @AppStorage("stratoscan.storms") private var storms = true
    @AppStorage("stratoscan.lightning") private var lightning = false

    var body: some View {
        Section {
            Toggle(isOn: $storms) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Rain and storms")
                    Text("Weather radar under the aircraft, updated every few minutes (RainViewer)")
                        .font(.caption).foregroundColor(.secondary)
                }
            }
            Toggle(isOn: $lightning) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Lightning")
                    Text("Recent strikes seen from satellite, in the Americas only (RealEarth, UW–Madison)")
                        .font(.caption).foregroundColor(.secondary)
                }
            }
        } header: {
            Text("Weather")
        }
    }
}
