#!/usr/bin/env python3
"""The public address only reads, and nothing it answers is finer than the
rounded receiver position (2026-10-26).

Runs the real gateway in front of a stand-in for lighttpd that answers every
method on every path with the data as the unit holds it: the exact receiver
position, aircraft.json with r_dst/r_dir, readsb's stats.json, the core feed
with its ring counts and close passes, and the sighting store with its
close passes and range records. Every method goes to every path the gateway
rewrites, strips or refuses, in several spellings. Only GET and HEAD may be
answered (and a browser's POST to /csp-report); nothing else may reach the
stand-in at all; a HEAD gets the rewritten answer's headers; and no answer
may carry the exact position or anything measured from it. Two receiver
positions in the same 0.01 degree cell give the same public answers.

Run: python3 tests/test_funnel_gateway_methods.py
"""
import http.client
import http.server
import importlib.util
import json
import pathlib
import sys
import threading

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fg", root / "deploy" / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


EXACT = [35.8776, -78.7875]           # RDU; the public answers say 35.88, -78.79
SAME_CELL = [35.8816, -78.7915]       # EXACT moved 0.004 degrees north and west: still 35.88, -78.79
NEARBY = 4321                         # a close-pass count no public answer may carry
RANGE_RECORDS = {"far": {"v": 187.3, "hex": "a1b2c3", "cs": "FARREC1", "at": 1791000001},
                 "near": {"v": 0.4, "hex": "a1b2c4", "cs": "NEARREC1", "at": 1791000002},
                 "high": {"v": 45000, "hex": "a1b2c5", "cs": "HIGHREC1", "at": 1791000003}}
# What must never come back publicly, in any answer to anything.
MARKERS = ["35.8776", "78.7875", "35.881", "78.791", "r_dst", "r_dir", "max_distance", "271828",
           str(NEARBY), "A Private Person", "FARREC1", "NEARREC1", "1791000001", "1791000002", "187.3", '"heard"']

receiver = {"lat": EXACT[0], "lon": EXACT[1], "refresh": 1000, "history": 120, "binCraft": True,
            "zstd": True, "outlineJson": True, "version": "readsb"}
UPSTREAM_FILES = {
    "/tar1090/data/receiver.json": receiver,
    "/tar1090/data/aircraft.json": {"now": 1.0, "aircraft": [
        {"hex": "a1b2c3", "flight": "DAL123  ", "lat": 35.95, "lon": -78.70, "alt_baro": 3000, "r_dst": 5.123, "r_dir": 41.5}]},
    "/tar1090/data/stats.json": {"now": 1.0, "last1min": {"messages": 5, "max_distance": 271828},
                                 "total": {"messages": 9, "max_distance": 271828}},
    "/tar1090/data/status.json": {"now": 1.0, "uptime": 2},
    "/api/aircraft": {"now": 1.0, "counts": {"heard": 31, "notHeard": None, "on978": 0}, "aircraft": [
        {"hex": "a1b2c3", "source": "antenna", "lat": 35.95, "lon": -78.70, "owner": {"name": "A Private Person"},
         "sightings": {"total": 5, "nearby": NEARBY}}]},
    "/sightings": {"a1b2c3": {"total": 5, "nearby": NEARBY}, "a1b2c4": {"total": 1, "nearby": NEARBY}},
    "/sightings/stats": {"since": 1790000000, "visits": 50, "nearby": NEARBY, "today": {"total": 9, "nearby": NEARBY},
                         "byOp": {"com": {"ac": 1, "visits": 5, "nearby": NEARBY}},
                         "byKind": {"jet": {"ac": 1, "visits": 5, "nearby": NEARBY}},
                         "records": RANGE_RECORDS, "top": [{"hex": "a1b2c3", "cs": "DAL123", "visits": 5}]},
    "/sightings/year": {"year": 2026, "ready": True, "visits": 50, "nearby": NEARBY, "records": RANGE_RECORDS,
                        "top": [{"hex": "a1b2c3", "cs": "DAL123", "visits": 5}]},
    "/sightings/unclassified": {"hexes": [], "remaining": 0},
    "/network": {"ac": [], "mine": 0, "network": 0, "stats": {"ready": False}},
    "/network/stats": {"stats": {"ready": False}},
    "/approaches": {"cells": {}},
    "/tar1090": "<html><script>let databaseFolder = \"db2\";</script><button onclick=\"x();\"></button></html>",
    "/tar1090/index.html": "<html><script>let databaseFolder = \"db2\";</script></html>",
    "/": "<html><script>go();</script></html>",
    "/index.html": "<html><script>go();</script></html>",
}
received = []                         # (method, path) of everything that reached the stand-in


class Upstream(http.server.BaseHTTPRequestHandler):
    """lighttpd, as far as the gateway can tell: every method, every file."""

    def _any(self):
        received.append((self.command, self.path))
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        doc = UPSTREAM_FILES.get(fg.Handler._normalise(self.path))
        if doc is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        html = isinstance(doc, str)
        body = (doc if html else json.dumps(doc)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html" if html else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self._any
        raise AttributeError(name)

    def log_message(self, *a):
        pass


up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
threading.Thread(target=up.serve_forever, daemon=True).start()
fg.UPSTREAM = "http://127.0.0.1:%d" % up.server_address[1]
gw = fg.QuietServer(("127.0.0.1", 0), fg.Handler)
threading.Thread(target=gw.serve_forever, daemon=True).start()


def ask(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", gw.server_address[1], timeout=10)
    c.request(method, path, body=body, headers={"Content-Type": "application/json"} if body is not None else {})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, data


REWRITTEN = {
    "receiver": ["/tar1090/data/receiver.json", "/tar1090/data/receiver.json?x=1", "/tar1090//data/receiver.json",
                 "/tar1090/data/receiver%2Ejson", "/tar1090/data/receiver.json/", "/TAR1090/data/receiver.json"],
    "aircraft": ["/tar1090/data/aircraft.json", "/tar1090/data/aircraft.json?_=1", "/x/../tar1090/data/aircraft.json"],
    "core": ["/api/aircraft", "/api/aircraft?network=1", "/API/aircraft", "/api//aircraft"],
    "sightings": ["/sightings", "/sightings/", "/sightings?x=1", "/%73ightings"],
    "stats": ["/sightings/stats", "/sightings/stats/", "/SIGHTINGS/stats"],
    "year": ["/sightings/year", "/sightings/year?y=2026"],
}
REFUSED = ["/tar1090/data/stats.json", "/tar1090/data/stats.json?x=1", "/./tar1090/data/stats.json"]
PASSED = ["/tar1090/data/status.json", "/network", "/network/stats", "/approaches", "/sightings/unclassified",
          "/tar1090/", "/tar1090/index.html", "/", "/index.html"]
ALL_PATHS = [p for ps in REWRITTEN.values() for p in ps] + REFUSED + PASSED
WRITES = ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
OTHER = ["PROPFIND", "TRACE", "QUERY", "MKCOL"]


def leaks(*parts):
    text = " ".join(p if isinstance(p, str) else p.decode("utf-8", "replace") for p in parts)
    return [m for m in MARKERS if m in text]


# ---- every method, every path --------------------------------------------
leaked, wrong_status, reached = [], [], []
for path in ALL_PATHS:
    for method in ["GET", "HEAD"] + WRITES + OTHER:
        before = len(received)
        status, headers, body = ask(method, path, b"{}" if method in ("POST", "PUT", "PATCH") else None)
        found = leaks(body, json.dumps(headers))
        if found:
            leaked.append("%s %s: %s" % (method, path, found))
        if method in ("GET", "HEAD"):
            want = (404,) if path in REFUSED else (200,)
            if status not in want:
                wrong_status.append("%s %s -> %d" % (method, path, status))
        else:
            if status not in (403, 405, 404, 400, 501) or (status == 405 and headers.get("allow") != "GET, HEAD"):
                wrong_status.append("%s %s -> %d" % (method, path, status))
            if len(received) != before:
                reached.append("%s %s" % (method, path))
check(not leaked, "no answer to any method carries the exact position or anything measured from it%s"
      % ("" if not leaked else ": " + "; ".join(leaked[:6])))
check(not wrong_status, "GET and HEAD are answered, everything else refused%s"
      % ("" if not wrong_status else ": " + "; ".join(wrong_status[:6])))
check(not reached, "nothing but a GET or HEAD reaches lighttpd%s" % ("" if not reached else ": " + "; ".join(reached[:6])))
check({m for m, _ in received} <= {"GET", "HEAD"}, "the stand-in saw only GETs and HEADs: %s" % sorted({m for m, _ in received}))

# ---- what the refusals say ---------------------------------------------------
status, headers, _ = ask("POST", "/tar1090/data/receiver.json", b"")
check(status == 405 and headers.get("allow") == "GET, HEAD", "a write anywhere but the stores is 405, Allow: GET, HEAD")
check(ask("POST", "/sightings", b'{"hex":"a1b2c3","kind":"total"}')[0] == 403,
      "a write to a store is still 403 Read-only, which the page stops writing on (#67)")
before = len(received)
check(ask("POST", "/csp-report", b'{"csp-report":{"effective-directive":"img-src","blocked-uri":"https://x.example/p"}}')[0] == 204
      and len(received) == before, "a browser's report to /csp-report is answered here and never forwarded")
check(ask("OPTIONS", "/")[0] == 405 and ask("TRACE", "/")[0] in (405, 501), "OPTIONS and TRACE are refused on the page too")

# ---- what the rewrites say ---------------------------------------------------
_, _, raw = ask("GET", "/tar1090/data/receiver.json")
r = json.loads(raw)
check(r["lat"] == 35.88 and r["lon"] == -78.79 and r["binCraft"] is False and r["zstd"] is False,
      "receiver.json: rounded to 0.01 degrees, and tar1090 told to ask for none of the refused files")
check(r["refresh"] == 1000, "and the rest of receiver.json as readsb wrote it")
a = json.loads(ask("GET", "/tar1090/data/aircraft.json")[2])["aircraft"][0]
check("r_dst" not in a and "r_dir" not in a and a["lat"] == 35.95, "aircraft.json: positions kept, r_dst and r_dir gone")
core = json.loads(ask("GET", "/api/aircraft?network=1")[2])
check(core["counts"] is None and core["aircraft"][0]["sightings"] == {"total": 5, "nearby": None}
      and core["aircraft"][0]["owner"] is None, "the core feed: no ring counts, no close passes, no owners")
s = json.loads(ask("GET", "/sightings")[2])
check(s == {"a1b2c3": {"total": 5, "nearby": None}, "a1b2c4": {"total": 1, "nearby": None}},
      "/sightings: each aircraft's visits, no close passes")
st = json.loads(ask("GET", "/sightings/stats")[2])
check(st["nearby"] is None and st["byOp"]["com"]["nearby"] is None and st["byKind"]["jet"]["nearby"] is None
      and st["byOp"]["com"]["visits"] == 5 and st["visits"] == 50, "/sightings/stats: no close-pass counts, the visits kept")
check(st["today"] is None, "and no today, which the app reads as two numbers and shows as unknown when missing")
check(st["records"]["far"] == {"v": 187.0} and st["records"]["near"] == {"v": 0.0},
      "the range records: whole nautical miles, no aircraft, no time")
check(st["records"]["high"] == RANGE_RECORDS["high"] and st["top"][0]["cs"] == "DAL123",
      "the records not measured from the radar, and the top visitors, as they were")
y = json.loads(ask("GET", "/sightings/year?y=2026")[2])
check(y["nearby"] is None and y["records"]["far"] == {"v": 187.0} and y["visits"] == 50, "/sightings/year likewise")
check(("GET", "/sightings/year?y=2026") in received, "the query goes through to the store")
check(ask("GET", "/tar1090/data/stats.json")[0] == 404, "stats.json is not served publicly")
summary = getattr(fg, "public_sighting_summary", lambda d: d)
counts = getattr(fg, "public_sighting_counts", lambda d: d)
check(summary({"records": {"far": {"v": "x", "cs": "FARREC1"}, "near": "odd", "fast": {"v": 500}}})
      == {"records": {"fast": {"v": 500}}} and summary([1]) == [1] and summary({"byOp": "odd"}) == {"byOp": "odd"},
      "a range record without a number goes altogether; odd answers pass through")
check(counts({"a1b2c3": "odd", "a1b2c4": {"total": 1}}) == {"a1b2c3": "odd", "a1b2c4": {"total": 1}} and counts([1]) == [1],
      "odd sighting counts pass through")

# ---- HEAD: the rewritten answer's headers, no body --------------------------
heads = []
for name, paths in REWRITTEN.items():
    for p in paths:
        g = ask("GET", p)
        h = ask("HEAD", p)
        if not (h[0] == 200 and h[2] == b"" and h[1].get("content-length") == str(len(g[2]))):
            heads.append(p)
check(not heads, "a HEAD of a rewritten answer gets its length, not the original's%s" % ("" if not heads else ": %s" % heads))

# ---- the policies ------------------------------------------------------------
page_policy = ask("GET", "/")[1].get("content-security-policy") or ""
check(page_policy.startswith("default-src 'none'") and "'sha256-" in page_policy and "'unsafe-inline'" not in page_policy.split("style-src")[0],
      "the radar page keeps its own hashed policy")
check(ask("GET", "/tar1090/data/status.json")[1].get("content-security-policy") is None, "data files get no page policy")

# ---- two positions in one 0.01 degree cell -------------------------------------
first = {p: ask("GET", p)[2] for p in REWRITTEN["receiver"]}
receiver.update(lat=SAME_CELL[0], lon=SAME_CELL[1])
second = {p: ask("GET", p)[2] for p in REWRITTEN["receiver"]}
check(first == second, "two receiver positions in the same 0.01 degree cell give the same public receiver.json")

gw.shutdown()
up.shutdown()
print("gateway method checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
