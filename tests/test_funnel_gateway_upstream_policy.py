#!/usr/bin/env python3
"""The web server's own policy headers never reach a public caller
(2026-11-15).

lighttpd gives the radar's page, on the radar and the home LAN, a
Content-Security-Policy of its own (deploy/86-stratoscan-nocache.conf),
which allows inline scripts, and tar1090's pages one and a report-only one
(deploy/88-stratoscan-tar1090.conf). The gateway fetches from that same
lighttpd. Relayed as they came, a public 200 of the page carried two
policies, and a public 304 carried the LAN's alone, which a browser stores
over the strict one it had kept with the page.

So the gateway drops the upstream's Content-Security-Policy,
Content-Security-Policy-Report-Only, X-Frame-Options and
X-Content-Type-Options from every answer it relays, whatever the status,
and sends only its own: the hashed policy on a 200 of the page, none on a
304. Runs the real gateway in front of a stand-in for a lighttpd that has
both conf files installed.

Run: python3 tests/test_funnel_gateway_upstream_policy.py
"""
import http.client
import http.server
import importlib.util
import pathlib
import re
import sys
import threading

root = pathlib.Path(__file__).resolve().parent.parent
D = root / "deploy"
spec = importlib.util.spec_from_file_location("fg", D / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def conf_headers(name):
    """The headers a conf file's one header list sets, comments left out."""
    live = "\n".join(line for line in (D / name).read_text().splitlines() if not line.lstrip().startswith("#"))
    return dict(re.findall(r'^\s*"([^"]+)" => "([^"]*)",?$', live, re.M))


LAN_PAGE = conf_headers("86-stratoscan-nocache.conf")
LAN_TAR1090 = conf_headers("88-stratoscan-tar1090.conf")
check("'unsafe-inline'" in LAN_PAGE.get("Content-Security-Policy", "") and "X-Frame-Options" in LAN_PAGE
      and "X-Content-Type-Options" in LAN_PAGE,
      "(the LAN's page headers, read from the conf file: a policy that allows inline script, and two more)")
check({"Content-Security-Policy", "Content-Security-Policy-Report-Only"} <= set(LAN_TAR1090),
      "(and tar1090's: a policy and a report-only one)")

PAGE = b"<html><head><script>start();</script></head><body>radar</body></html>"
ETAG = '"page-1"'


class Lighttpd(http.server.BaseHTTPRequestHandler):
    """lighttpd with both conf files in: the LAN's headers on the page, for
    a 200 and a 304 alike, and tar1090's on its pages. The policy headers
    are also put on a script and on a 404, which lighttpd does not do today,
    so that a later conf can't leak them either."""

    def _any(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            extra, ctype, body = LAN_PAGE, "text/html", PAGE
        elif path.startswith("/tar1090/"):
            extra, ctype, body = LAN_TAR1090, "text/html", b"<html><script>tar();</script></html>"
        elif path == "/vendor/app.js":
            extra, ctype, body = LAN_PAGE, "text/javascript", b"go();"
        else:
            extra, ctype, body = LAN_PAGE, "text/html", b"<html>not found</html>"
        status = 200 if path != "/missing" else 404
        if status == 200 and self.headers.get("If-None-Match") == ETAG:
            status, body = 304, b""
        self.send_response(status)
        self.send_header("ETag", ETAG)
        for k, v in extra.items():
            self.send_header(k, v)
        if status != 304:
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = _any

    def log_message(self, *a):
        pass


up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Lighttpd)
threading.Thread(target=up.serve_forever, daemon=True).start()
fg.UPSTREAM = "http://127.0.0.1:%d" % up.server_address[1]
gw = fg.QuietServer(("127.0.0.1", 0), fg.Handler)
threading.Thread(target=gw.serve_forever, daemon=True).start()


def public(method, path, **headers):
    """What a public caller receives: the status, the body, and every value
    of each header, lower-cased names."""
    c = http.client.HTTPConnection("127.0.0.1", gw.server_address[1], timeout=10)
    c.request(method, path, headers=headers)
    r = c.getresponse()
    body = r.read()
    got = {}
    for k, v in r.getheaders():
        got.setdefault(k.lower(), []).append(v)
    c.close()
    return r.status, body, got


CSP, CSP_RO = "content-security-policy", "content-security-policy-report-only"


def own_two_only(h):
    return h.get("x-frame-options") == [fg.SECURITY_HEADERS["X-Frame-Options"]] \
        and h.get("x-content-type-options") == [fg.SECURITY_HEADERS["X-Content-Type-Options"]]


check(fg.CSP_HEADER == "Content-Security-Policy", "(the gateway's policy is the enforced one)")

# ---- a 200 of the page ------------------------------------------------------------
for path in ("/", "/index.html"):
    status, body, h = public("GET", path)
    check(status == 200 and body == PAGE, "GET %s: the page" % path)
    check(h.get(CSP) == [fg.page_csp(PAGE)], "one Content-Security-Policy, the gateway's own for these bytes")
    check("'unsafe-inline'" not in h.get(CSP, [""])[0].split("script-src", 1)[-1].split(";", 1)[0]
          and "'sha256-" in h.get(CSP, [""])[0], "scripts by hash, never 'unsafe-inline': the LAN's policy is not in it")
    check(CSP_RO not in h, "no report-only policy")
    check(own_two_only(h), "X-Frame-Options and nosniff once each, the gateway's")
    check(h.get("etag") == [ETAG], "everything else the web server said is still relayed (its ETag)")

# ---- a 304 of the page: the case that undid the stored policy ---------------------
for path in ("/", "/index.html"):
    status, body, h = public("GET", path, **{"If-None-Match": ETAG})
    check(status == 304 and body == b"", "GET %s, revalidated: 304" % path)
    check(CSP not in h and CSP_RO not in h,
          "no Content-Security-Policy of any kind, so the browser keeps the strict one it stored")
    check(own_two_only(h), "X-Frame-Options and nosniff once each, the gateway's")
    check(h.get("etag") == [ETAG], "the ETag is still relayed")

# ---- every other answer -------------------------------------------------------------
status, _, h = public("HEAD", "/")
check(status == 200 and CSP not in h and CSP_RO not in h and own_two_only(h),
      "HEAD /: no policy (there is no body to hash), and not the LAN's")
status, _, h = public("GET", "/tar1090/")
check(status == 200 and h.get(CSP) == [fg.TAR1090_CSP] and CSP_RO not in h and own_two_only(h),
      "tar1090's page: the gateway's policy for it alone; the LAN's two are dropped")
status, _, h = public("GET", "/tar1090/", **{"If-None-Match": ETAG})
check(status == 304 and CSP not in h and CSP_RO not in h and own_two_only(h), "and on its 304, none")
for method, path, want in (("GET", "/vendor/app.js", 200), ("GET", "/missing", 404), ("HEAD", "/missing", 404)):
    status, _, h = public(method, path)
    check(status == want and CSP not in h and CSP_RO not in h and own_two_only(h),
          "%s %s (%d): no upstream policy header either" % (method, path, want))

# ---- and by name ----------------------------------------------------------------------
check(fg.UPSTREAM_POLICY_HEADERS == {CSP, CSP_RO, "x-frame-options", "x-content-type-options"},
      "the four headers dropped are the four the conf files set, whatever their case")
check({k.lower() for k in LAN_PAGE} - {"cache-control"} <= fg.UPSTREAM_POLICY_HEADERS
      and {k.lower() for k in LAN_TAR1090} <= fg.UPSTREAM_POLICY_HEADERS,
      "every policy header the two conf files send is one of them (Cache-Control is relayed)")

# ---- the order it reaches a unit in -----------------------------------------------------
# The gateway arrives by an update; the conf files only by hand. A unit with
# the conf files and the old gateway is the broken combination.
for name in ("86-stratoscan-nocache.conf", "88-stratoscan-tar1090.conf"):
    top = "\n".join((D / name).read_text().splitlines()[:14])
    check("ORDER" in top and "funnel-gateway.py" in top and "update comes first" in top,
          "%s says at its top that the gateway's update comes first" % name)

print("gateway upstream policy checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
