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
import sys

PARTS = ["stand_body.stl", "stand_paws.stl", "stand_toes.stl",
         "stand_tail.stl", "stand_tail_tip.stl"]
PLACES = 3          # 0.001mm -- finer than any boolean's rounding error


def faces(path):
    """Canonical, order-independent key per triangle."""
    out, v = set(), []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("vertex"):
                v.append(tuple(round(float(x), PLACES) for x in line.split()[1:4]))
                if len(v) == 3:
                    out.add(tuple(sorted(v)))   # sorted: winding must not matter
                    v = []
    return out


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
    print("No coincident faces: the preview will not stipple." if not fail
          else "Coincident faces found: these seams will z-fight in the slicer.")
    return fail


if __name__ == "__main__":
    sys.exit(main(sys.argv))
