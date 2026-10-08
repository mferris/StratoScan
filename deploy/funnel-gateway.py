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
import base64
import hashlib
import http.server
import json
import os
import posixpath
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UPSTREAM = "http://127.0.0.1:80"
LISTEN = ("127.0.0.1", 8085)
ROUNDED_PATH = "/tar1090/data/receiver.json"
# readsb puts every aircraft's distance and bearing FROM THE ANTENNA in
# aircraft.json (r_dst, r_dir). With the aircraft's own lat/lon, that locates
# the antenna exactly: measured 2026-09-28 against RDU's public URL, three
# aircraft put it within 54 m, which made rounding receiver.json pointless.
# Public requests get the feed without them; the page falls back to
# computing range from the (rounded) receiver position.
STRIPPED_PATH = "/tar1090/data/aircraft.json"
STRIPPED_FIELDS = ("r_dst", "r_dir")

# Under these, only the files named may answer publicly. readsb writes more
# than the page needs, and the rest locate the antenna exactly, which the two
# rewrites above exist to prevent (found 2026-10-04 on the live tunnel):
#   aircraft.binCraft.zst  the binary feed tar1090 prefers; its header carries
#                          the receiver's position unrounded (35.826027 where
#                          the rounded receiver.json said 35.83)
#   outline.json           the range outline, drawn around the antenna
#   history_*.json, chunks/  past aircraft.json snapshots, r_dst and r_dir intact
#   globe_history/, traces/  per-aircraft traces, likewise
# The four allowed are the two rewritten above and two counters-only files.
# The public receiver.json also turns binCraft, zstd, outlineJson and history
# off, so tar1090's own page asks for none of them.
TAR1090_PRIVATE_PREFIXES = ("/tar1090/data", "/tar1090/chunks", "/tar1090/globe_history")
TAR1090_PUBLIC_FILES = frozenset({"/tar1090/data/aircraft.json", "/tar1090/data/receiver.json",
                                  "/tar1090/data/stats.json", "/tar1090/data/status.json"})
PUBLIC_RECEIVER_FLAGS = {"binCraft": False, "zstd": False, "outlineJson": False, "history": 0}
COORD_PRECISION = 2  # decimal places -- ~0.7mi at this latitude

# Paths refused for public (Funnel) traffic. /wake physically powers the
# kiosk's display on; harmless in isolation, but it is an unauthenticated
# side effect on hardware in someone's house, and nothing off-LAN has any
# business reaching it. The kiosk and the rest of the LAN talk to lighttpd
# directly and are unaffected by this.
# /tts is text-to-speech: CPU-heavy synthesis on the unit, which only the
# house needs; a public caller could otherwise keep the Pi busy talking.
LOCAL_ONLY_PATHS = ("/wake", "/setup", "/tts")

# Paths that may be READ publicly but must not be WRITTEN publicly.
#
# The shared stores accept POSTs with no authentication -- fine when the only
# clients were on the LAN, but the Funnel makes them writable by anyone
# holding the URL. Verified: a POST through the tunnel successfully injected
# a fake sighting. A stranger could pollute the sighting counts and the
# approach heatmap, which is months of accumulated data.
#
# Reads stay open, because the page itself needs them from public viewers.
READ_ONLY_PUBLIC_PATHS = ("/sightings", "/approaches", "/network", "/api")

# A future edit that empties or mistypes this list would silently expose the
# device's privileged endpoints to the public internet. Fail loudly instead.
assert "/wake" in LOCAL_ONLY_PATHS and "/setup" in LOCAL_ONLY_PATHS, \
    "LOCAL_ONLY_PATHS must keep /wake and /setup off the public tunnel"

# How a listed path is matched. This MUST mirror how lighttpd decides which
# backend a request reaches, or the two disagree and the gap is an exposure.
#
# lighttpd routes on a bare regex prefix -- $HTTP["url"] =~ "^/setup" -- so
# /setupx, /setup-ui.html and /wakeup all reach the privileged backends.
# This gateway used to match only the exact path or "<path>/", which is
# strictly narrower. The difference was live and reachable from the public
# internet: /setupx returned the setup server's own 401 (its session auth was
# the only thing left standing), /wakeup reached the wake service, and POST
# /sightingsx and /networkx sailed past the read-only guard into the stores.
#
# Prefix matching is deliberately broader than lighttpd's, not narrower:
# _normalise() casefolds, so /SETUP is refused here even though lighttpd's
# regex is case-sensitive and would not have routed it. Over-refusing on the
# public tunnel costs nothing -- no legitimate public path begins with any of
# these prefixes.
def _matches(base, paths):
    return any(base.startswith(p) for p in paths)


def strip_antenna_relative(data):
    """aircraft.json without the fields measured from the antenna (STRIPPED_FIELDS)."""
    if isinstance(data, dict) and isinstance(data.get("aircraft"), list):
        for a in data["aircraft"]:
            if isinstance(a, dict):
                for k in STRIPPED_FIELDS:
                    a.pop(k, None)
    return data


def forward_headers(items):
    """Headers to send upstream: per-hop ones dropped, the public marker set.

    Split out of _proxy() so the security property is testable without a
    socket -- the marker being set is the whole point, and the previous
    version's failure was precisely that nobody could see it wasn't.
    """
    drop = HOP_BY_HOP | {PUBLIC_MARKER.lower()}
    out = {k: v for k, v in items if k.lower() not in drop}
    out[PUBLIC_MARKER] = "1"
    return out

# Headers that are per-hop or would otherwise be wrong to blindly forward
# (Content-Length is recomputed for the rewritten path; "server" is excluded
# so lighttpd's own version banner doesn't leak through this gateway on top
# of -- see version_string() below -- our own; the rest are transport-level,
# not meaningful to relay from an internal proxy hop).
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "server"}

# Marks a request as having arrived from the public tunnel, so a backend can
# refuse it even if the path filter above has a gap. setup-server.py has
# checked for this header since it was written -- but nothing ever set it, so
# the "belt and braces" it documented did not exist. Demonstrated against the
# live tunnel: /setupx returned 401 (marker absent, request reached the setup
# server) and 404 only when the CLIENT supplied the header itself.
#
# So it is set here, and any client-supplied copy is dropped first: a value
# that a caller can choose is not evidence of anything. Backends may now treat
# its presence as trustworthy.
PUBLIC_MARKER = "X-FR-Public"

# Cheap, zero-risk hardening now that this is reachable from the whole
# public internet: clickjacking/MIME-sniffing/referrer-leak protections.
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer-when-downgrade",
}

# ---- Content-Security-Policy for the page (security review 2026-10-04, #5) --
# The last layer behind the page's own escaping: a script that slipped past
# it could still not run, because the only scripts the browser may run are
# the page's own file (vendor/maplibre-gl.js) and its one inline block, named
# by the SHA-256 of its exact bytes -- computed here from the page lighttpd
# serves, so a release that changes the page changes the hash with it, and
# nothing is ever 'unsafe-inline' for scripts. The page has no inline event
# handlers and no javascript: links (tests/test_csp.py keeps it so).
#
# The hosts are everything the page talks to (tiles and glyphs, fonts, the
# weather, rain, lightning and places APIs); the unit's own data is 'self'.
# Styles stay 'unsafe-inline': MapLibre and the page set them from script,
# and an attacker who can inject style but not script gains little.
#
# REPORT-ONLY FIRST. Getting this wrong breaks the public page for every
# visitor, on browsers the maintainer doesn't have, so the policy goes out as
# Content-Security-Policy-Report-Only with violations counted (never stored)
# at /csp-report and read on the stats listener's /csp, and is switched to
# enforcing (CSP_ENFORCE=1 in the service's environment) only after a quiet
# spell on the live radar.
CSP_ENFORCE = os.environ.get("CSP_ENFORCE", "") == "1"
CSP_DIRECTIVES = (
    "default-src 'none'",
    "script-src 'self' {hashes}",
    "worker-src blob:",
    "child-src blob:",                      # older Safari reads this for workers
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",    # map tiles and sprites, overlay tiles, the aircraft photos
    "connect-src 'self' https://tiles.openfreemap.org https://api.open-meteo.com "
    "https://api.rainviewer.com https://tilecache.rainviewer.com https://*.rainviewer.com "
    "https://realearth.ssec.wisc.edu https://overpass-api.de https://fonts.googleapis.com",
    "media-src 'self' blob:",
    "manifest-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "report-uri /csp-report",
)
_INLINE_SCRIPT = re.compile(rb"<script>(.*?)</script>", re.S)
_csp_cache = {}     # sha256 of the page bytes -> policy string (one page, one entry)


def page_csp(page):
    """The policy for these exact page bytes."""
    digest = hashlib.sha256(page).hexdigest()
    policy = _csp_cache.get(digest)
    if policy is None:
        hashes = " ".join(
            "'sha256-%s'" % base64.b64encode(hashlib.sha256(block).digest()).decode()
            for block in _INLINE_SCRIPT.findall(page) if block.strip())
        policy = "; ".join(CSP_DIRECTIVES).format(hashes=hashes)
        _csp_cache.clear()
        _csp_cache[digest] = policy
    return policy


CSP_HEADER = "Content-Security-Policy" if CSP_ENFORCE else "Content-Security-Policy-Report-Only"
CSP_REPORT_MAX_BYTES = 8192
CSP_REPORT_KEYS = 64
_csp_reports = {}   # "directive blocked-host" -> count; bounded, in memory only
_csp_lock = threading.Lock()


def note_csp_report(body):
    """Count a browser's violation report: which directive, which host. The
    report itself (it can name the visitor's page URL and more) is dropped."""
    try:
        r = json.loads(body.decode("utf-8", "replace")).get("csp-report") or {}
        directive = str(r.get("effective-directive") or r.get("violated-directive") or "?").split(" ")[0][:40]
        blocked = str(r.get("blocked-uri") or "?")
        host = blocked if blocked in ("inline", "eval", "data", "blob", "?") else (urllib.parse.urlsplit(blocked).hostname or blocked[:40])
        key = "%s %s" % (directive, host[:60])
    except Exception:
        key = "unreadable"
    with _csp_lock:
        if key != "other" and key not in _csp_reports and len(_csp_reports) >= CSP_REPORT_KEYS - 1:
            key = "other"      # the bound counts "other" itself
        _csp_reports[key] = _csp_reports.get(key, 0) + 1


def csp_summary():
    with _csp_lock:
        return {"header": CSP_HEADER, "reports": dict(_csp_reports)}


# ---- visitor counts (roadmap 1.12) -----------------------------------------
# How many people look at this radar's public page, for its owner. Counts,
# not tracking: no cookies, nothing written about any one visitor.
#
# * Unique visitors in a day: each page load's address and browser are hashed
#   with a random salt made fresh each day and kept only in memory, and the
#   hashes are held in memory only until midnight. What is saved is counts.
#   Yesterday's hashes can't be linked to today's or turned back into an
#   address, because the salt that made them is gone.
# * The address is the LAST entry of X-Forwarded-For: the one Tailscale's
#   proxy adds. Earlier entries are whatever the client sent. Without the
#   header at all, unique visitors aren't counted, only page views, and the
#   summary says so ("basis").
# * The owner's own app, away from home, sends X-StratoScan-App and is
#   counted apart: minutes it was in use, not visits.
# * Only page loads count, not the page's own polling once it is open.
#   Obvious robots (crawlers, link previews, curl) are counted as robots.
#
# Saved to VISITS_DIR (the service's StateDirectory) every few minutes, and
# 90 days are kept. If the directory isn't there -- a unit whose service file
# predates this, until the installer is re-run -- the counts live in memory
# and restart from zero when the gateway does.
VISITS_DIR = (os.environ.get("STRATOSCAN_VISITS_DIR") or os.environ.get("STATE_DIRECTORY")
              or "/var/lib/stratoscan-visits")
STATS_LISTEN = ("127.0.0.1", 8091)        # loopback only; Funnel points at LISTEN. 8081-8090 are taken
VISITS_KEEP_DAYS = 90
VISITS_SAVE_S = 600
APP_HEADER = "X-StratoScan-App"
PAGE_PATHS = ("/", "/index.html")
MAX_REFERRERS = 20                         # per day; the rest are "other"
BOT_RE = re.compile(r"bot|crawl|spider|slurp|curl|wget|python|httpclient|okhttp|headless"
                    r"|preview|facebookexternalhit|whatsapp|discord|slack|telegram", re.I)


def device_kind(ua):
    """phone, tablet, computer, or bot -- from the browser's own description."""
    if not ua or BOT_RE.search(ua):
        return "bot"
    if "iPad" in ua or "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
        return "tablet"
    if "iPhone" in ua or "Mobile" in ua or "Android" in ua:
        return "phone"
    return "computer"


def referrer_site(ref, own_host):
    """The site a visitor came from (the host name only, never the address),
    or None for none, or this radar itself."""
    if not ref:
        return None
    try:
        host = (urllib.parse.urlsplit(ref).hostname or "").lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    own = (own_host or "").split(":")[0].lower()
    if not host or host == own or not re.match(r"^[a-z0-9.-]{1,80}$", host):
        return None
    return host


def visitor_address(headers):
    xff = headers.get("X-Forwarded-For") or ""
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    return parts[-1] if parts else None


def _new_day():
    return {"views": 0, "unique": 0, "bots": 0, "app_minutes": 0, "app_devices": 0,
            "hours": [0] * 24, "devices": {}, "referrers": {}, "basis": "views"}


class Visits:
    def __init__(self, directory=VISITS_DIR, now=time.time):
        self.lock = threading.Lock()
        self.dir = directory
        self.now = now
        self.days = {}
        self._day = None
        self._salt = b""
        self._seen = set()          # today's visitor hashes; memory only
        self._app_seen = set()
        self._app_minutes = set()
        self._saved_at = now()
        self._load()

    def _path(self):
        return os.path.join(self.dir, "visits.json")

    def _load(self):
        try:
            with open(self._path()) as f:
                d = json.load(f)
            if isinstance(d.get("days"), dict):
                self.days = d["days"]
        except (OSError, ValueError):
            pass

    def persistent(self):
        return os.path.isdir(self.dir) and os.access(self.dir, os.W_OK)

    def save(self):
        if not self.persistent():
            return False
        keep = sorted(self.days)[-VISITS_KEEP_DAYS:]
        self.days = {k: self.days[k] for k in keep}
        tmp = self._path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"days": self.days}, f, separators=(",", ":"))
        os.replace(tmp, self._path())
        return True

    def _roll(self, day):
        if day != self._day:
            self._day = day
            self._salt = secrets.token_bytes(16)
            self._seen.clear()
            self._app_seen.clear()
            self._app_minutes.clear()

    def _hash(self, addr, ua):
        if not addr:
            return None
        return hashlib.sha256(self._salt + addr.encode() + b"|" + ua.encode()).hexdigest()[:16]

    def record(self, method, path, headers):
        """One public request. `path` is already normalised."""
        is_app = headers.get(APP_HEADER) is not None
        is_page = method == "GET" and path in PAGE_PATHS
        if not (is_app or is_page):
            return
        t = self.now()
        lt = time.localtime(t)
        day = time.strftime("%Y-%m-%d", lt)
        ua = headers.get("User-Agent") or ""
        addr = visitor_address(headers)
        with self.lock:
            self._roll(day)
            d = self.days.setdefault(day, _new_day())
            if addr:
                d["basis"] = "visitors"
            v = self._hash(addr, ua)
            if is_app:
                minute = int(t // 60)
                if minute not in self._app_minutes:
                    self._app_minutes.add(minute)
                    d["app_minutes"] += 1
                if v and v not in self._app_seen:
                    self._app_seen.add(v)
                    d["app_devices"] += 1
            else:
                kind = device_kind(ua)
                if kind == "bot":
                    d["bots"] += 1
                else:
                    d["views"] += 1
                    d["hours"][lt.tm_hour] += 1
                    d["devices"][kind] = d["devices"].get(kind, 0) + 1
                    if v and v not in self._seen:
                        self._seen.add(v)
                        d["unique"] += 1
                    site = referrer_site(headers.get("Referer"), headers.get("Host"))
                    if site:
                        refs = d["referrers"]
                        if site not in refs and len(refs) >= MAX_REFERRERS:
                            site = "other"
                        refs[site] = refs.get(site, 0) + 1
            if t - self._saved_at >= VISITS_SAVE_S:
                self._saved_at = t
                try:
                    self.save()
                except OSError:
                    pass

    def summary(self, days=30):
        """For the owner: today, the last `days` days, and their totals."""
        with self.lock:
            keys = sorted(self.days)[-days:]
            rows = [{"date": k, **{f: self.days[k].get(f, 0) for f in
                     ("views", "unique", "bots", "app_minutes", "app_devices")}} for k in keys]
            hours, devices, refs = [0] * 24, {}, {}
            for k in keys[-7:]:
                for i, n in enumerate(self.days[k].get("hours", [])[:24]):
                    hours[i] += n
            for k in keys:
                for name, n in self.days[k].get("devices", {}).items():
                    devices[name] = devices.get(name, 0) + n
                for name, n in self.days[k].get("referrers", {}).items():
                    refs[name] = refs.get(name, 0) + n
            today = time.strftime("%Y-%m-%d", time.localtime(self.now()))
            basis = "visitors" if any(self.days[k].get("basis") == "visitors" for k in keys) else "views"
            return {
                "today": next((r for r in rows if r["date"] == today),
                              {"date": today, "views": 0, "unique": 0, "bots": 0, "app_minutes": 0, "app_devices": 0}),
                "days": rows,
                "hours7": hours,
                "devices": devices,
                "referrers": sorted(refs.items(), key=lambda kv: -kv[1])[:10],
                "basis": basis,
                "kept": self.persistent(),
            }


VISITS = None   # made at start-up; record() is never called before


class _StatsHandler(http.server.BaseHTTPRequestHandler):
    """Loopback-only: the setup server reads the counts from here for the
    radar's screen, its setup page and the owner's app at home."""
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/csp":
            body = json.dumps(csp_summary()).encode()
        elif path == "/visits" and VISITS is not None:
            body = json.dumps(VISITS.summary()).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


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
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30
    def version_string(self):
        return "StratoScan"  # don't advertise the Python/http.server version

    def _send_security_headers(self):
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)

    @classmethod
    def _is_read_only_public(cls, path):
        return _matches(cls._normalise(path), READ_ONLY_PUBLIC_PATHS)

    @classmethod
    def _is_rounded_receiver_json(cls, path):
        # Was a bare `path == ROUNDED_PATH` -- a real hole, since self.path
        # includes the query string and isn't traversal-collapsed. GET
        # /tar1090/data/receiver.json?x=1 (or a trailing slash, or any of the
        # percent-encodings _normalise() exists to defeat) failed that exact
        # match and fell through to the unfiltered _proxy(), leaking the
        # real, unrounded home coordinates to anyone with the Funnel URL.
        # Same class of bug as the /wake bypass _normalise()'s own docstring
        # documents; this call site just hadn't been switched over to it.
        return cls._normalise(path) == ROUNDED_PATH

    @classmethod
    def _is_tar1090_private(cls, path):
        base = cls._normalise(path)
        return _matches(base, TAR1090_PRIVATE_PREFIXES) and base not in TAR1090_PUBLIC_FILES

    def _dispatch(self):
        """Single gate for every HTTP method.

        Previously only do_GET and do_POST checked LOCAL_ONLY_PATHS, so any
        method added later would silently bypass it. Deny first, always.
        """
        if self._is_local_only(self.path) or self._is_tar1090_private(self.path):
            self.send_error(404)  # 404, not 403 -- don't confirm it exists
            return
        if VISITS is not None:
            try:
                VISITS.record(self.command, self._normalise(self.path), self.headers)
            except Exception:
                pass    # counting must never get in the way of serving
        # A browser reporting a policy violation (see CSP_DIRECTIVES): counted,
        # answered, never forwarded.
        if self.command == "POST" and self._normalise(self.path) == "/csp-report":
            length = int(self.headers.get("Content-Length", 0) or 0)
            if 0 < length <= CSP_REPORT_MAX_BYTES:
                note_csp_report(self.rfile.read(length))
            self.send_response(204)
            self.end_headers()
            return
        # Public traffic may read the shared stores but never write them.
        if self.command != "GET" and self._is_read_only_public(self.path):
            self.send_error(403, "Read-only")
            return
        if self.command == "GET" and self._is_rounded_receiver_json(self.path):
            self._serve_rounded_receiver_json()
        elif self.command in ("GET", "HEAD") and self._normalise(self.path) == STRIPPED_PATH:
            self._serve_stripped_aircraft_json()
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
        return _matches(cls._normalise(path), LOCAL_ONLY_PATHS)

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
        # and nothing that would send tar1090 to the files refused above
        data.update(PUBLIC_RECEIVER_FLAGS)

        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_stripped_aircraft_json(self):
        try:
            with _opener.open(UPSTREAM + STRIPPED_PATH, timeout=5) as upstream:
                data = json.loads(upstream.read())
        except Exception:
            self.send_response(502)
            self.end_headers()
            return
        body = json.dumps(strip_antenna_relative(data), separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        if self.command == "GET":
            self.wfile.write(body)

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None

        req_headers = forward_headers(self.headers.items())
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
        body = resp.read()
        self.send_response(status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self._send_security_headers()
        if (status == 200 and self._normalise(self.path) in PAGE_PATHS
                and (resp.headers.get("Content-Type") or "").startswith("text/html")):
            self.send_header(CSP_HEADER, page_csp(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # every request from every public viewer would otherwise hit the journal


def _save_and_exit(*_):
    try:
        VISITS.save()
    except Exception:
        pass
    os._exit(0)


if __name__ == "__main__":
    import signal
    VISITS = Visits()
    signal.signal(signal.SIGTERM, _save_and_exit)     # systemd stops it with SIGTERM
    threading.Thread(target=lambda: http.server.ThreadingHTTPServer(STATS_LISTEN, _StatsHandler).serve_forever(),
                     daemon=True).start()
    try:
        http.server.ThreadingHTTPServer(LISTEN, Handler).serve_forever()
    finally:
        try:
            VISITS.save()
        except OSError:
            pass
