#!/usr/bin/env python3
"""Who may write to the shared stores (security review 2026-10-26).

The sighting and approach stores take writes from the radar's own page and
from programs on the radar, nothing else: JSON only (a browser asks before
sending another site's JSON, and nothing here answers), an Origin that is
absent or the radar's own, and a Host that is one of the radar's own names.
These run both stores' real handlers over HTTP with the headers a browser
would send in each case, and check that the page still sends what they take.

Run: python3 tests/test_store_writes.py
"""
import http.client
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


def load(name, file):
    os.environ["STATE_DIRECTORY"] = tempfile.mkdtemp()
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


STORES = [
    ("sighting-store.py", "/sightings", {"hex": "a1b2c3", "kind": "total"},
     lambda m: sum(e.get("t", 0) for e in m.current()["ac"].values())),
    ("approach-store.py", "/approaches",
     {"hex": "a1b2c3", "points": [[-78.7875, 35.8776], [-78.79, 35.88]]},
     lambda m: m.current().get("landings", 0)),
]

JSON = "application/json"
CASES = [
    # (what, Content-Type, Host, Origin, taken?)
    ("the kiosk (http://localhost)", JSON, "localhost", "http://localhost", True),
    ("a browser at home on the radar's address", JSON, "192.168.1.23", "http://192.168.1.23", True),
    ("the same over https on 4443", JSON, "192.168.1.23:4443", "https://192.168.1.23:4443", True),
    ("the same over https on 443", JSON, "192.168.1.23", "https://192.168.1.23", True),
    ("a browser on the radar's Bonjour name", JSON, "stratoscan-rdu.local", "http://stratoscan-rdu.local", True),
    ("a charset on the type", JSON + "; charset=utf-8", "192.168.1.23", "http://192.168.1.23", True),
    ("a program on the radar (no Origin)", JSON, "127.0.0.1", None, True),
    ("plain text, as a page elsewhere sends without asking", "text/plain", "192.168.1.23", "https://attacker.example", False),
    ("plain text even from the radar's own page", "text/plain;charset=UTF-8", "localhost", "http://localhost", False),
    ("a form post", "application/x-www-form-urlencoded", "192.168.1.23", None, False),
    ("no type at all", None, "192.168.1.23", None, False),
    ("JSON from another site's page", JSON, "192.168.1.23", "https://attacker.example", False),
    ("JSON from a sandboxed or local-file page", JSON, "192.168.1.23", "null", False),
    ("JSON from the radar's address on another port", JSON, "192.168.1.23", "http://192.168.1.23:8080", False),
    ("a page elsewhere under a name of its own", JSON, "rebind.attacker.example", "http://rebind.attacker.example", False),
    ("the same with no Origin", JSON, "rebind.attacker.example", None, False),
]

for file, path, body, count in STORES:
    m = load(file.replace("-", "_")[:-3], file)
    srv = m.http.server.ThreadingHTTPServer(("127.0.0.1", 0), m.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def post(ctype, host, origin):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Host": host}
        if ctype:
            headers["Content-Type"] = ctype
        if origin is not None:
            headers["Origin"] = origin
        conn.request("POST", path, json.dumps(body).encode(), headers)
        status = conn.getresponse().status
        conn.close()
        return status

    for what, ctype, host, origin, taken in CASES:
        before = count(m)
        status = post(ctype, host, origin)
        after = count(m)
        if taken:
            check(status in (200, 204) and after == before + 1, "%s %s: taken (%d)" % (file, what, status))
        else:
            check(status in (403, 415) and after == before, "%s %s: refused (%d)" % (file, what, status))
        # The approach store counts one landing per aircraft per 5 minutes.
        getattr(m, "_recent", {}).clear()
    if path == "/sightings":
        # What install-setup-server.sh asks the running store, through lighttpd.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", path, b"{}", {"Host": "10.42.0.1", "Origin": "http://10.42.0.1", "Content-Type": JSON})
        check(conn.getresponse().status == 400,
              "%s: the installer's empty write from the radar's own page gets through, and is refused as empty" % file)
        conn.close()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path, headers={"Host": "rebind.attacker.example"})
    check(conn.getresponse().status == 200, "%s: reads are not this check's business (lighttpd's)" % file)
    conn.close()
    srv.shutdown()

page = (ROOT / "index.html").read_text()
start = page.index("function storeWrite(url, body)")
write = page[start:page.index("\n}\n", start)]
check("method: 'POST'" in write and "headers: { 'Content-Type': 'application/json' }" in write,
      "the page's storeWrite sends JSON, as the stores require")
check("sendBeacon" not in page, "and nothing on the page writes by sendBeacon, whose body is plain text")

print("store write checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
