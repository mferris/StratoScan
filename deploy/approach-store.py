#!/usr/bin/env python3
"""
Local-only (127.0.0.1) shared store for the home airport's approach heatmap.

index.html's client-side tracking (updateApproachTracking() / confirmApproachOnDrop()
in index.html) buffers candidate positions per-aircraft and, once a landing is
confirmed, commits them here instead of to browser localStorage -- localStorage
is scoped per-browser/per-device, so the kiosk's own accumulated picture would
never be visible to anyone checking in from a separate browser (their laptop,
phone, the Funnel URL). This service gives every viewer the same shared,
growing picture. lighttpd proxies /approaches requests to it (see
91-stratoscan-approach-store.conf), keeping the browser's fetch same-origin.

A grid of counts, not a list of points (2026-10-14). It used to keep the last
6,000 raw positions, and the page records one a second, up to 400 a landing:
the "picture built over time" was the last 15-40 landings, an hour or two at
RDU. Now each landing adds one to every CELL_DEG square (about 200 m) it
passed through, so every landing is kept, for good, in a file that stays
small: only the squares along the approach paths ever fill.

GET  /approaches  -> [[lon, lat, landings], ...], one per square, at its
                     centre. A page from before the grid reads the third
                     number as an altitude and still draws the squares.
POST /approaches  -> one landing: {"hex": "a1b2c3", "points": [[lon, lat], ...]}
                     (a bare [[lon, lat], ...] from an older page is taken too)

Every open viewer (kiosk, phone, laptop) reports the landings it sees. The
same aircraft reported again within DEDUPE_S counts once, so two browsers do
not double a landing; a bare list carries no hex and cannot be matched.

Counts live in memory and are written every FLUSH_INTERVAL and on shutdown,
like sighting-store.py: one landing used to rewrite the whole file.
"""
import heapq
import http.server
import json
import math
import os
import re
import signal
import sys
import threading
import time

LISTEN = ("127.0.0.1", 8082)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "approaches.json")
# The points list this replaced, kept once at conversion so it can be undone.
V1_BACKUP = STORE_PATH + ".points-v1"
CELL_DEG = 0.002          # ~220 m north-south, ~180 m east-west at RDU
# Squares within the page's 12 nm approach radius number ~40,000 at most;
# real approach paths fill a few thousand. Past the cap the least-used go.
MAX_CELLS = 40000
EVICT_TO = MAX_CELLS - 1000
FLUSH_INTERVAL = 1800
DEDUPE_S = 300
# Points further apart than this in the old list were two landings.
V1_TRACK_GAP_KM = 2.0
# A real batch is at most a few hundred small [lon,lat] pairs (the client
# caps its own per-plane buffer at 400 points, committed one landing at a
# time) -- this is generous headroom over that, not a tuned limit. Exists
# because this endpoint is reachable from the public internet via Tailscale
# Funnel with no auth: without a cap, Content-Length is attacker-controlled
# and the whole body gets read into memory before any validation happens.
MAX_BODY_BYTES = 200_000
HEX_RE = re.compile(r"^~?[0-9a-f]{6}$")

lock = threading.Lock()
_store = None
_dirty = False
_recent = {}              # hex -> when its landing was counted


def valid_point(p):
    return (
        isinstance(p, list) and len(p) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)
        and -180 <= p[0] <= 180 and -90 <= p[1] <= 90
    )


def cell_of(lon, lat):
    """The square a point is in, as the page works it out too: floor(x/CELL
    + 0.5) in both, so the two always agree."""
    return f"{math.floor(lat / CELL_DEG + 0.5)},{math.floor(lon / CELL_DEG + 0.5)}"


def fresh_store():
    return {"v": 2, "cells": {}, "landings": 0, "since": int(time.time())}


def km(a, b):
    """Rough distance between two [lon, lat] points, plenty for a gap test."""
    dy = (a[1] - b[1]) * 111.2
    dx = (a[0] - b[0]) * 111.2 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot(dx, dy)


def from_points(points):
    """The old list of raw positions as a grid. Its landings were stored end
    to end with nothing between them, so a square counts once per run of
    consecutive points inside it, and a jump of over V1_TRACK_GAP_KM starts
    another landing."""
    store = fresh_store()
    cells = store["cells"]
    prev_cell = prev = None
    for p in points:
        if not valid_point(p):
            continue
        if prev is None or km(prev, p) > V1_TRACK_GAP_KM:
            store["landings"] += 1
            prev_cell = None
        c = cell_of(p[0], p[1])
        if c != prev_cell:
            cells[c] = cells.get(c, 0) + 1
        prev_cell, prev = c, p
    return store


def load_store():
    try:
        with open(STORE_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return fresh_store(), False
    if isinstance(data, list):
        # Converted once, and written at once: the points are kept beside
        # it first, so a power cut at any moment loses neither.
        store = from_points(data)
        try:
            if not os.path.exists(V1_BACKUP):
                with open(V1_BACKUP, "w") as f:
                    json.dump(data, f, separators=(",", ":"))
                    f.flush()
                    os.fsync(f.fileno())
            save_store(store)
        except OSError:
            return store, True        # written by the next flush instead
        return store, False
    if isinstance(data, dict) and data.get("v") == 2 and isinstance(data.get("cells"), dict):
        store = fresh_store()
        store.update(data)
        store["cells"] = {k: n for k, n in data["cells"].items()
                          if isinstance(k, str) and isinstance(n, int) and n > 0}
        return store, False
    return fresh_store(), False


def save_store(store):
    # Written whole and renamed into place, and synced: a power cut leaves
    # either the old file or the new one, never half of one.
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STORE_PATH)


def current():
    """The in-memory store. Caller must hold `lock`."""
    global _store, _dirty
    if _store is None:
        _store, converted = load_store()
        _dirty = _dirty or converted
    return _store


def add_landing(store, points, hexcode=None, now=None):
    """Count one landing. False when the same aircraft's landing was already
    counted within DEDUPE_S (another open browser reporting it too)."""
    now = time.time() if now is None else now
    for h, t in list(_recent.items()):
        if now - t > DEDUPE_S:
            del _recent[h]
    if hexcode:
        if hexcode in _recent:
            return False
        _recent[hexcode] = now
    cells = store["cells"]
    for c in {cell_of(p[0], p[1]) for p in points}:
        cells[c] = cells.get(c, 0) + 1
    store["landings"] = store.get("landings", 0) + 1
    if len(cells) > MAX_CELLS:
        for c in heapq.nsmallest(len(cells) - EVICT_TO, cells, key=cells.get):
            del cells[c]
    return True


def to_points(store):
    """[[lon, lat, landings], ...] at each square's centre."""
    out = []
    for k, n in store["cells"].items():
        i, j = k.split(",")
        out.append([round(int(j) * CELL_DEG, 4), round(int(i) * CELL_DEG, 4), n])
    return out


def parse_landing(body):
    """(points, hex) from a POST body, or None if it is not one landing."""
    if isinstance(body, list):
        points, hexcode = body, None
    elif isinstance(body, dict) and isinstance(body.get("points"), list):
        points, hexcode = body["points"], body.get("hex")
        if not (isinstance(hexcode, str) and HEX_RE.match(hexcode)):
            hexcode = None            # counted, just not matched against others
    else:
        return None
    if not points or not all(valid_point(p) for p in points):
        return None
    return points, hexcode


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
            print(f"approach-store: flush failed: {e}", file=sys.stderr, flush=True)


def _shutdown(signum, frame):
    flush()
    sys.exit(0)


class Handler(http.server.BaseHTTPRequestHandler):
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30
    def version_string(self):
        return "StratoScan"  # don't advertise the Python/http.server version

    def do_GET(self):
        if self.path != "/approaches":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            body = json.dumps(to_points(current()), separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global _dirty
        if self.path != "/approaches":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        try:
            landing = parse_landing(json.loads(self.rfile.read(length)))
            if landing is None:
                raise ValueError("expected one landing's [lon, lat] points")
        except (ValueError, json.JSONDecodeError):
            self.send_response(400)
            self.end_headers()
            return

        with lock:
            if add_landing(current(), *landing):
                _dirty = True

        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # this gets hit on every confirmed landing across every open viewer; keep the journal quiet


if __name__ == "__main__":
    # SIGTERM is what systemd sends on stop, restart and reboot -- the flush
    # there is what keeps a clean shutdown from losing the last interval.
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    with lock:
        current()
    threading.Thread(target=_flusher, daemon=True).start()
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
