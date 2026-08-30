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
import posixpath
import re
import urllib.error
import urllib.parse
import urllib.request

UPSTREAM = "http://127.0.0.1:80"
LISTEN = ("127.0.0.1", 8085)
ROUNDED_PATH = "/tar1090/data/receiver.json"
COORD_PRECISION = 2  # decimal places -- ~0.7mi at this latitude

# Paths refused for public (Funnel) traffic. /wake physically powers the
# kiosk's display on; harmless in isolation, but it is an unauthenticated
# side effect on hardware in someone's house, and nothing off-LAN has any
# business reaching it. The kiosk and the rest of the LAN talk to lighttpd
# directly and are unaffected by this.
LOCAL_ONLY_PATHS = ("/wake", "/setup")

# A future edit that empties or mistypes this list would silently expose the
# device's privileged endpoints to the public internet. Fail loudly instead.
assert "/wake" in LOCAL_ONLY_PATHS and "/setup" in LOCAL_ONLY_PATHS, \
    "LOCAL_ONLY_PATHS must keep /wake and /setup off the public tunnel"

# Headers that are per-hop or would otherwise be wrong to blindly forward
# (Content-Length is recomputed for the rewritten path; "server" is excluded
# so lighttpd's own version banner doesn't leak through this gateway on top
# of -- see version_string() below -- our own; the rest are transport-level,
# not meaningful to relay from an internal proxy hop).
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "server"}

# Cheap, zero-risk hardening now that this is reachable from the whole
# public internet: clickjacking/MIME-sniffing/referrer-leak protections.
# Deliberately NOT a Content-Security-Policy here -- this app talks to enough
# different external hosts (map tiles, fonts, several free data APIs) that a
# CSP tight enough to matter needs to be built and tested against the live
# page, not improvised inline; getting it wrong risks breaking the app for
# every public viewer, worse than the marginal defense-in-depth it'd add on
# top of the XSS fix already in index.html.
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer-when-downgrade",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Relay redirects to the client instead of following them here.

    urlopen follows 3xx by default, which made this gateway hang: lighttpd's
    captive-portal rule returns a redirect to the hotspot address, and when
    the hotspot is down that address does not exist -- so the gateway sat
    there until timeout with a worker blocked, on a PUBLIC endpoint. Enough
    such requests is a denial of service.

    A proxy has no business chasing redirects anyway: the client should see
    the 3xx and decide.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


class Handler(http.server.BaseHTTPRequestHandler):
    def version_string(self):
        return "FlightRadar"  # don't advertise the Python/http.server version

    def _send_security_headers(self):
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)

    def _dispatch(self):
        """Single gate for every HTTP method.

        Previously only do_GET and do_POST checked LOCAL_ONLY_PATHS, so any
        method added later would silently bypass it. Deny first, always.
        """
        if self._is_local_only(self.path):
            self.send_error(404)  # 404, not 403 -- don't confirm it exists
            return
        if self.command == "GET" and self.path == ROUNDED_PATH:
            self._serve_rounded_receiver_json()
        else:
            self._proxy()

    do_GET = _dispatch
    do_POST = _dispatch
    do_HEAD = _dispatch
    do_PUT = _dispatch
    do_DELETE = _dispatch
    do_PATCH = _dispatch
    do_OPTIONS = _dispatch

    @staticmethod
    def _normalise(path):
        """Reduce a request path to the form the UPSTREAM server will act on.

        Matching the raw path is not enough and was a real hole: lighttpd
        percent-decodes and collapses traversal before routing, so /%77ake,
        /./wake and /x/../wake all reach the wake service while none of them
        string-compare equal to "/wake". Verified against the live gateway --
        all three returned 204 instead of 404.

        Decode repeatedly, because a single pass turns %2577 into %77 rather
        than into "w".
        """
        base = path.split("?", 1)[0].split("#", 1)[0]
        for _ in range(4):
            decoded = urllib.parse.unquote(base)
            if decoded == base:
                break
            base = decoded
        base = base.replace("\\", "/")          # defensive: some clients send backslashes
        base = re.sub(r"/{2,}", "/", base)      # //wake -> /wake
        if not base.startswith("/"):
            base = "/" + base
        base = posixpath.normpath(base)         # /x/../wake -> /wake
        if not base.startswith("/"):            # normpath can yield ".."
            base = "/" + base.lstrip("./")
        return (base.rstrip("/") or "/").casefold()

    @classmethod
    def _is_local_only(cls, path):
        base = cls._normalise(path)
        return any(base == p or base.startswith(p + "/") for p in LOCAL_ONLY_PATHS)

    def _serve_rounded_receiver_json(self):
        try:
            with _opener.open(UPSTREAM + self.path, timeout=5) as upstream:
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
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None

        req_headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=req_headers, method=self.command)

        try:
            with _opener.open(req, timeout=10) as upstream:
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
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(resp.read())

    def log_message(self, fmt, *args):
        pass  # every request from every public viewer would otherwise hit the journal


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
