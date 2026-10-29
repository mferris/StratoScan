// Fit checks for the retro enclosure's removable back plate.
//
// Run with `sh run-checks.sh`, which measures the VOLUME each target
// produces rather than whether it produced anything: a boolean between parts
// that touch leaves zero-thickness films with many facets and no volume, so
// counting facets calls a correct model broken.
//
// Lives beside the design on purpose. `use <>` resolves relative to the file
// containing it, so a copy kept anywhere else silently finds no modules and
// every check "passes" against nothing -- which is why `canary` exists and
// must be run.
use <retro-enclosure.scad>
$fs = 0.4;
$fa = 0.5;
check = "none";
// the power fix's checks read these (restated, as below)
speaker_bracket_depth=15; speaker_h=21; speaker_w=100;
// front heat-set inserts (restated): shelf top face, insert length, hole
fi_top = 57; fi_len = 5; fi_hole = 4.0;
outer_dia=223.34; wall=3; shell_depth=61; screw_r=106.67; n_screws=8;
speaker_angles=[0,180]; back_plate_t=3;
// Restated because `use <>` imports modules and functions but NOT variables.
// A stale value here checks geometry the design no longer has, and passes.
back_lip_h=4; back_lip_t=2; back_lip_gap=0.35; back_lip_skip=9; post_od=9;
back_post_h=9; ant_bolt_pcd=30; n_ant_bolts=3; ant_flange_d=40; ant_mount_y=81;
ant_bolt_d=3.4; usbc_cut_pos=[60,-51]; usbc_screw_pitch=24; usbc_cut_w=9.54; usbc_cut_h=3.86; usbc_cut_r=1.93;
usbc_recess_w=14; usbc_recess_h=10; usbc_recess_r=2.5; usbc_recess_d=1.4; insert_hole_dia=4.0; usbc_insert_len=3;
usbc_bridge_layer=0.2;
mount_hole_x=58; mount_hole_y=49; stand_angle=18;
base_w=outer_dia*0.86; base_d=150; plinth_rib_h=4; plinth_rib_w=3; plinth_rib_z=[3.5, 9.5];
ant_stub_len=30; ant_barrel_len=14; ant_socket_dia=33; ant_socket_depth=8;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; base_h=16;
ant_conn_dia=9.15; ant_boss_dia=48; ant_socket_lead=1.2;
// Measured off the antenna: 31.25mm across the flared bottom, its widest
// point. ant_relief_* is the clear space under the socket floor for the
// connector, which is what was actually stopping the base from seating.
ant_base_dia=31.25; ant_relief_dia=18; ant_relief_h=4;
rib_h=4.0; rib_w=5; rib_z_list=[10,22]; rib_a0=340; rib_arc=220; rib_lip=0.8;
grille_hole_dia=2.5; grille_pitch=4.5; grille_w=90; grille_h=40;
speaker_d=45; speaker_angles=[0,180]; exhaust_slot_w=2.2; exhaust_slot_h=12;
n_exhaust=24; exhaust_a0=30; exhaust_a1=150;
ant_cable_slot_w=7; ant_cable_exit_h=7.98; ant_flange_t=7; ant_flange_insert_d=5.5; back_insert_d=7;

// The SMA bulkhead variant. Restated here for the same reason as everything
// above: `use <>` brings in modules, not variables, so a check that names one
// of these directly needs its own copy.
ant_sma_hole=6.5; ant_sma_panel_t=3; ant_sma_cavity=14; ant_twin_cover_t=3;
ant_sma_boss_d=22; ant_sma_boss_h=10; ant_sma_cavity_d=25;


// The plate and the shell meet at a butt joint; neither may intrude on the
// other.
// ---- plinth ridges (roadmap 5.4) ---------------------------------------
// A probe just outside each face of the stand's plinth, spanning the middle
// half of that face and the ridge heights. Each must find ridge material, so
// a ridge missing from any side fails. The old strips (front only, 1mm proud,
// short of where these probes start) came out empty on all four.
module plinth_side_probe(side) {
    z0 = min(plinth_rib_z); z1 = max(plinth_rib_z) + plinth_rib_w;
    if (side == "front" || side == "back")
        translate([-base_w/4, (side == "front" ? -1 : 1) * (base_d/2 + plinth_rib_h/2) - plinth_rib_h/4, z0])
            cube([base_w/2, plinth_rib_h/2, z1 - z0]);
    else
        translate([(side == "left" ? -1 : 1) * (base_w/2 + plinth_rib_h/2) - plinth_rib_h/4, -base_d/4, z0])
            cube([plinth_rib_h/2, base_d/2, z1 - z0]);
}

// The grille block at each speaker, out past the wall and the rivets' height,
// front to back. Rivets anywhere in it stood up among the holes; three of the
// ring used to.
module grille_zone(a) {
  rotate([0,0,a]) translate([outer_dia/2 - 5, -grille_w/2 - 2, -1])
    cube([10, grille_w + 4, shell_depth + 2]);
}

// A ring band of the rib profile, at radius r0-r1 out from the wall's face and
// height z0-z1 relative to each ring's underside (rib_slopes_present, rib_lip_kept).
module rib_probe(r0, r1, z0, z1) {
  for (z = rib_z_list)
    translate([0, 0, z + z0])
      rotate([0, 0, rib_a0 + 5]) rotate_extrude(angle = rib_arc - 10)
        translate([outer_dia/2 + r0, 0]) square([r1 - r0, z1 - z0]);
}

// A strip along the middle half of the plinth's front face, at distance d0-d1
// out from the face and height z0-z1 relative to each ridge's underside
// (plinth_slopes_present, plinth_lip_kept).
module plinth_rib_probe(d0, d1, z0, z1) {
  for (z = plinth_rib_z)
    translate([-base_w/4, -base_d/2 - d1, z + z0]) cube([base_w/2, d1 - d0, z1 - z0]);
}

if (check=="plate_vs_shell") {
  intersection() { back_plate(); shell(); }
}
// Nothing on the plate may stand outside the case's own diameter, or it
// fouls the cradle arms.
else if (check=="plate_outside_case") {
  difference() { back_plate(); cylinder(d=outer_dia, h=300, center=true); }
}
// Every insert hole must be an open bore. The speaker brackets reach the
// wall at 0 and 180 degrees, exactly where two of the back posts stand, so a
// hole subtracted inside the post module gets unioned shut again by the
// bracket landing on it -- this check is why they are drilled after the
// union instead. It is a POSITIVE control: it must find eight open bores.
else if (check=="back_inserts_open") {
  difference() {
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), 0.5]) cylinder(d=3.6, h=6); }
    shell();
  }
}
// The retainer must slip into the shell's bore with retainer_clear to spare
// (it was drawn at exactly the bore, and the first print had to be forced):
// a ring 0.3mm inside the bore must not touch it.
else if (check=="retainer_clears_bore") {
  intersection() {
    retainer();
    difference() { cylinder(d=outer_dia + 2, h=10, center=true); cylinder(d=outer_dia - 2*wall - 0.6, h=12, center=true); }
  }
}
// Every screw must pass the retainer freely: an M3 clearance shank (3.2mm)
// at each screw position meets no ring.
else if (check=="retainer_screws_pass") {
  intersection() {
    retainer();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), -5]) cylinder(d=3.2, h=20); }
  }
}
// And the trim must have a clear M3 hole at each screw too.
else if (check=="trim_screws_pass") {
  intersection() {
    front_trim();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), -10]) cylinder(d=3.2, h=30); }
  }
}
// The pocket in the outer face for a plug's moulding (2026-10-29: 14 x 10 and
// 1.4 deep round the trigger board's socket; it was the old connector's,
// 2 mm deep): open to usbc_recess_d from the outer face over its whole
// footprint (a probe there meets no plate)...
else if (check=="usbc_recess_open") {
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
else if (check=="usbc_recess_web") {
  intersection() {
    back_plate();
    translate([usbc_cut_pos[0] - 6, usbc_cut_pos[1] + usbc_cut_h/2 + 0.3, -back_plate_t + usbc_recess_d + 0.1])
      cube([12, 2.0, back_plate_t - usbc_recess_d - 0.2]);
  }
}
// A plug in the USB-C socket (as big as the pocket, 14 x 10, and 35 mm out of
// the plate with its strain relief) clears the stand with the case leaning
// back in it (the socket is at the bottom of the plate since 2026-10-10)...
else if (check=="usbc_plug_clears_stand") {
  intersection() {
    stand();
    translate([0,0,base_h + cradle_od/2 - 3]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2])
      translate([usbc_cut_pos[0] - usbc_recess_w/2, usbc_cut_pos[1] - usbc_recess_h/2, -back_plate_t - 35])
        cube([usbc_recess_w, usbc_recess_h, 35]);
  }
}
// ...and the same probe, run on into the plate, does meet it (the probe is
// where the socket is).
else if (check=="usbc_plug_probe_works") {
  intersection() {
    back_plate();
    translate([usbc_cut_pos[0] - usbc_recess_w/2, usbc_cut_pos[1] - usbc_recess_h/2, -back_plate_t - 35])
      cube([usbc_recess_w, usbc_recess_h, 35 + back_plate_t + 1]);
  }
}
// sanity: this MUST produce geometry, or nothing above means anything.
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
// Each M2 cap head (3.8mm) sits 1.5mm down in its counterbore, on both
// covers: a head-sized probe that deep meets no cover.
else if (check=="twin_cover_heads_seat" || check=="twin_cover_heads_seat_11") {
  af = check=="twin_cover_heads_seat" ? [8, 8] : [11, 11];
  intersection() {
    antenna_mount_twin_cover(af);
    for (q = ant_twin_screw_xz(af)) translate([q[0], q[1], -1]) cylinder(d=3.8, h=1 + 1.5, $fn=24);
  }
}
// The lettering fills its engraving: it never overlaps the cover...
else if (check=="twin_cover_text_vs_cover" || check=="twin_cover_text_vs_cover_11") {
  af = check=="twin_cover_text_vs_cover" ? [8, 8] : [11, 11];
  intersection() { antenna_mount_twin_cover(af); ant_twin_label_solid(af); }
}
// ...and lies inside the cover's outline. With text_vs_cover empty, that
// puts every letter in the engraving: within the cover, but not in its
// material.
else if (check=="twin_cover_text_inside" || check=="twin_cover_text_inside_11") {
  af = check=="twin_cover_text_inside" ? [8, 8] : [11, 11];
  difference() { ant_twin_label_solid(af); translate([0, 0, -1]) linear_extrude(height=3) ant_twin_cover2d(af); }
}
else if (check=="twin_cover_text_present") ant_twin_label_solid([11, 11]);   // positive control: must have volume
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
// Three separate checks, because one "does the plate fit" test passes just
// as happily when the lip is missing altogether.
else if (check=="lip_present") {          // positive control
  intersection() {
    back_plate();
    difference() {
      cylinder(d=outer_dia, h=back_lip_h);
      cylinder(d=outer_dia - 2*wall - 2*back_lip_gap - 2*back_lip_t - 1,
               h=back_lip_h*3, center=true);
    }
  }
}
else if (check=="lip_clears_posts") {     // a full ring would hit all eight
  intersection() {
    back_plate();
    for (i=[0:n_screws-1]) { a=i*360/n_screws;
      translate([screw_r*cos(a), screw_r*sin(a), 0])
        cylinder(d=post_od, h=back_post_h); }
  }
}
else if (check=="lip_inside_bore") {      // proud of the bore locates nothing
  difference() {
    intersection() {
      back_plate();
      translate([0,0,0.1]) cylinder(d=outer_dia, h=back_lip_h - 0.2);
    }
    translate([0,0,-1]) cylinder(d=outer_dia - 2*wall - 2*back_lip_gap + 0.01,
                                 h=back_lip_h + 2);
  }
}
// ---- speaker grilles: no rivets on them, no holes behind the ribs --------
else if (check=="rivets_clear_of_grilles") {
  intersection() { rivets(); union() { for (a = speaker_angles) grille_zone(a); } }
}
// Paired control: the same probe turned to 90 degrees, where no speaker is,
// must find rivets, or the empty result above proves nothing.
else if (check=="rivets_present") {
  intersection() { rivets(); grille_zone(90); }
}
// No grille hole at or behind the ribs. The one row that sat between them read
// as a stray line of holes. The front rib's front edge is z = 27.
else if (check=="grille_in_front_of_ribs") {
  intersection() {
    for (a = speaker_angles) speaker_grille(a);
    translate([0,0,-1]) cylinder(d=outer_dia + 20, h=27 + 1);
  }
}
// ...and the grille in front of them is still there.
else if (check=="grille_present") {
  intersection() {
    for (a = speaker_angles) speaker_grille(a);
    translate([0,0,27]) cylinder(d=outer_dia + 20, h=shell_depth);
  }
}
// ---- side exhaust: top arc only, and open to the inside ----------------
// The slots used to be cut all round, through the speaker grilles and into the
// retention rails underneath, and only 2.5mm deep in a 3mm wall, so none of
// them reached the inside. Nothing may be cut outside the top arc
// (exhaust_a0..exhaust_a1, with 5 degrees of margin either side)...
else if (check=="exhaust_top_only") {
  intersection() {
    exhaust_slots();
    rotate([0,0,exhaust_a1 + 5])
      rotate_extrude(angle = 360 - (exhaust_a1 - exhaust_a0) - 10)
        translate([0, -1]) square([outer_dia, shell_depth + 2]);
  }
}
// ...and what is cut must reach past the wall's inner face. A probe ring just
// inside the bore finds about 13mm3 per slot; a blind dent finds nothing.
else if (check=="exhaust_reaches_inside") {
  intersection() {
    exhaust_slots();
    difference() {
      cylinder(d=outer_dia - 2*wall + 0.01, h=shell_depth);
      translate([0,0,-1]) cylinder(d=outer_dia - 2*wall - 1, h=shell_depth + 2);
    }
  }
}
// ---- vents clear of the antenna mount ---------------------------------
// Only the GRILLES are probed. Testing "every hole under the flange" counts
// the cable bore and the three bolt holes, which are meant to be there.
else if (check=="vents_clear_of_mount") {
  intersection() {
    translate([0,0,-back_plate_t]) { intake_grille(); fan_grille(); }
    translate([0, ant_mount_y, -back_plate_t - 1])
      cylinder(d=ant_flange_d, h=back_plate_t + 2);
  }
}
// Paired positive control: the same probe at the grille's OLD position must
// find the overlap that moving it was meant to remove.
else if (check=="vents_were_under_mount") {
  intersection() {
    translate([0, 136, 0]) translate([0,0,-back_plate_t]) fan_grille();
    translate([0, ant_mount_y, -back_plate_t - 1])
      cylinder(d=ant_flange_d, h=back_plate_t + 2);
  }
}
// ---- the single USB-C window ------------------------------------------
else if (check=="usbc_open") {            // positive control
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
else if (check=="usbc_inserts_clear_pocket") {
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
else if (check=="usbc_insert_probe_works") {
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

// ---- antenna mount ----------------------------------------------------
else if (check=="ant_inserts_open") {     // positive control: bosses bored
  difference() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), 0])
        cylinder(d=3.0, h=back_post_h); }
    back_plate();
  }
}

// ---- reversed antenna screws -----------------------------------------
// ant_inserts_open used to probe the plate's insert posts. Those posts are
// gone -- the insert moved into the mount's flange -- so that probe now sits
// in free air and returns its own volume whatever the plate looks like. It
// passed vacuously for exactly one run before this replaced it.

// The plate must be a plain clearance hole now: a 3mm probe passes through.
else if (check=="ant_plate_holes_open") {
  difference() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a),
                 -back_plate_t - 1])
        cylinder(d=3.0, h=back_plate_t + 2); }
    back_plate();
  }
}
// ...and the flange must now carry the pocket the insert presses into.
else if (check=="ant_flange_inserts_open") {
  intersection() {
    ant_flange_insert_bores();
    translate([-300,-300,-back_plate_t - ant_flange_insert_d])
      cube([600,600,ant_flange_insert_d]);
  }
}

// THE POINT OF THE WHOLE CHANGE. A driver coming from INSIDE the case, along
// each screw axis, must reach the plate without meeting the antenna mount.
else if (check=="driver_path_clear") {
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
else if (check=="driver_path_was_blocked") {
  intersection() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), -80])
        cylinder(d=6, h=80 - back_plate_t); }
    antenna_mount();
  }
}

// The turret is gone. "Nothing proud of outer_dia" is the obvious test and
// it is wrong: the decorative rivets and the cradle rails deliberately stand
// proud, out to r=115.7 all the way round, and the first version of this
// check reported all 13,632mm3 of them as a turret. The turret reached
// r=128, so the probe goes at 116.67 -- outside the rivets, well inside the
// turret.
else if (check=="no_turret") {
  difference() {
    shell();
    cylinder(d=2*116.67, h=shell_depth*3, center=true);
  }
}
// Paired positive control. An empty result above is also what a probe set
// too wide produces, so the retired turret module -- still defined in the
// design -- has to be caught by the SAME probe.
else if (check=="turret_probe_works") {
  difference() {
    antenna_turret_solid();
    cylinder(d=2*116.67, h=shell_depth*3, center=true);
  }
}
else if (check=="mount_vs_plate") {
  intersection() { antenna_mount(); back_plate(); }
}

// The antenna's own swept envelope, run 220mm out along its axis, must miss
// the case. The mount was dimensioned against the kitten's head, which is
// the LARGER obstacle (it has ears); this proves the same part also clears
// the plain cylinder, rather than assuming it follows.
else if (check=="antenna_clears_case") {
  intersection() {
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
      rotate([stand_angle,0,0]) rotate([-90,0,0])
        translate([0,0,ant_barrel_len - ant_socket_depth])
          cylinder(d=ant_socket_dia, h=220);
    shell();
  }
}
// ...and the mount itself must not foul the cradle the case sits in.
else if (check=="mount_vs_stand") {
  arm_lift = base_h + cradle_od/2 - 3;
  intersection() {
    stand();
    translate([0,0,arm_lift]) rotate([90-stand_angle,0,0])
      translate([0,0,-shell_depth/2]) union() { back_plate(); antenna_mount(); }
  }
}

// ---- the decorative ribs must not be perforated ----------------------
// The ribs sweep 220 degrees, which takes in both speakers and most of the
// exhaust slots. Before this, every grille hole in the rib band and the
// bottom 2.5mm of every slot cut straight through the ridge and out the far
// side: from the outside the rib looked chewed rather than raised.
//
// Nothing that is cut from the wall may take material out of a rib.
else if (check=="ribs_unbroken") {
  intersection() {
    ribs();
    union() {
      exhaust_slots();
      for (a = speaker_angles) speaker_grille(a);
    }
  }
}
// Paired positive control. An empty result above is also what ribs() failing
// to evaluate produces, or a probe that never reaches the wall -- and this
// check would then pass for a case with no ribs at all. The ribs must exist
// and have real volume.
else if (check=="plinth_ribs_front") { intersection() { stand(); plinth_side_probe("front"); } }
else if (check=="plinth_ribs_back")  { intersection() { stand(); plinth_side_probe("back"); } }
else if (check=="plinth_ribs_left")  { intersection() { stand(); plinth_side_probe("left"); } }
else if (check=="plinth_ribs_right") { intersection() { stand(); plinth_side_probe("right"); } }
else if (check=="ribs_present") {
  ribs();
}
// The stand's ridges match (2026-10-24): sloped under, a lip at the edge.
else if (check=="plinth_slopes_present") {
  intersection() { stand(); plinth_rib_probe(0.3, 1.3, -2, -1); }
}
else if (check=="plinth_lip_kept") {
  intersection() { stand(); plinth_rib_probe(plinth_rib_h - 0.55, plinth_rib_h - 0.05, -0.45, -0.05); }
}

// ---- the rings print without support (2026-10-24) ---------------------
// Square, each ring's underside was a 4mm shelf in mid-air: supported all
// round, and the supports welded on. Now it slopes at 45 degrees from the
// wall to a small square lip.
// The slope is there: just below each ring, by the wall, is solid.
else if (check=="rib_slopes_present") {
  intersection() { ribs(); rib_probe(0.3, 1.3, -2, -1); }
}
// And it stops short of the edge: under the outer half millimetre is air, the
// shadow line that keeps the rings looking square. A full 45-degree slope
// fills it. Fixed numbers, not rib_lip's: a lip of 0 must fail, not shrink the
// probe to nothing.
else if (check=="rib_lip_kept") {
  intersection() { ribs(); rib_probe(rib_h - 0.55, rib_h - 0.05, -0.45, -0.05); }
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



// ---- can the connector actually get through? --------------------------
// A 9.15mm plug gauge swept along the passage: down the antenna's axis from
// the socket floor, then straight out through the arm and the plate. It must
// touch nothing. This is the check the old design would have failed -- its
// bore was 9.0mm, and the socket floor met it at an angle besides.
else if (check=="connector_passes") {
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
else if (check=="connector_gauge_works") {
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
else if (check=="socket_takes_base") {
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
else if (check=="socket_gauge_works") {
  intersection() {
    ant_axis_frame()
      translate([0, 0, ant_barrel_len - ant_socket_depth])
        cylinder(d=ant_boss_dia + 2, h=ant_socket_depth + 1);
    antenna_mount();
  }
}
else if (check=="connector_has_room") {
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
else if (check=="cable_slot_open") {
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
else if (check=="cable_slot_other_side") {
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
pwr_m2_pitch=3.0; pwr_stop_clear=0.15;
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
// window, the plate is solid 1.5 mm deep. The control: the same strip, moved
// 1.5 mm up into the window, finds air.
module pwr_edge_strip(dy = 0) {
  translate([usbc_cut_pos[0] - pwr_trig_w/2 + 0.05, usbc_cut_pos[1] + pwr_board_y0() + 0.05 + dy, -1.5])
    cube([pwr_trig_w - 0.1, -usbc_cut_h/2 - pwr_board_y0() - 0.1, 1.49]);
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
// The regulator's tray has no set place: it goes on the plate's inner face
// wherever the case has room. All of the power fix at the window keeps to a
// 33 x 13.5 mm patch of the plate round it, up to 26 mm in from the plate, so
// the tray, and anything else stuck to the plate, need only keep off that
// patch (the READMEs say so): nothing of the parts is outside it.
module pwr_patch() {
  translate([usbc_cut_pos[0] - 16.5, usbc_cut_pos[1] - 9, -back_plate_t - 0.01]) cube([33, 13.5, back_plate_t + 26]);
}
if (check=="power_parts_in_patch")    difference() {
  union() { power_trigger_mount_placed(); power_trigger_stop_placed(); power_trigger_board_placed(); power_m2_probe(); power_m3_probe(); power_insert_probe(); }
  pwr_patch();
}

// The speaker sleeve is hollow (2026-10-23): inside it, from the speaker's
// face to the wall and clear of the four screw pads, there is no plastic. It
// was a solid block with the grille drilled through it as tubes. The control
// reaches 1 mm into the wall and finds it.
speaker_boss_h=4;
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
