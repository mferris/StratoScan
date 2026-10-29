// Fit checks for the control arc. Run with `sh run-checks.sh`, which
// measures the VOLUME each target produces (see the retro case's
// run-checks.sh for why volume, not facet count).
//
// Includes the design, so every dimension here is the design's own and
// cannot go stale the way restated numbers can.
include <retro-dials.scad>
dpart = "none";
check = "none";

// the case's local frame -> the stand's, as in_stand() poses it
module posed() { translate([0, 0, base_h + cradle_od/2 - 3]) rotate([90 - stand_angle, 0, 0]) translate([0, 0, -shell_depth/2]) children(); }

// the arc and its cover, as they sit on the case
module arc_and_cover() { pod(); pod_cover(); }
// a slab from height z forward, wider than the arc
module slab_from(z) translate([0, 0, z]) cylinder(r = pod_r_out + 5, h = 40, $fn = 96);
// the button's room behind the face: its 16 mm nut, `deep` back from the face
module button_room(deep) translate(concat(polar(ctl_r, button_a), [pod_z1 - pod_face_t - deep])) cylinder(d = 16, h = deep - 0.05, $fn = 48);

// ---- must be EMPTY -------------------------------------------------------
// The arc clears the shell everywhere except where its pads and neck land on
// the drum's surface (zero volume, a shared face).
if (check == "arc_vs_shell") intersection() { pod(); shell_dials(); }
// the trim where front_stack_placed() puts it (2026-10-29; this drew it on
// the panel's whole 6.45 mm depth, 4.9 mm too far forward)
if (check == "arc_vs_trim") intersection() { pod(); front_stack_placed("trim"); }
// The arc's face stays at least 0.5 mm behind the trim's face (2026-10-29).
// It stood 3.9 mm proud: the face was set from a trim drawn too far forward.
if (check == "arc_behind_trim_face") intersection() { pod(); slab_from(z_trim_face - 0.5); }
// and z_trim_face is where the trim's face really is: none of the trim, as
// front_stack_placed() puts it, stands in front of it
if (check == "trim_face_at_z_trim_face") intersection() { front_stack_placed("trim"); slab_from(z_trim_face + 0.01); }
if (check == "cover_vs_shell") intersection() { pod_cover(); shell_dials(); }
if (check == "cover_vs_arc") intersection() { pod_cover(); pod(); }
if (check == "arc_vs_stand") intersection() { posed() union() { pod(); pod_cover(); } stand(); }
// the side vent slots must still breathe: each slot, carried 4 mm outward,
// must not meet the arc
if (check == "vents_clear_of_arc") intersection() {
    pod();
    for (i = [0:n_exhaust - 1]) { a = i*360/n_exhaust;
        if (a >= exhaust_a0 && a <= exhaust_a1)
            rotate([0, 0, a]) translate([R_case - 1, -exhaust_slot_w/2, exhaust_z - exhaust_slot_h/2]) cube([6, exhaust_slot_w, exhaust_slot_h]); }
}
// nor the speaker grille on that side
if (check == "grille_clear_of_arc") intersection() {
    pod();
    rotate([0, 0, 0]) translate([R_case - 1, -grille_w/2, (shell_depth - speaker_d)/2 + speaker_d/2 - grille_h/2]) cube([8, grille_w, grille_h]);
}
// inside the case, each screw head (5.5 mm, 3 mm tall) and the wire's way in
// must not run into the front screw posts, the shelf or anything else
if (check == "screw_heads_clear") intersection() {
    shell_dials();
    for (a = pad_a) radial_cyl(a, pad_z, 5.6, R_case - wall - 3.2, R_case - wall - 0.05);
}
if (check == "wire_way_clear") intersection() {
    shell_dials();
    radial_cyl(wire_a, wire_z, wire_d - 0.4, R_case - wall - 10, R_case + 0.5);
}
// the wire hole in the arc lines up with the one in the shell
if (check == "wire_through_arc") intersection() {
    pod();
    radial_cyl(wire_a, wire_z, wire_d - 0.4, R_case - 1, pod_r_in + pod_wall + 0.5);
}
// the bought parts fit inside the arc, behind the face, and clear its cover
// (the cover was left out until 2026-10-29, so a part reaching into it
// passed):
//   12 mm button: 16 mm nut, button_deep (16 mm) deep with its tags
//   EC11 encoder: 13 x 13 body, 7 deep, then 6 mm of pins
//   lamp: the lens shank and a 5 mm LED with 12 mm of leads
if (check == "button_fits") intersection() { arc_and_cover(); button_room(button_deep); }
if (check == "encoder_fits") intersection() { arc_and_cover();
    translate(concat(polar(ctl_r, knob_a), [pod_z1 - enc_panel - 13])) rotate([0, 0, knob_a]) translate([-6.75, -6.75, 0]) cube([13.5, 13.5, 13 - (pod_face_t - enc_panel) - 0.05]); }
if (check == "lamp_fits") intersection() { arc_and_cover();
    translate(concat(polar(ctl_r, lamp_a), [pod_z1 - pod_face_t - 14])) cylinder(d = 9, h = 14 - 0.05, $fn = 32); }
// the knob clears the lettering and the face (it stands 1.5 mm off the face on the nut)
if (check == "knob_clear_of_face") intersection() { pod(); translate(concat(polar(ctl_r, knob_a), [pod_z1 + 1.5])) knob(); }

// ---- must find real geometry (positive controls) --------------------------
if (check == "pads_touch_drum") intersection() {
    for (a = pad_a) radial_cyl(a, pad_z, pad_d - 1, R_case - 0.3, R_case + 1);
    union() { pod(); shell_dials(); }
}
if (check == "screw_holes_open") difference() {
    for (a = pad_a) radial_cyl(a, pad_z, 3.0, R_case - wall - 0.5, R_case + pad_insert_h - 0.5);
    shell_dials(); pod();
}
if (check == "probe_finds_post") intersection() {   // the head probe, moved onto a post, must hit it
    shell_dials(); radial_cyl(45, 52, 5.6, R_case - wall - 3.2, R_case - wall - 0.05);
}
if (check == "labels_present") pod_text();
// The probes above sit where they should (2026-10-29): the arc's face is
// within 1.5 mm of the trim's face, so arc_behind_trim_face's slab starts
// just in front of it; the trim reaches within 0.2 mm of z_trim_face; and the
// common 21 mm button runs into the cover, so the fits see the cover.
if (check == "arc_face_near_trim") intersection() { pod(); slab_from(z_trim_face - 1.5); }
if (check == "trim_reaches_z_trim_face") intersection() { front_stack_placed("trim"); slab_from(z_trim_face - 0.2); }
if (check == "button_21mm_meets_cover") intersection() { arc_and_cover(); button_room(21); }
if (check == "canary") pod();
