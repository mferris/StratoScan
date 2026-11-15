#!/usr/bin/env python3
"""The radar's page on the radar itself and the LAN: framing and script
headers from lighttpd (SR-26, SR-27, 2026-11-15).

deploy/86-stratoscan-nocache.conf gives / and /index.html, on both
listeners, X-Frame-Options, nosniff and a Content-Security-Policy. The round
display loads the same page from http://localhost, so the policy must refuse
nothing the page does: every directive in it has to be one the public
gateway's policy for the same page has too, as strict or stricter there
(that one is enforced, and the page runs under it), with the one difference
that inline script is allowed here, because lighttpd can't name the page's
inline block by hash. It may not limit what the kiosk fetches.

Run: python3 tests/test_lan_page_headers.py
"""
import importlib.util
import pathlib
import re
import sys

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


def directives(policy):
    out = {}
    for part in policy.split(";"):
        words = part.split()
        if words:
            out[words[0]] = words[1:]
    return out


conf = (D / "86-stratoscan-nocache.conf").read_text()
live = "\n".join(line for line in conf.splitlines() if not line.lstrip().startswith("#"))
m = re.fullmatch(r'\s*\$HTTP\["url"\] =~ "([^"]+)" \{\n\s*setenv\.add-response-header = \(\n(.*?)\n\s*\)\n\}\s*', live, re.S)
check(m is not None, "86-stratoscan-nocache.conf is one block for the page with one list of headers")
url_re = re.compile(m.group(1).replace("\\\\", "\\") if m else "(?!)")
lines = [line.strip() for line in (m.group(2) if m else "").splitlines()]
pairs = [re.fullmatch(r'"([^"]+)" => "([^"]*)"(,?)', line) for line in lines]
check(all(pairs) and all(p.group(3) == "," for p in pairs[:-1]) and pairs[-1].group(3) == "",
      "each header a quoted pair, a comma between them and none after the last")
headers = {p.group(1): p.group(2) for p in pairs if p}
check(len(headers) == len(lines), "no header named twice")
# lighttpd keeps only the last setenv.add-response-header that matches a
# request: a second one for the page, here or in another of our files, would
# silently drop this list (or Cache-Control with it).
others = [f.name for f in D.glob("*.conf") if f.name != "86-stratoscan-nocache.conf"
          and "setenv.add-response-header" in "\n".join(
              line for line in f.read_text().splitlines() if not line.lstrip().startswith("#"))]
check(live.count("setenv.") == 1 and not others, "the only add-response-header in our lighttpd files%s"
      % ("" if not others else ": also in " + ", ".join(others)))

# ---- which requests get them --------------------------------------------------------
for path in ("/", "/index.html"):
    check(url_re.search(path) is not None, "covers %s" % path)
for path in ("/setup", "/tar1090/", "/api/aircraft", "/vendor/maplibre-gl.mjs", "/index.html/x", "/x/index.html", "/data/config.json"):
    check(url_re.search(path) is None, "and not %s" % path)
kiosk = (D / "stratoscan-kiosk.service").read_text()
km = re.search(r'"http://localhost(/[^"?]*)(\?[^"]*)?"\s*$', kiosk, re.M)
check(km is not None and url_re.search(km.group(1)) is not None,
      "the round display's own address (http://localhost%s) is one of them" % (km.group(1) if km else "?"))
check("86-stratoscan-nocache.conf" in (D / "install-setup-server.sh").read_text(), "the installer installs the file")

# ---- what they say --------------------------------------------------------------------
check(headers.get("Cache-Control") == "no-cache", "the page is still revalidated on every load")
check(headers.get("X-Frame-Options") == "DENY" and headers.get("X-Content-Type-Options") == "nosniff",
      "X-Frame-Options: DENY and nosniff")
check(headers["X-Frame-Options"] == fg.SECURITY_HEADERS["X-Frame-Options"]
      and headers["X-Content-Type-Options"] == fg.SECURITY_HEADERS["X-Content-Type-Options"], "as the public page has them")
check("Content-Security-Policy" in headers and "Content-Security-Policy-Report-Only" not in headers,
      "a Content-Security-Policy, enforced")
lan = directives(headers.get("Content-Security-Policy", ""))
for d in ("frame-ancestors", "object-src", "base-uri"):
    check(lan.get(d) == ["'none'"], "%s 'none'" % d)
check(lan.get("script-src") == ["'self'", "'unsafe-inline'"],
      "scripts from the radar itself and the page's own inline block: no other host, no eval")

# ---- nothing here can stop the round display painting -----------------------------------
# The public policy for this very page is enforced (CSP_ENFORCE) and the page
# runs under it. So a directive here is safe if the public one has it and
# allows no more than this one does.
page = (root / "index.html").read_bytes()
public = directives(fg.page_csp(page))
check(fg.CSP_HEADER == "Content-Security-Policy", "the public policy is the enforced one")
for name, allowed in lan.items():
    pub = public.get(name)
    extra = [] if pub is None else [s for s in pub if s not in allowed and not s.startswith("'sha256-")]
    check(pub is not None and not extra,
          "%s: the public policy has it and allows nothing this one refuses%s" % (name, "" if not extra else " (%s)" % " ".join(extra)))
check("'unsafe-inline'" not in public["script-src"] and any(s.startswith("'sha256-") for s in public["script-src"]),
      "the public policy still names the inline block by hash, never 'unsafe-inline'")
check("'unsafe-inline'" in lan.get("script-src", []) and not any(s.startswith("'sha256-") or s.startswith("'nonce-") for s in lan.get("script-src", [])),
      "this one allows the inline block outright: a hash here would go stale at the page's next update")
for d in ("default-src", "connect-src", "img-src", "media-src", "style-src", "font-src", "form-action", "frame-src", "sandbox",
          "upgrade-insecure-requests", "require-trusted-types-for", "report-uri", "report-to"):
    check(d not in lan, "no %s: what the kiosk fetches, plays and draws is untouched" % d)
text = page.decode("utf-8")
check("http://127.0.0.1:8090" in text, "(the kiosk does fetch from the unit's own API on another port)")
check(not re.search(r"<(base|object|embed|applet)\b", text, re.I), "the page has no <base> and no plugin for the policy to refuse")
check(not re.search(r"\beval\s*\(|new Function\s*\(|set(Timeout|Interval)\s*\(\s*['\"`]", text), "and passes no text to eval")
scripts = re.findall(r"<script\b([^>]*)>", text)
check(all(not a.strip() or re.search(r'src="(?!https?:|//)', a) for a in scripts),
      "its script tags are inline or its own files")
imports = re.findall(r"\bimport\(\s*(['\"])(.*?)\1", text)
check(imports and all(src.startswith("./vendor/") for _, src in imports), "and what it imports is under vendor/")

print("LAN page header checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
