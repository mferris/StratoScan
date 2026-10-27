#!/usr/bin/env python3
"""The public range records change at most once a day (2026-10-26).

The sighting store's 'far' and 'near' records are ranges from the antenna,
and a record moves the moment an aircraft beats it. Rounded to whole
nautical miles they still said when it moved, if the public saw them live.
So the public /sightings/stats and /sightings/year carry a copy, taken at
most once every RANGE_RECORDS_REFRESH_S: a change to either record in the
store must not show in any public answer before then, and shows after.

Runs the real gateway in front of a stand-in sighting store, on a clock
the test moves.

Run: python3 tests/test_funnel_gateway_records.py
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


DAY = getattr(fg, "RANGE_RECORDS_REFRESH_S", 86400)
clock = [1000.0]
if hasattr(fg, "PublicRangeRecords"):
    fg.PUBLIC_RANGE_RECORDS = fg.PublicRangeRecords(now=lambda: clock[0])

# Each side of a half-nm boundary, so a live whole-nm value would move.
records = {"far": {"v": 187.4, "hex": "a1b2c3", "cs": "FARREC1", "at": 1791000001},
           "near": {"v": 0.6, "hex": "a1b2c4", "cs": "NEARREC1", "at": 1791000002},
           "high": {"v": 45000, "hex": "a1b2c5", "cs": "HIGHREC1", "at": 1791000003}}
store = {
    "/sightings/stats": {"since": 1790000000, "visits": 50, "nearby": 7, "records": records},
    "/sightings/year": {"year": 2026, "ready": True, "visits": 50, "nearby": 7, "records": records},
}


class Store(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        doc = store.get(fg.Handler._normalise(self.path))
        body = json.dumps(doc).encode()
        self.send_response(200 if doc is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Store)
threading.Thread(target=up.serve_forever, daemon=True).start()
fg.UPSTREAM = "http://127.0.0.1:%d" % up.server_address[1]
gw = fg.QuietServer(("127.0.0.1", 0), fg.Handler)
threading.Thread(target=gw.serve_forever, daemon=True).start()

PATHS = ["/sightings/stats", "/sightings/stats?x=1", "/SIGHTINGS/stats/", "/sightings/year", "/sightings/year?y=2026"]


def ask(method, path):
    c = http.client.HTTPConnection("127.0.0.1", gw.server_address[1], timeout=10)
    c.request(method, path)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, r.getheader("Content-Length"), data


def answers():
    """Every public answer, GET and HEAD, keyed by method and path."""
    out = {}
    for p in PATHS:
        for m in ("GET", "HEAD"):
            status, length, body = ask(m, p)
            out[(m, p)] = (status, length, body)
    return out


def public_records(path="/sightings/stats"):
    try:
        return json.loads(ask("GET", path)[2]).get("records") or {}
    except ValueError:
        return {}


# ---- the first public answer -------------------------------------------------
# /sightings/year is asked first, then /sightings/stats: the copy is one.
first_year = public_records("/sightings/year")
first = answers()
r = public_records()
check(r.get("far") == {"v": 187.0} and r.get("near") == {"v": 1.0},
      "the public range records: whole nautical miles, no aircraft, no time (%s)" % {k: r.get(k) for k in ("far", "near")})
check(first_year.get("far") == r.get("far") and first_year.get("near") == r.get("near"),
      "/sightings/year and /sightings/stats carry the same copy")
check(all(v[0] == 200 for v in first.values()), "every public GET and HEAD of the summaries is answered")

# ---- both records move in the store; the public answers do not ------------
records["far"] = {"v": 187.6, "hex": "a1b2d1", "cs": "FARREC2", "at": 1791000100}
records["near"] = {"v": 0.4, "hex": "a1b2d2", "cs": "NEARREC2", "at": 1791000101}
moved = []
for later in (0, 1, 60, 3600, DAY / 2, DAY - 1):
    clock[0] = 1000.0 + later
    now = answers()
    if now != first:
        moved.append(later)
check(not moved, "a record's change shows in no public answer, GET or HEAD, for a day%s"
      % ("" if not moved else " (moved after %s s)" % moved))

# A record that is not a range keeps moving live: only far and near wait.
records["high"] = {"v": 47000, "hex": "a1b2d3", "cs": "HIGHREC2", "at": 1791000102}
check(public_records().get("high", {}).get("v") == 47000, "the highest record is not held back")
records["high"] = {"v": 45000, "hex": "a1b2c5", "cs": "HIGHREC1", "at": 1791000003}

# ---- after a day, the new copy ---------------------------------------------------
clock[0] = 1000.0 + DAY
r = public_records("/sightings/year?y=2026")
check(r.get("far") == {"v": 188.0} and r.get("near") == {"v": 0.0},
      "a day on, the public sees the records as they stand then (%s)" % {k: r.get(k) for k in ("far", "near")})
check(public_records() == r, "and /sightings/stats the same copy")
text = json.dumps([public_records(p) for p in PATHS])
check(not any(m in text for m in ("FARREC", "NEARREC", "a1b2d1", "a1b2d2", "1791000100", "187.6", "0.4")),
      "and still without the aircraft, the time or the tenths")

# A store answer without records (a year not counted yet) takes no copy: an
# empty one would hide the records for a day.
clock[0] = 1000.0 + 2 * DAY
store["/sightings/year"] = {"year": 2026, "ready": False}
check(json.loads(ask("GET", "/sightings/year")[2]) == {"year": 2026, "ready": False},
      "a year not counted yet passes through")
records["far"] = {"v": 189.2, "hex": "a1b2d4", "cs": "FARREC3", "at": 1791000200}
check(public_records().get("far") == {"v": 189.0}, "and the next summary takes the day's copy")

gw.shutdown()
up.shutdown()
print("public range record checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
