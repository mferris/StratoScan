#!/usr/bin/env python3
"""
Local-only (127.0.0.1) shared store for RDU approach-track points.

index.html's client-side tracking (updateApproachTracking() / confirmApproachOnDrop()
in index.html) buffers candidate positions per-aircraft and, once a landing is
confirmed, commits them here instead of to browser localStorage -- localStorage
is scoped per-browser/per-device, so the kiosk's own accumulated picture would
never be visible to anyone checking in from a separate browser (their laptop,
phone, the Funnel URL). This service gives every viewer the same shared,
growing picture. lighttpd proxies /approaches requests to it (see
91-flightwall-approach-store.conf), keeping the browser's fetch same-origin.

GET  /approaches  -> current accumulated points, as a JSON array of [lon, lat] pairs
POST /approaches  -> append points (JSON array of [lon, lat] pairs in the body);
                     capped at MAX_POINTS total, oldest evicted first

Multiple viewers (kiosk + anyone else with the page open) each independently
detect and report landings they observe -- there's no leader election, so the
same real landing could get reported more than once if two browsers are open
at the same time. Harmless: it just means that landing's path is
over-represented by a point or two in the accumulated picture, not wrong.
"""
import http.server
import json
import os
import threading

LISTEN = ("127.0.0.1", 8082)
STORE_PATH = os.path.join(os.environ.get("STATE_DIRECTORY", "."), "approaches.json")
MAX_POINTS = 6000

lock = threading.Lock()


def load_points():
    try:
        with open(STORE_PATH) as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_points(points):
    with open(STORE_PATH, "w") as f:
        json.dump(points, f)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/approaches":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            points = load_points()
        body = json.dumps(points).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/approaches":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            new_points = json.loads(self.rfile.read(length))
            if not isinstance(new_points, list):
                raise ValueError("expected a JSON array")
        except (ValueError, json.JSONDecodeError):
            self.send_response(400)
            self.end_headers()
            return

        with lock:
            points = load_points()
            points.extend(new_points)
            if len(points) > MAX_POINTS:
                points = points[-MAX_POINTS:]
            save_points(points)

        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # this gets hit on every confirmed landing across every open viewer; keep the journal quiet


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
