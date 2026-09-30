#!/usr/bin/env python3
"""
Unit events: the moments worth telling a paired phone about, decided here on
the unit and sent to the StratoScan relay (relay/), which fans them out to phones.

  emergency       squawk 7500 / 7600 / 7700, at any range
  notable         a listed aircraft (plane-alert-db), a military address or a
                  notable type, within NOTABLE_RADIUS_NM
  low_overhead    within LOW_RADIUS_NM and below LOW_MAX_ALT_FT
  helicopter      a rotorcraft within HELI_RADIUS_NM

The same rules as the kiosk's own alerts (index.html): the neutral notable
labels, military ranges and notable types are copied from it, and
tests/test_events.py fails if the two ever drift apart.

Privacy. An event carries the aircraft only: identity, type, altitude, and
its distance from the unit rounded to half a nautical mile with an 8-point
compass direction. Never the unit's location or the aircraft's position; the
relay refuses any event carrying a lat/lon field. What remains is inherent to
the feature -- "a helicopter passed within 2 miles" says roughly where the
unit is to whoever reads it -- which is why the relay keeps events only long
enough to deliver them, and why this is off until the owner pairs a phone.

Nothing here can affect the radar: it only reads readsb's aircraft.json, and
if the relay is unreachable events wait in a small in-memory queue, then
expire. Nothing is written to storage while it runs.

  events.py run       the service loop (flightradar-events.service)
  events.py status    what is on, what is queued, the last send
  events.py enable    turn events on (pairing a phone does this: pairing.py)
  events.py disable   turn them off
  events.py test      send one synthetic "test" event now
  events.py test-approach   a pretend approach (and its end), to try a phone's Live Activity
"""
import collections
import glob
import gzip
import importlib.util
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
AIRCRAFT_JSON = os.environ.get("FLIGHTRADAR_AIRCRAFT_JSON", "/run/readsb/aircraft.json")
NOTABLE_JSON = os.environ.get("FLIGHTRADAR_NOTABLE_JSON", "/var/www/html/data/notable.json")
TAR1090_DB_GLOB = os.environ.get("FLIGHTRADAR_TAR1090_DB", "/usr/local/share/tar1090/html/db-*")
RUN_DIR = os.environ.get("FLIGHTRADAR_EVENTS_RUN", "/run/flightradar-events")
STATUS = os.path.join(RUN_DIR, "status.json")
# What has been reported recently, so a restart (an update, a reinstall) does
# not report the same pass again. /run: survives a service restart
# (RuntimeDirectoryPreserve=restart), never touches storage.
FIRED = os.path.join(RUN_DIR, "fired.json")

POLL_S = 5
IDLE_POLL_S = 30              # while events are off: only watch for them being turned on
STALE_S = 30                  # ignore aircraft not heard for this long

NOTABLE_RADIUS_NM = 30
LOW_RADIUS_NM = 1.738         # 2 statute miles, the kiosk's nearby-alert radius
LOW_MAX_ALT_FT = 5000
HELI_RADIUS_NM = 3.0

# Per aircraft and kind: one event per pass, not one per poll.
COOLDOWN_S = {"emergency": 30 * 60, "notable": 6 * 3600,
              "low_overhead": 30 * 60, "helicopter": 30 * 60}
COOLDOWN_S["approach"] = 30 * 60
MAX_PER_HOUR = 60             # a floor against a bad table or odd traffic; emergencies exempt

# Approaching aircraft (the phone's Live Activity, roadmap 2.4): a plane that
# qualifies (notable, helicopter or low) and, on its present speed and track,
# will pass within APPROACH_CPA_NM in the next APPROACH_WARN_S. One event
# when predicted, carrying the time to the pass (the phone counts down by
# itself), and one "approach_end" shortly after it.
APPROACH_WARN_S = 180
APPROACH_MIN_S = 20           # closer than this, the ordinary alerts already cover it
APPROACH_CPA_NM = LOW_RADIUS_NM
APPROACH_MIN_GS = 30          # kt; slower than this (hovering, taxiing) a track predicts nothing
APPROACH_END_AFTER_S = 45

QUEUE_MAX = 50
EXPIRE_S = 15 * 60            # a stale alert is worse than none
BATCH = 20
MIN_SEND_GAP_S = 5            # the relay requires each request's timestamp to advance
BACKOFF_S = (30, 60, 120, 300, 600)
TIMEOUT_S = 10

EMERGENCY_SQUAWKS = {"7500": "hijack", "7600": "radio failure", "7700": "emergency"}
# readsb's own emergency field, from the aircraft's emergency/priority status.
EMERGENCY_STATES = {"general": "emergency", "lifeguard": "medical", "minfuel": "minimum fuel",
                    "nordo": "radio failure", "unlawful": "hijack", "downed": "downed aircraft"}

# ---- copied from index.html; tests/test_events.py keeps them identical ------

MILITARY_HEX_RANGES = [
    (0x33ff00, 0x33ffff, "Italian military"),
    (0x350000, 0x37ffff, "Spanish military"),
    (0x3aa000, 0x3affff, "French military"),
    (0x3b7000, 0x3bffff, "French military"),
    (0x3ea000, 0x3ebfff, "German military"),
    (0x3f4000, 0x3fbfff, "German military"),
    (0x400000, 0x40003f, "UK military"),
    (0x43c000, 0x43cfff, "UK military"),
    (0x480000, 0x480fff, "Dutch military"),
    (0x4b7000, 0x4b7fff, "Swiss military"),
    (0xadf7c8, 0xafffff, "US military"),
    (0xc20000, 0xc3ffff, "Canadian military"),
    (0xe40000, 0xe41fff, "Brazilian military"),
]

NOTABLE_TYPES = {
    "A388": "Airbus A380", "A124": "Antonov An-124", "A225": "Antonov An-225",
    "B741": "Boeing 747", "B742": "Boeing 747", "B743": "Boeing 747",
    "B744": "Boeing 747", "B748": "Boeing 747-8", "B74S": "Boeing 747SP",
    "C17": "C-17 Globemaster", "C5M": "C-5 Galaxy", "C5": "C-5 Galaxy",
    "B52": "B-52 Stratofortress", "B1": "B-1 Lancer", "B2": "B-2 Spirit",
    "K35R": "KC-135 Stratotanker", "KC46": "KC-46 Pegasus", "KC10": "KC-10 Extender",
    "E3TF": "E-3 Sentry (AWACS)", "E3CF": "E-3 Sentry (AWACS)", "P8": "P-8 Poseidon",
    "V22": "V-22 Osprey", "U2": "U-2 Dragon Lady", "R135": "RC-135",
    "VC25": "VC-25 (Air Force One)", "C32": "C-32 (Air Force Two)",
    "DC3": "Douglas DC-3", "C47": "Douglas C-47", "B17": "B-17 Flying Fortress",
    "P51": "P-51 Mustang", "B29": "B-29 Superfortress", "SPIT": "Supermarine Spitfire",
}

# plane-alert-db's category names are in-jokes, and a few pass judgement on
# people; an event only ever carries the neutral description.
NOTABLE_LABELS = {
    "Aerial Firefighter": "Firefighting aircraft", "Aerobatic Teams": "Aerobatic display team",
    "Army Air Corps": "UK Army Air Corps", "As Seen on TV": "Company aircraft",
    "Big Hello": "Heavy helicopter", "Bizjets": "Private jet", "CAP": "Civil Air Patrol",
    "Climate Crisis": "Large business jet", "Coastguard": "Coast guard or border patrol",
    "Da Comrade": "Russian- or Soviet-built aircraft", "Dictator Alert": "VIP aircraft",
    "Distinctive": "One-of-a-kind aircraft", "Dogs with Jobs": "Special-mission aircraft",
    "Don't you know who I am?": "Aircraft of a well-known person", "Flying Doctors": "Air ambulance",
    "Football": "Sports team aircraft", "GAF": "German Air Force", "Gas Bags": "Balloon or airship",
    "Governments": "Government aircraft", "Gunship": "Attack aircraft", "Head of State": "Head of state aircraft",
    "Hired Gun": "Military contractor", "Historic": "Historic aircraft",
    "Jesus he Knows me": "Religious organisation aircraft", "Joe Cool": "Notable aircraft",
    "Jump Johnny Jump": "de Havilland Chipmunk", "Nuclear": "Nuclear emergency support",
    "Oligarch": "VIP private jet", "Other Air Forces": "Air force", "Other Navies": "Navy",
    "Oxcart": "Surveillance aircraft", "Perfectly Serviceable Aircraft": "Skydiving aircraft",
    "Police Forces": "Police aircraft", "Ptolemy would be proud": "Aerial survey aircraft",
    "Quango": "International organisation (NATO, UN…)", "Radiohead": "Presidential or VIP transport",
    "RAF": "Royal Air Force", "Royal Aircraft": "Royal Family aircraft", "Royal Navy Fleet Air Arm": "Royal Navy",
    "Special Forces": "Special operations aircraft", "Toy Soldiers": "Army aircraft", "UAV": "Drone (UAV)",
    "UK National Police Air Service": "Police aircraft (UK NPAS)", "Ukraine": "Ukrainian aircraft",
    "United States Marine Corps": "US Marine Corps", "United States Navy": "US Navy", "USAF": "US Air Force",
    "Vanity Plate": "Distinctive registration", "Watch Me Fly": "Flight school aircraft",
    "You came here in that thing?": "Microlight or very small aircraft", "Zoomies": "Fast jet",
}

COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def _heartbeat():
    """heartbeat.py owns the unit key, the relay URL and request signing."""
    spec = importlib.util.spec_from_file_location("heartbeat", os.path.join(HERE, "heartbeat.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hb = _heartbeat()
CONFIG = os.path.join(hb.STATE_DIR, "events.json")    # {"enabled": bool}


# ---- settings -----------------------------------------------------------------

def enabled():
    return bool(hb._json(CONFIG).get("enabled"))


def set_enabled(on):
    os.makedirs(hb.STATE_DIR, mode=0o700, exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"enabled": bool(on)}, f)
    os.replace(tmp, CONFIG)
    if on:
        hb.load_key(create=True)


# ---- what an aircraft is --------------------------------------------------------

def military_operator(hex_):
    try:
        v = int(hex_, 16)
    except (TypeError, ValueError):
        return None
    for lo, hi, who in MILITARY_HEX_RANGES:
        if lo <= v <= hi:
            return who
    return None


def humanize_type(s):
    return " ".join(w[0] + w[1:].lower() if w.isalpha() and w.isupper() else w for w in s.split(" "))


class TypeDb:
    """Registration and type from tar1090's on-disk aircraft database.

    The same prefix-trie of gzipped JSON shards the kiosk reads over HTTP
    (index.html lookupType). Missing or unreadable: every lookup is empty and
    events just carry less detail.
    """
    SHARD_CACHE = 8
    HEX_CACHE = 5000

    def __init__(self, pattern=TAR1090_DB_GLOB):
        dirs = sorted(glob.glob(pattern), key=lambda d: os.path.getmtime(d))
        self.dir = dirs[-1] if dirs else None
        self.shards = collections.OrderedDict()
        self.hexes = collections.OrderedDict()
        self.types = {}
        if self.dir:
            raw = self._load("icao_aircraft_types2") or {}
            for code, e in raw.items():
                if isinstance(e, list) and e:
                    self.types[code.upper()] = (e[0], e[1] if len(e) > 1 else None)

    def _load(self, name):
        try:
            with open(os.path.join(self.dir, name + ".js"), "rb") as f:
                raw = f.read()
            return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        except (OSError, ValueError, EOFError):
            return None

    def _shard(self, key):
        if key in self.shards:
            self.shards.move_to_end(key)
            return self.shards[key]
        data = self._load(key)
        self.shards[key] = data
        if len(self.shards) > self.SHARD_CACHE:
            self.shards.popitem(last=False)
        return data

    def lookup(self, hex_):
        """{"reg", "type", "type_code", "desc"}; values None when unknown."""
        hex_ = (hex_ or "").upper()
        if hex_ in self.hexes:
            return self.hexes[hex_]
        entry = None
        level = 1
        while self.dir and hex_ and level <= len(hex_):
            bkey = hex_[:level]
            data = self._shard(bkey)
            if not isinstance(data, dict):
                break
            dkey = hex_[level:]
            if dkey in data:
                entry = data[dkey]
                break
            if dkey and bkey + dkey[0] in (data.get("children") or []):
                level += 1
                continue
            break
        out = {"reg": None, "type": None, "type_code": None, "desc": None}
        if isinstance(entry, list):
            reg = entry[0] if len(entry) > 0 else None
            code = (entry[1] or "").upper() if len(entry) > 1 and entry[1] else None
            long_ = entry[3] if len(entry) > 3 else None
            meta = self.types.get(code) if code else None
            out = {"reg": reg or None, "type_code": code,
                   "type": humanize_type(long_) if long_ else (humanize_type(meta[0]) if meta and meta[0] else None),
                   "desc": meta[1] if meta else None}
        self.hexes[hex_] = out
        if len(self.hexes) > self.HEX_CACHE:
            self.hexes.popitem(last=False)
        return out


class NotableDb:
    """hex -> [category, kind, operator, type], reloaded when notable-db.py refreshes it."""

    def __init__(self, path=NOTABLE_JSON):
        self.path, self.mtime, self.ac = path, None, {}

    def get(self, hex_):
        try:
            m = os.path.getmtime(self.path)
        except OSError:
            return None
        if m != self.mtime:
            try:
                with open(self.path) as f:
                    self.ac = json.load(f).get("ac") or {}
            except (OSError, ValueError):
                self.ac = {}
            self.mtime = m
        return self.ac.get(hex_)


def is_rotorcraft(a, info):
    desc = info.get("desc")
    if desc and len(desc) == 3:
        return desc[0] in "HGT"      # helicopter, gyrocopter, tiltrotor
    return a.get("category") == "A7"


def notable_reason(a, info, notable):
    """(label, operator) for the strongest reason this aircraft is notable, or None."""
    e = notable.get(a["hex"])
    if e:
        return NOTABLE_LABELS.get(e[0], "Notable aircraft"), (e[2] or None) if len(e) > 2 else None
    mil = military_operator(a["hex"])
    if mil:
        return mil, None
    code = info.get("type_code")
    if code and code in NOTABLE_TYPES:
        return NOTABLE_TYPES[code], None
    return None


# ---- detection -----------------------------------------------------------------------

def _alt_ft(a):
    alt = a.get("alt_baro")
    if alt == "ground":
        return 0
    if isinstance(alt, (int, float)):
        return int(alt)
    alt = a.get("alt_geom")
    return int(alt) if isinstance(alt, (int, float)) else None


def closest_approach(a):
    """(seconds until closest, distance then in nm) on the present track, or None.

    Uses readsb's own distance and bearing from the antenna, so it runs only
    here on the unit; nothing positional leaves it.
    """
    d, b, gs, trk = a.get("r_dst"), a.get("r_dir"), a.get("gs"), a.get("track")
    if not all(isinstance(v, (int, float)) for v in (d, b, gs, trk)) or gs < APPROACH_MIN_GS:
        return None
    x, y = d * math.sin(math.radians(b)), d * math.cos(math.radians(b))     # nm east, north
    vx, vy = gs * math.sin(math.radians(trk)) / 3600, gs * math.cos(math.radians(trk)) / 3600
    v2 = vx * vx + vy * vy
    t = -(x * vx + y * vy) / v2
    return t, math.hypot(x + vx * t, y + vy * t)


def describe(a, info, now):
    """The aircraft part of an event: identity, type, altitude, rounded distance. No position."""
    ev = {"ts": int(now), "hex": a["hex"]}
    flight = (a.get("flight") or "").strip()
    if flight:
        ev["flight"] = flight[:8]
    for k in ("reg", "type", "type_code"):
        if info.get(k):
            ev[k] = str(info[k])[:40]
    alt = _alt_ft(a)
    if alt is not None:
        ev["alt_ft"] = int(round(alt / 100.0)) * 100
    if isinstance(a.get("r_dst"), (int, float)):
        ev["dist_nm"] = round(a["r_dst"] * 2) / 2
    if isinstance(a.get("r_dir"), (int, float)):
        ev["dir"] = COMPASS[int((a["r_dir"] % 360) / 45 + 0.5) % 8]
    return ev


class Detector:
    def __init__(self, types=None, notable=None):
        self.types = types or TypeDb()
        self.notable = notable or NotableDb()
        self.fired = {}                        # (hex, kind[, detail]) -> ts
        self.approaching = {}                  # hex -> expected time of the pass
        self.sent_times = collections.deque()  # non-emergency events in the last hour

    def save(self, path=FIRED):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump([[list(k), t] for k, t in self.fired.items()], f)
            os.replace(tmp, path)
        except OSError:
            pass

    def load(self, path=FIRED, now=None):
        now = now if now is not None else time.time()
        try:
            with open(path) as f:
                rows = json.load(f)
        except (OSError, ValueError):
            return
        horizon = max(COOLDOWN_S.values())
        for k, t in rows if isinstance(rows, list) else []:
            if isinstance(k, list) and isinstance(t, (int, float)) and now - t <= horizon:
                self.fired[tuple(k)] = t

    def _due(self, key, kind, now):
        last = self.fired.get(key)
        return last is None or now - last >= COOLDOWN_S[kind]

    def _rate_ok(self, now):
        while self.sent_times and now - self.sent_times[0] > 3600:
            self.sent_times.popleft()
        return len(self.sent_times) < MAX_PER_HOUR

    def _emit(self, out, key, kind, ev, now):
        if kind != "emergency":
            if not self._rate_ok(now):
                return
            self.sent_times.append(now)
        self.fired[key] = now
        ev["kind"] = kind
        out.append(ev)

    def _check_approach(self, out, a, info, dist, alt, now):
        hex_ = a["hex"]
        if hex_ in self.approaching or dist <= APPROACH_CPA_NM:
            return
        cpa = closest_approach(a)
        if not cpa:
            return
        t, miss = cpa
        if not (APPROACH_MIN_S <= t <= APPROACH_WARN_S and miss <= APPROACH_CPA_NM):
            return
        why = notable_reason(a, info, self.notable)
        if why:
            reason = why[0]
        elif is_rotorcraft(a, info):
            reason = "Helicopter"
        elif alt is not None and 0 < alt <= LOW_MAX_ALT_FT:
            reason = "Low overhead"
        else:
            return
        if not self._due((hex_, "approach"), "approach", now):
            return
        ev = describe(a, info, now)
        ev["label"] = reason[:60]
        ev["eta_s"] = int(round(t / 10.0)) * 10
        self._emit(out, (hex_, "approach"), "approach", ev, now)
        if self.fired.get((hex_, "approach")) == now:       # not held back by the hourly cap
            self.approaching[hex_] = now + t

    def scan(self, doc, now=None):
        """New events for one aircraft.json snapshot."""
        now = now if now is not None else time.time()
        out = []
        for a in doc.get("aircraft") or []:
            hex_ = a.get("hex")
            if not isinstance(hex_, str) or hex_.startswith("~"):    # ~ = TIS-B, no real address
                continue
            if not isinstance(a.get("seen"), (int, float)) or a["seen"] > STALE_S:
                continue
            dist = a.get("r_dst") if isinstance(a.get("r_dst"), (int, float)) else None
            alt = _alt_ft(a)

            squawk = str(a.get("squawk") or "")
            what = EMERGENCY_SQUAWKS.get(squawk) or EMERGENCY_STATES.get(a.get("emergency"))
            if what:
                key = (hex_, "emergency", squawk or a.get("emergency"))
                if self._due(key, "emergency", now):
                    ev = describe(a, self.types.lookup(hex_), now)
                    ev["label"] = what
                    if squawk in EMERGENCY_SQUAWKS:
                        ev["squawk"] = squawk
                    self._emit(out, key, "emergency", ev, now)

            if dist is None:
                continue
            near_low = dist <= LOW_RADIUS_NM and alt is not None and 0 < alt <= LOW_MAX_ALT_FT
            # Type lookups only for aircraft close enough to matter: every
            # rule below is inside NOTABLE_RADIUS_NM.
            info = self.types.lookup(hex_) if dist <= NOTABLE_RADIUS_NM else {}

            if dist <= NOTABLE_RADIUS_NM and self._due((hex_, "notable"), "notable", now):
                why = notable_reason(a, info, self.notable)
                if why:
                    ev = describe(a, info, now)
                    ev["label"] = why[0][:60]
                    if why[1]:
                        ev["operator"] = why[1][:60]
                    self._emit(out, (hex_, "notable"), "notable", ev, now)

            self._check_approach(out, a, info, dist, alt, now)

            # A helicopter nearby is a helicopter event, never also a low one.
            if dist <= HELI_RADIUS_NM and is_rotorcraft(a, info):
                if self._due((hex_, "helicopter"), "helicopter", now):
                    self._emit(out, (hex_, "helicopter"), "helicopter", describe(a, info, now), now)
            elif near_low and self._due((hex_, "low_overhead"), "low_overhead", now):
                self._emit(out, (hex_, "low_overhead"), "low_overhead", describe(a, info, now), now)

        # An approach is over shortly after its predicted pass (or if the plane
        # vanished): tell the phone, which ends the Live Activity.
        for hex_, at in list(self.approaching.items()):
            if now > at + APPROACH_END_AFTER_S:
                del self.approaching[hex_]
                out.append({"kind": "approach_end", "ts": int(now), "hex": hex_})

        # forget passes long over, so this never grows without bound
        horizon = max(COOLDOWN_S.values())
        for k in [k for k, t in self.fired.items() if now - t > horizon]:
            del self.fired[k]
        return out


# ---- sending ---------------------------------------------------------------------------

class Sender:
    def __init__(self, post=None):
        self.queue = collections.deque(maxlen=QUEUE_MAX)   # overflow drops the oldest
        self.post = post or self._post
        self.next_try = 0.0
        self.failures = 0
        self.last = None
        self.unpaired = False

    def add(self, events):
        self.queue.extend(events)

    def _post(self, events):
        key = hb.load_key(create=True)
        body = json.dumps({"v": 1, "events": events}, separators=(",", ":")).encode()
        path = "/v1/events"
        headers = {"Content-Type": "application/json",
                   "User-Agent": "StratoScan-unit/1 (+https://github.com/mferris/StratoScan)"}
        headers.update(hb.sign_headers(key, "POST", path, body))
        req = urllib.request.Request(hb.RELAY_URL.rstrip("/") + path, data=body,
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return r.status, r.read(2048)
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception as e:
            return None, type(e).__name__.encode()

    def flush(self, now=None):
        """Send what is queued, when allowed. Returns a log line or None."""
        now = now if now is not None else time.time()
        while self.queue and now - self.queue[0]["ts"] > EXPIRE_S:
            self.queue.popleft()
        if not self.queue or now < self.next_try or not hb.RELAY_URL:
            return None
        batch = [self.queue[i] for i in range(min(BATCH, len(self.queue)))]
        status, detail = self.post(batch)
        self.last = {"at": int(now), "status": status, "count": len(batch)}
        if status is not None and 200 <= status < 300:
            for _ in batch:
                self.queue.popleft()
            self.failures = 0
            self.next_try = now + MIN_SEND_GAP_S
            try:
                reply = json.loads(detail or b"{}")
            except ValueError:
                reply = {}
            if reply.get("phones") == 0:
                # The relay stored nothing: no phone is paired any more.
                self.queue.clear()
                self.unpaired = True
                return "no phone is paired with this unit; events off"
            kinds = collections.Counter(e["kind"] for e in batch)
            return "sent " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items()))
        if status in (400, 401, 413):
            # The relay refused these events as such; resending the same
            # ones cannot succeed, and must not block the ones behind them.
            for _ in batch:
                self.queue.popleft()
            self.next_try = now + MIN_SEND_GAP_S
            return f"relay refused {len(batch)} events (HTTP {status})"
        self.next_try = now + BACKOFF_S[min(self.failures, len(BACKOFF_S) - 1)]
        self.failures += 1
        why = f"HTTP {status}" if status else detail.decode(errors="replace")
        return f"send failed ({why}); {len(self.queue)} queued, retrying"


def write_status(detector, sender, on):
    try:
        os.makedirs(RUN_DIR, exist_ok=True)
        tmp = STATUS + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"at": int(time.time()), "enabled": on, "queued": len(sender.queue),
                       "last_send": sender.last, "tracked": len(detector.fired)}, f)
        os.replace(tmp, STATUS)
    except OSError:
        pass


def config_mtime():
    try:
        return os.path.getmtime(CONFIG)
    except OSError:
        return None


class Service:
    """The run loop, one tick at a time (testable without sleeping).

    The service's sandbox makes storage read-only (flightradar-events.service,
    ProtectSystem=strict), so it never writes the on/off setting itself. When
    the relay says no phone is paired it pauses instead, until the setting
    changes: pairing.py, via setupd, owns that file and rewrites it when a
    phone pairs again.
    """

    def __init__(self, detector=None, sender=None):
        self.detector = detector or Detector()
        self.sender = sender or Sender()
        self.last_mtime = None
        self.paused_at = False      # config mtime when paused; False = not paused

    def tick(self):
        on = enabled()
        if self.paused_at is not False and config_mtime() != self.paused_at:
            self.paused_at = False  # the setting was rewritten: a phone paired again
        active = on and self.paused_at is False
        if active:
            try:
                m = os.path.getmtime(AIRCRAFT_JSON)
                if m != self.last_mtime:
                    self.last_mtime = m
                    with open(AIRCRAFT_JSON) as f:
                        doc = json.load(f)
                    new = self.detector.scan(doc)
                    if new:
                        self.detector.save()
                    for e in new:
                        print(f"events: {e['kind']} {e.get('flight') or e['hex']}"
                              f" {e.get('label', '')}".rstrip(), flush=True)
                    self.sender.add(new)
            except (OSError, ValueError):
                pass    # readsb mid-write or restarting; next poll
            line = self.sender.flush()
            if line:
                print(f"events: {line}", flush=True)
            if self.sender.unpaired:
                self.sender.unpaired = False
                self.sender.queue.clear()
                self.paused_at = config_mtime()
                print("events: paused until a phone is paired", flush=True)
                active = False
        else:
            self.sender.queue.clear()
        write_status(self.detector, self.sender, active)
        return POLL_S if active else IDLE_POLL_S


def run():
    svc = Service()
    svc.detector.load()
    print(f"events: watching {AIRCRAFT_JSON}; relay {hb.RELAY_URL or '(none)'}", flush=True)
    while True:
        time.sleep(svc.tick())


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "run":
        run()
        return 0
    if cmd == "status":
        print(json.dumps({"enabled": enabled(), "relay": hb.RELAY_URL or None,
                          "service": hb._json(STATUS) or None}, indent=1))
        return 0
    if cmd in ("enable", "disable"):
        set_enabled(cmd == "enable")
        print(f"events {cmd}d")
        return 0
    if cmd == "test":
        sender = Sender()
        sender.add([{"kind": "test", "ts": int(time.time()), "label": "Test event from this unit"}])
        print(sender.flush() or "nothing sent (no relay configured)")
        return 0 if sender.last and sender.last["status"] and 200 <= sender.last["status"] < 300 else 1
    if cmd == "test-approach":
        # A pretend aircraft "passing in 90 s", then its end, through the real
        # path: relay, Apple, the phone's Live Activity. For checking a phone
        # works without waiting for real traffic.
        sender = Sender()
        now = int(time.time())
        sender.add([{"kind": "approach", "ts": now, "hex": "abcdef", "flight": "TEST1",
                     "type": "Test aircraft", "label": "Test approach", "alt_ft": 2000,
                     "dist_nm": 4.0, "dir": "N", "eta_s": 90}])
        print(sender.flush() or "nothing sent (no relay configured)")
        if not (sender.last and sender.last["status"] and 200 <= sender.last["status"] < 300):
            return 1
        print("ending it in 100 s...", flush=True)
        time.sleep(100)
        sender.next_try = 0
        sender.add([{"kind": "approach_end", "ts": int(time.time()), "hex": "abcdef"}])
        print(sender.flush() or "end not sent")
        return 0
    print("usage: events.py run|status|enable|disable|test|test-approach", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
