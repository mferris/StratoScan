import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var baseURL: String = APIConfig.baseURL

    var body: some View {
        NavigationView {
            Form {
                Section {
                    TextField("Base URL", text: $baseURL)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                } header: {
                    Text("Receiver address")
                } footer: {
                    Text("Defaults to the Tailscale hostname (works from anywhere Tailscale is connected, or over the public internet if Funnel is on). On home WiFi you can instead use the Pi's LAN address, e.g. http://<radar>, for lower latency and no internet dependency.")
                }

                Section {
                    Button("Reset to Tailscale default") {
                        baseURL = APIConfig.defaultBaseURL
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        APIConfig.baseURL = baseURL
                        dismiss()
                    }
                }
            }
        }
    }
}

#Preview {
    SettingsView()
}
