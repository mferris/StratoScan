// Fit checks for the two-tone kitten enclosure. Each target is an
// INTERSECTION (or a DIFFERENCE) that must come out with no real volume.
//
// Not "empty": run these with `sh run-checks.sh`, which measures the volume
// of what each produces. Wherever two parts share a surface -- which is the
// whole point of the colour split -- a boolean leaves a zero-thickness film
// along that boundary, with thousands of facets and no volume. Judging by
// facet count calls a correct model broken.
//
// Lives beside the design on purpose: `use <>` resolves
// relative to the file that contains it, so a copy in /tmp silently finds
// nothing and every check "passes" against empty geometry.
use <kitten-enclosure-twotone.scad>
check = "none";
// Must match the design's resolution or the checks validate different
// geometry from what gets exported. This said $fn=96 while the design moved
// to adaptive $fa/$fs, and the giveaway was the canary reporting volume to
// the milligram across a resolution change that should have moved it.
$fs = 0.4;
$fa = 0.5;
outer_dia=223.34; shell_depth=56; wall=3; lip_height=6; shelf_h=2;
screw_r=106.67; n_screws=8; post_od=9;
screw_clear_dia=3.4; nose_angle=270; front_trim_h=4;
back_plate_t=3; ant_mount_y=88; ant_mount_standoff=26; ant_socket_dia=33;
speaker_bracket_depth=15; speaker_d=45;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; arm_gap=26; arm_w=16;
base_h=16; stand_angle=18;
// Restated because `use <>` imports modules and functions but NOT variables.
// These must track the design file: paws and tail are bigger here than in
// the single-colour version, and a stale value here would check the old
// geometry and pass.
paw_x=46; paw_h=18;

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
      union() { paw(paw_x); paw(-paw_x); }
      // the paw's lower half, which scales with the paw
      translate([-200,-200,-50]) cube([400,400,50 + paw_h*0.7]);
    }
  }
}
// It should still be nowhere near the LEFT paw.
else if (check=="tail_vs_left_paw") {
  intersection() { tail(); paw(-paw_x); }
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
    union() { paw(paw_x); paw(-paw_x); }
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
// The five colour bodies must add back up to exactly the one-piece stand,
// with nothing left over and nothing missing. Both directions are checked
// because each catches a different mistake: material_lost finds a region no
// part claims (a hole in the print), material_gained finds a region two
// parts both claim (an overlap, where which colour wins depends on the
// slicer's load order).
else if (check=="material_lost") {
  difference() { stand(); stand_colour_parts(); }
}
else if (check=="material_gained") {
  difference() { stand_colour_parts(); stand(); }
}
// Overlap between any two coloured bodies, checked pairwise rather than
// against the whole, since a body cannot overlap itself and the union above
// would hide a mutual overlap inside the total.
else if (check=="paws_vs_toes")     { intersection() { part_stand_paws(); part_stand_toes(); } }
else if (check=="paws_vs_tail")     { intersection() { part_stand_paws(); part_stand_tail(); } }
else if (check=="body_vs_paws")     { intersection() { part_stand_body(); part_stand_paws(); } }
else if (check=="tail_vs_tip")      { intersection() { part_stand_tail(); part_stand_tail_tip(); } }
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
// The hole under the nose must not be cut at all. Proving a hole is ABSENT
// needs a difference, not an intersection: a probe filling the hole's
// footprint through the bezel, minus the trim, must come out empty -- there
// is no void for it to find.
else if (check=="nose_screw_removed") {
  // Kept strictly inside the bezel's own thickness. A probe that overhangs
  // the part finds the air beyond it and reports that as a hole -- the first
  // version of this reached 1mm below the rabbet and "failed" on 11mm3 of
  // nothing.
  difference() {
    translate([screw_r*cos(270), screw_r*sin(270), 0.2])
      cylinder(d=screw_clear_dia - 0.2, h=front_trim_h - 0.4);
    front_trim();
  }
}
// ...and the paired positive control, in the canary group below, because an
// empty result above would also be what a probe in the wrong place, or a
// front_trim() that failed to evaluate, produces. This one must find a real
// hole at a normal position.
else if (check=="other_screws_present") {
  difference() {
    translate([screw_r*cos(225), screw_r*sin(225), 0.2])
      cylinder(d=screw_clear_dia - 0.2, h=front_trim_h - 0.4);
    front_trim();
  }
}
// ---- Removable back plate --------------------------------------------
// The antenna must clear the head. This is the check the mount was sized
// from rather than styled to: an envelope the diameter of the antenna,
// swept from the socket, intersected with the head and its ears. At a 12mm
// standoff it fouls the top rim by 876mm3 and at 18mm by 205mm3; it comes
// clear at 24, and the mount stands off 26.
else if (check=="antenna_clears_head") {
  intersection() {
    translate([0, ant_mount_y, -back_plate_t - ant_mount_standoff])
      rotate([stand_angle,0,0]) rotate([-90,0,0])
        translate([0,0,-6]) cylinder(d=ant_socket_dia, h=220);
    union() { shell(); ears_solid(); }
  }
}
// The mount must not show from the front. Anything of it outside the head's
// own outline would appear around the edge of the face.
else if (check=="mount_hidden") {
  intersection() {
    antenna_mount();
    difference() {
      cylinder(d=400, h=300, center=true);
      cylinder(d=outer_dia, h=300, center=true);
    }
  }
}
// The plate must meet the shell without either intruding on the other.
else if (check=="plate_vs_shell") {
  intersection() { back_plate(); shell(); }
}
// ...and must not foul the cradle once the head is seated in it.
else if (check=="mount_vs_stand") {
  arm_lift = base_h + cradle_od/2 - 3;
  intersection() {
    stand();
    translate([0,0,arm_lift]) rotate([90-stand_angle,0,0])
      translate([0,0,-shell_depth/2]) back_plate();
  }
}
// All eight insert holes must be open bores. The speaker brackets reach the
// wall at 0 and 180 degrees, right where two of the posts are, so a hole
// subtracted inside the post module gets unioned shut again -- this is the
// check that caught it needing to be drilled after the union instead.
else if (check=="back_inserts_open") {
  difference() {
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), 0.5]) cylinder(d=3.6, h=6); }
    shell();
  }
}
// sanity: this MUST produce geometry. If it comes out empty the modules
// are not being found and every other result here is worthless.
else if (check=="canary") { shell(); }
