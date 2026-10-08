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

  events.py run       the service loop (stratoscan-events.service)
  events.py status    what is on, what is queued, the last send
  events.py enable    turn events on (pairing a phone does this: pairing.py)
  events.py disable   turn them off
  events.py test      send one synthetic "test" event now
  events.py test-approach   a pretend approach (and its end), to try a phone's Live Activity
"""
import collections
import importlib.util
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from labels import (MILITARY_HEX_RANGES, NOTABLE_TYPES, NOTABLE_LABELS,  # noqa: E402
                    military_operator, humanize_type, TypeDb, NotableDb)
AIRCRAFT_JSON = os.environ.get("STRATOSCAN_AIRCRAFT_JSON", "/run/readsb/aircraft.json")
# The core feed (core-feed.py) knows each flight's route, looked up once there
# (adsb.im); an alert leads with the type and where it is going (#59). Asked
# only while an event is being written, at most every few seconds, and a
# feed that is down just means an alert without a route. Empty: never asked.
CORE_FEED_URL = os.environ.get("STRATOSCAN_CORE_FEED", "http://127.0.0.1:8088/api/aircraft")
RUN_DIR = os.environ.get("STRATOSCAN_EVENTS_RUN", "/run/stratoscan-events")
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
# The tables and lookups live in labels.py, the one copy shared with
# core-feed.py, so an alert can't label an aircraft differently from the
# screens. Re-exported here under their old names.

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


class Routes:
    """Where each aircraft is going, as the core feed has it: hex -> route text."""

    def __init__(self):
        self.at = 0
        self.by_hex = {}

    def get(self, hex_):
        if not CORE_FEED_URL:
            return None
        now = time.time()
        if now - self.at > 5:
            self.at = now
            try:
                with urllib.request.urlopen(CORE_FEED_URL, timeout=1.5) as r:
                    feed = json.load(r)
                self.by_hex = {
                    x["hex"]: x["route"]["text"]
                    for x in feed.get("aircraft", [])
                    if isinstance(x.get("route"), dict) and x["route"].get("text")
                    and x["route"].get("plausible") is not False
                }
            except Exception:
                pass                       # keep what we had; a route is a nicety
        return self.by_hex.get(hex_)


ROUTES = Routes()


def describe(a, info, now):
    """The aircraft part of an event: identity, type, route, altitude, rounded distance. No position."""
    ev = {"ts": int(now), "hex": a["hex"]}
    route = ROUTES.get(a["hex"])
    if route:
        ev["route"] = str(route)[:60]
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
    # Which way it's travelling (roadmap 3.4): what the aircraft broadcasts, so
    # nothing about the receiver. Lets the phone say "coming from the SW,
    # heading NE" and draw it.
    if isinstance(a.get("track"), (int, float)):
        ev["trk"] = int(round(a["track"])) % 360
    return ev


# ---- where the phones are (roadmap 2.7) ------------------------------------------
# A phone that asks for alerts about aircraft approaching *it* leaves its
# location at the relay, encrypted to this unit's X25519 "box" key, which
# only this unit can read. The key is derived from the unit's Ed25519
# identity key with HKDF -- a separate key, but one this sandboxed service
# can compute without a key file of its own -- and published to the relay
# signed by that identity, so a phone can check it against the unit id it
# scanned at pairing.
#
# A blob is base64url(ephemeral X25519 public key (32) | nonce (12) |
# ChaCha20-Poly1305 ciphertext and tag); the key is HKDF-SHA256 of the shared
# secret with info "stratoscan-location-v1" + ephemeral key + this unit's box
# key, and the phone's id is the associated data, so a blob can't be passed
# off as another phone's. Inside: {"lat", "lon", "ts"}. Decrypted positions
# stay in memory: never written, never logged, never sent.

BOX_INFO = b"stratoscan-box-v1"
LOCATION_INFO = b"stratoscan-location-v1"
BOX_KEY_CONTEXT = "stratoscan-boxkey-v1:"
LOCATION_POLL_S = 60
# While none of this unit's phones share a location, ask far less often: every
# 60 s was ~1,440 relay requests a day per radar for nothing, most of the
# relay's load. A phone that turns sharing on is picked up within this.
LOCATION_IDLE_POLL_S = 600
LOCATION_MAX_AGE_S = 6 * 3600          # older than this, it no longer says where the phone is
BOX_PUBLISH_EVERY_S = 24 * 3600
PHONE_LOOKUP_NM = 10                   # type lookups for aircraft this close to a phone


def box_private(ed_key):
    """This unit's X25519 box key, derived from its Ed25519 identity key."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    seed = ed_key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                serialization.NoEncryption())
    return X25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=BOX_INFO).derive(seed))


def box_public_raw(box_key):
    from cryptography.hazmat.primitives import serialization
    return box_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def decrypt_location(box_key, blob, phone):
    """(lat, lon, ts) from one phone's blob, or None if it isn't genuine."""
    import base64
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    try:
        raw = base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4))
        if len(raw) < 32 + 12 + 16 + 8:
            return None
        eph, nonce, sealed = raw[:32], raw[32:44], raw[44:]
        shared = box_key.exchange(X25519PublicKey.from_public_bytes(eph))
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                   info=LOCATION_INFO + eph + box_public_raw(box_key)).derive(shared)
        d = json.loads(ChaCha20Poly1305(key).decrypt(nonce, sealed, phone.encode()))
        lat, lon, ts = float(d["lat"]), float(d["lon"]), int(d["ts"])
    except (InvalidTag, ValueError, KeyError, TypeError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon, ts


def closest_approach_to(a, lat0, lon0):
    """(now nm, bearing from the point, seconds until closest, nm then) for a
    point that isn't the antenna, from the aircraft's own position and track;
    None without them. Flat-earth: fine within the few miles that matter."""
    lat, lon, gs, trk = a.get("lat"), a.get("lon"), a.get("gs"), a.get("track")
    if not all(isinstance(v, (int, float)) for v in (lat, lon, gs, trk)) or gs < APPROACH_MIN_GS:
        return None
    x = (lon - lon0) * 60 * math.cos(math.radians(lat0))      # nm east of the point
    y = (lat - lat0) * 60                                     # nm north
    vx, vy = gs * math.sin(math.radians(trk)) / 3600, gs * math.cos(math.radians(trk)) / 3600
    v2 = vx * vx + vy * vy
    t = -(x * vx + y * vy) / v2
    return math.hypot(x, y), math.degrees(math.atan2(x, y)) % 360, t, math.hypot(x + vx * t, y + vy * t)


class Detector:
    def __init__(self, types=None, notable=None):
        self.types = types or TypeDb()
        self.notable = notable or NotableDb()
        self.fired = {}                        # (hex, kind[, detail]) -> ts
        self.approaching = {}                  # hex -> expected time of the pass
        self.points = {}                       # phone id -> (lat, lon, ts): where opted-in phones are
        self.approaching_me = {}               # (hex, phone) -> expected time of the pass
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

    def _approach_reason(self, a, info, alt):
        why = notable_reason(a, info, self.notable)
        if why:
            return why[0]
        if is_rotorcraft(a, info):
            return "Helicopter"
        if alt is not None and 0 < alt <= LOW_MAX_ALT_FT:
            return "Low overhead"
        return None

    def _check_phone_approaches(self, out, a, alt, now):
        """The same rule as the radar's approach, against each phone's position."""
        hex_ = a["hex"]
        info = None
        for phone, (lat0, lon0, _) in self.points.items():
            if (hex_, phone) in self.approaching_me:
                continue
            cpa = closest_approach_to(a, lat0, lon0)
            if not cpa:
                continue
            dist, _bearing, t, miss = cpa
            if dist <= APPROACH_CPA_NM or not (APPROACH_MIN_S <= t <= APPROACH_WARN_S and miss <= APPROACH_CPA_NM):
                continue
            if info is None:
                info = self.types.lookup(hex_) if dist <= PHONE_LOOKUP_NM else {}
            reason = self._approach_reason(a, info, alt)
            key = (hex_, "approach", phone)
            if not reason or not self._due(key, "approach", now):
                continue
            ev = describe(a, info, now)
            # No distance or direction: those would be from the antenna, and
            # from the phone they'd say where it is. Which aircraft, and when.
            ev.pop("dist_nm", None)
            ev.pop("dir", None)
            ev["label"] = reason[:60]
            ev["eta_s"] = int(round(t / 10.0)) * 10
            ev["phone"] = phone
            self._emit(out, key, "approach", ev, now)
            if self.fired.get(key) == now:
                self.approaching_me[(hex_, phone)] = now + t

    def _check_phone_nearby(self, out, a, alt, now):
        """The radar's nearby rules -- notable within 30 nm, a helicopter
        within 3 nm, anything low within 2 mi -- measured from each phone's
        position as well as the antenna's (#44). The relay sends each phone
        only what it chose: the radar's, its own, or both."""
        lat, lon = a.get("lat"), a.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return
        hex_ = a["hex"]
        info = None
        for phone, (lat0, lon0, _) in self.points.items():
            d = math.hypot((lon - lon0) * 60 * math.cos(math.radians(lat0)), (lat - lat0) * 60)
            if d > NOTABLE_RADIUS_NM:
                continue
            if info is None:
                info = self.types.lookup(hex_)

            def event(label=None, operator=None):
                ev = describe(a, info, now)
                ev.pop("dist_nm", None)     # from the antenna, and from the phone they'd say where it is
                ev.pop("dir", None)
                ev["phone"] = phone
                if label:
                    ev["label"] = label[:60]
                if operator:
                    ev["operator"] = operator[:60]
                return ev

            key = (hex_, "notable", phone)
            if self._due(key, "notable", now):
                why = notable_reason(a, info, self.notable)
                if why:
                    self._emit(out, key, "notable", event(why[0], why[1]), now)
            if d <= HELI_RADIUS_NM and is_rotorcraft(a, info):
                key = (hex_, "helicopter", phone)
                if self._due(key, "helicopter", now):
                    self._emit(out, key, "helicopter", event(), now)
            elif d <= LOW_RADIUS_NM and alt is not None and 0 < alt <= LOW_MAX_ALT_FT:
                key = (hex_, "low_overhead", phone)
                if self._due(key, "low_overhead", now):
                    self._emit(out, key, "low_overhead", event(), now)

    def set_points(self, points, now=None):
        """Phone positions from the relay, newest wins; stale ones dropped."""
        now = now if now is not None else time.time()
        self.points = {p: v for p, v in points.items() if now - v[2] <= LOCATION_MAX_AGE_S}

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
            if self.points:
                self._check_phone_approaches(out, a, alt, now)
                self._check_phone_nearby(out, a, alt, now)

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
        for (hex_, phone), at in list(self.approaching_me.items()):
            if now > at + APPROACH_END_AFTER_S:
                del self.approaching_me[(hex_, phone)]
                out.append({"kind": "approach_end", "ts": int(now), "hex": hex_, "phone": phone})

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
        key = _unit_key()
        if key is None:
            return 0, b"no unit key yet (nothing has paired)"
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


def _unit_key():
    """The unit's signing key, or None before a phone has paired (pairing
    creates it, as root). The service never creates it: it runs as its own
    user with the key readable, not writable (security review 2026-10-04,
    item 1)."""
    return hb.load_key(create=False)


def relay_call(method, path, payload=None):
    """(status, parsed JSON or None) from a signed request to the relay."""
    key = _unit_key()
    if key is None:
        return None, None
    body = b"" if method == "GET" else json.dumps(payload or {}, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json",
               "User-Agent": "StratoScan-unit/1 (+https://github.com/mferris/StratoScan)"}
    headers.update(hb.sign_headers(key, method, path, body))
    req = urllib.request.Request(hb.RELAY_URL.rstrip("/") + path, data=body if method != "GET" else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.status, json.loads(r.read(65536) or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


class PhoneLocations:
    """Publishes this unit's box key, and collects its phones' positions."""

    def __init__(self, call=None):
        self.call = call or relay_call
        self.next_poll = 0.0
        self.next_publish = 0.0
        self.box = None
        self.count = 0

    def _box(self):
        if self.box is None:
            unit = _unit_key()
            if unit is None:
                return None
            self.box = box_private(unit)
        return self.box

    def publish(self):
        import base64
        box, unit = self._box(), _unit_key()
        if box is None or unit is None:
            return None
        key = base64.urlsafe_b64encode(box_public_raw(box)).rstrip(b"=").decode()
        sig = unit.sign((BOX_KEY_CONTEXT + key).encode())
        status, _ = self.call("POST", "/v1/unit/boxkey",
                              {"key": key, "sig": base64.urlsafe_b64encode(sig).rstrip(b"=").decode()})
        return status

    def tick(self, detector, now=None):
        """Poll when due. Returns a log line when something worth saying happened."""
        now = now if now is not None else time.time()
        if not hb.RELAY_URL or now < self.next_poll:
            return None
        self.next_poll = now + LOCATION_POLL_S
        line = None
        if now >= self.next_publish:
            status = self.publish()
            if status == 200:
                self.next_publish = now + BOX_PUBLISH_EVERY_S
            else:
                # an older relay (404) or a network fault: quietly, an hour on
                self.next_publish = self.next_poll = now + 3600
                return None
        status, reply = self.call("GET", "/v1/unit/locations")
        if status != 200 or not isinstance(reply, dict):
            self.next_poll = now + (3600 if status == 404 else 300)
            return None
        rows = reply.get("locations") or []
        if not rows:
            self.next_poll = now + LOCATION_IDLE_POLL_S
        points = {}
        box = self._box()
        for row in rows:
            if box is None:
                break
            if not isinstance(row, dict) or not isinstance(row.get("phone"), str) or not isinstance(row.get("blob"), str):
                continue
            fix = decrypt_location(box, row["blob"], row["phone"])
            if fix:
                points[row["phone"]] = fix
        detector.set_points(points, now)
        if len(detector.points) != self.count:
            # how many, never where
            line = f"watching for approaches to {len(detector.points)} phone(s) as well as the radar"
            self.count = len(detector.points)
        return line


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

    The service's sandbox makes storage read-only (stratoscan-events.service,
    ProtectSystem=strict), so it never writes the on/off setting itself. When
    the relay says no phone is paired it pauses instead, until the setting
    changes: pairing.py, via setupd, owns that file and rewrites it when a
    phone pairs again.
    """

    def __init__(self, detector=None, sender=None, locations=None):
        self.detector = detector or Detector()
        self.sender = sender or Sender()
        self.locations = locations or PhoneLocations()
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
            try:
                said = self.locations.tick(self.detector)
                if said:
                    print(f"events: {said}", flush=True)
            except Exception:
                pass    # approaches to phones are extra; never let them stop the alerts
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
