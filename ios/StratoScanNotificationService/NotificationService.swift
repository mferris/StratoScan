import UserNotifications
import UIKit

/// Runs for each alert before it is shown (the relay marks them
/// mutable-content), and attaches the airline's logo when the aircraft is an
/// airline's (#60). The mark comes from the airline's own site, fetched by
/// AirlineLogos and kept in this extension's cache; nothing about the owner
/// is sent. Anything that fails leaves the alert as it came.
final class NotificationService: UNNotificationServiceExtension {
    private var handler: ((UNNotificationContent) -> Void)?
    private var content: UNMutableNotificationContent?

    override func didReceive(_ request: UNNotificationRequest, withContentHandler contentHandler: @escaping (UNNotificationContent) -> Void) {
        handler = contentHandler
        let c = (request.content.mutableCopy() as? UNMutableNotificationContent) ?? UNMutableNotificationContent()
        content = c
        guard let info = request.content.userInfo["stratoscan"] as? [String: Any],
              let airline = AirlineLogos.airline(forCallsign: info["flight"] as? String),
              let domain = airline.domain else { contentHandler(c); return }
        Task {
            if let img = await AirlineLogos.fetch(domain: domain), let data = img.pngData() {
                // an attachment is moved into the notification's own store, so
                // it gets a copy of its own
                let url = FileManager.default.temporaryDirectory.appendingPathComponent("logo-\(domain)-\(UUID().uuidString).png")
                if (try? data.write(to: url)) != nil,
                   let att = try? UNNotificationAttachment(identifier: "airline", url: url, options: nil) {
                    c.attachments = [att]
                }
            }
            contentHandler(c)
        }
    }

    /// Out of time: show what there is.
    override func serviceExtensionTimeWillExpire() {
        if let content, let handler { handler(content) }
    }
}
