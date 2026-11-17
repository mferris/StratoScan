import SwiftUI
import UIKit

/// Settings section: which alerts arrive from paired radars.
struct AlertsSection: View {
    @EnvironmentObject private var push: PushManager
    @EnvironmentObject private var pairing: PairingStore
    @ObservedObject private var reporter = ApproachReporter.shared

    var body: some View {
        Section {
            // The one switch over all of it: off, the relay sends this phone
            // nothing. The choices below stay as they were for when it's on.
            Toggle(isOn: $push.alertsOn) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Alerts from my radar")
                    if !push.alertsOn {
                        Text("Off: nothing is sent to this phone, including the lock-screen countdown.")
                            .font(.caption).foregroundColor(.secondary)
                    }
                }
            }
            if push.permission == .denied {
                // "Nothing is sent" only once the relay has been told so.
                Text(push.pending
                     ? "Notifications are off for StratoScan in iOS. Telling the StratoScan service to send this phone nothing…"
                     : "Notifications are off for StratoScan in iOS, so nothing is sent to this phone.")
                    .font(.callout).foregroundColor(.secondary)
                // iOS tells no app when that switch changes, so the relay
                // hears of it when the app next runs; the switch above is
                // sent at once.
                Text("iOS doesn't tell StratoScan when that switch changes. The service hears of it the next time the app runs, so one more countdown can appear first. The switch above stops everything at once.")
                    .font(.caption).foregroundColor(.secondary)
                Button("Turn on notifications in iOS Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) {
                        UIApplication.shared.open(url)
                    }
                }
            }
            // Where the nearby alerts are about (#44).
            VStack(alignment: .leading, spacing: 6) {
                Text("Nearby alerts are about")
                Picker("Nearby alerts are about", selection: $push.place) {
                    ForEach(PushManager.Place.allCases) { Text($0.title).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                Text(push.place == .radar
                     ? "Low aircraft, helicopters and notable aircraft near your radar."
                     : "Measured from where your phone is, within reach of your radar's antenna. Your location is sent encrypted so only your radar can read it; it needs location set to Always.")
                    .font(.caption).foregroundColor(.secondary)
            }
            .disabled(!push.alertsOn)
            // VoiceOver says only "dimmed" of a disabled control, not why.
            .accessibilityHint(push.alertsOn ? "" : Self.offHint)
            ForEach(PushManager.Kind.allCases) { kind in
                Toggle(isOn: Binding(
                    get: { push.kinds.contains(kind) },
                    set: { on in if on { push.kinds.insert(kind) } else { push.kinds.remove(kind) } })) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(kind.title)
                        Text(kind.detail).font(.caption).foregroundColor(.secondary)
                    }
                }
                .disabled(!push.alertsOn)
                .accessibilityHint(push.alertsOn ? "" : Self.offHint)
            }
            if push.syncFailed {
                // Stays until the relay has the choices: a switch that looks
                // off while alerts still arrive is the fault this is here for.
                VStack(alignment: .leading, spacing: 2) {
                    // Orange callout text is too faint on a white row; the
                    // symbol carries the warning and the words stay readable.
                    Label("Not saved to the StratoScan service yet. Trying again.", systemImage: "exclamationmark.arrow.circlepath")
                        .imageScale(.small)
                        .font(.callout).foregroundColor(.secondary)
                    if let why = push.syncError {
                        Text(why).font(.caption).foregroundColor(.secondary)
                    }
                }
            }
            if push.needsLocation && !reporter.strangers.isEmpty {
                // the tripwire (2026-10-26): see Paired radars above
                Text("Your location isn't being sent: the StratoScan service lists a radar this phone didn't pair with (see Paired radars).")
                    .font(.callout).foregroundColor(.orange)
            }
            if push.needsLocation, let line = Self.withheldLine(pairing.radars.filter { $0.shareLocation == false }.count) {
                // Says how things stand and where the switch is, and no more
                // (2026-11-15): the choice is the owner's, radar by radar. It
                // gives a count, not names: a radar's name comes from the radar.
                Text(line).font(.callout).foregroundColor(.secondary)
            }
            if push.needsLocation && reporter.needsAlways {
                // Without Always, iOS won't wake the app when the phone moves.
                Button("Set location to Always for “Approaching me”") {
                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                }
                .font(.callout)
            }
            // Not while nothing is sent to this phone: alerts off, or
            // notifications refused in iOS, where a test would never show.
            Button("Send a test notification") { Task { await push.sendTest() } }
                .disabled(!push.registered || push.effectiveKinds.isEmpty)
            if let why = push.tokenProblem {
                Text(why).font(.callout).foregroundColor(.secondary)
            }
            if let msg = push.message {
                Text(msg).font(.callout).foregroundColor(.secondary)
            }
        } header: {
            Text("Alerts")
        } footer: {
            Text("Delivered through Apple's push service by the StratoScan relay. An alert names the aircraft and roughly how far away it is, never where the radar is.")
        }
        .task { await push.refreshPermission() }
        // only the test button's result; the "not saved" line stays
        .onDisappear { push.message = nil }
    }

    /// What VoiceOver adds to a choice the master switch has turned off.
    static let offHint = "Turn on Alerts from my radar first"

    /// The line for `count` paired radars that aren't told where the phone
    /// is; nil when every one is.
    static func withheldLine(_ count: Int) -> String? {
        guard count > 0 else { return nil }
        return count == 1
            ? "1 paired radar isn't told where this phone is. The switch is on that radar's page, under Paired radars."
            : "\(count) paired radars aren't told where this phone is. The switch is on each radar's page, under Paired radars."
    }
}
