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
back_plate_t=3; ant_mount_y=88; ant_stub_len=30; ant_barrel_len=14; ant_socket_dia=33; ant_socket_depth=6;
speaker_bracket_depth=15; speaker_d=45;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; arm_gap=26; arm_w=16;
base_h=16; stand_angle=18;
// Restated because `use <>` imports modules and functions but NOT variables.
// These must track the design file: paws and tail are bigger here than in
// the single-colour version, and a stale value here would check the old
// geometry and pass.
paw_x=46; paw_h=18;
n_toes=4; toe_dia=13.5; toe_splay=21; claw_len=6.5;
ant_conn_dia=9.15; ant_flange_t=4;
// The back-plate features added with the locating lip. Restated here for the
// same reason as everything above: `use <>` brings in modules, never values.
back_lip_h=4; back_lip_t=2; back_lip_gap=0.35; back_lip_skip=9;
back_post_h=9; ant_bolt_pcd=30; n_ant_bolts=3; ant_flange_d=40;
usbc_cut_pos=[60,-14]; usbc_cut_w=11.0; usbc_cut_h=6.5; usbc_screw_pitch=24.0;
mount_hole_x=58; mount_hole_y=49;

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
// The claws are a colour body like any other, so they overlap the toes they
// grow out of by colour_overlap and must not share a surface with them.
else if (check=="claws_vs_toes")    { intersection() { part_stand_toes(); part_stand_claws(); } }
// ...and they must actually STAND OFF the toes. A claw entirely buried in
// its toe still passes every seam and volume check above while being
// invisible on the print -- which is exactly what the grooves-as-nails
// problem looked like. Positive control: material must exist forward of the
// toes' own envelope.
else if (check=="claws_stand_proud") {
  difference() {
    union() { part_stand_claws(); }
    union() { paw_toes(paw_x); paw_toes(-paw_x); paw_pad(paw_x); paw_pad(-paw_x); }
  }
}
// A claw that reaches the desk plane would carry the stand's weight on four
// points per paw and rock. Nothing below z=0.6.
else if (check=="claws_off_the_desk") {
  intersection() {
    part_stand_claws();
    translate([-300,-300,-300]) cube([600,600,300.6]);
  }
}
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
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
      rotate([stand_angle,0,0]) rotate([-90,0,0])
        translate([0,0,ant_barrel_len - ant_socket_depth])
          cylinder(d=ant_socket_dia, h=220);
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
// The bolt-on mount must sit flat on the plate without either intruding on
// the other, and its bolt pattern must line up with the plate's.
else if (check=="mount_vs_plate") {
  intersection() { antenna_mount(); back_plate(); }
}
// sanity: this MUST produce geometry. If it comes out empty the modules
// are not being found and every other result here is worthless.
else if (check=="canary") { shell(); }

// ---- the locating lip -------------------------------------------------
// The lip must do three things, and each is checked separately because a
// single "does the plate fit" test passes just as happily when the lip is
// missing altogether.

// 1. It must EXIST. Positive control: without this, the two tests below
//    both pass against nothing, which is what a deleted lip looks like.
if (check=="lip_present") {
  intersection() {
    back_plate();
    difference() {
      cylinder(d=outer_dia, h=back_lip_h);          // above the plate's inner face
      cylinder(d=outer_dia - 2*wall - 2*back_lip_gap - 2*back_lip_t - 1,
               h=back_lip_h*3, center=true);
    }
  }
}

// 2. It must not touch the eight insert posts. A continuous ring at bore
//    diameter runs straight through all eight of them.
if (check=="lip_clears_posts") {
  intersection() {
    back_plate();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), 0])
        cylinder(d=post_od, h=back_post_h); }
  }
}

// 3. It must sit INSIDE the bore, not proud of it -- a lip larger than the
//    bore does not locate anything, it just stops the plate seating.
if (check=="lip_inside_bore") {
  difference() {
    intersection() {
      back_plate();
      translate([0,0,0.1]) cylinder(d=outer_dia, h=back_lip_h - 0.2);
    }
    translate([0,0,-1]) cylinder(d=outer_dia - 2*wall - 2*back_lip_gap + 0.01,
                                 h=back_lip_h + 2);
  }
}

// ---- vents clear of the antenna mount ---------------------------------
// The whole point of moving the grille: no vent may lie under the mount's
// flange, where it vents into the back of a solid disc.
// Testing "every hole under the flange" is wrong and the first version of
// this did exactly that: it counted the antenna cable bore and the three
// bolt holes -- 297mm3 of openings that are meant to be under the mount,
// since that is how the coax and the screws get through. The question is
// only whether GRILLE holes are under it, so the probe is the grilles
// themselves and nothing else.
if (check=="vents_clear_of_mount") {
  intersection() {
    translate([0,0,-back_plate_t]) { intake_grille(); fan_grille(); }
    translate([0, ant_mount_y, -back_plate_t - 1])
      cylinder(d=ant_flange_d, h=back_plate_t + 2);
  }
}

// Paired positive control. An empty result above is also what a mistyped
// grille module or a flange in the wrong place produces, so the SAME probe
// at the grille's OLD position has to find the overlap that was reported.
if (check=="vents_were_under_mount") {
  intersection() {
    translate([0, 68 - (-68), 0])         // shift the moved grille back to y=+68
      translate([0,0,-back_plate_t]) fan_grille();
    translate([0, ant_mount_y, -back_plate_t - 1])
      cylinder(d=ant_flange_d, h=back_plate_t + 2);
  }
}

// ---- the single USB-C window ------------------------------------------
// Positive control: the window must actually be cut. An empty result here is
// also what a mistyped position produces.
if (check=="usbc_open") {
  intersection() {
    difference() {
      translate([0,0,-back_plate_t]) cylinder(d=outer_dia, h=back_plate_t);
      back_plate();
    }
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      cylinder(d=usbc_screw_pitch + 6, h=back_plate_t + 2);
  }
}

// ...and it must not run into the Pi standoffs on the same face.
if (check=="usbc_clears_standoffs") {
  intersection() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      cylinder(d=usbc_screw_pitch + 6, h=back_plate_t + 20);
    for (x=[-mount_hole_x/2, mount_hole_x/2])
      for (y=[-mount_hole_y/2, mount_hole_y/2])
        translate([x,y,0]) cylinder(d=7, h=8);
  }
}

// ---- antenna insert bosses --------------------------------------------
// Positive control: each boss must be bored for its insert. Solid bosses
// would look identical from outside and take no insert at all.
if (check=="ant_inserts_open") {
  difference() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), 0])
        cylinder(d=ant_bolt_d_probe(), h=back_post_h); }
    back_plate();
  }
}
function ant_bolt_d_probe() = 3.0;

// ---- can the connector actually get through? --------------------------
// A 9.15mm plug gauge swept along the passage: down the antenna's axis from
// the socket floor, then straight out through the arm and the plate. It must
// touch nothing. This is the check the old design would have failed -- its
// bore was 9.0mm, and the socket floor met it at an angle besides.
if (check=="connector_passes") {
  intersection() {
    union() {
      translate([0, ant_mount_y, -back_plate_t - ant_stub_len - 1])
        cylinder(d=ant_conn_dia, h=ant_stub_len + back_plate_t + 2);
      hull() {
        translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
          cylinder(d=ant_conn_dia, h=0.01);
        ant_axis_frame()
          translate([0, 0, ant_barrel_len - ant_socket_depth - 0.01])
            cylinder(d=ant_conn_dia, h=0.02);
      }
    }
    union() { antenna_mount(); back_plate(); }
  }
}
// Paired positive control: the SAME gauge oversized to 13mm -- wider than the
// 11mm bore -- must be caught. An empty result above is otherwise also what a
// gauge swept down the wrong axis produces.
if (check=="connector_gauge_works") {
  intersection() {
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len - 1])
      cylinder(d=13, h=ant_stub_len + back_plate_t + 2);
    union() { antenna_mount(); back_plate(); }
  }
}
