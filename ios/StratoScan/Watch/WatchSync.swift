import Foundation
import WatchConnectivity

/// Tells the Watch app (roadmap 3.1) which radar to read: the home and away
/// addresses, and whether demo mode is on. The Watch can't read the phone's
/// shared settings, so the phone sends them whenever they may have changed.
/// Only the radar's addresses travel -- nothing about the owner.
final class WatchSync: NSObject, WCSessionDelegate {
    static let shared = WatchSync()

    func start() {
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    /// Send the current settings; cheap, and iOS keeps only the latest.
    func push() {
        guard WCSession.isSupported(), WCSession.default.activationState == .activated,
              WCSession.default.isPaired, WCSession.default.isWatchAppInstalled else { return }
        try? WCSession.default.updateApplicationContext([
            "home": APIConfig.baseURL,
            "away": APIConfig.awayURL ?? "",
            "demo": DemoFeed.isOn,
        ])
    }

    func session(_ s: WCSession, activationDidCompleteWith state: WCSessionActivationState, error: Error?) {
        if state == .activated { push() }
    }
    func sessionDidBecomeInactive(_ s: WCSession) {}
    func sessionDidDeactivate(_ s: WCSession) { s.activate() }
    func sessionWatchStateDidChange(_ s: WCSession) { push() }
}
