#!/usr/bin/env python3
"""
Dev-only server: serves index.html locally and proxies /tar1090/* to the
Raspberry Pi so the app can be tested with the exact same relative fetch
paths ('/tar1090/data/aircraft.json') it will use once deployed on the Pi
itself (same-origin there, no proxy needed). Not part of the deployed app.
"""
import http.server
import urllib.request
import os
import sys

# Your radar's address: STRATOSCAN_PI, or the first line of .dev-pi beside this
# file (git ignores it), or raspberrypi.local.
def _pi_host():
    if os.environ.get("STRATOSCAN_PI"):
        return os.environ["STRATOSCAN_PI"].rstrip("/")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dev-pi")) as f:
            return f.readline().strip().rstrip("/")
    except OSError:
        return "http://raspberrypi.local"

PI_HOST = _pi_host()
PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(("/tar1090/", "/api/")):
            try:
                with urllib.request.urlopen(PI_HOST + self.path, timeout=5) as upstream:
                    self.send_response(upstream.status)
                    self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/json"))
                    # urllib doesn't auto-decompress; some tar1090 assets (db shards) are
                    # served pre-gzipped, so the Content-Encoding header must be forwarded
                    # too or the browser has no idea the bytes need decompressing
                    if upstream.headers.get("Content-Encoding"):
                        self.send_header("Content-Encoding", upstream.headers["Content-Encoding"])
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(upstream.read())
            except Exception as e:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        return super().do_GET()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
