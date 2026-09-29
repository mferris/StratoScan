import SwiftUI
import WidgetKit

@main
struct RadomeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var pairing = PairingStore()
    @StateObject private var push = PushManager.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.dark)
                .environmentObject(pairing)
                .environmentObject(push)
                // radome://pair links: from the Camera app, the setup page,
                // or anything else that opens one.
                .onOpenURL { pairing.handle($0) }
                // Push tokens can change; re-register whenever a radar is paired.
                .task { if !pairing.radars.isEmpty { await push.enable() } }
                // The widget refreshes on iOS's budget; opening the app is a good moment too.
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                    WidgetCenter.shared.reloadAllTimelines()
                    PushManager.shared.endFinishedActivities()
                }
        }
    }
}
