#!/usr/bin/env python3
"""The app through the relay's shared cache (#68, roadmap 2.29).

A phone paired with a radar asks the relay for the network's aircraft and
for routes, which the radars already share there. It can only take what a
radar has fetched (it may not hand a disc up), so on a miss it asks adsb.lol
itself, as before. A disc is about 400 KB, so the phone names its view and
the relay sends only the aircraft in it.

The relay refuses a disc that is not on its lattice, so the app's lattice
(ios/Shared/NetLattice.swift) must land on the same centres as the relay's
and the unit's. Where swiftc is installed this compiles that file and checks
it against the unit's lattice (deploy/network-compare.py), which
tests/test_network_around.py checks against the relay's answers.

Run: python3 tests/test_app_netcache.py
"""
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

os.environ["STATE_DIRECTORY"] = tempfile.mkdtemp()
os.environ["STRATOSCAN_NET_RELAY"] = "0"
ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("nc", ROOT / "deploy" / "network-compare.py")
nc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nc)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


IOS = ROOT / "ios"
lattice_src = (IOS / "Shared" / "NetLattice.swift").read_text()

# ---- the app's lattice is the relay's ------------------------------------------
# Points across the globe, and views of several sizes for the one-disc test.
POINTS = [(lat10 / 10, lon10 / 10) for lat10 in range(-899, 900, 37) for lon10 in range(-1800, 1800, 43)]
VIEWS = [(lat, lon, want) for (lat, lon) in POINTS[::7] for want in (25, 26, 65, 130, 200, 250)]
KNOWN = [((35.8776, -78.7875), (34.8387, -77.6471)), ((51.5, -0.1), (52.2581, -4.7368)),
         ((-33.9, 151.2), (-34.8387, 148.2353)), ((89.9, 10), (87.0968, 45.0)),
         ((0, 0), (0.0, 2.9032)), ((40, -74), (40.6452, -76.5957))]

swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc:
    print("skip the compiled lattice checks: no swiftc here (they run on the Mac that builds the app)")
else:
    work = pathlib.Path(tempfile.mkdtemp())
    (work / "NetLattice.swift").write_text(lattice_src)
    lines = ["import Foundation", "func f(_ x: Double) -> String { String(format: \"%.4f\", x) }"]
    for lat, lon in POINTS + [k[0] for k in KNOWN]:
        lines.append(f'do {{ let c = NetLattice.centre({lat!r}, {lon!r}); print("C", f(c.lat), f(c.lon)) }}')
    for lat, lon, want in VIEWS:
        lines.append(f'do {{ if let c = NetLattice.holding({lat!r}, {lon!r}, wantNm: {want}) {{ print("H", f(c.lat), f(c.lon)) }} else {{ print("H none") }} }}')
    for lat, lon in [(35.8776, -78.7875), (60.2, 24.9), (-1.3, 36.8)]:
        lines.append(f'do {{ print("W", NetLattice.centres({lat!r}, {lon!r}, within: 700).prefix(8).map {{ "\\(f($0.centre.lat)),\\(f($0.centre.lon))" }}.joined(separator: " ")) }}')
    lines.append('print("R", NetLattice.rows, f(NetLattice.rowStep), f(NetLattice.spacingNm))')
    (work / "main.swift").write_text("\n".join(lines) + "\n")
    built = subprocess.run([swiftc, "-O", "-o", str(work / "lattice"), str(work / "NetLattice.swift"), str(work / "main.swift")],
                           capture_output=True, text=True)
    check(built.returncode == 0, "ios/Shared/NetLattice.swift compiles on its own (Foundation only)" + ("" if built.returncode == 0 else ": " + built.stderr[-400:]))
    if built.returncode == 0:
        out = subprocess.run([str(work / "lattice")], capture_output=True, text=True).stdout.splitlines()
        cs = [l.split()[1:] for l in out if l.startswith("C ")]
        hs = [l.split()[1:] for l in out if l.startswith("H ")]
        ws = [l.split()[1:] for l in out if l.startswith("W ")]
        r = next(l.split()[1:] for l in out if l.startswith("R "))
        check(r == [str(nc.LATTICE_ROWS), "%.4f" % nc.LATTICE_ROW_STEP, "%.4f" % nc.LATTICE_SPACING_NM],
              "the same %s rows, row step and spacing as the unit and the relay" % r[0])
        want_c = [["%.4f" % v for v in nc.lattice_centre(lat, lon)] for lat, lon in POINTS]
        check(cs[:len(POINTS)] == want_c, "the same lattice centre as the unit for %d points across the globe" % len(POINTS))
        check(cs[len(POINTS):] == [["%.4f" % v for v in k[1]] for k in KNOWN],
              "and the relay's own answers (relay/src/netcache.js), RDU's among them")
        want_h = []
        for lat, lon, want in VIEWS:
            discs, _ = nc.plan_discs(lat, lon, want / 1.3, lattice=True)
            want_h.append(["%.4f" % discs[0][0], "%.4f" % discs[0][1]] if len(discs) == 1 else ["none"])
        same = sum(a == b for a, b in zip(hs, want_h))
        check(same == len(VIEWS), "one disc holds a view exactly when the unit's plan_discs says so (%d of %d views)" % (same, len(VIEWS)))
        check(any(h != ["none"] for h in hs) and any(h == ["none"] for h in hs), "some views fit one disc and some don't")
        for (lat, lon), w in zip([(35.8776, -78.7875), (60.2, 24.9), (-1.3, 36.8)], ws):
            py = ["%.4f,%.4f" % (c[1], c[2]) for c in nc.lattice_centres(lat, lon, 700)[:8]]
            check(w == py, "the nearest centres round (%s, %s), in the unit's order" % (lat, lon))
    shutil.rmtree(work, ignore_errors=True)

# ---- the feed asks the relay first, and only what it can answer ----------------
feed = (IOS / "Shared" / "NetworkFeed.swift").read_text()
fetch = feed[feed.index("static func fetch(around"):feed.index("private static func decode(")]
check(fetch.index("fromRelay(at: at, radius: radius)") < fetch.index("api.adsb.lol"),
      "the feed asks the relay's cache before adsb.lol")
check("decode(data, within: (at, Double(radius)))" in fetch,
      "and keeps only the aircraft within the view, even if a relay sends a whole disc")
rel = feed[feed.index("private static func fromRelay("):]
check("NetLattice.holding(at.lat, at.lon, wantNm: Double(radius))" in rel,
      "only a view that one lattice disc holds goes to the relay (a wide view asks adsb.lol, as before)")
check("relayMissSeconds" in rel and "missedAt[key] = Date()" in rel,
      "a disc the relay didn't have is left alone for a while, not asked for again every few seconds")
m = __import__("re").search(r"static let relayMissSeconds: TimeInterval = (\d+)", feed)
check(m is not None and 10 <= int(m.group(1)) <= 120, "for between ten seconds and two minutes")

client = (IOS / "StratoScan" / "Pairing" / "RelayClient.swift").read_text()
check('"/v1/net/disc/%.4f/%.4f"' in client, "the disc is named on the lattice to four decimals, as the relay checks it")
check('"near=%.2f,%.2f,%d"' in client, "the view's middle goes out to two decimals (the relay refuses anything finer)")
ask = client[client.index("private func ask("):]
check("RelayIdentity.headers(method: method, path: path, body: body)" in ask and "percentEncodedQuery = query" in ask,
      "signed like every relay request: the path, not the query")
check('"/v1/net/routes"' in client, "routes come from the relay's cache too")

routes = (IOS / "StratoScan" / "Networking" / "RouteLookupClient.swift").read_text()
flush = routes[routes.index("private func flush()"):]
check(flush.index("Self.relay") < flush.index("routeAPIURL"), "a route is asked of the relay before adsb.im")
check("($0.lat * 10).rounded() / 10" in flush, "with positions rounded to 0.1 degrees, as the relay sends them on")
check("compactMap(\\.location)" in flush, "a stop without a city no longer throws the whole batch away")

app = (IOS / "StratoScan" / "App" / "StratoScanApp.swift").read_text()
check("NetworkFeed.relay = {" in app and "RouteLookupClient.relay = {" in app,
      "the app (not the widget or the Watch) wires both up")
check("!pairing.radars.isEmpty" in app, "and only while a radar is paired: the relay serves no one else")

# ---- the relay side ----------------------------------------------------------------
js = (ROOT / "relay" / "src" / "netcache.js").read_text()
disc = js[js.index("async function disc("):js.index("function discResponse(")]
check("if (w.kind === 'phone') return json(404, { error: 'not cached' });" in disc
      and disc.index("w.kind === 'phone'") < disc.index("cachePut(env, ctx, lease"),
      "the relay never asks a phone to fetch a disc, and a phone's miss takes no lease from the radars")
check("nearOnly(hit.body, near)" in disc, "a phone's view gets only the aircraft in it")

# ---- and the privacy policy says so ----------------------------------------------
privacy = (ROOT / "docs" / "privacy.md").read_text()
check("Nothing goes to the StratoScan relay." not in privacy, "the privacy policy no longer says nothing goes to the relay")
check("radars and phones" in privacy, "the relay's table names phones as well as radars")

print("app shared-cache checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
