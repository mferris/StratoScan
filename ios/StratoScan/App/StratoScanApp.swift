import SwiftUI
import WidgetKit

@main
struct StratoScanApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var pairing = PairingStore()
    @StateObject private var push = PushManager.shared
    @StateObject private var setup = RadarSetup()

    init() { WatchSync.shared.start() }   // tells the Watch app which radar to read

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
