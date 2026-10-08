#!/usr/bin/env python3
"""Every HTTP service on the unit gives a silent client's socket a timeout
(security review 2026-10-04, item 7): a connection that sends nothing, or
stops reading, no longer holds one of the server's threads for good.

Static: each request-handler class in a deploy/*.py that serves HTTP must
set `timeout` (BaseHTTPRequestHandler applies it to the request socket)."""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEPLOY = os.path.join(ROOT, "deploy")
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


served = 0
for name in sorted(os.listdir(DEPLOY)):
    if not name.endswith(".py"):
        continue
    src = open(os.path.join(DEPLOY, name), encoding="utf-8").read()
    if "ThreadingHTTPServer" not in src and "HTTPServer(" not in src:
        continue
    served += 1
    handlers = re.findall(r"^class (\w+)\(http\.server\.BaseHTTPRequestHandler\):\n([\s\S]*?)(?=^\S)", src, re.M)
    check(handlers, "%s: a request handler class is found" % name)
    for cls, body in handlers:
        m = re.search(r"^    timeout = (\d+)", body, re.M)
        check(bool(m) and 5 <= int(m.group(1)) <= 300, "%s: %s has a socket timeout" % (name, cls))
check(served >= 8, "the HTTP services were found (%d)" % served)
print("socket timeout checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
