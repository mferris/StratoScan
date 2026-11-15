import SwiftUI

/// What a StratoScan radar adds to the app (2026-11-15).
///
/// The app works without a radar: the aircraft around the phone, from the
/// public adsb.lol network. What a radar adds was nowhere said. Alerts were
/// a section missing from Settings, the logbook an explanation behind its
/// button, the widgets an error, and the one card that asked "No StratoScan
/// radar yet?" only showed with the public network switched off, which it
/// isn't unless its owner turns it off. This is the one place that says it,
/// reached from the radar screen, Settings and the logbook.
///
/// It is an invitation, not a gate: nothing here is needed to go on using
/// the app as it is.
struct RadarInvite: View {
    @ObservedObject var viewModel: RadarViewModel
    @Environment(\.dismiss) private var dismiss
    /// To where a radar's code is scanned (Settings), when the way there is
    /// not already behind this screen.
    var pair: (() -> Void)? = nil
    /// Run after the demo is turned on, to close whatever this is shown in.
    var afterDemo: (() -> Void)? = nil

    static let buildURL = URL(string: "https://github.com/mferris/StratoScan#readme")!

    /// What the radar does that the public network can't. Each is something
    /// the app does today with a radar paired, and not without.
    static let adds: [(symbol: String, title: String, detail: String)] = [
        ("antenna.radiowaves.left.and.right", "Your own antenna, live",
         "The aircraft your radar hears itself, every second, inside its range rings. The public network fills in the ones it didn't hear."),
        ("bell.badge", "Alerts",
         "Emergencies, notable and rare aircraft, low passes overhead, helicopters, and a countdown when one is coming your way."),
        ("book.closed", "A logbook",
         "Everything your radar has heard: records, regulars, the busiest hours, the year so far."),
        ("info.circle", "More about each aircraft",
         "How many times it has been by and, on your home WiFi, how many of those were close passes and who it is registered to."),
        ("applewatch", "On your wrist and Home Screen",
         "Widgets, StandBy and the Apple Watch show how many aircraft your radar hears, and the nearest."),
        ("circle.dashed.inset.filled", "A radar of your own",
         "A round screen on your desk or wall, showing your sky all day."),
    ]

    var body: some View {
        List {
            Section {
                VStack(spacing: 10) {
                    StratoScanLogo(height: 34)
                    // only someone on the public network is told they are
                    Text((viewModel.hasRadar || viewModel.isDemo ? "" : "You're seeing the aircraft around you from the public adsb.lol network. ")
                         + "A StratoScan radar is your own receiver: it hears the aircraft over your home itself.")
                        .font(.callout).multilineTextAlignment(.center).foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 6)
            }
            .listRowBackground(Color.clear)

            Section("With a radar") {
                ForEach(Self.adds, id: \.title) { item in
                    Label {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.title).font(.body.weight(.semibold))
                            Text(item.detail).font(.footnote).foregroundColor(.secondary)
                        }
                    } icon: {
                        Image(systemName: item.symbol)
                    }
                    .padding(.vertical, 2)
                }
            }

            Section {
                Link(destination: Self.buildURL) { Label("How to build a StratoScan radar", systemImage: "hammer") }
                if let pair {
                    Button { pair() } label: { Label("I have one: scan its code", systemImage: "qrcode.viewfinder") }
                }
                if !viewModel.isDemo {
                    Button {
                        viewModel.setDemo(true)
                        if let afterDemo { afterDemo() } else { dismiss() }
                    } label: { Label("Try it with recorded traffic", systemImage: "play.circle") }
                }
            } footer: {
                Text("The demo plays a few minutes recorded near RDU airport, with the rings, the sweep and a logbook, as a radar's owner sees them. Turn it off in Settings. Without a radar the app stays as it is.")
            }
        }
        .navigationTitle("What a radar adds")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// The invitation as a sheet of its own, from the radar screen.
struct RadarInviteSheet: View {
    @ObservedObject var viewModel: RadarViewModel
    var pair: (() -> Void)? = nil
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            RadarInvite(viewModel: viewModel, pair: pair, afterDemo: { dismiss() })
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
