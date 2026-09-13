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
                            to classify many at once. The whole store is
                            rewritten on every save, so backfilling thousands
                            of aircraft one request at a time would mean
                            thousands of rewrites of the same file -- pointless
                            wear on an SD card that has to last years.

Multiple viewers open at once each independently detect and report the same
real sighting -- same accepted tradeoff as approach-store.py: harmless
over-counting by a point or two, not wrong. Records are the exception and
need no such tolerance: they are compare-and-keep, so the same record
offered by four viewers still lands once.
"""
import http.server
import json
import os
import re
import threading
import time

LISTEN = ("127.0.0.1", 8083)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "sightings.json")
MAX_HEXES = 20000  # generous headroom over any realistic number of distinct aircraft ever seen
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
    os.replace(tmp, STORE_PATH)


def legacy_view(store):
    """The v1 shape, rebuilt from the current store."""
    return {h: {"total": e.get("t", 0), "nearby": e.get("n", 0)}
            for h, e in store["ac"].items()}


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
        if path == "/sightings/stats":
            with lock:
                return self._json(200, summarise(load_store()))
        if path == "/sightings/unclassified":
            with lock:
                store = load_store()
            hexes = [h for h, e in store["ac"].items() if not e.get("k")]
            return self._json(200, {"hexes": hexes[:MAX_UNCLASSIFIED],
                                    "remaining": max(0, len(hexes) - MAX_UNCLASSIFIED)})
        if path != "/sightings":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            store = load_store()
        self._json(200, legacy_view(store))

    def _do_batch(self, entries):
        if not isinstance(entries, list) or not entries or len(entries) > MAX_BATCH:
            self.send_response(400)
            self.end_headers()
            return
        applied = 0
        with lock:
            store = load_store()
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
                save_store(store)
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
            store = load_store()
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
            if classification is not None:
                apply_class(entry, classification)
            store["ac"][hexcode] = entry
            if records is not None:
                apply_records(store, hexcode, entry, records)
            if len(store["ac"]) > MAX_HEXES:
                # oldest-inserted-first eviction -- dict preserves insertion
                # order in Python 3.7+, and re-assigning an existing key
                # (above) doesn't move it, so this evicts genuinely stale
                # entries, not just-updated ones
                for k in list(store["ac"].keys())[: len(store["ac"]) - MAX_HEXES]:
                    del store["ac"][k]
            save_store(store)

        self._json(200, {"total": entry.get("t", 0), "nearby": entry.get("n", 0)})

    def log_message(self, fmt, *args):
        pass  # this gets hit on every new sighting across every open viewer; keep the journal quiet


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
