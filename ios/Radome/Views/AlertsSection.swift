import SwiftUI
import UIKit

/// Settings section: which alerts arrive from paired radars.
struct AlertsSection: View {
    @EnvironmentObject private var push: PushManager
    @EnvironmentObject private var pairing: PairingStore

    var body: some View {
        Section {
            if push.permission == .denied {
                Button("Turn on notifications in iOS Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) {
                        UIApplication.shared.open(url)
                    }
                }
            }
            ForEach(PushManager.Kind.allCases) { kind in
                Toggle(isOn: Binding(
                    get: { push.kinds.contains(kind) },
                    set: { on in if on { push.kinds.insert(kind) } else { push.kinds.remove(kind) } })) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(kind.title)
                        Text(kind.detail).font(.caption).foregroundColor(.secondary)
                    }
                }
            }
            Button("Send a test notification") { Task { await push.sendTest() } }
                .disabled(!push.registered)
            if let msg = push.message {
                Text(msg).font(.callout).foregroundColor(.secondary)
            }
        } header: {
            Text("Alerts")
        } footer: {
            Text("Delivered through Apple's push service by the Radome relay. An alert names the aircraft and roughly how far away it is, never where the radar is.")
        }
        .task { await push.refreshPermission() }
        .onDisappear { push.message = nil }
    }
}
