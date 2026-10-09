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
"Network comparison" setting is on -- which is ON by default
(DEFAULT_ALERT_SETTINGS in index.html). Turning it off stops all contact.

The view beyond the ring (/network/around) comes through the relay's
shared cache when this radar reports to the relay at all (heartbeat.py:
the owner's health-reports switch): a disc is fetched from adsb.lol once
and served to every radar and phone that asks for it (performance audit
2026-10-09). For that to be the same disc, those discs are on a fixed
world lattice, not round each radar's view. The relay itself cannot ask
adsb.lol (it rate-limits Cloudflare's shared addresses), so the unit that
finds a disc missing fetches it, with its own address as always, and hands
it up for the others. The relay is never a single point of failure:
unreachable, the unit asks adsb.lol itself, as before.

GET /network      -> {"ac": [...], "stats": {...}, "source": ..., "fetched": age_s}
GET /network/stats -> just the scorecard, no upstream call
"""
import http.server
import json
import math
import os
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import heartbeat                       # the unit key and the relay's address
except Exception:                          # an image without it, or a test
    heartbeat = None

LISTEN = ("127.0.0.1", 8087)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "coverage.json")

LOCAL_AIRCRAFT = "http://127.0.0.1/tar1090/data/aircraft.json"
LOCAL_RECEIVER = "http://127.0.0.1/tar1090/data/receiver.json"

# Community-run and free. Identify ourselves rather than arriving anonymous,
# and never poll faster than MIN_UPSTREAM_S -- this is somebody's donated
# bandwidth, and the page has no reason to want fresher than this.
# A real Mode S address is 24 bits, i.e. exactly six hex digits. Anything else
# in the feed is a placeholder, not an identity -- see the ghost loop below.
ICAO_HEX = re.compile(r"[0-9a-fA-F]{6}")

SOURCE_NAME = "adsb.lol"
SOURCE_URL = "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}"
USER_AGENT = "StratoScan/1.0 (+https://github.com/mferris/StratoScan; coverage self-comparison)"
MIN_UPSTREAM_S = 15
UPSTREAM_TIMEOUT = 8
RADIUS_NM = 25          # a little beyond the 20nm ring the radar draws
RING_NM = 20            # what the radar actually shows; stats use this

MAX_BODY = 400_000
# The network round a point the radar's screen is looking at (roadmap 2.23 on
# the kiosk, 2026-10-08): what adsb.lol serves round a point, how long one
# answer is kept for the same place, and how often adsb.lol may be asked at
# all, whoever asks -- the public page can, through the gateway.
AROUND_MIN_NM, AROUND_MAX_NM = 25, 250
AROUND_CACHE_S = 10
AROUND_UPSTREAM_GAP_S = 5
AROUND_MAX_BODY = 3_000_000     # a busy 250 nm disc is well over MAX_BODY
AROUND_PLACES = 8               # answers kept at once
_around = {"cache": {}, "last_upstream": 0.0}
# A view wider than one disc (the owner's ask, 2026-10-08): several discs on
# a square grid, spaced so they leave no gap, at most 3 x 3 of them covering
# the middle of the view; the rest of a continent stays empty, and the answer
# says how far it reaches. adsb.lol is asked at most TILE_CALLS times in any
# TILE_WINDOW_S, in all, whoever asks.
TILE_NM = AROUND_MAX_NM
TILE_SPACING_NM = AROUND_MAX_NM * math.sqrt(2)
TILE_MAX_N = 3
TILE_SINGLE_UP_TO_NM = 190      # a view this far out still fits one disc (x1.3 <= 250)
TILE_WINDOW_S, TILE_CALLS = 20, 9
TILE_CACHE_S = 15
TILE_PACE_S = 1.2               # between questions: adsb.lol refuses a burst (420/429, measured)
TILE_RETRY_S = 2.5              # one more try after a refusal
TILE_DISC_FRESH_S = 45          # a disc is asked for again after this (nine take the Pi ~25 s)
TILE_KEEP_S = 120               # a disc's last answer is shown this long while a fresh one is fetched
TILE_IN_THREAD = True           # the discs are fetched in the background (tests set False)
_tiles = {"cache": {}, "discs": {}, "calls": [], "busy": set(), "fetching": False}
# The relay's shared cache, and the lattice its discs are on (see the module
# docstring). The lattice is rows of 250 nm discs every 180/LATTICE_ROWS
# degrees of latitude (about 348 nm) with as many columns as fit
# LATTICE_SPACING_NM apart at that latitude, so every point on Earth is
# inside at least one disc and never more than ~248 nm from its nearest
# centre. The relay computes the same lattice (relay/src/netcache.js) and
# refuses a disc that is not on it, so the two formulas are kept identical.
RELAY = os.environ.get("STRATOSCAN_NET_RELAY", "1") != "0"     # tests switch it off
RELAY_DISC_PATH = "/v1/net/disc/{lat}/{lon}"
RELAY_TIMEOUT = 9
RELAY_PACE_S = 0.2              # between discs the relay already has
RELAY_CALLS = 40                # per TILE_WINDOW_S: most are the relay's, not adsb.lol's
RELAY_WAIT_S = 2.0              # while another radar is fetching the disc for everyone
LATTICE_R_NM = AROUND_MAX_NM
LATTICE_SPACING_NM = TILE_SPACING_NM
LATTICE_ROWS = math.ceil(10800 / LATTICE_SPACING_NM)     # 31, pole to pole
LATTICE_ROW_STEP = 180 / LATTICE_ROWS
LATTICE_MAX_DISCS = 16          # a continent-wide view; 9 view-centred discs reach as far
LATTICE_SLACK_NM = 2            # a view is "inside" a disc with this to spare, never on its rim

# Altitude bands, in feet. Chosen to separate a horizon problem from a
# sensitivity one: if the low bands are the weak ones the antenna is being
# blocked, and no amount of gain fixes that.
ALT_BANDS = [(0, 2000), (2000, 6000), (6000, 15000), (15000, 99000)]
BRG_BINS = 12           # 30-degree sectors
WINDOW_S = 24 * 3600    # scorecard covers a rolling day

lock = threading.Lock()
_cache = {"at": 0.0, "payload": None}
# The scorecard lives in memory and is written at most every FLUSH_INTERVAL,
# plus on shutdown. It used to be rewritten on every upstream fetch (every
# ~15 s, ~4,300 times a day) -- steady SD-card wear for a rolling one-day
# scorecard whose last few minutes are worth nothing after a power cut.
FLUSH_INTERVAL = 600
_store = None
_dirty = False


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
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STORE_PATH)   # atomic: a torn scorecard is worse than a stale one


def current():
    """The in-memory scorecard. Caller must hold `lock`."""
    global _store
    if _store is None:
        _store = load_store() or fresh_store()
    return _store


def flush():
    global _dirty
    with lock:
        if not _dirty or _store is None:
            return
        save_store(_store)
        _dirty = False


def _flusher():
    while True:
        time.sleep(FLUSH_INTERVAL)
        try:
            flush()
        except OSError as e:
            print(f"network-compare: flush failed: {e}", file=sys.stderr, flush=True)


def _shutdown(signum, frame):
    flush()
    sys.exit(0)


def fresh_store():
    return {
        "since": time.time(),
        "samples": 0,
        "heard": 0, "network": 0,
        "alt": {band_label(*b): [0, 0] for b in ALT_BANDS},
        "brg": {str(i): [0, 0] for i in range(BRG_BINS)},
        "age_mine": [], "age_net": [],
    }


def get_json(url, timeout=6, limit=MAX_BODY):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(limit).decode("utf-8", "replace"))


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
    global _store, _dirty
    with lock:
        # fold() may hand back a brand-new store when the day window rolls
        # over, so keep whatever it returns rather than mutating in place.
        _store = fold(current(), mine, theirs)
        _dirty = True
        card = scorecard(_store)

    # Only the aircraft this receiver did NOT hear are worth sending: the
    # page already has its own, and shipping duplicates would invite the
    # display to prefer network data over local, which is the opposite of
    # what this radar is for.
    ghosts = []
    for hexid, (a, r, b) in theirs.items():
        if hexid in mine:
            continue
        # A ghost is keyed by hex for its whole life -- the track that carries
        # its trail, its photo, its owner lookup and its sighting count. The
        # feed occasionally carries a target with a placeholder address rather
        # than a real 24-bit ICAO one, and every such target collapses into a
        # single track: one card on the radar reading "00000000 / SEEN x3",
        # merging unrelated aircraft and attributing a real registered owner
        # to an address that identifies nobody. Drop them rather than show a
        # confident answer assembled from several different aeroplanes.
        if not ICAO_HEX.fullmatch(hexid or ""):
            continue
        ghosts.append(ghost_entry(hexid, a))
    return {"ac": ghosts, "mine": len(mine), "network": len(theirs),
            "stats": card, "source": SOURCE_NAME, "at": time.time()}


def ghost_entry(hexid, a):
    """A network aircraft as the page draws it. The panel shows a ghost the
    same fields it shows a local contact, so the same fields have to survive
    this projection. baro_rate is the primary vertical rate for the same
    reason readsb prefers it; geom_rate is the fallback when a transponder
    only reports the GNSS-derived one."""
    return {
        "hex": hexid,
        "flight": (a.get("flight") or "").strip() or None,
        "lat": a.get("lat"), "lon": a.get("lon"),
        "alt": a.get("alt_baro"),
        "gs": a.get("gs"), "track": a.get("track"),
        "seen_pos": a.get("seen_pos"),
        "type": a.get("t"), "reg": a.get("r"),
        "squawk": a.get("squawk"),
        "vrate": a.get("baro_rate") if a.get("baro_rate") is not None
                 else a.get("geom_rate"),
        "emergency": a.get("emergency"),
        "category": a.get("category"),
    }


def relay_on():
    """Whether the discs come through the relay: its switch is health reports."""
    if not RELAY or heartbeat is None:
        return False
    try:
        return bool(heartbeat.relay_on())
    except Exception:
        return False


def lattice_cols(lat):
    return max(1, math.ceil(21600 * math.cos(math.radians(lat)) / LATTICE_SPACING_NM))


def lattice_centre(lat, lon):
    """The lattice centre whose cell holds (lat, lon): the nearest one."""
    k = min(LATTICE_ROWS - 1, max(0, math.floor((lat + 90) / LATTICE_ROW_STEP)))
    clat = -90 + (k + 0.5) * LATTICE_ROW_STEP
    n = lattice_cols(clat)
    dlon = 360 / n
    j = math.floor((lon + 180) / dlon) % n
    return round(clat, 4), round(-180 + (j + 0.5) * dlon, 4)


def lattice_centres(lat, lon, within_nm):
    """Lattice centres within `within_nm` of a point, nearest first:
    [(distance, lat, lon)]."""
    out, seen = [], set()
    rows = int(within_nm / 60 / LATTICE_ROW_STEP) + 2
    k0 = math.floor((lat + 90) / LATTICE_ROW_STEP)
    for k in range(max(0, k0 - rows), min(LATTICE_ROWS, k0 + rows + 1)):
        clat = -90 + (k + 0.5) * LATTICE_ROW_STEP
        n = lattice_cols(clat)
        dlon = 360 / n
        span = int(within_nm / (60 * max(0.05, math.cos(math.radians(clat)))) / dlon) + 2
        j0 = math.floor((lon + 180) / dlon)
        for j in range(j0 - span, j0 + span + 1):
            c = (round(clat, 4), round(-180 + ((j % n) + 0.5) * dlon, 4))
            if c in seen:
                continue
            seen.add(c)
            d, _ = haversine(lat, lon, c[0], c[1])
            if d <= within_nm:
                out.append((d, c[0], c[1]))
    out.sort()
    return out


def plan_discs(lat, lon, half, lattice):
    """Where to ask for a view `half` nm out from its middle, and how far
    the answer reaches: [(lat, lon, radius)], reach.

    Round the view (adsb.lol asked directly): one disc of the view's own
    radius while it fits, else the n x n grid of view_discs(). On the
    lattice (through the relay): the one disc that holds the whole view
    when there is one, else the nearest discs that between them cover it,
    at most LATTICE_MAX_DISCS; the reach is what they are sure to cover.
    """
    want = max(AROUND_MIN_NM, min(AROUND_MAX_NM, half * 1.3))
    if not lattice:
        if half <= TILE_SINGLE_UP_TO_NM:
            return [(lat, lon, int(want))], int(want)
        return view_discs(lat, lon, half)
    if half > TILE_SINGLE_UP_TO_NM:
        want = min(half * 1.3, TILE_MAX_N * TILE_SPACING_NM / 2)    # as far as the grid reached
    cands = lattice_centres(lat, lon, want + LATTICE_R_NM)
    if cands and cands[0][0] <= LATTICE_R_NM - LATTICE_SLACK_NM - want:
        return [(cands[0][1], cands[0][2], LATTICE_R_NM)], int(want)
    chosen = cands[:LATTICE_MAX_DISCS]
    reach = want
    if len(cands) > LATTICE_MAX_DISCS:
        # every centre within reach + 250 is in, so the first left out bounds it
        reach = min(want, cands[LATTICE_MAX_DISCS][0] - LATTICE_R_NM - LATTICE_SLACK_NM)
    return [(c[1], c[2], LATTICE_R_NM) for c in chosen], int(max(AROUND_MIN_NM, reach))


def view_discs(lat, lon, half):
    """Where to ask for a view `half` nm out from its middle: one disc round
    the middle while it fits, else an n x n grid of 250 nm discs (n <= 3)
    covering the middle; and the radius that covers."""
    if half <= TILE_SINGLE_UP_TO_NM:
        r = int(max(AROUND_MIN_NM, min(AROUND_MAX_NM, half * 1.3)))
        return [(lat, lon, r)], r
    n = max(2, min(TILE_MAX_N, math.ceil(2 * half / TILE_SPACING_NM)))
    discs = []
    for j in range(n):
        for i in range(n):
            east = (i - (n - 1) / 2) * TILE_SPACING_NM
            north = (j - (n - 1) / 2) * TILE_SPACING_NM
            discs.append((round(lat + north / 60, 2),
                          round(lon + east / (60 * math.cos(math.radians(lat))), 2), int(TILE_NM)))
    return discs, int(n * TILE_SPACING_NM / 2)


def _direct_disc(d):
    """adsb.lol itself: one more try after a refusal (420/429/503)."""
    for attempt in (1, 2):
        try:
            return get_json(SOURCE_URL.format(lat=d[0], lon=d[1], radius=d[2]),
                            timeout=UPSTREAM_TIMEOUT, limit=AROUND_MAX_BODY)
        except urllib.error.HTTPError as e:
            if attempt == 1 and e.code in (420, 429, 503):
                time.sleep(TILE_RETRY_S)
                continue
            return None
        except (urllib.error.URLError, OSError, ValueError):
            return None
    return None


def _relay_disc(d):
    """The relay's cache: the same disc every other radar gets. Not there
    yet, the relay says who fetches it: this unit, which then hands it up
    for the others, or another radar already on it, in which case wait a
    moment and ask again. Anything else -- the relay unreachable, not
    serving this unit, or saying to slow down -- adsb.lol itself, as
    before: that costs adsb.lol one question from this address, which is
    what it always got."""
    path = RELAY_DISC_PATH.format(lat=d[0], lon=d[1])
    for attempt in range(3):
        try:
            status, raw = heartbeat.relay_fetch("GET", path, timeout=RELAY_TIMEOUT, limit=AROUND_MAX_BODY)
        except (OSError, ValueError):
            break
        if status == 200:
            if len(raw) > AROUND_MAX_BODY:
                break
            try:
                return json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                break
        if status != 404:
            break
        try:
            why = json.loads(raw.decode("utf-8", "replace") or "{}")
        except ValueError:
            why = {}
        if why.get("fetching") and attempt < 2:
            time.sleep(RELAY_WAIT_S)
            continue
        net = _direct_disc(d)
        if why.get("fetch") and isinstance(net, dict):
            _share_disc(path, net)
        return net
    return _direct_disc(d)


def _share_disc(path, net):
    """Hand a disc this unit fetched up to the relay for the others. Best
    effort: a failure costs nothing but the sharing."""
    try:
        heartbeat.relay_fetch("PUT", path, json.dumps(net, separators=(",", ":")).encode(),
                              timeout=RELAY_TIMEOUT, limit=4096)
    except Exception:
        pass


def fetch_disc(d, lattice):
    """One disc's aircraft as the page draws them, or None."""
    net = _relay_disc(d) if lattice else _direct_disc(d)
    if not isinstance(net, dict):
        return None
    entries = []
    for a in net.get("ac", []):
        if not isinstance(a, dict) or a.get("lat") is None or a.get("lon") is None:
            continue
        hexid = str(a.get("hex", "")).strip().lower()
        if ICAO_HEX.fullmatch(hexid):
            entries.append(ghost_entry(hexid, a))
    return entries


def _fetch_discs(need, now, lattice=False):
    """One question at a time, a pause between them, one more try after a
    refusal; a disc that still won't answer keeps its last answer or stays
    missing. Runs in the background: nine paced questions take about twenty
    seconds, longer than the gateway's patience, so the answer to the page
    never waits for them (tiles_payload)."""
    try:
        _fetch_discs_inner(need, now, lattice)
    finally:
        with lock:
            for d in need:
                _tiles["busy"].discard(d)
            _tiles["fetching"] = False


def tiles_payload(lat, lon, half, now=None, lattice=None):
    """The network's aircraft over a view: every disc of plan_discs() the
    unit has an answer for, merged by hex, AT ONCE -- with the discs it is
    still fetching counted as pending, so the page asks again soon and the
    picture fills in. A disc's answer is kept TILE_DISC_FRESH_S before it is
    fetched again (a single disc on the lattice, AROUND_CACHE_S: it is the
    everyday zoomed-out view), shown TILE_KEEP_S meanwhile. Questions stay
    within the window; when the window is used up and nothing is known yet,
    None (429). On the lattice, the answer is what falls within the reach.
    The one disc a lattice view needs is fetched before answering, like a
    disc round the view used to be; several are fetched behind."""
    now = time.time() if now is None else now
    lattice = relay_on() if lattice is None else lattice
    discs, covered = plan_discs(lat, lon, half, lattice)
    key = ("view", round(round(lat * 20) / 20, 2), round(round(lon * 20) / 20, 2), len(discs), covered, lattice)
    fresh_s = AROUND_CACHE_S if lattice and len(discs) == 1 else TILE_DISC_FRESH_S
    keep_s = AROUND_CACHE_S if lattice and len(discs) == 1 else TILE_CACHE_S
    with lock:
        hit = _tiles["cache"].get(key)
        if hit and now - hit[0] < keep_s:
            out = dict(hit[1]); out["fetched"] = round(now - hit[0], 1)
            return out
        _tiles["calls"] = [t for t in _tiles["calls"] if now - t < TILE_WINDOW_S]
        need = [d for d in discs
                if not (_tiles["discs"].get(d) and now - _tiles["discs"][d][0] < fresh_s)
                and d not in _tiles["busy"]]
        room = (RELAY_CALLS if lattice else TILE_CALLS) - len(_tiles["calls"])
        # One paced stream of questions at a time: a second worker beside
        # the first would be the burst adsb.lol refuses.
        if _tiles["fetching"] and TILE_IN_THREAD:
            need = []
        need = need[:max(0, room)]
        _tiles["calls"].extend([now] * len(need))
        _tiles["busy"].update(need)
        if need:
            _tiles["fetching"] = True
        pending = [d for d in discs if d in _tiles["busy"]]
    if need:
        if TILE_IN_THREAD and not (lattice and len(need) == 1 and len(discs) == 1):
            threading.Thread(target=_fetch_discs, args=(need, now, lattice), daemon=True).start()
        else:
            _fetch_discs(need, now, lattice)
            pending = []
    merged = {}
    answered = 0
    with lock:
        for d in discs:
            kept = _tiles["discs"].get(d)
            if kept and now - kept[0] < TILE_KEEP_S:
                answered += 1
                for e in kept[1]:
                    merged.setdefault(e["hex"], e)
    if not answered and not pending:
        return None
    ac = list(merged.values())
    if lattice:
        ac = [e for e in ac if haversine(lat, lon, e["lat"], e["lon"])[0] <= covered]
    payload = {"ac": ac, "centre": {"lat": key[1], "lon": key[2]},
               "covered": covered, "discs": len(discs), "answered": answered, "pending": len(pending),
               "partial": answered < len(discs), "source": SOURCE_NAME,
               "via": "relay" if lattice else "direct", "at": now}
    if answered == len(discs) and not pending:      # only a whole, settled view is worth keeping
        with lock:
            if len(_tiles["cache"]) >= AROUND_PLACES:
                _tiles["cache"].clear()
            _tiles["cache"][key] = (now, payload)
    out = dict(payload); out["fetched"] = 0.0
    return out


def _fetch_discs_inner(need, now, lattice=False):
    for i, d in enumerate(need):
        if i:
            time.sleep(RELAY_PACE_S if lattice else TILE_PACE_S)
        entries = fetch_disc(d, lattice)
        with lock:
            _tiles["busy"].discard(d)        # pending counts only what is still to come
            if entries is None:
                continue
            if len(_tiles["discs"]) >= max(TILE_MAX_N * TILE_MAX_N, LATTICE_MAX_DISCS) * 2:
                _tiles["discs"].clear()
            # stamped when it lands (a fake clock in the tests): what "fresh" counts from
            _tiles["discs"][d] = (time.time() if TILE_IN_THREAD else now, entries)


def around_payload(lat, lon, radius, now=None):
    """The network's aircraft round a point: for the radar's screen when its
    view is panned or zoomed out past the ring. The point is rounded to 0.05
    degrees before it leaves the unit (as the app does; it is a place on a
    map, not anyone's location) and the radius clamped to what adsb.lol
    serves. One answer is kept per place for AROUND_CACHE_S, and adsb.lol is
    asked at most every AROUND_UPSTREAM_GAP_S, whoever asks: a question that
    can't be asked yet gets that place's last answer, marked stale, or None
    (429 to the caller)."""
    now = time.time() if now is None else now
    key = (round(round(lat * 20) / 20, 2), round(round(lon * 20) / 20, 2),
           int(max(AROUND_MIN_NM, min(AROUND_MAX_NM, radius))))
    with lock:
        hit = _around["cache"].get(key)
        if hit and now - hit[0] < AROUND_CACHE_S:
            out = dict(hit[1]); out["fetched"] = round(now - hit[0], 1)
            return out
        if now - _around["last_upstream"] < AROUND_UPSTREAM_GAP_S:
            if hit:
                out = dict(hit[1]); out["fetched"] = round(now - hit[0], 1); out["stale"] = True
                return out
            return None
        _around["last_upstream"] = now
    net = get_json(SOURCE_URL.format(lat=key[0], lon=key[1], radius=key[2]),
                   timeout=UPSTREAM_TIMEOUT, limit=AROUND_MAX_BODY)
    ghosts = []
    for a in net.get("ac", []):
        if a.get("lat") is None or a.get("lon") is None:
            continue
        hexid = str(a.get("hex", "")).strip().lower()
        if not ICAO_HEX.fullmatch(hexid):
            continue
        ghosts.append(ghost_entry(hexid, a))
    payload = {"ac": ghosts, "centre": {"lat": key[0], "lon": key[1]}, "radius": key[2],
               "source": SOURCE_NAME, "at": now}
    with lock:
        if len(_around["cache"]) >= AROUND_PLACES:
            _around["cache"].clear()
        _around["cache"][key] = (now, payload)
    out = dict(payload); out["fetched"] = 0.0
    return out


class Handler(http.server.BaseHTTPRequestHandler):
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30
    protocol_version = "HTTP/1.1"

    def version_string(self):
        return "StratoScan"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass        # the page moved on before the answer arrived; not an error here

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/network/stats":
            with lock:
                card = scorecard(current())
            return self._json(200, {"stats": card, "source": SOURCE_NAME})
        if path == "/network/around":
            q = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
            try:
                lat = float(q.get("lat", [""])[0]); lon = float(q.get("lon", [""])[0])
                radius = float(q.get("r", ["25"])[0])
                half = float(q["half"][0]) if "half" in q else None     # the view's reach: tiles if wide
            except (ValueError, IndexError):
                return self._json(400, {"error": "lat, lon, r and half must be numbers"})
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and radius == radius):
                return self._json(400, {"error": "lat or lon out of range"})
            try:
                lattice = relay_on()
                if lattice or (half is not None and half > TILE_SINGLE_UP_TO_NM):
                    out = tiles_payload(lat, lon, min(half if half is not None else radius / 1.3, 100000.0),
                                        lattice=lattice)
                else:
                    out = around_payload(lat, lon, half * 1.3 if half is not None else radius)
            except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
                return self._json(503, {"error": "upstream unavailable", "detail": type(e).__name__})
            if out is None:
                return self._json(429, {"error": "asked too often; try again in a few seconds"})
            return self._json(200, out)
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
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    threading.Thread(target=_flusher, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(LISTEN, Handler)
    srv.daemon_threads = True
    srv.serve_forever()


if __name__ == "__main__":
    main()
