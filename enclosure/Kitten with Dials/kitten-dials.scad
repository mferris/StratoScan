// ============================================================
// StratoScan KITTEN WITH DIALS: the kitten case wearing a collar under its
// chin, with the Retro with Dials' three controls set in it (2026-11-01):
//
//   SCREEN  a 12 mm momentary push button, on the left
//   STATUS  a jewel lamp (5 mm RGB LED behind a printed clear lens), in the
//           middle, where a collar's tag hangs: an inlaid ring round it
//   RANGE   a rotary encoder with a push switch, under the knob, on the right
//
// Everything else is the kitten case, unchanged and shared: this file
// includes ../Kitten Enclosure Two-Tone/kitten-enclosure-twotone.scad and
// adds parts. The controls themselves, their sizes, the knob and the lens
// are the Retro with Dials' (../Retro Radar with Dials/dial-controls.scad),
// and so is the wiring and the software (CONTROLS=1).
//
// Why the collar hangs from the face, not from the head's wall. The Retro
// with Dials' arc screws to the drum from inside. Under the kitten's chin
// that can't be done: the stand's cradle wraps the bottom 130 degrees of the
// head (205-335), its front arm hugging the wall 1 mm off it from z 43.5 to
// 59.5, and the keel filling 247-293 behind that, so no part on the head's
// outside below the chin can reach the wall short of z 59.5, 1.5 mm from the
// shell's front edge; and either side of the cradle the speakers' sleeves
// fill the wall inside. So the collar stands in front of the cradle, and
// fixes to the front trim instead: the trim grows a flange under the chin,
// in its own plane, which is the collar's back and its cover, and two M3
// screws come through it from behind into heat-set inserts in the collar.
// The trim is the kitten's own part (not shared), held by seven screws.
// The stand is the kitten's, unchanged.
//
// The wires go through a 45-degree channel in the flange and down a slot in
// the shell's front edge, in the shelf's gap at the bottom, into the case
// below the retainer. That slot is the only change to the shell.
//
// Coordinates are the kitten's: Z is the case axis (front = +Z), +Y up,
// +X to the right when you face the screen. The collar is centred on 270,
// straight down.
// ============================================================

include <../Kitten Enclosure Two-Tone/kitten-enclosure-twotone.scad>
part = "none";          // silence the kitten file's own part switch
include <../Retro Radar with Dials/dial-controls.scad>

dpart = "preview";      // preview | in_stand | exploded | closeup | sections
                        // shell_dials | front_trim_dials | collar_print | collar_text_print
                        // coupon_print | coupon_text_print

// ---------- where the collar sits ----------
R_head     = outer_dia/2;            // 111.67, the head's wall and the trim's rim
// The trim, where front_stack_placed() puts it: its back on the shell's front
// edge, its face at z_trim_face (66.62).
z_trim_back = shell_depth;           // 61
z_trim0     = shell_depth + glass_thickness;   // the trim's own z 0, in the head's frame
// The stand's front arm and keel come forward to here, the head's z, as the
// stand poses the head (the cradle's arms are arm_gap/2 + arm_w either side
// of the head's middle): 59.5. The flange's back is 1.5 mm in front of it.
z_arm_front = shell_depth/2 + arm_gap/2 + arm_w;
// The collar's inner edge, 2 mm off the trim's rim: the nose stands out to
// r 112.17 at 270 and 2.6 mm proud, and the collar must not touch it.
col_r_in   = R_head + 2;             // 113.67
// The collar stands on the flange, from the trim's face forward. 14.5 mm of
// room behind its 3 mm face: the lamp needs 14, the encoder 12, and the
// button 18 (16 with its tags and 2 for the wires to turn), which it gets
// from a 4 mm pocket in the flange behind it.
col_z0     = z_trim_face;            // 66.62, the collar's back, on the flange
col_room   = 14.5;
col_z1     = col_z0 + col_room + ctl_face_t;   // 84.12, the face
// Its outer wall leans out a little as it comes forward: r 138.5 at the
// back, 141 at the face. Two things under it set those (the head leans back
// 18 degrees in the stand, so the collar's lower edge is the part nearest
// the stand): the back's lowest point, at 270, stays 2 mm above the
// plinth, near whose front edge it is; and the face's lower edge stays 5 mm
// or more above the paws, which sit under it from about 240 to 300 degrees
// (checks.scad: collar_clears_stand_by_3).
col_r_back = 138.5;
col_r_face = 141;
// The band's two round ends are centred here; with the ends it runs from
// about 212 to 328 degrees, over the cradle's front arm (205-335) and up the
// cheeks, where the face has room for the button and the knob beyond the paws.
col_a0     = 218;
col_a1     = 322;
// The tag: a round tag hanging from the collar at 270, between the paws,
// carrying the STATUS lamp. Its sides lean out as it comes forward, an
// oblique cone from (centre r, radius) at the back to the same at the face:
// its back's lowest point stays 3.5 mm above the plinth, its face hangs
// lower, past the plinth's front edge, 13 mm above the desk.
col_tag_back = [127, 10];
col_tag_face = [133, 16];
col_wall   = 2.5;
// The cavity's outer side at the back stays inside the flange (col_r_flange),
// so the flange closes it.
col_cav_back = 135;

// ---------- the controls on the face (angle, radius) ----------
// SCREEN on the left cheek, STATUS on the tag, RANGE on the right cheek,
// where the knob is clear of the paws and the tail below it.
col_screen   = [228, 126.5];
col_status   = [270, 129.5];
col_range    = [312, 126.5];
// The lettering, in the shared engraving font at the shared size
// (lettering_cap), inlaid 0.6 mm in a second colour, upright: SCREEN and
// RANGE along the band beside their controls, on the side towards the tag,
// since the knob's 24 mm skirt fills the band's width; STATUS on the tag,
// under the jewel. [angle, radius, word]
col_labels   = [[237.6, 126.5, "SCREEN"], [301.9, 126.5, "RANGE"], [270, 141.3, "STATUS"]];
col_label_depth = 0.6;
// and a stud inlaid in each round end, as the arc has rivets
col_stud_d   = 3.6;

// ---------- the flange, on the trim ----------
// In the trim's own plane, the trim's full thickness, from just inside its
// rim (0.3 mm into it, outside the whisker grooves, which reach r 110.27) to
// col_r_flange: 3.2 mm above the plinth at its lowest, under the chin.
col_r_flange = 135.5;
// Two M3 x 10 countersunk screws from behind the flange into M3 x 5
// heat-set inserts in two columns in the collar, either side of the lamp.
col_boss_a   = [252, 288];
col_boss_r   = 127;
col_boss_d   = 8;
col_insert_d = 4.0;     // M3 heat-set insert, as everywhere else in the case
col_insert_h = 6;
col_screw_clear = 3.4;
col_csk_d    = 6.2;     // the countersink at the flange's back, 90 degrees
// The button's pocket in the flange: 4 mm deep, 1.62 mm of flange left.
col_pocket_d = button_nut + 0.6;
col_pocket   = 4;

// ---------- the wires ----------
// A 7 x 3 mm channel through the flange at 45 degrees, from inside the
// collar's cavity down to the trim's back, over a slot in the shell's front
// edge: eight thin wires, two rows of four. The slot is in the shelf's gap
// (245-295), between the retainer's key (250-258) and the front post at 270,
// and runs back to z 52.5, below the retainer (z 57-61), where the wires turn
// into the case.
col_wire_a   = 263;
col_wire_w   = 7;       // along the rim
col_wire_t   = 3;       // across it
col_wire_in  = 117.8;   // the channel's middle at the flange's front
col_wire_out = col_wire_in - (z_trim_face - z_trim_back);   // 112.18 at its back: 45 degrees
col_slot_w   = 7.5;
col_slot_z0  = 52.5;

// ============================================================
// helpers
// ============================================================
function col_t(z) = (z - col_z0) / (col_z1 - col_z0);
function col_r_out(z) = col_r_back + (col_r_face - col_r_back) * col_t(z);

// An annular band from r0 to r1 between the angles a0 and a1, with round
// ends centred on them, in plan.
module col_band2d(r0, r1, a0 = col_a0, a1 = col_a1) {
    rc = (r1 - r0)/2;  rm = (r0 + r1)/2;
    union() {
        intersection() {
            difference() { circle(r = r1, $fn = 720); circle(r = r0, $fn = 720); }
            polygon([[0, 0], polar(400, a0), polar(400, (a0 + a1)/2), polar(400, a1)]);
        }
        translate(polar(rm, a0)) circle(r = rc, $fn = 96);
        translate(polar(rm, a1)) circle(r = rc, $fn = 96);
    }
}

// A band whose outer radius runs from r1a at za to r1b at zb, the inner
// radius r0 throughout, with round ends: a rotate_extrude for the arc and an
// oblique cone at each end, so every section is col_band2d at that height.
// The cones are 0.01 mm narrower than the band (2026-11-01): at full width
// each touched the band's inner and outer faces along a line, and the
// collar's mesh had an edge there that a slicer reports as non-manifold.
module col_band(r0, r1a, za, r1b, zb) {
    rotate([0, 0, col_a0]) rotate_extrude(angle = col_a1 - col_a0, $fn = 720)
        polygon([[r0, za], [r1a, za], [r1b, zb], [r0, zb]]);
    for (a = [col_a0, col_a1]) hull() {
        translate(concat(polar((r0 + r1a)/2, a), [za])) cylinder(r = (r1a - r0)/2 - 0.01, h = 0.01, $fn = 96);
        translate(concat(polar((r0 + r1b)/2, a), [zb - 0.01])) cylinder(r = (r1b - r0)/2 - 0.01, h = 0.01, $fn = 96);
    }
}

function col_screen() = polar(col_screen[1], col_screen[0]);
function col_status() = polar(col_status[1], col_status[0]);
function col_range()  = polar(col_range[1], col_range[0]);

// one word, upright under the chin: its baseline along the circle of radius
// r, centred on angle a
module col_label2d(l) {
    rotate([0, 0, l[0] - 270]) translate([0, -l[1]])
        gorton_text(l[2], lettering_cap, lettering_pen, lettering_track);
}
module col_labels2d() { for (l = col_labels) col_label2d(l); }

// what is inlaid in the second colour: the lettering and the two studs
module col_studs2d() {
    for (a = [col_a0, col_a1]) translate(polar((col_r_in + col_r_face)/2, a)) circle(d = col_stud_d, $fn = 32);
}
module col_inlay2d() { col_labels2d(); col_studs2d(); }

// the tag at height z, in plan: the oblique cone's section there
module col_tag_disc(c, z, h = 0.01) translate(concat(polar(c[0], 270), [z])) cylinder(r = c[1], h = h, $fn = 96);
module col_tag(inset = 0, z0 = col_z0, z1 = col_z1) hull() {
    col_tag_disc([col_tag_back[0] + (col_tag_face[0] - col_tag_back[0]) * col_t(z0),
                  col_tag_back[1] + (col_tag_face[1] - col_tag_back[1]) * col_t(z0) - inset], z0);
    col_tag_disc([col_tag_back[0] + (col_tag_face[0] - col_tag_back[0]) * col_t(z1),
                  col_tag_back[1] + (col_tag_face[1] - col_tag_back[1]) * col_t(z1) - inset], z1 - 0.01);
}
// the collar's face in plan, for the lettering's checks
module col_face2d(inset = 0) {
    col_band2d(col_r_in + inset, col_r_face - inset);
    translate(polar(col_tag_face[0], 270)) circle(r = col_tag_face[1] - inset, $fn = 96);
}

// ============================================================
// the collar
// ============================================================
module collar() {
    difference() {
        union() {
            difference() {
                union() {
                    col_band(col_r_in, col_r_back, col_z0, col_r_face, col_z1);
                    col_tag();
                }
                // the cavity, open at the back, where the flange closes it
                col_band(col_r_in + col_wall, col_cav_back, col_z0 - 1,
                         col_r_out(col_z1 - ctl_face_t) - col_wall, col_z1 - ctl_face_t);
                col_tag(col_wall, col_z0 - 1, col_z1 - ctl_face_t);
            }
            // the two columns for the screws, from the face back to the flange
            for (a = col_boss_a) translate(concat(polar(col_boss_r, a), [col_z0]))
                cylinder(d = col_boss_d, h = col_z1 - col_z0 - 0.5, $fn = 48);
        }
        // their inserts, from the back
        for (a = col_boss_a) translate(concat(polar(col_boss_r, a), [col_z0 - 0.01]))
            cylinder(d = col_insert_d, h = col_insert_h, $fn = 32);
        // the controls, through the face
        translate([0, 0, col_z1]) {
            lamp_hole_cut(col_status());
            button_hole_cut(col_screen());
            encoder_hole_cut(col_range());
        }
        // the inlay, sunk into the face for the second colour
        translate([0, 0, col_z1 - col_label_depth]) linear_extrude(height = col_label_depth + 1) col_inlay2d();
    }
}

// the inlay as its own solid, for the second filament
module collar_text() {
    translate([0, 0, col_z1 - col_label_depth]) linear_extrude(height = col_label_depth) col_inlay2d();
}

// The lettering coupon: a lettering_coupon_t slice of the collar's face round
// each word, cut from the collar, with its lettering, as the arc's is: a few
// minutes' print to tune the slicer before the collar.
module col_coupon2d() intersection() { col_face2d(); for (l = col_labels) offset(r = 3) hull() col_label2d(l); }
module test_lettering_collar() intersection() {
    collar();
    translate([0, 0, col_z1 - lettering_coupon_t]) linear_extrude(height = lettering_coupon_t + 1) col_coupon2d();
}
module test_lettering_collar_text() translate([0, 0, col_z1 - col_label_depth]) linear_extrude(height = col_label_depth) col_labels2d();

// ============================================================
// the trim with its flange
// ============================================================
// The flange in the head's frame: the trim's thickness, from 0.3 mm inside
// the rim out to col_r_flange, under the collar.
module col_flange() {
    translate([0, 0, z_trim_back]) linear_extrude(height = z_trim_face - z_trim_back)
        col_band2d(R_head - 0.3, col_r_flange);
}
// What the flange loses: the screws' holes and countersinks from behind, the
// button's pocket, and the wires' channel.
module col_flange_cuts() {
    for (a = col_boss_a) translate(concat(polar(col_boss_r, a), [0])) {
        translate([0, 0, z_trim_back - 1]) cylinder(d = col_screw_clear, h = z_trim_face - z_trim_back + 2, $fn = 32);
        translate([0, 0, z_trim_back - 0.01]) cylinder(d1 = col_csk_d, d2 = 0, h = col_csk_d/2, $fn = 32);
    }
    translate(concat(col_screen(), [z_trim_face - col_pocket])) cylinder(d = col_pocket_d, h = col_pocket + 1, $fn = 64);
    col_wire_channel();
}
// the channel: a 7 x 3 mm slot, its middle at col_wire_in at the flange's
// front and col_wire_out at its back, so it leans inward at 45 degrees
module col_wire_channel() {
    rotate([0, 0, col_wire_a]) hull() {
        translate([col_wire_in, 0, z_trim_face]) col_wire_slot2d_solid();
        translate([col_wire_out, 0, z_trim_back - 0.02]) col_wire_slot2d_solid();
    }
}
module col_wire_slot2d_solid() linear_extrude(height = 0.02, center = true)
    hull() for (s = [-1, 1]) translate([0, s * (col_wire_w - col_wire_t)/2]) circle(d = col_wire_t, $fn = 24);

// the trim with its flange, in the head's frame
module front_trim_dials_placed() {
    difference() {
        union() {
            translate([0, 0, z_trim0]) front_trim();
            col_flange();
        }
        col_flange_cuts();
    }
}

// ============================================================
// the shell: the kitten's shell with the wires' slot
// ============================================================
module shell_dials() {
    difference() {
        shell();
        rotate([0, 0, col_wire_a])
            translate([R_head - wall - 1, -col_slot_w/2, col_slot_z0]) cube([wall + 2, col_slot_w, shell_depth - col_slot_z0 + 1]);
    }
}

// ============================================================
// pictures
// ============================================================
c_head   = "#26262A";   // the kitten's head, black
c_face   = "#2E2E33";
c_collar = "#B5452F";   // a red leather collar
c_glass  = "#08140E";

module screen_picture_k() {
    translate([0, 0, shell_depth + glass_thickness - 0.6]) {
        color(c_glass) cylinder(d = panel_diameter - 1, h = 0.5, $fn = 180);
        color("#2F7A4A") for (r = [30, 60, 89]) translate([0, 0, 0.5]) difference() { cylinder(r = r, h = 0.15, $fn = 180); translate([0, 0, -0.1]) cylinder(r = r - 0.6, h = 0.4, $fn = 180); }
        color("#3FAF66", 0.9) translate([0, 0, 0.55]) rotate_extrude(angle = 38, $fn = 180) square([89, 0.12]);
        color("#9CFFB8") for (p = [[30, 22], [-41, 50], [55, -35], [-20, -62], [70, 40]]) translate([p[0], p[1], 0.7]) cylinder(d = 3, h = 0.2, $fn = 16);
    }
}

module collar_controls() {
    translate([0, 0, col_z1]) controls_fitted(col_status(), col_screen(), col_range());
    color(c_label) collar_text();
}

module head_dials_assembled() {
    color(c_head) shell_dials();
    color("Gray") front_stack_placed("retainer");
    screen_picture_k();
    color(c_face) front_trim_dials_placed();
    color(c_collar) collar();
    collar_controls();
}

// the head in its stand, posed as on a desk (front towards -Y)
module posed_k() {
    translate([0, 0, base_h + cradle_od/2 - 3]) rotate([90 - stand_angle, 0, 0]) translate([0, 0, -shell_depth/2]) children();
}
module in_stand_dials() {
    color("#1c1c1c") part_stand_body();
    color("#f4f4f2") part_stand_paws();
    color("#1c1c1c") part_stand_toes();
    color("#1c1c1c") part_stand_tail();
    color("#f4f4f2") part_stand_tail_tip();
    color("#f4f4f2") part_stand_claws();
    posed_k() head_dials_assembled();
}

// The bought parts behind the face, for the sections only: the button's
// nut and body with its tags (button_deep), the encoder's body and pins, the
// LED and its leads.
c_part = "#C9A23A";
module bought_parts() translate([0, 0, col_z1 - ctl_face_t]) {
    translate(col_screen()) {
        translate([0, 0, -2]) cylinder(d = button_nut, h = 2, $fn = 6);
        translate([0, 0, -button_deep]) cylinder(d = 13, h = button_deep, $fn = 48);
    }
    translate(col_range()) rotate([0, 0, col_range[0]]) {
        translate([-enc_body/2, -enc_body/2, -(enc_room - 6) + (ctl_face_t - enc_panel)]) cube([enc_body, enc_body, enc_room - 6]);
        for (y = [-5, 0, 5]) translate([-5, y, -enc_room + (ctl_face_t - enc_panel)]) cylinder(d = 0.8, h = 6, $fn = 8);
    }
    translate(col_status()) {
        translate([0, 0, ctl_face_t - jewel_shank_h - 0.2]) cylinder(d = 5, h = 8.6, $fn = 32);
        for (x = [-1.9, -0.6, 0.6, 1.9]) translate([x, 0, -lamp_room + ctl_face_t + 0.5]) cylinder(d = 0.5, h = lamp_room - 3, $fn = 8);
    }
}

// A section through one control, at angle a: the head, the trim and the
// collar cut on the plane through the case's axis and the control, near
// the collar, each in its colour, with the bought part behind the face;
// seen from the side, the face up.
module section_cut(a) rotate([0, 0, a]) translate([92, -60, 38]) cube([75, 60, 80]);
module section_at(a) {
    color(c_head)   intersection() { shell_dials(); section_cut(a); }
    color("Gray")   intersection() { front_stack_placed("retainer"); section_cut(a); }
    color(c_glass)  intersection() { front_stack_placed("glass"); section_cut(a); }
    color(c_face)   intersection() { front_trim_dials_placed(); section_cut(a); }
    color(c_collar) intersection() { collar(); section_cut(a); }
    color(c_label)  intersection() { collar_text(); section_cut(a); }
    // the controls, each coloured after it is cut, so its cut face is too
    translate([0, 0, col_z1]) {
        color(c_knob)   intersection() { translate([0, 0, knob_standoff]) translate(col_range()) knob(); translate([0, 0, -col_z1]) section_cut(a); }
        color(c_chrome) intersection() { translate(col_screen()) { cylinder(d = 14, h = 1.6, $fn = 64); cylinder(d = 10, h = 2.4, $fn = 64); }
                                         translate([0, 0, -col_z1]) section_cut(a); }
        color(c_jewel)  intersection() { translate(col_status()) jewel(); translate([0, 0, -col_z1]) section_cut(a); }
    }
    color(c_part) intersection() { bought_parts(); section_cut(a); }
    // the stand's front arm and keel, where they sit behind the collar
    color("#5a5a5a") intersection() { inverse_posed_k() part_stand_body(); section_cut(a);
                                       translate([0, 0, -1]) cylinder(r = cradle_od/2 + 0.5, h = 100, $fn = 360); }
}
// the stand in the head's frame: posed_k()'s inverse
module inverse_posed_k() {
    translate([0, 0, shell_depth/2]) rotate([-(90 - stand_angle), 0, 0]) translate([0, 0, -(base_h + cradle_od/2 - 3)]) children();
}

if (dpart == "none") {}   // for checks.scad, which includes this file
else if (dpart == "shell_dials") shell_dials();
// The trim as it prints, face up and in its own frame, as front_trim.stl is
// exported: rabbet and flange on the bed.
else if (dpart == "front_trim_dials") translate([0, 0, -z_trim0]) front_trim_dials_placed();
// the collar and its inlay face down, the inlay the first 0.6 mm
else if (dpart == "collar_print") translate([0, 0, col_z1]) rotate([180, 0, 0]) collar();
else if (dpart == "collar_text_print") translate([0, 0, col_z1]) rotate([180, 0, 0]) collar_text();
else if (dpart == "coupon_print") translate([0, 0, col_z1]) rotate([180, 0, 0]) test_lettering_collar();
else if (dpart == "coupon_text_print") translate([0, 0, col_z1]) rotate([180, 0, 0]) test_lettering_collar_text();
else if (dpart == "collar") collar();
else if (dpart == "in_stand") in_stand_dials();
else if (dpart == "closeup") {
    intersection() {
        union() {
            color(c_head) shell_dials();
            color(c_face) front_trim_dials_placed();
            screen_picture_k();
        }
        translate([0, -125, 0]) cube([180, 90, 200], center = true);
    }
    color(c_collar) collar();
    collar_controls();
}
else if (dpart == "section_screen") section_at(col_screen[0]);
else if (dpart == "section_status") section_at(col_status[0]);
else if (dpart == "section_range")  section_at(col_range[0]);
else if (dpart == "section_wire")   section_at(col_wire_a);
else if (dpart == "exploded") {
    color(c_head) shell_dials();
    screen_picture_k();
    translate([0, 0, 25]) color(c_face) front_trim_dials_placed();
    translate([0, -15, 60]) { color(c_collar) collar(); collar_controls(); }
}
else head_dials_assembled();
