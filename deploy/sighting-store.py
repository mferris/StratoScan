#!/usr/bin/env python3
"""
Local-only (127.0.0.1) shared store for this receiver's flight history.

Tracks, per hex: how many distinct times this receiver has picked the
aircraft up (`t`), how many distinct times it came within the nearby-alert
radius (`n`, see ALERT_RADIUS_NM in index.html), and how many distinct times
it was seen only via the network comparison and not heard here at all (`g`).
Increments are driven client-side at the same "this is a new visit" moments
the rest of index.html already detects, not once per poll. Persisted
server-side rather than in localStorage, so the kiosk's own accumulated
history is visible to every viewer (laptop, phone, the Funnel URL), not just
whichever browser happened to be open when a plane flew by. lighttpd proxies
/sightings requests here (see 93-flightradar-sighting-store.conf).

Alongside the counts each aircraft carries a classification -- operator class
(commercial / private / military) and airframe kind (jet / heavy / prop /
helicopter / lighter-than-air) -- so the Statistics screens can answer "what
actually flies over this house" rather than only "how many". The classifying
happens on the page, where the type database and the callsign are already
resolved; this end only stores and aggregates what it is told.

  GET  /sightings        -> {"<hex>": {"total": N, "nearby": M}, ...}
                            The original shape, kept exactly: it is what the
                            radar reads on load to fill in per-plane counts,
                            and an older cached page must keep working.
  GET  /sightings/stats  -> the aggregate the Statistics screens render,
                            including hour-of-day and day-of-week histograms
                            of when aircraft actually arrive overhead.
  GET  /sightings/unclassified
                         -> {"hexes": [...]} -- aircraft with no airframe
                            recorded yet. The page can work out an airframe
                            from the hex alone (it has the type database that
                            the radar draws blip shapes from), so this is what
                            lets a history collected before classification
                            existed be filled in rather than written off.
  POST /sightings        -> body {"hex": "..."} plus any of:
                              "kind":  "total" | "nearby" | "network"
                                       -- increments that counter by one
                              "class": {"op": ..., "k": ..., "cs": ...}
                                       -- sets the aircraft's classification
                              "rec":   {"far": nm, "near": nm,
                                        "high": ft, "fast": kt}
                                       -- offers a value for each all-time
                                          record; kept only if it beats the
                                          standing one
                            Returns the updated {"total": N, "nearby": M}.
                         -> or body {"batch": [{"hex": ..., "class": {...}}, ...]}
                            to classify many at once.

The store lives in memory and is written to disk at most every
FLUSH_INTERVAL seconds, plus on shutdown. It used to be re-read and rewritten
whole on every POST: measured on the RDU unit, 3.5 GB written in 17 hours
from a file under 1 MB. At the MAX_HEXES ceiling on a busy site (SFO,
Schiphol) that pattern reaches ~100 GB/day -- a consumer SD card's whole
endurance in a year or two. The cost of batching is at most FLUSH_INTERVAL of
counts lost on a power cut, which is noise against years of history.

Multiple viewers open at once each independently detect and report the same
real sighting -- same accepted tradeoff as approach-store.py: harmless
over-counting by a point or two, not wrong. Records are the exception and
need no such tolerance: they are compare-and-keep, so the same record
offered by four viewers still lands once.
"""
import heapq
import http.server
import json
import os
import re
import signal
import sys
import threading
import time

LISTEN = ("127.0.0.1", 8083)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "sightings.json")
# A busy site (SFO, Schiphol) sees ~20k distinct airframes within weeks, so
# the cap is really an eviction policy, not headroom. 50k entries is ~5.5 MB
# on disk; with FLUSH_INTERVAL batching that is well under 1 GB/day of writes.
MAX_HEXES = 50000
# Evict down to this, not to MAX_HEXES exactly, so a full store evicts in
# occasional chunks rather than scanning all entries on every new aircraft.
EVICT_TO = MAX_HEXES - 1000
FLUSH_INTERVAL = 600
# A real body is ~40 bytes for a bare increment and ~150 with a classification
# and a record offer. Still tight: this endpoint is reachable from the public
# internet via Funnel, where the gateway allows GET and refuses writes -- this
# limit is the second line, not the first.
MAX_BODY_BYTES = 2000
HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$")

# Closed sets, not free text. Everything stored here is rendered back into the
# page, and an attacker who reached this endpoint should not be able to park
# arbitrary strings in it -- so an unrecognised class is dropped, not kept.
OPERATORS = ("com", "pri", "mil")
KINDS = ("heavy", "jet", "prop", "heli", "lta", "unknown")
COUNTERS = {"total": "t", "nearby": "n", "network": "g"}
# Each record is (key, "higher is better"). Range in nm, altitude in ft,
# ground speed in kt -- the units the page already displays.
RECORDS = {"far": True, "near": False, "high": True, "fast": True}
RECORD_LIMITS = {"far": 300.0, "near": 300.0, "high": 100000.0, "fast": 1500.0}
MAX_CS = 12  # a callsign is at most 8; the slack is for whatever a feed invents
MAX_BATCH = 400          # entries per batched write
MAX_UNCLASSIFIED = 400   # hexes handed out per request, so the page works in bounded chunks
# A batch is bigger than a single increment by design; still bounded, and the
# gateway refuses public writes regardless.
MAX_BATCH_BYTES = 64000

lock = threading.Lock()
_store = None   # loaded on first use; see current()
_dirty = False


def fresh_store():
    # `hours` is indexed by local hour, `dows` by ISO weekday (Monday = 0).
    # Both are local, deliberately: "when is it busy here" is a question about
    # this house's week, not about UTC.
    return {"v": 2, "ac": {}, "hours": [0] * 24, "dows": [0] * 7,
            "rec": {}, "since": int(time.time())}


def migrate(data):
    """Bring a store of any earlier shape up to the current one.

    v1 was a bare {hex: {total, nearby}} map with nothing else in it. Its
    counts are real history -- months of them on a unit that has been running
    a while -- so they are carried across rather than restarted. What v1 never
    recorded (classification, first/last seen, the hour histogram, the
    records) simply starts empty and fills in from live traffic.
    """
    if not isinstance(data, dict):
        return fresh_store()
    if data.get("v") == 2 and isinstance(data.get("ac"), dict):
        store = fresh_store()
        store.update(data)
        # a truncated or hand-edited file should not take the service down
        if not isinstance(store.get("hours"), list) or len(store["hours"]) != 24:
            store["hours"] = [0] * 24
        # Absent on any store written before day-of-week tracking existed --
        # not corrupt, just older. It starts empty and fills from live traffic,
        # exactly as `hours` did.
        if not isinstance(store.get("dows"), list) or len(store["dows"]) != 7:
            store["dows"] = [0] * 7
        if not isinstance(store.get("rec"), dict):
            store["rec"] = {}
        return store
    store = fresh_store()
    # v1 recorded no timestamps at all, so the day this migration ran is NOT
    # the day the history started -- a unit that has been up for months would
    # otherwise report "1 day" and turn every per-day figure into a lie.
    # Unknown until the first increment lands with a real clock behind it.
    store["since"] = None
    for hexcode, entry in data.items():
        if not HEX_RE.match(str(hexcode)) or not isinstance(entry, dict):
            continue
        store["ac"][hexcode.lower()] = {
            "t": int(entry.get("total") or 0),
            "n": int(entry.get("nearby") or 0),
        }
    return store


def load_store():
    try:
        with open(STORE_PATH) as f:
            return migrate(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return fresh_store()


def save_store(store):
    # Written whole and renamed into place: a half-written sightings.json is
    # indistinguishable from a corrupt one on the next read, and that would
    # throw away the entire accumulated history on a power cut mid-write.
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
        # Writes are now rare, so pay for durability: without this a power
        # cut shortly after the rename can leave a zero-length file on ext4.
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STORE_PATH)


def current():
    """The in-memory store. Caller must hold `lock`."""
    global _store
    if _store is None:
        _store = load_store()
    return _store


def mark_dirty():
    global _dirty
    _dirty = True


def flush():
    """Write the store if anything changed since the last write."""
    global _dirty
    with lock:
        if not _dirty or _store is None:
            return
        save_store(_store)
        _dirty = False


def evict(store):
    """Drop the least-recently-seen aircraft once the store is over its cap.

    Replaces insertion-order eviction, which (because updating a key keeps
    its position) threw out the aircraft seen FIRST -- the daily regulars --
    instead of one-off transits. Undated entries carried over from v1 have no
    `l` and go before anything with a real last-seen time.
    """
    ac = store["ac"]
    if len(ac) <= MAX_HEXES:
        return
    doomed = heapq.nsmallest(len(ac) - EVICT_TO, ac, key=lambda h: ac[h].get("l", 0))
    for h in doomed:
        del ac[h]


def _flusher():
    while True:
        time.sleep(FLUSH_INTERVAL)
        try:
            flush()
        except OSError as e:
            print(f"sighting-store: flush failed: {e}", file=sys.stderr, flush=True)


def _shutdown(signum, frame):
    flush()
    sys.exit(0)


def legacy_view(store):
    """The v1 shape, rebuilt from the current store."""
    return {h: {"total": e.get("t", 0), "nearby": e.get("n", 0)}
            for h, e in store["ac"].items()}


YEARS_KEPT = 12


def bump_year(store, entry, kind, now, first_ever):
    """Per-year aggregates for the Year-in-review screen.

    All-time totals can't answer "what was this year like", so each counted
    visit also lands in the year it happened (local time). Per-aircraft, only
    the current year's count is kept (entry["y"] = [year, visits]) -- enough
    for "most-seen this year" without a growing history per tail. At most
    YEARS_KEPT years of aggregates are kept.
    """
    local = time.localtime(now)
    year = str(local.tm_year)
    years = store.setdefault("years", {})
    y = years.get(year)
    if not isinstance(y, dict):
        y = years[year] = {"t": 0, "n": 0, "new": 0, "months": [0] * 12, "hours": [0] * 24}
        for old in sorted(years)[:-YEARS_KEPT]:
            del years[old]
    if kind == "total":
        y["t"] += 1
        y["months"][local.tm_mon - 1] += 1
        y["hours"][local.tm_hour] += 1
        if first_ever:
            y["new"] += 1
        cur = entry.get("y")
        if not (isinstance(cur, list) and len(cur) == 2 and cur[0] == local.tm_year):
            cur = [local.tm_year, 0]
        cur[1] += 1
        entry["y"] = cur
    elif kind == "nearby":
        y["n"] += 1


def year_summary(store, year=None):
    year = int(year or time.localtime().tm_year)
    y = (store.get("years") or {}).get(str(year))
    if not isinstance(y, dict):
        return {"year": year, "ready": False}
    mine = [(h, e) for h, e in store["ac"].items()
            if isinstance(e.get("y"), list) and e["y"][0] == year]
    kinds = {}
    for _, e in mine:
        k = e.get("k") if e.get("k") in KINDS else "unknown"
        kinds[k] = kinds.get(k, 0) + 1
    top = sorted(mine, key=lambda he: he[1]["y"][1], reverse=True)[:5]
    months, hours = y.get("months", [0] * 12), y.get("hours", [0] * 24)
    since = store.get("since")
    return {
        "year": year,
        "ready": True,
        "visits": y.get("t", 0),
        "nearby": y.get("n", 0),
        "newAircraft": y.get("new", 0),
        "aircraft": len(mine),
        "months": months,
        "hours": hours,
        "busiestMonth": months.index(max(months)) if any(months) else None,
        "busiestHour": hours.index(max(hours)) if any(hours) else None,
        "kinds": kinds,
        "top": [{"hex": h, "cs": e.get("cs"), "visits": e["y"][1], "k": e.get("k"), "op": e.get("op")}
                for h, e in top],
        "records": store.get("rec", {}),
        # Counting may have started partway through the year.
        "countingSince": since if since and time.localtime(since).tm_year == year else None,
    }


def _today(store):
    day = store.get("day")
    if isinstance(day, dict) and day.get("d") == time.strftime("%Y-%m-%d"):
        return {"total": int(day.get("t", 0)), "nearby": int(day.get("n", 0))}
    return {"total": 0, "nearby": 0}


def summarise(store):
    ac = store["ac"]
    by_op = {k: {"ac": 0, "visits": 0, "nearby": 0} for k in OPERATORS + ("unk",)}
    by_kind = {k: {"ac": 0, "visits": 0, "nearby": 0} for k in KINDS}
    visits = nearby = 0
    net_visits = net_only = 0
    heard = 0

    for entry in ac.values():
        t = entry.get("t", 0)
        n = entry.get("n", 0)
        g = entry.get("g", 0)
        visits += t
        nearby += n
        net_visits += g
        if t:
            heard += 1
        elif g:
            # never once heard by this antenna -- only ever seen because the
            # network comparison was on. The interesting number in the pair.
            net_only += 1
        op = entry.get("op") if entry.get("op") in OPERATORS else "unk"
        by_op[op]["ac"] += 1
        by_op[op]["visits"] += t
        by_op[op]["nearby"] += n
        kind = entry.get("k") if entry.get("k") in KINDS else "unknown"
        by_kind[kind]["ac"] += 1
        by_kind[kind]["visits"] += t
        by_kind[kind]["nearby"] += n

    top = sorted(
        ({"hex": h, "cs": e.get("cs"), "visits": e.get("t", 0),
          "op": e.get("op"), "k": e.get("k")}
         for h, e in ac.items() if e.get("t", 0) > 0),
        key=lambda r: r["visits"], reverse=True)[:6]

    since = store.get("since")
    days = max(1, round((time.time() - since) / 86400)) if since else None
    # Aircraft carried over from v1, which stored counts but never a date.
    # Their visits are real and counted; only their timing is unknown, and
    # the Statistics screens say so rather than quietly averaging over a
    # window that does not cover them.
    undated = sum(1 for e in ac.values() if "f" not in e)
    return {
        "since": since,
        "days": days,
        "undated": undated,
        "aircraft": len(ac),
        "heard": heard,
        "visits": visits,
        "nearby": nearby,
        "networkVisits": net_visits,
        "networkOnly": net_only,
        "byOp": by_op,
        "byKind": by_kind,
        "hours": store.get("hours", [0] * 24),
        "dows": store.get("dows", [0] * 7),
        "records": store.get("rec", {}),
        "today": _today(store),
        "top": top,
    }


def apply_class(entry, payload):
    op = payload.get("op")
    if op in OPERATORS:
        entry["op"] = op
    kind = payload.get("k")
    if kind in KINDS:
        entry["k"] = kind
    cs = payload.get("cs")
    if isinstance(cs, str):
        cs = cs.strip()[:MAX_CS]
        # only characters a real callsign or registration uses, so nothing
        # rendered back into the page can carry markup
        if re.fullmatch(r"[A-Za-z0-9\-]{1,%d}" % MAX_CS, cs):
            entry["cs"] = cs.upper()


def apply_records(store, hexcode, entry, payload):
    for key, higher_is_better in RECORDS.items():
        value = payload.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        value = float(value)
        # A feed glitch can report an aircraft at 300,000 ft or 4,000 kt, and
        # an all-time record is exactly the place a single bad sample does
        # permanent damage -- it never gets averaged away.
        if not (0 < value <= RECORD_LIMITS[key]):
            continue
        current = store["rec"].get(key)
        if current is not None:
            standing = current.get("v")
            if isinstance(standing, (int, float)):
                if higher_is_better and value <= standing:
                    continue
                if not higher_is_better and value >= standing:
                    continue
        store["rec"][key] = {
            "v": round(value, 1),
            "hex": hexcode,
            "cs": entry.get("cs"),
            "at": int(time.time()),
        }


class Handler(http.server.BaseHTTPRequestHandler):
    def version_string(self):
        return "FlightRadar"

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/sightings"
        # Built under the lock (handlers run on separate threads and a POST
        # may be mutating the same dicts), sent after releasing it.
        if path == "/sightings/stats":
            with lock:
                payload = summarise(current())
            return self._json(200, payload)
        if path == "/sightings/year":
            from urllib.parse import parse_qs, urlparse
            q = (parse_qs(urlparse(self.path).query).get("y") or [""])[0]
            year = int(q) if q.isdigit() and 2000 <= int(q) <= 2100 else None
            with lock:
                payload = year_summary(current(), year)
            return self._json(200, payload)
        if path == "/sightings/unclassified":
            with lock:
                hexes = [h for h, e in current()["ac"].items() if not e.get("k")]
            return self._json(200, {"hexes": hexes[:MAX_UNCLASSIFIED],
                                    "remaining": max(0, len(hexes) - MAX_UNCLASSIFIED)})
        if path != "/sightings":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            payload = legacy_view(current())
        self._json(200, payload)

    def _do_batch(self, entries):
        if not isinstance(entries, list) or not entries or len(entries) > MAX_BATCH:
            self.send_response(400)
            self.end_headers()
            return
        applied = 0
        with lock:
            store = current()
            for item in entries:
                if not isinstance(item, dict):
                    continue
                hexcode = item.get("hex", "")
                classification = item.get("class")
                if not isinstance(hexcode, str) or not HEX_RE.match(hexcode):
                    continue
                if not isinstance(classification, dict):
                    continue
                hexcode = hexcode.lower()
                # Deliberately only touches aircraft already on file: a batch
                # is for filling in what is known, never for inventing
                # sightings that never happened.
                entry = store["ac"].get(hexcode)
                if entry is None:
                    continue
                before = dict(entry)
                apply_class(entry, classification)
                if entry != before:
                    applied += 1
            if applied:
                mark_dirty()
        self._json(200, {"applied": applied})

    def do_POST(self):
        if self.path.split("?", 1)[0].rstrip("/") != "/sightings":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > MAX_BATCH_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if isinstance(payload, dict) and "batch" in payload:
                return self._do_batch(payload.get("batch"))
            if length > MAX_BODY_BYTES:
                raise ValueError("a single-aircraft body is much smaller than this")
            hexcode = payload.get("hex", "")
            kind = payload.get("kind")
            classification = payload.get("class")
            records = payload.get("rec")
            if not HEX_RE.match(hexcode):
                raise ValueError("expected a 6-hex-digit ICAO address")
            if kind is not None and kind not in COUNTERS:
                raise ValueError("kind must be 'total', 'nearby' or 'network'")
            if classification is not None and not isinstance(classification, dict):
                raise ValueError("class must be an object")
            if records is not None and not isinstance(records, dict):
                raise ValueError("rec must be an object")
            if kind is None and classification is None and records is None:
                raise ValueError("nothing to do")
        except (ValueError, json.JSONDecodeError, AttributeError, TypeError):
            self.send_response(400)
            self.end_headers()
            return
        hexcode = hexcode.lower()

        with lock:
            store = current()
            first_ever = hexcode not in store["ac"]
            entry = store["ac"].get(hexcode) or {"t": 0, "n": 0}
            now = int(time.time())
            if store.get("since") is None:
                store["since"] = now   # first moment we can actually date
            if kind is not None:
                entry[COUNTERS[kind]] = entry.get(COUNTERS[kind], 0) + 1
                entry.setdefault("f", now)
                entry["l"] = now
                if kind == "total":
                    local = time.localtime(now)
                    store["hours"][local.tm_hour] += 1
                    store["dows"][local.tm_wday] += 1
                # Today's tally, for the empty-sky screen. Local date, reset
                # on the first increment of a new day.
                if kind in ("total", "nearby"):
                    today = time.strftime("%Y-%m-%d", time.localtime(now))
                    day = store.get("day")
                    if not isinstance(day, dict) or day.get("d") != today:
                        day = store["day"] = {"d": today, "t": 0, "n": 0}
                    day["t" if kind == "total" else "n"] += 1
                bump_year(store, entry, kind, now, first_ever and kind == "total")
            if classification is not None:
                apply_class(entry, classification)
            store["ac"][hexcode] = entry
            if records is not None:
                apply_records(store, hexcode, entry, records)
            evict(store)
            mark_dirty()
            result = {"total": entry.get("t", 0), "nearby": entry.get("n", 0)}

        self._json(200, result)

    def log_message(self, fmt, *args):
        pass  # this gets hit on every new sighting across every open viewer; keep the journal quiet


if __name__ == "__main__":
    # SIGTERM is what systemd sends on stop, restart and reboot -- the flush
    # there is what keeps a clean shutdown from losing the last interval.
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    with lock:
        current()
    threading.Thread(target=_flusher, daemon=True).start()
    server = http.server.ThreadingHTTPServer(LISTEN, Handler)
    server.daemon_threads = True
    server.serve_forever()
