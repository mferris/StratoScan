#!/usr/bin/env python3
"""
Local-only (127.0.0.1) proxy that compares this receiver against a public
ADS-B network, and keeps a running scorecard of how the two differ.

Why a device-side service rather than fetching from the page:

  - Same origin. The page is served from http://localhost, so a direct
    call to another host is a cross-origin request the API need not allow.
  - One upstream call no matter how many people are looking. The kiosk,
    a laptop and the public Funnel URL all share the same cached answer,
    so a community-run service does not get hit once per viewer.
  - The receiver's exact position never leaves the network. The query is
    built from coordinates ROUNDED to 2dp (~1.1km), the same precision
    funnel-gateway.py already exposes publicly. Sending survey-precision
    coordinates to a third party to ask "what is near me" would undo the
    rounding the rest of this project does deliberately.

Nothing here runs on its own. The scorecard accumulates only from
requests the page makes, and the page only makes them when the
"Network comparison" setting is on -- which is OFF by default. A unit
nobody has enabled it on never contacts anyone.

GET /network      -> {"ac": [...], "stats": {...}, "source": ..., "fetched": age_s}
GET /network/stats -> just the scorecard, no upstream call
"""
import http.server
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request

LISTEN = ("127.0.0.1", 8087)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "coverage.json")

LOCAL_AIRCRAFT = "http://127.0.0.1/tar1090/data/aircraft.json"
LOCAL_RECEIVER = "http://127.0.0.1/tar1090/data/receiver.json"

# Community-run and free. Identify ourselves rather than arriving anonymous,
# and never poll faster than MIN_UPSTREAM_S -- this is somebody's donated
# bandwidth, and the page has no reason to want fresher than this.
SOURCE_NAME = "adsb.lol"
SOURCE_URL = "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}"
USER_AGENT = "FlightWall/1.0 (+hobby ADS-B receiver; coverage self-comparison)"
MIN_UPSTREAM_S = 15
UPSTREAM_TIMEOUT = 8
RADIUS_NM = 25          # a little beyond the 20nm ring the radar draws
RING_NM = 20            # what the radar actually shows; stats use this

MAX_BODY = 400_000

# Altitude bands, in feet. Chosen to separate a horizon problem from a
# sensitivity one: if the low bands are the weak ones the antenna is being
# blocked, and no amount of gain fixes that.
ALT_BANDS = [(0, 2000), (2000, 6000), (6000, 15000), (15000, 99000)]
BRG_BINS = 12           # 30-degree sectors
WINDOW_S = 24 * 3600    # scorecard covers a rolling day

lock = threading.Lock()
_cache = {"at": 0.0, "payload": None}


def band_label(lo, hi):
    return f"{lo}-{hi}" if hi < 99000 else f"{lo}+"


def load_store():
    try:
        with open(STORE_PATH) as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_store(store):
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
    os.replace(tmp, STORE_PATH)   # atomic: a torn scorecard is worse than a stale one


def fresh_store():
    return {
        "since": time.time(),
        "samples": 0,
        "heard": 0, "network": 0,
        "alt": {band_label(*b): [0, 0] for b in ALT_BANDS},
        "brg": {str(i): [0, 0] for i in range(BRG_BINS)},
        "age_mine": [], "age_net": [],
    }


def get_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(MAX_BODY).decode("utf-8", "replace"))


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = p2 - p1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    rng = 3440.065 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return rng, (math.degrees(math.atan2(y, x)) + 360) % 360


def home():
    d = get_json(LOCAL_RECEIVER, timeout=4)
    return float(d["lat"]), float(d["lon"])


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    return round(s[len(s) // 2], 1)


def compare(lat, lon):
    """One paired sample: what this antenna heard vs what the network has."""
    local = get_json(LOCAL_AIRCRAFT, timeout=4)
    # Round before it leaves the machine. See the module docstring.
    net = get_json(SOURCE_URL.format(lat=round(lat, 2), lon=round(lon, 2),
                                     radius=RADIUS_NM), timeout=UPSTREAM_TIMEOUT)

    mine = {}
    for a in local.get("aircraft", []):
        if "lat" not in a or "lon" not in a:
            continue
        r, b = haversine(lat, lon, a["lat"], a["lon"])
        if r <= RING_NM:
            mine[a["hex"].strip().lower()] = (a, r, b)

    theirs = {}
    for a in net.get("ac", []):
        if a.get("lat") is None or a.get("lon") is None:
            continue
        r, b = haversine(lat, lon, a["lat"], a["lon"])
        if r <= RING_NM:
            theirs[str(a.get("hex", "")).strip().lower()] = (a, r, b)

    return mine, theirs


def fold(store, mine, theirs):
    """Fold one paired sample into the rolling scorecard."""
    if time.time() - store.get("since", 0) > WINDOW_S:
        store = fresh_store()

    store["samples"] += 1
    store["network"] += len(theirs)
    store["heard"] += len(set(mine) & set(theirs))

    for hexid, (a, r, b) in theirs.items():
        alt = a.get("alt_baro")
        alt = 0 if alt == "ground" else (alt if isinstance(alt, (int, float)) else None)
        heard = hexid in mine
        if alt is not None:
            for lo, hi in ALT_BANDS:
                if lo <= alt < hi:
                    key = band_label(lo, hi)
                    store["alt"][key][1] += 1
                    if heard:
                        store["alt"][key][0] += 1
                    break
        k = str(int(b // (360 / BRG_BINS)) % BRG_BINS)
        store["brg"][k][1] += 1
        if heard:
            store["brg"][k][0] += 1

    both = set(mine) & set(theirs)
    for h in both:
        am = mine[h][0].get("seen_pos")
        an = theirs[h][0].get("seen_pos")
        if isinstance(am, (int, float)):
            store["age_mine"].append(round(am, 1))
        if isinstance(an, (int, float)):
            store["age_net"].append(round(an, 1))
    # bounded: these are only used for a median
    store["age_mine"] = store["age_mine"][-4000:]
    store["age_net"] = store["age_net"][-4000:]
    return store


def scorecard(store):
    if not store or not store.get("samples"):
        return {"ready": False}
    net = store["network"] or 1
    return {
        "ready": True,
        "since": store["since"],
        "samples": store["samples"],
        "coveragePct": round(100 * store["heard"] / net),
        "heard": store["heard"], "networkTotal": store["network"],
        "byAlt": {k: {"heard": v[0], "total": v[1],
                      "pct": round(100 * v[0] / v[1]) if v[1] else None}
                  for k, v in store["alt"].items()},
        "byBearing": {k: {"heard": v[0], "total": v[1],
                          "pct": round(100 * v[0] / v[1]) if v[1] else None}
                      for k, v in store["brg"].items()},
        "medianAgeMine": median(store["age_mine"]),
        "medianAgeNetwork": median(store["age_net"]),
        "source": SOURCE_NAME,
    }


def build_payload():
    lat, lon = home()
    mine, theirs = compare(lat, lon)
    with lock:
        store = fold(load_store() or fresh_store(), mine, theirs)
        save_store(store)
        card = scorecard(store)

    # Only the aircraft this receiver did NOT hear are worth sending: the
    # page already has its own, and shipping duplicates would invite the
    # display to prefer network data over local, which is the opposite of
    # what this radar is for.
    ghosts = []
    for hexid, (a, r, b) in theirs.items():
        if hexid in mine:
            continue
        ghosts.append({
            "hex": hexid,
            "flight": (a.get("flight") or "").strip() or None,
            "lat": a.get("lat"), "lon": a.get("lon"),
            "alt": a.get("alt_baro"),
            "gs": a.get("gs"), "track": a.get("track"),
            "seen_pos": a.get("seen_pos"),
            "type": a.get("t"), "reg": a.get("r"),
        })
    return {"ac": ghosts, "mine": len(mine), "network": len(theirs),
            "stats": card, "source": SOURCE_NAME, "at": time.time()}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def version_string(self):
        return "FlightRadar"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/network/stats":
            with lock:
                return self._json(200, {"stats": scorecard(load_store()),
                                        "source": SOURCE_NAME})
        if path != "/network":
            return self._json(404, {"error": "not found"})

        now = time.time()
        with lock:
            cached = _cache["payload"]
            fresh = cached is not None and now - _cache["at"] < MIN_UPSTREAM_S
        if fresh:
            out = dict(cached)
            out["fetched"] = round(now - _cache["at"], 1)
            return self._json(200, out)

        try:
            payload = build_payload()
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            # Upstream down, offline, or malformed. Serve the last good answer
            # if there is one -- a stale comparison is still useful, and the
            # radar's own data is unaffected either way.
            with lock:
                cached = _cache["payload"]
            if cached:
                out = dict(cached)
                out["stale"] = True
                out["error"] = type(e).__name__
                return self._json(200, out)
            return self._json(503, {"error": "upstream unavailable",
                                    "detail": type(e).__name__})
        with lock:
            _cache["at"] = time.time()
            _cache["payload"] = payload
        out = dict(payload)
        out["fetched"] = 0.0
        return self._json(200, out)


def main():
    srv = http.server.ThreadingHTTPServer(LISTEN, Handler)
    srv.serve_forever()


if __name__ == "__main__":
    main()
