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
EMPTY="twin_vs_stand_11 twin_slot_takes_jack_11 twin_barrel_through_panel_11 twin_cover_fits_11 twin_cover_pads_clear_jack_11 twin_vs_plate_11 twin_channel_probe_clear_11 twin_screw_probes_clear_11 top_screw_clear_of_twin_11 twin_bore_straight_11 twin_barrel_through_panel twin_cover_pads_clear_jack twin_channel_probe_clear twin_screw_probes_clear top_screw_clear_of_twin top_screw_clear_of_sma top_screw_clear_of_puck twin_vs_plate twin_vs_stand twin_bore_straight twin_slot_takes_jack twin_cover_fits twin_antennas_clear_case front_inserts_surrounded key_fits mount_vs_plate driver_path_clear sma_mount_vs_plate sma_barrel_fits ear_vs_post recess_vs_post whisker_through head_in_cradle
       tail_over_paw tail_vs_left_paw tail_vs_head paws_vs_head ears_vs_cradle
       whisker_vs_screws whisker_vs_nose whisker_off_nose nose_screw_removed
       antenna_clears_head mount_hidden plate_vs_shell mount_vs_stand sma_mount_vs_stand
       material_lost paws_vs_tail lip_clears_posts lip_inside_bore
       vents_clear_of_mount connector_passes
       socket_takes_base connector_has_room cable_slot_open power_mount_vs_plate power_board_held power_plug_reaches power_mount_vs_shell power_mount_vs_speakers power_moulding_reaches speaker_sleeve_hollow
       power_m3_clear_of_speakers power_speakers_on_pads power_stop_fits_tube power_stop_clear_of_board power_m2_holes_line_up power_m2_clear_of_board power_m2_threads_held power_wires_out power_stop_vs_shell power_stop_vs_speakers power_parts_vs_stand
       usbc_inserts_clear_pocket usbc_inserts_surrounded power_edge_on_plate power_socket_clears_window power_m3_pass power_m3_inside_plate power_parts_in_patch usbc_recess_open usbc_plug_clears_stand
       usbc_bridge_steps_open
       usbc_label_cut usbc_label_inside_plate usbc_label_off_gauge usbc_label_clear_of_holes power_m2_drivers_clear
       rail_lip_kept rear_rail_square speaker_slot_closed retainer_key_fits front_stack_seats
       front_posts_on_wall tail_on_the_desk stand_clip_takes_cable"

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
SEAM="material_gained paws_vs_toes body_vs_paws tail_vs_tip claws_vs_toes"
# Must come out WITH volume: proof the modules are being found at all. Without
# this, a typo in the `use <>` path makes every check above pass against
# nothing, which has happened on this project before.
CANARY="canary"

MAX_MM3=1.0    # a film is 0.0; a paw is ~27000. Anything between is real.
# A seam is the shared area times colour_overlap/2, i.e. 0.15mm of thickness.
# Even 10,000mm2 of shared surface -- far more than these parts have -- comes
# to 1500mm3. Past that it is not a seam, it is two parts genuinely occupying
# the same space, and which colour wins stops being invisible.
MAX_SEAM_MM3=1500

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

echo "Colour seams — must be present but thin (under ${MAX_SEAM_MM3} mm3):"
for c in $SEAM; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > 0 && $v < $MAX_SEAM_MM3" | bc -l)" = "1" ]; then
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

# The regulator's place (2026-10-29, #99): its tray screwed to two bosses
# across the bottom of the plate, ten tie bridges on the plate for the leads
# and the coax, two curbs that keep the slack of the runs tied at one end only
# on their own sides, and the routes they all run along. TRAY_EMPTY must come
# out with no real volume, like EMPTY above: the tray, the regulator in it and
# its screws clear of the plate, the shell, the speakers, the trigger board's
# parts and strip, the vents, the coax hole's 50 mm and the Pi's box, its
# inserts surrounded by plastic and its holes blind, the tie slots and
# tunnels open under their tented roofs and their decks whole, the leads'
# ferrules clear of the ties, the leads straight onto the saddles and the
# saddles' ties, heads on top, clear of the plate and the shell, OUT and IN
# on the tongues' tops; the curbs on solid plate and clear of everything
# else; every power lead, the pigtail's slack and the tray 20 mm or more from
# the coax, its slack and the SMA plugs, the coax 20 mm from the Pi's USB-C
# plug, each lead and the coax clear of everything else on the plate, and
# nothing within 2 mm of the HAT's switches. TRAY_FOUND are their controls
# and must find real geometry, like the positive controls below: each probe,
# moved to where it should catch something, does.
TRAY_EMPTY="tray_vs_plate tray_holds_board tray_screws_pass tray_screws_inside_plate tray_inserts_surrounded tray_holes_blind
       tray_vs_shell tray_vs_speakers tray_vs_trigger tray_off_strip tray_clear_of_grilles tray_clear_of_coax tray_vs_hat
       tray_tie_slots_open tray_ferrules_clear tray_leads_straight tray_ties_clear tray_labels_on_tongues
       tie_tunnels_open tie_decks_whole tie_tents_open tie_bridges_on_plate tie_bridges_clear curbs_on_plate curbs_clear coupon_unchanged
       routes_power_20mm_from_coax routes_port_20mm_from_coax routes_leads_clear routes_coax_clear hat_stack_clear"
TRAY_FOUND="tray_caps_on_bosses tray_located tray_one_way_round tray_board_on_ribs tray_screws_bite tray_insert_holes_open
       tray_speaker_probe_works tray_strip_probe_works tray_grille_probe_works tray_coax_probe_works tray_hat_probe_works
       tray_tie_probe_works tray_ferrule_probe_works tray_leads_on_saddles tray_tie_head_probe_works tray_labels_cut
       tie_tunnel_probe_works tie_spans_short tie_roofs_tented tie_zone_probe_works tie_bridges_present tray_bosses_present
       curbs_present curbs_probe_works
       routes_20mm_probe_works routes_pigtail_slack_probe_works routes_coax_slack_probe_works routes_port_probe_works
       routes_leads_probe_works routes_coax_probe_works hat_stack_probe_works"
echo "The regulator's place — must come out with no real volume (threshold ${MAX_MM3} mm3):"
for c in $TRAY_EMPTY; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v < $MAX_MM3" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3\n" "$c" "$v"; fail=1
    fi
done
echo "The regulator's place — controls, must find real geometry:"
for c in $TRAY_FOUND; do
    out="$TMP/$c.stl"
    "$SCAD" --backend=manifold -D "check=\"$c\"" -o "$out" "$DIR/checks.scad" >/dev/null 2>&1 || true
    v=$(vol_of "$out")
    if [ "$(echo "$v > 10" | bc -l)" = "1" ]; then
        printf "  PASS  %-18s %8s mm3\n" "$c" "$v"
    else
        printf "  FAIL  %-18s %8s mm3  (probe found nothing)\n" "$c" "$v"; fail=1
    fi
done

# Paired positive control for nose_screw_removed. An empty result there is
# also what a probe in the wrong place, or a front_trim() that failed to
# evaluate, would produce -- so a probe at a NORMAL screw position has to
# find a real hole. A 3.2mm probe through the bezel is about 56mm3; the
# threshold only has to separate that from nothing.
echo "Positive controls — must find real geometry:"
for c in key_blocks_45 key_blocks_90 key_blocks_135 key_blocks_180 key_blocks_225 key_blocks_270 key_blocks_315 other_screws_present back_inserts_open lip_present usbc_open ant_plate_holes_open ant_flange_inserts_open driver_path_was_blocked vents_were_under_mount socket_gauge_works cable_slot_other_side connector_gauge_works sma_passage_joins sma_panel_present sma_hole_open claws_stand_proud top_wall_solid front_insert_holes_open twin_panels_present twin_holes_open top_screw_was_under_mount twin_channel_open twin_cover_seats twin_cover_screws_open twin_antennas_probe_works twin_channel_open_11 twin_cover_seats_11 twin_cover_screws_open_11 twin_panels_present_11 power_plug_probe_works power_moulding_probe_works speaker_probe_works power_speaker_drawing_works power_stop_takes_push power_m2_threads_bite power_wire_probe_works usbc_insert_probe_works usbc_insert_holes_open power_mount_on_plate power_plate_holds_board power_edge_strip_works power_window_is_close power_m3_bite usbc_recess_web usbc_plug_probe_works usbc_bridge_steps_held power_board_on_floor usbc_label_present usbc_label_probe_works power_m2_drivers_reach rail_slope_present rear_rail_probe_works shelf_slope_present speaker_slot_probe_works retainer_key_blocks_45 retainer_key_blocks_90 retainer_key_blocks_135 retainer_key_blocks_180 retainer_key_blocks_225 retainer_key_blocks_270 retainer_key_blocks_315 front_stack_retainer_down front_stack_trim_down post_wall_probe_works tail_probe_works stand_clip_grips stand_clip_snaps; do
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

# The check the volume tests cannot make: two parts sharing a surface have
# zero shared volume and still stipple the preview. Compared face by face, on
# the exported meshes, with each body's lumps counted and, since 2026-10-29,
# each lump's lowest point, which must be on the bed.
echo "Colour bodies — no coincident faces, the right lumps, every lump on the bed:"
if python3 "$DIR/check-coincident.py" >"$TMP/coin.txt" 2>&1; then
    grep -c PASS "$TMP/coin.txt" | sed 's/^/  all /;s/$/ clean/'
else
    grep FAIL "$TMP/coin.txt" | sed 's/^/  /'
    fail=1
fi

[ "$fail" = "0" ] && echo "All checks passed." || echo "SOME CHECKS FAILED."
exit "$fail"
