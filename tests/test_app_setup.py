#!/usr/bin/env python3
"""
Checks for setting up a new radar from the app (roadmap 2.18) on the radar's
side: the first-run QR link, joining the home WiFi from the setup network,
and offering a pairing code whose secret only the phone holds.

And on the app's side (security review 2026-11-03, SR-06; 2026-11-15): a
setup link opened from outside the app must name the radar's certificate,
the flow then speaks only https to that certificate, the question before it
says the phone will pair, and the phone's position goes to the radar only
from a switch on the name screen that starts off. These read the app's
Swift; where swiftc is installed the link rules are compiled and run.

Later the same day, after review: a certificate that is named but not
written as one makes the link no link, from outside and in the app's scanner;
a code scanned in the app with no certificate is asked about before anything
is sent; the radar's host name from its hello is one DNS label or is dropped,
and only a home-network address is asked or kept; the question before an
outside link says the app can't tell whose radar it is; and the last screen
says when the radar got no location, and carries the switch for telling that
radar where the phone is.

Run: python3 tests/test_app_setup.py
"""
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", "deploy", file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ss = load("setup_server", "setup-server.py")
tmp = tempfile.mkdtemp()
ss.STATE_DIR = tmp
ss.STATE_FILE = os.path.join(tmp, "setup.json")

# ---- the first-run QR link -------------------------------------------------------------
HS = {"active": True, "ssid": "StratoScan-Setup", "psk": "pw&k=x 1", "address": "10.42.0.1"}
link = ss.setup_link("ABC-123", HS)
q = parse_qs(urlparse(link).query)
check("a setup link is a stratoscan://setup link", link.startswith("stratoscan://setup?"))
check("it carries the claim code and the setup network",
      q.get("c") == ["ABC-123"] and q.get("w") == ["StratoScan-Setup"] and q.get("a") == ["10.42.0.1"])
check("the network password survives & = and spaces as one value", q.get("k") == ["pw&k=x 1"])
check("on the setup network it gives no LAN address", "h" not in q)
ss.lan_addresses = lambda: ["100.98.1.2", "192.168.1.23"]
q = parse_qs(urlparse(ss.setup_link("ABC-123", {"active": False})).query)
check("already on a network, it gives the home address (not Tailscale's)", q.get("h") == ["192.168.1.23"] and "w" not in q)
ss.lan_addresses = lambda: []
check("with neither, there is no link to show", ss.setup_link("ABC-123", {"active": False}) is None)
check("with no claim code (already claimed), no link", ss.setup_link(None, HS) is None)

# ---- joining the home WiFi from the setup network ----------------------------------------
calls = []
answers = {}


def fake_setupd(verb, params=None, timeout=None):
    calls.append((verb, params))
    a = answers.get(verb, {"ok": True, "result": {}})
    return a.pop(0) if isinstance(a, list) else a


ss.call_setupd = fake_setupd
H = hashlib.sha256(b"a phone's secret").hexdigest()
ss.save_state({"schema": 1, "claimed": True})
ss.join_in_background("Home", "hunter22", H, delay=0, sleep=lambda s: None)
verbs = [v for v, _ in calls]
check("it joins, confirms, then offers the phone's code, in that order",
      verbs == ["wifi_connect", "wifi_confirm", "pair_offer_hash"])
check("the WiFi password goes to setupd as given", calls[0][1] == {"ssid": "Home", "psk": "hunter22"})
check("the offer carries only the hash", calls[2][1] == {"hash": H})
st = ss.load_state()
check("and records the join as done", st["join"]["state"] == "ok" and st["steps"].get("wifi") is True)

# ---- the nearest airport becomes the home airport when none is set (2026-10-23) ----------
class FakeRequest:
    def __init__(self, body):
        self.body, self.sent = body, None

    def _body(self):
        return self.body

    def _send(self, code, obj=None, **k):
        self.sent = (code, obj)

    def _err(self, code, token, message):
        self.sent = (code, {"error": token})


real_nearest, real_actual = ss.nearest_airports, ss.actual_airport
ss.nearest_airports = lambda lat, lon, n=6: [{"code": "CLT", "distanceNm": 4.2}, {"code": "JQF", "distanceNm": 9.0}]
answers["set_location"] = {"ok": True, "result": {"lat": 35.2, "lon": -80.9}}
answers["set_airport"] = {"ok": True, "result": {"code": "CLT"}}
ss.actual_airport = lambda: None
calls.clear(); req = FakeRequest({"lat": 35.2, "lon": -80.9}); st = {"schema": 1}
ss.Handler._location(req, st)
check("a location with no home airport yet makes the nearest one it",
      ("set_airport", {"code": "CLT"}) in calls and req.sent[1]["airport"] == {"code": "CLT"}
      and st["steps"].get("airport") is True)
ss.actual_airport = lambda: {"code": "RDU"}
calls.clear(); req = FakeRequest({"lat": 35.2, "lon": -80.9}); st = {"schema": 1}
ss.Handler._location(req, st)
check("but never replaces one already chosen",
      not any(v == "set_airport" for v, _ in calls) and req.sent[1]["airport"] is None)
ss.nearest_airports, ss.actual_airport = real_nearest, real_actual

calls.clear()
answers["wifi_connect"] = {"ok": False, "code": "wifi_auth_failed"}
ss.join_in_background("Home", "wrong", H, delay=0, sleep=lambda s: None)
check("a failed join is not confirmed, and offers nothing", [v for v, _ in calls] == ["wifi_connect"])
st = ss.load_state()
check("and says why, for the phone to read after rejoining the setup network",
      st["join"] == {**st["join"], "state": "failed", "code": "wifi_auth_failed"})
answers.pop("wifi_connect")

calls.clear()
answers["pair_offer_hash"] = [{"ok": False, "code": "relay"}, {"ok": False, "code": "relay"}, {"ok": True}]
ss.join_in_background("Home", "hunter22", H, delay=0, sleep=lambda s: None)
check("the offer is retried while the relay is unreachable, then stops",
      [v for v, _ in calls].count("pair_offer_hash") == 3)
answers.pop("pair_offer_hash", None)

calls.clear()
answers["pair_offer_hash"] = {"ok": False, "code": "relay"}
ss.join_in_background("Home", "hunter22", H, delay=0, sleep=lambda s: None)
check("but not forever", [v for v, _ in calls].count("pair_offer_hash") == ss.JOIN_OFFER_TRIES)
answers.pop("pair_offer_hash")

calls.clear()
ss.join_in_background("Home", "hunter22", None, delay=0, sleep=lambda s: None)
check("with no code to offer, it only joins", [v for v, _ in calls] == ["wifi_connect", "wifi_confirm"])

# ---- the hash, at each layer ---------------------------------------------------------------
check("the server only takes a hex SHA-256", bool(ss.RE_SECRET_HASH.match(H)) and not ss.RE_SECRET_HASH.match(H.upper())
      and not ss.RE_SECRET_HASH.match(H[:-1]) and not ss.RE_SECRET_HASH.match("a phone's secret"))
os.environ["STRATOSCAN_PAIRING_RUN"] = tmp
pr = load("pairing", "pairing.py")
sent = []
pr._call = lambda method, path, body=None: (sent.append((method, path, body)) or {"ok": True, "expires": 123})
r = pr.offer_hash(H)
check("pairing.py offers the hash to the relay, and nothing else",
      sent == [("POST", "/v1/unit/pairing", {"secret_hash": H})] and r["offered"] is True)
try:
    pr.offer_hash("not a hash")
    refused = False
except ValueError:
    refused = True
check("and refuses anything that isn't one", refused)
check("no secret is written on the radar", not os.path.exists(os.path.join(tmp, "pairing-offer.json")))

# ---- no read route swallows a save to the same path ---------------------------------------
# /setup/api/locale and /setup/api/ota each had an any-method route ahead of
# their POST route, so the setup page's Save and Install buttons only ever read.
import re
src = open(os.path.join(HERE, "..", "deploy", "setup-server.py")).read()
any_method = set(re.findall(r'if path == "(/setup/api/[^"]+)":', src))
posted = set(re.findall(r'if path == "(/setup/api/[^"]+)" and self.command == "POST"', src))
check("no path has both an any-method route and a POST route", not (any_method & posted))

# ---- the app's side of a setup link (SR-06, 2026-11-15) -----------------------------------
IOS = os.path.join(HERE, "..", "ios", "StratoScan")


def swift(*parts):
    """A Swift file without its comments (a // after a colon is a URL)."""
    text = open(os.path.join(IOS, *parts)).read()
    return "\n".join(re.sub(r"(?<![:\"])//.*$", "", line) for line in text.splitlines())


def body(text, start):
    """From `start` to the end of its braces; empty when it isn't there."""
    i = text.find(start)
    if i < 0:
        return ""
    depth = 0
    for k in range(text.index("{", i), len(text)):
        depth += {"{": 1, "}": -1}.get(text[k], 0)
        if depth == 0:
            return text[i:k + 1]
    return text[i:]


rs = swift("Setup", "RadarSetup.swift")
rv = swift("Setup", "RadarSetupView.swift")
cv = swift("Views", "ContentView.swift")
app = swift("App", "StratoScanApp.swift")
sv = swift("Views", "SettingsView.swift")

handle = body(rs, "func handle(_ url: URL, pairing: PairingStore)")
check("a link opened from outside goes through handle()", "setup.handle(url, pairing: pairing)" in body(app, ".onOpenURL"))
check("which refuses one that names no certificate, before anything is kept or started",
      "guard Self.mayStartFromOutside(l) else" in handle
      and handle.index("mayStartFromOutside") < handle.index("pendingLink = l")
      and "start(" not in handle)
check("and says why, and how to do it properly", "pairing.message = Self.unpinnedRefusal" in handle
      and "certificate" in rs[rs.index("static let unpinnedRefusal"):][:400] and "Scan a radar's code" in rs)
scanned = body(rs, "func scanned(_ url: URL, pairing: PairingStore)")
check("the app's own scanner hands its code to scanned(), and starts nothing itself",
      "setup.scanned(url, pairing: pairing)" in sv and "setup.start(" not in sv + cv + app)
check("a scanned code naming a certificate starts directly (a code read off the radar's screen)",
      re.search(r"if l\.fingerprint == nil \{\s*unprotectedLink = l\s*\} else \{\s*start\(l, pairing: pairing\)\s*\}", scanned) is not None)
check("nothing else starts one", len(re.findall(r"\bstart\(l, pairing:", rs + sv + cv + app)) == 3
      and "start(l, pairing: p)" in body(rs, "func confirmPending()")
      and "start(l, pairing: p)" in body(rs, "func confirmUnprotected()"))

# a code scanned in the app with no certificate is asked about first (2026-11-15)
check("a scanned code naming no certificate waits for a yes, with nothing sent",
      len(re.findall(r"\bstart\(", scanned)) == 1 and "unprotectedLink = l" in scanned
      and "guard let l = unprotectedLink, let p = pairing else { return }" in body(rs, "func confirmUnprotected()"))
at = cv.find('.confirmationDialog("This radar has no certificate"')
ask = cv[at:at + 700] if at >= 0 else ""
check("the question has Continue and Cancel, and Cancel drops the link",
      'Button("Continue") { setup.confirmUnprotected() }' in ask
      and 'Button("Cancel", role: .cancel) { setup.unprotectedLink = nil }' in ask
      and "Text(RadarSetup.unprotectedQuestion(" in ask)
uq = body(rs, "nonisolated static func unprotectedQuestion(")
check("and says the WiFi password and setup details go unprotected, on its own setup network",
      "WiFi password and the setup details will be sent to it unprotected" in uq and "on its own setup network." in uq)

# a certificate named but not written as one (2026-11-15)
parse_src = body(rs, "nonisolated static func parse(")
check("a link whose certificate is not written as one is no link, not a link without one",
      "guard let named = certificate(v) else { return nil }" in parse_src and "isHexDigit" not in parse_src)
check("from outside it is refused in words, before anything is kept",
      "pairing.message = Self.badCertificateRefusal" in handle
      and handle.index("badCertificateRefusal") < handle.index("pendingLink = l"))
check("and in the app's scanner too, which takes such a code so it can say so",
      "if Self.namesBadCertificate(url) { pairing.message = Self.badCertificateRefusal }" in scanned
      and "RadarSetup.namesBadCertificate(url)" in swift("Pairing", "PairingScannerView.swift"))

link = body(rs, "struct Link:")
check("a link naming a certificate is spoken to over https only",
      'var base: String { "\\(fingerprint == nil ? "http" : "https")://' in link
      and 'private var scheme: String { link?.fingerprint == nil ? "http" : "https" }' in rs)
check("on a session that accepts that certificate and no other",
      "session = Self.session(pinnedTo: l.fingerprint)" in body(rs, "func start(")
      and "got == fingerprint ? (.useCredential, URLCredential(trust: trust)) : (.cancelAuthenticationChallenge, nil)" in rs)
calls = re.findall(r"(\w+)\.data\(for:", rs)
check("every call of the flow goes through that session: %s" % calls, calls == ["session", "session"] and "URLSession.shared" not in rs
      and "URLSession.radar" not in rs)
connect = body(rs, "private func connect()")
check("the radar's own word that it has no certificate changes nothing: tls is read only to refuse",
      len(re.findall(r"\.tls\b", rs)) == 1 and "if l.fingerprint == nil && first.tls == true" in connect)

details = body(rs, "private func sendDetails()")
check("after the claim the phone sends the time zone and region, and no position",
      '"locale"' in details and "oneLocation" not in details and '"location"' not in details and "await sendDetails()" in connect)
check("the position is asked of iOS, and sent, in one place",
      len(re.findall(r'"location"', rs)) == 1 and '"location"' in body(rs, "private func sendPhoneLocation(")
      and "sendPhoneLocation" not in connect)
check("only with the owner's switch on, from the name screen",
      "if usePhoneLocation {" in body(rs, "func saveName()")
      and body(rs, "func saveName()").index("if usePhoneLocation {") < body(rs, "func saveName()").index("await sendPhoneLocation(stillWanted:")
      and len(re.findall(r"sendPhoneLocation\(", rs)) == 2)
check("the switch starts off, for every setup",
      "@Published var usePhoneLocation = false" in rs and "usePhoneLocation = false" in body(rs, "func start(")
      and not re.search(r"usePhoneLocation = true", rs + rv))
name_step = body(rv, "private var nameStep")
check("and is on the name screen, in plain words",
      'Toggle("Use this phone\'s location", isOn: $setup.usePhoneLocation)' in name_step
      and "this phone's exact position is sent to the radar" in name_step
      and "nothing about where this phone is goes to the radar" in name_step)
check("the screen no longer says the location was set from the phone", "Its location, nearest airport" not in rv)

# whether a location reached the radar, and the last screen (2026-11-15)
spl = body(rs, "private func sendPhoneLocation(")
check("sending the position says whether the radar took it",
      "private func sendPhoneLocation(stillWanted: () -> Bool) async -> Bool" in rs and "else { return false }" in spl and "return true" in spl
      and "@Published private(set) var radarLocated = false" in rs and "radarLocated = false" in body(rs, "func start("))
one = body(rs, "private static func oneLocation(")
check("the time allowed for a position starts after iOS's question is answered",
      "let status = await PermissionWait().answer()" in one
      and one.index("PermissionWait().answer()") < one.index("Task.sleep(for: .seconds(timeout))")
      and "guard status == .authorizedWhenInUse || status == .authorizedAlways else { return nil }" in one
      and "requestWhenInUseAuthorization" not in one)
pw = body(rs, "private final class PermissionWait")
check("and the answer is waited for, however long it takes",
      "withCheckedContinuation" in pw and "manager.requestWhenInUseAuthorization()" in pw
      and "authorizationStatus != .notDetermined" in body(pw, "nonisolated func locationManagerDidChangeAuthorization(")
      and "Task.sleep" not in pw)
check("the name screen says it is getting the phone's location meanwhile",
      'detail = "Getting this phone\'s location…"' in spl and "setup.busy && !setup.detail.isEmpty" in name_step
      and "? setup.detail" in name_step)
done = body(rv, "private var doneStep")
check("the last screen says when the radar got no location, and where it is set",
      "if !setup.radarLocated" in done
      and "The radar has no location yet. Set it on the radar's own screen, under Settings." in body(done, "if !setup.radarLocated"))
check("and that this radar is not told where this phone is, with the switch right there",
      'Toggle("Share this phone\'s location with this radar"' in done and "get: { setup.sharingWithRadar }" in done
      and "set: { setup.sharePhoneLocation($0) }" in done and "This radar is not told where this phone is." in done)
check("the switch is the per-radar setting, and the screen shows what was saved",
      "store.setShareLocation(on, unit: u)" in body(rs, "func sharePhoneLocation(")
      and "sharingWithRadar = false" in body(rs, "func start(")
      and "sharingWithRadar = store.radars.first(where: { $0.unit == u })?.shareLocation != false" in body(rs, "private func pair()"))
check("neither is left to the pairing's own message, an alert under the setup screens",
      "pairing.message" not in rv and "PairingStore" not in rv and "pairing?.message = nil" in body(rs, "private func find()"))

# the radar's host name from its hello (2026-11-15)
find = body(rs, "private func find()")
check("the hello's host name is kept only as one DNS label",
      "hostname = Self.hostLabel(first.hostname)" in connect and "hostname = first.hostname" not in rs)
check("the radar is looked for only where homeCandidates allows",
      "let candidates = Self.homeCandidates(hostname: hostname, lan: link?.lan)" in find and ".local" not in find
      and "for host in candidates" in find)
check("and only such a host is kept as its address or the radar view's",
      find.index("for host in candidates") < find.index("pairing?.setHost(host") < find.index('APIConfig.baseURL = "http://\\(host)"')
      and len(re.findall(r"setHost\(", rs)) == 1 and len(re.findall(r"APIConfig\.baseURL = ", rs)) == 1)
check("with nowhere to look the radar is paired all the same",
      "candidates.isEmpty ? 0 : 60" in find and "step = .done" in find[find.index("guard !Task.isCancelled else { return }"):])

sm = body(cv, "private var setupMessage: String")
check("the question before an outside link says the link names the radar and the app can't tell whose it is",
      "The link names the radar; the app can't tell whose it is." in sm
      and "Continue only if you just scanned the code on your own new radar's screen." in sm)
refusal = rs[rs.index("static let unpinnedRefusal"):][:400].split("\n")[0]
check("and neither it nor the refusal says a certificate shows whose radar it is",
      "can't tell which radar" not in rs and "proves" not in sm + refusal and "your radar's certificate" not in sm + refusal)
check("the question before a setup says the phone will pair with the radar",
      "This phone will pair with that radar" in sm and "Text(setupMessage)" in cv)
check("and that the radar gets the phone's location only by choice", "only if you choose that" in sm)

swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc or platform.system() != "Darwin":
    print("skip the compiled link checks: no swiftc here (they run on the Mac that builds the app)")
else:
    # The link's rules on their own: RadarSetup itself needs UIKit.
    raw = open(os.path.join(IOS, "Setup", "RadarSetup.swift")).read()
    parts = [body(raw, s) for s in ("struct Link: Equatable", "nonisolated static func isPrivateHost(",
                                    "nonisolated static func parse(", "nonisolated static func mayStartFromOutside(",
                                    "nonisolated static func certificate(", "nonisolated static func namesBadCertificate(",
                                    "nonisolated static func hostLabel(", "nonisolated static func homeCandidates(")]
    check("the link's rules are there to compile", all(parts))
    FP = "ab" * 32
    work = tempfile.mkdtemp()
    with open(os.path.join(work, "main.swift"), "w") as f:
        f.write("import Foundation\nenum RadarSetup {\n" + "\n".join(parts).replace("nonisolated ", "") + "\n}\n" + """
func show(_ what: String, _ s: String) {
    guard let l = RadarSetup.parse(URL(string: s)!) else { return print(what, "nolink") }
    print(what, RadarSetup.mayStartFromOutside(l) ? "outside-ok" : "outside-refused", l.base)
}
let fp = CommandLine.arguments[1]
show("NET", "stratoscan://setup?c=ABC-123&w=StratoScan-Setup&k=password1&a=10.42.0.1")
show("NETPIN", "stratoscan://setup?c=ABC-123&w=StratoScan-Setup&k=password1&a=10.42.0.1&f=" + fp)
show("LAN", "stratoscan://setup?c=ABC-123&h=192.168.1.23")
show("LANPIN", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=" + fp)
show("SHORTPIN", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=abcd")
show("NOTHEX", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=" + String(repeating: "zz", count: 32))
show("INTERNET", "stratoscan://setup?c=ABC-123&h=relay.example.com&f=" + fp)
show("EMPTYPIN", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=")
show("WIDEPIN", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=" + String(repeating: "\\u{FF11}", count: 64))
func bad(_ what: String, _ s: String) { print(what, RadarSetup.namesBadCertificate(URL(string: s)!)) }
bad("BAD-SHORT", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=abcd")
bad("BAD-EMPTY", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=")
bad("BAD-NONE", "stratoscan://setup?c=ABC-123&h=192.168.1.23")
bad("BAD-GOOD", "stratoscan://setup?c=ABC-123&h=192.168.1.23&f=" + fp)
bad("BAD-PAIR", "stratoscan://pair?u=x&s=y&f=abcd")
func hosts(_ what: String, _ name: String?, _ lan: String? = nil) {
    let c = RadarSetup.homeCandidates(hostname: name, lan: lan)
    print(what, c.isEmpty ? "-" : c.joined(separator: ","))
}
hosts("H-GOOD", "stratoscan-rdu")
hosts("H-BOTH", "StratoScan2", "192.168.1.23")
hosts("H-LONG", String(repeating: "a", count: 63))
hosts("H-TOOLONG", String(repeating: "a", count: 64))
hosts("H-NONE", nil, "192.168.1.23")
hosts("H-DOTTED", "relay.example.com")
hosts("H-LOCAL", "stratoscan.local")
hosts("H-SLASH", "relay.example.com/x")
hosts("H-AT", "user@relay")
hosts("H-PORT", "relay:8080")
hosts("H-LEAD", "-radar")
hosts("H-TRAIL", "radar-")
hosts("H-EMPTY", "")
hosts("H-SPACE", "my radar")
hosts("H-NEWLINE", "radar\\n")
hosts("H-ACCENT", "caf\\u{E9}")
hosts("H-HASH", "radar#")
hosts("H-LANOUT", "relay.example.com", "relay.example.com")
hosts("H-LANPUBLIC", nil, "8.8.8.8")
""")
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    built = subprocess.run([swiftc, "-target", arch + "-apple-macos14", "-o", os.path.join(work, "link"),
                            os.path.join(work, "main.swift")], capture_output=True, text=True, timeout=300)
    check("the link's rules compile on their own" + ("" if built.returncode == 0 else ": " + built.stderr[-600:]),
          built.returncode == 0)
    if built.returncode == 0:
        ran = subprocess.run([os.path.join(work, "link"), FP], capture_output=True, text=True, timeout=60)
        out = {l.split()[0]: l.split()[1:] for l in ran.stdout.splitlines() if l.strip()}
        check("a setup-network link with no certificate is refused from outside: %s" % out.get("NET"),
              out.get("NET") == ["outside-refused", "http://10.42.0.1"])
        check("with one it may ask, and speaks https: %s" % out.get("NETPIN"), out.get("NETPIN") == ["outside-ok", "https://10.42.0.1"])
        check("a home-network link with no certificate is refused from outside: %s" % out.get("LAN"),
              out.get("LAN") == ["outside-refused", "http://192.168.1.23"])
        check("with one it may ask, and speaks https: %s" % out.get("LANPIN"), out.get("LANPIN") == ["outside-ok", "https://192.168.1.23"])
        check("a certificate hash of the wrong length makes it no link at all: %s" % out.get("SHORTPIN"),
              out.get("SHORTPIN") == ["nolink"])
        check("as does one that isn't hex: %s" % out.get("NOTHEX"), out.get("NOTHEX") == ["nolink"])
        check("or an empty one, or one in full-width digits: %s %s" % (out.get("EMPTYPIN"), out.get("WIDEPIN")),
              out.get("EMPTYPIN") == ["nolink"] and out.get("WIDEPIN") == ["nolink"])
        check("such a link is known for what it is, so the owner can be told",
              out.get("BAD-SHORT") == ["true"] and out.get("BAD-EMPTY") == ["true"])
        check("and one with no certificate, a good one, or a pairing link is not taken for it",
              out.get("BAD-NONE") == ["false"] and out.get("BAD-GOOD") == ["false"] and out.get("BAD-PAIR") == ["false"])
        check("a hello's one-label host name is looked for as <name>.local: %s" % out.get("H-GOOD"),
              out.get("H-GOOD") == ["stratoscan-rdu.local"])
        check("beside the link's own home address: %s" % out.get("H-BOTH"), out.get("H-BOTH") == ["StratoScan2.local,192.168.1.23"])
        check("up to 63 characters and no more: %s" % out.get("H-TOOLONG"),
              out.get("H-LONG") == ["a" * 63 + ".local"] and out.get("H-TOOLONG") == ["-"])
        check("with no host name, the link's home address alone: %s" % out.get("H-NONE"), out.get("H-NONE") == ["192.168.1.23"])
        for key in ("H-DOTTED", "H-LOCAL", "H-SLASH", "H-AT", "H-PORT", "H-LEAD", "H-TRAIL", "H-EMPTY", "H-SPACE",
                    "H-NEWLINE", "H-ACCENT", "H-HASH", "H-LANOUT", "H-LANPUBLIC"):
            check("a host name or address that isn't a home-network one is not looked for (%s): %s" % (key, out.get(key)),
                  out.get(key) == ["-"])
        check("and a certificate doesn't let a link name a host on the internet: %s" % out.get("INTERNET"),
              out.get("INTERNET") == ["nolink"])

cancelled = rs.split("func saveName() async {")[1].split("\n    }\n")[0] if "func saveName() async {" in rs else ""
check("a name step still waiting when its setup is cancelled does nothing more: no location sent, the next setup not moved on",
      "let mine = run" in cancelled and cancelled.count("guard mine == run else { return }") >= 3
      and "sendPhoneLocation(stillWanted:" in cancelled and "guard stillWanted() else { return false }" in rs
      and "func cancel() {\n        run += 1" in rs)
print(f"{checks - len(failures)}/{checks} app setup checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
