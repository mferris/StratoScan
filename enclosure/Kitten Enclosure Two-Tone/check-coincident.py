#!/usr/bin/env python3
"""
Counts triangles that two colour bodies have in common, at identical
coordinates.

This is the check the volume test could not make. Two parts cut with the
exact shape of each other form a perfect partition -- zero shared volume,
which is what the volume test measures and reports as a pass -- while
sharing a whole surface. A renderer cannot order two faces at the same
depth, so the slicer preview stipples the seam with the wrong colour and a
white paw arrives speckled black. Nothing about that is visible in a volume
measurement; it needs the meshes compared face by face.

A pass is zero shared faces, which is what a deliberate interference at each
seam (colour_overlap in the .scad) produces.

Usage:  python3 check-coincident.py stand_paws.stl stand_toes.stl ...
        with no arguments, checks every pair of the five stand bodies.
"""
import itertools
import os
import struct
import sys

PARTS = ["stand_body.stl", "stand_paws.stl", "stand_toes.stl",
         "stand_claws.stl", "stand_tail.stl", "stand_tail_tip.stl"]

# How many separate lumps each body must export as. This is not pedantry: the
# claws were placed by offsetting along each toe's OWN axis, which also moves
# inward on a splayed toe, so their bases converged from 5.9mm apart to 3.56
# -- closer than a 3.6mm base is wide. Adjacent claws merged in pairs and
# eight claws exported as four. Every volume, seam and coincidence check
# passed while half the claws did not exist, because none of them can see
# topology. Two paws, two clumps of toes (one per paw), eight claws.
EXPECTED_LUMPS = {
    "stand_body.stl": 1, "stand_paws.stl": 2, "stand_toes.stl": 2,
    "stand_claws.stl": 8, "stand_tail.stl": 1, "stand_tail_tip.stl": 1,
}


# Every body that stands on the desk must start on the bed (2026-10-29): a
# lump whose lowest point is above it begins as an island in mid-air. The
# claws began 1.2mm up and the toes 0.47mm, and no volume, seam or lump count
# could see it. The white tail tip is left out: it continues the black tail,
# which carries it.
ON_BED = ["stand_body.stl", "stand_paws.stl", "stand_toes.stl",
          "stand_claws.stl", "stand_tail.stl"]


def lump_count(path):
    """Connected components, by shared vertices."""
    return len(lump_bottoms(path))


def lump_bottoms(path):
    """The lowest z of each connected component, by shared vertices."""
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for tri in _triangles(path):
        vs = [tuple(round(c, 3) for c in v) for v in tri]
        for v in vs:
            parent.setdefault(v, v)
        union(vs[0], vs[1])
        union(vs[1], vs[2])
    low = {}
    for v in parent:
        r = find(v)
        low[r] = min(low.get(r, v[2]), v[2])
    return list(low.values())
PLACES = 3          # 0.001mm -- finer than any boolean's rounding error


def _triangles(path):
    """Yield triangles from an STL, ascii or binary.

    Detected by content, not by extension: the meshes here are exported as
    binary (six times smaller for identical geometry) while OpenSCAD writes
    ascii for the check targets, and a reader that assumed one would silently
    return nothing for the other -- which reads exactly like a pass.
    """
    with open(path, "rb") as f:
        head = f.read(5)
        f.seek(0)
        if head == b"solid":
            v = []
            for raw in f:
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("vertex"):
                    v.append(tuple(float(x) for x in line.split()[1:4]))
                    if len(v) == 3:
                        yield tuple(v); v = []
            return
        f.seek(80)
        (count,) = struct.unpack("<I", f.read(4))
        for _ in range(count):
            d = f.read(50)
            if len(d) < 50:
                return
            n = struct.unpack("<12f", d[:48])
            yield (n[3:6], n[6:9], n[9:12])


def faces(path):
    """Canonical, order-independent key per triangle."""
    return {tuple(sorted(tuple(round(c, PLACES) for c in vert) for vert in tri))
            for tri in _triangles(path)}


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    names = argv[1:] or PARTS
    paths = {n: (n if os.path.isabs(n) else os.path.join(here, n)) for n in names}

    missing = [n for n, p in paths.items() if not os.path.exists(p)]
    if missing:
        print("missing: " + ", ".join(missing))
        return 1

    loaded = {n: faces(p) for n, p in paths.items()}
    for n, f in loaded.items():
        print(f"  {n:22} {len(f):7,} faces")
    print()

    fail = 0
    for a, b in itertools.combinations(names, 2):
        shared = loaded[a] & loaded[b]
        label = f"{a.replace('stand_','').replace('.stl','')} vs " \
                f"{b.replace('stand_','').replace('.stl','')}"
        if shared:
            print(f"  FAIL  {label:28} {len(shared):6,} coincident faces")
            fail = 1
        else:
            print(f"  PASS  {label:28} {0:6} coincident faces")

    print()
    print("Separate lumps per body — a merged or missing lump is invisible to"
          " every volume check:")
    for n in names:
        want = EXPECTED_LUMPS.get(n)
        if want is None:
            continue
        got = lump_count(paths[n])
        label = n.replace(".stl", "")
        if got == want:
            print(f"  PASS  {label:22} {got} lump(s)")
        else:
            print(f"  FAIL  {label:22} {got} lump(s), expected {want}")
            fail = 1

    print()
    print("Lumps that start on the bed — one above it starts in mid-air:")
    for n in names:
        if n not in ON_BED:
            continue
        lows = lump_bottoms(paths[n])
        up = [z for z in lows if z > 0.01]
        label = n.replace(".stl", "")
        if up:
            print(f"  FAIL  {label:22} {len(up)} of {len(lows)} lump(s) start "
                  f"{min(up):.2f}-{max(up):.2f} mm above the bed")
            fail = 1
        else:
            print(f"  PASS  {label:22} all {len(lows)} on the bed")

    print()
    print("No coincident faces: the preview will not stipple." if not fail
          else "Problems found: see FAIL lines above.")
    return fail


if __name__ == "__main__":
    sys.exit(main(sys.argv))
