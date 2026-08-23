#!/usr/bin/env python3
"""
Local-only reverse proxy sitting between Tailscale Funnel and lighttpd.

Funnel makes whatever it points at reachable by anyone on the public
internet, unauthenticated -- lighttpd (127.0.0.1:80) also serves the LAN
and the kiosk itself, which both legitimately need exact data (readsb's own
signal-range/MLAT math depends on the real configured position; nothing
about that changes here). This gateway is what Funnel is pointed at instead
of lighttpd directly, so only the copy that actually leaves the house over
the public internet gets filtered -- LAN/kiosk traffic never touches this
process at all.

Every request is proxied through unchanged except one: GET
/tar1090/data/receiver.json (readsb's own receiver-location endpoint, which
index.html's loadHome() fetches to auto-center the radar) has its lat/lon
rounded to 2 decimal places -- about 0.7 miles of fuzz, plenty to keep the
map/radar centered correctly at the app's actual range scale, but no longer
a literal street address to anyone who curls the Funnel URL.
"""
import http.server
import json
import urllib.request
import urllib.error

UPSTREAM = "http://127.0.0.1:80"
LISTEN = ("127.0.0.1", 8085)
ROUNDED_PATH = "/tar1090/data/receiver.json"
COORD_PRECISION = 2  # decimal places -- ~0.7mi at this latitude

# Headers that are per-hop or would otherwise be wrong to blindly forward
# (Content-Length is recomputed for the rewritten path; the rest are
# transport-level, not meaningful to relay from an internal proxy hop).
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host"}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == ROUNDED_PATH:
            self._serve_rounded_receiver_json()
        else:
            self._proxy()

    def do_POST(self):
        self._proxy()

    def _serve_rounded_receiver_json(self):
        try:
            with urllib.request.urlopen(UPSTREAM + self.path, timeout=5) as upstream:
                data = json.loads(upstream.read())
        except Exception:
            self.send_response(502)
            self.end_headers()
            return

        for key in ("lat", "lon"):
            if isinstance(data.get(key), (int, float)):
                data[key] = round(data[key], COORD_PRECISION)

        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None

        req_headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=req_headers, method=self.command)

        try:
            with urllib.request.urlopen(req, timeout=10) as upstream:
                self._relay(upstream.status, upstream)
        except urllib.error.HTTPError as e:
            self._relay(e.code, e)
        except Exception:
            self.send_response(502)
            self.end_headers()

    def _relay(self, status, resp):
        self.send_response(status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp.read())

    def log_message(self, fmt, *args):
        pass  # every request from every public viewer would otherwise hit the journal


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
