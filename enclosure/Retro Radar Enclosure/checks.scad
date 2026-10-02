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
// front heat-set inserts (restated): shelf top face, insert length, hole
fi_top = 57; fi_len = 5; fi_hole = 4.0;
outer_dia=223.34; wall=3; shell_depth=61; screw_r=106.67; n_screws=8;
speaker_angles=[0,180]; back_plate_t=3;
// Restated because `use <>` imports modules and functions but NOT variables.
// A stale value here checks geometry the design no longer has, and passes.
back_lip_h=4; back_lip_t=2; back_lip_gap=0.35; back_lip_skip=9; post_od=9;
back_post_h=9; ant_bolt_pcd=30; n_ant_bolts=3; ant_flange_d=40; ant_mount_y=88;
ant_bolt_d=3.4; usbc_cut_pos=[60,-14]; usbc_screw_pitch=16.5; usbc_screw_dia=3.4; usbc_cut_w=11.0; usbc_cut_h=6.5;
mount_hole_x=58; mount_hole_y=49; stand_angle=18;
base_w=outer_dia*0.86; base_d=150; plinth_rib_h=4; plinth_rib_w=3; plinth_rib_z=[3.5, 9.5];
ant_stub_len=30; ant_barrel_len=14; ant_socket_dia=33; ant_socket_depth=6;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; base_h=16;
ant_conn_dia=9.15; ant_boss_dia=45; ant_socket_lead=2;
// Measured off the antenna: 31.25mm across the flared bottom, its widest
// point. ant_relief_* is the clear space under the socket floor for the
// connector, which is what was actually stopping the base from seating.
ant_base_dia=31.25; ant_relief_dia=18; ant_relief_h=4;
rib_h=4.0; rib_w=5; rib_z_list=[10,22]; rib_a0=340; rib_arc=220;
grille_hole_dia=2.5; grille_pitch=4.5; grille_w=90; grille_h=40;
speaker_d=45; speaker_angles=[0,180]; exhaust_slot_w=2.2; exhaust_slot_h=12;
n_exhaust=24; exhaust_a0=30; exhaust_a1=150;
ant_cable_slot_w=7; ant_cable_exit_h=7.98; ant_flange_t=7; ant_flange_insert_d=5.5; back_insert_d=8;

// The SMA bulkhead variant. Restated here for the same reason as everything
// above: `use <>` brings in modules, not variables, so a check that names one
// of these directly needs its own copy.
ant_sma_hole=6.5; ant_sma_panel_t=3; ant_sma_cavity=14;
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
else if (check=="usbc_clears_standoffs") {
  intersection() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      cylinder(d=usbc_screw_pitch + 6, h=back_plate_t + 20);
    for (x=[-mount_hole_x/2, mount_hole_x/2])
      for (y=[-mount_hole_y/2, mount_hole_y/2])
        translate([x,y,0]) cylinder(d=7, h=8);
  }
}

// The USB-C pass-through screws moved from 24.0mm centres to 16.5mm, to suit
// a pass-through that mounts from INSIDE the plate. That pulls each screw
// 3.75mm closer to the window, leaving 1.60mm of plate between them where
// there used to be 5.35mm -- four perimeters at a 0.4mm nozzle. Still sound,
// but no longer something to change casually, so it is pinned.
//
// Grow the window by 1mm all round and the screw holes must STILL miss it.
// Empty here means at least 1mm of material survives between them.
else if (check=="usbc_screws_clear_window") {
  intersection() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      linear_extrude(height = back_plate_t + 2)
        offset(r = 1)
          square([usbc_cut_w, usbc_cut_h], center = true);
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      for (sx = [-1, 1])
        translate([sx * usbc_screw_pitch/2, 0, 0])
          cylinder(d = usbc_screw_dia, h = back_plate_t + 2);
  }
}
// Paired positive control: the same probe at the OLD 24.0mm pitch would also
// come out empty, so an empty result above proves nothing on its own. Grow
// the window by 4mm instead and the screws must now be caught -- which shows
// the probe can find them at all, and that they really did move inwards.
else if (check=="usbc_screw_probe_works") {
  intersection() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      linear_extrude(height = back_plate_t + 2)
        offset(r = 4)
          square([usbc_cut_w, usbc_cut_h], center = true);
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1])
      for (sx = [-1, 1])
        translate([sx * usbc_screw_pitch/2, 0, 0])
          cylinder(d = usbc_screw_dia, h = back_plate_t + 2);
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
