#!/bin/sh
# Runs every target in checks.scad and reports the VOLUME of what each one
# produces, rather than whether it produced anything at all.
#
# "The intersection must be empty" is the obvious test and it is wrong here.
# Wherever two parts share a surface -- which is the entire point of the
# colour split, since the toes sit in the pads and the tip continues the
# tail -- a boolean leaves a zero-thickness film along that boundary. Those
# films have thousands of facets and no volume. Judging by facet count calls
# a correct model broken; judging by volume separates a real interference
# from an artifact of two surfaces meeting exactly.
#
# Usage: sh run-checks.sh
set -eu

SCAD=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
DIR=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Must come out with no real volume: a real interference, or a region of the
# stand that no coloured part claims, which would print as a hole.
EMPTY="twin_vs_stand_11 twin_slot_takes_jack_11 twin_barrel_through_panel_11 twin_cover_fits_11 twin_cover_pads_clear_jack_11 twin_vs_plate_11 twin_channel_probe_clear_11 twin_screw_probes_clear_11 top_screw_clear_of_twin_11 twin_bore_straight_11 twin_barrel_through_panel twin_cover_pads_clear_jack twin_channel_probe_clear twin_screw_probes_clear top_screw_clear_of_twin top_screw_clear_of_sma top_screw_clear_of_puck twin_vs_plate twin_vs_stand twin_bore_straight twin_slot_takes_jack twin_cover_fits twin_antennas_clear_case retainer_clears_bore retainer_screws_pass trim_screws_pass front_inserts_surrounded key_fits plate_vs_shell plate_outside_case lip_clears_posts lip_inside_bore
       vents_clear_of_mount usbc_screws_clear_window no_turret ribs_unbroken mount_vs_plate driver_path_clear sma_mount_vs_plate sma_barrel_fits connector_passes
       exhaust_top_only rivets_clear_of_grilles grille_in_front_of_ribs antenna_clears_case mount_vs_stand sma_mount_vs_stand socket_takes_base connector_has_room cable_slot_open"

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

MAX_MM3=1.0    # a film is 0.0; the plate is ~100000. Anything between is real.

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
for c in key_blocks_45 key_blocks_90 key_blocks_135 key_blocks_180 key_blocks_225 key_blocks_270 key_blocks_315 back_inserts_open lip_present usbc_open ant_plate_holes_open ant_flange_inserts_open driver_path_was_blocked vents_were_under_mount socket_gauge_works cable_slot_other_side connector_gauge_works usbc_screw_probe_works turret_probe_works ribs_present exhaust_reaches_inside rivets_present grille_present plinth_ribs_front plinth_ribs_back plinth_ribs_left plinth_ribs_right sma_passage_joins sma_panel_present sma_hole_open front_insert_holes_open twin_panels_present twin_holes_open top_screw_was_under_mount twin_channel_open twin_cover_seats twin_cover_screws_open twin_antennas_probe_works twin_channel_open_11 twin_cover_seats_11 twin_cover_screws_open_11 twin_panels_present_11; do
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
