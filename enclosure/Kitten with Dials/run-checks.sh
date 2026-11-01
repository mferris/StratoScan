#!/bin/sh
# Runs every target in checks.scad and reports the volume each produces.
# Usage: sh run-checks.sh
set -eu

SCAD=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
DIR=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

EMPTY="collar_vs_trim collar_vs_shell trim_vs_shell trim_vs_retainer collar_off_bezel collar_vs_nose
       grooves_open trim_screws_open cavity_closed
       added_vs_stand collar_clears_stand_by_3 trim_clears_stand_by_3 above_desk_by_10
       head_in_cradle arm_ends_at_z_arm_front
       button_fits encoder_fits lamp_fits rooms_clear_of_channel knob_clear_of_face
       wire_channel_open wire_slot_open wire_way_inside screws_pass_flange screw_heads_seat
       labels_on_face labels_clear_of_controls labels_apart controls_on_face"
FOUND="collar_on_flange collar_stand_probe_bites trim_stand_probe_bites desk_probe_bites
       arm_reaches_z_arm_front button_21mm_meets_flange channel_probe_bites slot_probe_bites
       screw_holes_open head_probe_bites labels_present
       labels_near_edge labels_near_controls labels_near_each_other"
CANARY="canary"
MAX_MM3=1.0

vol_of() {
    python3 - "$1" <<'PY'
import struct, sys
try:
    d = open(sys.argv[1], "rb").read()
except FileNotFoundError:
    print("0.0"); raise SystemExit
tris = []
if d[:5] == b"solid" and b"facet" in d[:400]:
    v = []
    for line in d.decode(errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            v.append(tuple(float(x) for x in line.split()[1:4]))
            if len(v) == 3:
                tris.append(tuple(v)); v = []
else:
    n = struct.unpack("<I", d[80:84])[0]
    for i in range(n):
        f = struct.unpack("<12f", d[84 + 50*i:84 + 50*i + 48])
        tris.append((f[3:6], f[6:9], f[9:12]))
s = 0.0
for a, b, c in tris:
    s += (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6.0
print(f"{abs(s):.3f}")
PY
}

run() { "$SCAD" --backend=manifold --export-format binstl -D "check=\"$1\"" -o "$TMP/$1.stl" "$DIR/checks.scad" >/dev/null 2>&1 || true; vol_of "$TMP/$1.stl"; }

fail=0
echo "Must come out with no real volume (under ${MAX_MM3} mm3):"
for c in $EMPTY; do
    v=$(run "$c")
    if [ "$(echo "$v < $MAX_MM3" | bc -l)" = "1" ]; then printf "  PASS  %-28s %9s mm3\n" "$c" "$v"
    else printf "  FAIL  %-28s %9s mm3\n" "$c" "$v"; fail=1; fi
done
echo "Positive controls, must find real geometry:"
for c in $FOUND; do
    v=$(run "$c")
    if [ "$(echo "$v > 1" | bc -l)" = "1" ]; then printf "  PASS  %-28s %9s mm3\n" "$c" "$v"
    else printf "  FAIL  %-28s %9s mm3  (found nothing)\n" "$c" "$v"; fail=1; fi
done
echo "Canary, or nothing above means anything:"
for c in $CANARY; do
    v=$(run "$c")
    if [ "$(echo "$v > 1000" | bc -l)" = "1" ]; then printf "  PASS  %-28s %9s mm3\n" "$c" "$v"
    else printf "  FAIL  %-28s %9s mm3  (modules not found?)\n" "$c" "$v"; fail=1; fi
done
[ "$fail" = "0" ] && echo "All checks passed." || echo "SOME CHECKS FAILED."
exit "$fail"
