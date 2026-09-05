// Fit checks for the kitten enclosure. Each target is an INTERSECTION that
// must come out empty. Lives beside the design on purpose: `use <>` resolves
// relative to the file that contains it, so a copy in /tmp silently finds
// nothing and every check "passes" against empty geometry.
use <kitten-enclosure.scad>
check = "none";
// Must match the design's resolution or these validate different geometry
// from what gets exported. `use <>` imports modules and functions but NOT
// special variables, so the design's own settings do not come with them.
$fs = 0.4;
$fa = 0.5;
outer_dia=223.34; shell_depth=56; wall=3; lip_height=6; shelf_h=2;
screw_r=106.67; n_screws=8; post_od=9;
screw_clear_dia=3.4; nose_angle=270;
speaker_bracket_depth=15; speaker_d=45;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; arm_gap=26; arm_w=16;
base_h=16; stand_angle=18;

if (check=="ear_vs_post") {
  intersection() {
    ears_hollow();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), shell_depth-lip_height-1])
        cylinder(d=post_od+1, h=shelf_h+3); }
  }
}
// Does the inner-ear dish reach an insert post? That is the thing that
// actually matters. An earlier version of this check probed the whole rim
// band with a +0.01 fudge on its outer diameter, which reported a 0.06mm
// "interference" that was nothing but the 96-gon's flats dipping inside
// the true radius at the shared boundary -- a measurement artifact, not
// geometry. Posts stop at r=111.17, half a millimetre inside the wall, so
// probing them directly has real clearance and no boundary ambiguity.
else if (check=="recess_vs_post") {
  intersection() {
    inner_ear_recess();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), shell_depth-lip_height-1])
        cylinder(d=post_od, h=lip_height+2); }
  }
}
else if (check=="whisker_through") {
  r_mount = outer_dia/2 - wall - speaker_bracket_depth;
  zc = (shell_depth-speaker_d)/2 + speaker_d/2;
  intersection() {
    shell();
    translate([r_mount, 0, zc]) rotate([0,90,0]) cylinder(d=1.2, h=speaker_bracket_depth+wall+2, $fn=8);
  }
}
else if (check=="head_in_cradle") {
  arm_lift = base_h + cradle_od/2 - 3;
  intersection() {
    stand();
    translate([0,0,arm_lift]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2]) shell();
  }
}
// The tail now rests ON the right paw on purpose, so "must not touch" is
// the wrong assertion. What must not happen is the tail passing THROUGH the
// foot at pad height, which reads as one fused lump instead of a tail
// draped over a paw. So: it may meet the paw's upper half, but must not
// intrude into the lower half at all.
else if (check=="tail_over_paw") {
  intersection() {
    tail();
    intersection() {
      union() { paw(44); paw(-44); }
      translate([-200,-200,-50]) cube([400,400,61]);   // everything below z=11
    }
  }
}
// It should still be nowhere near the LEFT paw.
else if (check=="tail_vs_left_paw") {
  intersection() { tail(); paw(-44); }
}
// The tail must also stay under the cradled head, whose underside comes
// down to about z=27.
else if (check=="tail_vs_head") {
  arm_lift = base_h + cradle_od/2 - 3;
  intersection() {
    tail();
    translate([0,0,arm_lift]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2]) shell();
  }
}
// Paws must not reach the head either, now that they are taller.
else if (check=="paws_vs_head") {
  arm_lift = base_h + cradle_od/2 - 3;
  intersection() {
    union() { paw(44); paw(-44); }
    translate([0,0,arm_lift]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2]) shell();
  }
}
else if (check=="ears_vs_cradle") {
  arm_lift = base_h + cradle_od/2 - 3;
  intersection() {
    stand();
    translate([0,0,arm_lift]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2]) ears_solid();
  }
}
// The whiskers have to sit in the band between the nose and the screw holes
// either side of it. The first version of them missed by ninety degrees and
// printed before anyone noticed, so both ends of that band are now pinned.
else if (check=="whisker_vs_screws") {
  intersection() {
    whisker_grooves();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), -5])
        cylinder(d=screw_clear_dia, h=20); }
  }
}
else if (check=="whisker_vs_nose") {
  intersection() { whisker_grooves(); nose(); }
}
// ...and that they are actually beside the NOSE. An intersection can only
// prove two things do not touch; it cannot prove a feature is in the right
// place, which is exactly how six grooves reached a printed part on the
// wrong side of the face. This one is a difference: the grooves must lie
// entirely within a wedge centred on the nose, so it comes out empty only
// while every one of them is where it belongs.
else if (check=="whisker_off_nose") {
  // 270 is written out rather than taken from nose_angle on purpose. Sharing
  // the variable makes this vacuous: move nose_angle and the wedge follows
  // the grooves, so the two stay aligned and the check passes wherever they
  // both went. This number is where nose() actually puts itself --
  // translate([0, -screw_r, ..]), straight down -- so if the whiskers ever
  // leave the nose again, they leave the wedge too.
  difference() {
    whisker_grooves();
    rotate([0,0,270-45]) rotate_extrude(angle=90)
      translate([0,-10]) square([200,30]);
  }
}
// sanity: this MUST produce geometry. If it comes out empty the modules
// are not being found and every other result here is worthless.
else if (check=="canary") { shell(); }
