import SwiftUI

@main
struct RadomeApp: App {
    @StateObject private var pairing = PairingStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.dark)
                .environmentObject(pairing)
                // radome://pair links: from the Camera app, the setup page,
                // or anything else that opens one.
                .onOpenURL { pairing.handle($0) }
        }
    }
}
