#!/usr/bin/env python3
"""The public gateway and lighttpd must agree on which path a request names.

Security review 2026-11-03, SR-01. The gateway decided on a path it had
percent-decoded up to four times and collapsed, then forwarded the client's
own bytes, which lighttpd decodes once. lighttpd's static handler also
served a file with anything after its name. Between the two, a request the
gateway took for "/" reached a private file or a house-only backend.

This runs the real gateway in front of a stand-in for lighttpd that behaves
as the radar's lighttpd 1.4.79 does (calibrated against it on the LAN: the
table LIGHTTPD_OBSERVED below is what it answered, by status only), and asks
for every private file and backend in many spellings: encoded once, twice
and three times, %2E and %2e mixed, overlong UTF-8, path-info suffixes,
semicolons, backslashes, encoded slashes, NULs and control characters,
absolute-form targets, and paths hidden in the query.

Three ways round:
  A. the gateway alone, in front of a lighttpd configured as before SR-01
     (path-info served, no public deny block). An update delivers the
     gateway, not lighttpd's config, so this must hold on its own.
  B. the gateway in front of a lighttpd with 82- and 83-stratoscan-*.conf.
  C. lighttpd's confs alone, behind a gateway that forwards every request
     as the client sent it (the old bug, or a new one): the marked request
     still reaches nothing private.
And the house-only backends (photo-proxy, tts, wake) refuse the marker.

Run: python3 tests/test_funnel_gateway_decode_once.py [path/to/funnel-gateway.py]
"""
import http.client
import http.server
import importlib.util
import json
import os
import pathlib
import re
import sys
import tempfile
import threading
import urllib.parse

root = pathlib.Path(__file__).resolve().parent.parent
D = root / "deploy"
GATEWAY = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else D / "funnel-gateway.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fg = load("fg_decode_once", GATEWAY)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


# ---- the radar's files (fixture values: RDU airport) -------------------------
LAT, LON = 35.8776, -78.7875
EXACT = ("35.8776", "-78.7875")
MARKERS = {
    "receiver.json": json.dumps({"lat": LAT, "lon": LON, "refresh": 1000, "version": "x"}),
    "aircraft.json": json.dumps({"now": 1, "aircraft": [{"hex": "a1b2c3", "lat": 35.95, "lon": -78.7,
                                                         "r_dst": 3.2, "r_dir": 41.0}]}),
    "status.json": json.dumps({"now": 1, "uptime": 5}),
    "stats.json": json.dumps({"STATS-MARKER": 1}),
    "outline.json": json.dumps({"OUTLINE-MARKER": 1}),
}
SECRETS = ("r_dst", "r_dir", "STATS-MARKER", "OUTLINE-MARKER", "NOTABLE-PERSON-MARKER", "POWER-MARKER",
           "BACKEND-REACHED") + EXACT

tmp = pathlib.Path(tempfile.mkdtemp(prefix="sr01-"))
www, readsb, html = tmp / "www", tmp / "readsb", tmp / "tar1090html"
for d in (www / "data", readsb, html):
    d.mkdir(parents=True)
(www / "index.html").write_text("<html><script>go();</script></html>")
(www / "config.json").write_text("{}")
(www / "data" / "notable.json").write_text("{}")
(www / "data" / "notable-people.json").write_text(json.dumps({"names": {"a00003": "NOTABLE-PERSON-MARKER"}}))
(www / "data" / "power.json").write_text(json.dumps({"POWER-MARKER": 1}))
(html / "index.html").write_text("<html>tar1090</html>")
(www / "offline-map" / "fonts" / "Noto Sans Regular").mkdir(parents=True)
(www / "offline-map" / "fonts" / "Noto Sans Regular" / "0-255.pbf").write_text("glyphs")
for name, body in MARKERS.items():
    (readsb / name).write_text(body)
ALIASES = [("/tar1090/data/", readsb), ("/tar1090/", html)]       # longest first, as 88-tar1090.conf
PROXIED = [(r"^/photo/", "photo"), (r"^/approaches", "approaches"), (r"^/sightings", "sightings"),
           (r"^/api/", "core"), (r"^/network", "network"), (r"^/wake", "wake"), (r"^/tts", "tts"),
           (r"^/setup", "setup")]
HOUSE_ONLY = {"photo", "wake", "tts", "setup"}
PRIVATE_FILES = {readsb / "stats.json", readsb / "outline.json",
                 www / "data" / "notable-people.json", www / "data" / "power.json"}


# ---- lighttpd's confs, read from the files that ship ---------------------------
def public_conf():
    text = (D / "83-stratoscan-public.conf").read_text()
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    marker = re.search(r'\$REQUEST_HEADER\["([^"]+)"\]\s*!=\s*""', body)
    deny = re.findall(r'\$HTTP\["url"\]\s*=~\s*"((?:[^"\\]|\\.)*)"', body)
    allow = re.findall(r'\$HTTP\["url"\]\s*!~\s*"((?:[^"\\]|\\.)*)"', body)
    return marker and marker.group(1), deny, allow


def pathinfo_disabled():
    text = (D / "82-stratoscan-pathinfo.conf").read_text()
    return any(re.fullmatch(r'\s*static-file\.disable-pathinfo\s*=\s*"enable"\s*', l) for l in text.splitlines())


CONF_MARKER, CONF_DENY, CONF_ALLOW = public_conf()


# ---- a stand-in for lighttpd 1.4.79 --------------------------------------------
def simplify(path):
    """lighttpd's path clean-up: '//' collapsed, '.' and '..' resolved (never
    above the root), a trailing slash kept."""
    parts = path.split("/")[1:]
    out = []
    for i, seg in enumerate(parts):
        last = i == len(parts) - 1
        if seg in ("", "."):
            if last:
                out.append("")
            continue
        if seg == "..":
            if out:
                out.pop()
            if last:
                out.append("")
            continue
        out.append(seg)
    return "/" + "/".join(out)


class Lighttpd:
    """Decodes the path once, refuses control bytes and the 0xC0/0xC1 lead
    bytes with 400, cleans the path up, applies the public deny block when
    configured, routes ^/prefix to its backends, and serves static files with
    or without path-info."""

    def __init__(self, with_confs):
        self.with_confs = with_confs
        self.log = []                       # (url, what answered, marker present)

    def answer(self, target, headers):
        raw, _, _query = target.partition("?")
        if not raw.startswith("/"):
            return 400, b"bad request"
        b = urllib.parse.unquote_to_bytes(raw)
        if any(c < 0x20 or c == 0x7f or c in (0xc0, 0xc1) for c in b):
            return 400, b"bad request"
        url = simplify(b.decode("latin-1"))
        marked = any(k.lower() == "x-fr-public" and v != "" for k, v in headers.items())
        if self.with_confs and marked:
            if re.search(CONF_DENY[0], url):
                self.log.append((url, "denied", marked))
                return 403, b"forbidden"
            if re.search(CONF_DENY[1], url) and not re.search(CONF_ALLOW[0], url):
                self.log.append((url, "denied", marked))
                return 403, b"forbidden"
        for rx, name in PROXIED:
            if re.search(rx, url):
                self.log.append((url, name, marked))
                return 200, json.dumps({"backend": name, "note": "BACKEND-REACHED" if name in HOUSE_ONLY else ""}).encode()
        base, rest = www, url
        for prefix, d in ALIASES:
            if url.startswith(prefix):
                base, rest = d, url[len(prefix) - 1:]
                break
        fs = pathlib.Path(str(base) + rest)
        if rest.endswith("/") and (fs / "index.html").is_file():
            return self._file(url, fs / "index.html", marked)
        if fs.is_file() and not rest.endswith("/"):
            return self._file(url, fs, marked)
        if os.path.isdir(fs):
            return 403, b"forbidden"
        segs = rest.split("/")
        for n in range(len(segs) - 1, 0, -1):          # path-info: the longest prefix that is a file
            cand = pathlib.Path(str(base) + "/".join(segs[:n]))
            if cand.is_file():
                if self.with_confs and pathinfo_disabled():
                    return 404, b"not found"
                return self._file(url, cand, marked)
        return 404, b"not found"

    def _file(self, url, fs, marked):
        self.log.append((url, fs, marked))
        return 200, fs.read_bytes()


# What the radar's lighttpd 1.4.79 answered on 2026-11-04 (status only, asked
# from the radar itself, before 82- and 83-stratoscan-*.conf). The stand-in
# must agree, or the rest of this test proves nothing.
LIGHTTPD_OBSERVED = [
    (200, "/tar1090/data/receiver.json"), (200, "/tar1090/data/receiver.json/x"),
    (403, "/tar1090/data/receiver.json/%2e%2e"), (403, "/tar1090/data/receiver.json/%2E%2e"),
    (200, "/tar1090/data/receiver.json/%252e%252e"),
    (200, "/tar1090/data/receiver.json/%252e%252e/%252e%252e/%252e%252e"),
    (200, "/tar1090/data/receiver.json/%25252e%25252e"), (404, "/tar1090/data/receiver.json%3bx"),
    (404, "/tar1090/data/receiver.json;x"), (200, "/tar1090/data/receiver.json%2fx"),
    (404, "/tar1090/data/receiver.json%5cx"), (404, "/TAR1090/data/receiver.json"),
    (200, "/tar1090/data/%72eceiver.json"), (200, "/tar1090/data/stats.json/x"),
    (200, "/tar1090/data/outline.json/x"), (200, "/index.html/x"), (200, "/data/notable-people.json"),
    (200, "/data/notable-people.json/x"), (200, "/tar1090//data/receiver.json"),
    (400, "/tar1090/data/receiver.json%c0%ae"), (404, "/tar1090/data/receiver.json/.%2e/x"),
    (400, "/tar1090/data/receiver.json%00"), (400, "/tar1090/data/receiver.json%0a"),
    (200, "/tar1090/data/receiver.json/%ef%bc%8e%ef%bc%8e"), (404, "/tar1090/data/receiver.json%20"),
    (200, "/tar1090/data/receiver.json/."), (200, "/tar1090/data/./receiver.json"),
    (200, "/tar1090/data/x/../receiver.json"), (200, "/../../tar1090/data/receiver.json"),
    (200, "/tar1090/data/receiver.json/%e0%80%ae%e0%80%ae"), (403, "/tar1090/data/receiver.json/..%2f"),
    (200, "/tar1090/data/receiver.json/"),
]
stand_in = Lighttpd(with_confs=False)
off = [(want, p, stand_in.answer(p, {})[0]) for want, p in LIGHTTPD_OBSERVED if stand_in.answer(p, {})[0] != want]
check(not off, "the stand-in answers as the radar's lighttpd did, %d spellings%s"
      % (len(LIGHTTPD_OBSERVED), "" if not off else ": " + "; ".join("%s want %d got %d" % (p, w, g) for w, p, g in off)))


# ---- the stand-in on a socket, and the gateway in front of it --------------------
class Upstream(http.server.BaseHTTPRequestHandler):
    lighttpd = None

    def _any(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        status, body = self.lighttpd.answer(self.path, dict(self.headers.items()))
        self.send_response(status)
        self.send_header("Content-Type", "text/html" if body.startswith(b"<html") else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_POST = _any

    def log_message(self, *a):
        pass


def serve(handler_cls):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def ask(port, target, method="GET", headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.putrequest(method, target, skip_host=True, skip_accept_encoding=True)
    c.putheader("Host", "127.0.0.1")
    for k, v in (headers or {}).items():
        c.putheader(k, v)
    c.endheaders()
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, body


# ---- the spellings ----------------------------------------------------------------
UPS = {                                  # ways to write ".."
    "plain": "..", "single": "%2e%2e", "upper": "%2E%2E", "mixed": "%2E%2e", "half": ".%2e",
    "double": "%252e%252e", "double-mixed": "%252E%252e", "double-half": ".%252e",
    "triple": "%25252e%25252e", "triple-mixed": "%25252E%25252e",
    "overlong2": "%c0%ae%c0%ae", "overlong3": "%e0%80%ae%e0%80%ae", "double-overlong": "%25c0%25ae%25c0%25ae",
    "fullwidth": "%ef%bc%8e%ef%bc%8e",
}
SEPS = {"slash": "/", "enc-slash": "%2f", "double-enc-slash": "%252f", "backslash": "%5c",
        "double-backslash": "%255c", "semicolon": ";/"}
SUFFIXES = ["/x", "/", "/.", "/%2e", "/%252e", ";x", "%3bx", "/;x", "%2fx", "%252fx", "%00", "/%00", "%0a",
            "%20", "%5cx", "%09", "%7f", "/%2e%2e%2f", "%3f/x", "%23/x"]
FILES = {
    "receiver.json": "/tar1090/data/receiver.json", "aircraft.json": "/tar1090/data/aircraft.json",
    "stats.json": "/tar1090/data/stats.json", "outline.json": "/tar1090/data/outline.json",
    "notable-people": "/data/notable-people.json", "power": "/data/power.json",
}
BACKENDS = {                             # (prefix, what follows the climb, query)
    "setup": ("/setup", "x", ""), "wake": ("/wake", "alive", ""), "tts": ("/tts", "x", "?text=hello"),
    "photo": ("/photo", "x", "?/photo/abcdef"),
}


def attacks():
    out = {}
    for target, path in FILES.items():
        ps = out.setdefault(target, [])
        for up in UPS.values():
            for sep in SEPS.values():
                for n in (1, 2, 3):
                    ps.append(path + sep + (up + sep) * (n - 1) + up)
                    ps.append(path + (sep + up) * n + sep + "x")
            ps.append("/x/" + up + path)
        ps += [path + s for s in SUFFIXES]
        ps += ["/" + path, "/." + path, path.upper(), path.replace("/data/", "/DATA/"),
               "http://127.0.0.1" + path, "//127.0.0.1" + path, path.replace("json", "%6a%73%6f%6e") + "/x"]
    for target, (prefix, tail, query) in BACKENDS.items():
        ps = out.setdefault(target, [])
        for up in UPS.values():
            for sep in SEPS.values():
                for n in (1, 2, 3):
                    ps.append(prefix + (sep + up) * n + sep + tail + query)
            ps.append("/x/" + up + prefix + "/" + tail + query)
            ps.append("/x/" + up + "/" + prefix.lstrip("/") + query)
        ps += [prefix + query, prefix + "/" + tail + query, prefix.upper() + query, "/" + prefix + query,
               "/." + prefix + query, prefix + ";x" + query, prefix + "%00" + query,
               "/%" + "%02x" % ord(prefix[1]) + prefix[2:] + query,
               "/%25" + "%02x" % ord(prefix[1]) + prefix[2:] + query,
               "http://127.0.0.1" + prefix + query]
    out["photo"] += ["/x?/photo/abcdef", "/x/?/photo/abcdef", "/photo/abcdef", "/photo/type?q=Cessna"]
    return out


ATTACKS = attacks()
check(all(len(ATTACKS[t]) > 50 for t in list(FILES) + list(BACKENDS)),
      "every private file and house-only backend is asked for in many spellings (%d in all)"
      % sum(len(v) for v in ATTACKS.values()))


def leaked(status, body, log_before, lighttpd):
    """What, if anything, a public answer gave away."""
    text = body.decode("latin-1")
    found = [s for s in SECRETS if s in text]
    for url, what, marked in lighttpd.log[log_before:]:
        if what in HOUSE_ONLY:
            found.append("reached " + what)
        elif what in PRIVATE_FILES:
            found.append("served " + pathlib.Path(what).name)
    return found


def through_gateway(with_confs):
    lt = Lighttpd(with_confs)
    Upstream.lighttpd = lt
    up = serve(type("U", (Upstream,), {"lighttpd": lt}))
    fg.UPSTREAM = "http://127.0.0.1:%d" % up.server_address[1]
    gw = fg.QuietServer(("127.0.0.1", 0), fg.Handler)
    threading.Thread(target=gw.serve_forever, daemon=True).start()
    port = gw.server_address[1]
    results = {}
    for target, paths in ATTACKS.items():
        bad = []
        # receiver.json and aircraft.json are public, rounded and stripped by
        # the gateway: a spelling of their own name may be served that way.
        # Anything else must be refused.
        rewritten = target in ("receiver.json", "aircraft.json")
        for p in paths:
            for method in ("GET", "HEAD"):
                before = len(lt.log)
                status, body = ask(port, p, method)
                found = leaked(status, body, before, lt)
                if found or status not in ((200, 400, 403, 404) if rewritten else (400, 403, 404)):
                    bad.append("%s %s -> %d %s" % (method, p, status, ",".join(found)))
        results[target] = bad
    # And the public page still works: the files it reads, rounded and stripped.
    served = {}
    for p in ("/", "/index.html", "/tar1090/", "/config.json", "/data/notable.json", "/tar1090/data/status.json",
              "/tar1090/data/receiver.json", "/tar1090/data/receiver.json?_=1", "/tar1090/data/aircraft.json",
              "/tar1090/data/aircraft.json?_=17", "/offline-map/fonts/Noto%20Sans%20Regular/0-255.pbf"):
        served[p] = ask(port, p)
    gw.shutdown()
    up.shutdown()
    return results, served, lt


for label, with_confs in (("A, the gateway alone (lighttpd as before)", False),
                          ("B, the gateway and lighttpd's new confs", True)):
    results, served, lt = through_gateway(with_confs)
    for target, bad in results.items():
        check(not bad, "%s: no public spelling of %s gives anything away%s"
              % (label, target, "" if not bad else " (%d did, e.g. %s)" % (len(bad), "; ".join(bad[:3]))))
    ok_pages = all(s == 200 for s, _ in served.values())
    check(ok_pages, "%s: the public page's own files are still served%s"
          % (label, "" if ok_pages else ": " + ", ".join("%s %d" % (p, s) for p, (s, _) in served.items() if s != 200)))
    rec = json.loads(served["/tar1090/data/receiver.json"][1] or b"{}")
    check(rec.get("lat") == 35.88 and rec.get("lon") == -78.79 and rec.get("refresh") == 1000,
          "%s: receiver.json is rounded, the rest as written" % label)
    ac = served["/tar1090/data/aircraft.json?_=17"][1]
    check(b"r_dst" not in ac and b"35.95" in ac, "%s: aircraft.json keeps positions, loses r_dst and r_dir" % label)
    check(all(m for _, _, m in lt.log), "%s: everything the gateway forwarded carried the public marker" % label)


# ---- the gateway's decision, by itself ------------------------------------------------
canon = getattr(fg, "canonical_path", None)
check(canon is not None, "the gateway has one function that names a request's path")
if canon:
    want = {
        "/tar1090/data/receiver.json": "/tar1090/data/receiver.json",
        "/tar1090/data/%72eceiver.json?x=%252e": "/tar1090/data/receiver.json",
        "/a%20b": "/a b", "/%2e%2e": None, "/a/%252e": None, "/a/./b": None, "/a/.": None, "/a//b": None,
        "/a\\b": None, "/a%5cb": None, "/a;b": None, "/a%3bb": None, "/a%00": None, "/a%0d%0a": None,
        "/a%c0%ae": None, "/a%e0%80%ae": None, "/a%ef%bc%8e": None, "/a%": None, "/a%zz": None,
        "http://x/a": None, "*": None, "": None, "/a..b": None, "/café": None,
        "/tar1090/": "/tar1090/", "/sightings/stats/": "/sightings/stats/",
    }
    wrong = [(p, canon(p), w) for p, w in want.items() if canon(p) != w]
    check(not wrong, "it decodes once and refuses whatever is still ambiguous%s"
          % ("" if not wrong else ": " + "; ".join("%r -> %r not %r" % x for x in wrong)))
    rt = [p for p in ("/a b", "/a?b", "/a#b", "/a&b=c", "/tar1090/data/receiver.json", "/x/~y/z.json", "/tar1090/")
          if simplify(urllib.parse.unquote_to_bytes(fg.upstream_target(p, "").partition("?")[0]).decode("latin-1")) != p]
    check(not rt, "what it forwards decodes, once, to exactly the path it decided on%s" % ("" if not rt else ": %s" % rt))
    check(fg.upstream_target("/tar1090/data/receiver.json", "a=%252e&b") == "/tar1090/data/receiver.json?a=%252e&b",
          "and the query goes as the client sent it")
    src = GATEWAY.read_text()
    check("UPSTREAM + self.path" not in src and "range(4)" not in src.split("def refused_query")[0]
          and "posixpath.normpath" not in src, "nothing is forwarded as the client spelled it, or decoded more than once")


# ---- C: lighttpd's confs alone, behind a gateway that forwards everything raw --------
check(pathinfo_disabled(), "82-stratoscan-pathinfo.conf turns off path-info, outside any condition")
check(CONF_MARKER == fg.PUBLIC_MARKER and len(CONF_DENY) == 2 and len(CONF_ALLOW) == 1,
      "83-stratoscan-public.conf keys on the gateway's own marker (%r)" % CONF_MARKER)
lt = Lighttpd(with_confs=True)
raw_bad = []
for target, paths in ATTACKS.items():
    for p in paths:
        before = len(lt.log)
        status, body = lt.answer(p, {"X-FR-Public": "1"})
        found = [f for f in leaked(status, body, before, lt) if f not in EXACT]
        # The exact receiver.json and aircraft.json are allowed by name (the
        # gateway rounds and strips them); anything else under a name is not.
        if any(url in fg.TAR1090_PUBLIC_FILES for url, _, _ in lt.log[before:]):
            found = [f for f in found if f not in ("r_dst", "r_dir")]
        if found:
            raw_bad.append("%s -> %d %s" % (p, status, ",".join(found)))
check(not raw_bad, "C: marked public, no spelling reaches a private file or a house-only backend%s"
      % ("" if not raw_bad else " (%d did, e.g. %s)" % (len(raw_bad), "; ".join(raw_bad[:3]))))
marked = {p: lt.answer(p, {"X-FR-Public": "1"})[0] for p in sorted(fg.TAR1090_PUBLIC_FILES)}
check(all(s == 200 for s in marked.values()), "C: marked public, the three files the page reads are served: %s" % marked)
for p in ("/setup", "/wake/alive", "/tts?text=hi", "/photo/abcdef", "/data/notable-people.json", "/data/power.json",
          "/tar1090/data/stats.json", "/tar1090/data/outline.json", "/tar1090/data/aircraft.binCraft.zst",
          "/tar1090/chunks/chunks.json", "/tar1090/globe_history/x", "/tar1090/data/receiver.json/",
          "/Setup", "/PHOTO/abcdef"):
    check(lt.answer(p, {"X-FR-Public": "1"})[0] in (403, 404), "C: marked public, %s is refused" % p)
lan = {p: lt.answer(p, {})[0] for p in ("/setup", "/wake/alive", "/tts?text=hi", "/photo/abcdef",
                                       "/data/notable-people.json", "/tar1090/data/stats.json", "/")}
check(all(s == 200 for s in lan.values()), "C: unmarked (the radar and the LAN), all of it as before: %s" % lan)
check(lt.answer("/index.html/x", {})[0] == 404 and lt.answer("/tar1090/data/receiver.json/x", {})[0] == 404,
      "C: with path-info off, a file is served only under its own name, on the LAN too")
gaps = [p for p in fg.LOCAL_ONLY_PATHS if not re.search(CONF_DENY[0], p) or not re.search(CONF_DENY[0], p + "x")]
gaps += [p for p in fg.TAR1090_PRIVATE_PREFIXES if not re.search(CONF_DENY[1], p + "/x")]
gaps += [p for p in fg.TAR1090_PUBLIC_FILES if not re.search(CONF_ALLOW[0], p) or re.search(CONF_ALLOW[0], p + "/x")]
check(not gaps, "the conf's lists and the gateway's agree%s" % ("" if not gaps else ": %s" % gaps))
inst = (D / "install-setup-server.sh").read_text()
check("82-stratoscan-pathinfo.conf" in inst and "83-stratoscan-public.conf" in inst,
      "the installer installs both confs")
ota = (D / "ota.py").read_text()
check(all('"%s"' % f in ota for f in ("funnel-gateway.py", "photo-proxy.py", "tts-service.py", "wake-listener.py")),
      "an update delivers the gateway and the three backends (it cannot deliver lighttpd's confs)")


# ---- the house-only backends refuse the marker themselves -----------------------------
pp = load("pp_decode_once", D / "photo-proxy.py")
pp.Handler._fetch = lambda self, hexcode: {"found": True, "thumb": "https://x.example/t.jpg"}
pp.representative_photo = lambda label, *a, **k: {"found": True}
srv = serve(pp.Handler)
port = srv.server_address[1]
check(ask(port, "/photo/a1b2c3")[0] == 200, "photo-proxy: the house still gets a photo")
check(ask(port, "/photo/a1b2c3", headers={"X-FR-Public": "1"})[0] == 404
      and ask(port, "/photo/type?q=Cessna", headers={"X-FR-Public": "1"})[0] == 404,
      "photo-proxy: a request marked public is refused")
check(ask(port, "/x?/photo/abcdef")[0] == 404 and ask(port, "/photo/%2e%2e/x?/photo/abcdef")[0] == 404
      and ask(port, "/x/photo/abcdef")[0] == 404, "photo-proxy: the hex is read from the whole path, never the query")
srv.shutdown()

tts = load("tts_decode_once", D / "tts-service.py")
tts._voice = object()
tts.synthesize = lambda text: b"RIFFwav"
srv = serve(tts.Handler)
port = srv.server_address[1]
check(ask(port, "/tts?text=hello")[0] == 200, "tts: the house still gets speech")
check(ask(port, "/tts?text=hello", headers={"X-FR-Public": "1"})[0] == 404, "tts: a request marked public is refused")
srv.shutdown()

wl = load("wl_decode_once", D / "wake-listener.py")


def _never(*a, **k):
    raise AssertionError("a marked request got past the check")


wl._ensure_wayland = _never
srv = serve(wl.Handler)
port = srv.server_address[1]
check(all(ask(port, p, "POST", {"X-FR-Public": "1", "Content-Length": "0"})[0] == 404
          for p in ("/wake", "/wake/alive", "/wake/mode?m=on", "/wake/touch")),
      "wake: a request marked public is refused before it does anything")
srv.shutdown()

ss = (D / "setup-server.py").read_text()
check('self.headers.get("X-FR-Public") is not None' in ss, "setup-server: refuses the marker, as it always has")

print("decode-once checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
