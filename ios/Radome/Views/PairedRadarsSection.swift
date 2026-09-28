import SwiftUI

/// Settings section: the radars this phone gets alerts from.
struct PairedRadarsSection: View {
    @EnvironmentObject private var pairing: PairingStore
    @State private var scanning = false
    @State private var renaming: PairingStore.Radar?
    @State private var newName = ""

    var body: some View {
        Section {
            ForEach(pairing.radars) { radar in
                VStack(alignment: .leading, spacing: 2) {
                    Text(radar.name)
                    Text("Paired \(radar.pairedAt.formatted(date: .abbreviated, time: .omitted))")
                        .font(.caption).foregroundColor(.secondary)
                }
                .swipeActions {
                    Button("Unpair", role: .destructive) { Task { await pairing.unpair(radar) } }
                    Button("Rename") { renaming = radar; newName = radar.name }
                }
            }
            if PairingScannerView.isAvailable {
                Button("Scan a radar's pairing code") { scanning = true }
            }
            if pairing.busy { ProgressView() }
        } header: {
            Text("Paired radars")
        } footer: {
            Text(pairing.radars.isEmpty
                 ? "On the radar, open Settings › Phone & Watch › Pair a phone, then point your iPhone's Camera at the code."
                 : "Swipe a radar to rename or unpair it. Alerts say what flew by and roughly how far away, never where the radar is.")
        }
        .sheet(isPresented: $scanning) {
            PairingScannerView { url in
                scanning = false
                pairing.handle(url)
            }
            .ignoresSafeArea()
        }
        .alert("Rename radar", isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } })) {
            TextField("Name", text: $newName)
            Button("Save") { if let r = renaming { pairing.rename(r, to: newName) }; renaming = nil }
            Button("Cancel", role: .cancel) { renaming = nil }
        }
        .task { await pairing.refresh() }
    }
}
