import SwiftUI

/// Settings section: the radars this phone gets alerts from.
struct PairedRadarsSection: View {
    @EnvironmentObject private var pairing: PairingStore
    /// Owned by SettingsView, which presents the scanner. Presented from
    /// here, inside the Form, it was dismissed as soon as it appeared: a
    /// list redraws its rows (Settings follows the live radar), and a sheet
    /// attached to a row goes with it.
    @Binding var scanning: Bool

    var body: some View {
        Section {
            ForEach(pairing.radars) { radar in
                NavigationLink {
                    RadarDetailView(radar: radar)
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(radar.name)
                        Text("Paired \(radar.pairedAt.formatted(date: .abbreviated, time: .omitted))")
                            .font(.caption).foregroundColor(.secondary)
                    }
                }
            }
            if PairingScannerView.isAvailable {
                Button("Scan a radar's code") { scanning = true }
            }
            if pairing.busy { ProgressView() }
            // Said here while Settings is open; ContentView says it otherwise.
            if let msg = pairing.message {
                Text(msg).font(.callout).foregroundColor(.secondary)
            }
        } header: {
            Text("Paired radars")
        } footer: {
            Text(pairing.radars.isEmpty
                 ? "A new radar: scan the code on its first screen to set it up from here. One already set up: on the radar, open Settings › Phone & Watch › Pair a phone, and scan that code."
                 : "Alerts say what flew by and roughly how far away, never where the radar is.")
        }
        .task {
            await pairing.refresh()
            await pairing.refreshNames()
        }
        .onDisappear { pairing.message = nil }
    }
}

/// One paired radar: rename it, or stop its alerts.
struct RadarDetailView: View {
    @EnvironmentObject private var pairing: PairingStore
    @Environment(\.dismiss) private var dismiss
    let radar: PairingStore.Radar
    @State private var name = ""
    @State private var confirming = false

    var body: some View {
        Form {
            Section {
                TextField(radar.name, text: $name)
                    .onSubmit { pairing.rename(radar, to: name) }
            } header: {
                Text("Name")
            } footer: {
                Text(radar.ownName == true
                     ? "Your name for it, on this phone. Clear it to use the name set on the radar."
                     : "The name set on the radar. Type your own to use it on this phone instead.")
            }
            Section {
                Button("Unpair this radar", role: .destructive) { confirming = true }
            } footer: {
                Text("This phone stops getting its alerts. Pair again any time from the radar's screen.")
            }
        }
        .navigationTitle(radar.name)
        .onAppear { name = radar.name }
        .onDisappear { pairing.rename(radar, to: name) }
        .confirmationDialog("Stop alerts from \(radar.name)?", isPresented: $confirming, titleVisibility: .visible) {
            Button("Unpair", role: .destructive) {
                Task {
                    await pairing.unpair(radar)
                    dismiss()
                }
            }
        }
    }
}
