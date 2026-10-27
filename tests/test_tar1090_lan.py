#!/usr/bin/env python3
"""tar1090 on the radar's own address (security review 2026-10-26).

tar1090 is upstream's page, served on the same address as the radar's page
and /setup. deploy/88-stratoscan-tar1090.conf refuses a /tar1090/ link that
names a server for it to load from, in every spelling tar1090 itself would
read, and gives its page a policy that lets it fetch only from the radar and
the services it needs. These checks run the conf's own patterns.

Run: python3 tests/test_tar1090_lan.py
"""
import pathlib
import random
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


try:
    conf = (D / "88-stratoscan-tar1090.conf").read_text()
except OSError:
    conf = ""
um = re.search(r'^\$HTTP\["url"\] =~ "([^"]+)" \{\n(.*)^\}', conf, re.M | re.S)
check(um is not None, "88-stratoscan-tar1090.conf has a block for tar1090's paths")
url_re = re.compile(um.group(1) if um else "(?!)")
body = um.group(2) if um else ""
qm = re.search(r'\$HTTP\["querystring"\] =~ "([^"]+)" \{\s*url\.access-deny = \( "" \)\s*\}', body)
check(qm is not None, "inside it, a query-string match that refuses the request")
query_re = re.compile(qm.group(1) if qm else "(?!)")

for path in ("/tar1090/", "/tar1090/index.html", "/tar1090", "/tar1090/data/aircraft.json"):
    check(url_re.search(path) is not None, "the block covers %s" % path)
for path in ("/tar1090x/", "/index.html", "/api/aircraft", "/x/tar1090/"):
    check(url_re.search(path) is None, "and not %s" % path)

# ---- the parameters that name a server -------------------------------------------
DANGEROUS = {"aiscatcher_server", "dronejson", "customtiles"}


def tar1090_reads(query):
    """The parameter names tar1090 sees: URLSearchParams decodes them
    (%-escapes, + for space) and tar1090 lowercases them (early.js, usp)."""
    return {k.lower() for k, _ in urllib.parse.parse_qsl(query, keep_blank_values=True)}


def refused(query):
    return query_re.search(query) is not None


for q in ("aiscatcher_server=http://198.51.100.7:8100", "AISCATCHER_SERVER=x", "zoom=8&aiscatcher_server=x",
          "aiscatcher%5Fserver=x", "%61iscatcher_server=x", "aiscatcher_serve%72=x", "aiscatcher_server",
          "customTiles=https://tiles.example/{z}/{x}/{y}.png", "customtiles=remove", "zoom=8&CustomTiles=x",
          "droneJson=x", "DRONEJSON=x"):
    check(refused(q), "refused: ?%s" % q)
for q in ("", "icao=a1b2c3", "lat=35.8776&lon=-78.7875&zoom=9", "sidebarWidth=300&hideSidebar",
          "filter=a%20b", "reg=N12345", "aiscatcher_serverx=1", "xaiscatcher_server=1",
          "baseMap=osm&overlays=nexrad"):
    check(not refused(q), "served: ?%s" % (q or "(no query)"))

# Every spelling tar1090 would read as one of the three is refused: each
# character %-escaped or not, in either case, at either end of the query.
rng = random.Random(1090)
missed = []
for _ in range(3000):
    name = rng.choice(sorted(DANGEROUS))
    spelt = "".join(("%%%02X" % ord(c)) if rng.random() < 0.2 else (c.upper() if rng.random() < 0.5 else c)
                    for c in name)
    q = rng.choice(["%s=x", "zoom=8&%s=x", "%s", "%s=x&icao=a1b2c3"]) % spelt
    if tar1090_reads(q) & DANGEROUS and not refused(q):
        missed.append(q)
check(not missed, "every spelling tar1090 would read is refused (3000 tried)%s" % (": " + missed[0] if missed else ""))

# ---- what its page may fetch from ------------------------------------------------
sm = re.search(r'setenv\.set-response-header = \( "Content-Security-Policy" => "([^"]+)" \)', body)
check(sm is not None, "tar1090's pages get a Content-Security-Policy")
check("setenv.add-response-header" not in conf,
      "set with set-response-header, so 88-tar1090.conf's own headers (binCraft's gzip) are left alone")
policy = {}
for part in (sm.group(1) if sm else "").split(";"):
    words = part.split()
    if words:
        policy[words[0]] = words[1:]
connect = policy.get("connect-src", [])
check("'self'" in connect and "https://api.planespotters.net" in connect,
      "it may fetch from the radar and the photo service")
check(all(s == "'self'" or s.startswith("https://") and "*" not in s for s in connect),
      "and only from named https hosts besides the radar: %s" % " ".join(connect))
check(not any("adsb.im" in s or "adsb.lol" in s for s in connect),
      "not the route lookup (tar1090 makes it over plain http on the radar's address)")
check(not any("githubusercontent" in s or s in ("http:", "https:", "*") for s in connect),
      "not GitHub's raw files, or any host at all")
check(policy.get("object-src") == ["'none'"] and policy.get("base-uri") == ["'none'"]
      and policy.get("frame-ancestors") == ["'none'"], "no plugins, no <base>, not framed")
check("script-src" not in policy and "default-src" not in policy and "img-src" not in policy,
      "scripts and map tiles are left as tar1090 has them (its inline handlers, its tile servers)")

# ---- the radar's own page and the app still read tar1090's files ------------------
page = (ROOT / "index.html").read_text()
check("fetch('/tar1090/index.html'" in page,
      "the page still reads tar1090's index for its database folder (a fetch, which a policy does not touch)")

print("tar1090 checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
