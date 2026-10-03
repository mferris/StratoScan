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
    @State private var visits: Visits?

    /// The public page's visitor counts, from the radar itself (its setup
    /// server, LAN only), so only at home.
    struct Visits: Decodable {
        struct Day: Decodable { let views: Int?; let unique: Int?; let app_minutes: Int? }
        let available: Bool?
        let today: Day?
        let days: [Day]?
        let basis: String?
    }

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
            if let v = visits {
                Section {
                    if v.available == true, let t = v.today {
                        LabeledContent("Page views today", value: "\(t.views ?? 0)")
                        if v.basis == "visitors" {
                            LabeledContent("Visitors today", value: "\(t.unique ?? 0)")
                        }
                        LabeledContent("Page views, last 7 days", value: "\((v.days ?? []).suffix(7).reduce(0) { $0 + ($1.views ?? 0) })")
                        LabeledContent("Your app away from home today", value: "\(t.app_minutes ?? 0) min")
                    } else {
                        Text("This radar doesn't count visitors yet; it needs a software update.")
                            .foregroundStyle(.secondary)
                    }
                } header: {
                    Text("Visitors to its public page")
                } footer: {
                    Text("Counts only: no cookies, and nothing that identifies anyone. More on the radar: Settings › Statistics › Public page visitors.")
                }
            }
            Section {
                Button("Unpair this radar", role: .destructive) { confirming = true }
            } footer: {
                Text("This phone stops getting its alerts. Pair again any time from the radar's screen.")
            }
        }
        .navigationTitle(radar.name)
        .onAppear { name = radar.name }
        .task {
            guard let host = radar.host, let url = URL(string: "http://\(host)/setup/api/visits"),
                  let (data, resp) = try? await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 4)),
                  (resp as? HTTPURLResponse)?.statusCode == 200 else { return }
            visits = try? JSONDecoder().decode(Visits.self, from: data)
        }
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
