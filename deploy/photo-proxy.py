#!/usr/bin/env python3
"""
Local-only proxy for planespotters.net's photo API.

Exists purely because planespotters.net requires a descriptive custom
User-Agent identifying the calling application ("Generic library User-Agent
strings are not accepted" -- see https://www.planespotters.net/photo/api),
and browser fetch()/XMLHttpRequest can never set that header themselves --
it's exclusively controlled by the browser. So this runs server-side on the
Pi instead, listening on 127.0.0.1 only; lighttpd proxies /photo/<hex>
requests to it (see 89-stratoscan-photo-proxy.conf), keeping the browser's
fetch same-origin exactly like aircraft.json/receiver.json already are.

It also answers /photo/type?q=<aircraft type> with a representative photo of
that type from Wikipedia's lead image, credited from Wikimedia Commons (#33):
the page used to ask Wikipedia and Commons itself, so every public visitor's
browser called them. Now the unit does, once per type, with a descriptive
User-Agent as Wikimedia's policy asks.

Attribution requirement per planespotters.net's terms of use (photographer
credit + link back to the original photo) is enforced by the *caller*
(index.html), not here -- this just relays photographer/link through
unchanged so the caller has what it needs to comply.
"""
import html.parser
import http.server
import json
import re
import time
import urllib.parse
import urllib.request

LISTEN = ("127.0.0.1", 8081)
USER_AGENT = "StratoScan/1.0 (+https://github.com/mferris/StratoScan; personal ADS-B kiosk project)"
CACHE_TTL = 24 * 3600
HEX_RE = re.compile(r"/photo/([0-9a-fA-F]{6})$")

cache = {}  # hex -> (timestamp, response_body_bytes)

# The cache is keyed by a caller-supplied hex code and this service is
# reachable from the public tunnel (/photo/<hex> is not on the gateway's
# local-only list, and must not be -- public viewers need aircraft photos).
# There are 16.7M valid keys and nothing was evicting them, so a stranger
# walking the keyspace grew this dict without limit. Bounded, oldest-first.
CACHE_MAX = 4096

# Representative photos, keyed by the type's label. A type with no photo is
# remembered for an hour, not a day, in case the miss was a hiccup.
TYPE_PATH = "/photo/type"
TYPE_MAX_LEN = 80
TYPE_MISS_TTL = 3600
type_cache = {}  # label -> (timestamp, ttl, body)
WIKI_SEARCH = "https://en.wikipedia.org/w/api.php?action=query&list=search&srlimit=1&format=json&srsearch="
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
COMMONS_INFO = ("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo"
                "&iiprop=extmetadata&format=json&titles=")
# Only files on Commons are freely licensed; a file on English Wikipedia
# itself may be non-free "fair use", which doesn't extend to this app.
COMMONS_FILE_RE = re.compile(r"/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)")


class _Text(html.parser.HTMLParser):
    """The text of Commons' Artist field, which is HTML (often a user link)."""
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def html_text(s):
    t = _Text()
    t.feed(s or "")
    return " ".join("".join(t.parts).split())


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=5) as upstream:
        return json.loads(upstream.read())


def type_label(path):
    """The aircraft type asked for, or None if the request isn't a fair one."""
    parts = urllib.parse.urlsplit(path)
    if parts.path != TYPE_PATH:
        return None
    q = (urllib.parse.parse_qs(parts.query).get("q") or [""])[0].strip()
    if not q or len(q) > TYPE_MAX_LEN or not q.isprintable():
        return None
    return q


def representative_photo(label, fetch=get_json):
    """Wikipedia's lead image for the type, with its Commons credit; found
    False if there's none, it isn't on Commons, or it has no licence."""
    try:
        hits = (fetch(WIKI_SEARCH + urllib.parse.quote(label)).get("query") or {}).get("search") or []
        if not hits:
            return {"found": False}
        summary = fetch(WIKI_SUMMARY + urllib.parse.quote(hits[0]["title"].replace(" ", "_"), safe=""))
        thumb = (summary.get("thumbnail") or {}).get("source") or ""
        m = COMMONS_FILE_RE.search(thumb)
        if not thumb.startswith("https://") or not m:
            return {"found": False}
        file = urllib.parse.unquote(m.group(1))
        pages = (fetch(COMMONS_INFO + urllib.parse.quote("File:" + file)).get("query") or {}).get("pages") or {}
        info = (next(iter(pages.values()), {}).get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licence = html_text((meta.get("LicenseShortName") or {}).get("value"))
        if not licence:
            return {"found": False}
        return {
            "found": True,
            "thumb": thumb,
            "artist": (html_text((meta.get("Artist") or {}).get("value")) or "Unknown")[:80],
            "license": licence[:40],
            "page": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(file),
        }
    except Exception:
        return None  # couldn't ask: not remembered as a miss for long


def bounded_put(store, key, value):
    if len(store) >= CACHE_MAX:
        for k in sorted(store, key=lambda k: store[k][0])[:CACHE_MAX // 4]:
            store.pop(k, None)
    store[key] = value


class Handler(http.server.BaseHTTPRequestHandler):
    # A client that connects and then sends nothing (or reads nothing) held a
    # thread for good; now the socket gives up after this many seconds
    # (security review 2026-10-04, item 7).
    timeout = 30
    def version_string(self):
        return "StratoScan"  # don't advertise the Python/http.server version

    def do_GET(self):
        label = type_label(self.path)
        if label is not None:
            return self._type_photo(label)
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
            if len(cache) >= CACHE_MAX:
                # Drop the oldest entries rather than clearing: a full flush
                # would let a keyspace walk also evict the aircraft the kiosk
                # is actually showing, turning a memory bound into a way to
                # force repeated upstream fetches.
                for k in sorted(cache, key=lambda k: cache[k][0])[:CACHE_MAX // 4]:
                    cache.pop(k, None)
            cache[hexcode] = (now, body)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _type_photo(self, label):
        now = time.time()
        cached = type_cache.get(label)
        if cached and now - cached[0] < cached[1]:
            body = cached[2]
        else:
            result = representative_photo(label)
            body = json.dumps(result or {"found": False}).encode()
            ttl = CACHE_TTL if result and result["found"] else TYPE_MISS_TTL if result else 60
            bounded_put(type_cache, label, (now, ttl, body))
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
