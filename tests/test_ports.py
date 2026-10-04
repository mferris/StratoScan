#!/usr/bin/env python3
"""
No two of the radar's own services may listen on the same loopback port.

Found the hard way (2026-10-04): the visitor counts' stats listener was put on
8087, which network-compare.py already held. It passed every test on a Mac,
where nothing else was listening, and failed to start on the radar.

Run: python3 tests/test_ports.py
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(HERE, "..", "deploy")
failures = []
owners = {}

# Every ("127.0.0.1", N) listen address a service declares.
for path in sorted(glob.glob(os.path.join(DEPLOY, "*.py"))):
    src = open(path).read()
    for m in re.finditer(r'^\s*([A-Z_]*LISTEN[A-Z_]*)\s*=\s*\(\s*"127\.0\.0\.1"\s*,\s*(?:int\([^)]*"(\d+)"\)\)|(\d+))\s*\)',
                         src, re.M):
        port = int(m.group(2) or m.group(3))
        owners.setdefault(port, []).append(f"{os.path.basename(path)}:{m.group(1)}")

for port, who in sorted(owners.items()):
    if len(who) > 1:
        failures.append(f"port {port} is claimed by {', '.join(who)}")

# And whoever reads a service's port must name the one it listens on.
expect = {"8091": "funnel-gateway.py:STATS_LISTEN"}
for path in ("setup-server.py", "heartbeat.py"):
    src = open(os.path.join(DEPLOY, path)).read()
    for port in re.findall(r'127\.0\.0\.1:(\d+)/visits', src):
        if f"{os.path.basename(path)}" and port not in expect:
            failures.append(f"{path} reads visit counts from {port}, but the gateway serves them on 8091")

checks = len(owners) + 1
print(f"{checks - len(failures)}/{checks} port checks passed ({len(owners)} listeners: "
      + ", ".join(f"{p} {w[0].split(':')[0]}" for p, w in sorted(owners.items())) + ")")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
