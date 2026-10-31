#!/bin/sh
# Runs every target in checks.scad and reports the volume each produces.
# Usage: sh run-checks.sh
set -eu

SCAD=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
DIR=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

EMPTY="arc_vs_shell arc_vs_trim cover_vs_shell cover_vs_arc arc_vs_stand vents_clear_of_arc grille_clear_of_arc
       screw_heads_clear wire_way_clear wire_through_arc button_fits encoder_fits lamp_fits knob_clear_of_face
       arc_behind_trim_face trim_face_at_z_trim_face labels_on_face labels_clear_of_controls labels_apart"
FOUND="pads_touch_drum screw_holes_open probe_finds_post labels_present
       arc_face_near_trim trim_reaches_z_trim_face button_21mm_meets_cover
       labels_near_edge labels_near_controls labels_near_each_other"
CANARY="canary"
MAX_MM3=1.0

vol_of() {
    python3 - "$1" <<'PY'
import sys
try:
    f = open(sys.argv[1])
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
    s += (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6.0
print(f"{abs(s):.3f}")
PY
}

run() { "$SCAD" --backend=manifold -D "check=\"$1\"" -o "$TMP/$1.stl" "$DIR/checks.scad" >/dev/null 2>&1 || true; vol_of "$TMP/$1.stl"; }

fail=0
echo "Must come out with no real volume (under ${MAX_MM3} mm3):"
for c in $EMPTY; do
    v=$(run "$c")
    if [ "$(echo "$v < $MAX_MM3" | bc -l)" = "1" ]; then printf "  PASS  %-26s %9s mm3\n" "$c" "$v"
    else printf "  FAIL  %-26s %9s mm3\n" "$c" "$v"; fail=1; fi
done
echo "Positive controls, must find real geometry:"
for c in $FOUND; do
    v=$(run "$c")
    if [ "$(echo "$v > 1" | bc -l)" = "1" ]; then printf "  PASS  %-26s %9s mm3\n" "$c" "$v"
    else printf "  FAIL  %-26s %9s mm3  (found nothing)\n" "$c" "$v"; fail=1; fi
done
echo "Canary, or nothing above means anything:"
for c in $CANARY; do
    v=$(run "$c")
    if [ "$(echo "$v > 1000" | bc -l)" = "1" ]; then printf "  PASS  %-26s %9s mm3\n" "$c" "$v"
    else printf "  FAIL  %-26s %9s mm3  (modules not found?)\n" "$c" "$v"; fail=1; fi
done
[ "$fail" = "0" ] && echo "All checks passed." || echo "SOME CHECKS FAILED."
exit "$fail"
