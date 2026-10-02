import SwiftUI

/// The screens for setting up a new radar from the app (roadmap 2.18). The
/// work is in RadarSetup; this only shows where it has got to and asks for
/// the two things the phone can't know: a name, and the home WiFi password.
struct RadarSetupView: View {
    @ObservedObject var setup: RadarSetup
    @FocusState private var pskFocused: Bool

    var body: some View {
        NavigationStack {
            Group {
                switch setup.step {
                case .name: nameStep
                case .wifi: wifiStep
                case .done: doneStep
                case .failed(let why): failedStep(why)
                default: working
                }
            }
            .navigationTitle("Set up a radar")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if setup.step != .done {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { setup.cancel() }
                    }
                }
            }
        }
        .interactiveDismissDisabled()
    }

    private var working: some View {
        VStack(spacing: 18) {
            StratoScanLogo(height: 40)
            ProgressView().controlSize(.large)
            Text(setup.detail).multilineTextAlignment(.center).foregroundStyle(.secondary)
            Text(stepCaption).font(.caption).foregroundStyle(.tertiary)
        }
        .padding(32)
    }

    private var stepCaption: String {
        switch setup.step {
        case .joining: return "Step 1 of 5"
        case .claiming, .details: return "Step 2 of 5"
        case .switching, .pairing: return "Step 4 of 5"
        case .finding: return "Step 5 of 5"
        default: return ""
        }
    }

    private var nameStep: some View {
        Form {
            Section {
                TextField("Name", text: $setup.name)
                    .textInputAutocapitalization(.words)
                    .submitLabel(.next)
                    .onSubmit { Task { await setup.saveName() } }
            } header: {
                Text("Name this radar")
            } footer: {
                Text("Shown on its screen and on phones paired with it, such as \"Raleigh\" or \"Mom's radar\". It isn't shown on its public page. You can change it later on the radar.")
            }
            Section {
                Button {
                    Task { await setup.saveName() }
                } label: {
                    HStack { Text("Continue"); if setup.busy { Spacer(); ProgressView() } }
                }
                .disabled(setup.busy)
            } footer: {
                Text("Its location, nearest airport and time zone were set from this phone.")
            }
        }
    }

    private var wifiStep: some View {
        Form {
            Section {
                ForEach(setup.networks) { n in
                    Button {
                        setup.ssid = n.ssid
                        pskFocused = n.secured != false
                    } label: {
                        HStack {
                            Text(n.ssid).foregroundStyle(.primary)
                            Spacer()
                            if setup.ssid == n.ssid { Image(systemName: "checkmark") }
                            if n.secured != false { Image(systemName: "lock.fill").foregroundStyle(.secondary) }
                        }
                    }
                }
                Button(setup.busy ? "Looking…" : "Look again") { Task { await setup.scan() } }
                    .disabled(setup.busy)
            } header: {
                Text("Your home WiFi")
            } footer: {
                if setup.networks.isEmpty && !setup.busy {
                    Text("The radar didn't see any networks. Type yours below.")
                }
            }
            Section {
                TextField("Network name", text: $setup.ssid)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Password", text: $setup.psk)
                    .focused($pskFocused)
                    .submitLabel(.join)
                    .onSubmit { Task { await setup.join() } }
            } footer: {
                Text("The radar joins this network and your phone goes back to it. The password goes only to the radar.")
            }
            Section {
                Button("Join") { Task { await setup.join() } }
                    .disabled(setup.ssid.isEmpty || setup.busy)
            }
        }
    }

    private var doneStep: some View {
        VStack(spacing: 18) {
            Image(systemName: "checkmark.circle.fill").font(.system(size: 56)).foregroundStyle(.green)
            Text("\(setup.name.isEmpty ? "Your radar" : setup.name) is set up").font(.title2.bold())
            Text(setup.detail.isEmpty
                 ? "It's on your WiFi and paired with this phone. Its alerts will come here."
                 : setup.detail)
                .multilineTextAlignment(.center).foregroundStyle(.secondary)
            Button("Done") { setup.cancel() }
                .buttonStyle(.borderedProminent)
                .padding(.top, 8)
        }
        .padding(32)
    }

    private func failedStep(_ why: String) -> some View {
        VStack(spacing: 18) {
            Image(systemName: "exclamationmark.triangle.fill").font(.system(size: 48)).foregroundStyle(.orange)
            Text(why).multilineTextAlignment(.center)
            Button("Close") { setup.cancel() }
                .buttonStyle(.bordered)
        }
        .padding(32)
    }
}
