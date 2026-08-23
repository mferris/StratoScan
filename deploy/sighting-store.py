#!/usr/bin/env python3
"""
Local-only (127.0.0.1) shared store for per-aircraft sighting counts.

Tracks, per hex, how many distinct times this receiver has picked the
aircraft up (`total`) and how many distinct times it's come within the
nearby-alert radius (`nearby`, see ALERT_RADIUS_NM in index.html) --
incremented client-side at the same "this is a new visit" / "this just
triggered the alert" moments the rest of index.html already detects, not
once per poll. Same shape as approach-store.py: persisted server-side
rather than localStorage, so the kiosk's own accumulated counts are visible
to every viewer (laptop, phone, the Funnel URL), not just whichever browser
happened to be open when a plane flew by. lighttpd proxies /sightings
requests to it (see 93-flightradar-sighting-store.conf).

GET  /sightings          -> the full map, {"<hex>": {"total": N, "nearby": M}, ...}
POST /sightings          -> body {"hex": "...", "kind": "total"|"nearby"};
                             increments that one counter for that hex by 1,
                             returns the updated {"total": N, "nearby": M}

Multiple viewers open at once each independently detect and report the same
real sighting -- same accepted tradeoff as approach-store.py: harmless
over-counting by a point or two, not wrong.
"""
import http.server
import json
import os
import re
import threading

LISTEN = ("127.0.0.1", 8083)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "sightings.json")
MAX_HEXES = 20000  # generous headroom over any realistic number of distinct aircraft ever seen
MAX_BODY_BYTES = 2000  # a real body is ~40 bytes; this endpoint is reachable from the public internet via Funnel
HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$")

lock = threading.Lock()


def load_store():
    try:
        with open(STORE_PATH) as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_store(store):
    with open(STORE_PATH, "w") as f:
        json.dump(store, f)


class Handler(http.server.BaseHTTPRequestHandler):
    def version_string(self):
        return "FlightRadar"

    def do_GET(self):
        if self.path != "/sightings":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            store = load_store()
        body = json.dumps(store).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/sightings":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        try:
            payload = json.loads(self.rfile.read(length))
            hexcode = payload.get("hex", "")
            kind = payload.get("kind")
            if not HEX_RE.match(hexcode) or kind not in ("total", "nearby"):
                raise ValueError("expected {hex: 6-hex-digit string, kind: 'total'|'nearby'}")
        except (ValueError, json.JSONDecodeError, AttributeError):
            self.send_response(400)
            self.end_headers()
            return
        hexcode = hexcode.lower()

        with lock:
            store = load_store()
            entry = store.get(hexcode) or {"total": 0, "nearby": 0}
            entry[kind] = entry.get(kind, 0) + 1
            store[hexcode] = entry
            if len(store) > MAX_HEXES:
                # oldest-inserted-first eviction -- dict preserves insertion
                # order in Python 3.7+, and re-assigning an existing key
                # (above) doesn't move it, so this evicts genuinely stale
                # entries, not just-updated ones
                for k in list(store.keys())[: len(store) - MAX_HEXES]:
                    del store[k]
            save_store(store)

        body = json.dumps(entry).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # this gets hit on every new sighting across every open viewer; keep the journal quiet


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
