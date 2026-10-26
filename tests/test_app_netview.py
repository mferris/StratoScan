#!/usr/bin/env python3
"""The app's network view near home comes through the radar (#88, 2026-10-26).

Zoomed or panned past the ring, the app asked the relay's shared cache for
the network's aircraft (#68), then adsb.lol directly, even when the view was
round the radar itself, which already keeps those discs for its own screen
and asks adsb.lol once for everyone who looks (/network/around, which the
kiosk uses and the public address passes read-only).

Now a view whose middle is within 100 nm of the radar, and narrow enough for
one disc, is asked of the radar first while its polling answers: the middle
rounded to 0.05 degrees and the half-size in whole nm, on the radar's capped
session with a 5 s limit, at whichever of its addresses is in use. Whatever
it has is drawn, partial or still filling in; refused, late, not its answer,
too old, or nothing yet, and that round goes to the relay, then adsb.lol, as
before. A view far from home, a radar that isn't answering, the demo, and
Sky view's aircraft round the phone are as they were. The phone's position
never goes to the radar: a view centred on the phone is not asked of it.

The first part reads the app's Swift. Where swiftc is installed the second
compiles the network code and runs it against a local stand-in radar, with a
stand-in for the relay, so nothing here asks the real relay or adsb.lol.

Run: python3 tests/test_app_netview.py
"""
import http.server
import json
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

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
feed = SWIFT["ios/Shared/NetworkFeed.swift"]
vm = SWIFT["ios/StratoScan/ViewModels/RadarViewModel.swift"]
sky = SWIFT["ios/StratoScan/Views/SkyView.swift"]

# ---- the radar first, only near home ------------------------------------------------
fv = body(feed, "static func fetchView(")
check("radar: Coordinate?" in fv.split("{")[0], "the network view is told the radar's place, or none")
check(before(fv, "nearRadar(centre, halfNm: halfNm, radar: radar)", "fromRadar(around: centre, halfNm: halfNm)")
      and before(fv, "fromRadar(around:", "self.discs(around: centre, halfNm: halfNm)"),
      "a view near the radar is asked of it before the relay and adsb.lol")
check("return got" in fv.split("self.discs(around:")[0], "and what it answers is the view's: nothing else is asked that round")
near = body(feed, "static func nearRadar(")
m = re.search(r"static let radarNearNm = ([\d.]+)", feed)
check(m is not None and float(m.group(1)) <= 100, "near is the view's middle within 100 nm of the radar")
check("halfNm <= singleUpToNm" in near and "<= radarNearNm" in near, "and a view narrow enough for one disc (190 nm)")

fr = body(feed, "static func fromRadar(")
check("let at = rounded(centre)" in fr and '"/network/around?lat=%.2f&lon=%.2f&half=%d", at.lat, at.lon' in fr,
      "the radar gets the view's middle rounded to 0.05°, never finer")
check("centre.lat" not in fr.split("URLRequest(")[0].replace("rounded(centre)", ""),
      "and nothing but the rounded middle goes into the question")
check("Int(halfNm.rounded())" in fr, "and the half-size in whole nm")
m = re.search(r"static let radarSeconds: TimeInterval = ([\d.]+)", feed)
check("URLSession.radar.data(for: req)" in fr and "timeoutInterval: radarSeconds" in fr
      and m is not None and float(m.group(1)) <= 6, "on the radar's capped session, with a short limit (5 s)")
check("APIConfig.url(path)" in fr and "Endpoint.shared.resolve()" not in fr,
      "at the address the radar's polling is using, home or away, with no look-up of its own")
check("AircraftFeedClient.appHeader" in fr, "marked as the owner's app, as every question to the radar is")
check("statusCode == 200" in fr and "names.isEmpty && (answer.pending ?? 0) > 0" in fr,
      "a refusal, or nothing yet with more on its way, is no answer")
check("radarKeepSeconds" in fr, "nor is an answer the radar has kept too long")
check("decode(data, within: (at, discs(around: centre, halfNm: halfNm).coveredNm)" in fr,
      "kept to the disc the phone would have asked for, as the relay's answer is")
check("Extra(hex: $0.hex, r: $0.reg, t: $0.type)" in fr, "with the registration and type the radar names its own way")

# ---- the relay, then adsb.lol, as before ---------------------------------------------
fe = body(feed, "static func fetch(around")
check(before(fe, "fromRelay(at: at, radius: radius)", "api.adsb.lol") and "fromRadar" not in fe,
      "a disc is still the relay's, then adsb.lol's, and never the radar's")
check("for (i, d) in discs.enumerated()" in fv and "viewBudgetSeconds" in fv, "a wide view is still its discs, in its budget")

# ---- only the view, only while the radar answers ---------------------------------------
callers = [f for f, s in SWIFT.items() if "fromRadar(around:" in s and f != "ios/Shared/NetworkFeed.swift"]
check(not callers and feed.count("fromRadar(around:") == 1 and "fromRadar(around:" in fv,
      "the radar is asked from the network view alone")
asks = [f for f, s in SWIFT.items() if "/network/around" in s]
check(asks == ["ios/Shared/NetworkFeed.swift"], "nothing else asks the radar for the network: %s" % asks)
views = [f for f, s in SWIFT.items() if "NetworkFeed.fetchView(" in s]
check(views == ["ios/StratoScan/ViewModels/RadarViewModel.swift"], "the radar view is the one network view: %s" % views)
check("NetworkFeed.fetch(around: me)" in sky and "fetchView" not in sky and "fromRadar" not in sky,
      "Sky view's aircraft round the phone still come from the relay and adsb.lol")
pv = body(vm, "private func pollNetworkAroundView()")
check("let radar = radarForView" in pv and "NetworkFeed.fetchView(around: centre, halfNm: rangeNm, radar: radar)" in pv,
      "the radar view hands it the radar, when it may be asked")
rf = body(vm, "private var radarForView")
check("connected" in rf and "Date().timeIntervalSince(lastGoodFetch) < staleInterval" in rf,
      "only while the radar's polling answers")
check("!DemoFeed.isOn" in rf and "hasRadar" in rf, "never in the demo, nor with no radar")
check("!(centreOnMe && me != nil)" in rf, "never for a view on the phone: its position doesn't go to the radar")
check("return home" in rf, "and it is the radar's own place the view is measured from")
poll = body(vm, "private func pollOnce()") + body(vm, "private func pollRadar()") + body(vm, "    func start()")
check("fromRadar" not in poll and "fetchView" not in poll, "nothing new on the way to the radar's own aircraft")
m = re.search(r"let networkInterval: TimeInterval = (\d+)", vm)
check(m is not None and int(m.group(1)) == 5, "the view's network is asked every 5 s, as before")

privacy = (ROOT / "docs" / "privacy.md").read_text()
flat = " ".join(privacy.split())
check("asks your radar for the network's aircraft in that view" in flat and "rounded to 0.05°" in flat,
      "the privacy policy says a view near the radar is asked of it, with its middle rounded")
check("Your phone's position never goes to the radar" in flat, "and that the phone's position never goes to it")

# ---- compiled, against a stand-in radar ----------------------------------------------
RDU = (35.8776, -78.7875)
# a view panned 20 nm east of the radar; its middle, rounded, is (35.90, -78.40)
NEAR = (35.8812, -78.3987)
# a view 280 nm north-east, at the middle of one of the relay's lattice discs
FAR = (40.6, -76.6)


def ghost(hexid, lat, lon, **kw):
    """An aircraft as network-compare.py's ghost_entry() sends it."""
    a = {"hex": hexid, "flight": None, "lat": lat, "lon": lon, "alt": 12000, "gs": 300.0, "track": 90.0,
         "seen_pos": 1.2, "type": None, "reg": None, "squawk": None, "vrate": 0, "emergency": None, "category": "A3"}
    a.update(kw)
    return a


IN_VIEW = [ghost("a00001", 35.95, -78.35, flight="DAL123 ", type="A321", reg="N123DL"),
           ghost("a00002", 35.85, -78.45, alt="ground")]
OUT_OF_VIEW = [ghost("a00003", 37.9, -76.0)]       # well past the 39 nm the phone would have asked for

swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc or platform.system() != "Darwin":
    print("skip the compiled checks: no swiftc here (they run on the Mac that builds the app)")
else:
    mode = {"now": "normal"}
    asked = []          # (mode, query, app header) for every /network/around

    def answer(m):
        """The stand-in's answer in each mode: (status, body, seconds to wait first)."""
        whole = {"centre": {"lat": 35.9, "lon": -78.4}, "covered": 39, "discs": 1, "answered": 1, "pending": 0,
                 "partial": False, "source": "adsb.lol", "via": "relay", "at": time.time(), "fetched": 0.0}
        if m == "normal":
            return 200, dict(whole, ac=IN_VIEW + OUT_OF_VIEW), 0
        if m == "pending":      # the last answer for that place, a fresher one on its way
            return 200, {"ac": IN_VIEW[:1], "centre": {"lat": 35.9, "lon": -78.4}, "radius": 39, "source": "adsb.lol",
                         "at": time.time() - 6, "fetched": 6.0, "stale": True, "pending": 1}, 0
        if m == "partial":      # some of a lattice view's discs, the rest still coming
            return 200, dict(whole, ac=IN_VIEW, discs=2, answered=1, pending=1, partial=True), 0
        if m == "clear":        # an empty sky, settled: that is an answer
            return 200, dict(whole, ac=[]), 0
        if m == "nothingyet":   # nothing yet, and more on its way
            return 200, {"ac": [], "centre": {"lat": 35.9, "lon": -78.4}, "radius": 39, "source": "adsb.lol",
                         "at": time.time(), "fetched": None, "pending": 1}, 0
        if m == "old":          # a place's answer kept from long ago
            return 200, dict(whole, ac=IN_VIEW, fetched=900.0, stale=True), 0
        if m == "refused":
            return 503, {"error": "upstream unavailable", "detail": "URLError"}, 0
        if m == "toosoon":
            return 429, {"error": "asked too often; try again in a few seconds"}, 0
        if m == "notjson":
            return 200, "<html>a captive portal</html>", 0
        if m == "late":         # past the app's 5 s
            return 200, dict(whole, ac=IN_VIEW), 8
        return 404, {"error": "not found"}, 0

    class Radar(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path.startswith("/as/"):
                mode["now"] = path[4:]
                self.send_response(204)
                self.end_headers()
                return
            if path != "/network/around":
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            m = mode["now"]
            asked.append((m, query, self.headers.get("X-StratoScan-App")))
            status, out, wait = answer(m)
            time.sleep(wait)
            raw = out.encode() if isinstance(out, str) else json.dumps(out).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except OSError:
                pass        # the app gave up first

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Radar)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    radar_url = "http://127.0.0.1:%d" % server.server_address[1]

    work = pathlib.Path(tempfile.mkdtemp())
    (work / "main.swift").write_text("""import Foundation
let a = CommandLine.arguments
APIConfig.awayURL = nil
APIConfig.baseURL = a[1]
let rdu = Coordinate(lat: %(rdu_lat)r, lon: %(rdu_lon)r)
let near = Coordinate(lat: %(near_lat)r, lon: %(near_lon)r)
let far = Coordinate(lat: %(far_lat)r, lon: %(far_lon)r)

/// The relay, standing in: one aircraft at the view's middle, so a view that
/// fell back is told apart, and adsb.lol is never asked.
final class Count: @unchecked Sendable {
    private let lock = NSLock()
    private var n = 0
    func add() { lock.withLock { n += 1 } }
    var value: Int { lock.withLock { n } }
}
let relayAsked = Count()
NetworkFeed.relay = { _, at, _ in
    relayAsked.add()
    return Data(#"{"ac": [{"hex": "b00001", "lat": \\#(at.lat), "lon": \\#(at.lon), "alt_baro": 9000, "r": "N9RL", "t": "C172"}]}"#.utf8)
}
/// A fall-back the relay holds: one disc of the lattice holds the view, so
/// the stand-in answers and adsb.lol is never asked.
func safe(_ c: Coordinate, _ half: Double) -> Bool {
    let at = NetworkFeed.rounded(c)
    return NetLattice.holding(at.lat, at.lon, wantNm: NetworkFeed.discs(around: c, halfNm: half).coveredNm.rounded()) != nil
}
func look(_ name: String, around c: Coordinate, half: Double, radar: Coordinate?) async {
    guard safe(c, half) else { print("UNSAFE", name); return }
    _ = try? await URLSession.radar.data(for: URLRequest(url: URL(string: a[1] + "/as/" + name)!, timeoutInterval: 2))
    let relayBefore = relayAsked.value
    let t = Date()
    let list = await NetworkFeed.fetchView(around: c, halfNm: half, radar: radar)
    let items = (list ?? []).map { "\\($0.0.hex):\\($0.1?.r ?? "-"):\\($0.1?.t ?? "-")" }.sorted().joined(separator: ",")
    print("VIEW", name, list == nil ? "nil" : (items.isEmpty ? "empty" : items), relayAsked.value - relayBefore,
          String(format: "%%.1f", Date().timeIntervalSince(t)))
}
for m in ["normal", "pending", "partial", "clear", "nothingyet", "old", "refused", "toosoon", "notjson", "late"] {
    await look(m, around: near, half: 29.6, radar: rdu)
}
await look("far", around: far, half: 29.6, radar: rdu)
await look("unreachable", around: near, half: 29.6, radar: nil)
func isNear(_ c: Coordinate, _ half: Double) -> String { NetworkFeed.nearRadar(c, halfNm: half, radar: rdu) ? "yes" : "no" }
print("NEAR", isNear(near, 30), isNear(near, 190), isNear(near, 191), isNear(Coordinate(lat: rdu.lat + 1.62, lon: rdu.lon), 30),
      isNear(Coordinate(lat: rdu.lat + 1.71, lon: rdu.lon), 30), isNear(far, 30))
""" % {"rdu_lat": RDU[0], "rdu_lon": RDU[1], "near_lat": NEAR[0], "near_lon": NEAR[1], "far_lat": FAR[0], "far_lon": FAR[1]})
    srcs = [str(IOS / "Shared" / n) for n in ["APIConfig.swift", "Aircraft.swift", "AircraftFeedClient.swift", "DemoFeed.swift",
                                              "Geo.swift", "NetLattice.swift", "NetworkFeed.swift"]]
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    built = subprocess.run([swiftc, "-target", arch + "-apple-macos14", "-o", str(work / "netview"), *srcs, str(work / "main.swift")],
                           capture_output=True, text=True, timeout=300)
    check(built.returncode == 0, "the network code compiles with the radar asked first" + ("" if built.returncode == 0 else ": " + built.stderr[-600:]))
    if built.returncode == 0:
        home = work / "home"
        home.mkdir()
        # its settings in a home of its own, not this Mac's
        env = {"CFFIXED_USER_HOME": str(home), "HOME": str(home), "PATH": "/usr/bin:/bin"}
        ran = subprocess.run([str(work / "netview"), radar_url], capture_output=True, text=True, timeout=180, env=env)
        lines = ran.stdout.splitlines()
        check(not [l for l in lines if l.startswith("UNSAFE")], "every fall-back is the stand-in relay's, never adsb.lol")
        got = {l.split()[1]: l.split()[2:] for l in lines if l.startswith("VIEW ")}
        hits = lambda m: [q for (mm, q, _) in asked if mm == m]
        RADAR = "a00001:N123DL:A321,a00002:-:-"
        RELAY = "b00001:N9RL:C172"

        def view(m):
            v = got.get(m, ["?", "?", "99"])
            return v[0], int(v[1]) if v[1].isdigit() else -1, float(v[2])

        aircraft, relay, secs = view("normal")
        check(aircraft == RADAR, "a view near home is drawn from the radar's answer, with its names: %s" % aircraft)
        check("a00003" not in aircraft, "only what is within the disc the phone would have asked for")
        check(relay == 0, "and the relay and adsb.lol are not asked that round (%d)" % relay)
        q = urllib.parse.parse_qs(hits("normal")[0]) if hits("normal") else {}
        check(hits("normal") == ["lat=35.90&lon=-78.40&half=30"],
              "the radar is asked once, for the middle rounded to 0.05° and the half-size in whole nm: %s" % hits("normal"))
        check(len(q) == 3 and all(re.fullmatch(r"-?\d+\.\d{2}", v[0]) and abs(float(v[0]) * 20 - round(float(v[0]) * 20)) < 1e-6
                                  for k, v in q.items() if k in ("lat", "lon")), "never more precise than that")
        check(all(h == "1" for (_, _, h) in asked), "every question says it is the owner's app")
        check(view("pending")[:2] == ("a00001:N123DL:A321", 0), "an answer with more on its way is drawn: %s" % got.get("pending"))
        check(view("partial")[:2] == (RADAR, 0), "and so is part of a view, the rest still coming: %s" % got.get("partial"))
        check(view("clear")[:2] == ("empty", 0), "an empty sky, settled, is an answer: %s" % got.get("clear"))
        for m, what in [("nothingyet", "nothing yet with more on its way"), ("refused", "a 503"), ("toosoon", "a 429"),
                        ("notjson", "an answer that isn't JSON"), ("old", "an answer kept for a quarter of an hour")]:
            aircraft, relay, secs = view(m)
            check(aircraft == RELAY and relay == 1 and len(hits(m)) == 1,
                  "%s falls back to the relay that round (%s, relay asked %d)" % (what, aircraft, relay))
        aircraft, relay, secs = view("late")
        check(aircraft == RELAY and relay == 1, "a radar that doesn't answer in time falls back too (%s)" % aircraft)
        check(4.5 <= secs <= 7.0, "within its 5 s limit, not the session's 12 (%.1f s)" % secs)
        check(view("far")[:2] == (RELAY, 1) and not hits("far"), "a view far from home never asks the radar: %s" % got.get("far"))
        check(view("unreachable")[:2] == (RELAY, 1) and not hits("unreachable"),
              "nor does any view while the radar isn't answering: %s" % got.get("unreachable"))
        nr = next((l.split()[1:] for l in lines if l.startswith("NEAR ")), None)
        check(nr == ["yes", "yes", "no", "yes", "no", "no"],
              "near home: within 100 nm of the radar, and no wider than 190 nm each way (%s)" % nr)
        if ran.returncode != 0:
            check(False, "the stand-in run ended badly: " + ran.stderr[-400:])
    server.shutdown()
    shutil.rmtree(work, ignore_errors=True)

print("app network-view checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
