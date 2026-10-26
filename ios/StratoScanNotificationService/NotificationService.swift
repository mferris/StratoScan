import UserNotifications
import UIKit

/// Runs for each alert before it is shown (the relay marks them
/// mutable-content), and attaches the airline's logo when the aircraft is an
/// airline's (#60). The mark comes from the airline's own site, fetched by
/// AirlineLogos and kept in this extension's cache; nothing about the owner
/// is sent. Anything that fails leaves the alert as it came.
final class NotificationService: UNNotificationServiceExtension {
    private let lock = NSLock()
    private var handler: ((UNNotificationContent) -> Void)?
    private var content: UNMutableNotificationContent?

    /// How long an alert may wait for its airline's mark (#86, 2026-10-26).
    /// The alert is held until this extension hands it back, and the two
    /// icon services, 8 s each, could hold an approaching aircraft's alert
    /// for half a minute. A mark not in hand by then is left off.
    static let logoWaitSeconds: Double = 4

    override func didReceive(_ request: UNNotificationRequest, withContentHandler contentHandler: @escaping (UNNotificationContent) -> Void) {
        lock.withLock { handler = contentHandler }
        let c = (request.content.mutableCopy() as? UNMutableNotificationContent) ?? UNMutableNotificationContent()
        content = c
        guard let info = request.content.userInfo["stratoscan"] as? [String: Any],
              let airline = AirlineLogos.airline(forCallsign: info["flight"] as? String),
              let domain = airline.domain else { deliver(c); return }
        Task {
            let logo = await withTaskGroup(of: UIImage?.self) { g in
                g.addTask { await AirlineLogos.fetch(domain: domain) }
                g.addTask { try? await Task.sleep(for: .seconds(Self.logoWaitSeconds)); return nil }
                let first = await g.next() ?? nil
                g.cancelAll()
                return first
            }
            // its own copy: `c` may already be on its way, out of time
            let out = (c.mutableCopy() as? UNMutableNotificationContent) ?? c
            if let img = logo, let data = img.pngData() {
                // an attachment is moved into the notification's own store, so
                // it gets a copy of its own
                let url = FileManager.default.temporaryDirectory.appendingPathComponent("logo-\(domain)-\(UUID().uuidString).png")
                if (try? data.write(to: url)) != nil,
                   let att = try? UNNotificationAttachment(identifier: "airline", url: url, options: nil) {
                    out.attachments = [att]
                }
            }
            deliver(out)
        }
    }

    /// Out of time: show what there is.
    override func serviceExtensionTimeWillExpire() {
        if let content { deliver(content) }
    }

    /// Hands the alert back once only, whichever comes first.
    private func deliver(_ c: UNNotificationContent) {
        let h: ((UNNotificationContent) -> Void)? = lock.withLock {
            defer { handler = nil }
            return handler
        }
        h?(c)
    }
}
