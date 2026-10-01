import SwiftUI

struct SettingsView: View {
    @ObservedObject var viewModel: RadarViewModel
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var pairing: PairingStore
    @State private var baseURL: String = APIConfig.baseURL
    @State private var awayURL: String = APIConfig.awayURL ?? ""
    @State private var showNetwork: Bool = AircraftFeedClient.showNetwork

    var body: some View {
        NavigationView {
            Form {
                Section {
                    StratoScanLogo(height: 36)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 4)
                }
                .listRowBackground(Color.clear)
                PairedRadarsSection()
                if !pairing.radars.isEmpty { AlertsSection() }
                ThemeSection()

                Section {
                    LabeledContent("At home") {
                        TextField("http://<radar>", text: $baseURL)
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
                    Text("The app uses the home address on your WiFi and switches to the away address, the radar's public HTTPS page, when you leave. The away address is filled in automatically when the radar has one: turn on its public page in the radar's setup under Remote access. Alerts don't depend on either; they arrive wherever you are.")
                }

                Section {
                    Toggle("Show aircraft the radar didn't hear", isOn: $showNetwork)
                } footer: {
                    Text("Adds aircraft a public ADS-B network (adsb.lol) reports near the radar that its own antenna missed, drawn hollow, as on the radar's screen. The radar fetches them once for everyone; turning this off stops the app asking.")
                }

                Section {
                    Toggle("Demo mode", isOn: Binding(get: { viewModel.isDemo }, set: { viewModel.setDemo($0) }))
                } footer: {
                    Text("Plays a few minutes of real traffic recorded near RDU airport, so you can see StratoScan working without a radar.")
                }

                Section {
                    NavigationLink("About & credits") { CreditsView() }
                }
            }
            // Saved however the sheet closes, Done or a swipe down.
            .onDisappear { save() }
            // Saved as it's switched: a didSet on @State doesn't fire for a
            // binding write, so it would never have been stored.
            .onChange(of: showNetwork) { _, on in AircraftFeedClient.showNetwork = on }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
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
