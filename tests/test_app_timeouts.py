#!/usr/bin/env python3
"""Nothing in the app waits without a time limit (#86), and its runway
outlines come from the radar (#87) (2026-10-26).

The owner asked that nothing wait without a time limit, for the free map or
anything else. In the app a URLRequest's timeoutInterval is only how long a
request may go quiet: on URLSession.shared a server that keeps trickling holds
it for up to 7 days. And several waits a person sees were longer than they
needed to be:

- the network's aircraft (up to nine adsb.lol discs, minutes when it was
  silent) were fetched inside the radar's polling, so the radar's own
  aircraft stood still meanwhile;
- the app read the radar's position again before its first look at the
  aircraft, even with a copy in hand, and "connecting" lasted as long as the
  slowest look-up, since its 8 s grace was only checked when a fetch came back;
- receiver.json failing did not drop the chosen address, so the Watch stayed
  on a dead home address;
- an alert waited on two icon services for its airline's mark;
- the widgets had no limit in all, and a cancelled setup went on for minutes.

Now every request goes through URLSession.radar (12 s in all) or
URLSession.bounded (30 s), or the setup's own session (75 s), each request
with its own quiet limit too, and those waits are fixed. The radar keeps the
runway outlines (/api/runways), and the app asks it before Overpass.

The first part reads the app's Swift, so a new request without a limit fails
here. Where swiftc is installed the second compiles the shared networking code
and runs it against a local stand-in radar.

Run: python3 tests/test_app_timeouts.py
"""
import http.server
import json
import pathlib
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

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
check(len(SWIFT) > 40, "the app's Swift is all read (%d files)" % len(SWIFT))

# ---- every request has a limit -------------------------------------------------
shared = [f for f, s in SWIFT.items() if "URLSession.shared" in s]
check(not shared, "nothing uses URLSession.shared, which gives a trickling request 7 days" + (": " + ", ".join(shared) if shared else ""))
from_url = [f for f, s in SWIFT.items() if ".data(from:" in s]
check(not from_url, "no data(from:), which can't carry a time limit" + (": " + ", ".join(from_url) if from_url else ""))
async_image = [f for f, s in SWIFT.items() if "AsyncImage(" in s]
check(not async_image, "no AsyncImage, which has no time limit of its own" + (": " + ", ".join(async_image) if async_image else ""))

ALLOWED = {"URLSession.radar", "URLSession.bounded"}
odd = []
for f, s in SWIFT.items():
    for m in re.finditer(r"([\w.]+)\.data\(for:", s):
        who = m.group(1)
        if who in ALLOWED or (f.endswith("Setup/RadarSetup.swift") and who == "session"):
            continue
        odd.append("%s (%s)" % (f, who))
check(not odd, "every request goes through a session with a limit in all" + (": " + ", ".join(odd) if odd else ""))

no_limit = []
for f, s in SWIFT.items():
    for m in re.finditer(r"URLRequest\(", s):
        # the constructor's own arguments
        depth, k = 0, m.end() - 1
        for k in range(m.end() - 1, len(s)):
            depth += {"(": 1, ")": -1}.get(s[k], 0)
            if depth == 0:
                break
        if "timeoutInterval:" in s[m.start():k]:
            continue
        name = re.search(r"var (\w+)\s*=\s*$", s[max(0, m.start() - 40):m.start()])
        after = s[k:k + 1500]
        if name and re.search(r"\b%s\.timeoutInterval = " % re.escape(name.group(1)), after):
            continue
        no_limit.append("%s:%d" % (f, s[:m.start()].count("\n") + 1))
check(not no_limit, "every URLRequest says how long it may go quiet" + (": " + ", ".join(no_limit) if no_limit else ""))

made = [f for f, s in SWIFT.items() if "URLSession(configuration:" in s]
check(sorted(made) == ["ios/Shared/APIConfig.swift", "ios/StratoScan/Setup/RadarSetup.swift"],
      "sessions are made in two places only: " + ", ".join(made))
api = SWIFT["ios/Shared/APIConfig.swift"]
radar = re.search(r"static let radar = capped\(at: (\d+)\)", api)
bounded = re.search(r"static let bounded = capped\(at: (\d+)\)", api)
check(radar is not None and int(radar.group(1)) <= 15,
      "URLSession.radar gives up within 15 s in all (the gateway allows the radar 10)")
check(bounded is not None and int(bounded.group(1)) <= 30, "URLSession.bounded within 30 s in all")
check("c.timeoutIntervalForResource = seconds" in body(api, "private static func capped("), "both by their resource limit")
setup = SWIFT["ios/StratoScan/Setup/RadarSetup.swift"]
m = re.search(r"c\.timeoutIntervalForResource = (\d+)", body(setup, "private static func session(pinnedTo"))
check(m is not None and int(m.group(1)) <= 90, "the setup's sessions give up in the end too (75 s)")

mapbg = SWIFT["ios/StratoScan/Views/MapBackgroundView.swift"]
limits = body(mapbg, "private static let mapRequestLimits")
check("c.timeoutIntervalForResource = 30" in limits and "MLNNetworkConfiguration.sharedManager.sessionConfiguration = c" in limits,
      "MapLibre's own requests (the free map's tiles, the weather) give up within 30 s")
make = body(mapbg, "func makeUIView(")
check(before(make, "_ = Self.mapRequestLimits", "MLNMapView("), "set before the first map is made")

# ---- nothing a person waits on waits on a third party --------------------------
vm = SWIFT["ios/StratoScan/ViewModels/RadarViewModel.swift"]
poll = body(vm, "private func pollOnce()")
check("await pollNetworkAroundView()" not in poll and "await self.pollNetworkAroundView()" not in poll.split("networkTask = Task")[0],
      "the radar's polling never waits for the network's aircraft")
check("networkTask = Task" in poll and "if networkTask == nil" in poll, "they come in a task of their own, one at a time")
start = body(vm, "    func start()")
check("if self.home == nil { await self.loadHome() } else { Task { await self.loadHome() } }" in start,
      "with the radar's position kept, the first look doesn't wait to read it again")
resume = body(vm, "    func resume()")
check("try? await Task.sleep(for: .seconds(grace))" in resume and "self.connecting = false" in resume,
      "\"connecting\" ends when its grace is up, not when the slowest fetch comes back")
m = re.search(r"private let connectGrace: TimeInterval = (\d+)", vm)
check(m is not None and int(m.group(1)) <= 10, "a grace of 10 s at most")

feed = SWIFT["ios/Shared/NetworkFeed.swift"]
fv = body(feed, "static func fetchView(")
m = re.search(r"static let viewBudgetSeconds = ([\d.]+)", feed)
check(m is not None and float(m.group(1)) <= 30, "a wide view gets 30 s at most in all")
check("if Date() >= deadline" in fv and "Date().addingTimeInterval(retrySeconds) < deadline" in fv,
      "no disc is asked, nor tried again, once it is up")

client = SWIFT["ios/Shared/AircraftFeedClient.swift"]
rec = body(client, "static func fetchReceiver()")
check(rec.count("Endpoint.shared.invalidate()") >= 2, "receiver.json failing drops the chosen address, as the feed does")
check("keepHome(c)" in rec, "the radar's position is kept as read")
check("guard let home = try await AircraftFeedClient.home()" in body(client, "static func load() async throws"),
      "a widget uses the kept position, not a look-up every time")
home_fn = body(client, "static func home()")
check("86400" in home_fn and "return try await fetchReceiver()" in home_fn, "read again once a day")
end = body(api, "func resolve(")
check("if let t = inFlight { return t }" in end, "one look-up for the address at a time, shared by whoever asks")

for f in ["ios/StratoScanWidget/StratoScanWidget.swift", "ios/StratoScanWatchWidget/StratoScanWatchWidget.swift"]:
    s = SWIFT[f]
    check("Nearby.load(within: Nearby.widgetSeconds)" in s and "Nearby.load()" not in s,
          "%s finishes inside WidgetKit's time" % f.split("/")[1])
m = re.search(r"static let widgetSeconds: TimeInterval = (\d+)", client)
check(m is not None and int(m.group(1)) <= 15, "a widget's look is given 15 s at most")
check("home = try await AircraftFeedClient.home()" in SWIFT["ios/StratoScanWatch/WatchRadarView.swift"],
      "the Watch glance uses the kept position too")

ns = SWIFT["ios/StratoScanNotificationService/NotificationService.swift"]
m = re.search(r"static let logoWaitSeconds: Double = ([\d.]+)", ns)
check(m is not None and float(m.group(1)) <= 5, "an alert waits 5 s at most for its airline's mark")
check("defer { handler = nil }" in body(ns, "private func deliver(") and "contentHandler(" not in body(ns, "Task {"),
      "and is handed back once only")

check("work?.cancel()" in body(setup, "    func cancel()"), "Cancel stops the setup's work")
for fn in ["private func pair()", "private func find()", "private func waitForHello("]:
    check("!Task.isCancelled" in body(setup, fn), "a cancelled setup stops in %s" % fn.split("(")[0].split()[-1])
m = re.search(r'timeoutInterval: path == "wifi/scan" \? (\d+) : (\d+)\)', body(setup, "private func apiRaw("))
check(m is not None and int(m.group(1)) <= 60 and int(m.group(2)) <= 30, "a setup step waits 30 s at most, a WiFi scan 60")
check("beginBackgroundTask" in SWIFT["ios/StratoScan/Location/ApproachReporter.swift"],
      "the approach report asks iOS for the time it needs, and no more")
types = SWIFT["ios/StratoScan/Networking/AircraftTypeClient.swift"]
disc = body(types, "private func discoverDatabaseFolder()")
check(before(disc, "Endpoint.shared.resolve()", "Self.get("), "the type database is asked where the radar answers")
routes = SWIFT["ios/StratoScan/Networking/RouteLookupClient.swift"]
check("req.timeoutInterval = 10" in body(routes, "private func flush()"), "a route asked of adsb.im directly has a limit")

# ---- the runway outlines from the radar (#87) ------------------------------------
rc = SWIFT["ios/StratoScan/Networking/RunwayClient.swift"]
fetch = body(rc, "static func fetchRunwayGeoJSON(")
check(before(fetch, "fromRadar(", "fromOverpass("), "the radar's copy is asked for before Overpass")
check("guard cachedRunwayGeoJSON(center: center, rangeNm: rangeNm) == nil" in fetch,
      "Overpass only when the radar can't answer and the phone has no copy")
fr = body(rc, "private static func fromRadar(")
check('APIConfig.url("/api/runways")' in fr and "Endpoint.shared.resolve()" in fr,
      "through whichever of the radar's addresses answers")
m = re.search(r'URLRequest\(url: APIConfig.url\("/api/runways"\), timeoutInterval: (\d+)\)', fr)
check(m is not None and int(m.group(1)) <= 5 and "URLSession.radar.data(for: req)" in fr, "with a short limit")
check("abs(c[0] - centre.lat) <= 0.05" in fr and "abs(c[1] - centre.lon) <= 0.05" in fr and "let centre = rounded(center)" in fr,
      "taken when its centre is the radar's position rounded to 0.05°, give or take a step")
check('doc["type"] as? String == "FeatureCollection"' in fr and "!features.isEmpty" in fr, "and only a set of runways")
check("geojson.write(to: url, options: .atomic)" in fr, "kept on the phone for its month, as Overpass's answer was")
lr = body(vm, "private func loadRunways()")
check(before(lr, "runwaysTask = Task", "RunwayClient.fetchRunwayGeoJSON"), "and nothing waits for it")

# ---- compiled, against a stand-in radar --------------------------------------------
swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc or platform.system() != "Darwin":
    print("skip the compiled checks: no swiftc here (they run on the Mac that builds the app)")
else:
    hits = {"receiver": 0, "runways": 0}
    # the radar's runways for RDU, its centre as offline-map.py writes it
    runways = {"centre": [35.9, -78.8]}
    RUNWAY = {"type": "Feature", "properties": {"aeroway": "runway", "ref": "5L/23R"},
              "geometry": {"type": "LineString", "coordinates": [[-78.80, 35.86], [-78.77, 35.89]]}}

    class Radar(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/tar1090/data/receiver.json":
                hits["receiver"] += 1
                time.sleep(0.3)
                body_ = b'{"lat": 35.8776, "lon": -78.7875}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body_)))
                self.end_headers()
                self.wfile.write(body_)
            elif self.path == "/api/runways":
                hits["runways"] += 1
                if runways["centre"] is None:
                    body_ = b'{"error": "not built"}'
                    self.send_response(404)
                else:
                    body_ = json.dumps({"type": "FeatureCollection", "features": [RUNWAY], "centre": runways["centre"],
                                        "radiusNm": 22.5, "built": "2026-10-26T00:00:00Z",
                                        "source": "OpenStreetMap via Overpass",
                                        "licence": "ODbL 1.0, \u00a9 OpenStreetMap contributors"}).encode()
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body_)))
                self.end_headers()
                self.wfile.write(body_)
            elif self.path.startswith("/as/"):
                # the stand-in's runways from now on: for somewhere else, or none
                runways["centre"] = {"/as/near": [35.85, -78.75], "/as/far": [36.0, -78.8], "/as/none": None}[self.path]
                self.send_response(204)
                self.end_headers()
            elif self.path == "/trickle":
                hits.setdefault("resolving", hits["receiver"])      # those were the five callers'
                # a byte every two seconds: never quiet for long, never done
                self.send_response(200)
                self.send_header("Content-Length", "1000")
                self.end_headers()
                try:
                    for _ in range(30):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(2)
                except OSError:
                    pass
            else:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Radar)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(16)
    held = []

    def hold():
        while True:
            try:
                held.append(silent.accept()[0])     # and never answer
            except OSError:
                return
    threading.Thread(target=hold, daemon=True).start()
    radar_url = "http://127.0.0.1:%d" % server.server_address[1]
    silent_url = "http://127.0.0.1:%d" % silent.getsockname()[1]

    work = pathlib.Path(tempfile.mkdtemp())
    (work / "main.swift").write_text("""import Foundation
let a = CommandLine.arguments
print("CAP", URLSession.radar.configuration.timeoutIntervalForResource, URLSession.bounded.configuration.timeoutIntervalForResource)
APIConfig.awayURL = nil
APIConfig.baseURL = a[1]
let got = await withTaskGroup(of: String.self) { g -> [String] in
    for _ in 0..<5 { g.addTask { await Endpoint.shared.resolve() } }
    var out: [String] = []
    for await b in g { out.append(b) }
    return out
}
print("RESOLVED", Set(got).count, got[0])
APIConfig.baseURL = a[2]
var t = Date()
let n = await Nearby.load(within: 2)
print("NEARBY", n == nil ? "nil" : "some", String(format: "%.1f", Date().timeIntervalSince(t)))
t = Date()
do {
    _ = try await URLSession.radar.data(for: URLRequest(url: URL(string: a[1] + "/trickle")!, timeoutInterval: 8))
    print("TRICKLE done", String(format: "%.1f", Date().timeIntervalSince(t)))
} catch {
    print("TRICKLE", (error as? URLError)?.code == .timedOut ? "timedout" : "error", String(format: "%.1f", Date().timeIntervalSince(t)))
}
""")
    # The runways (#87), only from an app that asks the radar before Overpass
    # and keeps off Overpass while it has a copy: the test puts one on the
    # "phone" first, so it asks no one outside.
    radar_first = before(fetch, "fromRadar(", "fromOverpass(") and "guard cachedRunwayGeoJSON(" in fetch
    if radar_first:
        with open(work / "main.swift", "a") as f:
            f.write("""APIConfig.baseURL = a[1]
let rdu = Coordinate(lat: 35.8776, lon: -78.7875)
for step in ["exact", "near", "far", "none"] {
    if step != "exact" { _ = try? await URLSession.radar.data(for: URLRequest(url: URL(string: a[1] + "/as/" + step)!, timeoutInterval: 2)) }
    guard RunwayClient.cachedRunwayGeoJSON(center: rdu, rangeNm: 20) != nil else { print("RUNWAYS", step, "nocopy"); break }
    let got = await RunwayClient.fetchRunwayGeoJSON(center: rdu, rangeNm: 20)
    let doc = got.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
    print("RUNWAYS", step, got == nil ? "nil" : (doc?.keys.sorted().joined(separator: ",") ?? "?"), (doc?["features"] as? [Any])?.count ?? 0)
}
""")
    srcs = [str(IOS / "Shared" / n) for n in ["APIConfig.swift", "Aircraft.swift", "AircraftFeedClient.swift", "DemoFeed.swift", "Geo.swift"]]
    if radar_first:
        srcs.append(str(IOS / "StratoScan" / "Networking" / "RunwayClient.swift"))
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    built = subprocess.run([swiftc, "-target", arch + "-apple-macos14", "-o", str(work / "net"), *srcs, str(work / "main.swift")],
                           capture_output=True, text=True, timeout=300)
    check(built.returncode == 0, "the shared networking code compiles on its own" + ("" if built.returncode == 0 else ": " + built.stderr[-600:]))
    if built.returncode == 0:
        home = work / "home"
        home.mkdir()
        # a copy of the runways already on the "phone", an old one
        caches = home / "Library" / "Caches"
        caches.mkdir(parents=True)
        kept = caches / "runways-35.90_-78.80_20.geojson"
        kept.write_text('{"type": "FeatureCollection", "features": []}')
        # its settings in a home of its own, not this Mac's
        env = {"CFFIXED_USER_HOME": str(home), "HOME": str(home), "PATH": "/usr/bin:/bin"}
        ran = subprocess.run([str(work / "net"), radar_url, silent_url], capture_output=True, text=True, timeout=120, env=env)
        out = {l.split()[0]: l.split()[1:] for l in ran.stdout.splitlines() if l.strip()}
        check(out.get("CAP") == ["12.0", "30.0"], "the sessions' limits in all are 12 s and 30 s: %s" % out.get("CAP"))
        check(out.get("RESOLVED") == ["1", radar_url], "five callers at once all get the radar's address: %s" % out.get("RESOLVED"))
        check(hits.get("resolving") == 1, "from one look-up between them (%s asked the radar)" % hits.get("resolving"))
        nb = out.get("NEARBY", ["?", "99"])
        check(nb[0] == "nil" and float(nb[1]) < 3.5,
              "a widget's look at a radar that never answers ends at its limit (%s s, not 1.5 + 8 + 8)" % nb[1])
        tr = out.get("TRICKLE", ["?", "0"])
        check(tr[0] == "timedout" and 11 <= float(tr[1]) <= 15,
              "a radar that trickles is given up after 12 s in all (%s s), though never quiet for 8" % tr[1])
        rw = {l.split()[1]: l.split()[2:] for l in ran.stdout.splitlines() if l.startswith("RUNWAYS ")}
        if not radar_first:
            print("skip the compiled runway checks: this app goes to Overpass first")
        else:
            check(rw.get("exact") == ["features,type", "1"],
                  "the radar's runways are taken, without its notes: %s" % rw.get("exact"))
            check(len(json.loads(kept.read_text())["features"]) == 1, "and kept on the phone in place of the old copy")
            check(rw.get("near") == ["features,type", "1"], "a centre one 0.05° step over is still this radar's: %s" % rw.get("near"))
            check(rw.get("far") == ["nil", "0"], "a copy for somewhere else is not taken: %s" % rw.get("far"))
            check(rw.get("none") == ["nil", "0"], "nor is there anything when the radar hasn't one: %s" % rw.get("none"))
            check(hits["runways"] == 4, "the radar was asked each time (%d), and with a copy on the phone Overpass never was" % hits["runways"])
        if ran.returncode != 0:
            check(False, "the stand-in run ended badly: " + ran.stderr[-400:])
    server.shutdown()
    silent.close()

print("app time-limit checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
