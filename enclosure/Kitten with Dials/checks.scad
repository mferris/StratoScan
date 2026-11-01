// Fit checks for the kitten's collar. Run with `sh run-checks.sh`, which
// measures the VOLUME each target produces (see the kitten case's
// run-checks.sh for why volume, not facet count).
//
// Includes the design, so every dimension here is the design's own and
// cannot go stale the way restated numbers can.
include <kitten-dials.scad>
dpart = "none";
check = "none";

// the trim with its flange, and the collar, as they sit on the head
module front() { front_trim_dials_placed(); collar(); }
// the controls as fitted: knob, bezel and jewel
module fitted() translate([0, 0, col_z1]) controls_fitted(col_status(), col_screen(), col_range());
// everything the collar adds in front of the head
module added() { front(); fitted(); }
// a slab of the head's frame from height z forward, wide enough for the collar
module slab_from(z) translate([0, 0, z]) cylinder(r = 200, h = 80);
// the stand's cradle and keel near the collar: under the chin, inside r 150
// (inside r 135: further out, in front of the head, is the plinth)
module under_chin() intersection() { stand(); posed_k() translate([0, 0, -10])
    rotate([0, 0, 200]) rotate_extrude(angle = 140) square([135, 100]); }

// the bought parts behind the face (dial-controls.scad), the face's front at col_z1
module rooms() translate([0, 0, col_z1]) {
    button_room_at(col_screen());
    encoder_room_at(col_range(), col_range[0]);
    lamp_room_at(col_status());
}

// the wires' way: a 6 x 2 mm probe down the flange's channel, then down the
// shell's slot to below the retainer, then into the case
module wire_probe_channel() rotate([0, 0, col_wire_a]) hull() {
    translate([col_wire_in + 0.5, 0, z_trim_face + 0.5]) cube([2, 6, 0.01], center = true);
    translate([col_wire_out - 0.5, 0, z_trim_back - 0.5]) cube([2, 6, 0.01], center = true);
}
module wire_probe_slot() rotate([0, 0, col_wire_a]) translate([R_head - wall + 0.05, -3, col_slot_z0 + 0.5])
    cube([wall + 0.5, 6, z_trim_back - col_slot_z0 - 0.6]);
module wire_probe_inside() rotate([0, 0, col_wire_a]) translate([R_head - wall - 8, -3, col_slot_z0 + 0.5])
    cube([8.5, 6, 57 - col_slot_z0 - 1]);
// the two screws: 3 mm shanks from the flange's back into the inserts
module screw_probe(dz = 0) for (a = col_boss_a) translate(concat(polar(col_boss_r, a), [z_trim_back + 1.5 + dz]))
    cylinder(d = 3, h = z_trim_face - z_trim_back + col_insert_h - 2.5, $fn = 24);

// ---- must be EMPTY -------------------------------------------------------
// The collar and the trim touch only face to face: the collar's back on the
// flange's front, the trim's back on the shell's front edge.
if (check == "collar_vs_trim")  intersection() { collar(); front_trim_dials_placed(); }
if (check == "collar_vs_shell") intersection() { collar(); shell_dials(); }
if (check == "trim_vs_shell")   intersection() { front_trim_dials_placed(); shell_dials(); }
if (check == "trim_vs_retainer") intersection() { front_trim_dials_placed(); front_stack_placed("retainer"); }
// The collar keeps 2 mm off the trim's rim, so it hides none of the bezel
// and clears the nose, which stands out to r 112.17 at 270.
if (check == "collar_off_bezel") intersection() { collar(); translate([0, 0, z_trim_back - 1]) cylinder(r = R_head + 1.9, h = 40, $fn = 360); }
if (check == "collar_vs_nose") intersection() { collar(); translate([0, 0, z_trim0]) nose(); }
// The flange fills none of the whisker grooves, and leaves the trim's seven
// screw holes open.
if (check == "grooves_open") intersection() { front_trim_dials_placed(); translate([0, 0, z_trim0]) whisker_grooves(); }
if (check == "trim_screws_open") intersection() { front_trim_dials_placed();
    for (i = [0:n_screws - 1]) { a = i*360/n_screws; if (ang_gap(a, nose_angle) > 1)
        translate([screw_r*cos(a), screw_r*sin(a), z_trim_back - 1]) cylinder(d = 3, h = 10, $fn = 24); } }
// The flange closes the collar's cavity: nothing of the cavity's open back
// lies outside the flange.
if (check == "cavity_closed") linear_extrude(height = 1) difference() { col_cavity_back2d(); col_flange2d(); }
// and over the paws, where the band's edge and the flange both come in,
// the flange stays inside the collar's back, so none of it shows beyond
// the collar's outer edge
if (check == "flange_inside_collar") linear_extrude(height = 1) difference() {
    intersection() { col_flange2d(); polygon([[0, 0], polar(300, col_narrow_a[0] - 5), polar(300, 270), polar(300, col_narrow_a[3] + 5)]); }
    // the collar's back, filled: its band and the tag's back
    col_band2d(col_r_in, col_r_back, narrow = true);
    translate(polar(col_tag_back[0], 270)) circle(r = col_tag_back[1], $fn = 96);
    circle(r = col_r_in + 0.01, $fn = 720);
}
// In the stand, as in_stand_dials() poses the head: nothing the collar adds
// meets the stand, and it clears it by 3 mm (moved 3 mm down, it still meets
// nothing), and stays 10 mm above the desk. The controls stand 30 mm and
// more above the stand, so the collar and the flange are what come nearest.
if (check == "added_vs_stand") intersection() { posed_k() added(); stand(); }
if (check == "collar_clears_stand_by_3") intersection() { translate([0, 0, -3]) posed_k() collar(); stand(); }
// Since the band's lower edge came in over the paws (2026-11-01), the
// collar clears the stand by 8 mm: its nearest point is now the tag's back,
// over the plinth, which meets it about 9 mm down.
if (check == "collar_clears_stand_by_8") intersection() { translate([0, 0, -8]) posed_k() collar(); stand(); }
if (check == "trim_clears_stand_by_3") intersection() { translate([0, 0, -3]) posed_k() front_trim_dials_placed(); stand(); }
if (check == "above_desk_by_10") intersection() { translate([0, 0, -10]) posed_k() added(); translate([-300, -300, -50]) cube([600, 600, 50]); }
// and the head still sits in the cradle as the kitten's does
if (check == "head_in_cradle") intersection() { posed_k() shell_dials(); stand(); }
// z_arm_front is where the cradle's front arm and keel really end: none of
// the stand under the chin stands in front of it
if (check == "arm_ends_at_z_arm_front") intersection() { under_chin(); posed_k() slab_from(z_arm_front + 0.01); }
// The bought parts fit behind the face, inside the collar and the flange's
// pocket (12 mm button 16 mm deep with its tags, EC11 encoder, lamp).
if (check == "button_fits")  intersection() { front(); translate([0, 0, col_z1]) button_room_at(col_screen()); }
if (check == "encoder_fits") intersection() { front(); translate([0, 0, col_z1]) encoder_room_at(col_range(), col_range[0]); }
if (check == "lamp_fits")    intersection() { front(); translate([0, 0, col_z1]) lamp_room_at(col_status()); }
// and they clear the columns and the wires' channel
if (check == "rooms_clear_of_channel") intersection() { rooms(); col_wire_channel(); }
if (check == "knob_clear_of_face") intersection() { collar(); translate([0, 0, col_z1 + knob_standoff]) translate(col_range()) knob(); }
// The wires' way is open: down the flange's channel, down the shell's slot,
// and into the case below the retainer, clear of its key and the front post.
if (check == "wire_channel_open") intersection() { wire_probe_channel(); front(); }
if (check == "wire_slot_open") intersection() { wire_probe_slot(); union() { shell_dials(); front_stack_placed("retainer"); } }
if (check == "wire_way_inside") intersection() { wire_probe_inside(); union() { shell_dials(); front_stack_placed("retainer"); } }
// The screws: their 3 mm shanks pass the flange and reach 3.5 mm into the
// inserts, and their countersunk heads stay inside the flange's back.
if (check == "screws_pass_flange") intersection() { screw_probe(); front_trim_dials_placed(); }
// an M3 countersunk head, 5.6 mm, seated flush in the flange's back
module screw_head(dz = 0) for (a = col_boss_a) translate(concat(polar(col_boss_r, a), [z_trim_back + dz]))
    cylinder(d1 = 5.6, d2 = 3, h = 1.3, $fn = 32);
if (check == "screw_heads_seat") intersection() { screw_head(); front_trim_dials_placed(); }
// The lettering keeps 1 mm inside the face's edge; 1 mm clear of the jewel,
// the button's 16 mm bezel, the knob's skirt and the studs; and its words
// 2 mm apart. Its strokes and gaps are measured by
// tests/test_enclosure_core.py (check 13).
module word2d(i) col_label2d(col_labels[i]);
module controls2d(grow) {
    translate(col_status()) circle(d = jewel_flange_d + 2*grow, $fn = 64);
    translate(col_screen()) circle(d = 16 + 2*grow, $fn = 64);
    translate(col_range()) circle(d = knob_skirt_d + 2*grow, $fn = 64);
    for (a = [col_a0, col_a1]) translate(polar((col_r_in + col_r_face)/2, a)) circle(d = col_stud_d + 2*grow, $fn = 32);
}
module words_meet(grow) for (i = [0 : len(col_labels) - 2]) for (j = [i + 1 : len(col_labels) - 1])
    intersection() { offset(r = grow) word2d(i); offset(r = grow) word2d(j); }
if (check == "labels_on_face") linear_extrude(height = 1) difference() { col_labels2d(); col_face2d(1); }
if (check == "labels_clear_of_controls") linear_extrude(height = 1) intersection() { col_labels2d(); controls2d(1); }
if (check == "labels_apart") linear_extrude(height = 1) words_meet(1);
// the knob's skirt and the jewel stay over the face
if (check == "controls_on_face") linear_extrude(height = 1) difference() {
    union() { translate(col_status()) circle(d = jewel_flange_d, $fn = 64); translate(col_screen()) circle(d = 16, $fn = 64);
              translate(col_range()) circle(d = knob_skirt_d, $fn = 64); }
    col_face2d(); }

// ---- must find real geometry (positive controls) --------------------------
// the collar stands on the flange: raised 0.2 mm into the collar, the
// flange meets it
if (check == "collar_on_flange") intersection() { collar(); translate([0, 0, 0.2]) col_flange(); }
// the stand probes are near enough to bite: 10 mm down the collar, and
// 6 mm down the flange, meet the stand; 15 mm down, the collar meets the desk
if (check == "collar_stand_probe_bites") intersection() { translate([0, 0, -10]) posed_k() collar(); stand(); }
if (check == "trim_stand_probe_bites") intersection() { translate([0, 0, -6]) posed_k() front_trim_dials_placed(); stand(); }
if (check == "desk_probe_bites") intersection() { translate([0, 0, -15]) posed_k() added(); translate([-300, -300, -50]) cube([600, 600, 50]); }
// the stand under the chin does reach z_arm_front, within 0.5 mm
if (check == "arm_reaches_z_arm_front") intersection() { under_chin(); posed_k() slab_from(z_arm_front - 0.5); }
// the common 21 mm button runs into the flange's floor, so button_fits sees it
if (check == "button_21mm_meets_flange") intersection() { front(); translate([0, 0, col_z1]) button_room_at(col_screen(), 21); }
// the probes find the parts they look past: the channel probe moved 6 mm
// along the rim meets the flange; the slot probe moved 10 mm meets the
// shell's wall; the screw probe moved 2 mm back meets the flange's back
if (check == "channel_probe_bites") intersection() { rotate([0, 0, 360*6/(2*PI*115)]) wire_probe_channel(); front_trim_dials_placed(); }
if (check == "slot_probe_bites") intersection() { rotate([0, 0, 360*10/(2*PI*110)]) wire_probe_slot(); shell_dials(); }
if (check == "screw_holes_open") difference() { screw_probe(); front_trim_dials_placed(); collar(); }
// and the head probe, 0.5 mm deeper than flush, meets the countersink's walls
if (check == "head_probe_bites") intersection() { screw_head(0.5); front_trim_dials_placed(); }
// the cavity check bites: a flange 0.5 mm smaller all round leaves some
// of the cavity's back open
if (check == "cavity_probe_bites") linear_extrude(height = 1) difference() { col_cavity_back2d(); offset(r = -0.5) col_flange2d(); }
// the old, full-width flange would show past the collar over the paws
if (check == "full_flange_shows") linear_extrude(height = 1) difference() {
    intersection() { col_band2d(R_head - 0.3, col_r_flange); polygon([[0, 0], polar(300, col_narrow_a[0] - 5), polar(300, 270), polar(300, col_narrow_a[3] + 5)]); }
    col_band2d(col_r_in, col_r_back, narrow = true);
    translate(polar(col_tag_back[0], 270)) circle(r = col_tag_back[1], $fn = 96);
    circle(r = col_r_in + 0.01, $fn = 720);
}
if (check == "labels_present") collar_text();
// The three lettering probes are near enough to bite: the words come
// within 5 mm of the face's edge, within 4 mm of a control, and within 64
// mm of each other (STATUS, on the tag, is about 60 mm from the other two).
if (check == "labels_near_edge") linear_extrude(height = 1) difference() { col_labels2d(); col_face2d(5); }
if (check == "labels_near_controls") linear_extrude(height = 1) intersection() { col_labels2d(); controls2d(4); }
if (check == "labels_near_each_other") linear_extrude(height = 1) words_meet(32);
if (check == "canary") collar();
