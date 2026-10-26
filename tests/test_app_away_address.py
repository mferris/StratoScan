#!/usr/bin/env python3
"""The app's away address comes only from a radar it paired, and is never
swapped by its word alone (security review, 2026-10-26).

At home the app asks the radar for its public (away) address, from the setup
server's LAN-only hello, so an already-paired phone learns it with no typing.
The home address is plain http and the hello is not signed, so whatever
answers there was taken for the radar, and its address replaced the one in
use. Now:

- only a hello naming a radar paired here counts; the widget and the Watch,
  which don't have the list, don't learn it (they get it from the phone);
- it fills in an away address only where there is none; a different one is
  offered in Settings › Radar view, and used only once the owner takes it;
- the Bonjour finder takes only home-network addresses, as a setup link's.

The first part reads the app's Swift. Where swiftc is installed the second
compiles the shared address code and runs it against a local stand-in radar,
so nothing here asks a real radar.

Run: python3 tests/test_app_away_address.py
"""
import base64
import http.server
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def code(text):
    """The Swift without its comments (a // after a colon is a URL)."""
    return "\n".join(re.sub(r"(?<![:\"])//.*$", "", line) for line in text.splitlines())


def body(text, start):
    """From `start` to the end of its braces; empty when it isn't there."""
    i = text.find(start)
    if i < 0:
        return ""
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        depth += {"{": 1, "}": -1}.get(text[k], 0)
        if depth == 0:
            return text[i:k + 1]
    return text[i:]


def before(text, a, b):
    """`a` comes before `b` in `text`, and both are there."""
    return a in text and b in text and text.index(a) < text.index(b)


SWIFT = {p.relative_to(ROOT).as_posix(): code(p.read_text()) for p in sorted(IOS.rglob("*.swift"))
         if ".xcodeproj" not in p.parts and "build" not in p.parts}
api = SWIFT["ios/Shared/APIConfig.swift"]

# ---- the away address learned at home ------------------------------------------------
la = body(api, "private func learnAway(")
check("let unit = hello.unit, paired.contains(unit)" in la, "the public address is learned only from a hello naming a radar paired here")
check(before(la, "lock.withLock({ pairedHook })?(), !paired.isEmpty", "URLSession.radar.data("),
      "and without the app's list (the widget, the Watch) the radar isn't asked at all")
fill = body(la, "if APIConfig.awayURL == nil")
check('APIConfig.shared.set(pub, forKey: "radome.awayURL")' in fill and la.count('forKey: "radome.awayURL"') == 1,
      "it fills in an away address only where there is none")
check("APIConfig.awayOffered = pub == APIConfig.awayURL ? nil : pub" in la, "a different one is offered, not swapped in")
setters = sorted(f for f, s in SWIFT.items() if "pairedUnits = " in s)
check(setters == ["ios/StratoScan/App/StratoScanApp.swift"]
      and "Endpoint.shared.pairedUnits = { PairingStore.savedUnits() }" in SWIFT["ios/StratoScan/App/StratoScanApp.swift"],
      "the app gives the list; the widget and the Watch don't")
sv = SWIFT["ios/StratoScan/Views/SettingsView.swift"]
check("if let offered = APIConfig.awayOffered, awayURL != offered" in sv and "awayURL = offered" in sv,
      "Settings offers the radar's new public address, taken only with a tap")
check("if newValue != nil, newValue == awayOffered { awayOffered = nil }" in body(api, "static var awayURL"),
      "and once taken, it is no longer offered")
find = body(SWIFT["ios/StratoScan/Pairing/RadarFinder.swift"], "static func find(")
check("where RadarSetup.isPrivateHost(host)" in find, "the Bonjour finder takes only home-network addresses")

# ---- compiled, against a stand-in radar ------------------------------------------------
swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc or platform.system() != "Darwin":
    print("skip the compiled checks: no swiftc here (they run on the Mac that builds the app)")
else:
    def unit_id():
        return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()

    PAIRED, STRANGER = unit_id(), unit_id()
    # 127.0.0.1:9 refuses at once: the look-up's try of the away address
    # never leaves this Mac.
    A, B = "https://127.0.0.1:9/a", "https://127.0.0.1:9/b"
    HELLOS = {"widget": {"unit": PAIRED, "publicUrl": A}, "stranger": {"unit": STRANGER, "publicUrl": A},
              "first": {"unit": PAIRED, "publicUrl": A}, "changed": {"unit": PAIRED, "publicUrl": B},
              "same": {"unit": PAIRED, "publicUrl": B}}
    state = {"mode": None}
    hellos = {}

    class Radar(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code_, obj):
            body_ = json.dumps(obj).encode()
            self.send_response(code_)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_)))
            self.end_headers()
            self.wfile.write(body_)

        def do_GET(self):
            if self.path == "/tar1090/data/receiver.json":
                self.send(200, {"lat": 35.8776, "lon": -78.7875})
            elif self.path == "/setup/api/hello":
                hellos[state["mode"]] = hellos.get(state["mode"], 0) + 1
                self.send(200, {"product": "StratoScan", **HELLOS[state["mode"]]})
            elif self.path.startswith("/as/"):
                state["mode"] = self.path[4:]
                self.send(200, {})
            else:
                self.send(404, {})

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Radar)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    radar_url = "http://127.0.0.1:%d" % server.server_address[1]

    work = pathlib.Path(tempfile.mkdtemp())
    (work / "main.swift").write_text("""import Foundation
let a = CommandLine.arguments
func mode(_ m: String) async {
    _ = try? await URLSession.radar.data(for: URLRequest(url: URL(string: a[1] + "/as/" + m)!, timeoutInterval: 2))
}
func look(_ what: String) async {
    Endpoint.shared.invalidate()
    _ = await Endpoint.shared.resolve()
    try? await Task.sleep(for: .seconds(1.5))       // learnAway runs behind the look-up
    print(what, APIConfig.awayURL ?? "nil", APIConfig.awayOffered ?? "nil")
}
APIConfig.awayURL = nil
APIConfig.awayOffered = nil
APIConfig.baseURL = a[1]
await mode("widget"); await look("WIDGET")
Endpoint.shared.pairedUnits = { [CommandLine.arguments[2]] }
await mode("stranger"); await look("STRANGER")
await mode("first"); await look("FIRST")
await mode("changed"); await look("CHANGED")
APIConfig.awayURL = APIConfig.awayOffered
print("TAKEN", APIConfig.awayURL ?? "nil", APIConfig.awayOffered ?? "nil")
await mode("same"); await look("SAME")
""")
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    built = subprocess.run([swiftc, "-target", arch + "-apple-macos14", "-o", str(work / "away"),
                            str(IOS / "Shared" / "APIConfig.swift"), str(work / "main.swift")],
                           capture_output=True, text=True, timeout=300)
    check(built.returncode == 0, "the shared address code compiles on its own" + ("" if built.returncode == 0 else ": " + built.stderr[-600:]))
    if built.returncode == 0:
        home = work / "home"
        home.mkdir()
        # its settings in a home of its own, not this Mac's
        env = {"CFFIXED_USER_HOME": str(home), "HOME": str(home), "PATH": "/usr/bin:/bin"}
        ran = subprocess.run([str(work / "away"), radar_url, PAIRED], capture_output=True, text=True, timeout=120, env=env)
        out = {l.split()[0]: l.split()[1:] for l in ran.stdout.splitlines() if l.strip()}
        check(out.get("WIDGET") == ["nil", "nil"] and hellos.get("widget", 0) == 0,
              "without the app's list, nothing is learned and the radar isn't asked: %s, %d hellos" % (out.get("WIDGET"), hellos.get("widget", 0)))
        check(out.get("STRANGER") == ["nil", "nil"] and hellos.get("stranger", 0) >= 1,
              "a hello naming a radar not paired here is asked, and not believed: %s" % out.get("STRANGER"))
        check(out.get("FIRST") == [A, "nil"], "a paired radar's public address fills in an empty away address: %s" % out.get("FIRST"))
        check(out.get("CHANGED") == [A, B], "a different one later is only offered; the away address stays: %s" % out.get("CHANGED"))
        check(out.get("TAKEN") == [B, "nil"], "taken in Settings, it is used and no longer offered: %s" % out.get("TAKEN"))
        check(out.get("SAME") == [B, "nil"], "and the radar giving the one in use offers nothing: %s" % out.get("SAME"))
        if ran.returncode != 0:
            check(False, "the stand-in run ended badly: " + ran.stderr[-400:])
    server.shutdown()

print("app away address checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
