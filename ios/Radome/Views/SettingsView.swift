import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var pairing: PairingStore
    @State private var baseURL: String = APIConfig.baseURL

    var body: some View {
        NavigationView {
            Form {
                PairedRadarsSection()
                if !pairing.radars.isEmpty { AlertsSection() }

                Section {
                    TextField("http://<radar>", text: $baseURL)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    if let host = pairedHost, baseURL != "http://\(host)" {
                        Button("Use this radar's home address (\(host))") {
                            baseURL = "http://\(host)"
                        }
                    }
                } header: {
                    Text("Radar view address")
                } footer: {
                    Text("Where the live radar view on this screen reads from. Pairing fills in the radar's home address, which works on your home WiFi. Away from home, use the radar's Tailscale name if you set one up. Alerts don't depend on this: they come through the Radome service wherever you are.")
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
        guard !t.isEmpty else { return }
        APIConfig.baseURL = t.hasPrefix("http://") || t.hasPrefix("https://") ? t : "http://\(t)"
    }
}

#Preview {
    SettingsView().environmentObject(PairingStore()).environmentObject(PushManager.shared)
}
