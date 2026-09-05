// ============================================================
// FlightWall Enclosure — 3-piece stack
//   1. front_trim  — sits IN FRONT of the glass, overlaps its
//                    outer black border, screws pass through it
//   2. retainer    — sits BEHIND the glass, the glass rests on
//                    this ring's front face
//   3. shell (case)— deep body housing Pi/dongle/wiring, has
//                    heat-set insert posts the screws thread into
//
// Assembly order (front to back):
//   front_trim -> [glass] -> retainer -> shell
//   8 screws pass through front_trim's clearance holes, through
//   the retainer's clearance holes (both outside the glass
//   diameter, in the rim band — never through the glass itself),
//   and thread into heat-set inserts pressed into the shell posts.
// ============================================================

part = "preview"; // "front_trim" | "retainer" | "shell" | "preview" | "exploded"

// ---- Curve resolution ------------------------------------------------
// $fa/$fs rather than a fixed $fn. A fixed count makes the flats grow with
// the feature, so the biggest, most looked-at surfaces come out roughest: at
// $fn=96 this shell's 223mm rim carried 7.3mm flats and the cradle 8.2mm,
// while every 3mm screw hole also got 96 sides it had no use for. $fs caps
// the chord -- the width of one flat, which is what the eye reads as
// faceting -- so a big curve gets the facets and a small hole does not.
//
// This is the one design here that has actually been printed, so the small
// fit-critical features keep their own explicit $fn below and are untouched.
// What changes is the geometry without an explicit setting, and the four
// wide arcs. The effect on a 3.4mm clearance hole is 0.02mm on diameter --
// two hundredths, against a printer tolerance an order of magnitude larger.
$fs = 0.4;   // max chord in mm
$fa = 0.5;   // max degrees per fragment

// ---------- MEASURED VALUES ----------
panel_diameter    = 203.34;
panel_active      = 178.15;
panel_glass_depth = 6.45;   // whole panel module depth (glass + LCD stack) -- used only for the assembly preview/exploded view below, NOT the rabbet
glass_thickness   = 1.62;   // measured with calipers: just the glass sheet itself -- this is what the rabbet has to span
pcb_w = 108; pcb_h = 72;
mount_hole_x = 58; mount_hole_y = 49;

// ---------- MEASURE ON YOUR ASSEMBLED UNIT, THEN SET ----------
// Bumped 42 -> 56 to give the side-mounted speakers (45mm along this
// axis) room without touching the Pi/heatsink stack -- double check
// against your actual internal component height before printing; more
// depth is free (bigger box), less isn't.
shell_depth = 56; // front glass face to back of tallest internal component

// ---------- DESIGN PARAMETERS ----------
rim = 10;                     // width of the ring band outside the glass edge
outer_dia = panel_diameter + 2*rim;   // 223.34mm — outer diameter of all 3 parts
wall = 3;

glass_overlap   = 4;          // how far front_trim / retainer overlap the glass edge
retention_opening = panel_diameter - 2*glass_overlap; // 195.34mm — what's left visible

front_trim_h  = 4;            // front trim thickness
retainer_h    = 4;            // retainer ring thickness
lip_height    = 6;            // shell's front lip (glass + retainer seat here)

screw_r = panel_diameter/2 + rim/2;   // screw ring sits centered in the rim band
n_screws = 8;
screw_clear_dia = 3.4;        // M3 clearance hole (front_trim + retainer)
insert_hole_dia = 4.2;        // M3 heat-set insert hole (shell posts)
post_od = 9;                  // outer diameter of each insert post in the shell

// ---------- RABBET (stepped bezel) + BOTTOM RELIEF ----------
// front_trim used to be one flat ring, entirely reliant on screw tension
// to squeeze the outer rim shut against the glass-thickness gap. Stepped
// instead: the inner band (overlapping the glass) stays at the normal
// front_trim_h thickness; the outer band (beyond the glass, out in the
// `rim`) protrudes an extra rabbet_depth further back -- exactly the
// glass's own thickness -- so it reaches retainer/shell's shelf flush,
// with a real mechanical stop instead of needing to be forced shut.
// (Was wrongly set to panel_glass_depth -- the whole panel module's
// depth, 6.45mm -- which stepped the outer band back far more than the
// 1.62mm glass sheet it's actually meant to span, leaving a gap instead
// of a flush seat. glass_thickness is the real, calipers-measured value.)
rabbet_depth = glass_thickness;

// The display module's driver board (touch + speaker FPC connectors) is
// taped directly to the back of the glass near its edge, at the bottom of
// the panel -- there's no room there for retainer's usual glass-overlap
// band. Relieved locally across just this arc instead of trying to keep
// a uniform rim everywhere. Same "270deg = -Y = bottom" convention
// exhaust_skip_deg already uses below for the cable-exit arc.
relief_center_deg = 270;
relief_arc_deg    = 50;

// How much of the old lip_height is left, once retainer gets its own
// dedicated shelf to sit on (see shell(), below) instead of overlapping
// the insert posts. Posts shrink to this height so they stay clear of
// retainer's Z-range entirely -- retainer's 3.4mm screw holes were never
// going to clear a 9mm-diameter post otherwise.
shelf_h = lip_height - retainer_h;

// Desk-stand build now (not primarily wall-hung), so the power + antenna
// pass-throughs move to the back FLOOR disc (world Z=0..wall) instead of
// the old radial side-wall holes -- easier to reach and keeps them off
// to one side, close together, out of the way of the PCB standoffs.
usbc_hole_dia      = 23;   // Adafruit #4218 round panel-mount USB-C: needs 21.5-27mm, ~29.5mm OD barrel/nut
antenna_hole_dia   = 6.5;  // generic SMA-F/F bulkhead panel jack: 1/4-36 thread, ~6.3mm hole, ~9.5mm hex nut
// ---- Removable back plate --------------------------------------------
// The back was a fixed floor with the electronics standing on it, which
// meant the only way to a Pi was through the glass. It is now a separate
// screwed plate, and everything that stood on the floor went with it: the
// PCB standoffs, the fan mount, the intake and fan grilles, and the two
// cable glands. Undo eight screws and the whole tray lifts out as one
// assembly rather than the case having to be opened from the front.
//
// No locating spigot. A ring into the bore is the obvious way to register a
// plate like this, and it lands exactly where the eight screw posts already
// are -- the posts straddle the bore wall, so any ring thick enough to
// locate would have to be notched eight times to clear them. Eight screws
// on a 213mm circle locate it perfectly well on their own.
back_plate_t   = 3;    // same as the floor it replaces
back_post_h    = 9;    // insert post standing inside the case
back_insert_d  = 8;    // how deep the heat-set insert hole is drilled

back_holes_x       = 60;   // shared X position, tucked toward one side
back_holes_y1      = -20;  // USB-C
back_holes_y2      = 6;    // antenna, spaced just enough to clear both nuts

// ---------- RETRO SONAR/RADAR STYLING ----------
// A ring of raised "rivets" just behind the front lip, and a couple of
// raised horizontal ribs around the body -- reads as an old bolted
// instrument housing rather than a smooth modern shell.
n_rivets      = 24;
rivet_dia     = 4;
rivet_h       = 1.4;
rivet_z       = shell_depth - lip_height - 6;

rib_h    = 2.2;      // how far each rib stands proud of the wall
rib_w    = 5;         // width (in Z) of each rib band
rib_z_list = [10, 22]; // Z positions of the two ribs
// The ribs stand 2.2mm proud but the cradle bore only clears the case by
// cradle_clearance (1mm), so a full ring would jam against the arms/keel
// -- the case would perch on its ribs instead of seating. Limited to the
// TOP arc, clear of the whole cradle contact zone; the bottom of the case
// is hidden inside the stand anyway, so nothing is lost visually.
rib_a0   = 340;      // start angle
rib_arc  = 220;      // 340deg -> 200deg, i.e. everything except the cradle zone


// ---------- ANTENNA MOUNT (top of case) ----------
// A turret standing proud of the case wall at the top (local +Y, same
// side as the keyholes). Its socket face is counter-tilted forward by
// stand_angle so that once the whole case leans back by stand_angle on
// its desk stand, the two tilts cancel and the antenna ends up truly
// vertical in real-world space, not leaning back with the case.
//
// The antenna's actual mount (a magnetic base you thread the antenna
// into, with the coax connector living inside that thread) isn't
// something to reverse-engineer and 3D-print blind -- instead this is
// a friction-fit socket sized ~1.5mm over the measured 31.5mm base,
// with a center pass-through sized for a generic SMA-F/F bulkhead
// jack (buy one, thread it in from inside) that the antenna's base can
// land on directly if it does turn out to be SMA-compatible.
antenna_socket_dia    = 33;
antenna_socket_depth  = 6;
antenna_turret_dia    = 42;
antenna_turret_len    = 18;   // how far the turret stands proud of the case wall
antenna_bulkhead_hole = 6.5;  // generic SMA bulkhead panel-mount hole
// The base's coax exits RADIALLY from the rim, not down through the
// bottom, so a plain axial hole left the wire pinched under the base with
// nowhere to go but down the outside of the case. Replaced by a slot that
// runs from the turret axis out past the socket wall and straight through
// into the cavity: the wire drops out of the base sideways, into the
// notch, and the connector passes through into the case in one short run.
// Sized for the connector (~8mm across) to pass, not just the cable.
antenna_cable_dia = 9;
antenna_cable_off = 14;   // reach from axis; socket wall is at r=16.5, turret at r=21

// ---------- SPEAKERS (Waveshare 8ohm 5W, stereo pair) ----------
// 100 x 45 x 21mm, mounting holes at 92mm (long axis) x 36mm (short
// axis) spacing. The 100mm long axis has to run tangentially (around
// the case), not through its depth -- shell_depth (56mm) is the only
// axis with room for the 45mm short axis. Each speaker sits on a
// bracket that bridges from the curved side wall inward to a flat
// mounting face, firing outward through a grille patch cut straight
// through the wall right in front of it. One per side (0deg / 180deg
// -- left/right when viewed face-on), clear of the antenna turret
// (top), the cable relief arc (bottom), and the keyholes (also top).
speaker_w = 100; speaker_d = 45; speaker_h = 21;
speaker_hole_x = 92; speaker_hole_y = 36;
speaker_screw_dia = 2.6;     // self-tapping into printed bosses
speaker_boss_dia  = 6;
speaker_boss_h    = 4;
speaker_bracket_depth = 15;  // how far inboard of the wall the flat mounting face sits
speaker_angles = [0, 180];

// grille: a patch of small round holes through the wall in front of
// each speaker's face
grille_hole_dia   = 2.5;
grille_pitch      = 4.5;
grille_w = 90; grille_h = 40; // slightly inset from the full speaker footprint

// ---------- MOUNTING: wall keyholes + optional desk stand ----------
// Two keyhole slots on the back (floor) let the case hang flush on
// two wall screws. A separate desk-stand piece plugs its two pegs
// into the same keyhole openings for desk use — same two holes,
// two different accessories.
keyhole_x = 40;              // +/- from center
keyhole_y = 70;              // up from center (near the top of the back, so it hangs right)
keyhole_pad_dia = 24;        // local thickened boss so there's enough material for the pocket
keyhole_pad_thickness = 10;  // thickness of that boss (vs. the thin 3mm general wall)
keyhole_head_dia = 10;       // wide opening — screw head (or stand peg) goes in here
keyhole_head_depth = 6;      // how deep the wide opening is cut, from outside in
keyhole_slot_w = 5;          // narrow channel width — screw shank slides in here
keyhole_slot_len = 18;       // length of the narrow channel, extending upward from the head
keyhole_slot_depth = 5;      // shallower than the head — leaves a catch lip behind it

stand_angle = 18;            // degrees the case leans back from vertical when desk-mounted

// ---------- DESK CRADLE ----------
// Replaces the old peg-into-keyhole stand (two small pegs taking all
// the load -- flimsy). Instead: two ring-arc arms shaped to the case's
// own outer curve, cradling it by broad surface contact under and
// partway up each side, gravity-seated on a solid plinth. No pegs, no
// keyholes involved -- the case just rests in it.
cradle_clearance = 1;                      // radial clearance over the case's outer surface
cradle_id  = outer_dia + 2*cradle_clearance;
cradle_od  = cradle_id + 26;               // arm thickness (radial)
cradle_arc = 130;                          // degrees of arc each arm wraps: 65deg either side
                                            // of straight-down, so it stops 25deg SHORT of the
                                            // equator. (An earlier comment here claimed it went
                                            // "past horizontal so the case can't roll out" --
                                            // it does not, and that is not what retains the
                                            // case. The bowl only cups it; the axial lock is
                                            // the retention rails. Lifting straight up is meant
                                            // to work -- that's how you take it off the stand.)
arm_w   = 16;                              // width of each arm along the case's depth axis
arm_gap = 26;                              // gap between the two arms
base_w = outer_dia*0.86; base_d = 150; base_h = 16;
// ---------- CRADLE STYLING ----------
// The arms were bare ring segments ending in sawn-off square faces, which
// read as unfinished next to the case's riveted, ribbed body -- and the tips
// are exactly what the user looks at head-on. Two additions, both purely
// additive so neither touches the bore or the retention geometry:
//   - rounded caps on every arm tip, turning a cut edge into a forged one
//   - a rivet arc across the FRONT arm's outward face, echoing the ring of
//     rivets around the case itself (same rivet_dia/rivet_h)
cradle_rivets      = 7;
cradle_rivet_inset = 14;  // degrees held back from each tip so none sit on the round

keel_arc   = 46;   // arc (deg) of the solid keel under the bowl
keel_reach = 80;   // how far the keel extends radially outward (trimmed at the desk plane)

// ---------- CRADLE RETENTION RAILS ----------
// The cradle bowl holds the case radially but did nothing axially: with
// the bowl's axis tilted stand_angle from horizontal, gravity puts a
// sin(18deg) ~= 0.31g component straight down that axis, and the case
// simply slid backwards out of the arms. These two rails sit just inboard
// of each arm's inner face, so the arms are trapped between them and the
// case can no longer slide either way. Positions are derived from the
// stand's own arm_gap, so the two parts stay matched by construction.
arm_a_inner = shell_depth/2 - arm_gap/2;   // z where arm A's inboard face lands
arm_b_inner = shell_depth/2 + arm_gap/2;   // z where arm B's inboard face lands
retain_clear = 0.5;   // fore/aft slop, per side
retain_w     = 4;     // rail width in Z
retain_h     = 4;     // proud of the wall: 1mm crosses the bore clearance,
                       // leaving 3mm actually engaging the arm's inner face
// split around the keel (which is full-depth at the very bottom), so the
// rails grab the two flanks of each arm instead of fouling the keel
retain_segs = [[207, 38], [295, 38]];   // [start angle, arc] per segment

// ---------- VENTILATION ----------
// The active cooler's fan faces INTO the shell cavity (away from
// the display), pulling air in from behind and exhausting outward
// at the base of the heatsink. So: intake on the rear floor,
// centered on the fan (which sits over the Pi's mount pattern,
// centered at the origin); exhaust as slots around the side wall.
intake_dia   = 54;   // covers the fan + heatsink footprint with margin
intake_hole  = 3;    // individual intake hole diameter
intake_pitch = 6;    // spacing between intake holes

// ---------- 30mm FAN (CanaKit 5V PWM, 30x30, 25mm hole pitch) ----------
// Mounted flat on the back floor above the Pi, drawing outside air in
// through its own grille. Placed clear of the Pi footprint (+/-54 x +/-36),
// and the USB-C / antenna holes (x=60).
// Stood UPRIGHT on a bracket just outside the Pi's +Y edge, axis
// horizontal, blowing -Y straight across the top of the Pi and its
// heatsink -- rather than lying flat on the floor, which only pushed air
// at the screen and stirred the cavity. Fresh air enters the floor grille
// directly behind it and is drawn through the bracket's opening.
fan_size = 30; fan_hole_pitch = 25;
fan_plate_y = 50;      // plate plane: clear of the Pi (ends y=36), clear of the wall
fan_plate_t = 3;
fan_plate_z0 = wall;   // stands off the floor's top face
fan_plate_h  = 35;
fan_plate_w  = 36;
fan_open_dia = 28;     // throat the fan blows through
fan_axis_z   = 21;     // opening centre: spans the Pi's component zone
fan_boss_dia = 6; fan_boss_h = 4; fan_screw_pilot = 2.5;
fan_grille_dia = 26;
fan_grille_pos = [0, 68];   // floor intake, immediately behind the fan

exhaust_slot_w = 2.2;
exhaust_slot_h = 12;
exhaust_z      = shell_depth / 2;  // mid-depth: lands in the 26mm gap BETWEEN the two
                                   // cradle arms, the one part of the lower wall that is
                                   // actually open to air when the case is in the stand
n_exhaust      = 24;
exhaust_skip_deg = 50; // only the keel arc now -- with the slots moved to
                       // mid-depth they clear the arms and rails entirely, so
                       // the lower flanks can breathe again instead of being
                       // blanked off.

// ============================================================
module screw_ring_holes(dia, h) {
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), -h/2 - 1])
            cylinder(d=dia, h=h+2);
    }
}

// ============================================================
// FRONT TRIM — sits on top of the glass, overlapping just its
// outer black border. Stepped (rabbeted): flat front face
// throughout for a uniform cosmetic look, but the underside steps
// down an extra rabbet_depth in the outer band (beyond the glass)
// so that band lands flush on retainer/shell's shelf. Local Z=0
// is defined as the glass's top face -- the inner (glass-overlap)
// band sits right at that face; the outer band's underside reaches
// down to local Z=-rabbet_depth, which is exactly retainer's top
// face once assembled (see the preview placement below).
// ============================================================
module front_trim() {
    total_h = front_trim_h + rabbet_depth;
    difference() {
        union() {
            cylinder(d=outer_dia, h=front_trim_h);
            translate([0,0,-rabbet_depth])
                difference() {
                    cylinder(d=outer_dia, h=rabbet_depth);
                    cylinder(d=panel_diameter, h=rabbet_depth);
                }
        }
        translate([0,0,-rabbet_depth-1])
            cylinder(d=retention_opening, h=total_h+2);
        for (i = [0:n_screws-1]) {
            a = i * 360/n_screws;
            translate([screw_r*cos(a), screw_r*sin(a), -rabbet_depth-1])
                cylinder(d=screw_clear_dia, h=total_h+2);
        }
    }
}

// ============================================================
// RETAINER — sits behind the glass; the glass rests on this
// ring's front face. Same opening as front_trim so the glass
// edge is captured evenly front and back. Relieved across
// relief_center_deg +/- relief_arc_deg/2 (see above) where the
// driver board's FPC connectors need the space instead.
// ============================================================
module retainer() {
    relief_r0 = retention_opening/2 - 1;
    relief_w  = panel_diameter/2 - retention_opening/2 + 2; // covers the glass-overlap band, +1mm margin each side
    difference() {
        cylinder(d=outer_dia - 2*wall, h=retainer_h);
        translate([0,0,-1])
            cylinder(d=retention_opening, h=retainer_h+2);
        screw_ring_holes(screw_clear_dia, retainer_h);
        rotate([0,0, relief_center_deg - relief_arc_deg/2])
            rotate_extrude(angle = relief_arc_deg)
                translate([relief_r0, -1])
                    square([relief_w, retainer_h+2]);
    }
}

// ============================================================
// VENT HOLE GENERATORS
// ============================================================
module intake_grille() {
    // triangular grid of small round holes within a circle, centered
    // on the fan/Pi mounting position
    n = ceil(intake_dia / intake_pitch) + 2;
    for (row = [-n:n]) {
        y = row * intake_pitch * 0.866; // sqrt(3)/2 for a triangular grid
        x_off = (row % 2 == 0) ? 0 : intake_pitch/2;
        for (col = [-n:n]) {
            x = col * intake_pitch + x_off;
            if (x*x + y*y < (intake_dia/2)*(intake_dia/2)) {
                translate([x, y, -1])
                    cylinder(d=intake_hole, h=wall+2, $fn=10);
            }
        }
    }
}

module exhaust_slots() {
    for (i = [0:n_exhaust-1]) {
        a = i * 360/n_exhaust;
        // skip the arc facing the cable exits (around -90deg / 270deg)
        skip = (a > 270 - exhaust_skip_deg/2 && a < 270 + exhaust_skip_deg/2);
        if (!skip) {
            translate([(outer_dia/2)*cos(a), (outer_dia/2)*sin(a), exhaust_z])
                rotate([0,0,a])
                    rotate([90,0,90])
                        linear_extrude(height=wall+2, center=true)
                            translate([-wall-1,0,0])
                                square([wall+2, exhaust_slot_w], center=true);
        }
    }
}

module keyhole_pocket() {
    // wide head opening (screw head / stand peg goes in here)
    translate([0,0,-1])
        cylinder(d=keyhole_head_dia, h=keyhole_head_depth+1);
    // narrow slot extending upward, shallower — catches the screw shank
    translate([0, keyhole_slot_len/2, -1])
        hull() {
            cylinder(d=keyhole_slot_w, h=keyhole_slot_depth+1);
            translate([0, keyhole_slot_len/2, 0])
                cylinder(d=keyhole_slot_w, h=keyhole_slot_depth+1);
        }
}

module keyholes() {
    for (x = [-keyhole_x, keyhole_x]) {
        translate([x, keyhole_y, 0]) keyhole_pocket();
    }
}

module keyhole_pads() {
    // local thickened boss on the inside of the floor so the pocket
    // above has enough material without punching into the cavity
    for (x = [-keyhole_x, keyhole_x]) {
        translate([x, keyhole_y, wall])
            cylinder(d=keyhole_pad_dia, h=keyhole_pad_thickness - wall);
    }
}

// ============================================================
// RETRO STYLING — rivets ringed around the front lip, and a couple of
// raised ribs around the body. Purely cosmetic, added to the shell's
// outer wall (never touches the glass/rabbet fit).
// ============================================================
module rivets() {
    for (i = [0:n_rivets-1]) {
        a = i * 360/n_rivets;
        translate([(outer_dia/2)*cos(a), (outer_dia/2)*sin(a), rivet_z])
            rotate([0,0,a])
                translate([-rivet_h/2, 0, 0])
                    rotate([0,90,0])
                        cylinder(d=rivet_dia, h=rivet_h, $fn=16);
    }
}

module ribs() {
    for (z = rib_z_list) {
        translate([0,0,z])
            rotate([0,0,rib_a0])
                rotate_extrude(angle=rib_arc)
                    translate([outer_dia/2, 0])
                        square([rib_h, rib_w]);
    }
}

// ============================================================
// FAN MOUNT — four bosses on the inside of the back floor for a 30x30
// fan, plus its own grille through the floor so it actually has
// something to breathe. Bosses are self-tapping pilots, not inserts:
// a 30mm fan weighs nothing and this keeps assembly simple.
// ============================================================
module fan_mount() {
    // vertical plate with the throat + 25mm-pitch bosses
    difference() {
        union() {
            translate([-fan_plate_w/2, fan_plate_y, fan_plate_z0])
                cube([fan_plate_w, fan_plate_t, fan_plate_h]);
            // thread bosses on the BACK face, so the fan lands flat on the
            // front face and screws pick up 3mm of plate + 4mm of boss
            for (dx = [-fan_hole_pitch/2, fan_hole_pitch/2])
                for (dz = [-fan_hole_pitch/2, fan_hole_pitch/2])
                    translate([dx, fan_plate_y + fan_plate_t, fan_axis_z + dz])
                        rotate([-90,0,0])
                            cylinder(d=fan_boss_dia, h=fan_boss_h, $fn=24);
            // two fins tying the plate down to the floor -- a bare 3mm
            // vertical wall this tall would flex and eventually snap
            for (x = [-15, 15])
                translate([x - 1.5, fan_plate_y + fan_plate_t, fan_plate_z0])
                    cube([3, 15, 14]);
        }
        // the throat
        translate([0, fan_plate_y - 1, fan_axis_z])
            rotate([-90,0,0])
                cylinder(d=fan_open_dia, h=fan_plate_t + 2);
        // screw pilots, right through plate and bosses
        for (dx = [-fan_hole_pitch/2, fan_hole_pitch/2])
            for (dz = [-fan_hole_pitch/2, fan_hole_pitch/2])
                translate([dx, fan_plate_y - 1, fan_axis_z + dz])
                    rotate([-90,0,0])
                        cylinder(d=fan_screw_pilot, h=fan_plate_t + fan_boss_h + 2, $fn=16);
    }
}

module fan_grille() {
    n = ceil(fan_grille_dia / intake_pitch) + 2;
    for (row = [-n:n]) {
        y = row * intake_pitch * 0.866;
        x_off = (row % 2 == 0) ? 0 : intake_pitch/2;
        for (col = [-n:n]) {
            x = col * intake_pitch + x_off;
            if (x*x + y*y < (fan_grille_dia/2)*(fan_grille_dia/2))
                translate([fan_grille_pos[0]+x, fan_grille_pos[1]+y, -1])
                    cylinder(d=intake_hole, h=wall+2, $fn=10);
        }
    }
}

// ============================================================
// CRADLE RETENTION RAILS — the axial stop that keeps the case from
// sliding back out of the stand. Sits in the open band between the two
// cradle arms, hugging each arm's inboard face. Split into two arc
// segments per rail so they straddle the keel rather than hitting it.
// Nothing here changes the stand: the printed cradle still fits.
// ============================================================
module cradle_rails() {
    for (seg = retain_segs)
        for (z = [arm_a_inner + retain_clear,
                  arm_b_inner - retain_clear - retain_w])
            translate([0,0,z])
                rotate([0,0,seg[0]])
                    rotate_extrude(angle=seg[1])
                        translate([outer_dia/2, 0])
                            square([retain_h, retain_w]);
}

// ============================================================
// SPEAKERS — one per side (0deg/180deg). A bracket bridges from the
// curved wall inward to a flat mounting face; screw_bosses land the
// speaker's real 92x36mm hole pattern; a grille patch is cut straight
// through the wall right in front of the speaker's face.
// ============================================================
module speaker_bracket(angle) {
    r_wall  = outer_dia/2 - wall;
    r_mount = r_wall - speaker_bracket_depth;
    z0 = (shell_depth - speaker_d)/2;

    rotate([0,0,angle]) {
        // Clipped to the case's own outer cylinder: the bracket is a FLAT
        // slab spanning a 100mm chord of a 223mm circle, so its corners sit
        // at r=119.6 -- 8mm PROUD of the 111.7mm wall. Unclipped they punched
        // straight through the shell as four bumps on the outside, and fouled
        // the cradle arms where they did. Clipping costs nothing: the corners
        // were outside the case, and the mounting bosses are far inboard.
        intersection() {
            hull() {
                translate([r_wall - 0.2, -speaker_w/2, z0])
                    cube([0.2, speaker_w, speaker_d]);
                translate([r_mount, -speaker_w/2, z0])
                    cube([0.2, speaker_w, speaker_d]);
            }
            cylinder(d=outer_dia, h=shell_depth);
        }
        for (dy = [-speaker_hole_x/2, speaker_hole_x/2])
            for (dz = [-speaker_hole_y/2, speaker_hole_y/2])
                translate([r_mount - speaker_boss_h, dy, z0 + speaker_d/2 + dz])
                    rotate([0,90,0])
                        difference() {
                            cylinder(d=speaker_boss_dia, h=speaker_boss_h, $fn=16);
                            translate([0,0,-0.1]) cylinder(d=speaker_screw_dia, h=speaker_boss_h+0.2, $fn=12);
                        }
    }
}

module speaker_grille(angle) {
    // The holes have to clear BOTH solids in the sound path, not just the
    // outer wall: speaker_bracket's hull fills the full
    // speaker_bracket_depth from its mounting face (r_mount) out to the
    // wall's inner surface, so a cut sized to `wall` alone drilled the
    // wall and then dead-ended against that slab -- open from outside,
    // completely blocked from inside. Cutting from r_mount outward makes
    // it a real through-path. Starting exactly at r_mount also keeps the
    // four mounting bosses intact: they sit INBOARD of that face
    // (r_mount - speaker_boss_h .. r_mount), so the cut only meets their
    // outer end plane and removes no boss material.
    r_mount = outer_dia/2 - wall - speaker_bracket_depth;
    z0 = (shell_depth - speaker_d)/2;
    n_y = floor(grille_w / grille_pitch);
    n_z = floor(grille_h / grille_pitch);
    rotate([0,0,angle])
        for (iy = [0:n_y]) {
            dy = (iy - n_y/2) * grille_pitch;
            for (iz = [0:n_z]) {
                dz = (iz - n_z/2) * grille_pitch;
                translate([r_mount, dy, z0 + speaker_d/2 + dz])
                    rotate([0,90,0])
                        cylinder(d=grille_hole_dia,
                                 h=speaker_bracket_depth + wall + 3, $fn=10);
            }
        }
}

// ============================================================
// ANTENNA TURRET — top of the case, counter-tilted by stand_angle so
// the socket reads vertical once the whole case leans back on its
// stand. See variable block above for the reasoning.
// ============================================================
module antenna_turret_solid() {
    translate([0, outer_dia/2 - 1, shell_depth*0.55])
        rotate([stand_angle, 0, 0])
            rotate([-90,0,0])
                cylinder(d=antenna_turret_dia, h=antenna_turret_len);
}

module antenna_turret_cuts() {
    translate([0, outer_dia/2 - 1, shell_depth*0.55])
        rotate([stand_angle, 0, 0]) {
            translate([0,0,0])
                rotate([-90,0,0]) {
                    translate([0,0,antenna_turret_len - antenna_socket_depth])
                        cylinder(d=antenna_socket_dia, h=antenna_socket_depth+1, $fn=64);
                    // cable slot: +Y here maps to the case's -Z (its back),
                    // so the wire exits rearward, hidden behind the case
                    translate([0,0,-1])
                        hull() {
                            cylinder(d=antenna_cable_dia, h=antenna_turret_len+2, $fn=32);
                            translate([0, antenna_cable_off, 0])
                                cylinder(d=antenna_cable_dia, h=antenna_turret_len+2, $fn=32);
                        }
                }
        }
}

// ============================================================
// DESK CRADLE — a solid plinth with two ring-arc arms shaped to the
// case's own outer curve. The case rests IN the cradle by gravity and
// broad surface contact (each arm wraps 130deg, well past horizontal
// on both sides, so it can't roll out) -- no pegs, no keyholes, no
// small stress points carrying the load. Print separately; the case
// simply sets down into it.
// ============================================================
module cradle_arm(depth_offset) {
    arm_t = (cradle_od - cradle_id) / 2;      // radial thickness of the arm
    r_mid = (cradle_id + cradle_od) / 4;      // mid-thickness radius
    // ring segment: lies flat in the XY plane, hole-axis along local Z,
    // arc centered on "straight down" (270deg) so it cradles the
    // underside and wraps partway up both sides
    translate([0, 0, depth_offset]) {
        rotate([0,0, 270 - cradle_arc/2])
            rotate_extrude(angle = cradle_arc)
                translate([cradle_id/2, 0])
                    square([arm_t, arm_w]);
        // Rounded tip caps. Diameter is exactly the arm's own thickness and
        // they sit on the mid-thickness radius, so they span cradle_id/2 to
        // cradle_od/2 precisely -- rounding the tip in plan view without
        // narrowing the bore by a thousandth.
        for (a = [270 - cradle_arc/2, 270 + cradle_arc/2])
            translate([r_mid*cos(a), r_mid*sin(a), 0])
                cylinder(d=arm_t, h=arm_w);
    }
}

// Rivet arc across the front arm's outward face -- the surface the user
// actually looks at. Same diameter and proud height as the case's rivets, so
// the two read as one family. Held clear of the tips (cradle_rivet_inset) so
// none straddle the new rounds.
module cradle_front_rivets() {
    r_mid  = (cradle_id + cradle_od) / 4;
    z_face = arm_gap/2 + arm_w;               // outward face of the FRONT arm
    a0     = 270 - cradle_arc/2 + cradle_rivet_inset;
    span   = cradle_arc - 2*cradle_rivet_inset;
    for (i = [0:cradle_rivets-1]) {
        a = a0 + i * span / (cradle_rivets - 1);
        translate([r_mid*cos(a), r_mid*sin(a), z_face])
            cylinder(d=rivet_dia, h=rivet_h, $fn=16);
    }
}

module stand() {
    // The arms are ring segments built in the XY plane (axis along Z).
    // To cradle a cylinder lying on its side, that axis has to end up
    // HORIZONTAL -- hence rotate([90 - stand_angle, 0, 0]): the 90
    // lays the ring's axis over into the horizontal, and subtracting
    // stand_angle tips it back so the case leans at the same angle the
    // antenna turret is counter-tilted for. (A previous pass rotated by
    // only stand_angle, leaving the rings nearly flat -- they floated
    // above the plinth, never touching it: Genus -2, three loose solids.)
    // Lifted so the arc's outer bottom lands just inside the plinth's
    // top face, giving a solid fused joint rather than a tangent kiss.
    arm_lift = base_h + cradle_od/2 - 3;

    // everything gets trimmed flat at the desk plane (z=0) -- the keel
    // is generated generously and simply cut off where the desk is,
    // rather than trying to solve its exact intersection analytically
    intersection() {
    translate([-400, -400, 0]) cube([800, 800, 400]);
    union() {
        // plinth, flat on the desk
        translate([-base_w/2, -base_d/2, 0])
            cube([base_w, base_d, base_h]);

        // shallow grooves across the plinth's front face, echoing the
        // case's own ribs for a matching look
        for (z = [base_h*0.35, base_h*0.65]) {
            translate([-base_w/2 - 1, -base_d/2 - 1, z])
                cube([base_w + 2, 3, 2]);
        }

        // the two cradle arms, laid horizontal and tipped back, plus a
        // keel below the bowl tying them to each other and down into
        // the plinth. The keel starts at cradle_id/2 -- the bowl's own
        // inner radius -- so by construction it can never intrude into
        // the space the case occupies, however the tilt shifts things.
        // (Tilting means the rear arm alone hangs higher than the front
        // one; without this keel only the front arm reached the base.)
        translate([0, 0, arm_lift])
            rotate([90 - stand_angle, 0, 0]) {
                cradle_arm(-(arm_gap/2 + arm_w));
                cradle_arm(arm_gap/2);
                cradle_front_rivets();
                translate([0, 0, -(arm_gap/2 + arm_w)])
                    rotate([0, 0, 270 - keel_arc/2])
                        rotate_extrude(angle = keel_arc)
                            translate([cradle_id/2, 0])
                                square([keel_reach, arm_gap + 2*arm_w]);
            }
    }
    }
}

// ============================================================
// SHELL (case) — houses Pi, dongle, wiring. Front lip has 8
// posts with heat-set insert holes that the screws thread into.
// Vented: intake grille on the floor (under the fan), exhaust
// slots around the side wall. Two keyhole slots for wall mount
// (or the separate stand accessory, for desk use).
// ============================================================
// Eight insert posts standing inside the case at the back, mirroring the
// front's. They straddle the bore wall -- centred on screw_r, which is 2mm
// outboard of the inner face -- so each one merges into the wall rather
// than standing free.
module back_posts() {
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), 0])
            cylinder(d=post_od, h=back_post_h);
    }
}

// Drilled in shell()'s difference stage, NOT inside back_posts(). The
// speaker brackets reach the wall at 0 and 180 degrees, exactly where two of
// these posts are, and at z 5.5 upward -- so a hole subtracted inside the
// post module gets unioned shut again by the bracket landing on top of it.
// Subtracting after everything is unioned is the only order that guarantees
// eight open holes. back_inserts_open in the checks proves it.
module back_post_holes() {
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), -0.01])
            cylinder(d=insert_hole_dia, h=back_insert_d);
    }
}

// ============================================================
// BACK PLATE — the electronics tray, screwed on like the faceplate
// ============================================================
module back_plate() {
    difference() {
        union() {
            translate([0,0,-back_plate_t])
                cylinder(d=outer_dia, h=back_plate_t);

            // Everything that used to stand on the floor. Their own
            // geometry is unchanged; it is only shifted down so what used
            // to sit on the floor's top face now sits on the plate's.
            for (x = [-mount_hole_x/2, mount_hole_x/2])
                for (y = [-mount_hole_y/2, mount_hole_y/2])
                    translate([x, y, 0])
                        difference() {
                            cylinder(d=7, h=8);
                            cylinder(d=2.5, h=9);
                        }
            // No fan mount. There was a plate here standing perpendicular
            // to the tray, carrying a 30mm fan; the fan goes on the Pi
            // instead. fan_mount() and its fan_plate_* variables are left
            // defined but unused, the same way the wall-mount keyhole code
            // above is, so putting it back is a one-line change.
        }
        // Clearance for the eight screws into the shell's back posts.
        for (i = [0:n_screws-1]) {
            a = i * 360/n_screws;
            translate([screw_r*cos(a), screw_r*sin(a), -back_plate_t-1])
                cylinder(d=screw_clear_dia, h=back_plate_t+2);
        }
        // USB-C power + antenna cable glands, off to one side and clear of
        // the standoffs, as they were on the floor.
        translate([back_holes_x, back_holes_y1, -back_plate_t-1])
            cylinder(d=usbc_hole_dia, h=back_plate_t+2);
        translate([back_holes_x, back_holes_y2, -back_plate_t-1])
            cylinder(d=antenna_hole_dia, h=back_plate_t+2);
        // The grilles cut a band from z=-1 to wall+1; shifted down by the
        // plate thickness that band covers the plate exactly.
        translate([0,0,-back_plate_t]) intake_grille();
        translate([0,0,-back_plate_t]) fan_grille();
    }
}

module shell() {
    difference() {
        union() {
            // Bored straight through: the back is a separate plate now.
            difference() {
                cylinder(d=outer_dia, h=shell_depth);
                translate([0,0,-1])
                    cylinder(d=outer_dia - 2*wall, h=shell_depth + 2);
            }
            back_posts();
            // keyhole_pads();  // wall-mount removed -- see keyholes() below
            rivets();
            ribs();
            cradle_rails();
            for (a = speaker_angles) speaker_bracket(a);
            antenna_turret_solid();
        }
        // keyholes();  // wall-mount removed: this is a desk-cradle build now,
        // and the back is a clean flat disc. The keyhole_*/keyholes()/
        // keyhole_pads() definitions above are left intact (unused) so
        // wall-mounting is a two-line change if it's ever wanted back.
        exhaust_slots();
        for (a = speaker_angles) speaker_grille(a);
        antenna_turret_cuts();
        back_post_holes();
    }

    // Continuous shelf for retainer to seat on -- replaces relying on the
    // 8 discrete posts alone, whose 9mm barrels would otherwise collide
    // with retainer's 3.4mm screw holes (the posts used to occupy the
    // exact same Z-range retainer sits in). Its top face (world Z =
    // shell_depth) is what front_trim's rabbeted outer band lands flush
    // against too. Relieved at the same bottom arc as retainer, so
    // there's a clear full-depth channel for the driver board's cabling.
    difference() {
        translate([0,0,shell_depth - lip_height])
            difference() {
                cylinder(d=outer_dia - 2*wall, h=shelf_h);
                cylinder(d=retention_opening, h=shelf_h+0.02);
            }
        rotate([0,0, relief_center_deg - relief_arc_deg/2])
            rotate_extrude(angle = relief_arc_deg)
                translate([retention_opening/2 - 1, shell_depth - lip_height - 1])
                    square([outer_dia/2 - retention_opening/2 + 2, shelf_h + 2]);
    }

    // insert posts, now only shelf_h tall so they sit entirely below the
    // shelf (and below retainer) instead of overlapping either
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), shell_depth - lip_height])
            difference() {
                cylinder(d=post_od, h=shelf_h);
                translate([0,0,shelf_h-8])
                    cylinder(d=insert_hole_dia, h=9);
            }
    }


    // No dongle pocket. There was a fitted open-topped tray on the floor
    // here; it did not work in practice -- the dongle plus its USB lead and
    // the antenna pigtail do not sit the way a rigid tray assumes, and it
    // fought the cable routing rather than helping it. The dongle now just
    // lies in the cavity, which is what actually happens anyway.
}

// ============================================================
if (part == "front_trim") front_trim();
else if (part == "retainer") retainer();
else if (part == "shell") shell();
else if (part == "back_plate") back_plate();
else if (part == "stand") stand();
else if (part == "test_antenna") {
    // small coupon around the antenna turret -- real shell() geometry,
    // just clipped to a local box so it prints in minutes, not hours
    intersection() {
        shell();
        translate([-40, 65, 0])
            cube([80, 70, 60]);
    }
}
else if (part == "test_speaker") {
    // small coupon around one speaker bracket + its grille (the 0deg
    // side); same real shell() geometry, clipped to a local box
    intersection() {
        shell();
        translate([75, -55, -1])
            cube([45, 110, shell_depth + 2]);
    }
}
else if (part == "exploded") {
    color("DimGray")    translate([0,0,shell_depth + 40]) front_trim();
    color("LightBlue",0.4) translate([0,0,shell_depth + 25]) cylinder(d=panel_diameter, h=panel_glass_depth); // glass, for reference
    color("SlateGray")  translate([0,0,shell_depth + 10]) retainer();
    color("SteelBlue")  shell();
}
else {
    // assembled preview -- retainer now seats on the shelf (world Z =
    // shell_depth - retainer_h to shell_depth), glass sits right on top
    // of retainer, and front_trim's local Z=0 (its inner, glass-overlap
    // band) lines up with the glass's own top face. front_trim's
    // rabbeted outer band then reaches back down exactly to shell_depth
    // -- the shelf's top face -- with no gap left to force shut.
    color("SteelBlue") shell();
    color("SlateGray") translate([0,0,shell_depth - retainer_h + 0.1]) retainer();
    color("LightBlue",0.4) translate([0,0,shell_depth + 0.1]) cylinder(d=panel_diameter, h=panel_glass_depth);
    color("DimGray") translate([0,0,shell_depth + panel_glass_depth + 0.1]) front_trim();
}
