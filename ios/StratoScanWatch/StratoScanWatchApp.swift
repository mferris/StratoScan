import SwiftUI
import WidgetKit
import UserNotifications
import WatchConnectivity

/// StratoScan on the wrist (roadmap 3.1): a glance at the radar, and the
/// nearest aircraft. Reads the same feed as the phone, from the same radar,
/// whose addresses the phone sends over (WatchSync on the phone).
@main
struct StratoScanWatchApp: App {
    init() { WatchReceiver.shared.start(); UNUserNotificationCenter.current().delegate = WatchReceiver.shared }
    var body: some Scene {
        WindowGroup { WatchRadarView() }
    }
}

/// Stores the radar's addresses the phone sends, and the aircraft a tapped
/// alert is about (#61), which the glance picks out.
final class WatchReceiver: NSObject, ObservableObject, WCSessionDelegate, UNUserNotificationCenterDelegate {
    static let shared = WatchReceiver()
    @Published var highlightHex: String?
    /// A radar is set up on the phone, as it last said (yes until it has).
    @Published var hasRadar = APIConfig.hasRadar
    /// Counts up when the phone sends another radar's addresses, or none:
    /// what the glance was showing is the last one's.
    @Published var radarChanges = 0

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard let info = response.notification.request.content.userInfo["stratoscan"] as? [String: Any],
              let hex = info["hex"] as? String else { return }
        await MainActor.run { highlightHex = hex.lowercased() }
    }

    func start() {
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    private func apply(_ c: [String: Any]) {
        let before = "\(APIConfig.baseURL)|\(APIConfig.awayURL ?? "")|\(DemoFeed.isOn)|\(APIConfig.hasRadar)"
        if let home = c["home"] as? String, !home.isEmpty { APIConfig.baseURL = home }
        if let away = c["away"] as? String { APIConfig.awayURL = away.isEmpty ? nil : away }
        if let demo = c["demo"] as? Bool { DemoFeed.isOn = demo }
        if let has = c["hasRadar"] as? Bool { APIConfig.hasRadar = has }
        let after = "\(APIConfig.baseURL)|\(APIConfig.awayURL ?? "")|\(DemoFeed.isOn)|\(APIConfig.hasRadar)"
        let has = APIConfig.hasRadar
        DispatchQueue.main.async {
            self.hasRadar = has
            if before != after {
                self.radarChanges += 1
                WidgetCenter.shared.reloadAllTimelines()
            }
        }
    }

    func session(_ s: WCSession, activationDidCompleteWith state: WCSessionActivationState, error: Error?) {
        if !s.receivedApplicationContext.isEmpty { apply(s.receivedApplicationContext) }
    }
    func session(_ s: WCSession, didReceiveApplicationContext c: [String: Any]) { apply(c) }
}
