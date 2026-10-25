import SwiftUI
import WidgetKit

@main
struct StratoScanApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var pairing = PairingStore()
    @StateObject private var push = PushManager.shared
    @StateObject private var setup = RadarSetup()

    init() {
        WatchSync.shared.start()   // tells the Watch app which radar to read
        // Start watching the network now, so the first look-up for the radar
        // knows whether the phone is on WiFi rather than guessing (2026-10-25).
        _ = Endpoint.shared
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.dark)
                .environmentObject(pairing)
                .environmentObject(push)
                // stratoscan://pair links (radome:// from older units): from the Camera app, the setup page,
                // or anything else that opens one.
                // stratoscan://setup links: a new radar's first-run code (2.18).
                .onOpenURL { url in
                    if !pairing.handle(url) { setup.handle(url, pairing: pairing) }
                }
                .environmentObject(setup)
                .fullScreenCover(isPresented: Binding(get: { setup.active }, set: { if !$0 { setup.cancel() } })) {
                    RadarSetupView(setup: setup)
                }
                // Push tokens can change; re-register whenever a radar is paired.
                .task { if !pairing.radars.isEmpty { await push.enable() } }
                // A paired radar that has moved on the home network is found
                // again by Bonjour, not retyped (#76).
                .task { [pairing] in Endpoint.shared.finder = { await RadarFinder.find(pairing: pairing) } }
                // The network's aircraft and routes from the relay's shared
                // cache while a radar is paired (#68): the relay serves only
                // phones paired with a radar; adsb.lol and adsb.im directly
                // otherwise, or when it doesn't have them.
                .task { [pairing] in
                    let paired: @Sendable () async -> Bool = { await MainActor.run { !pairing.radars.isEmpty } }
                    NetworkFeed.relay = { disc, near, nm in
                        await paired() ? await RelayClient().netDisc(disc, near: near, nm: nm) : nil
                    }
                    RouteLookupClient.relay = { body in await paired() ? await RelayClient().netRoutes(body) : nil }
                }
                // The widget refreshes on iOS's budget; opening the app is a good moment too.
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                    WidgetCenter.shared.reloadAllTimelines()
                    PushManager.shared.endFinishedActivities()
                    WatchSync.shared.push()
                    // At home: pick up a rename made on the radar (2.17).
                    Task { await pairing.refreshNames() }
                }
        }
    }
}
