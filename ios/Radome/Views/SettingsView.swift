import SwiftUI

struct SettingsView: View {
    @ObservedObject var viewModel: RadarViewModel
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var pairing: PairingStore
    @State private var baseURL: String = APIConfig.baseURL
    @State private var awayURL: String = APIConfig.awayURL ?? ""

    var body: some View {
        NavigationView {
            Form {
                PairedRadarsSection()
                if !pairing.radars.isEmpty { AlertsSection() }

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
    }
}

#Preview {
    SettingsView(viewModel: RadarViewModel()).environmentObject(PairingStore()).environmentObject(PushManager.shared)
}
