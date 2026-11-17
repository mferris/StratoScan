#!/usr/bin/env python3
"""The app's alert switches reach the relay (2026-11-17).

An owner turned "Allow Notifications" off in iOS Settings and still got a
banner for an approaching aircraft. The lock-screen countdown is a Live
Activity, which that switch doesn't cover; and with notifications off the
app has no push token, and without a token it told the relay nothing at
all, so no switch in the app could stop it either. A change that failed to
send was shown once and never tried again, and each flip of a switch went
as its own request, in no order.

Now there is one switch over all alerts; what the relay is asked to send is
nothing when that is off or iOS refuses notifications; every change goes
through one sender, with or without a token; a change the relay hasn't
taken is tried again and said so in Settings.

These read the app's Swift. The relay's side is tested in
relay/test/relay.test.js.

Run: python3 tests/test_app_alert_switches.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios" / "StratoScan"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def body(src, start):
    """The text of the declaration that begins with `start`, to its closing brace."""
    i = src.index(start)
    depth = 0
    for j in range(src.index("{", i), len(src)):
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        if depth == 0:
            return src[i:j + 1]
    raise ValueError(start)


push = (IOS / "Pairing" / "PushManager.swift").read_text()
client = (IOS / "Pairing" / "RelayClient.swift").read_text()
section = (IOS / "Views" / "AlertsSection.swift").read_text()
app = (IOS / "App" / "StratoScanApp.swift").read_text()
reporter = (IOS / "Location" / "ApproachReporter.swift").read_text()

# 1. the master switch
check('private static let alertsOnKey = "stratoscan.alertsOn"' in push
      and "alertsOn = UserDefaults.standard.object(forKey: Self.alertsOnKey) as? Bool ?? true" in push,
      "one switch over all alerts, kept across launches, on until it is turned off")
rows = section[section.index("Section {"):]
check(rows.index("Toggle(isOn: $push.alertsOn)") < rows.index("push.permission == .denied") < rows.index("Picker(")
      and 'Text("Alerts from my radar")' in section
      and 'Text("Off: nothing is sent to this phone, including the lock-screen countdown.")' in section,
      "it is the first row of the Alerts section, and says what off means")
check(section.count(".disabled(!push.alertsOn)") == 2 and ".disabled(!push.registered || push.effectiveKinds.isEmpty)" in section
      and "ForEach(PushManager.Kind.allCases)" in section and "if push.alertsOn" not in section,
      "off, the kinds and the place stay in view but can't be changed; the test button is off while nothing is sent")

# 2. what is actually sent
eff = body(push, "var effectiveKinds: [String]")
check("guard alertsOn, permission != .denied else { return [] }" in eff and '"near_radar"' in eff and '"near_me"' in eff
      and ".sorted()" in eff,
      "nothing is asked for with the switch off or notifications refused in iOS; else the kinds and the place")
check("var needsLocation: Bool { !effectiveKinds.isEmpty && (kinds.contains(.approach_me) || place != .radar) }" in push
      and "if ApproachReporter.shared.enabled != want { ApproachReporter.shared.setEnabled(want) }" in push
      and "enabled || PushManager.shared.needsLocation" not in reporter
      and "} else if enabled {\n            setEnabled(false)" in body(reporter, "func resumeIfEnabled()")
      and push.index("await PushManager.shared.refreshPermission()") < push.index("ApproachReporter.shared.resumeIfEnabled()"),
      "the phone's location is not sent while nothing is, at launch included")

# 3. one sender
check("sendRegistration" not in push and len(re.findall(r"Task \{ await relay", push)) == 0
      and all("effectiveChanged()" in body(push, "@Published var %s" % v) for v in ("place: Place", "alertsOn: Bool", "kinds: Set<Kind>")),
      "every switch goes through the one sender, not a task of its own")
sync = body(push, "func sync()")
check("if sending { changedWhileSending = true; return }" in sync and "} while changedWhileSending" in sync
      and "changedWhileSending = false\n                await attempt()" in sync,
      "one request at a time; a change during a send causes one more, with the latest state")
attempt = body(push, "private func attempt() async")
check("try await relay.register(token: token, environment: environment, kinds: sent," in attempt
      and "registered = try await relay.setKinds(sent)" in attempt
      and 'send("POST", "/v1/phone/kinds", ["kinds": kinds])' in client
      and "func setKinds(_ kinds: [String]) async throws -> Bool" in client,
      "with a push token the kinds go with the registration; without one, on their own")
check('private static let acceptedKey = "stratoscan.alertsAccepted"' in push and "if at == revision { accepted = want }" in attempt
      and 'effectiveKinds.joined(separator: ",") + (token != nil || allowed ? "|token" : "|kinds")' in push
      and "return want != accepted && want != refused" in body(push, "var pending: Bool"),
      "what the relay last took is remembered, and anything else is still to send")

check(attempt.index("if token == nil, allowed, !askedForToken { askForToken() }") < attempt.index("if token == nil, awaitingToken { return }")
      < attempt.index("let sent = effectiveKinds")
      and "askedForToken = true" in body(push, "private func askForToken()"),
      "a launch waits for Apple's token whichever opening comes first: one request, not the kinds and then the registration")

# 4. trying again
check("sync()" in body(push, "func enable() async") and ".task { if !pairing.radars.isEmpty { await push.enable() } }" in app,
      "a change the relay never took is sent at the next launch, when a radar is paired")
active = body(push, "func becameActive() async")
check(active.index("await refreshPermission()") < active.index("sync()")
      and "await PushManager.shared.becameActive()" in app[app.index("didBecomeActiveNotification"):],
      "coming back to the app checks iOS's permission first, then tells the relay")
retry = body(push, "private func scheduleRetry()")
check("private static let retryDelays: [UInt64] = [5, 15, 60]" in push and "guard pending || ApproachReporter.shared.withdrawalOwed else { failures = 0; return }" in retry
      and "retry?.cancel()" in retry and "min(failures, Self.retryDelays.count - 1)" in retry and "scheduleRetry()" in sync,
      "while it hasn't, the app tries again after 5 s, 15 s, 60 s and then every minute, and stops when it has")
check('where no.status == 403 && no.message == "pair with a radar first"' in attempt and "refused = want" in attempt
      and "guard !PairingStore.savedUnits().isEmpty else { return false }" in body(push, "var pending: Bool")
      and "refused = nil" in body(push, "func enable() async"),
      "no paired radar, here or at the relay, is neither a failure nor something to retry")

check('beginBackgroundTask(withName: "alert-choices")' in sync and "if sendTask == .invalid" in sync
      and "if retry == nil || failures > 1 { endSendTask() }" in sync
      and "UIApplication.shared.endBackgroundTask(sendTask)" in body(push, "private func endSendTask()"),
      "a send, and its first try again, get time to finish after the app leaves the screen")
woken = body(push, "for await activity in Activity<ApproachAttributes>.activityUpdates")
check(woken.index("await refreshPermission()") < woken.index("if !wantsCountdown { endApproachActivities() }") < woken.index("sync()"),
      "woken by a countdown, the app looks at iOS's permission, takes an unwanted countdown down and tells the relay")
report = body(reporter, "private func report(_ l: CLLocation) async")
check(report.index("await PushManager.shared.refreshPermission()") < report.index("PushManager.shared.sync()") < report.index("guard enabled,"),
      "woken by a move, the same, before any location is sent")
on = body(reporter, "func setEnabled(_ on: Bool)")
queue = body(reporter, "private func queueWithdrawal()")
check(on.index("lastSent = .distantPast") < on.index("begin()") and "oweWithdrawal()" in on
      and queue.index("await before?.value") < queue.index("guard withdrawalOwed, !enabled else { return }") < queue.index("await withdraw()")
      and report.index("await withdrawing?.value") < report.index("guard enabled else { return }") < report.index("relay.units()"),
      "off and back on sends the location again at once, after the withdrawal has gone")

# 4b. a withdrawal that didn't arrive is owed until it does
owe = body(reporter, "private func oweWithdrawal()")
check('private static let owedKey = "stratoscan.withdrawalOwed"' in reporter
      and "UserDefaults.standard.set(newValue, forKey: Self.owedKey)" in reporter
      and owe.index("withdrawalOwed = true") < owe.index("queueWithdrawal()")
      and "try? await relay.location(unit: u.unit, blob: nil)" not in reporter,
      "turning the location off notes a withdrawal as owed, across launches, before trying it")
wd = body(reporter, "private func withdraw() async -> Bool")
check("return PairingStore.savedUnits().isEmpty" in wd[wd.index("units = try await relay.units()"):wd.index("var gone = true")]
      and "} catch let no as RelayClient.Failure where no.status == 403 {" in wd
      and "} catch {\n                gone = false" in wd and wd.rstrip().endswith("return gone\n    }")
      and "if gone, wanted == withdrawalsWanted, !enabled { withdrawalOwed = false }" in queue
      and reporter.count("withdrawalOwed = false") == 3,
      "it is settled only when the relay listed the radars and every one gave the location up, or none is paired")
check(wd.index('beginBackgroundTask(withName: "approach-withdraw")') < wd.index("defer { endWithdrawTask() }") < wd.index("relay.units()")
      and "self?.endWithdrawTask()" in wd
      and "UIApplication.shared.endBackgroundTask(withdrawTask)" in body(reporter, "private func endWithdrawTask()"),
      "a withdrawal gets time to finish after the app leaves the screen, and always hands it back")
again = body(reporter, "func retryWithdrawal()")
resume = body(reporter, "func resumeIfEnabled()")
check("guard withdrawalOwed, !enabled, withdrawalsQueued == 0 else { return }" in again
      and active.index("await refreshPermission()") < active.index("ApproachReporter.shared.retryWithdrawal()") < active.index("guard !PairingStore")
      and "} else {" in resume and "retryWithdrawal()" in resume
      and retry.index("ApproachReporter.shared.retryWithdrawal()") < retry.index("sync()"),
      "an owed withdrawal is tried again when the app comes forward, at launch, and with the relay's own tries")
check(on.index("withdrawalOwed = false") < on.index("begin()")
      and resume.index("withdrawalOwed = false") < resume.index("begin()")
      and "if !enabled { oweWithdrawal() }" in report[report.index("try? await relay.location(unit: unit, blob: blob)"):],
      "back on, nothing is owed before the fresh report starts; a report overtaken by the switch going off is withdrawn again")
check(report.index("repeat {\n            wanted = withdrawalsWanted\n") < report.index("await withdrawing?.value")
      and report.rstrip().endswith("} while enabled && wanted != withdrawalsWanted\n    }"),
      "off and back on while a report is on its way: that report goes again, behind the withdrawal the off began")
still = body(push, "func withdrawalStillOwed()")
check(queue.index("await withdraw()") < queue.index("if withdrawalOwed, !enabled { PushManager.shared.withdrawalStillOwed() }")
      and "if retry == nil, !sending { scheduleRetry() }" in still,
      "a withdrawal that fails with no send to the relay after it still sets the tries going")

# 5. what Settings says
check('Label("Not saved to the StratoScan service yet. Trying again.", systemImage: "exclamationmark.arrow.circlepath")' in section and "if push.syncFailed {" in section
      and "if let why = push.syncError" in section and section.count("onDisappear") == 1
      and ".onDisappear { push.message = nil }" in section and "syncFailed = false" not in section,
      "a change that didn't arrive is said so, with why, until it does; leaving Settings doesn't clear it")
denied = section[section.index("if push.permission == .denied"):]
check(denied.index("Text(push.pending") < denied.index('? "Notifications are off for StratoScan in iOS. Telling the StratoScan service to send this phone nothing…"')
      < denied.index(': "Notifications are off for StratoScan in iOS, so nothing is sent to this phone.")')
      < denied.index("The switch above stops everything at once.")
      < denied.index('Button("Turn on notifications in iOS Settings")')
      and "objectWillChange.send()" in body(push, "private var accepted: String?"),
      "notifications refused in iOS: Settings says nothing is sent only once the relay has been told, and that the app's own switch is the sure one")
check(len(re.findall(r"\bmessage = ", push)) == 2 and all("message = " in l for l in body(push, "func sendTest() async").splitlines()
                                                         if "localizedDescription" in l or "Sent." in l),
      "the test button's line is only the test's result")
saved = section[section.index("if push.syncFailed {"):section.index("if push.needsLocation && !reporter.strangers.isEmpty")]
check(".foregroundColor(.orange)" not in saved and ".font(.callout).foregroundColor(.secondary)" in saved,
      "the not-saved line is readable: secondary text with a symbol, not orange")
check(section.count('.accessibilityHint(push.alertsOn ? "" : Self.offHint)') == 2
      and 'static let offHint = "Turn on Alerts from my radar first"' in section
      and all(section.index(".disabled(!push.alertsOn)", i) < section.index(".accessibilityHint(", i)
              for i in (section.index("Picker("), section.index("ForEach(PushManager.Kind.allCases)"))),
      "switched off by the master switch, the place and each kind tell VoiceOver what to turn on first")

# 6. the countdown
check("if !wantsCountdown { endApproachActivities() }" in push
      and "sent.contains(Kind.approach.rawValue) || sent.contains(Kind.approach_me.rawValue)" in push
      and "await activity.end(nil, dismissalPolicy: .immediate)" in body(push, "private func endApproachActivities()"),
      "with no countdown wanted, one already on the lock screen comes down at once")

# 7. an older relay
check("var status = 0" in client and "status: status)" in client
      and "syncError = (error as? RelayClient.Failure)?.status == 404 ? nil : error.localizedDescription" in attempt
      and "syncFailed = true" in attempt,
      "a relay without the route (404) is a failure that is retried, shown without a raw error")

print("app alert-switch checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
