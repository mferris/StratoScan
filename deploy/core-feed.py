#!/usr/bin/env python3
"""
The core feed (roadmap 1.8): one merged, labelled list of the aircraft this
unit knows about, for every screen -- the kiosk, the public page, the iPhone
app, the Watch, and in time the alerts.

Why it exists: the page, the app and the alerts each used to build their own
picture from readsb's aircraft.json, with their own copies of the tables that
say what an aircraft is. The copies drifted (the military badge was fixed
twice in one day; the app never showed the network's aircraft; counts
differed between the app and the kiosk), and every public visitor's browser
repeated every route and owner lookup against third-party services. Here the
labelling happens once, on the unit, from labels.py -- the same module the
alerts use -- and the lookups are made once and cached.

    GET /api/aircraft             the antenna's aircraft, labelled
    GET /api/aircraft?network=1   plus those a public ADS-B network reports in
                                  the ring that the antenna didn't hear
                                  (source "network"), fetched through
                                  network-compare.py only because a client
                                  asked -- that service's promise that nothing
                                  contacts the network on its own still holds

Safe to publish: no antenna-relative field (r_dst, r_dir) and no receiver
position leaves this service, so the feed can't locate the receiver; the
public gateway serves it read-only like the other stores. Aircraft positions
are what the aircraft broadcast to everyone.

Lookups (routes from adsb.im, registered owners from adsbdb for private
aircraft) run in a background thread, batched and cached in memory the way
the page did them; the feed never waits on them, it carries whatever is
known so far. Nothing is written to disk, so no SD-card wear.
"""
import http.server
import json
import math
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import labels  # noqa: E402

LISTEN = ("127.0.0.1", int(os.environ.get("STRATOSCAN_CORE_PORT", "8088")))
AIRCRAFT_JSON = os.environ.get("STRATOSCAN_AIRCRAFT_JSON", "/run/readsb/aircraft.json")
RECEIVER_JSON = os.environ.get("STRATOSCAN_RECEIVER_JSON", "/run/readsb/receiver.json")
NETWORK_URL = os.environ.get("STRATOSCAN_NETWORK_URL", "http://127.0.0.1:8087/network")
ROUTE_API = os.environ.get("STRATOSCAN_ROUTE_API", "https://adsb.im/api/0/routeset")
OWNER_API = os.environ.get("STRATOSCAN_OWNER_API", "https://api.adsbdb.com/v0/aircraft/{hex}")
LOOKUPS = os.environ.get("STRATOSCAN_CORE_LOOKUPS", "1") != "0"   # tests switch them off
USER_AGENT = "StratoScan/1.0 (+https://github.com/mferris/StratoScan; core feed)"

RING_NM = 20            # what the radar draws; counts use it, as the kiosk's do
STALE_S = 60            # readsb keeps an aircraft this long after its last message
AIRCRAFT_CACHE_S = 1.0  # one read of aircraft.json per second, however many clients
NETWORK_CACHE_S = 15.0  # network-compare caches upstream for 15 s itself
ROUTE_BATCH_S, ROUTE_BATCH_MAX = 4.0, 50
OWNER_RETRY_S = 300
CACHE_MAX = 20000       # routes/owners kept; the oldest go first

# Fields copied from readsb's record, under the feed's names. Antenna-relative
# ones (r_dst, r_dir) are deliberately absent.
FIELDS = {"flight": "flight", "lat": "lat", "lon": "lon", "gs": "gs", "track": "track",
          "squawk": "squawk", "category": "category", "emergency": "emergency",
          "seen_pos": "seenPos", "seen": "seen", "nav_heading": "navHeading"}


def _now():
    return time.time()


class Cache(dict):
    """A dict that forgets its oldest entries past CACHE_MAX."""
    def put(self, k, v):
        self.pop(k, None)
        self[k] = v
        while len(self) > CACHE_MAX:
            self.pop(next(iter(self)))


class Lookups:
    """Routes and owners, fetched in the background and cached."""

    def __init__(self):
        self.routes, self.owners = Cache(), Cache()
        self.route_queue, self.owner_queue = {}, set()
        self.owner_failed = {}
        self.lock = threading.Lock()
        if LOOKUPS:
            threading.Thread(target=self._loop, daemon=True).start()

    def want_route(self, cs, lat, lon):
        with self.lock:
            if cs not in self.routes and cs not in self.route_queue:
                self.route_queue[cs] = (lat, lon)

    def want_owner(self, hex_):
        with self.lock:
            failed = self.owner_failed.get(hex_)
            if hex_ in self.owners or (failed and _now() - failed < OWNER_RETRY_S):
                return
            self.owner_queue.add(hex_)

    def _loop(self):
        while True:
            time.sleep(ROUTE_BATCH_S)
            try:
                self._flush_routes()
                self._flush_owners()
            except Exception as e:  # a lookup must never take the feed down
                print(f"core: lookup error: {e}", flush=True)

    def _flush_routes(self):
        with self.lock:
            batch = list(self.route_queue.items())[:ROUTE_BATCH_MAX]
        if not batch:
            return
        body = json.dumps({"planes": [{"callsign": cs, "lat": lat, "lng": lon}
                                      for cs, (lat, lon) in batch]}).encode()
        req = urllib.request.Request(ROUTE_API, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                routes = json.load(r)
        except (OSError, ValueError):
            return   # a hiccup: cache nothing, retry later (as the page did)
        if not isinstance(routes, list):
            routes = []
        found = {}
        for route in routes:
            if not isinstance(route, dict) or not route.get("callsign"):
                continue
            stops = route.get("_airports") or []
            found[route["callsign"]] = ({"text": " → ".join(a.get("location", "?") for a in stops),
                                         "plausible": route.get("plausible") is not False}
                                        if len(stops) >= 2 else None)
        with self.lock:
            for cs, _ in batch:
                self.routes.put(cs, found.get(cs))
                self.route_queue.pop(cs, None)

    def _flush_owners(self):
        with self.lock:
            batch = list(self.owner_queue)[:10]
            self.owner_queue.difference_update(batch)
        for hex_ in batch:
            req = urllib.request.Request(OWNER_API.format(hex=hex_), headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    a = (json.load(r).get("response") or {}).get("aircraft") or {}
                owner = a.get("registered_owner")
                result = {"name": owner, "country": a.get("registered_owner_country_name")} if owner else None
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    with self.lock:
                        self.owner_failed[hex_] = _now()
                    continue
                result = None          # 404: not in the registry; remember that
            except (OSError, ValueError):
                with self.lock:
                    self.owner_failed[hex_] = _now()
                continue
            with self.lock:
                self.owners.put(hex_, result)
                self.owner_failed.pop(hex_, None)


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _nm(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl, dp = math.radians(lon2 - lon1), p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3440.065 * 2 * math.asin(min(1.0, math.sqrt(h)))


class Feed:
    def __init__(self, lookups=None):
        self.types = labels.TypeDb()
        self.notable = labels.NotableDb()
        self.lookups = lookups or Lookups()
        self._antenna = (0.0, [])
        self._network = (0.0, [])
        self.lock = threading.Lock()

    def _receiver(self):
        r = _read_json(RECEIVER_JSON) or {}
        lat, lon = r.get("lat"), r.get("lon")
        return (lat, lon) if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) else None

    def _antenna_raw(self):
        with self.lock:
            at, ac = self._antenna
            if _now() - at < AIRCRAFT_CACHE_S:
                return ac
            data = _read_json(AIRCRAFT_JSON) or {}
            ac = [a for a in data.get("aircraft", []) if isinstance(a, dict) and a.get("hex")
                  and (a.get("seen") is None or a.get("seen") <= STALE_S)]
            self._antenna = (_now(), ac)
            return ac

    def _network_raw(self):
        with self.lock:
            at, ac = self._network
            if _now() - at < NETWORK_CACHE_S:
                return ac
        try:
            req = urllib.request.Request(NETWORK_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as r:
                ac = (json.load(r) or {}).get("ac") or []
        except (OSError, ValueError):
            ac = []
        with self.lock:
            self._network = (_now(), ac)
        return ac

    def label(self, a, source):
        hex_ = a["hex"].lower().lstrip("~")
        info = self.types.lookup(hex_)
        flight = (a.get("flight") or "").strip() or None
        out = {"hex": hex_, "source": source}
        for k, name in FIELDS.items():
            if a.get(k) is not None:
                out[name] = a[k].strip() if k == "flight" else a[k]
        alt = a.get("alt_baro", a.get("alt"))
        out["alt"] = "ground" if alt == "ground" else (alt if isinstance(alt, (int, float)) else a.get("alt_geom"))
        vrate = a.get("baro_rate", a.get("vrate"))
        out["vrate"] = vrate if vrate is not None else a.get("geom_rate")
        out["operator"] = labels.operator(hex_, flight)
        out["reg"] = info.get("reg") or a.get("r") or a.get("reg")
        out["type"] = {"code": info.get("type_code") or a.get("t") or a.get("type"),
                       "name": info.get("type"), "desc": info.get("desc")}
        nb = self.notable.get(hex_)
        out["notable"] = ({"category": nb[0], "label": labels.NOTABLE_LABELS.get(nb[0], nb[0])}
                          if isinstance(nb, list) and nb else None)
        cs = labels.real_callsign(flight)
        out["route"] = self.lookups.routes.get(cs) if cs else None
        if cs and cs not in self.lookups.routes and isinstance(a.get("lat"), (int, float)):
            self.lookups.want_route(cs, a["lat"], a.get("lon"))
        out["owner"] = None
        if out["operator"]["kind"] == "private":
            out["owner"] = self.lookups.owners.get(hex_)
            if hex_ not in self.lookups.owners:
                self.lookups.want_owner(hex_)
        return out

    def build(self, with_network=False):
        home = self._receiver()
        antenna = self._antenna_raw()
        heard = {a["hex"].lower().lstrip("~") for a in antenna}
        aircraft = [self.label(a, "antenna") for a in antenna]
        network = []
        if with_network:
            for a in self._network_raw():
                if isinstance(a, dict) and a.get("hex") and a["hex"].lower() not in heard:
                    network.append(self.label(a, "network"))
            aircraft += network

        def in_ring(x):
            if not home or not isinstance(x.get("lat"), (int, float)) or not isinstance(x.get("lon"), (int, float)):
                return False
            return _nm(home[0], home[1], x["lat"], x["lon"]) <= RING_NM

        return {"now": round(_now(), 1),
                "counts": {"heard": sum(1 for x in aircraft if x["source"] == "antenna" and in_ring(x)),
                           "notHeard": sum(1 for x in network if in_ring(x)) if with_network else None},
                "aircraft": aircraft}


FEED = None


class Handler(http.server.BaseHTTPRequestHandler):
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30
    server_version = "StratoScan"
    sys_version = ""

    def version_string(self):
        return "StratoScan"

    def _send(self, code, body, ctype="application/json"):
        raw = json.dumps(body, separators=(",", ":")).encode() if not isinstance(body, bytes) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path != "/api/aircraft":
            return self._send(404, {"error": "not found"})
        q = urllib.parse.parse_qs(url.query)
        try:
            self._send(200, FEED.build(with_network=q.get("network", ["0"])[0] == "1"))
        except Exception as e:  # never a traceback to a client
            print(f"core: build failed: {e}", flush=True)
            self._send(500, {"error": "unavailable"})

    do_HEAD = do_GET

    def do_POST(self):
        self._send(405, {"error": "read only"})

    do_PUT = do_DELETE = do_PATCH = do_POST

    def log_message(self, *a):
        pass


def main():
    global FEED
    FEED = Feed()
    srv = http.server.ThreadingHTTPServer(LISTEN, Handler)
    print(f"core: serving /api/aircraft on {LISTEN[0]}:{LISTEN[1]}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
