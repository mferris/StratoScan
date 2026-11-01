// ============================================================
// The three controls every "with Dials" case carries, and the two parts
// printed for them: the RANGE knob and the STATUS lamp's jewel lens
// (2026-11-01). Retro Radar with Dials and Kitten with Dials both include
// this file, so the bought parts' sizes, the knob and the lens are one
// design, and the two cases take the same parts and print the same knob and
// lens (knob.stl and jewel_lens.stl, in this folder).
//
//   STATUS  a jewel lamp (5 mm RGB LED behind a printed clear lens)
//   SCREEN  a 12 mm momentary push button, short-bodied
//   RANGE   an EC11 rotary encoder with a push switch, under the knob
//
// Moved here from retro-dials.scad unchanged. A case that includes this
// file holds its controls in a face ctl_face_t thick, as the arc's is.
// ============================================================

// ---------- the face the controls go through ----------
ctl_face_t  = 3;      // the face's thickness
lamp_hole   = 12.2;   // the jewel lens's shank
enc_hole    = 7.4;    // EC11 encoder, M7 bushing
enc_panel   = 2.0;    // the face is thinned to this round the encoder so its nut reaches
enc_relief  = 15;     // diameter of that thinning, from inside
button_hole = 12.2;   // 12 mm momentary panel button: short enough to fit behind the face
// The most the button may reach behind the face, body and tags (2026-10-29).
// The arc's cavity is 18.1 mm deep, to its cover, and this leaves 2 mm for
// the wires to turn off the tags. The common 21 mm button is too long.
button_deep = 16;
button_nut  = 16;     // across the button's nut, the widest thing behind the face
// The lamp behind the face: the lens's shank, a 5 mm LED and 12 mm of its
// leads, in a 9 mm round, 14 mm deep from the face's inner side.
lamp_room_d = 9;
lamp_room   = 14;
// The encoder behind the face: a 13 x 13 body, 7 deep, then 6 mm of pins.
enc_body    = 13.5;
enc_room    = 13;

// ---------- the knob (printed) ----------
knob_cap_d  = 18;
knob_cap_h  = 14;
knob_skirt_d = 24;
knob_skirt_h = 3;
knob_flutes = 18;
knob_shaft_d = 6.15;   // 6 mm D shaft
knob_shaft_flat = 4.6; // across the flat
knob_bore_h = 12;
knob_standoff = 1.5;   // the encoder's nut holds the knob this far off the face

// ---------- the jewel lens (printed in clear or translucent filament) ----------
jewel_d      = 16;
jewel_flange_d = 16.6;
jewel_flange_t = 1.2;
jewel_shank_d  = 11.9;
jewel_shank_h  = ctl_face_t + 0.4;
led_d          = 5.1;   // 5 mm RGB LED, pushed into the shank

// ---------- picture colours ----------
c_knob   = "#1B1C1D";
c_label  = "#E9E2CC";
c_chrome = "#B9BEC2";
c_jewel  = "#6CFF8E";

function polar(r, a) = [r*cos(a), r*sin(a)];

module knob() {
    difference() {
        union() {
            cylinder(d = knob_skirt_d, h = knob_skirt_h, $fn = 96);
            translate([0, 0, knob_skirt_h]) cylinder(d1 = knob_skirt_d - 2, d2 = knob_cap_d, h = 2, $fn = 96);
            difference() {
                cylinder(d = knob_cap_d, h = knob_skirt_h + knob_cap_h, $fn = 96);
                for (i = [0:knob_flutes - 1]) rotate([0, 0, i*360/knob_flutes])
                    translate([knob_cap_d/2 + 0.6, 0, knob_skirt_h + 2.5]) cylinder(d = 2.6, h = knob_cap_h, $fn = 16);
            }
            // the pointer, a raised line across the skirt
            translate([knob_cap_d/2 - 1, -0.7, 0]) cube([knob_skirt_d/2 - knob_cap_d/2 + 0.6, 1.4, knob_skirt_h + 0.6]);
        }
        // D bore from below
        translate([0, 0, -0.01]) intersection() {
            cylinder(d = knob_shaft_d, h = knob_bore_h, $fn = 48);
            translate([-knob_shaft_d/2, -knob_shaft_d/2, 0]) cube([knob_shaft_flat, knob_shaft_d, knob_bore_h]);
        }
        // a small chamfer on the top edge
        translate([0, 0, knob_skirt_h + knob_cap_h - 0.8]) difference() {
            cylinder(d = knob_cap_d + 2, h = 2, $fn = 96);
            cylinder(d1 = knob_cap_d, d2 = knob_cap_d - 2.4, h = 1.2, $fn = 96);
        }
    }
}

module jewel() {
    difference() {
        union() {
            translate([0, 0, -jewel_shank_h]) cylinder(d = jewel_shank_d, h = jewel_shank_h, $fn = 64);
            cylinder(d = jewel_flange_d, h = jewel_flange_t, $fn = 64);
            // faceted dome: an octagonal low-poly cap, the jewel lamp's cut glass
            translate([0, 0, jewel_flange_t]) intersection() {
                scale([1, 1, 0.62]) sphere(d = jewel_d, $fn = 8);
                translate([-20, -20, 0]) cube([40, 40, 20]);
            }
        }
        translate([0, 0, -jewel_shank_h - 0.01]) cylinder(d = led_d, h = jewel_shank_h + 2.5, $fn = 32);
    }
}

// The holes for the three controls in a face whose front is at z = 0 and
// which is ctl_face_t thick, each at its point in x and y: the lamp's, the
// button's, and the encoder's, with the face thinned round it from inside.
module lamp_hole_cut(p)   translate([p[0], p[1], -ctl_face_t - 1]) cylinder(d = lamp_hole, h = ctl_face_t + 2, $fn = 64);
module button_hole_cut(p) translate([p[0], p[1], -ctl_face_t - 1]) cylinder(d = button_hole, h = ctl_face_t + 2, $fn = 64);
module encoder_hole_cut(p) translate([p[0], p[1], -ctl_face_t - 1]) {
    cylinder(d = enc_hole, h = ctl_face_t + 2, $fn = 48);
    cylinder(d = enc_relief, h = 1 + ctl_face_t - enc_panel, $fn = 48);   // thin the face from inside
}

// What each bought part takes behind a face whose front is at z = 0, for the
// fit checks: the button's nut `deep` back, the encoder's body (turned by
// `a` degrees), and the lamp.
module button_room_at(p, deep = button_deep) translate([p[0], p[1], -ctl_face_t - deep]) cylinder(d = button_nut, h = deep - 0.05, $fn = 48);
module encoder_room_at(p, a = 0) translate([p[0], p[1], -enc_panel - enc_room]) rotate([0, 0, a])
    translate([-enc_body/2, -enc_body/2, 0]) cube([enc_body, enc_body, enc_room - (ctl_face_t - enc_panel) - 0.05]);
module lamp_room_at(p) translate([p[0], p[1], -ctl_face_t - lamp_room]) cylinder(d = lamp_room_d, h = lamp_room - 0.05, $fn = 32);

// The three controls as they look fitted, on a face whose front is at z = 0:
// the knob standing off the face on its nut, the button's chrome bezel and
// flat cap, and the jewel.
module controls_fitted(lamp, button, knob_at) {
    color(c_knob) translate([knob_at[0], knob_at[1], knob_standoff]) knob();
    color(c_chrome) translate([button[0], button[1], 0]) {
        cylinder(d = 14, h = 1.6, $fn = 64);
        cylinder(d = 10, h = 2.4, $fn = 64);
    }
    color(c_jewel, 0.85) translate([lamp[0], lamp[1], 0]) jewel();
}
