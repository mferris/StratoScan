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
// 42 -> 56 gave the side-mounted speakers (45mm along this axis) room
// without touching the Pi/heatsink stack. 56 -> 61 is the FlyCatcher: it
// is a HAT, so it stacks onto the BACK of the Pi, and the Pi hangs off the
// LCD panel at the front -- which puts the HAT's pre-amp slide switches
// facing the back plate. At 56 they fouled it as the plate was screwed
// down, which is the worst kind of interference: everything appears to fit
// until the last two turns, and then it is loading the board.
//
// Deeper is nearly free here -- a bigger box, more filament, a longer
// print -- and too shallow is a case that cannot be closed without
// pressing on a switch. Measure YOUR stack before printing: this is the
// one number that has had to move every time the internals changed.
shell_depth_note = "56 -> 61 for the FlyCatcher HAT's pre-amp switches";
shell_depth = 61;           // front glass face to back of the tallest component

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

// ---- Back plate: locating lip ----------------------------------------
// A rib standing off the plate's inner face that drops into the shell bore,
// so the plate lands centred and square and holds itself there while the
// screws go in.
//
// It cannot be a continuous ring: the eight insert posts straddle the bore
// wall (posts span r=102.2..111.2, the wall is r=108.7..111.7), so a full
// ring at bore diameter would run through every one of them. Eight arcs, one
// per gap between posts.
back_lip_h    = 4;
back_lip_t    = 2;
back_lip_gap  = 0.35;
back_lip_lead = 1.2;
back_lip_skip = 9;

// ---- USB-C pass-through ----------------------------------------------
// ONE opening, replacing the separate USB-C power gland and SMA antenna
// gland that used to sit side by side. The antenna no longer needs a
// bulkhead here: its coax comes in through the antenna mount's cable bore.
//
// !!! THESE NUMBERS ARE A PLACEHOLDER AND MUST BE MEASURED !!!
// The listing for the panel-mount USB-C cable publishes no cutout
// dimensions, so these are the usual values for that style of part, not
// measured ones. Print part="usbc_gauge" -- a coupon carrying this cutout
// plus four neighbouring sizes -- and fit the connector before committing a
// whole back plate.
usbc_cut_w       = 11.0;
usbc_cut_h       = 6.5;
usbc_cut_r       = 1.2;
usbc_screw_pitch = 16.5;   // centre-to-centre of the two mounting screws
usbc_screw_dia   = 2.3;
usbc_cut_pos     = [60, -14];

// ---- Antenna-mount inserts (inside face) -----------------------------
// Bosses on the INNER face taking M3 heat-set inserts, so the mount screws
// into the plate rather than needing a nut held inside the case.
ant_insert_boss_od = 7.5;
ant_insert_bore    = 4.0;
ant_insert_h       = back_insert_d + 1;

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
// Moved from [0, 68]. The antenna mount's flange is a 40mm disc centred at
// y=88, so at +68 this grille sat underneath it from y=68 to y=81, venting
// into the back of a solid disc. Directly opposite it is clear of the
// flange, the standoffs, the USB-C window and the screw ring.
fan_grille_pos = [0, -68];

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
            if (x*x + y*y < (intake_dia/2)*(intake_dia/2))
                translate([x, y, -1]) cylinder(d=intake_hole, h=wall+2, $fn=10);
        }
    }
}

module exhaust_slots() {
    for (i = [0:n_exhaust-1]) {
        a = i * 360/n_exhaust;
        skip = (a > 270 - exhaust_skip_deg/2 && a < 270 + exhaust_skip_deg/2);
        if (!skip)
            translate([(outer_dia/2)*cos(a), (outer_dia/2)*sin(a), exhaust_z])
                rotate([0,0,a]) rotate([90,0,90])
                    linear_extrude(height=wall+2, center=true)
                        hull() {
                            translate([0,  exhaust_slot_h/2 - exhaust_slot_w/2]) circle(d=exhaust_slot_w);
                            translate([0, -exhaust_slot_h/2 + exhaust_slot_w/2]) circle(d=exhaust_slot_w);
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
                cylinder(d=fan_open_dia, h=fan_plate_t + 2, $fn=48);
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
// ANTENNA TURRET — REMOVED, replaced by the bolt-on antenna mount on the
// back plate (see below), which is the same part the kitten build uses.
//
// The turret grew the socket out of the top of the case wall. The mount
// puts it on the removable plate instead, so both cases now carry the
// identical antenna assembly and the identical back plate, and the antenna
// angle can be changed without reprinting a shell.
//
// antenna_turret_solid()/antenna_turret_cuts() are left defined but unused,
// the same treatment the wall-mount keyhole code above gets, so putting the
// turret back is a two-line change in shell().
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

// ============================================================
// ANTENNA MOUNT — bolt-on, shared with the kitten build
//
// Identical geometry in both designs: both cases are the same 223.34mm
// diameter and both lean back by the same stand_angle (18), so one mount
// serves both and the back plates are interchangeable.
//
// The arm reaches STRAIGHT BACK from the plate, and only then does a barrel
// rise from its end along the antenna's own axis. That two-stage shape is
// forced rather than styled: a barrel coaxial with the antenna and rooted on
// the plate would climb toward the case the whole way and run into it. An
// earlier attempt hulled a pad on the plate to a disc at the mouth, which
// produced a cone with the socket bored into its flank -- the antenna
// pointed sideways and down instead of up.
// ============================================================
ant_stub_dia   = 26;
ant_stub_len   = 30;
ant_barrel_len = 14;
ant_flange_d   = 40;
ant_flange_t   = 4;
ant_bolt_pcd   = 30;
ant_bolt_d     = 3.4;
n_ant_bolts    = 3;
ant_mount_y        = 88;
// The socket the antenna's base sits down into, and the rim around it --
// "the lip" -- that stops the base falling out sideways once it is in.
//
// This was 33, and a printed one showed why that is wrong: the base is a
// flared cone slightly wider than 33 where it needs to pass, so it never got
// under the rim at all. It perched on top and tipped over, while the cable
// underneath ran through perfectly.
//
// ant_socket_lead is what makes it leverageable: a chamfer at the mouth, so
// the base can be tipped in on one side and rolled under the far side instead
// of having to drop in dead square.
// Sized to the measured base, which is 31.25mm across the flared bottom --
// its widest point. That is the whole story of this socket: it was 33mm
// originally, which already had 1.75mm of clearance, so THE BORE WAS NEVER
// WHAT STOPPED IT. Two guesses said otherwise (a base bigger than the hole,
// then a cone with a wider flare higher up) and both were wrong.
//
// The photograph shows what is actually happening: the skirt is down in the
// socket on one side, and on the other the coax connector is sitting in the
// notch where the cable passage breaks through the wall, propping the base up
// and tilting it. The obstruction is underneath the base, not around it.
//
// Hence ant_relief_*: a clear space below the socket floor for the connector
// and whatever strain relief comes with it, so the base can come down the
// last few millimetres instead of resting on its own cable.
ant_base_dia       = 31.25;  // MEASURED, across the flared bottom
ant_base_clear     = 1.75;   // drops in; no levering, nothing to snap off
ant_socket_dia     = ant_base_dia + ant_base_clear;   // 33.0
ant_socket_depth   = 8;
ant_relief_dia     = 18;     // a little room under the floor, for the moulding
ant_relief_h       = 4;      // on the underside of the base

// THE CABLE LEAVES THE SIDE OF THE BASE, 7.98mm above its bottom -- measured.
// That is the whole problem, and nothing about the bore was ever going to fix
// it: the lead cannot go down through the socket floor because the base is
// sitting on the floor. It has to leave sideways.
//
// The printed mount had no way out, so the connector ended up jammed in the
// notch where the cable passage happens to break through the wall, holding
// the base up at an angle. That notch was an accident of the geometry. This
// is the same idea done deliberately and made big enough.
//
// The slot faces local +Y in the antenna's frame, which points back down
// toward the plate, so the lead drops straight into the passage that was
// already there rather than having to be led around the barrel.
ant_cable_slot_w   = 7;      // the lead is ~4mm; this is not a tight fit
ant_cable_exit_h   = 7.98;   // MEASURED, base bottom to where the lead leaves
ant_socket_lead    = 1.2;
ant_boss_dia       = 48;   // 42 -> 45 -> 48; the rim is the part that broke
// The coax CONNECTOR has to pass through here, not just the cable. Measured
// at 9.15mm across its widest point, so the bore is that plus clearance --
// a 9mm bore (what this was) will not pass a 9.15mm connector at all.
ant_conn_dia       = 9.15;
ant_cable_dia      = ant_conn_dia + 1.85;   // 11.0

// ---- the SMA bulkhead variant ----------------------------------------
// A second antenna mount, sharing this one's bolt circle, arm and
// counter-tilt, but ending in a panel-mount SMA jack instead of a socket cut
// to one particular base.
//
// The socket above fits exactly one antenna: the FlightAware desktop puck
// these dimensions were measured from. That was the right call while it was
// the only antenna in the room, and the wrong shape to ship three units on --
// it makes the case pick the antenna. A bulkhead inverts that. Anything with
// an SMA plug screws on: the same puck, a tuned whip standing straight off
// the back, or coax running to an antenna on a mast, which is where the
// reception actually is. Measured on this hardware, an indoor puck saw 1
// aircraft while a properly sited antenna saw 14 of the same sky.
//
// The counter-tilt is the part that must not change. ADS-B is vertically
// polarised, and ant_axis_frame() is what keeps the jack -- and so whatever
// screws into it -- vertical while the case leans back in its cradle.
ant_sma_hole    = 6.5;   // 1/4-36 UNS thread measures 6.35mm; this is the panel hole
ant_sma_panel_t = 3;     // bulkhead jacks are threaded for about 1.5-3mm of panel
ant_sma_cavity  = 14;    // behind the panel: the nut, and room for the coax to turn
ant_sma_boss_d  = 22;    // no 33mm base to hold any more, so the boss shrinks
ant_sma_boss_h  = 10;    // panel sits at 7-10, clear of the cable bore's 6mm top


function ant_barrel_base() = [0, ant_mount_y, -back_plate_t - ant_stub_len];

// rotate([-90,0,0]) lays a +Z cylinder along +Y; rotate([stand_angle,0,0])
// then tilts it back by exactly what the cradle tilts the case forward, so
// the two cancel and the antenna stands vertical on the desk.
module ant_axis_frame() {
    translate(ant_barrel_base())
        rotate([stand_angle, 0, 0])
            rotate([-90, 0, 0])
                children();
}

// Bolt positions, shared by the mount's flange and the plate it lands on so
// the two cannot drift apart. +30 rather than +90: at +90 one bolt points
// straight up the plate and its insert boss runs into the locating lip.
module ant_bolt_holes(h, z0) {
    for (i = [0 : n_ant_bolts - 1]) {
        a = i * 360/n_ant_bolts + 30;
        translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), z0])
            cylinder(d=ant_bolt_d, h=h);
    }
}

// The passage the connector travels, in two pieces that are hulled into one.
//
// The straight run alone was the bug. It is bored along the PLATE's normal,
// while the socket above it is tilted by stand_angle -- so the socket floor
// met the bore at an angle and left a shoulder across the opening. That
// shoulder is the lip the antenna's base lands on, and no amount of widening
// the straight bore removes it, because the two are not coaxial.
//
// So the socket floor is opened along the ANTENNA's own axis and hulled down
// to the straight run: one continuous passage, no step anywhere across it.
module ant_cable_bore(z_top) {
    // straight run, out through the arm and the plate
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len - 2])
        cylinder(d=ant_cable_dia, h=ant_stub_len + z_top + 2);
    // socket floor, opened square to the antenna and swept onto that run
    hull() {
        translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
            cylinder(d=ant_cable_dia, h=0.01);
        ant_axis_frame()
            translate([0, 0, ant_barrel_len - ant_socket_depth - 0.01])
                cylinder(d=ant_cable_dia, h=0.02);
    }
}

module antenna_mount() {
    difference() {
        union() {
            translate([0, ant_mount_y, -back_plate_t - ant_flange_t])
                cylinder(d=ant_flange_d, h=ant_flange_t);
            translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
                cylinder(d=ant_stub_dia, h=ant_stub_len);
            ant_axis_frame() translate([0,0,-6])
                cylinder(d=ant_boss_dia, h=ant_barrel_len + 6);
        }
        // chamfered mouth, so the base can be tipped in and levered under the
        // rim rather than having to go in perfectly square
        ant_axis_frame() {
            // the seat itself
            translate([0, 0, ant_barrel_len - ant_socket_depth])
                cylinder(d=ant_socket_dia, h=ant_socket_depth + 1);
            // lead-in at the mouth
            translate([0, 0, ant_barrel_len - ant_socket_lead])
                cylinder(d1 = ant_socket_dia,
                         d2 = ant_socket_dia + 2*ant_socket_lead,
                         h  = ant_socket_lead + 1);
            // a little relief under the floor for whatever is moulded into
            // the underside of the base
            translate([0, 0, ant_barrel_len - ant_socket_depth - ant_relief_h])
                cylinder(d=ant_relief_dia, h=ant_relief_h + 0.1);
            // the way out for the lead: a slot through the socket wall, from
            // the floor up past the rim, facing the plate
            translate([0, 0, ant_barrel_len - ant_socket_depth])
                translate([-ant_cable_slot_w/2, 0, 0])
                    cube([ant_cable_slot_w,
                          ant_boss_dia/2 + 1,
                          ant_socket_depth + ant_socket_lead + 1]);
        }
        ant_cable_bore(0);
        ant_bolt_holes(ant_flange_t + 2, -back_plate_t - ant_flange_t - 1);
        // nothing may stand proud of the plate's outer face
        translate([-300, -300, -back_plate_t]) cube([600, 600, 600]);
    }
}

module antenna_mount_sma() {
    difference() {
        union() {
            // flange and arm are the socket mount's, unchanged: same bolt
            // circle, same inserts, same plate. Only the far end differs.
            translate([0, ant_mount_y, -back_plate_t - ant_flange_t])
                cylinder(d=ant_flange_d, h=ant_flange_t);
            translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
                cylinder(d=ant_stub_dia, h=ant_stub_len);
            ant_axis_frame() translate([0,0,-6])
                cylinder(d=ant_sma_boss_d, h=ant_sma_boss_h + 6);
        }
        ant_axis_frame() {
            // the jack's hole, through the panel at the top of the boss
            translate([0, 0, ant_sma_boss_h - ant_sma_panel_t - 0.01])
                cylinder(d=ant_sma_hole, h=ant_sma_panel_t + 0.02, $fn=48);
            // the space behind it. Deliberately reaches DOWN to -6 so it
            // meets the cable bore's sweep rather than relying on the two
            // happening to touch: an unconnected cavity looks identical in
            // preview and is a solid wall in the print.
            translate([0, 0, -6])
                cylinder(d=ant_sma_cavity,
                         h=ant_sma_boss_h - ant_sma_panel_t + 6);
        }
        ant_cable_bore(0);
        ant_bolt_holes(ant_flange_t + 2, -back_plate_t - ant_flange_t - 1);
        // nothing may stand proud of the plate's outer face
        translate([-300, -300, -back_plate_t]) cube([600, 600, 600]);
    }
}



// A test coupon for the socket, so the right diameter costs ten minutes
// instead of a whole mount. Five sockets, 34 to 38mm, each with the real
// lead-in chamfer, the real depth and the real cable hole underneath, so the
// antenna base sits exactly as it will on the mount. The rim of each carries
// a number of notches equal to its position: one notch is 34, five is 38.
//
// Print it, find the smallest socket the base will lever into and sit square
// in, and set ant_socket_dia to that. Smallest, not easiest -- the rim is
// what stops the base falling sideways, so slack is not free.
module antenna_socket_gauge() {
    // Half-millimetre steps, bracketing the answer rather than spanning the
    // whole plausible range: a base reported as "slightly larger than 34"
    // needs 34.5 / 35 / 35.5 / 36 / 36.5, not 34 / 35 / 36 / 37 / 38. Change
    // gauge_from and gauge_step to re-aim it.
    gauge_from = 34.5; gauge_step = 0.5;
    n = 5; pitch = 52; t = ant_socket_depth + 3;
    for (i = [0 : n-1]) {
        d = gauge_from + i*gauge_step;
        translate([i*pitch - (n-1)*pitch/2, 0, 0])
            difference() {
                cylinder(d = d + 9, h = t);
                translate([0, 0, t - ant_socket_depth])
                    cylinder(d = d, h = ant_socket_depth + 1);
                translate([0, 0, t - ant_socket_lead])
                    cylinder(d1 = d, d2 = d + 2*ant_socket_lead,
                             h = ant_socket_lead + 1);
                translate([0, 0, -1]) cylinder(d = ant_cable_dia, h = t + 2);
                for (k = [0 : i])
                    rotate([0, 0, 210 + k*14])
                        translate([(d+9)/2, 0, t - 0.9])
                            cube([3, 1.4, 2], center = true);
            }
    }
}

module back_lip() {
    ri = outer_dia/2 - wall - back_lip_gap - back_lip_t;
    ro = outer_dia/2 - wall - back_lip_gap;
    span = 360/n_screws - 2*back_lip_skip;
    for (i = [0 : n_screws - 1])
        rotate([0, 0, i*360/n_screws + back_lip_skip])
            rotate_extrude(angle = span)
                polygon([[ri, 0],
                         [ro, 0],
                         [ro, back_lip_h - back_lip_lead],
                         [ro - back_lip_lead, back_lip_h],
                         [ri, back_lip_h]]);
}

module usbc_cutout() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1]) {
        linear_extrude(height = back_plate_t + 2)
            offset(r = usbc_cut_r) offset(delta = -usbc_cut_r)
                square([usbc_cut_w, usbc_cut_h], center = true);
        for (sx = [-1, 1])
            translate([sx * usbc_screw_pitch/2, 0, 0])
                cylinder(d = usbc_screw_dia, h = back_plate_t + 2);
    }
}

module ant_insert_bosses() {
    for (i = [0 : n_ant_bolts - 1]) {
        a = i * 360/n_ant_bolts + 30;
        translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), 0])
            cylinder(d = ant_insert_boss_od, h = ant_insert_h);
    }
}

// Two diameters on purpose: the insert pocket stops on a shoulder 1mm above
// the plate rather than running out through it, so the insert cannot be
// pressed too deep and the bolt still passes freely from outside.
module ant_insert_bores() {
    for (i = [0 : n_ant_bolts - 1]) {
        a = i * 360/n_ant_bolts + 30;
        translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), 0]) {
            translate([0, 0, 1])
                cylinder(d = ant_insert_bore, h = ant_insert_h);
            translate([0, 0, -back_plate_t - 1])
                cylinder(d = ant_bolt_d, h = back_plate_t + 2);
        }
    }
}

// A 5-minute test coupon: the real cutout flanked by four neighbours at
// +/-0.5 and +/-1.0mm. Fit the connector to it before printing a back plate.
module usbc_gauge() {
    difference() {
        translate([-70, -18, 0]) cube([140, 36, back_plate_t]);
        for (i = [-2 : 2])
            translate([i * 28, 0, -1])
                linear_extrude(height = back_plate_t + 2)
                    offset(r = usbc_cut_r) offset(delta = -usbc_cut_r)
                        square([usbc_cut_w + i*0.5, usbc_cut_h + i*0.5], center = true);
    }
}

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
            back_lip();
            ant_insert_bosses();
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
        // One pass-through, for the panel-mount USB-C cable.
        usbc_cutout();
        // The grilles cut a band from z=-1 to wall+1; shifted down by the
        // plate thickness that band covers the plate exactly.
        translate([0,0,-back_plate_t]) intake_grille();
        translate([0,0,-back_plate_t]) fan_grille();
        // The antenna mount screws into inserts here; its coax comes through
        // the middle of the bolt circle rather than through its own gland.
        ant_insert_bores();
        translate([0, ant_mount_y, -back_plate_t - 1])
            cylinder(d=ant_cable_dia, h=back_plate_t + 2);
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
        }
        // keyholes();  // wall-mount removed: this is a desk-cradle build now,
        // and the back is a clean flat disc. The keyhole_*/keyholes()/
        // keyhole_pads() definitions above are left intact (unused) so
        // wall-mounting is a two-line change if it's ever wanted back.
        exhaust_slots();
        for (a = speaker_angles) speaker_grille(a);
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
else if (part == "antenna_mount") antenna_mount();
else if (part == "antenna_mount_sma") antenna_mount_sma();
else if (part == "usbc_gauge") usbc_gauge();
else if (part == "antenna_socket_gauge") antenna_socket_gauge();
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
