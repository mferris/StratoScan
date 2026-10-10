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
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import labels  # noqa: E402
try:
    import heartbeat  # noqa: E402   the unit key and the relay's address
except Exception:                   # an image without it, or a test
    heartbeat = None

LISTEN = ("127.0.0.1", int(os.environ.get("STRATOSCAN_CORE_PORT", "8088")))
AIRCRAFT_JSON = os.environ.get("STRATOSCAN_AIRCRAFT_JSON", "/run/readsb/aircraft.json")
RECEIVER_JSON = os.environ.get("STRATOSCAN_RECEIVER_JSON", "/run/readsb/receiver.json")
NETWORK_URL = os.environ.get("STRATOSCAN_NETWORK_URL", "http://127.0.0.1:8087/network")
ROUTE_API = os.environ.get("STRATOSCAN_ROUTE_API", "https://adsb.im/api/0/routeset")
OWNER_API = os.environ.get("STRATOSCAN_OWNER_API", "https://api.adsbdb.com/v0/aircraft/{hex}")
LOOKUPS = os.environ.get("STRATOSCAN_CORE_LOOKUPS", "1") != "0"   # tests switch them off
# Routes and owners come through the relay's shared cache when this radar
# reports to the relay at all (heartbeat.py: the owner's health-reports
# switch): a callsign's route and an aircraft's owner are the same for
# every radar, so the relay asks adsb.im and adsbdb once for all of them
# (performance audit 2026-10-09). The relay answers in their own shapes.
# Anything but an answer -- unreachable, not serving this unit, the
# service refusing the relay -- and the feed asks them itself, which costs
# them one question from this address, as before.
RELAY = os.environ.get("STRATOSCAN_NET_RELAY", "1") != "0"
RELAY_ROUTES_PATH = "/v1/net/routes"
RELAY_OWNER_PATH = "/v1/net/owner/{hex}"
USER_AGENT = "StratoScan/1.0 (+https://github.com/mferris/StratoScan; core feed)"

RING_NM = 20            # what the radar draws; counts use it, as the kiosk's do
# Which band each aircraft was heard on (2026-10-10). readsb turns 978 MHz
# (UAT) messages into 1090-style ones before merging them, so its own list
# cannot say which came from where; the 978 decoder's JSON output can, so
# this listens to it and remembers each address it decoded for UAT_KEEP_S.
# An aircraft readsb tags ADS-R ("adsr_icao") is a 978 aircraft too, re-sent
# on 1090 by a ground station. Nothing listening on the port (no 978 radio,
# or it is switched off) is normal: every aircraft is then 1090.
UAT_JSON = ("127.0.0.1", int(os.environ.get("STRATOSCAN_UAT_JSON_PORT", "30979")))
UAT_KEEP_S = 90
UAT_RETRY_S = 30
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


def relay_on():
    if not RELAY or heartbeat is None:
        return False
    try:
        return bool(heartbeat.relay_on())
    except Exception:
        return False


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
        routes = None
        if relay_on():
            try:
                status, raw = heartbeat.relay_fetch("POST", RELAY_ROUTES_PATH, body, timeout=10, limit=1 << 20)
                if status == 200:
                    routes = json.loads(raw.decode("utf-8", "replace"))
            except (OSError, ValueError):
                pass         # anything but an answer: ask adsb.im ourselves
        if routes is None:
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

    @staticmethod
    def _owner_result(d):
        a = ((d if isinstance(d, dict) else {}).get("response") or {}).get("aircraft") or {}
        owner = a.get("registered_owner")
        return "found", ({"name": owner, "country": a.get("registered_owner_country_name")} if owner else None)

    def _owner(self, hex_):
        """adsbdb's registered owner of one aircraft, through the relay when
        this radar reports to it, else from adsbdb: (state, result), the
        state 'found', 'absent' (not in the registry: remember that) or
        'failed' (ask again later)."""
        if relay_on():
            try:
                status, raw = heartbeat.relay_fetch("GET", RELAY_OWNER_PATH.format(hex=hex_), timeout=8, limit=65536)
                if status == 200:
                    return self._owner_result(json.loads(raw.decode("utf-8", "replace")))
                if status == 404:
                    return "absent", None
            except (OSError, ValueError):
                pass                       # anything but an answer: ask adsbdb ourselves
        req = urllib.request.Request(OWNER_API.format(hex=hex_), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                return self._owner_result(json.load(r))
        except urllib.error.HTTPError as e:
            return ("absent", None) if e.code == 404 else ("failed", None)
        except (OSError, ValueError):
            return "failed", None

    def _flush_owners(self):
        with self.lock:
            batch = list(self.owner_queue)[:10]
            self.owner_queue.difference_update(batch)
        for hex_ in batch:
            state, result = self._owner(hex_)
            with self.lock:
                if state == "failed":
                    self.owner_failed[hex_] = _now()
                    continue
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


class UatHeard:
    """Addresses the 978 MHz decoder has decoded lately, from its JSON port."""

    def __init__(self, start=True):
        self.seen = {}
        self.lock = threading.Lock()
        if start and LOOKUPS:
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                with socket.create_connection(UAT_JSON, timeout=10) as s:
                    s.settimeout(120)
                    buf = b""
                    while True:
                        d = s.recv(65536)
                        if not d:
                            break
                        buf += d
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            self.note(line)
            except OSError:
                pass                       # no decoder running: every aircraft is 1090
            time.sleep(UAT_RETRY_S)

    def note(self, line):
        try:
            m = json.loads(line)
        except ValueError:
            return
        a = m.get("address") if isinstance(m, dict) else None
        if isinstance(a, str) and len(a) == 6:
            with self.lock:
                self.seen[a.lower()] = _now()

    def heard(self, hex_):
        with self.lock:
            t = self.seen.get(hex_)
            if t is None:
                return False
            if _now() - t > UAT_KEEP_S:
                self.seen.pop(hex_, None)
                return False
            return True


def band_of(a, hex_, uat):
    """'978' (decoded by this radar's 978 radio), '978 via 1090' (a 978
    aircraft re-sent on 1090 by a ground station, ADS-R), or '1090'."""
    if uat is not None and uat.heard(hex_):
        return "978"
    if str(a.get("type") or "").startswith("adsr"):
        return "978 via 1090"
    return "1090"


class Feed:
    def __init__(self, lookups=None, uat=None):
        self.types = labels.TypeDb()
        self.notable = labels.NotableDb()
        self.lookups = lookups or Lookups()
        self.uat = uat if uat is not None else UatHeard()
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
        if source == "antenna":
            out["band"] = band_of(a, hex_, self.uat)
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
                           "notHeard": sum(1 for x in network if in_ring(x)) if with_network else None,
                           "on978": sum(1 for x in aircraft if x.get("band", "").startswith("978") and in_ring(x))},
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
