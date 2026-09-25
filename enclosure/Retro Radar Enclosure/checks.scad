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
use <flightwall-enclosure.scad>
$fs = 0.4;
$fa = 0.5;
check = "none";
outer_dia=223.34; wall=3; shell_depth=56; screw_r=106.67; n_screws=8;
speaker_angles=[0,180]; back_plate_t=3;
// Restated because `use <>` imports modules and functions but NOT variables.
// A stale value here checks geometry the design no longer has, and passes.
back_lip_h=4; back_lip_t=2; back_lip_gap=0.35; back_lip_skip=9; post_od=9;
back_post_h=9; ant_bolt_pcd=30; n_ant_bolts=3; ant_flange_d=40; ant_mount_y=88;
ant_bolt_d=3.4; usbc_cut_pos=[60,-14]; usbc_screw_pitch=24.0;
mount_hole_x=58; mount_hole_y=49; stand_angle=18;
ant_stub_len=30; ant_barrel_len=14; ant_socket_dia=33; ant_socket_depth=6;
cradle_id=outer_dia+2; cradle_od=cradle_id+26; base_h=16;
ant_conn_dia=9.15; ant_boss_dia=45; ant_socket_lead=2;
// Measured off the antenna: 31.25mm across the flared bottom, its widest
// point. ant_relief_* is the clear space under the socket floor for the
// connector, which is what was actually stopping the base from seating.
ant_base_dia=31.25; ant_relief_dia=18; ant_relief_h=4;
ant_cable_slot_w=7; ant_cable_exit_h=7.98; ant_flange_t=4; back_insert_d=8;

// The SMA bulkhead variant. Restated here for the same reason as everything
// above: `use <>` brings in modules, not variables, so a check that names one
// of these directly needs its own copy.
ant_sma_hole=6.5; ant_sma_panel_t=3; ant_sma_cavity=14;
ant_sma_boss_d=22; ant_sma_boss_h=10;


// The plate and the shell meet at a butt joint; neither may intrude on the
// other.
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
// ---- antenna mount ----------------------------------------------------
else if (check=="ant_inserts_open") {     // positive control: bosses bored
  difference() {
    for (i=[0:n_ant_bolts-1]) { a=i*360/n_ant_bolts + 30;
      translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), 0])
        cylinder(d=3.0, h=back_post_h); }
    back_plate();
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
