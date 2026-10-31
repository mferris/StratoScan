// ============================================================
// StratoScan retro radar WITH DIALS: the retro case plus one control
// arc on its upper right, carrying three controls:
//
//   STATUS  a jewel lamp (5 mm RGB LED behind a printed clear lens):
//           green hearing aircraft, amber receiver deaf, red power trouble
//   RANGE   a rotary encoder with a push switch: turn to zoom, push for home
//   SCREEN  a 12 mm momentary push button: screen on/off, hold for always on
//
// Everything else is the retro case, unchanged and shared: this file
// includes ../Retro Radar Enclosure/retro-enclosure.scad and adds parts.
// The only change to the retro shell is three holes through its wall
// (two screws and the wire hole), cut in shell_dials() below.
//
// Why one arc and not a pod on each shoulder: two round pods on the upper
// shoulders of a round drum make the well-known three-circle "mouse ears"
// silhouette, which is somebody else's trademark. One arc hugging the
// drum reads as an instrument's control column -- the arrangement many
// radar consoles used, with the controls beside the scope -- and copies no
// particular product. See README.md, "Design references".
//
// Coordinates are the retro case's: Z is the case axis (front = +Z), +Y up,
// +X to the right when you face the screen.
// ============================================================

include <../Retro Radar Enclosure/retro-enclosure.scad>
part = "none";          // silence the retro file's own part switch

dpart = "preview";      // preview | front | exploded | in_stand
                        // shell_dials | pod | pod_cover | pod_text | knob | jewel

// ---------- the arc ----------
R_case    = outer_dia/2;          // 111.67, the drum's outer wall
pod_gap   = 2.0;                  // between the arc's inner face and the drum: clears the rivets (1.4 proud)
pod_r_in  = R_case + pod_gap;     // 113.67
pod_r_out = 148;
pod_w     = pod_r_out - pod_r_in; // 36.33 radially
pod_r_mid = (pod_r_in + pod_r_out)/2;
pod_a0    = 32;                   // lower end: its round end stays clear of the speaker grille (+-23 deg round 0)
pod_a1    = 74;                   // upper end
pod_wall  = 2.5;
pod_face_t = 3;                   // front face thickness
// The face sits 1 mm behind the front trim's face, so the arc reads as a
// part bolted to the case rather than a bulge in the trim. z_trim_face is
// the retro file's, 66.62, where front_stack_placed() puts the trim
// (2026-10-29). This file had its own, worked out from the panel's whole
// 6.45 mm depth rather than the 1.62 mm glass, which stood the face at
// 70.55, 3.9 mm proud of the trim. The arc is 4.9 mm shallower for it, so
// the button behind the face is a short one (button_deep).
pod_z1    = z_trim_face - 1;      // front face, 65.62
// The back, with its cover, stays in front of the side vent slots (their
// tops are at z=41.25), so all nine still breathe.
pod_z0    = 44.5;

// ---------- the controls on the face (angle, radius) ----------
ctl_r      = 127;
lamp_a     = 65;
knob_a     = 40;
button_a   = 52.5;
lamp_hole  = 12.2;   // the jewel lens's shank
enc_hole   = 7.4;    // EC11 encoder, M7 bushing
enc_panel  = 2.0;    // the face is thinned to this round the encoder so its nut reaches
enc_relief = 15;     // diameter of that thinning, from inside
button_hole = 12.2;  // 12 mm momentary panel button: short enough to fit behind the face
// The most the button may reach behind the face, body and tags (2026-10-29).
// The cavity behind the face is 18.1 mm deep, to the cover, and this leaves
// 2 mm for the wires to turn off the tags. The common 21 mm button would run
// through the 2.5 mm cover (button_21mm_meets_cover).
button_deep = 16;
// The lettering round the outer edge, inlaid in a second colour like the
// antenna cover's (see "Inlaid lettering" in the retro file). Until
// 2026-10-31 it was size 3.3 at r 143.6, centred on its controls, and its
// 0.5 mm strokes printed broken: SCREEN's C almost gone, STATUS's S half
// there. At 5.6, fattened 0.11 mm a side, the strokes are 1.04 mm and the
// narrowest gap 0.87 mm. The three words are then too long to centre on
// their controls, 12.5 deg apart, without running into each other, so
// STATUS stands 2.4 deg beyond its lamp and RANGE 2 deg short of its knob,
// still over them, with about 3.5 mm between the words. The words are
// straight, so their ends stand further out than their middles; at r 143.1
// they keep 1 mm inside the face's edge and clear of the knob's skirt
// (checks.scad: labels_on_face, labels_clear_of_controls, labels_apart).
label_r    = 143.1;
label_size = 5.6;
label_depth = 0.6;
label_bold  = 0.11;  // each stroke fattened by this much a side
label_spacing = 1.1;
label_font  = "Liberation Sans:style=Bold";
labels     = [[lamp_a + 2.4, "STATUS"], [button_a, "SCREEN"], [knob_a - 2, "RANGE"]];

// ---------- fixing it to the case ----------
// Two M3 screws from INSIDE the case, through the wall, into heat-set
// inserts in two pads on the arc's inner face; the wires pass through a
// neck between them. Positions are chosen against everything already on
// the wall and inside it (see checks.scad):
//   rivets every 15 deg at z=49, side vent slots 30..150 deg up to z=41.25,
//   front screw posts at 45 and 90 deg (r=106.67, z 45..57 with the cone),
//   the glass shelf from z=55 inward. Pads at 37.5 and 67.5 sit midway
//   between rivets; the neck at 52.5 likewise.
pad_a    = [37.5, 67.5];
pad_z    = 49;
pad_d    = 8;
pad_insert_d = 4.0;   // M3 heat-set insert, as everywhere else in the case
pad_insert_h = 6;
pad_into = 1.5;       // how far each pad stands into the arc's cavity (6 mm of boss for an M3x5 insert)
wire_a   = 52.5;
wire_z   = 50;
wire_d   = 7;         // nine thin wires, passed through before soldering
neck_d   = 12;
screw_clear = 3.4;

// ---------- the back cover ----------
cover_t   = 2.5;
cover_lip = 2.0;      // locating lip into the cavity
cover_screw_pilot = 2.2;   // M2.5 self-tapping

// ---------- the knob (printed) ----------
knob_cap_d  = 18;
knob_cap_h  = 14;
knob_skirt_d = 24;
knob_skirt_h = 3;
knob_flutes = 18;
knob_shaft_d = 6.15;   // 6 mm D shaft
knob_shaft_flat = 4.6; // across the flat
knob_bore_h = 12;

// ---------- the jewel lens (printed in clear or translucent filament) ----------
jewel_d      = 16;
jewel_flange_d = 16.6;
jewel_flange_t = 1.2;
jewel_shank_d  = 11.9;
jewel_shank_h  = pod_face_t + 0.4;
led_d          = 5.1;   // 5 mm RGB LED, pushed into the shank

// ============================================================
// helpers
// ============================================================
function polar(r, a) = [r*cos(a), r*sin(a)];

// the arc's outline, seen from the front: a band between the two radii,
// with round ends
module pod_outline2d(inset = 0) {
    r0 = pod_r_in + inset;  r1 = pod_r_out - inset;  rc = pod_w/2 - inset;
    union() {
        intersection() {
            difference() { circle(r = r1, $fn = 720); circle(r = r0, $fn = 720); }
            polygon([[0, 0], polar(400, pod_a0), polar(400, (pod_a0 + pod_a1)/2), polar(400, pod_a1)]);
        }
        translate(polar(pod_r_mid, pod_a0)) circle(r = rc, $fn = 96);
        translate(polar(pod_r_mid, pod_a1)) circle(r = rc, $fn = 96);
    }
}

// a radial cylinder at angle a, height z, from radius r0 to r1
module radial_cyl(a, z, d, r0, r1) {
    rotate([0, 0, a]) translate([r0, 0, z]) rotate([0, 90, 0]) cylinder(d = d, h = r1 - r0, $fn = 32);
}

// a teardrop along the radius, point towards +Z, so a hole in a wall that is
// printed upright prints clean. point = -1 turns it towards -Z, for the arc,
// which prints face down (2026-10-29).
module radial_teardrop(a, z, d, r0, r1, point = 1) {
    rotate([0, 0, a]) translate([r0, 0, z]) rotate([0, 90, 0])
        linear_extrude(height = r1 - r0)
            rotate([0, 0, point > 0 ? 180 : 0]) hull() { circle(d = d, $fn = 32); translate([d/2*sqrt(2)/1.0, 0]) circle(d = 0.01); }
}

// tangential lettering on the face, centred on angle a
module label2d(a, s) {
    rotate([0, 0, a - 90]) translate([0, label_r])
        offset(delta = label_bold)
            text(s, size = label_size, font = label_font, halign = "center", valign = "center", spacing = label_spacing);
}

// ============================================================
// the arc
// ============================================================
module pod() {
    difference() {
        union() {
            difference() {
                translate([0, 0, pod_z0]) linear_extrude(height = pod_z1 - pod_z0) pod_outline2d();
                // the cavity, open at the back for the cover
                translate([0, 0, pod_z0 - 1]) linear_extrude(height = pod_z1 - pod_face_t - pod_z0 + 1) pod_outline2d(pod_wall);
            }
            // pads and neck reach across the gap and land on the drum; kept
            // in front of the back, where the cover goes. The neck is a
            // teardrop pointing at the face (2026-10-29): the arc prints face
            // down, and the round neck's underside, standing 2 mm off the
            // wall, took support.
            intersection() {
                union() {
                    for (a = pad_a) radial_cyl(a, pad_z, pad_d, R_case - 1, pod_r_in + pod_wall + pad_into);
                    // The neck runs 0.01mm past the arc's inner wall
                    // (2026-10-29). Its flat end stopped on the wall's inner
                    // face, which is round, so the two touched along one
                    // line, and the arc's mesh had edges there that a slicer
                    // reports as non-manifold.
                    radial_teardrop(wire_a, wire_z, neck_d, R_case - 1, pod_r_in + pod_wall + 0.01);
                }
                translate([-200, -200, pod_z0]) cube([400, 400, 100]);
            }
            // bosses for the cover's two screws, in the round ends
            for (a = [pod_a0, pod_a1]) translate(concat(polar(pod_r_mid, a), [pod_z0]))
                cylinder(d = 7, h = pod_z1 - pod_face_t - pod_z0, $fn = 32);
        }
        // the drum itself, so the pads and neck seat on its curve
        translate([0, 0, pod_z0 - 2]) cylinder(r = R_case, h = 60, $fn = 720);
        // insert holes in the pads, from the drum side
        for (a = pad_a) radial_cyl(a, pad_z, pad_insert_d, R_case - 2, R_case + pad_insert_h);
        // the wire hole, a teardrop pointing at the back, so its roof prints
        // clean face down (2026-10-29: it was round, and took support). Its
        // tip is cut flat 1.2 mm short of the back, so the wall there stays
        // 1.2 mm; the flat is a 1.3 mm bridge.
        intersection() {
            radial_teardrop(wire_a, wire_z, wire_d, R_case - 2, pod_r_in + pod_wall + 1, -1);
            translate([-200, -200, pod_z0 + 1.2]) cube([400, 400, 100]);
        }
        // the controls
        translate(concat(polar(ctl_r, lamp_a), [pod_z1 - pod_face_t - 1])) cylinder(d = lamp_hole, h = pod_face_t + 2, $fn = 64);
        translate(concat(polar(ctl_r, button_a), [pod_z1 - pod_face_t - 1])) cylinder(d = button_hole, h = pod_face_t + 2, $fn = 64);
        translate(concat(polar(ctl_r, knob_a), [pod_z1 - pod_face_t - 1])) {
            cylinder(d = enc_hole, h = pod_face_t + 2, $fn = 48);
            cylinder(d = enc_relief, h = 1 + pod_face_t - enc_panel, $fn = 48);   // thin the face from inside
        }
        // the lettering, sunk into the face for the second colour
        translate([0, 0, pod_z1 - label_depth]) linear_extrude(height = label_depth + 1) inlay2d();
        // pilot holes for the cover screws
        for (a = [pod_a0, pod_a1]) translate(concat(polar(pod_r_mid, a), [pod_z0 - 1])) cylinder(d = cover_screw_pilot, h = 12, $fn = 24);
    }
}

// what is inlaid in the second colour: the lettering, and a rivet dot in each
// round end, echoing the drum's rivets (flat, because the arc prints face down)
module inlay2d() {
    labels2d();
    for (a = [pod_a0, pod_a1]) translate(polar(pod_r_mid, a)) circle(d = 3.6, $fn = 32);
}

// the lettering alone, for its checks
module labels2d() {
    for (l = labels) label2d(l[0], l[1]);
}

// the lettering as its own solid, for a second filament
module pod_text() {
    translate([0, 0, pod_z1 - label_depth]) linear_extrude(height = label_depth) inlay2d();
}

// The lettering test coupon (2026-10-31): a lettering_coupon_t slice of the
// arc's face round each word, cut from the arc itself, with its lettering.
// Like the plate's and the cover's coupons (in the retro file), a few
// minutes' print to tune the slicer before the 2.5-hour arc.
module coupon2d() intersection() { pod_outline2d(); for (l = labels) offset(r = 3) hull() label2d(l[0], l[1]); }
module test_lettering_arc() intersection() {
    pod();
    translate([0, 0, pod_z1 - lettering_coupon_t]) linear_extrude(height = lettering_coupon_t + 1) coupon2d();
}
module test_lettering_arc_text() translate([0, 0, pod_z1 - label_depth]) linear_extrude(height = label_depth) labels2d();

// the flat cover that closes the arc's back
module pod_cover() {
    difference() {
        union() {
            translate([0, 0, pod_z0 - cover_t]) linear_extrude(height = cover_t) pod_outline2d();
            translate([0, 0, pod_z0]) linear_extrude(height = cover_lip) difference() { pod_outline2d(pod_wall + 0.25); pod_outline2d(pod_wall + 1.6); }
        }
        for (a = [pod_a0, pod_a1]) translate(concat(polar(pod_r_mid, a), [pod_z0 - cover_t - 1])) {
            cylinder(d = 2.8, h = cover_t + cover_lip + 2, $fn = 24);
            cylinder(d1 = 5.6, d2 = 2.8, h = 1.4 + 1, $fn = 24);     // countersink
        }
        // round the screw bosses, and round the two pads where they stand into the cavity
        for (a = [pod_a0, pod_a1]) translate(concat(polar(pod_r_mid, a), [pod_z0 - 0.01])) cylinder(d = 7.6, h = cover_lip + 1, $fn = 32);
        for (a = pad_a) radial_cyl(a, pad_z, pad_d + 1.2, R_case - 2, pod_r_in + pod_wall + pad_into + 0.6);
    }
}

// ============================================================
// the shell: the retro shell with the arc's three holes
// ============================================================
module shell_dials() {
    difference() {
        shell();
        for (a = pad_a) radial_cyl(a, pad_z, screw_clear, R_case - wall - 2, R_case + 1);
        radial_teardrop(wire_a, wire_z, wire_d, R_case - wall - 2, R_case + 1);
    }
}

// ============================================================
// the knob and the lens
// ============================================================
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

// ============================================================
// pictures
// ============================================================
c_body  = "#7A877D";   // instrument grey-green
c_trim  = "#26292A";
c_knob  = "#1B1C1D";
c_label = "#E9E2CC";
c_chrome = "#B9BEC2";

// the screen, for the picture only: a dark scope with rings and a sweep, just
// under the glass's front face, where front_stack_placed() puts it
module screen_picture() {
    translate([0, 0, shell_depth + glass_thickness - 0.6]) {
        color("#08140E") cylinder(d = panel_diameter - 1, h = 0.5, $fn = 180);
        color("#2F7A4A") for (r = [30, 60, 89]) translate([0, 0, 0.5]) difference() { cylinder(r = r, h = 0.15, $fn = 180); translate([0, 0, -0.1]) cylinder(r = r - 0.6, h = 0.4, $fn = 180); }
        color("#3FAF66", 0.9) translate([0, 0, 0.55]) rotate_extrude(angle = 38, $fn = 180) square([89, 0.12]);
        color("#9CFFB8") for (p = [[30, 22], [-41, 50], [55, -35], [-20, -62], [70, 40]]) translate([p[0], p[1], 0.7]) cylinder(d = 3, h = 0.2, $fn = 16);
    }
}

module controls_in_place() {
    // knob on its encoder shaft, standing off the face by the nut
    color(c_knob) translate(concat(polar(ctl_r, knob_a), [pod_z1 + 1.5])) knob();
    // button: a chrome bezel and a flat cap
    color(c_chrome) translate(concat(polar(ctl_r, button_a), [pod_z1])) {
        cylinder(d = 14, h = 1.6, $fn = 64);
        cylinder(d = 10, h = 2.4, $fn = 64);
    }
    // the jewel
    color("#6CFF8E", 0.85) translate(concat(polar(ctl_r, lamp_a), [pod_z1])) jewel();
    color(c_label) pod_text();
}

// The retainer and trim are placed by the retro file's front_stack_placed()
// (2026-10-29), so the pictures show the trim where it is built.
module case_dials_assembled() {
    color(c_body) shell_dials();
    color(c_trim) front_stack_placed("retainer");
    screen_picture();
    color(c_trim) front_stack_placed("trim");
    color(c_body) pod();
    color(c_body) pod_cover();
    controls_in_place();
}

// the case in its stand, posed as on a desk (front towards -Y)
module in_stand() {
    color("#3D4640") stand();
    translate([0, 0, base_h + cradle_od/2 - 3]) rotate([90 - stand_angle, 0, 0]) translate([0, 0, -shell_depth/2])
        case_dials_assembled();
}

if (dpart == "none") {}   // for checks.scad, which includes this file
else if (dpart == "shell_dials") shell_dials();
// print orientation: the arc and its lettering face down (the lettering is
// the first 0.6 mm), the cover flat, the lens on its shank
else if (dpart == "pod_print") translate([0, 0, pod_z1]) rotate([180, 0, 0]) pod();
else if (dpart == "pod_text_print") translate([0, 0, pod_z1]) rotate([180, 0, 0]) pod_text();
else if (dpart == "coupon_print") translate([0, 0, pod_z1]) rotate([180, 0, 0]) test_lettering_arc();
else if (dpart == "coupon_text_print") translate([0, 0, pod_z1]) rotate([180, 0, 0]) test_lettering_arc_text();
else if (dpart == "pod_cover_print") translate([0, 0, -(pod_z0 - cover_t)]) pod_cover();
else if (dpart == "jewel_print") translate([0, 0, jewel_shank_h]) jewel();
else if (dpart == "pod") pod();
else if (dpart == "pod_cover") pod_cover();
else if (dpart == "pod_text") pod_text();
else if (dpart == "knob") knob();
else if (dpart == "jewel") jewel();
else if (dpart == "in_stand") in_stand();
else if (dpart == "arc_closeup") { color(c_body) pod(); controls_in_place(); color(c_body) intersection() { shell_dials(); translate(concat(polar(130, 53), [0])) cylinder(r = 70, h = 80); } color(c_trim) intersection() { front_stack_placed("trim"); translate(concat(polar(130, 53), [0])) cylinder(r = 70, h = 90); } }
else if (dpart == "exploded") {
    color(c_body) shell_dials();
    screen_picture();
    color(c_trim) front_stack_placed("trim");
    translate([22, 22, 0]) { color(c_body) pod(); color(c_label) pod_text(); }
    translate([22, 22, -40]) color(c_body) pod_cover();
    translate([22, 22, 40]) {
        color(c_knob) translate(concat(polar(ctl_r, knob_a), [pod_z1 + 1.5])) knob();
        color("#6CFF8E", 0.85) translate(concat(polar(ctl_r, lamp_a), [pod_z1])) jewel();
    }
}
else case_dials_assembled();
