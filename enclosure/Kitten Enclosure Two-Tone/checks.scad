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
// the power fix's checks read these (restated, as below)
speaker_h=21; speaker_w=100;
// front heat-set inserts (restated): shelf top face, insert length, hole
fi_top = 57; fi_len = 5; fi_hole = 4.0;
// Must match the design's resolution or the checks validate different
// geometry from what gets exported. This said $fn=96 while the design moved
// to adaptive $fa/$fs, and the giveaway was the canary reporting volume to
// the milligram across a resolution change that should have moved it.
$fs = 0.4;
$fa = 0.5;
outer_dia=223.34; shell_depth=61; wall=3; lip_height=6; shelf_h=2;
screw_r=106.67; n_screws=8; post_od=9;
screw_clear_dia=3.4; nose_angle=270; front_trim_h=4;
back_plate_t=3; ant_mount_y=81; ant_stub_len=30; ant_barrel_len=14; ant_socket_dia=33; ant_socket_depth=8;
speaker_bracket_depth=15; speaker_d=45;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; arm_gap=26; arm_w=16;
base_h=16; stand_angle=18;
// Restated because `use <>` imports modules and functions but NOT variables.
// These must track the design file: paws and tail are bigger here than in
// the single-colour version, and a stale value here would check the old
// geometry and pass.
paw_x=46; paw_h=18;
n_toes=4; toe_dia=13.5; toe_splay=21; claw_len=6.5;
ant_conn_dia=9.15; ant_boss_dia=48; ant_socket_lead=1.2;
// Measured off the antenna: 31.25mm across the flared bottom, its widest
// point. ant_relief_* is the clear space under the socket floor for the
// connector, which is what was actually stopping the base from seating.
ant_base_dia=31.25; ant_relief_dia=18; ant_relief_h=4;
ant_cable_slot_w=7; ant_cable_exit_h=7.98; ant_flange_t=7; ant_flange_insert_d=5.5;

// The SMA bulkhead variant. Restated here for the same reason as everything
// above: `use <>` brings in modules, not variables, so a check that names one
// of these directly needs its own copy.
ant_sma_hole=6.5; ant_sma_panel_t=3; ant_sma_cavity=14; ant_twin_cover_t=3;
ant_sma_boss_d=22; ant_sma_boss_h=10; ant_sma_cavity_d=25;

// The back-plate features added with the locating lip. Restated here for the
// same reason as everything above: `use <>` brings in modules, never values.
back_lip_h=4; back_lip_t=2; back_lip_gap=0.35; back_lip_skip=9;
back_post_h=9; ant_bolt_pcd=30; n_ant_bolts=3; ant_flange_d=40;
// The USB-C window moved to [60,-51] on 2026-10-10 and this copy didn't,
// so usbc_open probed the old spot and failed from then (found 2026-10-13).
// Since 2026-10-29 it is the trigger board's socket's window, with a pocket
// for a plug's moulding and two insert holes beside it.
usbc_cut_pos=[60,-51]; usbc_cut_w=9.54; usbc_cut_h=3.86; usbc_cut_r=1.93; usbc_screw_pitch=24;
usbc_recess_w=14; usbc_recess_h=10; usbc_recess_r=2.5; usbc_recess_d=1.4; insert_hole_dia=4.0; usbc_insert_len=3;
usbc_bridge_layer=0.2;
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
if (check=="recess_vs_post") {
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

// ---- the SMA bulkhead mount -------------------------------------------
// Same three questions the socket mount has to answer -- does it stay off
// the plate, does it stay out of the cradle -- plus the one that is specific
// to this variant and the one most likely to be wrong.

// It must not intrude on the plate it bolts to.
else if (check=="sma_mount_vs_plate") {
  intersection() { antenna_mount_sma(); back_plate(); }
}
// It must not foul the cradle arms when the case is in its stand.
else if (check=="sma_mount_vs_stand") {
  intersection() {
    antenna_mount_sma();
    translate([0,0,base_h + cradle_od/2 - 3])
      rotate([90 - stand_angle,0,0])
        translate([0,0,-shell_depth/2]) stand();
  }
}
// THE ONE THAT MATTERS. The cavity behind the jack has to actually meet the
// cable bore, or the coax has nowhere to go: the jack threads into a sealed
// pocket. In preview that is invisible -- both volumes are cut, the part
// looks hollow, and the wall between them only exists in the print. This is
// a POSITIVE control: the two cut volumes must overlap.
else if (check=="sma_passage_joins") {
  intersection() {
    ant_axis_frame() translate([0,0,-6])
      cylinder(d=ant_sma_cavity, h=ant_sma_boss_h - ant_sma_panel_t + 6);
    ant_cable_bore(0);
  }
}
// The panel the jack's nut pulls against must still be there. The cable bore
// sweeps up to 6mm in this frame and the panel starts at 7; get that wrong
// and the bore eats the panel, leaving the jack nothing to clamp. POSITIVE
// control: material in the annulus around the hole.
else if (check=="sma_panel_present") {
  intersection() {
    antenna_mount_sma();
    ant_axis_frame() {
      difference() {
        translate([0,0,ant_sma_boss_h - ant_sma_panel_t])
          cylinder(d=ant_sma_boss_d, h=ant_sma_panel_t);
        translate([0,0,ant_sma_boss_h - ant_sma_panel_t - 1])
          cylinder(d=ant_sma_hole, h=ant_sma_panel_t + 2);
      }
    }
  }
}
// ...and the hole through it must be clear. POSITIVE control: a probe a
// little under the hole diameter survives the mount untouched.
else if (check=="sma_hole_open") {
  difference() {
    ant_axis_frame() translate([0,0,ant_sma_boss_h - ant_sma_panel_t - 0.5])
      cylinder(d=ant_sma_hole - 0.5, h=ant_sma_panel_t + 1);
    antenna_mount_sma();
  }
}

// The two-piece barrel, as a solid. A Ø13 x 25mm slug hanging off the panel
// underside stands in for the bulkhead's inner half plus the jumper mated
// onto it. It must fit in the void without touching the part.
//
// Pinned because the 25mm is an ESTIMATE from listings, not a measurement off
// the parts, and because a cavity a few mm short does not fail loudly -- the
// plug simply will not seat and the antenna ends up proud and crooked, which
// is discovered with a printed plate in hand.
else if (check=="sma_barrel_fits") {
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_sma_boss_h - ant_sma_panel_t - ant_sma_cavity_d])
        cylinder(d=13, h=ant_sma_cavity_d);
    antenna_mount_sma();
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
// ---- back-plate key (roadmap 5.6) --------------------------------------
// The plate must seat exactly one way. key_fits: correctly oriented, the key
// meets the plate with no volume. key_blocks_*: rotated by each of the other
// seven 45-degree steps -- every other position the eight posts allow -- the
// key must hit the plate. A key that blocked only some angles would still let
// it go in wrong, so each rotation is its own check.
else if (check=="key_fits") { intersection() { back_plate(); back_key(); } }
else if (check=="key_blocks_45")  { intersection() { rotate([0,0,45])  back_plate(); back_key(); } }
else if (check=="key_blocks_90")  { intersection() { rotate([0,0,90])  back_plate(); back_key(); } }
else if (check=="key_blocks_135") { intersection() { rotate([0,0,135]) back_plate(); back_key(); } }
else if (check=="key_blocks_180") { intersection() { rotate([0,0,180]) back_plate(); back_key(); } }
else if (check=="key_blocks_225") { intersection() { rotate([0,0,225]) back_plate(); back_key(); } }
else if (check=="key_blocks_270") { intersection() { rotate([0,0,270]) back_plate(); back_key(); } }
else if (check=="key_blocks_315") { intersection() { rotate([0,0,315]) back_plate(); back_key(); } }
// ---- no side slots ----------------------------------------------------
// The kitten vents through its hollow ears, open at the back; the side wall
// is plain. A probe where the last slot was (straight up, mid-depth) must
// find the full wall there, about 79mm3; a slot would take most of it.
else if (check=="top_wall_solid") {
  intersection() {
    shell();
    translate([-1.1, outer_dia/2 - wall, 29.25]) cube([2.2, wall, 12]);
  }
}
// ---- front heat-set inserts: plastic all round, holes open ---------------
// The front posts used to give an insert 2mm of plastic. Every M3x5 insert
// must now have a 1.75mm-thick ring of plastic all round it for its whole
// length (front_insert_len below the shelf's top face, z = 57)...
else if (check=="front_inserts_surrounded") {
  for (i = [0:n_screws-1]) { a = i*360/n_screws;
    difference() {
      translate([screw_r*cos(a), screw_r*sin(a), fi_top - fi_len])
        difference() { cylinder(d=8, h=fi_len); translate([0,0,-1]) cylinder(d=fi_hole + 0.5, h=fi_len + 2); }
      shell();
    } }
}
// ...and each hole is open for the insert (about 57mm3 each, 450 for eight).
else if (check=="front_insert_holes_open") {
  for (i = [0:n_screws-1]) { a = i*360/n_screws;
    difference() {
      translate([screw_r*cos(a), screw_r*sin(a), fi_top - fi_len]) cylinder(d=fi_hole - 0.2, h=fi_len);
      shell();
    } }
}
// ---- the twin mount (1090 + 978 MHz) ----------------------------------
// Same flange and bolts as the others, so the same two interference checks.
else if (check=="twin_vs_plate") {
  intersection() { antenna_mount_twin(); back_plate(); }
}
else if (check=="twin_vs_stand") {
  intersection() {
    antenna_mount_twin();
    translate([0,0,base_h + cradle_od/2 - 3])
      rotate([90 - stand_angle,0,0])
        translate([0,0,-shell_depth/2]) stand();
  }
}
else if (check=="twin_vs_stand_11") {
  intersection() {
    antenna_mount_twin([11, 11]);
    translate([0,0,base_h + cradle_od/2 - 3])
      rotate([90 - stand_angle,0,0])
        translate([0,0,-shell_depth/2]) stand();
  }
}
// The twin mount is two parts and nothing is threaded round a corner, so the
// route is checked leg by leg: a plug beside a cable straight down the bore,
// the jack's hex body standing in each slot, the cover in its seat.
else if (check=="twin_bore_straight") {
  intersection() { antenna_mount_twin(); ant_twin_bore_probe(); }
}
else if (check=="twin_slot_takes_jack") {
  intersection() { antenna_mount_twin(); ant_twin_jack_probe(); }
}
else if (check=="twin_cover_fits") {
  intersection() { antenna_mount_twin(); ant_twin_cover_placed(); }
}
// POSITIVE controls: the channel is open air, the cover really sits in its
// seat (pushed 2mm into the body it must hit), and thin rods pass through
// the cover's holes into open insert holes.
else if (check=="twin_channel_open") {
  difference() { ant_twin_channel_probe(); antenna_mount_twin(); }
}
else if (check=="twin_cover_seats") {
  intersection() {
    antenna_mount_twin();
    ant_axis_frame() translate([0, ant_twin_seat([8, 8]) + ant_twin_cover_t - 2, 0]) rotate([90, 0, 0]) antenna_mount_twin_cover();
  }
}
else if (check=="twin_cover_screws_open") {
  difference() { ant_twin_screw_probes(); union() { antenna_mount_twin(); ant_twin_cover_placed(); } }
}
// Both whips, swept 220mm up from their towers, must miss the case.
else if (check=="twin_antennas_clear_case") {
  intersection() { ant_twin_envelopes(); shell(); }
}
// POSITIVE controls: the panels the jacks clamp to are there, and the jack
// holes through them are open.
else if (check=="twin_panels_present") {
  intersection() { antenna_mount_twin(); ant_twin_panel_ring(); }
}
else if (check=="twin_holes_open") {
  difference() { ant_twin_hole_probe(); antenna_mount_twin(); }
}
// ---- the plate's top screw vs the antenna mount (2026-10-07) ----------
// With the flange at y=88 it reached y=108 and covered the plate's top
// screw at (0, screw_r): the plate could not be screwed on with the mount
// fitted. A column the width of the screw head plus a hex key's wobble,
// from the plate's outer face out past the mount, must meet no mount.
else if (check=="top_screw_clear_of_twin") {
  intersection() { antenna_mount_twin(); translate([0, screw_r, -back_plate_t - 80]) cylinder(d=8, h=80); }
}
else if (check=="top_screw_clear_of_sma") {
  intersection() { antenna_mount_sma(); translate([0, screw_r, -back_plate_t - 80]) cylinder(d=8, h=80); }
}
else if (check=="top_screw_clear_of_puck") {
  intersection() { antenna_mount(); translate([0, screw_r, -back_plate_t - 80]) cylinder(d=8, h=80); }
}
// POSITIVE control: the same column against the flange where it used to be.
else if (check=="top_screw_was_under_mount") {
  intersection() {
    translate([0, 88, -back_plate_t - 7]) cylinder(d=ant_flange_d, h=7);
    translate([0, screw_r, -back_plate_t - 80]) cylinder(d=8, h=80);
  }
}
// POSITIVE control for twin_antennas_clear_case: the same envelopes moved
// 60mm down the axis AND 40mm toward the case (they start behind the plate
// and lean away from it, so down alone never reaches the shell) do hit it.
else if (check=="twin_antennas_probe_works") {
  intersection() {
    for (s = [-1, 1]) ant_twin_frame(s) translate([0, -40, 32 - 60]) cylinder(d=15, h=220);
    shell();
  }
}
// "Open" means the probes meet no body at all, not just that most of each
// survives: the complements of twin_channel_open and twin_cover_screws_open.
else if (check=="twin_channel_probe_clear") {
  intersection() { ant_twin_channel_probe(); antenna_mount_twin(); }
}
else if (check=="twin_screw_probes_clear") {
  intersection() { ant_twin_screw_probes(); union() { antenna_mount_twin(); ant_twin_cover_placed(); } }
}
else if (check=="twin_barrel_through_panel") {
  intersection() { antenna_mount_twin(); ant_twin_barrel_probe(); }
}
else if (check=="twin_cover_pads_clear_jack") {
  intersection() { ant_twin_cover_placed(); ant_twin_jack_probe(); }
}
// ---- the 11mm style of the twin mount -----------------------------------
// The default style above is for 8mm jack bodies; every check that depends
// on the jack's size is repeated for the 11mm style. AF11 = [11, 11].
else if (check=="twin_slot_takes_jack_11") {
  intersection() { antenna_mount_twin([11, 11]); ant_twin_jack_probe([11, 11]); }
}
else if (check=="twin_barrel_through_panel_11") {
  intersection() { antenna_mount_twin([11, 11]); ant_twin_barrel_probe([11, 11]); }
}
else if (check=="twin_cover_fits_11") {
  intersection() { antenna_mount_twin([11, 11]); ant_twin_cover_placed([11, 11]); }
}
else if (check=="twin_cover_pads_clear_jack_11") {
  intersection() { ant_twin_cover_placed([11, 11]); ant_twin_jack_probe([11, 11]); }
}
else if (check=="twin_vs_plate_11") {
  intersection() { antenna_mount_twin([11, 11]); back_plate(); }
}
else if (check=="twin_channel_probe_clear_11") {
  intersection() { ant_twin_channel_probe([11, 11]); antenna_mount_twin([11, 11]); }
}
else if (check=="twin_screw_probes_clear_11") {
  intersection() { ant_twin_screw_probes([11, 11]); union() { antenna_mount_twin([11, 11]); ant_twin_cover_placed([11, 11]); } }
}
else if (check=="top_screw_clear_of_twin_11") {
  intersection() { antenna_mount_twin([11, 11]); translate([0, screw_r, -back_plate_t - 80]) cylinder(d=8, h=80); }
}
else if (check=="twin_bore_straight_11") {
  intersection() { antenna_mount_twin([11, 11]); ant_twin_bore_probe(); }
}
// POSITIVE controls for the 11mm style
else if (check=="twin_channel_open_11") {
  difference() { ant_twin_channel_probe([11, 11]); antenna_mount_twin([11, 11]); }
}
else if (check=="twin_cover_seats_11") {
  intersection() {
    antenna_mount_twin([11, 11]);
    ant_axis_frame() translate([0, ant_twin_seat([11, 11]) + ant_twin_cover_t - 2, 0]) rotate([90, 0, 0]) antenna_mount_twin_cover([11, 11]);
  }
}
else if (check=="twin_cover_screws_open_11") {
  difference() { ant_twin_screw_probes([11, 11]); union() { antenna_mount_twin([11, 11]); ant_twin_cover_placed([11, 11]); } }
}
else if (check=="twin_panels_present_11") {
  intersection() { antenna_mount_twin([11, 11]); ant_twin_panel_ring([11, 11]); }
}
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


// The holes for the trigger board mount's two inserts sit 24 mm apart since
// 2026-10-29, outside the moulding's pocket. (They were screw holes 16.5 mm
// apart, for the old connector, with 1.6 mm of plate between them and its
// window.) Grow the pocket by 1.6 mm all round and the insert holes must
// still miss it: at least 1.6 mm of plate, four perimeters at a 0.4 mm
// nozzle, between them.
if (check=="usbc_inserts_clear_pocket") {
  intersection() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      linear_extrude(height = back_plate_t + 2)
        offset(r = 1.6) offset(r = usbc_recess_r) offset(delta = -usbc_recess_r)
          square([usbc_recess_w, usbc_recess_h], center = true);
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      for (sx = [-1, 1])
        translate([sx * usbc_screw_pitch/2, 0, 0])
          cylinder(d = insert_hole_dia, h = back_plate_t + 2);
  }
}
// Paired positive control: grow the pocket by 4 mm instead and the holes must
// now be caught, which shows the probe can find them at all.
if (check=="usbc_insert_probe_works") {
  intersection() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      linear_extrude(height = back_plate_t + 2)
        offset(r = 4) offset(r = usbc_recess_r) offset(delta = -usbc_recess_r)
          square([usbc_recess_w, usbc_recess_h], center = true);
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      for (sx = [-1, 1])
        translate([sx * usbc_screw_pitch/2, 0, 0])
          cylinder(d = insert_hole_dia, h = back_plate_t + 2);
  }
}
// The pocket in the outer face for a plug's moulding (2026-10-29: 14 x 10 and
// 1.4 deep round the trigger board's socket): open to usbc_recess_d from the
// outer face over its whole footprint (a probe there meets no plate)...
if (check=="usbc_recess_open") {
  intersection() {
    back_plate();
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 0.5])
      linear_extrude(height = usbc_recess_d + 0.45)
        offset(r = usbc_recess_r - 0.1) offset(delta = -usbc_recess_r)
          square([usbc_recess_w, usbc_recess_h], center = true);
  }
}
// ...and the web round the window is still there (a probe in it, between the
// window and the pocket's edge, finds plate): the pocket must never break
// through.
if (check=="usbc_recess_web") {
  intersection() {
    back_plate();
    translate([usbc_cut_pos[0] - 6, usbc_cut_pos[1] + usbc_cut_h/2 + 0.3, -back_plate_t + usbc_recess_d + 0.1])
      cube([12, 2.0, back_plate_t - usbc_recess_d - 0.2]);
  }
}
// A plug in the USB-C socket (as big as the pocket, 14 x 10, and 35 mm out of
// the plate with its strain relief) clears the stand, paws, tail and all,
// with the head leaning back in it...
if (check=="usbc_plug_clears_stand") {
  intersection() {
    stand();
    translate([0,0,base_h + cradle_od/2 - 3]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2])
      translate([usbc_cut_pos[0] - usbc_recess_w/2, usbc_cut_pos[1] - usbc_recess_h/2, -back_plate_t - 35])
        cube([usbc_recess_w, usbc_recess_h, 35]);
  }
}
// ...and the same probe, run on into the plate, does meet it (the probe is
// where the socket is).
if (check=="usbc_plug_probe_works") {
  intersection() {
    back_plate();
    translate([usbc_cut_pos[0] - usbc_recess_w/2, usbc_cut_pos[1] - usbc_recess_h/2, -back_plate_t - 35])
      cube([usbc_recess_w, usbc_recess_h, 35 + back_plate_t + 1]);
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

// ---- reversed antenna screws -----------------------------------------
// ant_inserts_open used to probe the plate's insert posts. Those posts are
// gone -- the insert moved into the mount's flange -- so that probe now sits
// in free air and returns its own volume whatever the plate looks like. It
// passed vacuously for exactly one run before this replaced it.

// The plate must be a plain clearance hole now: a 3mm probe passes through.
if (check=="ant_plate_holes_open") {
  difference() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a),
                 -back_plate_t - 1])
        cylinder(d=3.0, h=back_plate_t + 2); }
    back_plate();
  }
}
// ...and the flange must now carry the pocket the insert presses into.
if (check=="ant_flange_inserts_open") {
  intersection() {
    ant_flange_insert_bores();
    translate([-300,-300,-back_plate_t - ant_flange_insert_d])
      cube([600,600,ant_flange_insert_d]);
  }
}

// THE POINT OF THE WHOLE CHANGE. A driver coming from INSIDE the case, along
// each screw axis, must reach the plate without meeting the antenna mount.
if (check=="driver_path_clear") {
  intersection() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), 0])
        cylinder(d=6, h=45); }
    union() { antenna_mount(); antenna_mount_sma(); }
  }
}
// Paired positive control, and the measurement that justified reversing them.
// The SAME driver approaching from OUTSIDE -- the old direction -- must be
// caught by the socket mount's boss. Without this, driver_path_clear passes
// for a probe that was never near anything.
if (check=="driver_path_was_blocked") {
  intersection() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), -80])
        cylinder(d=6, h=80 - back_plate_t); }
    antenna_mount();
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

// ---- will a base of a given size actually get in? -------------------------
// The printed mount failed on exactly this and no check noticed, because
// every existing check asks whether parts COLLIDE. None asked whether the
// hole the antenna has to pass through is big enough, which is a different
// question and the one that mattered.
//
// A disc the size of the largest base the socket is meant to take, occupying
// the socket from floor to just past the rim, must touch nothing.
//
// Just past the rim, not well above it: the first version ran the disc 12mm
// into the air above the mouth and failed at 283mm3, which was the arm. A
// 35mm disc held 12mm above the socket does overlap the arm alongside it --
// and means nothing, because the antenna's base is a cone that narrows and
// comes in from outside, not an infinite cylinder lowered down the axis. The
// question is whether the base fits THE SOCKET.
if (check=="socket_takes_base") {
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_barrel_len - ant_socket_depth])
        cylinder(d=ant_base_dia, h=ant_socket_depth);
    antenna_mount();
  }
}
// Paired control: the same sweep at a size the socket is NOT meant to take
// must be caught, or an empty result above would only prove the probe misses
// the mount entirely.
if (check=="socket_gauge_works") {
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_barrel_len - ant_socket_depth])
        cylinder(d=ant_boss_dia + 2, h=ant_socket_depth + 1);
    antenna_mount();
  }
}
if (check=="connector_has_room") {
  // Room under the socket floor for the connector and its lead. The printed
  // mount had the base resting on its own cable, tilted, with the connector
  // wedged in the notch beside it -- and no check asked about the space
  // underneath, because every check was about the space around.
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_barrel_len - ant_socket_depth - ant_relief_h])
        cylinder(d=ant_relief_dia, h=ant_relief_h);
    antenna_mount();
  }
}

// ---- can the lead actually get out? ---------------------------------------
// The antenna's cable leaves the SIDE of its base, 7.98mm above the bottom,
// so with the base seated it is 7.98mm above the socket floor -- essentially
// at the rim. It cannot go down through the floor; the base is on the floor.
// A rod at that height, running radially out through the wall on the slot
// side, must meet nothing.
if (check=="cable_slot_open") {
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_barrel_len - ant_socket_depth + ant_cable_exit_h])
        rotate([-90, 0, 0])
          cylinder(d=4, h=ant_boss_dia/2 + 2);
    antenna_mount();
  }
}
// Paired control: the SAME rod on the opposite side must be blocked. Without
// it, an empty result above is also what a rod aimed into thin air produces,
// and "the slot is open" would be indistinguishable from "the probe misses
// the mount entirely".
if (check=="cable_slot_other_side") {
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_barrel_len - ant_socket_depth + ant_cable_exit_h])
        rotate([90, 0, 0])
          cylinder(d=4, h=ant_boss_dia/2 + 2);
    antenna_mount();
  }
}

// ---- the power fix (roadmap 5.7): the trigger board in the USB-C window ----
// Since 2026-10-29 the board's socket goes through the plate: the board's
// front edge bears on the plate's inner face, its socket goes out through a
// window its own shape, and the socket's face stands in the pocket, past the
// pocket's floor. The mount sits on the plate round the board, held by two M3
// screws from inside into inserts in the plate, and a printed stop behind the
// board, locked by two M2 screws through the mount's side walls, presses it
// forward. Restated for the probes below:
pwr_m2_pilot=1.65; pwr_m2_csk=2.8; pwr_trig_w=10.72; pwr_trig_proud=2.0;
pwr_m2_pitch=3.0; pwr_stop_clear=0.15; pwr_key_l=3.0;
// The speakers themselves aren't in shell() (only their sleeves and pads), so
// their bodies are drawn here: 100 x 45 x 21, the face on the sleeve's rim,
// where the four screw pads hold it. Until 2026-10-29 this drew each one 4 mm
// further out, its face where the bracket's mounting face used to be: inside
// its own screw pads, by 4487 mm3, and 4 mm clear of a mount that in fact
// reached 1 mm into the speaker's corner. power_speakers_on_pads now holds
// the drawing to the pads.
module pwr_speaker_bodies() {
  for (a = speaker_angles) rotate([0, 0, a])
    translate([outer_dia/2 - wall - speaker_bracket_depth - speaker_boss_h - speaker_h, -speaker_w/2, (shell_depth - speaker_d)/2])
      cube([speaker_h, speaker_w, speaker_d]);
}
// Round each M2 screw's thread in the stop, from the bottom of its
// countersink to the screw's tip: the pilot's own teardrop inside, and
// 1.2 mm of plastic outside it all round, roof included.
module pwr_m2_thread_rings() {
  x0 = pwr_stop_hw() - (pwr_m2_csk - pwr_m2_pilot)/2;
  e = pwr_m2_engaged();
  r = pwr_m2_pilot/2;
  for (i = [0, 1]) let (sx = i == 0 ? 1 : -1)
    translate([usbc_cut_pos[0] + sx*(x0 - e/2), usbc_cut_pos[1] + pwr_m2_y(), pwr_m2_z()[i]])
      rotate([90, 0, 0]) difference() {     // roofed toward the stop's bottom, as its pilots are
        rotate([0, 90, 0]) linear_extrude(height = e, center = true)
          hull() { circle(r = r + 1.2, $fn = 48); translate([-r*sqrt(2), 0]) circle(r = 1.2, $fn = 48); }
        pwr_x_teardrop(pwr_m2_pilot + 0.05, e + 2);
      }
}
// the case's local frame -> the stand's, as the case sits in it
module pwr_posed() { translate([0, 0, base_h + cradle_od/2 - 3]) rotate([90 - stand_angle, 0, 0]) translate([0, 0, -shell_depth/2]) children(); }

// The mount sits on the plate: nothing of it is in the plate...
if (check=="power_mount_vs_plate")    intersection() { power_trigger_mount_placed(); back_plate(); }
// ...and its face is down on it: moved 0.5 mm into the plate, it meets it.
if (check=="power_mount_on_plate")    intersection() { translate([0, 0, -0.5]) power_trigger_mount_placed(); back_plate(); }
// The board and its socket meet neither the plate nor the mount, but for the
// two ribs in the mount's roof (power_top_ribs_squeeze_socket, below)...
if (check=="power_board_held")        intersection() { power_trigger_board_placed(); union() { back_plate(); power_trigger_mount_placed(ribs = false); } }
// ...and the plate is what stops the board: moved 1.5 mm forward, its front
// edge runs into the plate.
if (check=="power_plate_holds_board") intersection() { translate([0, 0, -1.5]) power_trigger_board_placed(); back_plate(); }
// The board lies on the tube's floor (2026-10-29): moved 0.1 mm down, it runs
// into it. Until then the floor was 0.2 mm lower, and the board could rise
// and fall in the tube.
if (check=="power_board_on_floor")    intersection() { translate([0, -0.1, 0]) power_trigger_board_placed(); power_trigger_mount_placed(ribs = false); }
// The roof's two ribs press the socket's top down onto it. This one must come
// out small but not empty (SQUEEZE in run-checks.sh): the ribs' tips in the
// socket's top, as drawn 0.25 mm deep.
if (check=="power_top_ribs_squeeze_socket") intersection() { power_trigger_board_placed(); power_trigger_mount_placed(); }
// So the board cannot rock. Until 2026-10-29 it could tip about 2.3 degrees,
// its back end up, about the window's lower edge before its socket met the
// roof. Tipped 1 degree that way it now runs into the roof's ribs, even with
// their tips crushed to the socket's top as the board leaves them: this one
// must find more than a film (MEETS in run-checks.sh). The stop is drawn
// without its ribs, which press the board's back edge but do not hold it
// down.
module pwr_rocked(a) {
  yp = usbc_cut_pos[1] - usbc_cut_h/2;
  translate([0, yp, 0]) rotate([-a, 0, 0]) translate([0, -yp, 0]) children();
}
if (check=="power_board_cannot_rock") intersection() {
  pwr_rocked(1) power_trigger_board_placed();
  difference() {
    union() { back_plate(); power_trigger_mount_placed(); translate([usbc_cut_pos[0], usbc_cut_pos[1], 0]) power_trigger_stop_shape(ribs = false); }
    power_trigger_board_placed();
  }
}
// The board's front edge bears on solid plate below the window: in front of
// the edge, across the board's width and from its underside up to the
// window, the plate is solid from its inner face to the pocket's floor, all
// of the plate there (back_plate_t - usbc_recess_d: 1.6 mm, or 1.4 with the
// deeper pocket the README allows; an assert in the design holds it to 1.4 or
// more). Until 2026-10-29 the strip was a fixed 1.5 mm deep, so that deeper
// pocket failed this check although the plate was whole. The control: the
// same strip, moved 1.5 mm up into the window, finds air.
module pwr_edge_strip(dy = 0) {
  t = back_plate_t - usbc_recess_d;
  translate([usbc_cut_pos[0] - pwr_trig_w/2 + 0.05, usbc_cut_pos[1] + pwr_board_y0() + 0.05 + dy, -t + 0.01])
    cube([pwr_trig_w - 0.1, -usbc_cut_h/2 - pwr_board_y0() - 0.1, t - 0.02]);
}
if (check=="power_edge_on_plate")     difference() { pwr_edge_strip(); back_plate(); }
if (check=="power_edge_strip_works")  difference() { pwr_edge_strip(1.5); back_plate(); }
// The socket goes through its window with room all round: its shell, 0.25 mm
// bigger all round, meets no plate through the web. The control: 1 mm bigger
// all round, it does, so the window is close round the socket.
module pwr_socket_probe(grow) {
  translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t + usbc_recess_d - 0.5])
    linear_extrude(height = back_plate_t - usbc_recess_d + 1) pwr_socket2d(grow);
}
if (check=="power_socket_clears_window") intersection() { pwr_socket_probe(0.25); back_plate(); }
if (check=="power_window_is_close")      intersection() { pwr_socket_probe(1.0); back_plate(); }
// The pocket's floor bridges in two steps (2026-10-29). In the first layer
// over the pocket the opening runs from one side wall of the pocket to the
// other, as tall as the window, so every line of that layer spans the pocket;
// in the second it is the window's rectangle. A probe in each, 0.05 mm inside
// its outline and 0.02 inside the layer, meets no plate...
module pwr_bridge_probe(w, h, layer) {
  translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t + usbc_recess_d + layer*usbc_bridge_layer + 0.02])
    linear_extrude(height = usbc_bridge_layer - 0.04) square([w - 0.1, h - 0.1], center = true);
}
if (check=="usbc_bridge_steps_open") intersection() {
  union() { pwr_bridge_probe(usbc_recess_w, usbc_cut_h, 0); pwr_bridge_probe(usbc_cut_w, usbc_cut_h, 1); }
  back_plate();
}
// ...and from the second layer up the slot's two ends, beyond the window's
// rectangle, are solid plate: the slot is one layer and no more.
if (check=="usbc_bridge_steps_held") intersection() {
  for (sx = [-1, 1])
    translate([usbc_cut_pos[0] + sx*(usbc_recess_w + usbc_cut_w)/4, usbc_cut_pos[1], -back_plate_t + usbc_recess_d + usbc_bridge_layer + 0.02])
      linear_extrude(height = back_plate_t - usbc_recess_d - usbc_bridge_layer - 0.04)
        square([(usbc_recess_w - usbc_cut_w)/2 - 0.1, usbc_cut_h - 0.1], center = true);
  back_plate();
}
// A plug's shell (8.4 x 2.6) reaches the socket's face, out in the pocket...
if (check=="power_plug_reaches")      intersection() { power_plug_probe(); union() { back_plate(); power_trigger_mount_placed(); } }
// ...and the same probe, moved 6 mm up, stops on the plate.
if (check=="power_plug_probe_works")  intersection() { translate([0, 6, 0]) power_plug_probe(); back_plate(); }
// So does a moulding the size the pocket is drawn for (2026-10-29): 13.4 x
// 9.4, the pocket less 0.3 a side, from outside down to the socket's face,
// meets no plate, no mount and no insert. Until then the socket's face was at
// the plate's inner face, and a moulding had to go through the web to it.
// The control: one 1 mm bigger than the pocket each way stops on the outer
// face.
module pwr_moulding_probe(w, h) {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 20])
        linear_extrude(height = 20 + back_plate_t - pwr_trig_proud - 0.01)
            offset(r = 2) offset(delta = -2) square([w, h], center = true);
}
if (check=="power_moulding_reaches")     intersection() { pwr_moulding_probe(usbc_recess_w - 0.6, usbc_recess_h - 0.6); union() { back_plate(); power_trigger_mount_placed(); power_insert_probe(); } }
if (check=="power_moulding_probe_works") intersection() { pwr_moulding_probe(usbc_recess_w + 1, usbc_recess_h + 1); back_plate(); }

// ---- the mount's M3 screws and their inserts (2026-10-29) ----
// From inside, through the ears and into the inserts: the shanks meet neither
// the mount nor the plate (the ears' holes and the inserts' holes are open
// round them)...
if (check=="power_m3_pass")           intersection() { power_m3_probe(head = false); union() { power_trigger_mount_placed(); back_plate(); } }
// ...each goes 2.5 mm into its insert (this control finds them there)...
if (check=="power_m3_bite")           intersection() { power_m3_probe(head = false); power_insert_probe(insert_hole_dia); }
// ...and nothing of a screw or an insert comes out past the plate's outer
// face, where it could catch a moulding or the stand.
if (check=="power_m3_inside_plate")   intersection() { union() { power_m3_probe(); power_insert_probe(); } translate([0, 0, -back_plate_t - 50]) cylinder(r = 150, h = 50); }
// The heads, on the ears, stay under the speaker beside the window (its
// corner comes down to 8 mm from the plate).
if (check=="power_m3_clear_of_speakers") intersection() { power_m3_probe(); pwr_speaker_bodies(); }
// The inserts' holes are open right through the plate (the probe is held
// inside the plate's thickness, so a closed hole finds nothing)...
if (check=="usbc_insert_holes_open")  difference() {
  for (sx = [-1, 1]) translate([usbc_cut_pos[0] + sx*usbc_screw_pitch/2, usbc_cut_pos[1], -back_plate_t + 0.01])
    cylinder(d = insert_hole_dia - 0.2, h = back_plate_t - 0.02);
  back_plate();
}
// ...and each has solid plate 1.5 mm thick all round it, through the plate's
// whole thickness, for its knurl to melt into.
if (check=="usbc_inserts_surrounded") difference() {
  for (sx = [-1, 1]) translate([usbc_cut_pos[0] + sx*usbc_screw_pitch/2, usbc_cut_pos[1], -back_plate_t + 0.01])
    difference() {
      cylinder(d = insert_hole_dia + 3, h = back_plate_t - 0.02);
      translate([0, 0, -1]) cylinder(d = insert_hole_dia + 0.1, h = back_plate_t + 2);
    }
  back_plate();
}

// The mount clears the shell and the speaker beside it...
if (check=="power_mount_vs_shell")    intersection() { power_trigger_mount_placed(); shell(); }
if (check=="power_mount_vs_speakers") intersection() { power_trigger_mount_placed(); pwr_speaker_bodies(); }
// The speakers as drawn here sit on their pads, not in them.
if (check=="power_speakers_on_pads")  intersection() { pwr_speaker_bodies(); shell(); }
// The control for the speaker checks: the speaker drawing catches an ear 9 mm
// tall where the mount's nearer ear is, so the speaker's corner does come
// down past it.
if (check=="power_speaker_drawing_works") intersection() {
  translate([usbc_cut_pos[0] + usbc_screw_pitch/2, usbc_cut_pos[1], 0]) cylinder(d = 7.5, h = 9);
  pwr_speaker_bodies();
}

// ---- the stop behind the board (2026-10-29) ----
// It slides into the mount's back end and fits there: nothing of it is in the
// mount...
if (check=="power_stop_fits_tube")    intersection() { power_trigger_stop_placed(); power_trigger_mount_placed(); }
// ...or in the board, but for its two crush ribs: without them it stands
// clear of the board's back edge, so it presses on no part of the board...
if (check=="power_stop_clear_of_board") intersection() {
  translate([usbc_cut_pos[0], usbc_cut_pos[1], 0]) power_trigger_stop_shape(ribs = false);
  power_trigger_board_placed();
}
// ...and the ribs press into the board's back edge by their squeeze, so the
// board has no play along its length. This one must come out small but not
// empty (SQUEEZE in run-checks.sh): empty is a gap behind the board, and more
// than a sliver is the stop's body on the board.
if (check=="power_ribs_squeeze_board") intersection() { power_trigger_stop_placed(); power_trigger_board_placed(); }
// Positive control: the stop is right behind the board; moved 2 mm back, the
// board runs into its body.
if (check=="power_stop_takes_push")   intersection() { translate([0, 0, 2]) power_trigger_board_placed(); power_trigger_stop_placed(); }
// The M2 screws: a probe under the pilots' size, down each screw's axis from
// its wall's outer face to the stop's far side, meets neither the mount nor
// the stop, so the walls' pilots and the stop's line up...
if (check=="power_m2_holes_line_up")  intersection() {
  power_m2_probe(1.4, pwr_m2_reach() - 0.1, false);
  union() { power_trigger_mount_placed(); power_trigger_stop_placed(); }
}
// ...the screws, heads and all, touch neither the board nor its wires...
if (check=="power_m2_clear_of_board") intersection() { power_m2_probe(); union() { power_trigger_board_placed(); power_wire_probe(); } }
// ...and each has its whole thread, at least 4 mm (an assert in the design),
// in solid stop with 1.2 mm of plastic all round: the rings above, less the
// stop, leave nothing. Their control: the same rings do lie in the stop.
if (check=="power_m2_threads_held")   difference() { pwr_m2_thread_rings(); power_trigger_stop_placed(); }
if (check=="power_m2_threads_bite")   intersection() { pwr_m2_thread_rings(); power_trigger_stop_placed(); }
// The board's two output wires (2.1 mm across, from its top face) run
// straight out of the back over the stop, meeting nothing. The control: moved
// 3 mm down, they run into the stop.
if (check=="power_wires_out")         intersection() { power_wire_probe(); union() { power_trigger_mount_placed(); power_trigger_stop_placed(); power_m2_probe(); } }
if (check=="power_wire_probe_works")  intersection() { power_wire_probe(-3); power_trigger_stop_placed(); }
// The stop and the screws clear the shell and the speakers; and the whole
// power fix, posed in the stand with the case, clears the stand.
if (check=="power_stop_vs_shell")     intersection() { union() { power_trigger_stop_placed(); power_m2_probe(); } shell(); }
if (check=="power_stop_vs_speakers")  intersection() { union() { power_trigger_stop_placed(); power_m2_probe(); } pwr_speaker_bodies(); }
if (check=="power_parts_vs_stand")    intersection() {
  pwr_posed() union() { power_trigger_mount_placed(); power_trigger_stop_placed(); power_trigger_board_placed(); power_m2_probe(); power_m3_probe(); }
  stand();
}

// ---- the stop goes in only the right way round (2026-10-29) ----
// Back to front it used to go in as easily: its pilots sit a pitch apart
// about the middle of its length, and their countersinks change sides as it
// turns, so both screws found one and drew it in, 0.5 mm back off the board.
// Now a key at its back end runs in a slot in the mount's +x wall. Each wrong
// way round (back to front, upside down, and both at once, end over end) is
// turned about the middle of the stop's pilots, so they still line up with
// the walls', and posed pwr_catch further out than home: the furthest out a
// screw could start in it, its countersink's radius past the next screw's
// place. There it must run into the mount (BLOCKED in run-checks.sh), even
// pushed over by its 0.15 mm of play to whichever side frees it most; it
// cannot go further in without passing there.
pwr_catch = pwr_m2_pitch + pwr_m2_csk/2;    // 4.4
module pwr_stop_posed(r, dx = 0, key = true) {
  ym = pwr_m2_y();
  zm = (pwr_m2_z()[0] + pwr_m2_z()[1])/2;
  translate([usbc_cut_pos[0] + dx, usbc_cut_pos[1], pwr_catch])
    translate([0, ym, zm]) rotate(r) translate([0, -ym, -zm]) power_trigger_stop_shape(key = key);
}
// Back to front the key leads, on the -x side, where there is no slot, and
// meets the end of the mount; pushed +x, it still runs 0.7 mm into the wall.
if (check=="power_stop_back_to_front_blocked") intersection() { pwr_stop_posed([0, 180, 0], pwr_stop_clear); power_trigger_mount_placed(); }
// Upside down, or end over end, the T's wide top is down where the chamber
// is narrower (and the key is up, against the tube's wall).
if (check=="power_stop_upside_down_blocked")   intersection() { pwr_stop_posed([0, 0, 180], pwr_stop_clear); power_trigger_mount_placed(); }
if (check=="power_stop_end_over_end_blocked")  intersection() { pwr_stop_posed([180, 0, 0], -pwr_stop_clear); power_trigger_mount_placed(); }
// Their controls. The right way round, slid in from outside the mount's back
// end all the way home, 0.25 mm at a time, the stop meets nothing of the
// mount: the key passes its slot from end to end...
module pwr_stop_swept(from = 9, step = 0.25) {
  for (i = [0 : round(from/step)]) translate([0, 0, i*step]) power_trigger_stop_placed();
}
if (check=="power_stop_slides_home")    intersection() { pwr_stop_swept(); power_trigger_mount_placed(); }
// ...and back to front without its key, posed as above, it meets nothing
// either: the key is what stops it, as nothing did before.
if (check=="power_stop_key_is_what_blocks") intersection() { pwr_stop_posed([0, 180, 0], pwr_stop_clear, key = false); power_trigger_mount_placed(); }
// Those two must come out with nothing at all (CLEAR in run-checks.sh), not
// just under the 1 mm3 the other empty checks allow (2026-10-29). Where the
// key runs into the wall it is only about 0.36 mm2 across, so under 1 mm3 a
// slot begun 2.5 mm late passed: the stop jammed 2.35 mm short of home, its
// ribs off the board. The control: the slot begun 0.5 mm late, the wall
// left whole for its first 0.5 mm, jams the stop 0.35 mm short of home, and
// the sweep finds it, about 0.13 mm3 (JAMMED in run-checks.sh).
module pwr_slot_begun_late(late = 0.5) {
  translate([usbc_cut_pos[0], usbc_cut_pos[1], pwr_stop_z1() - pwr_key_l - pwr_stop_clear])
    linear_extrude(height = late) intersection() {
      pwr_key_slot2d();
      translate([pwr_stop_hw() + pwr_stop_clear, -50]) square([50, 100]);   // the wall, past the chamber's side
    }
}
if (check=="power_stop_jam_probe_works") intersection() { pwr_stop_swept(); union() { power_trigger_mount_placed(); pwr_slot_begun_late(); } }
// The regulator's tray has no set place: it goes on the plate's inner face
// wherever the case has room. All of the power fix at the window keeps to a
// 70 x 13.5 mm strip of the plate across it, up to 26 mm in from the plate,
// so the tray, and anything else stuck to the plate, need only keep off that
// strip (the READMEs say so): nothing of the parts is outside it, nor of the
// M2 screwdriver's way in from either side. Until 2026-10-29 it was a 33 x
// 13.5 mm patch, the parts alone, and a tray stuck beside the mount could
// have stood in the screwdriver's way.
module pwr_patch() {
  translate([usbc_cut_pos[0] - 35, usbc_cut_pos[1] - 9, -back_plate_t - 0.01]) cube([70, 13.5, back_plate_t + 26]);
}
// The screwdriver's way in to each M2 screw (2026-10-29): from the screw's
// head straight out along its axis, 6 mm across, as driver_path_clear allows
// for the antenna mount's, and 25 mm long, a driver's shaft; `inset` starts
// it that far back into the head. The stop is locked with the plate off the
// case, so the shell is not in the way.
pwr_mount_wall=1.6;
module pwr_m2_driver_paths(len = 25, inset = 0) {
  for (i = [0, 1]) let (sx = i == 0 ? 1 : -1)
    translate([usbc_cut_pos[0] + sx*(pwr_tube_w()/2 + pwr_mount_wall + 2.0 - inset), usbc_cut_pos[1] + pwr_m2_y(), pwr_m2_z()[i]])
      rotate([0, sx*90, 0]) cylinder(d = 6, h = len, $fn = 24);
}
if (check=="power_parts_in_patch")    difference() {
  union() { power_trigger_mount_placed(); power_trigger_stop_placed(); power_trigger_board_placed(); power_m2_probe(); power_m3_probe(); power_insert_probe(); pwr_m2_driver_paths(); }
  pwr_patch();
}
// Those ways in are clear: each meets nothing of the power fix or the plate...
if (check=="power_m2_drivers_clear")  intersection() {
  pwr_m2_driver_paths();
  union() { power_trigger_mount_placed(); power_trigger_stop_placed(); power_trigger_board_placed(); power_m3_probe(); back_plate(); }
}
// ...and they start at the screws: begun 3 mm further in, they run into the
// screws' heads and the mount's walls (the control).
if (check=="power_m2_drivers_reach")  intersection() { pwr_m2_driver_paths(inset = 3); union() { power_trigger_mount_placed(); power_m2_probe(); } }

// ---- the charger it needs, engraved in the plate (2026-10-29) ----
// "USB-C PD / 12V 27W", 0.6 mm deep in the outer face above the USB-C
// pocket, read from behind. Restated for the probes below:
usbc_gauge_size=[36,18]; usbc_label_depth=0.6;
// Where its letters are, there is no plate: they are cut...
if (check=="usbc_label_cut")           intersection() { usbc_label_solid(); back_plate(); }
// ...and they are there, in the plate's blank (the control, about 80 mm3).
if (check=="usbc_label_present")       intersection() { usbc_label_solid(); translate([0, 0, -back_plate_t]) cylinder(d = outer_dia, h = back_plate_t); }
// They lie inside the plate, 5 mm or more in from its rim and no more than
// 1 mm into its outer face...
if (check=="usbc_label_inside_plate")  difference() { usbc_label_solid(); translate([0, 0, -back_plate_t]) cylinder(d = outer_dia - 10, h = 1); }
// ...outside the coupon's 36 x 18 patch, so usbc_gauge is the plate's own
// geometry, unchanged...
if (check=="usbc_label_off_gauge")     intersection() {
  usbc_label_solid();
  translate([usbc_cut_pos[0] - usbc_gauge_size[0]/2, usbc_cut_pos[1] - usbc_gauge_size[1]/2, -back_plate_t - 1])
    cube([usbc_gauge_size[0], usbc_gauge_size[1], back_plate_t + 2]);
}
// ...and 1.5 mm or more from every other hole in the plate: the pocket, the
// window and the inserts' holes beside it, the vents, the antenna mount's
// holes and the eight screws' (1.5 mm past a screw's hole is past its head).
// The probe is the letters' outline grown by 1.5 mm, through the plate; the
// control moves it 12 mm down, over the pocket, where it finds them.
module usbc_label_probe(dy = 0) {
  translate([0, dy, -back_plate_t - 1]) linear_extrude(height = back_plate_t + 2) offset(r = 1.5) projection() usbc_label_solid();
}
module plate_holes_but_label() {
  difference() {
    translate([0, 0, -back_plate_t]) cylinder(d = outer_dia, h = back_plate_t);
    back_plate();
    translate([0, 0, -0.02]) usbc_label_solid(usbc_label_depth + 0.04);
  }
}
if (check=="usbc_label_clear_of_holes") intersection() { usbc_label_probe(); plate_holes_but_label(); }
if (check=="usbc_label_probe_works")    intersection() { usbc_label_probe(-12); plate_holes_but_label(); }

// The speaker sleeve is hollow (2026-10-23): inside it, from the speaker's
// face to the wall and clear of the four screw pads, there is no plastic. It
// was a solid block with the grille drilled through it as tubes. The control
// reaches 1 mm into the wall and finds it.
speaker_boss_h=4; speaker_angles=[0,180];
module spk_cavity_probe(reach) {
  for (a = speaker_angles) rotate([0, 0, a])
    intersection() {
      translate([outer_dia/2 - wall - speaker_bracket_depth - speaker_boss_h + 0.5, -42, (shell_depth - speaker_d)/2 + speaker_d/2 - 14])
        cube([30, 84, 28]);
      cylinder(r = outer_dia/2 - wall - 0.5 + reach, h = shell_depth, $fn = 360);
    }
}
if (check=="speaker_sleeve_hollow") intersection() { spk_cavity_probe(0); shell(); }
if (check=="speaker_probe_works")   intersection() { spk_cavity_probe(1.5); shell(); }

// ---- less support inside the shell (2026-10-29) ------------------------
// Restated, as above: `use <>` brings in no values.
retain_h=4; retain_w=4; retain_clear=0.5;
retain_segs=[[207, 38], [295, 38]]; retention_opening=195.34;

// The front rail's underside slopes to a lip, as the retro case's rings' do;
// the rear rail's stays square, because it bears on the rear arm. A ring band at
// r0-r1 out from the wall's face, z0-z1 from a rail's underside, over the
// middle of each segment.
module rail_probe(z_rail, r0, r1, z0, z1) {
  for (seg = retain_segs)
    translate([0, 0, z_rail + z0])
      rotate([0, 0, seg[0] + 5]) rotate_extrude(angle = seg[1] - 10)
        translate([outer_dia/2 + r0, 0]) square([r1 - r0, z1 - z0]);
}
front_rail_z = shell_depth/2 + arm_gap/2 - retain_clear - retain_w;   // 39, its underside
rear_rail_z  = shell_depth/2 - arm_gap/2 + retain_clear;              // 18
// The slope is there: just below the front rail, by the wall, is solid...
if (check=="rail_slope_present")    intersection() { shell(); rail_probe(front_rail_z, 0.3, 1.3, -2, -1); }
// ...and it stops short of the edge: under the rail's outer half millimetre
// is air, the shadow line. Fixed numbers, so that a lip of 0 fails.
if (check=="rail_lip_kept")         intersection() { shell(); rail_probe(front_rail_z, retain_h - 0.55, retain_h - 0.05, -0.45, -0.05); }
// The rear rail is still square: under it, across its width, is air. The
// control is the same probe 1 mm up, in the rail, which finds it.
if (check=="rear_rail_square")      intersection() { shell(); rail_probe(rear_rail_z, 0.3, retain_h - 0.3, -1, -0.05); }
if (check=="rear_rail_probe_works") intersection() { shell(); rail_probe(rear_rail_z, 0.3, retain_h - 0.3, 0.05, 1); }

// The shelf's underside slopes down to the wall: just under the shelf, by
// the wall, is solid. Probed in the two lower quarters, between the front
// posts (solid anyway), where both cases have it; nothing was there before.
module shelf_slope_probe() {
  for (w = [[212, 220], [230, 242], [298, 310], [320, 328]])
    rotate([0, 0, w[0]]) rotate_extrude(angle = w[1] - w[0])
      translate([outer_dia/2 - wall - 1.5, shell_depth - lip_height - 3]) square([1.2, 1]);
}
if (check=="shelf_slope_present") intersection() { shell(); shelf_slope_probe(); }

// Over each speaker the sleeve's top wall reaches the shelf: where the 2mm
// slot between them was, all is solid, either side of the front post's
// insert hole. The control is the same probe against the shell, which must
// find it, since an empty probe would pass the first for nothing.
module speaker_slot_probe() {
  for (a = speaker_angles) rotate([0, 0, a]) for (s = [-1, 1])
    intersection() {
      translate([retention_opening/2 + 1, s > 0 ? 3.5 : -44, shell_depth - lip_height - 1.8]) cube([10, 40.5, 1.6]);
      cylinder(r = outer_dia/2 - wall - 0.3, h = shell_depth, $fn = 360);
    }
}
if (check=="speaker_slot_closed")      difference() { speaker_slot_probe(); shell(); }
if (check=="speaker_slot_probe_works") intersection() { speaker_slot_probe(); shell(); }

// ---- the retainer goes in one way only (2026-10-29) --------------------
retainer_h=4;   // restated
// Seated on the shelf the right way round, the retainer's key drops into the
// shelf's gap and meets nothing (retainer_key_fits). Turned by each of the
// other seven 45-degree steps the screws allow, the key lands on the shelf,
// about 126 mm3 (retainer_key_blocks_*), so the ring stands 2mm proud before
// a screw goes in. Each angle is its own check, as the back plate's are: a
// key that blocked only some would still let it in wrong.
module retainer_seated(a = 0) { translate([0, 0, shell_depth - retainer_h]) rotate([0, 0, a]) retainer(); }
if (check=="retainer_key_fits")       intersection() { retainer_seated(0);   shell(); }
if (check=="retainer_key_blocks_45")  intersection() { retainer_seated(45);  shell(); }
if (check=="retainer_key_blocks_90")  intersection() { retainer_seated(90);  shell(); }
if (check=="retainer_key_blocks_135") intersection() { retainer_seated(135); shell(); }
if (check=="retainer_key_blocks_180") intersection() { retainer_seated(180); shell(); }
if (check=="retainer_key_blocks_225") intersection() { retainer_seated(225); shell(); }
if (check=="retainer_key_blocks_270") intersection() { retainer_seated(270); shell(); }
if (check=="retainer_key_blocks_315") intersection() { retainer_seated(315); shell(); }

// ---- the front stack, placed in one place (2026-10-29) -----------------
// The front stack as front_stack_placed() puts it, for every picture: it
// meets the shell with no volume (front_stack_seats). Lowered 0.2mm, the
// retainer runs into the shelf and the trim into the shell's rim, each on
// its own, so neither stands off the shell: a trim floating 4.9mm proud, as
// the pictures had it, passes the first check and fails the last.
if (check=="front_stack_seats")          intersection() { front_stack_placed(); shell(); }
if (check=="front_stack_retainer_down")  intersection() { translate([0, 0, -0.2]) front_stack_placed("retainer"); shell(); }
if (check=="front_stack_trim_down")      intersection() { translate([0, 0, -0.2]) front_stack_placed("trim"); shell(); }
