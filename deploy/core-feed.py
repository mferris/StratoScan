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
    GET /api/trails               where each aircraft has been (#84)
    GET /api/runways              the runway outlines round the radar, as
                                  offline-map.py keeps them (#87): from disk,
                                  never fetched while a screen waits

Safe to publish: no antenna-relative field (r_dst, r_dir) and no receiver
position leaves this service, so the feed can't locate the receiver; the
public gateway serves it read-only like the other stores. Aircraft positions
are what the aircraft broadcast to everyone.

Lookups (routes from adsb.im, registered owners from adsbdb for private
aircraft) run in a background thread, batched and cached in memory the way
the page did them; the feed never waits on them, it carries whatever is
known so far. Nothing is written to disk, so no SD-card wear.
"""
import hashlib
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
RUNWAYS_FILE = os.environ.get("STRATOSCAN_RUNWAYS_FILE", "/var/www/html/offline-map/runways.geojson")
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
# How long the decoder may say nothing before the connection is made again. A
# quiet 978 band is normal (RDU has decoded nothing at all), and every
# reconnect costs two "accepted a connection" lines in the journal: at 120 s
# that was ~1,150 lines a day, ~70 MB of SD card writes (2026-10-16). A
# decoder that restarts closes the connection, which is seen at once anyway.
UAT_IDLE_S = 3600
STALE_S = 60            # readsb keeps an aircraft this long after its last message
AIRCRAFT_CACHE_S = 1.0  # one read of aircraft.json per second, however many clients
NETWORK_CACHE_S = 60.0  # network-compare caches upstream for 60 s itself (#67)
# How long an answer waits for a refresh of the network's aircraft before it
# goes out with the last list (#86, 2026-10-26). The list is refreshed behind
# the feed, one refresh at a time: the app's poll used to wait on adsb.lol
# through network-compare, and a slow answer there failed the whole poll,
# the antenna's aircraft too.
NETWORK_WAIT_S = 2.0
# An answer network-compare marks as not its current one, "pending" (a fresh
# one is on its way) or "stale" (the last kept through a failure), or none at
# all (a 503 while it first asks, a body cut off), is asked for again after
# NETWORK_RETRY_S instead of kept for a minute. Aircraft known for longer than
# NETWORK_OLD_S are not shown at all (review, 2026-10-26): with nothing asking
# for an hour, the first answer was last night's list, which went out to the
# app as live aircraft for a minute and into the trails.
NETWORK_RETRY_S = 5.0
NETWORK_OLD_S = 120.0
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
                    s.settimeout(UAT_IDLE_S)
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


# The sighting store's counts, for each aircraft's "sightings" and the "first
# time here" reason (#77): the app shows them as the kiosk does. Its legacy
# view is the whole store, so it is asked at most once a minute.
SIGHTINGS_URL = os.environ.get("STRATOSCAN_SIGHTINGS_URL", "http://127.0.0.1:8083/sightings")
SIGHTINGS_CACHE_S = 60.0
# index.html's RARE_FIRST_MIN_CATALOGUE: until the radar has seen this many
# aircraft, "never seen here before" is true of nearly everything.
RARE_FIRST_MIN_CATALOGUE = 2000


class SightingCounts:
    """hex -> (total, nearby) from the sighting store, refreshed at most once
    a minute; the last good answer is kept through a failure.

    Refreshed behind the feed (#86, 2026-10-26): reading the whole store held
    up one feed answer a minute, the app's poll and the kiosk's included, by
    up to its time limit. Only the first answer after a start waits for it,
    and briefly, so its counts are not all zero."""

    FIRST_WAIT_S = 1.0

    def __init__(self, url=SIGHTINGS_URL):
        self.url = url
        self.counts = {}
        self.at = -1e9
        self.busy = False
        self.lock = threading.Lock()

    def get(self):
        if not LOOKUPS and self.url == SIGHTINGS_URL:
            return self.counts                # tests: no store to ask
        with self.lock:
            if self.busy or _now() - self.at < SIGHTINGS_CACHE_S:
                return self.counts
            first = self.at < 0
            self.at = _now()              # one try a minute, answered or not
            self.busy = True
        t = threading.Thread(target=self._refresh, daemon=True)
        t.start()
        if first:
            t.join(self.FIRST_WAIT_S)
        with self.lock:
            return self.counts

    def _refresh(self):
        counts = None
        try:
            with urllib.request.urlopen(self.url, timeout=3) as r:
                doc = json.load(r)
            counts = {h.lower(): (int(v.get("total") or 0), int(v.get("nearby") or 0))
                      for h, v in doc.items() if isinstance(h, str) and isinstance(v, dict)}
        except Exception:
            # The last good counts are kept, whatever went wrong. Only some
            # errors were caught at first: an answer cut off mid-body (an
            # IncompleteRead, no OSError) ended the refresh with busy still
            # set, and the counts were never refreshed again (review, 2026-10-26).
            counts = None
        finally:
            with self.lock:
                if counts is not None:
                    self.counts = counts
                self.busy = False


def band_of(a, hex_, uat):
    """'978' (decoded by this radar's 978 radio), '978 via 1090' (a 978
    aircraft re-sent on 1090 by a ground station, ADS-R), or '1090'."""
    if uat is not None and uat.heard(hex_):
        return "978"
    if str(a.get("type") or "").startswith("adsr"):
        return "978 via 1090"
    return "1090"


# ---- trails (roadmap 2.30, #84) -------------------------------------------------
# Where each aircraft has been, for a screen that has just opened. The app's
# trails started from the moment it opened while the kiosk's ran back a quarter
# of an hour (the owner's ask, 2026-10-25), so the feed keeps one per aircraft,
# from the antenna and from the network, in memory only, and serves them at
# /api/trails. Straight stretches are collapsed as they are recorded, so a long
# leg costs two points, not one every few seconds.
TRAIL_KEEP_S = 900           # as long as the app keeps one (PlaneState.historySeconds)
TRAIL_EVERY_S = 5.0          # the antenna's aircraft are sampled this often
TRAIL_STRAIGHT_NM = 0.05     # a point this close to the line through its neighbours goes,
TRAIL_LEVEL_FT = 300         # if all three are level within this: the screens colour a
                             # trail by altitude, so a climb keeps its points
TRAIL_MAX_POINTS = 400       # per aircraft, whatever it does
TRAIL_MAX_AIRCRAFT = 3000


def _straight(a, b, c):
    """Whether point b lies on the way from a to c, level: within
    TRAIL_STRAIGHT_NM of the line, and all three within TRAIL_LEVEL_FT."""
    k = math.cos(math.radians(a[1]))
    bx, by = (b[2] - a[2]) * 60 * k, (b[1] - a[1]) * 60
    cx, cy = (c[2] - a[2]) * 60 * k, (c[1] - a[1]) * 60
    span = math.hypot(cx, cy)
    if span < 1e-6:
        return False
    if abs(cx * by - cy * bx) / span > TRAIL_STRAIGHT_NM:
        return False
    along = (bx * cx + by * cy) / (span * span)
    if not 0 <= along <= 1:
        return False
    alts = (a[3], b[3], c[3])
    if None in alts:
        return a[3] == b[3] == c[3]
    return max(alts) - min(alts) <= TRAIL_LEVEL_FT


def _trail_point(a, now):
    """[time, lat, lon, altitude in feet or None] for a readsb or network
    record with a position, else None."""
    lat, lon = a.get("lat"), a.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    seen = a.get("seen_pos")
    t = now - (seen if isinstance(seen, (int, float)) and seen >= 0 else 0)
    alt = a.get("alt_baro", a.get("alt"))
    alt = 0 if alt == "ground" else (alt if isinstance(alt, (int, float)) else None)
    return [round(t, 1), round(lat, 5), round(lon, 5), alt]


class Trails:
    def __init__(self):
        self.lock = threading.Lock()
        self.d = {}           # hex -> [[t, lat, lon, alt], ...], oldest first

    def note(self, hex_, p):
        with self.lock:
            pts = self.d.get(hex_)
            if pts is None:
                if len(self.d) >= TRAIL_MAX_AIRCRAFT:
                    return
                pts = self.d[hex_] = []
            if pts:
                last = pts[-1]
                if p[0] <= last[0] or (p[1] == last[1] and p[2] == last[2]):
                    return                     # nothing new
                if len(pts) >= 2 and _straight(pts[-2], last, p):
                    pts[-1] = p                # still on the same straight line
                    return
            pts.append(p)
            if len(pts) > TRAIL_MAX_POINTS:
                del pts[0]

    def payload(self, now):
        """{"now", "trails": {hex: [[seconds ago, lat, lon, alt], ...]}} for the
        last TRAIL_KEEP_S. Ages, not times, so a screen with a different clock
        reads them right."""
        out = {}
        with self.lock:
            for h in list(self.d):
                pts = [q for q in self.d[h] if now - q[0] <= TRAIL_KEEP_S]
                if not pts:
                    del self.d[h]
                    continue
                self.d[h] = pts
                if len(pts) >= 2:
                    out[h] = [[round(now - q[0], 1), q[1], q[2], q[3]] for q in pts]
        return {"now": round(now, 1), "keepS": TRAIL_KEEP_S, "trails": out}


# ---- runway outlines (#87) ---------------------------------------------------
# offline-map.py fetches them from Overpass about once a month, for a box
# round the receiver rounded to 0.05 degrees, and keeps them on disk; the
# kiosk, the public page and the app read them here instead of each asking
# Overpass. Read from the file, never fetched while a screen waits: missing,
# or for another place (the radar has moved and the new ones aren't in yet),
# it is 404, and a screen keeps the copy it has.
RUNWAYS_MAX_AGE_S = 3600     # how long a screen may keep an answer without asking
RUNWAYS_MAX_BYTES = 32 << 20


def runway_centre(lat, lon):
    """offline-map.py's: the receiver rounded to 0.05 degrees."""
    return round(round(float(lat) * 20) / 20, 2), round(round(float(lon) * 20) / 20, 2)


class Runways:
    """The outlines file, kept in memory while it is unchanged on disk."""

    def __init__(self, path=None):
        self.path = path or RUNWAYS_FILE
        self.lock = threading.Lock()
        self.key = self.got = None

    def get(self):
        """(bytes, etag, centre) as the file has them, or None."""
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        key = (st.st_mtime_ns, st.st_size, st.st_ino)
        with self.lock:
            if key != self.key:
                try:
                    with open(self.path, "rb") as f:
                        raw = f.read(RUNWAYS_MAX_BYTES + 1)
                    if len(raw) > RUNWAYS_MAX_BYTES:
                        raise ValueError("too big")
                    lat, lon = json.loads(raw)["centre"]
                    self.got = (raw, '"%s"' % hashlib.sha256(raw).hexdigest()[:32], (float(lat), float(lon)))
                except (OSError, ValueError, KeyError, TypeError):
                    self.got = None
                self.key = key
            return self.got

    def for_place(self, home):
        """The outlines if they are for this receiver position, else None."""
        got = self.get()
        if not got or not home:
            return None
        want = runway_centre(*home)
        if abs(got[2][0] - want[0]) > 1e-6 or abs(got[2][1] - want[1]) > 1e-6:
            return None
        return got


class Feed:
    def __init__(self, lookups=None, uat=None, sightings=None, trails=True):
        self.types = labels.TypeDb()
        self.notable = labels.NotableDb()
        self.lookups = lookups or Lookups()
        self.uat = uat if uat is not None else UatHeard()
        self.sightings = sightings if sightings is not None else SightingCounts()
        self._antenna = (0.0, [])
        self._network = (0.0, [])       # (when network-compare fetched them, the network's aircraft)
        self._network_due = 0.0         # when they are asked for again
        self._network_worker = None     # the one refresh of the network's aircraft running, if any
        self.lock = threading.Lock()
        self.trails = Trails()
        self.runways = Runways()
        if trails:
            threading.Thread(target=self._trail_loop, daemon=True).start()

    def _trail_loop(self):
        """The antenna's aircraft into the trails every TRAIL_EVERY_S, whether
        or not a screen is asking: a trail is for the one that opens next."""
        while True:
            time.sleep(TRAIL_EVERY_S)
            try:
                self._note_trails(self._antenna_raw())
            except Exception as e:      # never the end of the feed
                print(f"core: trail sample failed: {e}", flush=True)

    def _note_trails(self, records):
        now = _now()
        for a in records:
            if isinstance(a, dict) and a.get("hex"):
                p = _trail_point(a, now)
                if p:
                    self.trails.note(a["hex"].lower().lstrip("~"), p)

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
        """The network's aircraft: the last list, refreshed behind the feed
        when it is due (NETWORK_CACHE_S after network-compare fetched a
        current one, NETWORK_RETRY_S after anything else). An answer waits at
        most NETWORK_WAIT_S for a refresh, then goes out with what is known,
        unless that is older than NETWORK_OLD_S."""
        with self.lock:
            at, ac = self._network
            if _now() < self._network_due:
                return ac if _now() - at < NETWORK_OLD_S else []
            worker = self._network_worker
            if worker is None:
                worker = self._network_worker = threading.Thread(target=self._refresh_network, daemon=True)
                worker.start()
        worker.join(NETWORK_WAIT_S)
        with self.lock:
            at, ac = self._network
            return ac if _now() - at < NETWORK_OLD_S else []

    def _refresh_network(self):
        ac, age, current = [], 0.0, False
        try:
            req = urllib.request.Request(NETWORK_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as r:
                doc = json.load(r)
            fetched = doc.get("fetched")            # how long ago network-compare asked adsb.lol
            age = max(0.0, float(fetched)) if isinstance(fetched, (int, float)) else 0.0
            ac = [a for a in doc.get("ac") or [] if isinstance(a, dict)]
            current = not doc.get("pending") and not doc.get("stale") and age < NETWORK_CACHE_S
        except Exception:
            # network-compare down or still asking (503), or an answer cut
            # off (an IncompleteRead, no OSError) or of the wrong shape: none
            # for now, asked again soon. Catching only some errors let a
            # refresh die still marked running, and the list was never
            # refreshed again (review, 2026-10-26).
            ac, age, current = [], 0.0, False
        finally:
            with self.lock:
                now = _now()
                self._network = (now - age, ac)
                # A current list is kept until network-compare's own copy is due again.
                self._network_due = now - age + NETWORK_CACHE_S if current else now + NETWORK_RETRY_S
                self._network_worker = None
        # The network's aircraft are fetched only while a screen shows them
        # (privacy.md), so their trails grow only then, a point per fetch.
        # Only from a current answer: an old one's points were noted when it
        # was new, or are too old to be stamped with now.
        if current:
            self._note_trails(ac)

    def label(self, a, source, counts=None):
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
        # readsb's own "type" is the message type ("adsb_icao"), never the
        # aircraft's: it was shown as one when the type database had no entry
        # (2026-10-15). network-compare.py's records do put the aircraft type
        # there (adsb.lol's "t"), so only theirs is read.
        code = info.get("type_code") or a.get("t") or (a.get("type") if source == "network" else None)
        out["type"] = {"code": code, "name": info.get("type"), "desc": info.get("desc")}
        nb = self.notable.get(hex_)
        out["notable"] = ({"category": nb[0], "label": labels.NOTABLE_LABELS.get(nb[0], nb[0])}
                          if isinstance(nb, list) and nb else None)
        # What the kiosk shows for an aircraft and the app now does too (#77):
        # its sighting counts, and the strongest reason it is notable, worked
        # out once here (labels.rare_reason, as the phone alerts are).
        total = nearby = None
        if source == "antenna" and counts is not None:
            total, nearby = counts.get(hex_, (0, 0))
            out["sightings"] = {"total": total, "nearby": nearby}
        rare = labels.rare_reason(hex_, out["type"]["code"], self.notable)
        if (rare is None and total is not None and total <= 1
                and len(counts) >= RARE_FIRST_MIN_CATALOGUE):
            rare = {"kind": "first", "label": "Never seen here before", "operator": None}
        out["rare"] = rare
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
        counts = self.sightings.get()
        aircraft = [self.label(a, "antenna", counts) for a in antenna]
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

    def _send(self, code, body, ctype="application/json", cache="no-store", etag=None):
        raw = json.dumps(body, separators=(",", ":")).encode() if not isinstance(body, bytes) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", cache)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _runways(self):
        got = FEED.runways.for_place(FEED._receiver())
        if not got:
            return self._send(404, {"error": "not built"})
        raw, etag, _ = got
        cache = f"max-age={RUNWAYS_MAX_AGE_S}"
        asked = [t.strip() for t in (self.headers.get("If-None-Match") or "").split(",")]
        if etag in asked or "*" in asked:
            self.send_response(304)       # the copy the screen has is this one
            self.send_header("Cache-Control", cache)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        return self._send(200, raw, cache=cache, etag=etag)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/api/trails":
            return self._send(200, FEED.trails.payload(_now()))
        if url.path == "/api/runways":
            return self._runways()
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
    print(f"core: serving /api/aircraft, /api/trails and /api/runways on {LISTEN[0]}:{LISTEN[1]}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
