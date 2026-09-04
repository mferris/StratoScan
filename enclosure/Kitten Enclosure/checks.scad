// Fit checks for the kitten enclosure. Each target is an INTERSECTION that
// must come out empty. Lives beside the design on purpose: `use <>` resolves
// relative to the file that contains it, so a copy in /tmp silently finds
// nothing and every check "passes" against empty geometry.
use <kitten-enclosure.scad>
check = "none";
$fn = 96;   // match the design's resolution, or small interferences hide
outer_dia=223.34; shell_depth=56; wall=3; lip_height=6; shelf_h=2;
screw_r=106.67; n_screws=8; post_od=9;
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
// sanity: this MUST produce geometry. If it comes out empty the modules
// are not being found and every other result here is worthless.
else if (check=="canary") { shell(); }
