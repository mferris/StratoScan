import SwiftUI

/// Settings section: the radars this phone gets alerts from.
struct PairedRadarsSection: View {
    @EnvironmentObject private var pairing: PairingStore
    @State private var scanning = false

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
                Button("Scan a radar's pairing code") { scanning = true }
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
                 ? "On the radar, open Settings › Phone & Watch › Pair a phone, then point your iPhone's Camera at the code."
                 : "Alerts say what flew by and roughly how far away, never where the radar is.")
        }
        .sheet(isPresented: $scanning) {
            PairingScannerView { url in
                scanning = false
                // Scanned on purpose from this screen: that tap is the confirmation.
                if let link = PairingStore.parse(url) { Task { await pairing.pair(link) } }
            }
            .ignoresSafeArea()
        }
        .task { await pairing.refresh() }
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
            Section("Name") {
                TextField("Name", text: $name)
                    .onSubmit { pairing.rename(radar, to: name) }
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
