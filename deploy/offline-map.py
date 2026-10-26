#!/usr/bin/env python3
"""
Offline fallback basemap: the vector tiles and fonts covering this unit's
radar area, stored on the device and served by lighttpd at /offline-map/.

Why: the live map depends on a single free service (tiles.openfreemap.org).
If it is down, the kiosk shows a blank disc; if it disappears -- likely at
some point in a ten-year life -- the map is gone for good. With this extract
on disk the page falls back to a local style (see OFFLINE_MAP in index.html)
and keeps drawing roads, water, towns and labels with no internet at all.

Where the data comes from: Protomaps' daily OpenStreetMap builds, published
as one PMTiles archive for the whole planet (~140 GB). PMTiles is designed to
be read in pieces over HTTP range requests, so only this area's few hundred
tiles are downloaded -- a few MB, once per location. The reader below is the
PMTiles v3 spec implemented directly (header, varint directories, Hilbert
tile IDs), so the device needs no extra binaries.

When it runs:
  build LAT LON  setupd.py starts this, in the background, whenever the
                 location is registered or changed.
  ensure         net-watchdog.py runs this when online. It rebuilds only if
                 the stored map does not match the receiver's location (a
                 build that failed, e.g. set up before WiFi worked), is over a
                 year old, and has not failed in the last few hours.

Runway outlines (#87, 2026-10-26) are kept here too, in runways.geojson,
and core-feed.py hands them to the kiosk, the public page and the app at
/api/runways. Each of those used to ask OpenStreetMap's Overpass service
itself, the kiosk with the antenna's exact position, and the app waited on
it. Both commands fetch them as well, when there are none, they are a
month old, or they are for somewhere else; an ensure whose map is current
fetches only them.

Privacy: the tiles cover an area around the house, and the directory is
reachable through the public Funnel like the rest of the web root. So the
centre is rounded to 2 decimal places (~1 km) before anything is built or
stored -- the same precision funnel-gateway.py already publishes -- and
setupd's "Erase everything" deletes the directory. The runways' box is
centred on the receiver rounded to 0.05 degrees (~5 km), as the app's is,
and widened to cover the ring anyway.
"""
import concurrent.futures
import datetime
import gzip
import json
import math
import os
import shutil
import struct
import sys
import time
import urllib.parse
import urllib.request

WEB_ROOT = os.environ.get("STRATOSCAN_WEB_ROOT", "/var/www/html")
OUT_DIR = os.path.join(WEB_ROOT, "offline-map")
STATE_DIR = os.environ.get("STRATOSCAN_OFFLINE_STATE", "/var/lib/stratoscan-offline-map")
FAILED_STAMP = os.path.join(STATE_DIR, "last-failure")
RECEIVER_JSON = "/run/readsb/receiver.json"

BUILDS_URL = "https://build-metadata.protomaps.dev/builds.json"
BUILD_BASE = "https://build.protomaps.com/"
FONT_BASE = "https://protomaps.github.io/basemaps-assets/fonts/"
FONTSTACKS = ("Noto Sans Regular", "Noto Sans Italic")
USER_AGENT = ("StratoScan/1.0 (+https://github.com/mferris/StratoScan; "
              "one-time offline map extract for a home ADS-B display)")

# Radius (nm) fetched at each zoom. The radar is a fixed 20 nm disc, which
# lands at zoom ~8-11 depending on screen size and latitude (the 1080px kiosk
# at 36N is ~9.9; a phone through Funnel ~8.3). Low zooms get a wide margin
# because they cost a handful of tiles; the detailed ones only need the disc
# plus its corners. Vector tiles are 512 px, so MapLibre asks for
# floor(zoom): even a large monitor at zoom ~10.6 wants z10. z11 is headroom;
# anything closer overzooms it, which vector data does without blurring. A
# z12 layer was tried and was ~45% of the download for tiles never requested.
RADIUS_BY_ZOOM = {z: 80 for z in range(0, 9)}
RADIUS_BY_ZOOM.update({9: 60, 10: 45, 11: 32})
MAX_ZOOM = max(RADIUS_BY_ZOOM)
MAX_TILES = 4000            # a sanity bound, far above any real area
REBUILD_AFTER_S = 365 * 86400
RETRY_AFTER_FAILURE_S = 6 * 3600
PRECISION = 2               # decimal places; see "Privacy" above

# Runway outlines (see the docstring). The query is the one the kiosk made,
# for a box 22.5 nm each way: the 20 nm ring and 2.5 nm for the rounding, as
# the app's RunwayClient.roundingPadNm.
RUNWAYS_FILE = os.path.join(OUT_DIR, "runways.geojson")
RUNWAYS_FAILED_STAMP = os.path.join(STATE_DIR, "runways-last-failure")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_USER_AGENT = ("StratoScan/1.0 (+https://github.com/mferris/StratoScan; "
                       "runway outlines for a home ADS-B display, once a month)")
RUNWAY_RADIUS_NM = 22.5
RUNWAY_STEP = 20            # the centre is rounded to 1/20 degree (0.05, ~5 km)
RUNWAYS_REFRESH_S = 30 * 86400
RUNWAYS_RETRY_S = 3600      # after Overpass failed: a shared, often busy service
RUNWAYS_EMPTY_RETRY_S = 86400   # after it found none: there may truly be none
RUNWAYS_TIMEOUT_S = 30      # the whole question, answer and all
RUNWAYS_MAX_BYTES = 32 << 20
RUNWAYS_SOURCE = "OpenStreetMap via Overpass"
RUNWAYS_LICENCE = "ODbL 1.0, © OpenStreetMap contributors"


def log(msg):
    print(f"offline-map: {msg}", flush=True)


# ---- HTTP -----------------------------------------------------------------

def fetch(url, byte_range=None, timeout=30, attempts=3):
    headers = {"User-Agent": USER_AGENT}
    if byte_range:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if byte_range and len(data) != byte_range[1] - byte_range[0] + 1:
                raise IOError(f"short read: {len(data)} bytes")
            return data
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise IOError(f"{url}: {last}")


def latest_build():
    try:
        builds = json.loads(fetch(BUILDS_URL, timeout=20))
        keys = sorted(b["key"] for b in builds if str(b.get("key", "")).endswith(".pmtiles"))
        if keys:
            return BUILD_BASE + keys[-1]
    except Exception as e:
        log(f"build list unavailable ({e}); probing recent dates")
    # The list is a convenience; the archives themselves are named by date.
    today = datetime.date.today()
    for back in range(1, 15):
        name = (today - datetime.timedelta(days=back)).strftime("%Y%m%d") + ".pmtiles"
        try:
            fetch(BUILD_BASE + name, (0, 6), attempts=1)
            return BUILD_BASE + name
        except Exception:
            continue
    raise IOError("no Protomaps build reachable")


# ---- PMTiles v3 -------------------------------------------------------------

HEADER = struct.Struct("<7sB11Q4B2B4iB2i")


def read_header(url):
    h = HEADER.unpack(fetch(url, (0, 126)))
    if h[0] != b"PMTiles" or h[1] != 3:
        raise ValueError("not a PMTiles v3 archive")
    return {
        "root": (h[2], h[3]), "leaf_off": h[6], "data_off": h[8],
        "internal_comp": h[14], "tile_comp": h[15], "tile_type": h[16],
        "max_zoom": h[18],
    }


def decompress(data, kind):
    if kind in (0, 1):          # unknown / none
        return data
    if kind == 2:
        return gzip.decompress(data)
    raise ValueError(f"unsupported compression {kind}")


def read_varint(buf, pos):
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def parse_directory(buf):
    n, pos = read_varint(buf, 0)
    ids, runs, lengths, offsets = [], [], [], []
    last = 0
    for _ in range(n):
        v, pos = read_varint(buf, pos)
        last += v
        ids.append(last)
    for _ in range(n):
        v, pos = read_varint(buf, pos)
        runs.append(v)
    for _ in range(n):
        v, pos = read_varint(buf, pos)
        lengths.append(v)
    for i in range(n):
        v, pos = read_varint(buf, pos)
        # 0 means "immediately after the previous entry" (clustered archives)
        offsets.append(offsets[i - 1] + lengths[i - 1] if v == 0 and i > 0 else v - 1)
    return list(zip(ids, runs, offsets, lengths))


def zxy_to_tileid(z, x, y):
    acc = ((1 << (2 * z)) - 1) // 3      # tiles in every zoom below z
    n = 1 << z
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if x & s else 0
        ry = 1 if y & s else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:                      # rotate the quadrant
            if rx == 1:
                x, y = n - 1 - x, n - 1 - y
            x, y = y, x
        s >>= 1
    return acc + d


class Archive:
    def __init__(self, url):
        self.url = url
        self.h = read_header(url)
        self._dirs = {}

    def _directory(self, offset, length):
        key = (offset, length)
        if key not in self._dirs:
            raw = fetch(self.url, (offset, offset + length - 1))
            self._dirs[key] = parse_directory(decompress(raw, self.h["internal_comp"]))
        return self._dirs[key]

    def locate(self, tile_id):
        """(absolute offset, length) of a tile's bytes, or None if absent."""
        offset, length = self.h["root"]
        for _ in range(4):               # root + up to 3 leaf levels
            entries = self._directory(offset, length)
            lo, hi, found = 0, len(entries) - 1, None
            while lo <= hi:              # last entry with id <= tile_id
                mid = (lo + hi) // 2
                if entries[mid][0] <= tile_id:
                    found, lo = entries[mid], mid + 1
                else:
                    hi = mid - 1
            if found is None:
                return None
            eid, run, off, ln = found
            if run == 0:                 # a pointer to a leaf directory
                offset, length = self.h["leaf_off"] + off, ln
                continue
            if tile_id < eid + run:
                return self.h["data_off"] + off, ln
            return None
        return None


# ---- area ---------------------------------------------------------------

def tile_range(lat, lon, radius_nm, z):
    dlat = radius_nm / 60.0
    dlon = radius_nm / (60.0 * max(0.05, math.cos(math.radians(lat))))
    n = 1 << z

    def tx(lo):
        return min(n - 1, max(0, int((lo + 180.0) / 360.0 * n)))

    def ty(la):
        la = max(-85.0511, min(85.0511, la))
        r = math.radians(la)
        return min(n - 1, max(0, int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)))

    return range(tx(lon - dlon), tx(lon + dlon) + 1), range(ty(lat + dlat), ty(lat - dlat) + 1)


def wanted_tiles(lat, lon):
    out = []
    for z, radius in RADIUS_BY_ZOOM.items():
        xs, ys = tile_range(lat, lon, radius, z)
        out.extend((z, x, y) for x in xs for y in ys)
    return out


# ---- MVT strings (to know which glyph ranges the labels need) -------------

def _fields(buf):
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            _, pos = read_varint(buf, pos)
        elif wire == 1:
            pos += 8
        elif wire == 5:
            pos += 4
        elif wire == 2:
            ln, pos = read_varint(buf, pos)
            yield field, buf[pos:pos + ln]
            pos += ln
        else:
            return


# Only what the fallback style draws. `landuse` -- every field, plot and
# industrial estate -- was ~40% of Amsterdam's extract on its own; the much
# lighter `landcover` (woods, grass) gives the same sense of terrain at the
# radar's scale. Buildings, POIs and transit are never visible on a 20 nm disc.
KEEP_LAYERS = {b"earth", b"water", b"landcover", b"roads", b"places",
               b"boundaries"}


def _encode_varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def filter_tile(tile):
    """The tile with every layer outside KEEP_LAYERS removed.

    A vector tile is just a sequence of length-prefixed layers (field 3), so
    dropping one is dropping its bytes -- no re-encoding of geometry.
    """
    out = bytearray()
    for f, layer in _fields(tile):
        if f != 3:
            continue
        lname = next((v for k, v in _fields(layer) if k == 1), b"")
        if lname in KEEP_LAYERS:
            out += b"\x1a" + _encode_varint(len(layer)) + layer
    return bytes(out)


def _packed(buf):
    pos, out = 0, []
    while pos < len(buf):
        v, pos = read_varint(buf, pos)
        out.append(v)
    return out


def mvt_strings(tile, key=b"name"):
    """The `name` values in the label-bearing layers of a vector tile.

    Only the tag the style actually draws: the tiles also carry translations
    in dozens of languages (name:ja, name:ar, ...), and fetching glyphs for
    all of those tripled the download for labels that are never shown.
    """
    out = set()
    for f, layer in _fields(tile):
        if f != 3:
            continue
        parts = list(_fields(layer))
        lname = next((v for k, v in parts if k == 1), b"")
        if lname not in (b"places", b"water"):
            continue
        keys = [v for k, v in parts if k == 3]
        values = [v for k, v in parts if k == 4]
        if key not in keys:
            continue
        want = keys.index(key)
        for k, feature in parts:
            if k != 2:
                continue
            for fk, fv in _fields(feature):
                if fk != 2:
                    continue
                tags = _packed(fv)
                for i in range(0, len(tags) - 1, 2):
                    if tags[i] == want and tags[i + 1] < len(values):
                        for vk, vv in _fields(values[tags[i + 1]]):
                            if vk == 1:
                                out.add(vv.decode("utf-8", "replace"))
    return out


# ---- build --------------------------------------------------------------

def round_home(lat, lon):
    return round(float(lat), PRECISION), round(float(lon), PRECISION)


def build(lat, lon):
    lat, lon = round_home(lat, lon)
    url = latest_build()
    log(f"building for {lat},{lon} from {url.rsplit('/', 1)[-1]}")
    arc = Archive(url)
    if arc.h["tile_type"] != 1:
        raise ValueError("archive is not vector tiles")

    tiles = wanted_tiles(lat, lon)
    if len(tiles) > MAX_TILES:
        raise ValueError(f"{len(tiles)} tiles is more than this should ever need")
    located = []
    for z, x, y in tiles:
        where = arc.locate(zxy_to_tileid(z, x, y))
        if where:
            located.append(((z, x, y), where))

    # One request per run of neighbouring tiles rather than one per tile: the
    # archive is clustered by Hilbert order, so a small area is mostly a few
    # contiguous stretches. Kind to the host, and much faster on a Pi.
    located.sort(key=lambda t: t[1][0])
    groups = []
    for key, (off, ln) in located:
        if groups and off - groups[-1]["end"] <= 64 * 1024 and \
                off + ln - groups[-1]["start"] <= 4 * 1024 * 1024:
            g = groups[-1]
            g["end"] = max(g["end"], off + ln)
        else:
            groups.append({"start": off, "end": off + ln, "tiles": []})
            g = groups[-1]
        g["tiles"].append((key, off, ln))

    staging = OUT_DIR + ".new"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    strings = set()

    def fetch_group(g):
        blob = fetch(url, (g["start"], g["end"] - 1))
        out = []
        for (z, x, y), off, ln in g["tiles"]:
            data = decompress(blob[off - g["start"]:off - g["start"] + ln], arc.h["tile_comp"])
            out.append(((z, x, y), filter_tile(data)))
        return out

    written = total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(fetch_group, groups):
            for (z, x, y), data in result:
                path = os.path.join(staging, "tiles", str(z), str(x), f"{y}.pbf")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
                written += 1
                total += len(data)
                if z >= 9:
                    strings |= mvt_strings(data)

    # Labels are drawn from glyph ranges of 256 code points. Fetch exactly the
    # ranges this area's names use -- Latin for Raleigh or Amsterdam, but CJK
    # or Cyrillic too if that is what the local names are written in.
    # Always: Basic Latin + Latin-1, Latin Extended-A (Polish, Czech, Turkish
    # ...) and General Punctuation (dashes, curly quotes) -- a few KB each,
    # and a label whose glyph range is missing is dropped outright.
    ranges = {0, 1, 32}
    for s in strings:
        ranges.update(ord(c) // 256 for c in s)
    for stack in FONTSTACKS:
        for r in sorted(ranges):
            name = f"{r * 256}-{r * 256 + 255}.pbf"
            try:
                data = fetch(FONT_BASE + urllib.request.quote(stack) + "/" + name, timeout=20)
            except IOError:
                continue            # a missing range costs some labels, not the map
            path = os.path.join(staging, "fonts", stack, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            total += len(data)

    meta = {
        "lat": lat, "lon": lon, "source": url.rsplit("/", 1)[-1],
        "built": int(time.time()), "minzoom": 0, "maxzoom": MAX_ZOOM,
        "tiles": written, "bytes": total,
        "attribution": "© OpenStreetMap contributors · Protomaps",
    }
    with open(os.path.join(staging, "meta.json"), "w") as f:
        json.dump(meta, f)
    for root, dirs, files in os.walk(staging):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)
        for n in files:
            os.chmod(os.path.join(root, n), 0o644)
    os.chmod(staging, 0o755)

    carry_runways(staging)

    # Swap whole directories, so a viewer never sees half of one area and
    # half of another, and a failed build leaves the previous map in place.
    old = OUT_DIR + ".old"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.exists(OUT_DIR):
        os.rename(OUT_DIR, old)
    os.rename(staging, OUT_DIR)
    shutil.rmtree(old, ignore_errors=True)
    try:
        os.unlink(FAILED_STAMP)
    except OSError:
        pass
    log(f"done: {written} tiles, {len(ranges)} glyph ranges, {total / 1e6:.1f} MB")
    return meta


def current_meta():
    try:
        with open(os.path.join(OUT_DIR, "meta.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def receiver_location():
    with open(RECEIVER_JSON) as f:
        d = json.load(f)
    return float(d["lat"]), float(d["lon"])


def needs_build(now=None):
    """(lat, lon) to build for, or None if the stored map is right."""
    now = now or time.time()
    try:
        lat, lon = round_home(*receiver_location())
    except (OSError, ValueError, KeyError, TypeError):
        return None                 # no location yet: nothing to build
    meta = current_meta()
    if meta and (meta.get("lat"), meta.get("lon")) == (lat, lon) and \
            now - meta.get("built", 0) < REBUILD_AFTER_S:
        return None
    try:
        if now - os.path.getmtime(FAILED_STAMP) < RETRY_AFTER_FAILURE_S:
            return None
    except OSError:
        pass
    return lat, lon


# ---- runway outlines (#87) -------------------------------------------------

def runway_centre(lat, lon):
    """The receiver rounded to 0.05 degrees: all that leaves the radar."""
    return (round(round(float(lat) * RUNWAY_STEP) / RUNWAY_STEP, 2),
            round(round(float(lon) * RUNWAY_STEP) / RUNWAY_STEP, 2))


def runway_bbox(centre, radius_nm=RUNWAY_RADIUS_NM):
    """(south, west, north, east) radius_nm round centre: index.html's rangeBBox."""
    lat, lon = centre
    m = radius_nm * 1852
    dlat = m / 111320
    dlon = m / (111320 * math.cos(math.radians(lat)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def overpass_query(centre):
    bb = ",".join(f"{v:.5f}" for v in runway_bbox(centre))
    return (f'[out:json][timeout:25];(way["aeroway"="runway"]({bb});'
            f'way["aeroway"="taxiway"]({bb}););out body;>;out skel qt;')


def ask_overpass(centre):
    """Overpass's answer for the box round centre, within RUNWAYS_TIMEOUT_S
    in all: the socket's limit is per read, so the read has a deadline too."""
    body = urllib.parse.urlencode({"data": overpass_query(centre)}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=body, method="POST", headers={
        "User-Agent": OVERPASS_USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"})
    end = time.monotonic() + RUNWAYS_TIMEOUT_S
    raw = bytearray()
    with urllib.request.urlopen(req, timeout=RUNWAYS_TIMEOUT_S) as r:
        while len(raw) <= RUNWAYS_MAX_BYTES:
            if time.monotonic() > end:
                raise IOError(f"Overpass took longer than {RUNWAYS_TIMEOUT_S} s")
            chunk = r.read1(1 << 16)
            if not chunk:
                break
            raw += chunk
    if len(raw) > RUNWAYS_MAX_BYTES:
        raise IOError("Overpass answered more than expected")
    return json.loads(bytes(raw).decode("utf-8", "replace"))


def overpass_to_geojson(elements):
    """index.html's overpassToGeoJSON: each runway and taxiway as a line,
    a way with fewer than two of its points known left out."""
    nodes = {el.get("id"): [el["lon"], el["lat"]] for el in elements
             if isinstance(el, dict) and el.get("type") == "node" and "lat" in el and "lon" in el}
    features = []
    for el in elements:
        if not isinstance(el, dict) or el.get("type") != "way" or not el.get("tags"):
            continue
        aeroway = el["tags"].get("aeroway")
        if aeroway not in ("runway", "taxiway"):
            continue
        coords = [nodes[i] for i in el.get("nodes") or [] if i in nodes]
        if len(coords) < 2:
            continue
        features.append({"type": "Feature", "properties": {"aeroway": aeroway, "ref": el["tags"].get("ref") or ""},
                         "geometry": {"type": "LineString", "coordinates": coords}})
    return {"type": "FeatureCollection", "features": features}


def current_runways():
    try:
        with open(RUNWAYS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def runways_due(centre, now=None):
    """Whether the stored outlines need fetching for centre: there are none,
    they are a month old, or they are for somewhere else."""
    now = now or time.time()
    cur = current_runways()
    try:
        same = [round(float(x), 2) for x in cur["centre"]] == list(centre)
        age = now - os.path.getmtime(RUNWAYS_FILE)
    except (OSError, TypeError, KeyError, ValueError):
        return True
    return not same or age >= RUNWAYS_REFRESH_S


def needs_runways(now=None):
    """The rounded centre to fetch outlines for, or None: none due, no
    location yet, or a recent failure (an hour; a day after an empty answer)."""
    now = now or time.time()
    try:
        centre = runway_centre(*receiver_location())
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not runways_due(centre, now):
        return None
    try:
        with open(RUNWAYS_FAILED_STAMP) as f:
            wait = int(f.read().strip() or RUNWAYS_RETRY_S)
        if now - os.path.getmtime(RUNWAYS_FAILED_STAMP) < wait:
            return None
    except (OSError, ValueError):
        pass
    return centre


def write_runways(doc):
    """runways.geojson, whole or not at all: a temporary file, then renamed."""
    os.makedirs(OUT_DIR, exist_ok=True)
    os.chmod(OUT_DIR, 0o755)
    tmp = RUNWAYS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, separators=(",", ":"), ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, RUNWAYS_FILE)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def build_runways(centre):
    """Fetch and store the outlines round centre (already rounded). An
    empty answer is not stored: it is asked again a day later."""
    answer = ask_overpass(centre)
    # A busy Overpass can answer 200 with what it managed before giving up,
    # saying so in a remark; that is kept a month, so it is a failure here.
    if "error" in str(answer.get("remark") or "").lower():
        raise IOError(f"Overpass: {str(answer['remark'])[:120]}")
    geo = overpass_to_geojson(answer.get("elements") or [])
    if not geo["features"]:
        _runways_failed(RUNWAYS_EMPTY_RETRY_S)
        log(f"no runways found round {centre[0]},{centre[1]}; asking again in a day")
        return None
    geo.update(centre=list(centre), radiusNm=RUNWAY_RADIUS_NM,
               built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               source=RUNWAYS_SOURCE, licence=RUNWAYS_LICENCE)
    write_runways(geo)
    try:
        os.unlink(RUNWAYS_FAILED_STAMP)
    except OSError:
        pass
    log(f"runways: {len(geo['features'])} outlines round {centre[0]},{centre[1]}")
    return geo


def _runways_failed(wait_s):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(RUNWAYS_FAILED_STAMP, "w") as f:
            f.write(str(int(wait_s)))
    except OSError:
        pass


def carry_runways(staging):
    """A rebuilt map's directory replaces the old one whole: the outlines
    go with it, rather than vanishing until the next fetch."""
    if os.path.exists(RUNWAYS_FILE):
        shutil.copy2(RUNWAYS_FILE, os.path.join(staging, os.path.basename(RUNWAYS_FILE)))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "ensure"
    if cmd == "build" and len(argv) == 4:
        target = (float(argv[2]), float(argv[3]))
        # A new location: its outlines now, whatever an earlier failure said.
        runways = runway_centre(*target)
        if not runways_due(runways):
            runways = None
    elif cmd == "ensure":
        target = needs_build()
        runways = needs_runways()
    else:
        print("usage: offline-map.py build LAT LON | ensure", file=sys.stderr)
        return 2
    ok = True
    if target is not None:
        try:
            build(*target)
        except Exception as e:
            log(f"build failed: {type(e).__name__}: {e}")
            shutil.rmtree(OUT_DIR + ".new", ignore_errors=True)
            try:
                os.makedirs(STATE_DIR, exist_ok=True)
                open(FAILED_STAMP, "w").close()
            except OSError:
                pass
            ok = False
    # Independent of the map: either may work while the other's service is down.
    if runways is not None:
        try:
            build_runways(runways)
        except Exception as e:
            log(f"runways failed: {type(e).__name__}: {e}; asking again in an hour")
            _runways_failed(RUNWAYS_RETRY_S)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
