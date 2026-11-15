#!/usr/bin/env python3
"""The app without a radar, and what it says a radar adds (2026-11-15).

The app works with no radar paired: the aircraft around the phone, from the
public adsb.lol network (roadmap 2.13). Five things were wrong with it there:

- Sky view opened on an empty sky: the network's aircraft were only asked for
  "away from the radar", and with no radar there was nothing to be away from;
- the header said "FINDING YOU..." until the centre-on-me button was tapped,
  with the map already on the phone;
- with location refused, the view sat at 0 N 0 E with no word of why, and the
  network was asked for the aircraft there;
- the demo's logbook was hidden behind the "kept by your radar" explanation;
- the one invitation ("No StratoScan radar yet?") only showed with the public
  network switched off, which it isn't unless its owner turns it off.

And nothing said what a radar adds: alerts were a section missing from
Settings, the widgets said "Radar not reachable" to someone with no radar.
Now one screen says it (RadarInvite), reached from the radar screen, Settings
and the logbook; the radar screen names whose aircraft it is showing; and a
widget tells "no radar yet" from "your radar can't be reached".

These read the app's Swift.

Run: python3 tests/test_app_no_radar.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def code(path):
    """The Swift without its comments."""
    return "\n".join(re.sub(r"(?<![:\"])//.*$", "", line) for line in (IOS / path).read_text().splitlines())


content = code("StratoScan/Views/ContentView.swift")
model = code("StratoScan/ViewModels/RadarViewModel.swift")
sky = code("StratoScan/Views/SkyView.swift")
logbook = code("StratoScan/Views/LogbookView.swift")
settings = code("StratoScan/Views/SettingsView.swift")
invite = code("StratoScan/Views/RadarInviteView.swift")
widget = code("StratoScanWidget/StratoScanWidget.swift")
config = code("Shared/APIConfig.swift")

# ---- the five ---------------------------------------------------------------------------
away = sky.split("private var isAway: Bool {")[1].split("\n    }")[0]
check("if viewModel.isDemo { return false }" in away and "!viewModel.hasRadar ||" in away,
      "Sky view asks for the aircraft around the phone when there is no radar (and not in the demo)")
check('if viewModel.hasRadar { return "Aimed from the radar." }' in sky and '"Location is off for StratoScan."' in sky,
      "and doesn't say it is aimed from a radar that isn't there")

where = content.split("private var locationText: String {")[1].split("\n    }\n")[0]
no_radar = where.split("if !viewModel.hasRadar && !viewModel.isDemo {")[1].split("\n        }\n")[0]
check('if viewModel.me != nil { return "AROUND YOU · " + rangeText }' in no_radar
      and "if let moved = viewModel.panCentre { return place(moved) }" in no_radar,
      "without a radar the header says AROUND YOU once the phone is found, or where the map was moved to")
check('location.denied ? "LOCATION IS OFF FOR STRATOSCAN IN SETTINGS" : "FINDING YOU…"' in no_radar,
      "and FINDING YOU only while it is being found")

check("var hasViewCentre: Bool { panCentre != nil || radarPlace != nil || me != nil }" in model
      and "private var radarPlace: Coordinate? { (hasRadar || isDemo) ? home : nil }" in model
      and "return panCentre ?? radarPlace ?? me ?? Coordinate(lat: 0, lon: 0)" in model,
      "a radar unpaired a moment ago doesn't leave the view on its place, called 'around you'")
check("&& hasViewCentre &&" in model
      and re.search(r"private var wantsViewNetwork: Bool \{[^\n]*&& hasViewCentre &&", model) is not None,
      "the network isn't asked about 0 N 0 E while the view has nowhere to be")
foot = content.split("private func footer(_ geo: GeometryProxy) -> some View {")[1]
first = foot.split("} else if viewModel.connecting {")[0]
check("viewModel.networkOn && !viewModel.hasViewCentre && (!viewModel.hasRadar ||" in first and "location.denied" in first
      and "LOCATION IS OFF FOR STRATOSCAN" in first and "openSettingsURLString" in first and "viewModel.setDemo(true)" in first,
      "location refused, with no radar: the screen says so, with the way to Settings and the demo")

check("LogbookView(noRadar: !viewModel.hasRadar && !viewModel.isDemo" in content
      and ".task(id: noRadar) { if !noRadar { await load() } }" in logbook,
      "the demo's logbook shows without a radar, and loads when the demo is turned on from it")

# ---- the invitation ---------------------------------------------------------------------
wants = content.split("private var wantsInvite: Bool {")[1].split("\n    }")[0]
check(all(s in wants for s in ("!viewModel.hasRadar", "!viewModel.isDemo", "!inviteDismissed", "!inWallMode",
                               "viewModel.networkOn", "viewModel.hasViewCentre")),
      "the radar screen invites only someone with no radar, on the live sky, who hasn't put it away")
check('@AppStorage("stratoscan.inviteDismissed")' in content and "inviteDismissed = true" in content
      and "if wantsInvite { invitePill }" in content and "RadarInviteSheet(viewModel: viewModel" in content,
      "it can be put away for good, and opens what a radar adds")
check(len(re.findall(r'^\s+\("[a-z0-9.]+", "[^"]+",\s*$', invite, re.M)) >= 5
      and all(w in invite for w in ("Alerts", "A logbook", "Your own antenna, live")),
      "one screen lists what a radar adds: its own antenna, alerts, the logbook and more")
check("RadarInvite.buildURL" in logbook and 'Link(destination: Self.buildURL)' in invite and "viewModel.setDemo(true)" in invite
      and "if let pair {" in invite,
      "with the ways on from it: build one, pair one, or try the demo")
check(not re.search(r"\$\s?\d|\bprice|\bbuy\b|\bcost|\bpurchase|\bsubscri", invite, re.I),
      "and no prices or selling in it: this repository is public")
none_paired = settings.split("if !pairing.radars.isEmpty {")[1].split("ThemeSection()")[0]
check("AlertsSection()" in none_paired and 'Text("Alerts")' in none_paired and "RadarInvite(viewModel: viewModel" in none_paired,
      "Settings says what alerts need when no radar is paired, instead of leaving them out")
check('Button("Try the demo, with a sample logbook") { tryDemo() }' in logbook, "the logbook's explanation offers the demo, and says that is what it is")
check(".sheet(isPresented: $showSettings, onDismiss: syncHasRadar)" in content and "if phase == .active { syncHasRadar();" in content,
      "an address typed or cleared in Settings counts at once, not at the next launch")
privacy = (ROOT / "docs" / "privacy.md").read_text()
check("**Sky view away from home, or with no radar**" in privacy and "or no radar is set up" in privacy,
      "the privacy page says Sky view asks for the aircraft around the phone with no radar too")

# ---- the labels -------------------------------------------------------------------------
check('"PUBLIC NETWORK · AROUND YOU"' in foot and '"PUBLIC NETWORK"' in foot and "DATA © ADSB.LOL (ODbL)" in foot,
      "without a radar the screen says its aircraft are the public network's, with adsb.lol's credit")
check("} else if viewModel.source == .radar && !inWallMode {" in foot and '"YOUR RADAR · LIVE"' in foot,
      "with one, at home, it says they are the radar's own")

# ---- the widgets ------------------------------------------------------------------------
check('shared.object(forKey: hasRadarKey) as? Bool ?? true' in config and "APIConfig.hasRadar = viewModel.hasRadar" in content
      and "WidgetCenter.shared.reloadAllTimelines()" in content,
      "the app tells the widgets whether a radar is set up (taken as yes until it has said)")
check(widget.count("No radar yet") == 3 and widget.count("Radar not reachable") == 3
      and "hasRadar: APIConfig.hasRadar || DemoFeed.isOn" in widget,
      "and a widget says 'No radar yet', not 'Radar not reachable', to someone with none")

# ---- the rest of the review (2026-11-15) ------------------------------------------------
watch = code("StratoScanWatch/WatchRadarView.swift")
watch_app = code("StratoScanWatch/StratoScanWatchApp.swift")
complication = code("StratoScanWatchWidget/StratoScanWatchWidget.swift")
sync = code("StratoScan/Watch/WatchSync.swift")
store = code("StratoScan/Pairing/PairingStore.swift")
feed = code("Shared/Aircraft.swift")
check('"hasRadar": APIConfig.hasRadar' in sync and 'if let has = c["hasRadar"] as? Bool { APIConfig.hasRadar = has }' in watch_app
      and "WatchSync.shared.push()" in content.split("private func syncHasRadar()")[1].split("\n    }\n")[0],
      "the Watch is told whether a radar is set up, when that changes")
check("No radar yet." in watch and "Can't reach the radar." in watch and "receiver.hasRadar || DemoFeed.isOn" in watch
      and "@Published var hasRadar = APIConfig.hasRadar" in watch_app and ".onChange(of: receiver.radarChanges)" in watch
      and "WidgetCenter.shared.reloadAllTimelines()" in watch_app,
      "and its app says 'No radar yet', not that it can't reach one")
check(re.search(r'\} else if entry\.nearby != nil \{\s*Text\("Nothing nearby"\)', complication) is not None
      and '"No radar in reach"' in complication and "APIConfig.hasRadar" not in complication,
      "its complication says 'Nothing nearby' only of a sky it has heard from")
check('(entry.hasRadar ? "STRATOSCAN" : "NO RADAR YET")' in widget, "and the StandBy radar says so too")

gone = store.split("func unpair(_ radar: Radar) async {")[1].split("\n    }\n")[0]
check('let wasRead = radar.host.map { APIConfig.baseURL == "http://\\($0)" } ?? false' in gone
      and 'radars.compactMap(\\.host).first.map { "http://\\($0)" } ?? APIConfig.defaultBaseURL' in gone
      and "if wasRead || (radars.isEmpty && APIConfig.baseURL == APIConfig.defaultBaseURL) {" in gone and "APIConfig.awayURL = nil" in gone,
      "unpairing a radar takes its addresses out of the radar view (an address typed for another stays)")

check("var networkPaused: Bool { networkPauseOwner != nil }" in model and "if networkPaused {" in model
      and "viewModel.networkPauseOwner = mine" in sky
      and "defer { if viewModel.networkPauseOwner == mine { viewModel.networkPauseOwner = nil } }" in sky
      and sky.count("viewModel.networkPauseOwner = nil") >= 3 and "if !networkPaused, now.timeIntervalSince(viewNetworkFetchedAt)" in model,
      "while Sky view asks the network for the aircraft around the phone, the radar screen under it doesn't ask too")
check("networkPaused ? nearMe[hex] ?? viewNetwork[hex] : viewNetwork[hex] ?? nearMe[hex]" in model,
      "and an aircraft's details then come from Sky view's fresh copy")

check("var heardAt: Double? = nil" in feed and "feed.now! - feed.heardAt!" in model
      and "var receiverReporting: Bool { (receiverLag ?? 0) < Self.receiverQuietS }" in model,
      "the app knows how far behind the radar's answer its receiver is (a radar that doesn't say counts as live)")
check('viewModel.receiverReporting ? "YOUR RADAR · LIVE" : "YOUR RADAR · ITS RECEIVER HAS STOPPED REPORTING"' in foot,
      "and says LIVE only while the receiver is writing its list")
core = (ROOT / "deploy" / "core-feed.py").read_text()
check(".onChange(of: pairing.radars.count) { _, _ in" in settings and "baseURL = APIConfig.baseURL" in settings,
      "Settings takes the addresses an unpair changed, and doesn't write the old ones back on closing")
check("func radarChanged() {" in model and "viewModel.radarChanged()" in content and "let origin = radarPlace ?? me ?? centre" in model,
      "another radar's addresses, or none, drop the last radar's place, runways and aircraft")
check('"heardAt": heard_at,' in core and 'heard = data.get("now")' in core and "self._heard_at = round(_now(), 1)" in core,
      "the radar's feed carries when its receiver last wrote its list")

print("app no-radar checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
