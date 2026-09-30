#!/usr/bin/env python3
"""
Checks for deploy/offline-map.py -- offline, no network.

The PMTiles reader is hand-written, so its arithmetic is pinned against the
spec's published values: a wrong Hilbert ID does not fail loudly, it quietly
fetches the wrong square of the planet. The rest pins the rules that protect
the owner: the stored centre is rounded, and a correct map is never rebuilt.

Run: python3 tests/test_offline_map.py
"""
import gzip
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "deploy", "offline-map.py")

failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_WEB_ROOT"] = tmp
os.environ["STRATOSCAN_OFFLINE_STATE"] = os.path.join(tmp, "state")
spec = importlib.util.spec_from_file_location("offline_map", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# ---- Hilbert tile IDs: values from the PMTiles v3 spec's test suite ----------
check("z0 is tile 0", m.zxy_to_tileid(0, 0, 0) == 0)
check("z1 0,0", m.zxy_to_tileid(1, 0, 0) == 1)
check("z1 0,1", m.zxy_to_tileid(1, 0, 1) == 2)
check("z1 1,1", m.zxy_to_tileid(1, 1, 1) == 3)
check("z1 1,0", m.zxy_to_tileid(1, 1, 0) == 4)
check("z2 starts after every z0/z1 tile", m.zxy_to_tileid(2, 0, 0) == 5)
check("a deep tile", m.zxy_to_tileid(12, 3423, 1763) == 19078479)
ids = {m.zxy_to_tileid(3, x, y) for x in range(8) for y in range(8)}
check("every z3 tile gets its own id", len(ids) == 64)
check("z3 ids are exactly the z3 block", ids == set(range(21, 21 + 64)))

# ---- directory decoding ------------------------------------------------------
def varint(n):
    return m._encode_varint(n)

entries = [(5, 1, 0, 100), (6, 3, 100, 50), (20, 0, 7, 30)]   # last is a leaf pointer
buf = varint(3)
last = 0
for tid, _, _, _ in entries:
    buf += varint(tid - last)
    last = tid
for _, run, _, _ in entries:
    buf += varint(run)
for _, _, _, ln in entries:
    buf += varint(ln)
buf += varint(0 + 1) + varint(0) + varint(7 + 1)   # 0 = "right after the previous"
parsed = m.parse_directory(buf)
check("directory ids are delta-decoded", [e[0] for e in parsed] == [5, 6, 20])
check("a zero offset means contiguous", parsed[1][2] == 100)
check("an explicit offset is one-based", parsed[2][2] == 7)
check("run length 0 marks a leaf pointer", parsed[2][1] == 0)

# ---- layer stripping ---------------------------------------------------------
def layer(name, payload=b"x" * 10):
    body = b"\x0a" + varint(len(name)) + name + b"\x12" + varint(len(payload)) + payload
    return b"\x1a" + varint(len(body)) + body

tile = layer(b"roads") + layer(b"buildings", b"y" * 500) + layer(b"water") + layer(b"landuse")
kept = [next(v for k, v in m._fields(l) if k == 1) for f, l in m._fields(m.filter_tile(tile)) if f == 3]
check("kept layers survive in order", kept == [b"roads", b"water"])
check("buildings are dropped", b"y" * 500 not in m.filter_tile(tile))
check("an empty tile stays empty", m.filter_tile(b"") == b"")

# ---- area --------------------------------------------------------------------
xs, ys = m.tile_range(35.88, -78.79, 20, 10)
check("a 20 nm disc at z10 is a handful of tiles", 2 <= len(xs) <= 5 and 2 <= len(ys) <= 5)
xs, ys = m.tile_range(89.9, 0, 60, 3)
check("near the pole the range stays on the map", max(ys) < 8 and min(ys) >= 0)
xs, _ = m.tile_range(0, 179.9, 60, 4)
check("the antimeridian clamps rather than wrapping out of range", max(xs) <= 15)
check("the tile count is bounded for any location",
      max(len(m.wanted_tiles(lat, 0)) for lat in (0, 35, 52, 70)) < m.MAX_TILES)

# ---- privacy: nothing more precise than the gateway publishes ---------------
check("the centre is rounded to ~1 km", m.round_home(35.877612, -78.787498) == (35.88, -78.79))

# ---- when to rebuild ---------------------------------------------------------
recv = os.path.join(tmp, "receiver.json")
m.RECEIVER_JSON = recv
check("no location yet: nothing to build", m.needs_build() is None)

with open(recv, "w") as f:
    json.dump({"lat": 35.877612, "lon": -78.787498}, f)
check("no map yet: build for the rounded location", m.needs_build() == (35.88, -78.79))

os.makedirs(m.OUT_DIR, exist_ok=True)
with open(os.path.join(m.OUT_DIR, "meta.json"), "w") as f:
    json.dump({"lat": 35.88, "lon": -78.79, "built": int(time.time())}, f)
check("a current map for this location is left alone", m.needs_build() is None)

with open(recv, "w") as f:
    json.dump({"lat": 52.3676, "lon": 4.9041}, f)
check("a moved unit rebuilds for its new location", m.needs_build() == (52.37, 4.9))

with open(recv, "w") as f:
    json.dump({"lat": 35.8776, "lon": -78.7875}, f)
check("a move smaller than the rounding does not rebuild", m.needs_build() is None)

with open(os.path.join(m.OUT_DIR, "meta.json"), "w") as f:
    json.dump({"lat": 35.88, "lon": -78.79, "built": int(time.time()) - m.REBUILD_AFTER_S - 1}, f)
check("a year-old map is refreshed", m.needs_build() == (35.88, -78.79))

os.makedirs(m.STATE_DIR, exist_ok=True)
open(m.FAILED_STAMP, "w").close()
check("a recent failure backs off", m.needs_build() is None)
old = time.time() - m.RETRY_AFTER_FAILURE_S - 1
os.utime(m.FAILED_STAMP, (old, old))
check("an old failure is retried", m.needs_build() == (35.88, -78.79))

check("gzip tiles decompress", m.decompress(gzip.compress(b"abc"), 2) == b"abc")
check("uncompressed tiles pass through", m.decompress(b"abc", 1) == b"abc")

print(f"{checks - len(failures)}/{checks} offline map checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
