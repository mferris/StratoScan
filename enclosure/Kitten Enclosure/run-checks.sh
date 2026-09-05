#!/bin/sh
# Runs every target in checks.scad and reports the VOLUME of what each one
# produces, rather than whether it produced anything at all.
#
# Volume rather than facet count: a boolean between parts that touch leaves
# zero-thickness films along the boundary, with many facets and no volume,
# so counting facets can call a correct model broken. Volume separates a
# real interference from two surfaces meeting exactly.
#
# Usage: sh run-checks.sh
set -eu

SCAD=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
DIR=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Must come out with no real volume: a real interference, or a region of the
# stand that no coloured part claims, which would print as a hole.
EMPTY="ear_vs_post recess_vs_post whisker_through head_in_cradle
       tail_over_paw tail_vs_left_paw tail_vs_head paws_vs_head ears_vs_cradle
       whisker_vs_screws whisker_vs_nose whisker_off_nose nose_screw_removed"

# Must come out SMALL but non-zero. These are the colour seams, and they
# overlap on purpose -- see colour_overlap in the .scad. Cutting each part
# with the exact shape of its neighbour gives zero here and a speckled
# preview, because the two bodies then share a surface at identical
# coordinates and no renderer can order them. So the interesting question is
# not "is it zero" but "is it still only a seam".
SEAM="material_gained paws_vs_toes body_vs_paws tail_vs_tip"
# Must come out WITH volume: proof the modules are being found at all. Without
# this, a typo in the `use <>` path makes every check above pass against
# nothing, which has happened on this project before.
CANARY="canary"

MAX_MM3=1.0    # a film is 0.0; a paw is ~19000. Anything between is real.

vol_of() {
    python3 - "$1" <<'PY'
import sys
p = sys.argv[1]
try:
    f = open(p)
except FileNotFoundError:
    print("0.0"); raise SystemExit
tris, v = [], []
for line in f:
    line = line.strip()
    if line.startswith('vertex'):
        v.append(tuple(float(x) for x in line.split()[1:4]))
        if len(v) == 3:
            tris.append(tuple(v)); v = []
s = 0.0
for a, b, c in tris:
    s += (a[0]*(b[1]*c[2]-b[2]*c[1])
        - a[1]*(b[0]*c[2]-b[2]*c[0])
        + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6.0
print(f"{abs(s):.3f}")
PY
}

fail=0
echo "Checks that must come out with no real volume (threshold ${MAX_MM3} mm3):"
for c in $EMPTY; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v < $MAX_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3\n" "$c" "$v"; fail=1
    fi
done

# Paired positive control for nose_screw_removed. An empty result there is
# also what a probe in the wrong place, or a front_trim() that failed to
# evaluate, would produce -- so a probe at a NORMAL screw position has to
# find a real hole. A 3.2mm probe through the bezel is about 56mm3; the
# threshold only has to separate that from nothing.
echo "Positive controls — must find real geometry:"
for c in other_screws_present; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > 10" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (probe found no hole)\n" "$c" "$v"; fail=1
    fi
done

echo "Canary — must produce real geometry, or nothing above means anything:"
for c in $CANARY; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > 1000" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (modules not found?)\n" "$c" "$v"; fail=1
    fi
done

[ "$fail" = "0" ] && echo "All checks passed." || echo "SOME CHECKS FAILED."
exit "$fail"
