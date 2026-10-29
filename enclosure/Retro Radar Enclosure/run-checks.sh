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
EMPTY="twin_vs_stand_11 twin_slot_takes_jack_11 twin_barrel_through_panel_11 twin_cover_fits_11 twin_cover_pads_clear_jack_11 twin_vs_plate_11 twin_channel_probe_clear_11 twin_screw_probes_clear_11 top_screw_clear_of_twin_11 twin_bore_straight_11 twin_barrel_through_panel twin_cover_pads_clear_jack twin_channel_probe_clear twin_screw_probes_clear top_screw_clear_of_twin top_screw_clear_of_sma top_screw_clear_of_puck twin_vs_plate twin_vs_stand twin_bore_straight twin_slot_takes_jack twin_cover_fits twin_antennas_clear_case usbc_plug_clears_stand usbc_recess_open twin_cover_heads_seat twin_cover_heads_seat_11 twin_cover_text_vs_cover twin_cover_text_vs_cover_11 twin_cover_text_inside twin_cover_text_inside_11 retainer_clears_bore retainer_screws_pass trim_screws_pass front_inserts_surrounded key_fits plate_vs_shell plate_outside_case lip_clears_posts lip_inside_bore
       vents_clear_of_mount no_turret ribs_unbroken mount_vs_plate driver_path_clear sma_mount_vs_plate sma_barrel_fits connector_passes
       exhaust_top_only rivets_clear_of_grilles grille_in_front_of_ribs antenna_clears_case mount_vs_stand sma_mount_vs_stand socket_takes_base connector_has_room cable_slot_open power_mount_vs_plate power_board_held power_plug_reaches power_mount_vs_shell power_mount_vs_speakers power_moulding_reaches speaker_sleeve_hollow rib_lip_kept plinth_lip_kept
       power_m3_clear_of_speakers power_speakers_on_pads power_stop_fits_tube power_stop_clear_of_board power_m2_holes_line_up power_m2_clear_of_board power_m2_threads_held power_wires_out power_stop_vs_shell power_stop_vs_speakers power_parts_vs_stand
       usbc_inserts_clear_pocket usbc_inserts_surrounded power_edge_on_plate power_socket_clears_window power_m3_pass power_m3_inside_plate power_parts_in_patch
       usbc_bridge_steps_open
       usbc_label_cut usbc_label_inside_plate usbc_label_off_gauge usbc_label_clear_of_holes power_m2_drivers_clear
       rail_lip_kept rear_rail_square speaker_slot_closed retainer_key_fits front_stack_seats
       shell_seats_in_stand grille_clear_of_posts"

# Must come out small but not empty (2026-10-29): the trigger board's stop
# presses its two crush ribs into the board's back edge, 0.4 mm as drawn (0.3
# as printed), so the stop and the board overlap by a sliver, about 0.35 mm3;
# and the two ribs in the mount's roof press 0.25 mm into the socket's top,
# about 0.45 mm3. Empty is a gap, which a plug going in would close; more than
# SQUEEZE_MAX_MM3 is the stop's body, or the roof, on the board rather than
# their ribs.
SQUEEZE="power_ribs_squeeze_board power_top_ribs_squeeze_socket"
SQUEEZE_MIN_MM3=0.05
SQUEEZE_MAX_MM3=1.0

# Must find more than a film (2026-10-29): the trigger board tipped 1 degree
# in its mount runs into the roof's ribs, about 0.16 mm3, so it cannot rock.
# Without the ribs the same tip finds a film, 0.003.
MEETS="power_board_cannot_rock"
MEETS_MIN_MM3=0.05

# Must run into the mount (2026-10-29): the trigger board's stop the wrong
# way round, as far in as a screw could start in it. Back to front its key
# runs 0.7 mm into the mount's wall, about 0.7 mm3; upside down, or end over
# end, its T does, about 2 mm3. A film is 0.0; right way round, or back to
# front without its key, the same poses find nothing.
BLOCKED="power_stop_back_to_front_blocked power_stop_upside_down_blocked power_stop_end_over_end_blocked"
BLOCK_MIN_MM3=0.3

# Must come out with nothing at all, not just under MAX_MM3 (2026-10-29): the
# trigger board's stop the right way round, slid in all the way home, and
# back to front without its key. Where the key runs into the mount's wall it
# is only about 0.36 mm2 across, so under MAX_MM3 a slot begun 2.5 mm late,
# which jams the stop 2.35 mm short of home, passed. JAMMED is their
# control: the slot begun 0.5 mm late jams it 0.35 mm short, about 0.13 mm3,
# and must come out over CLEAR_MAX_MM3, so this limit sees it.
CLEAR="power_stop_slides_home power_stop_key_is_what_blocks"
JAMMED="power_stop_jam_probe_works"
CLEAR_MAX_MM3=0.01

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

echo "Squeezes — must be present but only a sliver (${SQUEEZE_MIN_MM3} to ${SQUEEZE_MAX_MM3} mm3):"
for c in $SQUEEZE; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > $SQUEEZE_MIN_MM3 && $v < $SQUEEZE_MAX_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3\n" "$c" "$v"; fail=1
    fi
done

echo "Contacts — must find more than a film (over ${MEETS_MIN_MM3} mm3):"
for c in $MEETS; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > $MEETS_MIN_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (nothing there)\n" "$c" "$v"; fail=1
    fi
done

echo "Blocked — the wrong way round must run into the mount (over ${BLOCK_MIN_MM3} mm3):"
for c in $BLOCKED; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > $BLOCK_MIN_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (it goes in)\n" "$c" "$v"; fail=1
    fi
done

echo "Clear — must meet nothing at all, not just under ${MAX_MM3} mm3 (under ${CLEAR_MAX_MM3} mm3):"
for c in $CLEAR; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v < $CLEAR_MAX_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (it jams)\n" "$c" "$v"; fail=1
    fi
done
for c in $JAMMED; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > $CLEAR_MAX_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3  (the control: a jam it sees)\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (the control: a jam it cannot see)\n" "$c" "$v"; fail=1
    fi
done

# Paired positive control for nose_screw_removed. An empty result there is
# also what a probe in the wrong place, or a front_trim() that failed to
# evaluate, would produce -- so a probe at a NORMAL screw position has to
# find a real hole. A 3.2mm probe through the bezel is about 56mm3; the
# threshold only has to separate that from nothing.
echo "Positive controls — must find real geometry:"
for c in key_blocks_45 key_blocks_90 key_blocks_135 key_blocks_180 key_blocks_225 key_blocks_270 key_blocks_315 back_inserts_open lip_present usbc_open ant_plate_holes_open ant_flange_inserts_open driver_path_was_blocked vents_were_under_mount socket_gauge_works cable_slot_other_side connector_gauge_works turret_probe_works ribs_present exhaust_reaches_inside rivets_present grille_present plinth_ribs_front plinth_ribs_back plinth_ribs_left plinth_ribs_right sma_passage_joins sma_panel_present sma_hole_open front_insert_holes_open twin_panels_present twin_holes_open top_screw_was_under_mount twin_channel_open twin_cover_seats twin_cover_screws_open twin_antennas_probe_works twin_channel_open_11 twin_cover_seats_11 twin_cover_screws_open_11 twin_panels_present_11 twin_cover_text_present usbc_recess_web usbc_plug_probe_works power_plug_probe_works power_moulding_probe_works speaker_probe_works rib_slopes_present plinth_slopes_present power_speaker_drawing_works power_stop_takes_push power_m2_threads_bite power_wire_probe_works usbc_insert_probe_works usbc_insert_holes_open power_mount_on_plate power_plate_holds_board power_edge_strip_works power_window_is_close power_m3_bite usbc_bridge_steps_held power_board_on_floor usbc_label_present usbc_label_probe_works power_m2_drivers_reach rail_slope_present rear_rail_probe_works shelf_slope_present speaker_slot_probe_works retainer_key_blocks_45 retainer_key_blocks_90 retainer_key_blocks_135 retainer_key_blocks_180 retainer_key_blocks_225 retainer_key_blocks_270 retainer_key_blocks_315 front_stack_retainer_down front_stack_trim_down shell_seats_probe_works grille_post_probe_works; do
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
