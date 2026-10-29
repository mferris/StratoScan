// ============================================================
// StratoScan retro radar enclosure — 3-piece stack
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
// Radial clearance between the retainer and the shell's bore. It was zero
// (the ring drawn at exactly the bore's diameter), and the first print, a
// PETG ring in an ASA shell, had to be forced in (2026-10-09): ASA shrinks a
// little more than PETG, so the bore came out smaller than the ring. 0.4mm a
// side leaves a slip fit across both materials; the screws, not the bore,
// centre the ring.
retainer_clear = 0.4;
lip_height    = 6;            // shell's front lip (glass + retainer seat here)

screw_r = panel_diameter/2 + rim/2;   // screw ring sits centered in the rim band
n_screws = 8;
screw_clear_dia = 3.4;        // M3 clearance hole (front_trim + retainer)
// Heat-set inserts: the Kadrick M2-M5 kit (2026-10-02). Its M3 inserts are
// 4.5mm across the knurl and 3.9mm at the lead-in, in lengths of 3-8mm. A 4.0
// hole lets the lead-in drop in square and gives the knurl 0.25mm a side to
// melt into. It was 4.2, which left a 4.5 insert only 0.15mm of bite.
insert_hole_dia = 4.0;        // M3 heat-set insert hole, every M3 insert in the case
post_od = 9;                  // outer diameter of each insert post in the shell
// The 8 front posts. They used to be only shelf_h (2mm) tall: an insert sat in
// 2mm of plastic with open air under it, and the wall on one side only.
// Measured 2026-10-02: 2mm of the ring round the insert was solid; below that,
// a third of it. Now each post hangs below the shelf, merged into the wall,
// deep enough for an M3x5 insert with plastic under it. A 45-degree cone
// under the post means it prints without support. Screws: M3x14 (through the
// trim's outer band, 5.6mm, and the retainer, 4mm, then 4-5mm of thread).
front_insert_len = 5;         // M3x5 insert
front_post_h     = 8;         // from the shelf's top face down
front_post_cone  = 4;         // 45-degree skirt under it

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
// the cradle's keel and the cable-exit arc use.
relief_center_deg = 270;
relief_arc_deg    = 50;

// ---- Where the front stack sits (2026-10-29) -------------------------
// Where the trim's face is: the retainer on the shelf with its front face at
// shell_depth, the glass on the retainer, the trim on the glass.
// front_stack_placed() puts the three there, for the pictures and checks.
z_trim_face = shell_depth + glass_thickness + front_trim_h;   // 66.62

// ---- The retainer's key (2026-10-29) ---------------------------------
// A tab on the retainer's back face, outboard of the glass's edge, that drops
// into the shelf's gap at the bottom only when the ring's relief is there
// too, over the display's driver board. At any of the other seven screw
// positions it lands on the shelf and holds the ring 2mm proud, before a
// screw goes in, so the trim's screws can't press the glass, and the board
// taped to its back, onto solid ring. Clear of the screw notches, and just
// outside the relief, whose outer edge is at r 102.67.
retainer_key_a = [250, 258];   // degrees: inside the shelf's 245-295 gap
retainer_key_r = [102.7, 107];
retainer_key_h = 2;

// ---- The shelf's underside (2026-10-29) ------------------------------
// It slopes at 45 degrees from r 103 down to the wall, so the outer half of
// the 11mm ledge prints on its own rather than on 55mm-tall supports. Not
// over the speakers, whose sleeves reach up to the shelf there instead
// (speaker_bracket()); not over 30-75 degrees, where the Retro with Dials has
// two screw heads and a wire hole inside the wall at z 49-50; and not in the
// shelf's own gap at the bottom.
shelf_slope_r0   = 103;
shelf_slope_skip = [30, 75];

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
back_insert_d  = 7;    // how deep the heat-set insert hole is drilled: an M3x6 insert + 1mm

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
// ---- Back-plate key (roadmap 5.6) ------------------------------------
// The rib above is eight identical arcs, one between each pair of the eight
// evenly spaced posts, so the plate used to seat at any of eight positions
// 45 degrees apart -- and only one of them puts the antenna mount at the top.
// One block on the shell's bore wall, and a matching notch in one arc of the
// rib, leave exactly one. Placed lower left, between the posts at 225 and
// 270: clear of the antenna-mount bosses at the top (which already come
// within 0.2mm of the rib) and of the USB-C window. Both shells use the same
// angle, so the one plate still fits both cases.
back_key_a     = 247.5;
back_key_w     = 6;                 // tangential width of the block
back_key_reach = 2.6;               // in from the bore wall: past the rib's gap + thickness (2.35)
back_key_h     = back_lip_h + 1;    // deeper than the rib is tall
back_key_clear = 0.5;               // per side, between the block and the notch

// ---- USB-C pass-through ----------------------------------------------
// ONE opening, replacing the separate USB-C power gland and SMA antenna
// gland that used to sit side by side. The antenna no longer needs a
// bulkhead here: its coax comes in through the antenna mount's cable bore.
//
// Since 2026-10-29 the opening is the 12 V trigger board's own (the power
// fix, below). The board's front edge bears on the plate's inner face, its
// socket goes out through a window its own shape, and a plug's moulding goes
// into a pocket in the outer face to meet the socket. The window's size and
// the pocket's depth follow the board's measured sizes, so they are set with
// them, in "The power fix". Until then the opening took a panel-mount USB-C
// extension: an 11 x 8 window, two M3 holes 16.5 mm apart and a 2 mm pocket
// with the screw heads in it. That extension does not fit this plate.
//
// 37 mm below where it was ([60, -14]): the owner's ask, 2026-10-10. At
// the old spot the power jumper bent hard against the Pi's USB ports; the
// bottom centre, tried first, did not suit either.
usbc_cut_pos     = [60, -51];
// The pocket, for a plug's moulding (2026-10-29). The USB-C standard lets a
// moulding be up to 12.35 x 6.5 mm, and real ones run bigger: thick strain
// reliefs, braided cables. 14 x 10 takes any that keeps to the standard,
// with 0.8 mm to spare each side across and 1.7 above and below, and
// mouldings that don't, up to about 13.4 x 9.4. The owner's went through
// the old 11 x 8 window.
usbc_recess_w    = 14;
usbc_recess_h    = 10;
usbc_recess_r    = 2.5;    // its corners, as round as a moulding's
// The trigger board's mount is held by two M3 screws from INSIDE the case,
// through its ears and into M3 x 3 heat-set inserts pressed into the plate
// (2026-10-29), so nothing of them is in the outer face, and each screw
// clamps the ear's whole thickness. 24 mm apart, so each insert keeps 3 mm
// of plate between it and the pocket. At the old 16.5 mm an M3 head, 5.5 to
// 6 mm across, reached to within 5.3 mm of the window's centre line, inside
// the 14 mm a moulding needs: with the pocket only 1.4 mm deep it could
// neither sit in the pocket nor be sunk out of a moulding's way.
usbc_screw_pitch = 24;
usbc_insert_len  = 3;      // M3 x 3: flush with both faces of the 3 mm plate

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

rib_h    = 4.0;      // how far each rib stands proud of the wall.
// 2.2 -> 4.0: at 2.2 the underside was too small an overhang for
// BambuStudio to generate support for, so it printed rough. A wider
// overhang trips the detector.
rib_w    = 5;         // width (in Z) of each rib band
// The underside -- the face toward the back plate, which is down when the
// shell prints -- slopes at 45 degrees from the wall, so the rings print with
// no support at all (2026-10-24). Square, they needed supports all round, and
// those welded on: the band below the first ring and the top of the first
// ring (where the second ring's supports stood) came off torn. The slope
// stops rib_lip short of the outer edge, a small square step that keeps the
// crisp shadow line under each ring, which a plain slope loses. A step that
// small is too little for the slicer to support and prints clean on its own.
// From the front nothing changes: the front face is square and 4mm deep.
rib_lip  = 0.8;
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
speaker_boss_len  = 6;     // the screw pads' depth, from the speaker's face into the sleeve
speaker_duct_wall = 1.6;   // the sleeve's walls (2026-10-23: it was a solid block)
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
// ---------- PLINTH RIDGES ----------
// Two raised bands round the plinth, echoing the case's own ribs. They were
// two strips across the FRONT only, standing 1mm proud: an overhang that
// small is under BambuStudio's support threshold, so the underside printed
// unsupported and rough -- the same failure the case ribs had at 2.2mm,
// fixed by going to 4mm (rib_h). So these match it: 4mm proud, all the way
// round, as one band per level so the corners are mitred rather than two
// strips butting into each other. Tops stay under z=13, where the cradle
// arms and keel fuse into the plinth (arm_lift puts them at base_h - 3).
// Their undersides slope like the case's rings (see plinth_ribs()).
plinth_rib_h = 4;           // how far each band stands out from the plinth
plinth_rib_w = 3;           // height of each band
plinth_rib_z = [3.5, 9.5];  // bottom of each band: 3.5-6.5 and 9.5-12.5
// ---------- THE CHARGER CABLE'S CLIP (2026-10-29) ----------
// Nothing held the cable, so its weight and every tug levered the plug in the
// trigger board's socket, on a board 19 x 11 mm, and a moving cable is what
// set off the power cuts. The plug points straight back, 18 degrees down,
// from the window at usbc_cut_pos; its end is about (60, 49) and 69 mm above
// the desk, and the cable drops from it onto the plinth at y 55-62. So a
// groove in the plinth's top, directly under the plug, from y 52 to the back
// edge, takes it there: round, a little under the cable so it grips, with a
// mouth narrower than the cable so it snaps in. Over the back edge the groove
// turns down round a 4mm radius, and carries on down the back face, through
// both ridges, so the cable hangs flat to the back and leaves along the desk.
// With a slack loop of 40-50mm left up to the plug, a pull moves the stand
// before it moves the plug. Measure your cable first: this is for one about
// 4mm thick.
stand_cable_d    = 4;                 // the charger's cable: about 4mm, measure yours
stand_clip_grip  = 0.2;               // the groove is this much under the cable
stand_clip_mouth = stand_cable_d - 0.7;   // so it snaps in past 0.35mm a side
stand_clip_x     = usbc_cut_pos[0];   // under the plug
stand_clip_y0    = 52;                // the groove's front end
stand_clip_sink  = 2.5;               // from the top face, and the back face, to the cable's axis
stand_clip_bend  = 4;                 // the radius it turns down over the back edge, on its axis
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
// The front rail's underside slopes at 45 degrees to a small square lip, as
// the rings' do (2026-10-29), so it prints without support. Square, it was
// supported from the top of the rear rail, the ASA-on-ASA weld that tore the
// rings on 2026-10-24. Its top is the face that bears, on the front arm, so
// nothing is lost. The rear rail stays square: its underside is the face
// that bears, on the rear arm, and is what holds the case in the stand.
retain_lip = 0.8;

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
// Centred in the window between the top of the upper decorative rib and the
// rear cradle arm, rather than at plain mid-depth. At mid-depth the slots ran
// from z=24.5 and the upper rib band is 22-27, so every slot cut through the
// rib and came out the other side -- the rib read as broken rather than as a
// ridge. Moving rather than shortening keeps the full 12mm of vent: the clear
// window is 16.5mm and the slot is 12mm, so it fits with ~2mm either side.
//
// Derived, not typed, so it follows shell_depth and the rib positions instead
// of silently becoming wrong the next time either moves. The kitten has no
// ribs, but exhaust_z is shared core, and the slots stay inside the arm gap
// there too -- identical part, no reason to fork it.
rib_top_z      = 27;               // max(rib_z_list) + rib_w, restated for the kitten
arm_b_inner_z  = shell_depth/2 + 13;   // arm_gap/2 = 13
exhaust_z      = (rib_top_z + arm_b_inner_z) / 2;
                                   // cradle arms, the one part of the lower wall that is
                                   // actually open to air when the case is in the stand
n_exhaust      = 24;   // on a 15-degree pitch; only those in the top arc are cut
// Slots only across the top, between the two speakers: 30-150 degrees, nine
// slots. The rest were removed (2026-10-01). At 0 and 180 they ran into the
// speaker grilles, whose 90mm width spans the three slots at each side, and
// behind the grille the speaker bracket blanks them off, so they were
// dents rather than vents. Underneath, six landed on the retention rails
// (retain_segs, 207-245 and 295-333). Both made the case harder to read and
// to print for no airflow. Hot air leaves by the top anyway.
exhaust_a0 = 30;
exhaust_a1 = 150;

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
    od = outer_dia - 2*wall - 2*retainer_clear;
    difference() {
        cylinder(d=od, h=retainer_h);
        translate([0,0,-1])
            cylinder(d=retention_opening, h=retainer_h+2);
        // The screws pass at screw_r, set by the inserts already in printed
        // shells, which leaves less than a hole's width of ring outside them.
        // Closed holes left a 0.3mm sliver that printed as nicks, not holes;
        // so each is an open notch, a 3.4mm slot from the hole out through
        // the rim. The screw still passes clear, and the notches stop the
        // ring turning.
        for (i = [0:n_screws-1])
            rotate([0, 0, i * 360/n_screws])
                translate([0, 0, -1]) hull() {
                    translate([screw_r, 0, 0]) cylinder(d=screw_clear_dia, h=retainer_h+2);
                    translate([od/2 + 2, 0, 0]) cylinder(d=screw_clear_dia, h=retainer_h+2);
                }
        rotate([0,0, relief_center_deg - relief_arc_deg/2])
            rotate_extrude(angle = relief_arc_deg)
                translate([relief_r0, -1])
                    square([relief_w, retainer_h+2]);
    }
    // The key (2026-10-29): a tab standing retainer_key_h off the back face,
    // the face that sits on the shelf. See retainer_key_a.
    rotate([0, 0, retainer_key_a[0]])
        rotate_extrude(angle = retainer_key_a[1] - retainer_key_a[0])
            translate([retainer_key_r[0], -retainer_key_h])
                square([retainer_key_r[1] - retainer_key_r[0], retainer_key_h + 0.01]);
}

// The retainer as it prints: glass face down, so the key stands up off its
// top rather than being the first layer, under a ring 2mm up in the air
// (2026-10-29). retainer.stl is exported this way up.
module retainer_print() {
    translate([0, 0, retainer_h]) rotate([180, 0, 0]) retainer();
}

// The front stack where it sits on the shell (2026-10-29): the retainer on
// the shelf, the glass on the retainer, and the trim on the glass, with its
// face at z_trim_face. `which` is "retainer", "glass" or "trim" for one of
// them, so a picture can colour each; anything else gives all three. The
// pictures put the trim on the panel's whole 6.45mm depth instead of the
// 1.62mm glass, and the kitten's sat the retainer inside the shelf; placing
// the stack here once stops that. The Retro with Dials sets its arc's face
// 1mm behind z_trim_face, and its checks hold z_trim_face to the trim this
// puts there; the core test stops a variant setting its own, as the Dials
// did until 2026-10-29.
module front_stack_placed(which = "all") {
    all = which != "retainer" && which != "glass" && which != "trim";
    if (all || which == "retainer")
        translate([0, 0, shell_depth - retainer_h]) retainer();
    if (all || which == "glass")
        translate([0, 0, shell_depth]) cylinder(d = panel_diameter, h = glass_thickness);
    if (all || which == "trim")
        translate([0, 0, shell_depth + glass_thickness]) front_trim();
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
        // Centred in the wall, so the cut (wall + 2 deep) breaks out on both
        // faces. It used to be centred on the OUTER face, which took it only
        // 2.5mm into the 3mm wall: every slot was a blind dent, and the case
        // had no exhaust at all.
        if (a >= exhaust_a0 && a <= exhaust_a1)
            translate([(outer_dia/2 - wall/2)*cos(a), (outer_dia/2 - wall/2)*sin(a), exhaust_z])
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
// Angular half-width of a speaker grille on the outer wall, plus a rivet's
// radius: no rivet sits on a grille (2026-10-01). Three of the ring fell
// across each one, standing up among the holes.
grille_half_deg = (grille_w/2 + rivet_dia/2 + 1) / (outer_dia/2) * 180 / PI;
function near_speaker(a) =
    len([for (s = speaker_angles)
         if (abs((a - s + 540) % 360 - 180) < grille_half_deg) s]) > 0;
// Nor under the stand's front arm (2026-10-29): its arc, 205-335 degrees,
// plus a rivet's radius and 1mm. The nine there were hidden by the arm, and
// stood 0.7mm proud into the cradle's 1mm clearance, so the case's front sat
// on the tips of two or three of them rather than on its wall
// (shell_seats_in_stand). The ring keeps the nine across the top.
function under_front_arm(a) =
    abs((a - 270 + 540) % 360 - 180) < cradle_arc/2 + (rivet_dia/2 + 1) / (outer_dia/2) * 180 / PI;

module rivets() {
    for (i = [0:n_rivets-1]) {
        a = i * 360/n_rivets;
        if (!near_speaker(a) && !under_front_arm(a))
        translate([(outer_dia/2)*cos(a), (outer_dia/2)*sin(a), rivet_z])
            rotate([0,0,a])
                translate([-rivet_h/2, 0, 0])
                    rotate([0,90,0])
                        cylinder(d=rivet_dia, h=rivet_h, $fn=16);
    }
}

module ribs() {
    // The profile starts 0.3mm inside the wall so it overlaps it rather than
    // touching it; the slope still meets the outer face 4mm - rib_lip below
    // the ring.
    for (z = rib_z_list) {
        translate([0,0,z])
            rotate([0,0,rib_a0])
                rotate_extrude(angle=rib_arc)
                    translate([outer_dia/2, 0])
                        polygon([[-0.3, -(rib_h - rib_lip) - 0.3], [rib_h - rib_lip, 0],
                                 [rib_h, 0], [rib_h, rib_w], [-0.3, rib_w]]);
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
    for (seg = retain_segs) {
        // the rear rail, square: its underside bears on the rear arm
        translate([0,0,arm_a_inner + retain_clear])
            rotate([0,0,seg[0]])
                rotate_extrude(angle=seg[1])
                    translate([outer_dia/2, 0])
                        square([retain_h, retain_w]);
        // the front rail, its underside sloped to a lip (retain_lip). The
        // profile starts 0.3mm inside the wall so it overlaps it, as the
        // rings' does.
        translate([0,0,arm_b_inner - retain_clear - retain_w])
            rotate([0,0,seg[0]])
                rotate_extrude(angle=seg[1])
                    translate([outer_dia/2, 0])
                        polygon([[-0.3, -(retain_h - retain_lip) - 0.3], [retain_h - retain_lip, 0],
                                 [retain_h, 0], [retain_h, retain_w], [-0.3, retain_w]]);
    }
}

// ============================================================
// SPEAKERS — one per side (0deg/180deg). A thin sleeve, the speaker's own
// outline, runs from the speaker's face to the curved wall, so the sound
// goes out through the grille and not into the case; four screw pads in
// its corners land the speaker's real 92x36mm hole pattern; the grille is
// cut through the wall in front of it. Until 2026-10-23 the bracket was a
// solid block 15mm deep with the grille drilled through it as tubes, some
// 50 cm3 of plastic a side for nothing (the owner's ask).
// ============================================================
module speaker_bracket(angle) {
    r_wall  = outer_dia/2 - wall;
    r_mount = r_wall - speaker_bracket_depth;
    r_face  = r_mount - speaker_boss_h;     // the speaker's face, on the sleeve's rim
    z0 = (shell_depth - speaker_d)/2;
    zc = z0 + speaker_d/2;
    t  = speaker_duct_wall;
    rotate([0,0,angle]) {
        // The sleeve, stopped at the wall and fused 0.5 into it: a flat box
        // across a 100mm chord of the curved wall would otherwise poke out
        // through the shell at its ends.
        difference() {
            intersection() {
                translate([r_face, -speaker_w/2, z0]) cube([r_wall + 1 - r_face, speaker_w, speaker_d]);
                cylinder(r = r_wall + 0.5, h = shell_depth);
            }
            intersection() {
                translate([r_face - 1, -speaker_w/2 + t, z0 + t])
                    cube([r_wall + 2 - r_face, speaker_w - 2*t, speaker_d - 2*t]);
                cylinder(r = r_wall, h = shell_depth);     // the wall itself stays
            }
        }
        // Up to the shelf (2026-10-29): the sleeve's top wall carries on from
        // the sleeve's top, z 53, to the shelf's underside, z 55, wherever the
        // shelf is over it. The 2mm slot between the two was supported, and
        // support in a slot that size can hardly be got out. Outside the
        // shelf's inner edge it stops at z 53, as before, so nothing comes
        // any nearer the back of the display.
        intersection() {
            translate([r_face, -speaker_w/2, z0 + speaker_d - 0.01])
                cube([r_wall + 1 - r_face, speaker_w, shell_depth - lip_height - (z0 + speaker_d) + 0.01]);
            difference() {
                cylinder(r = r_wall + 0.5, h = shell_depth);
                translate([0, 0, -1]) cylinder(d = retention_opening, h = shell_depth + 2);
            }
        }
        // the four screw pads, filling the sleeve's corners
        for (sy = [-1, 1]) for (sz = [-1, 1])
            intersection() {
                difference() {
                    translate([r_face, sy > 0 ? speaker_hole_x/2 - speaker_boss_dia/2 : -speaker_w/2,
                               sz > 0 ? zc + speaker_hole_y/2 - speaker_boss_dia/2 : z0])
                        cube([speaker_boss_len, speaker_w/2 - speaker_hole_x/2 + speaker_boss_dia/2,
                              speaker_d/2 - speaker_hole_y/2 + speaker_boss_dia/2]);
                    translate([r_face - 0.1, sy*speaker_hole_x/2, zc + sz*speaker_hole_y/2])
                        rotate([0,90,0]) cylinder(d=speaker_screw_dia, h=speaker_boss_len + 0.2, $fn=12);
                }
                cylinder(r = r_wall + 0.5, h = shell_depth);
            }
    }
}


// Clearance between a grille hole and a rib edge.
grille_rib_clear = 0.6;

// The grille is the block of rows in front of the ribs, and nothing behind
// them (2026-10-01). The ribs sweep 220 degrees, taking in both speakers, so
// a hole on a rib would perforate it (the rib reads as broken), and the one
// row that fitted in the 7mm gap BETWEEN the ribs read as a stray line of
// holes rather than part of the grille. Every hole whose edge comes within
// grille_rib_clear of the rearmost rib's front edge, or anywhere behind it, is
// dropped. Written over rib_z_list, so moving or adding a rib moves this too.
function behind_ribs(z) =
    let (c = grille_hole_dia/2 + grille_rib_clear,
         front = max([for (rz = rib_z_list) rz + rib_w]))
    z - c < front;

// Clearance between a grille hole and a front post (2026-10-29).
grille_post_clear = 0.5;

// Nor any hole at a front post (2026-10-29). The post at each speaker's axis
// hangs down from the shelf to z 45 and stands in the way of the grille's
// front rows: it filled 64% of the front row's middle hole, cut into the two
// beside it, and the tip of its cone reached into the middle hole of the row
// behind. The holes run parallel to the speaker's axis, past the post, so a
// hole meets the post wherever the two overlap seen along the hole. Every
// hole whose edge comes within grille_post_clear of the post's outline, seen
// that way, is dropped: four a speaker. post_gap(u, z) is how far a point at
// height z, u from the post's axis across the hole, is from that outline:
// the 9mm barrel down to z 49, then the 45-degree cone under it.
function post_gap(u, z) =
    let (top = shell_depth - lip_height + shelf_h, z1 = top - front_post_h, z0 = z1 - front_post_cone)
    min([for (zz = [z0 : 0.1 : top]) norm([max(0, u - (post_od/2 - max(0, z1 - zz))), zz - z])]);
// A hole in the grille at `angle`, dy across it and at height z, is near a
// front post: one whose barrel reaches the holes' start, x0 (only the post on
// the speaker's axis does).
function near_post(angle, dy, z, x0) =
    len([for (i = [0:n_screws-1])
         let (b = i*360/n_screws - angle)
         if (screw_r*cos(b) + post_od/2 > x0
             && post_gap(abs(dy - screw_r*sin(b)), z) < grille_hole_dia/2 + grille_post_clear) i]) > 0;

// `grow` widens every hole by that much all round, for a check
// (grille_clear_of_posts); it changes no hole's place.
module speaker_grille(angle, grow = 0) {
    // Since the bracket became a hollow sleeve (2026-10-23) the holes need
    // cross only the wall. They start inside the sleeve, just past the screw
    // pads, so they never bore into a pad, and end past the outer surface.
    r_mount = outer_dia/2 - wall - speaker_bracket_depth;
    z0 = (shell_depth - speaker_d)/2;
    x0 = r_mount - speaker_boss_h + speaker_boss_len + 0.1;
    n_y = floor(grille_w / grille_pitch);
    n_z = floor(grille_h / grille_pitch);
    rotate([0,0,angle])
        for (iy = [0:n_y]) {
            dy = (iy - n_y/2) * grille_pitch;
            for (iz = [0:n_z]) {
                dz = (iz - n_z/2) * grille_pitch;
                if (!behind_ribs(z0 + speaker_d/2 + dz) && !near_post(angle, dy, z0 + speaker_d/2 + dz, x0))
                    translate([x0, dy, z0 + speaker_d/2 + dz])
                        rotate([0,90,0])
                            cylinder(d=grille_hole_dia + 2*grow,
                                     h=speaker_bracket_depth + speaker_boss_h - speaker_boss_len - 0.1 + wall + 3, $fn=10);
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

// The plinth's ridges: for each level, a ring the shape of the plinth's
// footprint, plinth_rib_h wide, standing out from all four faces. Their
// undersides slope at 45 degrees to a small square lip, as the case's rings
// do (rib_lip), so they print without support (2026-10-24): square, the
// slicer supported them all round. The slope is a frame too, started 0.3mm
// inside the plinth so the two overlap; it meets the plinth's face
// plinth_rib_h - rib_lip below each ridge. The upper ridge's slope starts a
// little below the lower ridge's top, which only joins them.
module plinth_ribs() {
    for (z = plinth_rib_z) {
        translate([0, 0, z])
            linear_extrude(height = plinth_rib_w)
                difference() {
                    offset(delta = plinth_rib_h) square([base_w, base_d], center = true);
                    square([base_w, base_d], center = true);
                }
        difference() {
            hull() {
                translate([0, 0, z - (plinth_rib_h - rib_lip) - 0.3])
                    linear_extrude(height = 0.01) offset(delta = -0.3) square([base_w, base_d], center = true);
                translate([0, 0, z - 0.01])
                    linear_extrude(height = 0.02) offset(delta = plinth_rib_h - rib_lip) square([base_w, base_d], center = true);
            }
            translate([0, 0, z - plinth_rib_h - 1])
                linear_extrude(height = plinth_rib_h + 2) offset(delta = -0.6) square([base_w, base_d], center = true);
        }
    }
}

// The charger cable's clip, cut from the plinth (2026-10-29): see
// stand_cable_d. Along the top a round groove a little under the cable, with
// a mouth narrower than it; then a turn down over the back edge, its mouth on
// the outside of the turn; then a channel down the back face as wide as the
// groove but open to the back, so the cable leaves it wherever it bends away
// to the desk, and a notch as wide through both ridges. None of it needs
// support: under the mouths' lips the groove's curve is 60 degrees or more
// from flat, and the channel down the back face is upright.
module stand_cable_clip() {
    r  = (stand_cable_d - stand_clip_grip) / 2;
    zc = base_h - stand_clip_sink;      // the top groove's axis
    yc = base_d/2 - stand_clip_sink;    // the back channel's axis
    R  = stand_clip_bend;
    y1 = yc - R;                        // where the groove starts to turn down
    translate([stand_clip_x, stand_clip_y0, zc]) {
        rotate([-90, 0, 0]) cylinder(r = r, h = y1 - stand_clip_y0 + 0.01);
        sphere(r = r);
    }
    hull() for (y = [stand_clip_y0, y1])
        translate([stand_clip_x, y, zc]) cylinder(d = stand_clip_mouth, h = stand_clip_sink + 1);
    translate([stand_clip_x, y1, zc - R]) rotate([0, 90, 0]) rotate([0, 0, 90])
        rotate_extrude(angle = 90) {
            translate([R, 0]) circle(r = r);
            translate([R, -stand_clip_mouth/2]) square([2*stand_clip_sink + 1, stand_clip_mouth]);
        }
    translate([stand_clip_x, yc, -1]) cylinder(r = r, h = zc - R + 1 + 0.01);
    translate([stand_clip_x - r, yc, -1]) cube([2*r, base_d/2 - yc + 0.01, zc - R + 1 + 0.01]);
    translate([stand_clip_x - r, base_d/2 - 0.01, -1]) cube([2*r, plinth_rib_h + 1, base_h + 2]);
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
    // rather than trying to solve its exact intersection analytically.
    // The cable's clip is cut from it after (2026-10-29).
    difference() {
    intersection() {
    translate([-400, -400, 0]) cube([800, 800, 400]);
    union() {
        // plinth, flat on the desk
        translate([-base_w/2, -base_d/2, 0])
            cube([base_w, base_d, base_h]);

        plinth_ribs();

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
    stand_cable_clip();
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
ant_flange_t   = 7;   // 4 -> 7: the insert now lives in the FLANGE, not the plate
ant_flange_insert_d = 5.5;  // heat-set pocket depth, leaving 1.5mm of flange behind it
ant_bolt_pcd   = 30;
ant_bolt_d     = 3.4;
n_ant_bolts    = 3;
// 88 -> 81 (2026-10-07): at 88 the 40mm flange reached y=108 and sat over
// the plate's top screw (0, 106.7), so the plate could not be screwed on
// with the mount fitted. At 81 the flange ends at 101, 2.9mm short of the
// screw head's edge. The centre vent reaches only y=27, so nothing below
// moves. top_screw_clear_of_mount in the checks holds this.
ant_mount_y        = 81;
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
// The plate's own hole. 13, not 11, since the twin mount's two plugs share it
// and the second has to pass the first cable (see antenna_mount_twin).
ant_plate_hole     = 13;

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
// How far the cavity runs BELOW the panel, for the two-piece barrel: the
// bulkhead's inner half plus the jumper plug mated onto it. That length was
// estimated at ~20mm from listings, not measured off the parts, so this is
// deliberately generous -- 25mm covers any plausible barrel-and-jumper pair,
// and the cost of the extra 7mm is 3.8mm more overhang at the back of an
// arm that already stands 30mm off the plate.
//
// Guessing short here is the expensive mistake. The mount is quick to
// reprint; the back plate it bolts to is not, and a cavity 3mm too shallow
// means the plug will not seat and the antenna sits proud at an angle.
ant_sma_cavity_d = 25;


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
        ant_flange_insert_bores();
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
            ant_axis_frame()
                translate([0,0,ant_sma_boss_h - ant_sma_panel_t - ant_sma_cavity_d])
                    cylinder(d=ant_sma_boss_d,
                             h=ant_sma_cavity_d + ant_sma_panel_t);
        }
        ant_axis_frame() {
            // the jack's hole, through the panel at the top of the boss
            translate([0, 0, ant_sma_boss_h - ant_sma_panel_t - 0.01])
                cylinder(d=ant_sma_hole, h=ant_sma_panel_t + 0.02, $fn=48);
            // the space behind it. Deliberately reaches DOWN to -6 so it
            // meets the cable bore's sweep rather than relying on the two
            // happening to touch: an unconnected cavity looks identical in
            // preview and is a solid wall in the print.
            translate([0, 0, ant_sma_boss_h - ant_sma_panel_t - ant_sma_cavity_d])
                cylinder(d=ant_sma_cavity, h=ant_sma_cavity_d);
        }
        ant_cable_bore(0);
        ant_flange_insert_bores();
        // nothing may stand proud of the plate's outer face
        translate([-300, -300, -back_plate_t]) cube([600, 600, 600]);
    }
}

// ---- the twin mount: 1090 and 978 MHz side by side (roadmap 5.3) ------
// The FlyCatcher has two inputs, 1090 and 978 MHz, and the antenna bundle two
// hinged whips with SMA plugs. One mount holds both: the same flange, bolt
// circle and arm as the others, ending in a crossbar with a bulkhead jack at
// each end. Bought for it: two SMA male to SMA female bulkhead RG316 jumpers,
// about 30cm -- the bulkhead end in a tower, the plug end on the FlyCatcher.
//
// The counter-tilt stays. The whips' hinges could take up the case's lean,
// but a hinge holds firmly only at its stops (straight, or folded flat), and
// part-way it sags over months. With the jacks counter-tilted the whips stand
// vertical with their hinges straight, and can still fold down to move it.
//
// 80mm apart: two antennas this close in frequency detune each other when
// bunched, and further apart than this the crossbar outgrows the head.
//
// Two parts, body and cover, since 2026-10-07. The first version threaded
// each cable through an internal tunnel -- down a tower, along the crossbar,
// down the arm -- and could not be assembled: both ends of a jumper are
// rigid metal about 9mm across and 15-20mm long, and a body that fat cannot
// turn a right-angle corner inside an 11mm bore (the geometry allows a few
// millimetres of rigid length there, not twenty). The checks only ever
// passed a straight probe down each leg. Found by the owner, printed part
// in hand.
//
// Now nothing turns a corner. The crossbar and towers are one "goalpost"
// with an open channel on the face away from the case (local +Y, which is
// print-up when the body prints flange-down, so the channel, the slots and
// every hole need no support; the towers' outboard ends and the bar's top
// edge start in mid-air in that orientation and want tree supports under
// them, on the face toward the case), closed by a flat cover that sits
// flush inside a rim on five M2 screws. The arm's bore runs straight on
// through the crossbar and out of the channel floor, so each plug is pushed
// into it end-on from open air and on out through the plate. The bulkhead
// end slides sideways into a slot under each tower's panel that is a close
// fit on the jack's hex body, so the jack cannot turn while its nut is
// tightened and nothing inside has to be held. Both plugs share the one
// bore: 13mm, because the second plug (9.2mm across its nut's corners) has
// to pass the first cable (2.5mm); the plate's hole (ant_plate_hole) is
// the same 13mm for the same reason.
//
// Panel 2mm: the bulkhead's thread is 10mm from its shoulder (measured
// 2026-10-07), and 2 of panel + 0.6 of washer + 2.5 of nut leaves 4.9mm for
// the whip's own coupling nut. 3mm would leave 3.9, which is marginal.
//
// Two styles of this mount (2026-10-08): the owner's jumpers come with an
// 8mm hex body or an 11mm one, and a mount is printed for one kind. Every
// size that depends on the body -- slot, pocket, tower width, the bar's
// thickness, the cover's tab and pad, the screw positions -- is a function
// of the jack size, and the mount's modules take the pair of sizes as an
// argument (antenna_mount_twin([11, 11])), so one source prints either, or
// a mixed one if that is ever wanted. The cover can carry each side's
// frequency so nobody has to guess which whip goes where.
//
// Sides are indexed as seen from BEHIND the case, which is where anyone
// fitting a whip stands: [0] is the viewer's LEFT (local +X) and [1] the
// RIGHT (local -X).
ant_twin_jack_af   = [8, 8];            // the default style; the dispatcher has antenna_mount_twin_8 and _11
ant_twin_hole      = [6.7, 6.7];        // panel holes: a 1/4-36 barrel measures 6.35 and printed holes come out small
ant_twin_labels    = ["1090", "978"];   // engraved in the cover under each tower; "" for none
ant_twin_label_on  = true;
ant_twin_sep       = 80;    // between the two jacks
ant_twin_bar_z     = 30;    // crossbar height along the antenna axis: 9mm walls round the 12mm channel
ant_twin_top       = 32;    // top of each tower, along the axis from the arm's end
ant_twin_corner_r  = 6;     // the goalpost's corners, in the plane of the bar (tower tops, bar ends)
ant_twin_edge_r    = 1.5;   // every other edge: the same round the cases have, not a box
ant_twin_panel_t   = 2;     // the panel the jack's nut clamps (see the thread arithmetic above)
ant_twin_wall      = 8.6;   // tower wall either side of its slot
ant_twin_chan_z    = 12;    // channel width along the axis
ant_twin_floor_y   = -4.6;  // the channel floor (local Y); each slot has its own, where the hex seats
ant_twin_bore      = 13;    // the arm bore: a plug beside a cable. ant_plate_hole matches.
ant_twin_cover_t   = 3;
ant_twin_cover_gap = 0.2;   // all round the cover, in its seat
ant_twin_rim       = 1.5;   // rim round the cover
ant_twin_pocket_z  = 26;    // above this the open slot becomes a closed pocket the hex body's size,
                            // so the 2mm panel over it rests on solid plastic on every side beyond
                            // the hex (the washer bears on that) and the body is held fore-aft too
ant_twin_cover_top = 25.8;  // the cover's tabs stop under the pocket
ant_twin_m2_hole   = 3.0;   // M2 heat-set insert, 3.2mm across the knurl (3.2 if the kit's are the 3.5mm kind). MEASURE the kit's.
ant_twin_m2_depth  = 6;
ant_twin_screw_hole = 2.4;  // M2 clearance through the cover
// Counterbored so the M2 cap heads sit mostly below the face (the owner's
// ask, 2026-10-10): 3.8mm heads, 2mm tall, in 4.4mm bores 1.5mm deep, so
// they stand 0.5mm proud and 1.5mm of cover stays under them. The cover
// prints outer face down, so each bore opens on the plate and its roof is a
// 1mm-wide ring round the screw hole: a bridge any slicer spans, which the
// "no counterbore" note here used to rule out too cautiously. The M2 x 6
// screws still fit: the cover is 1.5mm thinner under the head, so they reach
// 1.5mm deeper, 4.5 of the 6mm insert hole.
ant_twin_cbore_d = 4.4;
ant_twin_cbore_h = 1.5;
ant_twin_back_pad  = 4;     // the bar is thicker on its case side behind the flare under the bore's mouth
ant_twin_back_pad_w = 40;
ant_twin_label_size = 6;
ant_twin_label_depth = 0.6;
ant_twin_plug_d    = 9.3;   // an SMA plug's hex across its corners

// Everything sized from a jack body `a` (across flats), and from a pair
// `af` = [left, right]. Functions, so the checks (which `use` this file and
// see its functions but not its variables) can size their probes the same
// way for either style.
function ant_twin_corners(a)  = a / cos(30);                            // the hex across its corners
function ant_twin_slot_w(a)   = a + 0.8;                                // its flats slide between the slot's walls
function ant_twin_slot_y0(a)  = -ant_twin_corners(a) / 2;              // seated on this floor, the barrel is under the hole
function ant_twin_pocket_y(a) = ant_twin_corners(a) / 2 + 0.26;        // the pocket's far wall
function ant_twin_tower_w(a)  = ant_twin_slot_w(a) + 2 * ant_twin_wall;
function ant_twin_screw_x(a)  = ant_twin_sep/2 + ant_twin_slot_w(a)/2 + ant_twin_wall/2;  // mid-wall beside the slot
function ant_twin_side(af, s) = af[s > 0 ? 0 : 1];
function ant_twin_seat(af)    = max(ant_twin_pocket_y(af[0]), ant_twin_pocket_y(af[1])) + 3;  // 3mm of wall between pocket and seat
function ant_twin_bar_y(af)   = 2 * (ant_twin_seat(af) + ant_twin_cover_t);              // the cover flush with the bar
// Cover screws, as (X, Z) in the axis frame: one in each tower's outer wall
// beside the slot, one in each tower's foot (solid: the channel stops at
// the slots), one in the bar's top wall. Each insert hole has at least
// 2.2mm of wall on every side, and each hole in the cover at least 2.1mm to
// the cover's edge.
function ant_twin_screw_xz(af) = [[ant_twin_screw_x(af[0]), 23], [-ant_twin_screw_x(af[1]), 23],
                                  [ant_twin_screw_x(af[0]), -8], [-ant_twin_screw_x(af[1]), -8], [0, 10]];

// One jack's frame: the counter-tilted antenna axis, moved out along X.
module ant_twin_frame(s) {
    ant_axis_frame() translate([s * ant_twin_sep/2, 0, 0]) children();
}

// A bore that prints without support: a circle with a 45-degree roof on the
// side that faces up when the body prints flange-down (local +Y).
module ant_twin_teardrop(d, h) {
    hull() {
        cylinder(d=d, h=h);
        // apex at r*sqrt(2): the square's side corners land on the circle, a true 45 roof
        translate([0, d/2 * 0.707, 0]) rotate([0,0,45])
            translate([-d/4, -d/4, 0]) cube([d/2, d/2, h]);
    }
}

// The goalpost, in the axis frame's X (across) and Z (up the antenna axis):
// the bar between the towers, a tower of its own width at each end.
module ant_twin_outline2d(af) {
    offset(r=ant_twin_corner_r) offset(delta=-ant_twin_corner_r) union() {
        translate([-ant_twin_sep/2, -ant_twin_bar_z/2]) square([ant_twin_sep, ant_twin_bar_z]);
        for (s = [-1, 1]) let (w = ant_twin_tower_w(ant_twin_side(af, s)))
            translate([s*ant_twin_sep/2 - w/2, -ant_twin_bar_z/2])
                square([w, ant_twin_bar_z/2 + ant_twin_top]);
    }
}

// A 2D shape in (X, Z), extruded along the frame's Y from y0 to y1.
module ant_twin_slab(y0, y1) {
    translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(height = y1 - y0) children();
}

// The cover's outline: the goalpost inset by the rim and the fit gap, and
// stopped short of the pockets.
module ant_twin_cover2d(af) {
    intersection() {
        offset(delta = -(ant_twin_rim + ant_twin_cover_gap)) ant_twin_outline2d(af);
        translate([-200, -200]) square([400, 200 + ant_twin_cover_top]);
    }
}

// The bore in the body's own frame: straight along the plate's normal from
// above the flange face, down the arm, through the crossbar and out of the
// channel. One cylinder, so there is nothing for a plug to turn into.
module ant_twin_bore() {
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len - 30])
        cylinder(d=ant_twin_bore, h=ant_stub_len + 30 + 1);
}

module antenna_mount_twin(af = ant_twin_jack_af) {
    seat = ant_twin_seat(af);
    bar_y = ant_twin_bar_y(af);
    difference() {
        union() {
            translate([0, ant_mount_y, -back_plate_t - ant_flange_t])
                cylinder(d=ant_flange_d, h=ant_flange_t);
            translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
                cylinder(d=ant_stub_dia, h=ant_stub_len);
            // the goalpost, every edge rounded: the outline shrunk by the
            // edge radius and the slab shortened by it, then grown back
            // with a sphere
            ant_axis_frame() minkowski() {
                ant_twin_slab(-bar_y/2 + ant_twin_edge_r, bar_y/2 - ant_twin_edge_r)
                    offset(delta=-ant_twin_edge_r) ant_twin_outline2d(af);
                sphere(r=ant_twin_edge_r, $fn=16);
            }
            // the thicker back behind the flare
            ant_axis_frame() ant_twin_slab(-bar_y/2 - ant_twin_back_pad, -bar_y/2 + 0.01)
                offset(r=ant_twin_corner_r) offset(delta=-ant_twin_corner_r)
                    square([ant_twin_back_pad_w, ant_twin_bar_z], center=true);
        }
        ant_axis_frame() {
            // the cover seat: the wall-side face inside the rim, down to the seat
            ant_twin_slab(seat, bar_y/2 + 1)
                offset(r=ant_twin_cover_gap) ant_twin_cover2d(af);
            // the channel along the bar, open to the seat, one floor
            ant_twin_slab(ant_twin_floor_y, seat + 1)
                square([ant_twin_sep, ant_twin_chan_z], center=true);
            for (s = [-1, 1]) let (a = ant_twin_side(af, s), sw = ant_twin_slot_w(a), i = s > 0 ? 0 : 1) {
                // the open slot under the tower, its floor where the hex seats
                ant_twin_slab(ant_twin_slot_y0(a), seat + 1)
                    translate([s*ant_twin_sep/2 - sw/2, -ant_twin_chan_z/2])
                        square([sw, ant_twin_chan_z/2 + ant_twin_pocket_z]);
                // the closed pocket above it, up to the panel: the hex body's size
                ant_twin_slab(ant_twin_slot_y0(a), ant_twin_pocket_y(a))
                    translate([s*ant_twin_sep/2 - sw/2, ant_twin_pocket_z - 0.01])
                        square([sw, ant_twin_top - ant_twin_panel_t - ant_twin_pocket_z + 0.01]);
                // the jack's hole through the panel
                translate([s*ant_twin_sep/2, 0, ant_twin_top - ant_twin_panel_t - 0.01])
                    ant_twin_teardrop(ant_twin_hole[i], ant_twin_panel_t + 0.02);
            }
            // the cover's inserts, from the seat into the body
            for (p = ant_twin_screw_xz(af))
                translate([p[0], seat - ant_twin_m2_depth, p[1]])
                    rotate([-90, 0, 0]) cylinder(d=ant_twin_m2_hole, h=ant_twin_m2_depth + 1, $fn=24);
        }
        ant_twin_bore();
        // where the bore breaks through the channel floor, a flare along the
        // bar so each cable can curve from the floor into the bore without
        // wrapping a sharp edge. The cable bends about Z (it arrives along X
        // and turns down), so the rounding has to be in the X-Y plane: the
        // bore's section just under the floor, hulled with a sphere the
        // channel's width either side of the mouth. The spheres reach 6mm
        // below the floor at X = +-11.5, which is why the bar has its thicker
        // back there (ant_twin_back_pad).
        hull() {
            intersection() {
                ant_twin_bore();
                ant_axis_frame() ant_twin_slab(-bar_y/2 - 1, ant_twin_floor_y) square([60, 60], center=true);
            }
            for (sx = [-1, 1]) ant_axis_frame()
                translate([sx * (ant_twin_bore/2 + 5), ant_twin_floor_y, 0]) sphere(d=ant_twin_chan_z, $fn=48);
        }
        ant_flange_insert_bores();
        // nothing may stand proud of the plate's outer face
        translate([-300, -300, -back_plate_t]) cube([600, 600, 600]);
    }
}

// The cover, laid out for printing: flat, outer face down, X across and Y up
// the antenna axis. Five M2 clearance holes; a pad on the inner face at each
// tower that reaches down over the jack's body (0.4mm clear of its corners);
// each side's frequency engraved in the outer face under its tower, read
// from behind the case, so it is mirrored here.
module antenna_mount_twin_cover(af = ant_twin_jack_af) {
    difference() {
        union() {
            linear_extrude(height = ant_twin_cover_t) ant_twin_cover2d(af);
            for (s = [-1, 1]) let (a = ant_twin_side(af, s), w = ant_twin_slot_w(a) - 0.4,
                                   t = ant_twin_seat(af) - (ant_twin_corners(a)/2 + 0.4))
                translate([s*ant_twin_sep/2 - w/2, 16, ant_twin_cover_t - 0.01])
                    cube([w, ant_twin_cover_top - 0.3 - 16, t + 0.01]);
        }
        for (p = ant_twin_screw_xz(af)) translate([p[0], p[1], -1]) {
            cylinder(d=ant_twin_screw_hole, h=ant_twin_cover_t + 2, $fn=24);
            cylinder(d=ant_twin_cbore_d, h=ant_twin_cbore_h + 1, $fn=32);   // the head's seat, in the outer face (z=0)
        }
        if (ant_twin_label_on)
            translate([0, 0, -0.01]) ant_twin_label_solid(af, ant_twin_label_depth + 0.01);
    }
}

// Each side's frequency, as a solid `h` deep from the outer face (z=0) in:
// cut from the cover above, and printed on its own as the lettering that
// fills the engraving in a second colour (antenna_mount_twin_cover_text_*,
// 2026-10-10). Mirrored, since the face is read from behind the case.
module ant_twin_label_solid(af = ant_twin_jack_af, h = ant_twin_label_depth) {
    for (s = [-1, 1]) let (i = s > 0 ? 0 : 1) if (ant_twin_labels[i] != "")
        translate([s * (ant_twin_sep/2 - 6), 0, 0]) mirror([1, 0, 0])
            linear_extrude(height = h) {
                translate([0, 2.5]) text(ant_twin_labels[i], size=ant_twin_label_size,
                    font="Liberation Sans:style=Bold", halign="center", valign="center");
                translate([0, -5.5]) text("MHz", size=ant_twin_label_size * 0.55,
                    font="Liberation Sans:style=Bold", halign="center", valign="center");
            }
}

// The cover in its seat on the body, for the checks and the preview.
module ant_twin_cover_placed(af = ant_twin_jack_af) {
    ant_axis_frame() translate([0, ant_twin_seat(af) + ant_twin_cover_t, 0])
        rotate([90, 0, 0]) antenna_mount_twin_cover(af);
}

// ---- probes for the checks --------------------------------------------
// A plug beside a cable, 12mm, straight down the bore from the flange face
// to below the crossbar: must meet nothing.
module ant_twin_bore_probe() {
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len - 20])
        cylinder(d=ant_twin_bore - 1, h=ant_stub_len + 20 - 0.5);
}
// Each jack's hex body, seated on its slot's floor with its corners along
// Y, standing from the channel up into the pocket: must meet nothing.
module ant_twin_jack_probe(af = ant_twin_jack_af) {
    for (s = [-1, 1]) let (a = ant_twin_side(af, s)) ant_twin_frame(s)
        translate([0, ant_twin_slot_y0(a) + ant_twin_corners(a)/2 + 0.1, 11])
            rotate([0, 0, 30])
                cylinder(d=ant_twin_corners(a) - 0.1, h=ant_twin_top - ant_twin_panel_t - 11 - 0.3, $fn=6);
}
// Each jack's barrel, 6.35, standing through the panel with the hex seated:
// must meet no panel.
module ant_twin_barrel_probe(af = ant_twin_jack_af) {
    for (s = [-1, 1]) let (a = ant_twin_side(af, s)) ant_twin_frame(s)
        translate([0, ant_twin_slot_y0(a) + ant_twin_corners(a)/2, ant_twin_top - ant_twin_panel_t - 1])
            cylinder(d=6.35, h=ant_twin_panel_t + 2, $fn=48);
}
// A rod lying along the channel, a little under its width: must be in air.
module ant_twin_channel_probe(af = ant_twin_jack_af) {
    ant_axis_frame() translate([0, (ant_twin_floor_y + ant_twin_seat(af))/2, 0]) rotate([0, 90, 0])
        cylinder(d=ant_twin_chan_z - 2, h=ant_twin_sep - 14, center=true);
}
// Thin rods through the cover's holes into the body's insert holes, from the
// cover's outer face down: open holes leave them whole.
module ant_twin_screw_probes(af = ant_twin_jack_af) {
    ant_axis_frame() for (p = ant_twin_screw_xz(af))
        translate([p[0], ant_twin_seat(af) - ant_twin_m2_depth + 1, p[1]])
            rotate([-90, 0, 0]) cylinder(d=2, h=ant_twin_m2_depth - 1 + ant_twin_cover_t, $fn=16);
}
// For the checks: the ring of panel round each jack hole, and a probe a
// little under the hole, down its middle.
module ant_twin_panel_ring(af = ant_twin_jack_af) {
    for (s = [-1, 1]) let (i = s > 0 ? 0 : 1) ant_twin_frame(s)
        difference() {
            translate([0, 0, ant_twin_top - ant_twin_panel_t]) cylinder(d=ant_twin_tower_w(ant_twin_side(af, s)) - 4, h=ant_twin_panel_t);
            translate([0, 0, ant_twin_top - ant_twin_panel_t - 1]) cylinder(d=ant_twin_hole[i] + 0.5, h=ant_twin_panel_t + 2);
        }
}
module ant_twin_hole_probe() {
    for (s = [-1, 1]) let (i = s > 0 ? 0 : 1) ant_twin_frame(s)
        translate([0, 0, ant_twin_top - ant_twin_panel_t - 0.5]) cylinder(d=ant_twin_hole[i] - 0.5, h=ant_twin_panel_t + 1);
}

// Each whip's swept envelope, straight up its axis from the top of its tower:
// 15mm across (the hinge housing) and 220mm long.
module ant_twin_envelopes() {
    for (s = [-1, 1]) ant_twin_frame(s)
        translate([0, 0, ant_twin_top]) cylinder(d=15, h=220);
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
    difference() {
        for (i = [0 : n_screws - 1])
            rotate([0, 0, i*360/n_screws + back_lip_skip])
                rotate_extrude(angle = span)
                    polygon([[ri, 0],
                             [ro, 0],
                             [ro, back_lip_h - back_lip_lead],
                             [ro - back_lip_lead, back_lip_h],
                             [ri, back_lip_h]]);
        back_key_notch();
    }
}

// The key itself, fused into the bore wall (it reaches half a wall-thickness
// into it). Its notch is cut from the plate's rib in back_lip().
module back_key() {
    r_wall = outer_dia/2 - wall;
    rotate([0, 0, back_key_a])
        translate([r_wall - back_key_reach, -back_key_w/2, 0])
            cube([back_key_reach + wall/2, back_key_w, back_key_h]);
}

module back_key_notch() {
    r_wall = outer_dia/2 - wall;
    rotate([0, 0, back_key_a])
        translate([r_wall - back_key_reach - 1, -(back_key_w/2 + back_key_clear), -1])
            cube([back_key_reach + 3, back_key_w + 2*back_key_clear, back_lip_h + 2]);
}

// The single pass-through, cut through the plate from below (2026-10-29):
// the window the trigger board's socket goes out through, the pocket in the
// outer face for a plug's moulding, the two bridge steps between them (see
// usbc_bridge_layer), and the holes for the two inserts its mount screws
// into.
module usbc_cutout() {
    fl = -back_plate_t + usbc_recess_d;     // the pocket's floor
    translate([usbc_cut_pos[0], usbc_cut_pos[1], 0]) {
        translate([0, 0, -back_plate_t - 1])
            linear_extrude(height = back_plate_t + 2) usbc_window2d();
        // the pocket, in the outer face (z = -back_plate_t)
        translate([0, 0, -back_plate_t - 1])
            linear_extrude(height = usbc_recess_d + 1)
                offset(r = usbc_recess_r) offset(delta = -usbc_recess_r)
                    square([usbc_recess_w, usbc_recess_h], center = true);
        // the first layer over the pocket: a slot the window's height, from
        // one side wall of the pocket to the other
        translate([0, 0, fl - 0.01])
            linear_extrude(height = usbc_bridge_layer + 0.01)
                square([usbc_recess_w, usbc_cut_h], center = true);
        // the second: the window's rectangle, its ends square
        translate([0, 0, fl + usbc_bridge_layer - 0.01])
            linear_extrude(height = usbc_bridge_layer + 0.01)
                square([usbc_cut_w, usbc_cut_h], center = true);
        for (sx = [-1, 1])
            translate([sx * usbc_screw_pitch/2, 0, -back_plate_t - 1])
                cylinder(d = insert_hole_dia, h = back_plate_t + 2);
    }
}

// The window, face on: the socket's own outline, usbc_cut_clear bigger all
// round, its ends round as the socket's shell's are.
module usbc_window2d() {
    hull() for (sx = [-1, 1])
        translate([sx * (usbc_cut_w/2 - usbc_cut_r), 0]) circle(r = usbc_cut_r);
}


// The screws come from INSIDE the case now, so the inserts live here in the
// flange rather than in posts on the plate.
//
// The old way could not be assembled. Sighting down a screw's axis, the
// socket mount's boss is 24mm wide either side of the antenna axis while the
// bolts sit only 15mm out, so every bolt except the bottom one is directly
// underneath it -- no driver reaches them at any angle, and no rotation of
// the bolt circle helps, because nothing on a 30mm circle clears a 48mm
// shadow. Measured, not guessed; the SMA mount's 22mm boss clears every bolt,
// which is why only the socket mount felt wrong.
//
// Reversing the screws sidesteps the boss entirely: the back plate is
// removable, so its inner face is open air at assembly time. It also makes
// the plate simpler -- three clearance holes instead of three posts standing
// inside the case. The cost is real and worth stating: the mount can no
// longer be taken off without removing the back plate.
module ant_flange_insert_bores() {
    for (i = [0 : n_ant_bolts - 1]) {
        a = i * 360/n_ant_bolts + 30;
        translate([ant_bolt_pcd/2*cos(a),
                   ant_mount_y + ant_bolt_pcd/2*sin(a),
                   -back_plate_t - ant_flange_insert_d])
            cylinder(d = ant_insert_bore, h = ant_flange_insert_d + 0.01);
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
    // Just a clearance hole now. The insert moved to the mount's flange, so
    // the plate no longer carries a pocket or a post -- the screw passes
    // straight through from the inside and threads into the mount.
    for (i = [0 : n_ant_bolts - 1]) {
        a = i * 360/n_ant_bolts + 30;
        translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a),
                   -back_plate_t - 1])
            cylinder(d = ant_bolt_d, h = back_plate_t + 2);
    }
}

// A ten-minute test coupon (2026-10-29): the piece of the back plate round
// the USB-C window, cut from back_plate() itself, so its window, pocket and
// insert holes are the plate's own. Press the two inserts in, screw the
// trigger board's mount on with the board and its stop in it, and plug the
// charger's cable in: it must click fully home, its moulding down in the
// pocket, before a whole plate is worth printing. It prints as the plate
// does, outer face down. It used to carry five sizes of the old connector's
// window.
usbc_gauge_size = [36, 18];
module usbc_gauge() {
    translate([-usbc_cut_pos[0], -usbc_cut_pos[1], back_plate_t])
        intersection() {
            back_plate();
            translate([usbc_cut_pos[0] - usbc_gauge_size[0]/2, usbc_cut_pos[1] - usbc_gauge_size[1]/2, -back_plate_t - 1])
                cube([usbc_gauge_size[0], usbc_gauge_size[1], back_plate_t + 2]);
        }
}

// The charger it needs, engraved in the plate's outer face above the USB-C
// pocket (2026-10-29). The trigger board asks the charger for 12 V, and one
// that has no 12 V, such as a Pi-style 5 V 5 A supply, never starts the
// radar and gives no sign why. Two lines of capitals 5 mm tall, 0.6 mm deep,
// in the font of the antenna cover's lettering. It is read from behind the
// case, so it is mirrored here. The plate prints outer face down, so the
// letters are its first three layers, open to the bed: they need no support.
// It stands 1.5 mm above the coupon's patch, so usbc_gauge is unchanged, and
// is well clear of every hole in the plate.
usbc_label       = ["USB-C PD", "12V 27W"];
usbc_label_cap   = 5;       // the capitals' height
usbc_label_size  = usbc_label_cap / 0.955;   // the text size for that: Liberation Sans Bold's capitals are 0.955 of it
usbc_label_pitch = 7.5;     // line to line, 2.5 mm between them
usbc_label_depth = 0.6;
usbc_label_pos   = [usbc_cut_pos[0],
                    usbc_cut_pos[1] + usbc_gauge_size[1]/2 + 1.5 + (usbc_label_pitch*(len(usbc_label) - 1) + usbc_label_cap)/2];

// The label's lines, face on as they read, centred on [0, 0].
module usbc_label2d() {
    for (i = [0 : len(usbc_label) - 1])
        translate([0, ((len(usbc_label) - 1)/2 - i) * usbc_label_pitch])
            text(usbc_label[i], size = usbc_label_size, font = "Liberation Sans:style=Bold",
                 halign = "center", valign = "center");
}

// Its letters as a solid h deep from the plate's outer face in, mirrored to
// read from behind: cut from back_plate(), and probed by the checks.
module usbc_label_solid(h = usbc_label_depth) {
    translate([usbc_label_pos[0], usbc_label_pos[1], -back_plate_t]) mirror([1, 0, 0])
        linear_extrude(height = h) usbc_label2d();
}

// ---- The power fix (roadmap 5.7, #53), 2026-10-17 ------------------------
// Three small parts for the 12 V trigger board and the 5 V regulator
// (docs/power-fix.md). The trigger board takes the charger's plug itself, in
// the back plate's USB-C window, so no panel-mount extension is needed.
// power_trigger_mount is a sleeve round the board, screwed to the plate's
// inner face; power_trigger_stop slides in behind the board, and two M2
// screws through the mount's side walls lock it there. power_regulator_tray
// holds the regulator, stuck to the plate's inner face wherever the case has
// room.
//
// The socket goes through the plate since 2026-10-29. The owner's power kept
// cutting out when the cable moved: the plug would not make a good
// connection. Until then the socket's face sat at the plate's inner face,
// behind the whole 3 mm plate, so a plug's moulding had to travel through a
// 2 mm pocket and an 11 x 8 window in the 1 mm web before the plug was home.
// A moulding a little too big, or a board a little off-centre, and it never
// got there. Now:
//   - The board's front edge bears on the plate's inner face, and its socket,
//     which stands pwr_trig_proud past that edge, goes out through a window
//     in the plate: the socket's own round-ended outline, usbc_cut_clear
//     bigger all round. The window locates the socket, and the plate takes
//     the pull of unplugging straight from the board's edge: no flange,
//     nothing printed between them.
//   - The pocket in the outer face goes past the socket's face, so a
//     moulding meets the socket and never the plate, and the plug goes fully
//     home.
//   - The mount sits flat on the plate's inner face, level with the board's
//     front edge. Its two M3 screws come from inside, through its ears, into
//     heat-set inserts in the plate, so nothing of them is in the outer face.
//   - The stop presses the board's back edge forward, so the board is held
//     between the plate and the stop with no play, and two ribs in the
//     tube's roof press its socket down, so the board lies on the tube's
//     floor and cannot rock.
// A first version (2026-10-17) clamped the board with a bezel in the pocket,
// which needed its front edge inside the window; the board measured 10.72 mm
// across, too close for a printed hole. It goes the other way now: only the
// socket goes through.
//
// The stop replaced a 1.75 mm filament pin (2026-10-29). The pin crossed the
// tube 0.25 mm behind the board, so the board had that much play and more as
// the pin bent. The owner put two M2 screws in the pin's holes instead, their
// tips pressing on the board; it held, but the power cut out twice in two
// days when the cable was jiggled. Now nothing touches the board but the
// plate in front, the stop's two crush ribs on its back edge, the tube's
// floor under it and the two ribs in the tube's roof on its socket, and the
// screws hold everything with no slack:
//   - The M2 screws thread into the stop: a solid block, so each gets more
//     than 4 mm of thread, which the mount's thin walls could never give.
//   - They thread through the walls too, rather than passing through
//     clearance holes. A screw in a clearance hole can shift by the hole's
//     slack when the board pushes on the stop, and crush ribs, once squeezed,
//     do not spring back to follow it: the board would have its play again.
//     Threaded in the wall, the screw has no slack to give.
//   - Each pilot in the stop has a countersink. Push the stop in until its
//     ribs touch the board's back edge; each screw, coming through its wall,
//     lands on the countersink and draws the stop the last 0.3 mm forward,
//     squeezing the ribs onto the board, before it threads in. The ribs take
//     up the board's and the print's tolerances, about 0.3 mm either way.
//     They are drawn 0.1 mm longer than that (pwr_rib_tip): in Bambu
//     Studio's slice of the stop, 0.8 mm ribs printed 0.71 mm proud of its
//     face, their tips rounded off by the nozzle's line, so they squeezed
//     the board by 0.21 mm, not 0.3, and a board 0.2 mm short got none.
//   - The two screws are staggered along the board, one in each wall, so each
//     can run most of the way across the stop: two on one line would meet in
//     the middle long before M2 x 8 was in.
//   - The stop's chamber is deeper than the board's tube and, below the
//     board's level, 0.6 mm narrower each side, and the stop is a T to match.
//     Upside down it would still take the screws, with its ribs under the
//     board's edge and the board loose; as a T it cannot go in that way far
//     enough for its holes to meet the walls'. The board cannot drop into the
//     deeper part either, on its way past, and the walls round the screws are
//     2.2 mm thick.
//   - The stop is keyed, so it goes in only the right way round (2026-10-29).
//     Back to front it went in as easily, the T being the same either way:
//     its pilots sit a pitch apart about the middle of its length, and their
//     countersinks, one on each side, change sides as it turns, so both
//     screws found one and drew the stop 0.5 mm back off the board, which
//     they left loose. Now a key runs along the bottom of the stop's +x side
//     at its back end (pwr_key_*), in a slot in the mount's +x wall. The
//     right way round the key follows the stop in, into its slot; back to
//     front it leads, on the side with no slot, and meets the end of the
//     mount before the stop is in, nowhere near the screws.
//
// The ribs in the tube's roof (2026-10-29). The plate and the stop hold the
// board along its length, but nothing held it from above: it had 0.4 mm of
// room up and down in the tube, its socket 0.3 either way in the window, and
// modelled, it could rock about 2.3 degrees about the window's lower edge
// before its socket met the roof, its back end rising 0.7 mm up the stop's
// ribs. Plug and socket move together, so that was not the old fault, but
// every jiggle of the cable worked the crushed ribs. Now the tube's floor is
// at the board's underside, so the socket sits in the middle of its window,
// and its roof is 2 x pwr_trig_clear over the socket, the board's room to
// slide in. Two crush ribs along the roof, over the socket's flat top and
// from the plate back pwr_top_rib_len, take that room up and press the
// socket down by pwr_top_rib_squeeze, so the board lies on the floor and
// cannot rock. They are the stop's 90-degree ribs, drawn pwr_rib_tip longer
// for the same reason, and their back ends are 45-degree ramps that the
// socket rides under on its way in. They are clear of the wires: those are
// soldered at the board's back edge.
//
// Measured on the owner's boards, 2026-10-17, except where it says otherwise.
pwr_trig_l        = 19.19;  // socket face to the board's back edge
pwr_trig_w        = 10.72;  // across the board
pwr_trig_t        = 4.83;   // the board's underside to the socket's flat top
pwr_trig_sock_w   = 8.94;   // the USB-C socket's shell, across: the standard size
pwr_trig_sock_t   = 3.26;   // and through, its ends round; it sits on top of the board
pwr_trig_proud    = 2.0;    // how far the socket's face stands past the board's front edge
// Round the board in the mount, a side: 0.25 until 2026-10-29, closer now
// that the board's socket goes through a close-fitting window. Since then
// none under the board, which lies on the tube's floor, and twice this over
// its socket, which the roof's ribs take up.
pwr_trig_clear    = 0.2;
pwr_mount_wall    = 1.6;
// The mount's two ears take its M3 screws (2026-10-29): button heads, from
// inside the case, through a clearance hole in each ear and 2.5 mm into an
// M3 x 3 insert in the plate. Each screw clamps its ear, 5.5 mm of plastic.
// The ear nearer the speaker at 0 degrees is under that speaker's corner,
// which starts 8 mm in from the plate, so the ears and the heads on them stop
// at 7.15. M3 x 8 is the length: an M3 x 10 would come 1.5 mm out of the
// plate's outer face, and an M3 x 6 would barely reach its insert. The
// asserts below hold both ends.
pwr_ear_od        = 7.5;
pwr_ear_t         = 5.5;
pwr_m3_len        = 8;
pwr_m3_head       = [5.7, 1.65];   // a button head (ISO 7380): across, and tall
// The stop and its two M2 screws (2026-10-29). M2 x 8 by default; M2 x 10
// fits too. M2 x 6 would leave under 4 mm of thread in the stop, and M2 x 12
// would reach the far wall. The asserts below hold both ends.
pwr_m2_len        = 8;
pwr_m2_pilot      = 1.65;   // thread-forming M2 in ASA, in the stop and in the walls
pwr_m2_wall       = 1.25;   // plastic round each pilot in the stop (1.2 at least)
pwr_m2_pitch      = 3.0;    // between the two screws, along the board
pwr_m2_csk        = 2.8;    // the countersink round each pilot's mouth in the stop
pwr_stop_clear    = 0.15;   // round the stop in its chamber, a side
pwr_stop_step     = 0.6;    // how much narrower, each side, the stop's body is than its top
pwr_rib_h         = 0.9;    // the stop's two crush ribs: 90-degree ridges across the board's back edge (0.8 until 2026-10-29)
pwr_rib_squeeze   = 0.3;    // how far they press into it once the screws are in, as printed
pwr_rib_tip       = 0.1;    // how much shorter a printed rib comes out than it is drawn: its tip is rounded off
pwr_rib_x         = 3.0;    // either side of the middle, well inside the board's 10.72
// The stop's key (2026-10-29): a 45-degree ridge along the bottom of the
// stop's +x side, pwr_key_t out from it and as far up it, for pwr_key_l
// forward from its back face. As the stop prints, upside down, the bottom is
// on top and the ridge's slope faces the bed, so it needs no support. Back
// to front, pushed over by its 0.15 mm of play, it still runs 0.7 mm into
// the mount's -x wall. It stays clear of the pilots, which are higher in the
// stop, and its slot in the mount stops behind the +x screw, so that screw's
// thread in the wall is whole; the slot, low in the chamber, also keeps the
// chamber narrower than the board above it.
pwr_key_t         = 1.0;
pwr_key_l         = 3.0;
// The two ribs along the tube's roof (2026-10-29), the same 90-degree
// ridges, over the socket's flat top: it is flat for 2.84 mm either side of
// the middle, and the wires' pads are at the board's back edge.
pwr_top_rib_x       = 1.5;  // either side of the middle
pwr_top_rib_len     = 4.0;  // along the socket from the plate, then a 45-degree ramp
pwr_top_rib_squeeze = 0.15; // how far they press into the socket's top, as printed
pwr_reg_l         = 63;     // the regulator: a 9-36 V to 5.2 V module, 63 x 27 (published)
pwr_reg_w         = 27;
pwr_reg_h         = 12.29;  // its tallest capacitor to the board's underside: 16 mm off the plate in the tray
pwr_reg_clear     = 0.5;    // a side
pwr_tray_floor    = 2;
pwr_tray_wall     = 2;
pwr_tray_wall_h   = 5;      // above the floor: it holds the board's edges, not its parts
pwr_tray_rib_w    = 3;
pwr_tray_rib_h    = 1.5;    // the board rests on two ribs; its solder joints stay clear
pwr_tie_w         = 6;      // grooves under the floor for an optional cable tie
pwr_tie_d         = 1.2;

// The back plate's window and the pocket's depth, from the board's sizes
// (2026-10-29). The window is the socket's outline usbc_cut_clear bigger all
// round: 0.3, because a printed hole comes out smaller than it is drawn, by a
// tenth or so a side, and ASA shrinks as it cools. The pocket's floor is
// usbc_seat_margin behind the socket's face: the floor prints as a bridge
// over the pocket, and a bridge sags, by a layer or more in ASA. Level with
// the socket's face, a sagging floor would stop a moulding just short of it,
// which is the fault this fixes. That leaves a web of 1.6 mm round the
// window, 60% more than the old 1 mm.
usbc_cut_clear    = 0.3;
usbc_cut_w        = pwr_trig_sock_w + 2*usbc_cut_clear;    // 9.54
usbc_cut_h        = pwr_trig_sock_t + 2*usbc_cut_clear;    // 3.86
usbc_cut_r        = usbc_cut_h/2;                          // round ends
usbc_seat_margin  = 0.4;
usbc_recess_d     = back_plate_t - pwr_trig_proud + usbc_seat_margin;   // 1.4
// The pocket's floor prints as a bridge in two steps, a layer each
// (2026-10-29). Left to itself, a slicer starts that floor with the window's
// two loops in mid-air, held by nothing, then lays the bridge from the
// pocket's sides up to them in stubs held at one end only: Bambu Studio's
// slice of the coupon did exactly that. Whatever sags hangs into the pocket
// where a moulding's face lands, and the floor is only usbc_seat_margin
// behind the socket's face. So the first layer over the pocket is open in a
// slot as tall as the window, right across the pocket: every line of that
// layer spans the pocket from one side wall to the other. The second is open
// in the window's rectangle, so its new plastic is two short bridges, 3.86 mm,
// across the slot's ends. The window's round ends start on the third layer,
// on solid plastic. Each step is one of the plate's 0.2 mm layers, and the
// pocket is seven of them deep, so each step is a layer of its own. Bambu
// Studio's counterbore hole bridging does worse with this shape: leave it off.
usbc_bridge_layer = 0.2;

assert(back_plate_t - usbc_recess_d < pwr_trig_proud,
       "the socket's face must stand past the pocket's floor, or a moulding stops on the plate short of it");
assert(abs(usbc_recess_d/usbc_bridge_layer - round(usbc_recess_d/usbc_bridge_layer)) < 1e-6,
       "the pocket must be a whole number of layers deep, so each bridge step is a layer of its own");
assert(usbc_cut_h/2 <= usbc_recess_h/2 - usbc_recess_r,
       "the first bridge step's slot must end on the pocket's straight side walls, not in its corners");
// The limits a reprint for a bigger moulding meets (2026-10-29), so each
// passes at its limit, not just short of it: at usbc_seat_margin = 0.6 or
// usbc_recess_w = 16.8 the plain sums come out a hair under 1.0, 1.4 and 1.6.
assert(back_plate_t - usbc_recess_d - 2*usbc_bridge_layer >= 1.0 - 1e-6,
       "the window's round-ended part, above the two bridge steps, must be at least 1 mm of plate");
// The board's front edge bears on the plate over the pocket, which takes the
// pull of unplugging (2026-10-29): back_plate_t - usbc_recess_d thick, 1.6 mm
// as drawn. The deeper pocket, at usbc_seat_margin = 0.6, thins it to 1.4,
// and it may be no thinner. With 0.2 mm layers the window's limit above
// lands there too; this one holds whatever the layers are.
assert(back_plate_t - usbc_recess_d >= 1.4 - 1e-6,
       "the plate the board's front edge bears on, over the pocket, must be at least 1.4 mm thick");
assert(pwr_trig_t - pwr_trig_sock_t - usbc_cut_clear >= 1.0,
       "the board's front edge must bear on at least 1 mm of plate below the window");
assert(usbc_cut_w < pwr_trig_w,
       "the window must be narrower than the board, or unplugging pulls the board through it");
assert(usbc_screw_pitch/2 - insert_hole_dia/2 - usbc_recess_w/2 >= 1.6 - 1e-6,
       "the inserts need 1.6 mm of plate between them and the pocket");
assert(usbc_insert_len <= back_plate_t,
       "the inserts must not stand out of the plate's outer face");
assert(pwr_m3_len - pwr_ear_t <= back_plate_t - 0.3,
       "the M3 screws must end inside the plate, short of its outer face: use a shorter screw");
assert(pwr_m3_len - pwr_ear_t >= 2,
       "the M3 screws need 2 mm of thread in their inserts: use a longer screw");
assert(pwr_ear_t >= 2.5,
       "each M3 screw must clamp at least 2.5 mm of plastic");
assert(pwr_ear_t + pwr_m3_head[1] <= (shell_depth - speaker_d)/2 - 0.5,
       "the ears, and the M3 heads on them, must stay under the speaker beside the window");

// In the plate's frame round the window (its centre at x = y = 0, the
// plate's inner face at z = 0, its outer face at z = -back_plate_t, the case
// inward along +z): the socket is centred in the window with its face at
// z = -pwr_trig_proud, in the pocket, and the board lies below it, its front
// edge on the plate at z = 0. The mount's flat face is on the plate too.
function pwr_board_y0() = pwr_trig_sock_t/2 - pwr_trig_t;          // the board's underside
function pwr_pcb_y1()   = pwr_board_y0() + pwr_trig_t - pwr_trig_sock_t;   // its top face, where the wires are soldered
function pwr_board_z1() = pwr_trig_l - pwr_trig_proud;             // its back edge
// The board's tube: its floor at the board's underside, where the roof's
// ribs hold it (2026-10-29: pwr_trig_clear lower until then), and its roof
// 2 x pwr_trig_clear over the socket, the same all along.
function pwr_tube_y0()  = pwr_board_y0();
function pwr_tube_y1()  = pwr_trig_sock_t/2 + 2*pwr_trig_clear;
// the roof's ribs, from the roof to their tips: its room over the socket,
// the squeeze, and what a printed tip loses
function pwr_top_rib_h() = pwr_tube_y1() - pwr_trig_sock_t/2 + pwr_top_rib_squeeze + pwr_rib_tip;
// The stop, in the same frame. Its top part is the tube's width less its
// clearance, and reaches 2 x pwr_trig_clear under the board's top face, so
// the wires soldered there pass over it; below the board's level its body is
// narrower (pwr_stop_hw) and carries the two M2 pilots, with pwr_m2_wall of
// plastic past their teardrop roofs too. Its front face stands
// pwr_rib_h - pwr_rib_squeeze - pwr_rib_tip behind the board's back edge, so
// only the ribs reach the board.
function pwr_tube_w()   = pwr_trig_w + 2*pwr_trig_clear;
function pwr_stop_hw()  = pwr_tube_w()/2 - pwr_stop_step - pwr_stop_clear;
function pwr_stop_y1()  = pwr_pcb_y1() - 2*pwr_trig_clear;
function pwr_m2_y()     = pwr_stop_y1() - pwr_m2_wall - pwr_m2_pilot/2;
function pwr_stop_y0()  = pwr_m2_y() - pwr_m2_pilot/2*sqrt(2) - pwr_m2_wall;
function pwr_stop_z0()  = pwr_board_z1() + pwr_rib_h - pwr_rib_squeeze - pwr_rib_tip;
// the screws' axes along the board: [the one through the +x wall, the one through the -x wall]
function pwr_m2_z()     = [pwr_stop_z0() + pwr_m2_wall + pwr_m2_pilot/2,
                           pwr_stop_z0() + pwr_m2_wall + pwr_m2_pilot/2 + pwr_m2_pitch];
function pwr_stop_z1()  = pwr_m2_z()[1] + pwr_m2_pilot/2 + pwr_m2_wall;
function pwr_mount_len() = pwr_stop_z1() + 0.4;                    // the tube's back end, just past the stop's
// from a wall's outer face, where a screw's head sits, to the stop's far side
function pwr_m2_reach() = pwr_mount_wall + pwr_stop_step + pwr_stop_clear + 2*pwr_stop_hw();
// a screw's full thread in the stop: its length less the wall, the gap and the countersink
function pwr_m2_engaged() = pwr_m2_len - pwr_mount_wall - pwr_stop_step - pwr_stop_clear - (pwr_m2_csk - pwr_m2_pilot)/2;
assert(pwr_m2_engaged() >= 4,
       "the M2 screws must have at least 4 mm of thread in the stop: use a longer screw");
assert(pwr_m2_len <= pwr_m2_reach() - 0.5,
       "the M2 screws must end inside the stop, short of the far wall: use a shorter screw");
assert(pwr_m2_pitch >= pwr_m2_pilot + 1.2,
       "the two M2 pilots need 1.2 mm of plastic between them");
assert(pwr_rib_squeeze > 0 && pwr_rib_squeeze + pwr_rib_tip < pwr_rib_h - 0.3,
       "the ribs must reach into the board's back edge, and the stop's face stay clear of it");
assert(pwr_rib_squeeze + pwr_rib_tip < (pwr_m2_csk - pwr_m2_pilot)/2,
       "the countersinks must be able to draw the stop forward as far as its ribs squeeze");
assert(pwr_stop_hw() + pwr_stop_clear < pwr_trig_w/2 - 0.2,
       "the stop's chamber must be narrower than the board below its level, so the board cannot drop into it");
assert(pwr_top_rib_squeeze > 0 && pwr_top_rib_x + pwr_top_rib_h() <= pwr_trig_sock_w/2 - pwr_trig_sock_t/2,
       "the roof's ribs must press on the socket's flat top, not on its round ends");
assert(pwr_key_t - 2*pwr_stop_clear >= 0.5,
       "back to front, the stop's key must still run 0.5 mm into the mount's wall with the stop pushed over by its play");
assert(pwr_stop_y0() + pwr_key_t <= pwr_m2_y() - pwr_m2_pilot/2*sqrt(2) - 0.2,
       "the stop's key must stay 0.2 mm below the ends of the pilots in its side");
assert(pwr_mount_wall + pwr_stop_step - pwr_key_t >= 1.2,
       "the key's slot must leave 1.2 mm of the mount's wall behind it");
assert(pwr_stop_z1() - pwr_key_l - pwr_stop_clear >= pwr_m2_z()[0] + pwr_m2_pilot/2*sqrt(2) + 0.5,
       "the key's slot must stop short of the +x screw's pilot in the wall, so that screw's thread is whole");

// A hole along x that prints without support with z up: round, with a
// 45-degree roof toward +z. The mount prints flat face down, z up; the stop
// turns it to suit the way it prints.
module pwr_x_teardrop(d, h) {
    rotate([0, 90, 0]) linear_extrude(height = h, center = true)
        hull() { circle(d = d); translate([-d/2*sqrt(2), 0]) square(0.01, center = true); }
}

// The socket's shell, face on: pwr_trig_sock_w x pwr_trig_sock_t, its ends
// round. grow makes it bigger all round, for the checks.
module pwr_socket2d(grow = 0) {
    hull() for (sx = [-1, 1])
        translate([sx * (pwr_trig_sock_w/2 - pwr_trig_sock_t/2), 0]) circle(d = pwr_trig_sock_t + 2*grow);
}

// The roof's two ribs, in the mount's frame (2026-10-29): 90-degree ridges
// along the tube's roof over the socket's flat top, from the plate back
// pwr_top_rib_len, each ending in a 45-degree ramp for the socket to ride
// under on its way in. As the mount prints, z up, they are two ridges up the
// roof's wall from the bed, and each ramp is the top of its ridge going back
// into the wall, so nothing overhangs.
module pwr_top_ribs() {
    h = pwr_top_rib_h();
    y1 = pwr_tube_y1();
    for (sx = [-1, 1]) translate([sx*pwr_top_rib_x, 0, 0]) hull() {
        linear_extrude(height = pwr_top_rib_len) polygon([[-h, y1 + 0.01], [h, y1 + 0.01], [0, y1 - h]]);
        translate([0, 0, pwr_top_rib_len + h])
            linear_extrude(height = 0.01) polygon([[-0.01, y1 + 0.01], [0.01, y1 + 0.01], [0, y1]]);
    }
}

// The stop's key, face on, in the mount's frame (2026-10-29): a 45-degree
// ridge on the bottom corner of the stop's +x side, pwr_key_t out and as far
// up, its slope facing the stop's top.
module pwr_key2d() {
    hw = pwr_stop_hw();
    y0 = pwr_stop_y0();
    polygon([[hw - 0.01, y0], [hw + pwr_key_t, y0], [hw - 0.01, y0 + pwr_key_t + 0.01]]);
}

// Its slot in the mount's +x wall: the key pwr_stop_clear bigger all round,
// as the rest of the stop is in its chamber, the slot's sharp outer corner
// cut off square, so the wall behind it keeps 1.2 mm.
module pwr_key_slot2d() {
    intersection() {
        offset(delta = pwr_stop_clear) pwr_key2d();
        translate([0, -50]) square([pwr_stop_hw() + pwr_key_t + pwr_stop_clear, 100]);
    }
}

// The trigger mount, in place (it goes at usbc_cut_pos). It prints as it
// sits, flat face down: the face that goes on the plate, with the ears'
// faces in it. The board's tube is open at the front, the board's front edge
// level with the face. Behind the board the tube's floor drops to make a
// chamber for the stop; a 45-degree step underneath carries the deeper part,
// so nothing overhangs, and the M2 pilots through the walls are teardrops.
// ribs = false leaves the roof's ribs off, for the checks.
module power_trigger_mount(ribs = true) {
    cw = pwr_tube_w();
    y0 = pwr_tube_y0();                       // the tube's floor, the board on it
    y1 = pwr_tube_y1();                       // its roof, the same all along
    yk = y0 - pwr_stop_clear;                 // where the chamber narrows, under the stop's top
    yc = pwr_stop_y0() - pwr_stop_clear;      // the stop's floor
    hc = pwr_stop_hw() + pwr_stop_clear;      // the chamber's half-width below yk
    w  = pwr_mount_wall;
    px = usbc_screw_pitch/2;
    zc = pwr_board_z1();               // the chamber starts at the board's back edge
    len = pwr_mount_len();
    drop = y0 - yc;
    difference() {
        union() {
            translate([-cw/2 - w, y0 - w, 0]) cube([cw + 2*w, y1 - y0 + 2*w, len]);
            hull() {
                translate([-cw/2 - w, y0 - w, zc - drop]) cube([cw + 2*w, y1 - y0 + 2*w, 0.01]);
                translate([-cw/2 - w, yc - w, zc]) cube([cw + 2*w, y1 - yc + 2*w, len - zc]);
            }
            // the ears, on the plate with the rest of the face
            for (sx = [-1, 1]) translate([sx*px, 0, 0]) cylinder(d = pwr_ear_od, h = pwr_ear_t);
            translate([-px, -pwr_ear_od/2, 0]) cube([2*px, pwr_ear_od, pwr_ear_t]);
        }
        // the board's tube, open at both ends, less the roof's ribs
        difference() {
            translate([-cw/2, y0, -1]) cube([cw, y1 - y0, len + 2]);
            if (ribs) pwr_top_ribs();
        }
        // the stop's chamber behind it: as wide down to just under the board's
        // floor, then narrower and deeper
        translate([-cw/2, yk, zc]) cube([cw, y1 - yk, len]);
        translate([-hc, yc, zc]) cube([2*hc, yk - yc + 0.01, len]);
        // a 0.5 mm lead-in round the back end, for the board and the stop
        translate([0, 0, len - 0.5]) hull() {
            translate([-cw/2, yk, 0]) cube([cw, y1 - yk, 0.01]);
            translate([-cw/2 - 0.5, yk - 0.5, 0.51]) cube([cw + 1, y1 - yk + 1, 0.01]);
        }
        translate([0, 0, len - 0.5]) hull() {
            translate([-hc, yc, 0]) cube([2*hc, yk - yc, 0.01]);
            translate([-hc - 0.5, yc - 0.5, 0.51]) cube([2*hc + 1, yk - yc + 1, 0.01]);
        }
        // the slot for the stop's key (2026-10-29), in the +x wall at the
        // chamber's floor, from just in front of where the key ends to the
        // back end, and its own 0.5 mm lead-in there
        translate([0, 0, pwr_stop_z1() - pwr_key_l - pwr_stop_clear]) linear_extrude(height = len) pwr_key_slot2d();
        translate([0, 0, len - 0.5]) hull() {
            linear_extrude(height = 0.01) pwr_key_slot2d();
            translate([0, 0, 0.51]) linear_extrude(height = 0.01) offset(delta = 0.5) pwr_key_slot2d();
        }
        // the M2 pilots, one through each side wall, staggered along the board
        for (i = [0, 1]) let (sx = i == 0 ? 1 : -1)
            translate([sx*(hc + cw/2 + w)/2, pwr_m2_y(), pwr_m2_z()[i]]) pwr_x_teardrop(pwr_m2_pilot, cw/2 + w - hc + 1);
        // the M3 screws' clearance holes through the ears, each with a 1 mm
        // chamfer at the face: room for the insert's end and any plastic it
        // has raised round its hole
        for (sx = [-1, 1]) translate([sx*px, 0, 0]) {
            translate([0, 0, -1]) cylinder(d = screw_clear_dia, h = pwr_ear_t + 2);
            translate([0, 0, -0.01]) cylinder(d1 = screw_clear_dia + 2, d2 = screw_clear_dia, h = 1.01);
        }
    }
}

module power_trigger_mount_placed(ribs = true) { translate([usbc_cut_pos[0], usbc_cut_pos[1], 0]) power_trigger_mount(ribs); }

// The stop, in the mount's frame, where the two screws hold it: a T, its top
// the tube's width and its body narrower. Its crush ribs run up its front
// face across the board's back edge, from just above the tube's floor to the
// stop's top; ribs = false leaves them off, for the checks. Both pilots run
// right across, each countersunk on the side its screw comes in from; they
// are teardrops, roofed toward the stop's bottom, which is up as it prints.
// The key along the bottom of its +x side, at its back end, makes it go in
// only the right way round (2026-10-29); key = false leaves it off, for the
// checks.
module power_trigger_stop_shape(ribs = true, key = true) {
    hw = pwr_stop_hw();
    ht = pwr_tube_w()/2 - pwr_stop_clear;     // the top's half-width
    yk = pwr_tube_y0();                       // the top's underside, level with the tube's floor
    y0 = pwr_stop_y0(); y1 = pwr_stop_y1();
    z0 = pwr_stop_z0(); z1 = pwr_stop_z1();
    yr = yk + 0.1;
    csk = (pwr_m2_csk - pwr_m2_pilot)/2;
    difference() {
        union() {
            translate([-hw, y0, z0]) cube([2*hw, yk - y0 + 0.01, z1 - z0]);
            // the top, its two upper edges chamfered: they are on the bed as
            // it prints, where the first layer spreads
            translate([0, 0, z0]) linear_extrude(height = z1 - z0)
                polygon([[-ht, yk], [ht, yk], [ht, y1 - 0.4], [ht - 0.4, y1], [-ht + 0.4, y1], [-ht, y1 - 0.4]]);
            if (ribs) for (sx = [-1, 1])
                translate([sx*pwr_rib_x, yr, z0]) rotate([-90, 0, 0]) linear_extrude(height = y1 - yr)
                    polygon([[-pwr_rib_h, -0.01], [pwr_rib_h, -0.01], [0, pwr_rib_h]]);
            if (key) translate([0, 0, z1 - pwr_key_l]) linear_extrude(height = pwr_key_l) pwr_key2d();
        }
        for (i = [0, 1]) let (sx = i == 0 ? 1 : -1, z = pwr_m2_z()[i]) {
            translate([0, pwr_m2_y(), z]) rotate([90, 0, 0]) pwr_x_teardrop(pwr_m2_pilot, 2*ht + 2);
            translate([sx*(hw + 0.01), pwr_m2_y(), z]) rotate([0, -sx*90, 0])
                cylinder(d1 = pwr_m2_csk + 0.02, d2 = pwr_m2_pilot, h = csk + 0.01);
        }
    }
}

module power_trigger_stop_placed() { translate([usbc_cut_pos[0], usbc_cut_pos[1], 0]) power_trigger_stop_shape(); }

// The stop as it prints: on its top face, the T's wide part down, so its
// narrower body stands on it with nothing overhanging; the ribs rise from the
// bed up its front face, the pilots lie level, roofed upward, and the key's
// 45-degree slope faces the bed, at the top.
module power_trigger_stop() {
    translate([0, 0, pwr_stop_y1()]) rotate([-90, 0, 0]) translate([0, 0, -pwr_stop_z0()])
        power_trigger_stop_shape();
}

// The board itself, as the mount holds it, for the checks: its circuit
// board, the front edge on the plate, and its socket's shell, round-ended,
// from its face 7 mm back.
module power_trigger_board_placed() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], 0]) {
        translate([-pwr_trig_w/2, pwr_board_y0(), 0])
            cube([pwr_trig_w, pwr_trig_t - pwr_trig_sock_t, pwr_board_z1()]);
        translate([0, 0, -pwr_trig_proud]) linear_extrude(height = 7) pwr_socket2d();
    }
}

// A USB-C plug's shell (8.4 x 2.6), from out past the stand to the socket's face.
module power_plug_probe() {
    translate([usbc_cut_pos[0] - 4.2, usbc_cut_pos[1] - 1.3, -back_plate_t - 20])
        cube([8.4, 2.6, 20 + back_plate_t - pwr_trig_proud]);
}

// The two M2 screws as they sit, for the checks: each shank d across and len
// long, in from its wall's outer face, and its head (a cap or pan head, 4 mm
// across and 2 tall) on that face.
module power_m2_probe(d = 2.0, len = pwr_m2_len, head = true) {
    for (i = [0, 1]) let (sx = i == 0 ? 1 : -1)
        translate([usbc_cut_pos[0] + sx*(pwr_tube_w()/2 + pwr_mount_wall), usbc_cut_pos[1] + pwr_m2_y(), pwr_m2_z()[i]]) {
            rotate([0, -sx*90, 0]) cylinder(d = d, h = len, $fn = 24);
            if (head) rotate([0, sx*90, 0]) cylinder(d = 4.0, h = 2.0, $fn = 24);
        }
}

// The two M3 screws as they sit, for the checks: each shank d across and len
// long, from its ear's face away from the plate toward the plate, and its
// button head on that face.
module power_m3_probe(d = 3.0, len = pwr_m3_len, head = true) {
    for (sx = [-1, 1])
        translate([usbc_cut_pos[0] + sx*usbc_screw_pitch/2, usbc_cut_pos[1], pwr_ear_t]) {
            translate([0, 0, -len]) cylinder(d = d, h = len, $fn = 24);
            if (head) cylinder(d = pwr_m3_head[0], h = pwr_m3_head[1], $fn = 24);
        }
}

// The two M3 x 3 inserts as they are pressed into the plate, d across (4.5,
// their knurl), flush with its outer face, for the checks.
module power_insert_probe(d = 4.5) {
    for (sx = [-1, 1])
        translate([usbc_cut_pos[0] + sx*usbc_screw_pitch/2, usbc_cut_pos[1], -back_plate_t])
            cylinder(d = d, h = usbc_insert_len, $fn = 32);
}

// The board's two output wires, 18 AWG (2.1 mm across), soldered on its top
// face near the back edge and laid straight out past the mount's back end,
// for the checks. dy moves them up or down.
module power_wire_probe(dy = 0) {
    for (sx = [-1, 1])
        translate([usbc_cut_pos[0] + sx*2.6, usbc_cut_pos[1] + pwr_pcb_y1() + 1.05 + dy, pwr_board_z1() - 3])
            cylinder(d = 2.1, h = pwr_mount_len() - pwr_board_z1() + 13, $fn = 24);
}

// The regulator's tray, printed and fitted floor down. The board's long axis
// is x; both ends stay open for its terminals, jack and USB socket.
module power_regulator_tray() {
    iw = pwr_reg_w + 2*pwr_reg_clear;
    il = pwr_reg_l + 2*pwr_reg_clear;
    w  = pwr_tray_wall;
    difference() {
        union() {
            translate([-il/2, -iw/2 - w, 0]) cube([il, iw + 2*w, pwr_tray_floor]);
            for (sy = [-1, 1])
                translate([-il/2, sy > 0 ? iw/2 : -iw/2 - w, 0]) cube([il, w, pwr_tray_floor + pwr_tray_wall_h]);
            for (sy = [-1, 1])
                translate([-il/2, sy > 0 ? iw/2 - pwr_tray_rib_w : -iw/2, 0])
                    cube([il, pwr_tray_rib_w, pwr_tray_floor + pwr_tray_rib_h]);
        }
        for (x = [-il/4, il/4])
            translate([x - pwr_tie_w/2, -iw/2 - w - 1, -0.01]) cube([pwr_tie_w, iw + 2*w + 2, pwr_tie_d]);
    }
}

// The Pi's 58x49 mounting posts, M2.5 pilot holes, 8mm tall. Not part of
// the plate any more (see back_plate); defined so they can come back.
module pi_posts() {
    for (x = [-mount_hole_x/2, mount_hole_x/2])
        for (y = [-mount_hole_y/2, mount_hole_y/2])
            translate([x, y, 0])
                difference() {
                    cylinder(d=7, h=8);
                    cylinder(d=2.5, h=9);
                }
}

module back_plate() {
    difference() {
        union() {
            translate([0,0,-back_plate_t])
                cylinder(d=outer_dia, h=back_plate_t);

            // No Pi posts. The four 58x49 standoffs that stood here were
            // the Pi's original mounting, kept "as an alternative" once the
            // Pi moved onto the display's back; nobody used them in a year
            // and the owner asked for them gone (2026-10-07). pi_posts()
            // below is left defined but unused, so they are one line away.
            back_lip();
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
        // One pass-through, for the trigger board's socket (2026-10-29).
        usbc_cutout();
        // and the charger it needs, engraved above it (2026-10-29)
        translate([0, 0, -0.01]) usbc_label_solid(usbc_label_depth + 0.01);
        // The grilles cut a band from z=-1 to wall+1; shifted down by the
        // plate thickness that band covers the plate exactly.
        translate([0,0,-back_plate_t]) intake_grille();
        translate([0,0,-back_plate_t]) fan_grille();
        // The antenna mount screws into inserts here; its coax comes through
        // the middle of the bolt circle rather than through its own gland.
        ant_insert_bores();
        translate([0, ant_mount_y, -back_plate_t - 1])
            cylinder(d=ant_plate_hole, h=back_plate_t + 2);
        // its inner edge chamfered: both cables bend over it on the way to
        // the receiver, and a sharp printed edge would wear the jackets
        translate([0, ant_mount_y, -1.5])
            cylinder(d1=ant_plate_hole, d2=ant_plate_hole + 3, h=1.5 + 0.01);
    }
}

module front_posts() {
    top = shell_depth - lip_height + shelf_h;
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), top - front_post_h]) {
            cylinder(d=post_od, h=front_post_h);
            translate([0, 0, -front_post_cone])
                cylinder(d1=post_od - 2*front_post_cone, d2=post_od, h=front_post_cone);
        }
    }
}

// Cut after the whole shell is unioned: at 0 and 180 degrees a speaker
// bracket lands in a post, and would fill a hole cut any earlier.
module front_post_holes() {
    top = shell_depth - lip_height + shelf_h;
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), top - front_insert_len - 1])
            cylinder(d=insert_hole_dia, h=front_insert_len + 1 + 0.01);
    }
}

// The shelf's 45-degree underside (2026-10-29): a ring of slope under the
// shelf, from shelf_slope_r0 at the shelf's underside out and down to the
// wall, drawn 0.3mm into both so it fuses with them. Cut away over each
// speaker's sleeve (its full 100mm width), over shelf_slope_skip, and over
// the shelf's gap at the bottom, where there is no shelf to hold up.
module shelf_slope() {
    z1 = shell_depth - lip_height;      // the shelf's underside
    r1 = outer_dia/2 - wall;            // the bore
    difference() {
        rotate_extrude()
            polygon([[shelf_slope_r0 - 0.3, z1 + 0.3], [r1 + 0.3, z1 + 0.3],
                     [r1 + 0.3, z1 - (r1 - shelf_slope_r0) - 0.3]]);
        for (a = speaker_angles)
            rotate([0, 0, a]) translate([0, -speaker_w/2, -1]) cube([outer_dia, speaker_w, shell_depth + 2]);
        for (w = [shelf_slope_skip, [relief_center_deg - relief_arc_deg/2, relief_center_deg + relief_arc_deg/2]])
            rotate([0, 0, w[0]]) rotate_extrude(angle = w[1] - w[0])
                translate([0, -1]) square([outer_dia, shell_depth + 2]);
    }
}

module shell() {
    difference() {
        shell_body();
        front_post_holes();
    }
}

module shell_body() {
    difference() {
        union() {
            // Bored straight through: the back is a separate plate now.
            difference() {
                cylinder(d=outer_dia, h=shell_depth);
                translate([0,0,-1])
                    cylinder(d=outer_dia - 2*wall, h=shell_depth + 2);
            }
            back_posts();
            back_key();
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
    // Its underside slopes from r 103 to the wall (2026-10-29), so only its
    // inner 5mm needs support. See shelf_slope_r0.
    shelf_slope();

    // The front insert posts: from the shelf's top face (below the retainer)
    // down, merged into the wall, with a cone under each. Their holes are cut
    // in shell(), after everything is unioned, as back_post_holes() is.
    front_posts();


    // No dongle pocket. There was a fitted open-topped tray on the floor
    // here; it did not work in practice -- the dongle plus its USB lead and
    // the antenna pigtail do not sit the way a rigid tray assumes, and it
    // fought the cable routing rather than helping it. The dongle now just
    // lies in the cavity, which is what actually happens anyway.
}

// ============================================================
if (part == "front_trim") front_trim();
else if (part == "retainer") retainer_print();   // glass face down, as it prints
else if (part == "shell") shell();
else if (part == "back_plate") back_plate();
else if (part == "antenna_mount") antenna_mount();
else if (part == "antenna_mount_sma") antenna_mount_sma();
else if (part == "antenna_mount_twin") antenna_mount_twin();                 // the default style (ant_twin_jack_af)
else if (part == "antenna_mount_twin_8") antenna_mount_twin([8, 8]);         // for jumpers with 8mm hex bodies
else if (part == "antenna_mount_twin_11") antenna_mount_twin([11, 11]);      // for jumpers with 11mm hex bodies
else if (part == "antenna_mount_twin_cover") antenna_mount_twin_cover();
else if (part == "antenna_mount_twin_cover_8") antenna_mount_twin_cover([8, 8]);
else if (part == "antenna_mount_twin_cover_11") antenna_mount_twin_cover([11, 11]);
else if (part == "antenna_mount_twin_cover_text_8") ant_twin_label_solid([8, 8]);     // the lettering, for a second colour
else if (part == "antenna_mount_twin_cover_text_11") ant_twin_label_solid([11, 11]);
else if (part == "twin_assembled") { antenna_mount_twin(); ant_twin_cover_placed(); back_plate(); }  // for pictures
else if (part == "twin_assembled_11") { antenna_mount_twin([11, 11]); ant_twin_cover_placed([11, 11]); back_plate(); }
else if (part == "none") {}  // for a file that includes this one to draw its own views
else if (part == "usbc_gauge") usbc_gauge();
else if (part == "power_trigger_mount") power_trigger_mount();
else if (part == "power_trigger_stop") power_trigger_stop();
else if (part == "power_regulator_tray") power_regulator_tray();
else if (part == "antenna_socket_gauge") antenna_socket_gauge();
else if (part == "stand") stand();
else if (part == "test_rings") {
    // A 40-degree slice of the shell's back 29mm: both rings, the band below
    // them and the back rim, real shell() geometry. Prints back-down like the
    // shell, in about half an hour, to see how a material does the rings'
    // slope and lip before a seven-hour shell (2026-10-24).
    intersection() {
        shell();
        rotate([0, 0, 45]) rotate_extrude(angle = 40)
            translate([outer_dia/2 - 12, -1]) square([20, 30]);
    }
}
else if (part == "test_clip") {
    // The stand's cable clip in a 24 x 33 mm piece of the plinth's back, to
    // try the charger's cable in before printing the stand (2026-10-29).
    intersection() {
        stand();
        translate([stand_clip_x - 12, stand_clip_y0 - 6, -1])
            cube([24, base_d/2 + plinth_rib_h - stand_clip_y0 + 6 + 1, base_h + 2]);
    }
}
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
    // assembled preview -- retainer seats on the shelf (world Z =
    // shell_depth - retainer_h to shell_depth), glass sits right on top
    // of retainer, and front_trim's local Z=0 (its inner, glass-overlap
    // band) lines up with the glass's own top face. front_trim's
    // rabbeted outer band then reaches back down exactly to shell_depth
    // -- the retainer's front face and the shell's rim -- with no gap left
    // to force shut. Placed by front_stack_placed() since 2026-10-29: the
    // trim stood on the panel's whole depth here, 4.83mm too far forward.
    color("SteelBlue") shell();
    color("SlateGray") front_stack_placed("retainer");
    color("LightBlue",0.4) front_stack_placed("glass");
    color("DimGray") front_stack_placed("trim");
}
