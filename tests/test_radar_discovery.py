#!/usr/bin/env python3
"""The app finds its radar on the home network after an address change (#76).

On 2026-10-23 the router had given RDU a new address after its card was
rebuilt, and the app sat on the old one, "out of reach", until the owner
retyped it. Now every radar advertises _stratoscan._tcp through avahi, and when
the home address doesn't answer and the phone is on a local network, the app
browses for that service, asks each radar's LAN-only hello for its unit id, and
keeps the one it is paired with.

Run: python3 tests/test_radar_discovery.py
"""
import importlib.util
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


# ---- the radar advertises itself, and nothing secret ---------------------------
svc_path = ROOT / "deploy" / "avahi-stratoscan.service"
svc = ET.parse(svc_path).getroot()
types = [s.findtext("type") for s in svc.iter("service")]
ports = [s.findtext("port") for s in svc.iter("service")]
check(types == ["_stratoscan._tcp"] and ports == ["80"], "the radar advertises _stratoscan._tcp on port 80")
check(not list(svc.iter("txt-record")), "with no TXT record: nothing secret, and the hello says who it is")
inst = (ROOT / "deploy" / "install-setup-server.sh").read_text()
check("install -m 0644 deploy/avahi-stratoscan.service /etc/avahi/services/stratoscan.service" in inst,
      "the installer puts the service file in avahi's services folder")

# ---- the hello the app asks carries the unit id -------------------------------
srv = (ROOT / "deploy" / "setup-server.py").read_text()
hello = srv[srv.index('if path == "/setup/api/hello"'):][:2500]
check('"unit": unit_id()' in hello, "the LAN-only hello reports the radar's unit id")
check("secret" not in hello.split('"unit": unit_id()')[0].lower().split("return self._send")[-1],
      "and no pairing secret")

# ---- the app browses for it, checks the unit, and keeps the address -----------
finder = (ROOT / "ios" / "StratoScan" / "Pairing" / "RadarFinder.swift").read_text()
check('.bonjour(type: "_stratoscan._tcp"' in finder, "the app browses for _stratoscan._tcp")
check("/setup/api/hello" in finder and "units.contains(unit)" in finder,
      "and keeps only a radar whose hello names a paired unit")
check("pairing.setHost(host, unit: unit)" in finder, "recording the address on the paired radar")
check("ip.version = .v4" in finder, "IPv4 only (a link-local IPv6 address needs a scope id no URL can carry)")

api = (ROOT / "ios" / "Shared" / "APIConfig.swift").read_text()
resolve = api[api.index("func resolve("):api.index("private func set(")]
# 2026-10-25: home and the public address are asked at once; one after the
# other, away from home the app waited 1.5 s on home and up to 4 s on the
# finder before asking the public address, which answers in a third of a second.
ask_home, ask_away = resolve.index("async let homeAnswers = Self.answers(home"), resolve.index("async let awayAnswers")
check(max(ask_home, ask_away) < resolve.index("if await homeAnswers"),
      "Endpoint asks home and the public address at once")
check(resolve.index("if await homeAnswers") < resolve.index("await awayAnswers"),
      "and home wins whenever it answers")
away_branch = resolve[resolve.index("if let away, await awayAnswers"):resolve.index("if let look, let found = await found(by: look")]
check("Task { if await self.found(by: look, home: home) != nil { self.invalidate() } }" in away_branch,
      "when only the public address answers, the finder runs behind it, not in front")
check(resolve.index("if let away, await awayAnswers") < resolve.index("if let look, let found = await found(by: look"),
      "and runs in front only when the public address doesn't answer either")
check("Task { await self.learnAway(from: home) }" in resolve, "learning the public address at home no longer holds up the first look")
check("onLocalNetwork || !pathKnown" in resolve and "findEvery" in resolve,
      "the finder runs only on a local network (or before the network is known, just after launch), at most every couple of minutes")
check("APIConfig.baseURL = found" in resolve, "a radar it finds becomes the home address")
m = re.search(r"static let findEvery: TimeInterval = (\d+)", api)
check(m is not None and 60 <= int(m.group(1)) <= 300, "it looks again after no less than a minute and no more than five")

app = (ROOT / "ios" / "StratoScan" / "App" / "StratoScanApp.swift").read_text()
check("_ = Endpoint.shared" in app[app.index("init()"):app.index("var body")],
      "the network watch starts at launch, so the first look-up knows whether the phone is on WiFi")
check("Endpoint.shared.finder = { await RadarFinder.find(pairing: pairing) }" in app,
      "the app (not the widget or the Watch) sets the finder")

yml = (ROOT / "ios" / "project.yml").read_text()
plist = (ROOT / "ios" / "StratoScan" / "App" / "Info.plist").read_text()
check("NSBonjourServices: [_stratoscan._tcp]" in yml
      and re.search(r"<key>NSBonjourServices</key>\s*<array>\s*<string>_stratoscan\._tcp</string>", plist),
      "iOS is told which service the app browses for (NSBonjourServices), in project.yml and the generated plist")
check("NSLocalNetworkUsageDescription" in yml, "and why it uses the local network")

print("radar discovery checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
