#!/usr/bin/env python3
"""
Local-only proxy for planespotters.net's photo API.

Exists purely because planespotters.net requires a descriptive custom
User-Agent identifying the calling application ("Generic library User-Agent
strings are not accepted" -- see https://www.planespotters.net/photo/api),
and browser fetch()/XMLHttpRequest can never set that header themselves --
it's exclusively controlled by the browser. So this runs server-side on the
Pi instead, listening on 127.0.0.1 only; lighttpd proxies /photo/<hex>
requests to it (see 89-flightradar-photo-proxy.conf), keeping the browser's
fetch same-origin exactly like aircraft.json/receiver.json already are.

Attribution requirement per planespotters.net's terms of use (photographer
credit + link back to the original photo) is enforced by the *caller*
(index.html), not here -- this just relays photographer/link through
unchanged so the caller has what it needs to comply.
"""
import http.server
import json
import re
import time
import urllib.request

LISTEN = ("127.0.0.1", 8081)
USER_AGENT = "FlightRadar/1.0 (+https://github.com/mferris/FlightRadar; personal ADS-B kiosk project)"
CACHE_TTL = 24 * 3600
HEX_RE = re.compile(r"/photo/([0-9a-fA-F]{6})$")

cache = {}  # hex -> (timestamp, response_body_bytes)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        m = HEX_RE.search(self.path)
        if not m:
            self.send_response(404)
            self.end_headers()
            return
        hexcode = m.group(1).lower()

        now = time.time()
        cached = cache.get(hexcode)
        if cached and now - cached[0] < CACHE_TTL:
            body = cached[1]
        else:
            body = json.dumps(self._fetch(hexcode)).encode()
            cache[hexcode] = (now, body)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _fetch(self, hexcode):
        try:
            req = urllib.request.Request(
                f"https://api.planespotters.net/pub/photos/hex/{hexcode}",
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=5) as upstream:
                data = json.loads(upstream.read())
        except Exception:
            return {"found": False}

        photos = data.get("photos") or []
        if not photos:
            return {"found": False}

        p = photos[0]
        return {
            "found": True,
            "thumb": (p.get("thumbnail") or {}).get("src"),
            "thumbLarge": (p.get("thumbnail_large") or {}).get("src"),
            "link": p.get("link"),
            "photographer": p.get("photographer"),
        }

    def log_message(self, fmt, *args):
        pass  # this gets hit on every detail-panel open; keep the journal quiet


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
