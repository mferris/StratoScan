// ============================================================
// StratoScan — KITTEN enclosure
//
// Same radar, same hardware, different animal. Every dimension that
// touches a physical part is copied verbatim from the Retro Radar
// build, which is printed and validated: the 203.34mm round panel, the
// Pi's 58x49 standoff pattern, the two 100x45mm speakers, the 30mm fan,
// the M3 screw ring, the USB-C and SMA bulkheads. Only the SHAPE is new.
//
// The design idea is that the round display IS the face. Everything
// else follows from that: ears above it, whiskers where the speakers
// already were, a nose on the bezel, and a stand shaped like a sitting
// cat with front paws and a curled tail.
//
// Parts (print all four):
//   1. front_trim — the face: bezel ring, nose, whisker grooves
//   2. retainer   — ring behind the glass (identical to the retro part)
//   3. shell      — the head: body cylinder + ears, all the internals
//   4. stand      — sitting body: plinth, cradle, paws, tail
//
// Assembly is unchanged: front_trim -> [glass] -> retainer -> shell,
// 8 M3 screws through the trim and retainer into heat-set inserts in
// the shell's posts. The head then sets down into the stand.
// ============================================================

part = "preview";  // front_trim | retainer | shell | stand | preview | exploded | test_ear | test_clip
// ---- Curve resolution ------------------------------------------------
// $fa/$fs rather than a fixed $fn, which is what this was before.
//
// A fixed count makes the flats grow with the feature, so the biggest, most
// looked-at surfaces come out roughest: at $fn=96 the head's 223mm rim had
// 7.3mm flats and the cradle 8.2mm, while every 3mm screw hole also got 96
// sides it had no use for. $fs caps the chord -- the width of one flat,
// which is what the eye reads as faceting -- so a big curve gets the facets
// and a small hole does not.
//
// 0.4mm is one extrusion width: below that the printer cannot reproduce the
// difference. $fa then bounds the count on very large radii. Together these
// give the head 0.97mm flats for about a quarter more mesh than $fn=96 --
// cheaper than raising $fn would have been, because the savings on small
// holes pay for the big surfaces.
$fs = 0.4;   // max chord in mm
$fa = 0.5;   // max degrees per fragment

// ============================================================
// HARDWARE CONTRACT — do not change these to suit the styling.
// They describe real parts. Copied from the Retro Radar build.
// ============================================================
panel_diameter    = 203.34;
panel_active      = 178.15;
panel_glass_depth = 6.45;   // whole panel module (preview only, NOT the rabbet)
glass_thickness   = 1.62;   // the glass sheet alone — this is what the rabbet spans

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
rim = 10;
outer_dia = panel_diameter + 2*rim;   // 223.34
wall = 3;

glass_overlap     = 4;
retention_opening = panel_diameter - 2*glass_overlap;
front_trim_h  = 4;
retainer_h    = 4;
// Radial clearance between the retainer and the shell's bore. It was zero
// (the ring drawn at exactly the bore's diameter), and the first print, a
// PETG ring in an ASA shell, had to be forced in (2026-10-09): ASA shrinks a
// little more than PETG, so the bore came out smaller than the ring. 0.4mm a
// side leaves a slip fit across both materials; the screws, not the bore,
// centre the ring.
retainer_clear = 0.4;
lip_height    = 6;
shelf_h       = lip_height - retainer_h;
rabbet_depth  = glass_thickness;

screw_r = panel_diameter/2 + rim/2;
n_screws = 8;
screw_clear_dia = 3.4;
// Heat-set inserts: the Kadrick M2-M5 kit. Its M3 inserts are 4.5mm across
// the knurl and 3.9mm at the lead-in, 3-8mm long. A 4.0 hole gives the knurl
// 0.25mm a side to melt into (4.2 left 0.15mm). Same as the retro case.
insert_hole_dia = 4.0;
post_od = 9;
// The 8 front posts hang 8mm below the shelf's top face, merged into the
// wall, with a 45-degree cone under each, so an M3x5 insert has plastic all
// round it. They were 2mm tall. Screws: M3x14. See the retro case's notes.
front_insert_len = 5;
front_post_h     = 8;
front_post_cone  = 4;

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

// ---- Removable back plate --------------------------------------------
// The back was a fixed floor with the electronics standing on it, so the
// only way in was through the glass. It is now a separate screwed plate,
// and everything that stood on the floor went with it: the standoffs, the
// fan mount, the intake and fan grilles, and the two cable glands.
//
// The Pi itself is mounted to the LCD panel, so taking the plate off
// exposes the back of the Pi and its cabling rather than removing it. The
// 58x49 standoffs that stood here as an alternative mounting were never
// used and are gone (2026-10-07); pi_posts() keeps their geometry.
//
// No locating spigot: a ring into the bore lands exactly where the eight
// screw posts are, since those straddle the bore wall. Eight screws on a
// 213mm circle locate the plate perfectly well on their own.
back_plate_t   = 3;    // same as the floor it replaces

// ---- Antenna mount ---------------------------------------------------
// The retro build carries the antenna on a turret out of the top of the
// case. There is no turret here -- it would be a spike out of a cat's
// skull -- so the antenna mounts on the back plate instead, behind the
// head, and only the antenna itself shows above the ears.
//
// Same socket as the retro turret, and counter-tilted by stand_angle the
// same way, so the antenna reads vertical once the whole case leans back in
// its cradle.
//
// The standoff is what makes that possible, and it is not decoration. A
// vertical antenna rising from a plate the same diameter as the head has to
// travel outward past a 111.7mm radius to clear it, and it gains z the whole
// way -- so mounted flat against the plate it converges on the head and
// fouls the top rim. Standing the socket back from the plate buys the height
// it needs to clear: at 12mm the antenna's 33mm envelope passes the rim with
// room to spare, at 0mm it cuts straight through it. antenna_clears_head in
// checks.scad is what holds that.
// Bolted on rather than moulded into the plate: it prints flat and
// support-free on its own, the plate does too, and the antenna angle can be
// changed later without reprinting the tray.
ant_stub_dia   = 26;   // the arm reaching back from the plate
ant_stub_len   = 30;   // how far back it reaches
// 30 is measured, not chosen. A vertical antenna rising from a plate the
// diameter of the head must travel out past a 111.7mm radius to clear it,
// gaining height toward the head the whole way -- so the arm is what buys
// the room to do that behind the head rather than through it. Swept against
// the antenna's own envelope: at 22mm it fouls the top rim even at nominal
// diameter, at 26mm it clears nominal but not +2mm, and at 30mm it still
// clears with 6mm of radial slack. antenna_clears_head holds it.
ant_barrel_len = 14;   // socket barrel, along the antenna's own axis
ant_flange_d   = 40;
ant_flange_t   = 7;   // 4 -> 7: the insert now lives in the FLANGE, not the plate
ant_flange_insert_d = 5.5;  // heat-set pocket depth, leaving 1.5mm of flange behind it
ant_bolt_pcd   = 30;
ant_bolt_d     = 3.4;
n_ant_bolts    = 3;

ant_mount_y        = 81;   // up the plate, inside its rim, and clear of the top screw (was 88, which covered it; 2026-10-07)
ant_mount_standoff = 26;   // how far the socket sits back from the plate
// 26 is not a guess. Swept against the antenna's own 33mm envelope: 12mm
// fouls the head's top rim by 876mm3, 18mm by 205mm3, and it comes clear at
// 24mm. 26 keeps a margin. The number is this large because a vertical
// antenna rising from a plate the same diameter as the head has to travel
// outward past a 111.7mm radius to clear it, gaining z the whole way -- the
// standoff is what buys the height to do that behind the head rather than
// through it.
// The socket the antenna's base sits down into, and the rim around it --
// "the lip" -- that stops the base falling out sideways once it is in.
//
// This was 33, and a printed one showed why that is wrong: the base is a
// flared cone slightly wider than 33 where it needs to pass, so it never got
// under the rim at all. It perched on top and tipped over, while the cable
// underneath ran through perfectly. "Won't QUITE fit" is the useful part of
// that report -- the miss is small, so the fix is a few millimetres and a way
// to get the base past the rim rather than a redesign.
//
// ant_socket_lead is what makes it leverageable: a chamfer at the mouth, so
// the base can be tipped in on one side and rolled under the far side instead
// of having to drop in dead square. Without it a socket only fits a base that
// is smaller than the hole in every direction at once.
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

back_post_h    = 9;    // insert post standing inside the case
back_insert_d  = 7;    // depth of the heat-set insert hole: an M3x6 insert + 1mm

// ---- Back plate: locating lip ----------------------------------------
// A rib standing off the plate's inner face that drops into the shell bore,
// so the plate lands centred and square and stays there while the screws go
// in -- rather than being juggled against eight holes at once.
//
// It cannot be a continuous ring. The eight insert posts straddle the bore
// wall (they span r=102.2..111.2, the wall is r=108.7..111.7), so a full
// ring at bore diameter would run straight through every one of them. It is
// eight arcs instead, one per gap between posts. That is also plenty: three
// points locate a circle, and this has eight.
back_lip_h    = 4;      // how far it stands into the bore
back_lip_t    = 2;      // radial thickness
back_lip_gap  = 0.35;   // radial clearance into the bore, per side
back_lip_lead = 1.2;    // chamfer on the outer top edge, so it self-guides
back_lip_skip = 9;      // degrees of clearance either side of each post
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
// The mount used to bolt through bare clearance holes, which needs a nut
// held inside the case while the bolt is turned outside. These are bosses
// on the INNER face taking M3 heat-set inserts instead, so the mount screws
// into the plate and can be taken off one-handed.
ant_insert_boss_od = 7.5;
ant_insert_bore    = 4.0;   // pilot for a standard M3 heat-set insert
ant_insert_h       = back_insert_d + 1;

// speakers — the cheeks
speaker_w = 100; speaker_d = 45; speaker_h = 21;
speaker_hole_x = 92; speaker_hole_y = 36;
speaker_screw_dia = 2.6;
speaker_boss_dia  = 6;
speaker_boss_h    = 4;
speaker_boss_len  = 6;     // the screw pads' depth, from the speaker's face into the sleeve
speaker_duct_wall = 1.6;   // the sleeve's walls (2026-10-23: it was a solid block)
speaker_bracket_depth = 15;
speaker_angles = [0, 180];

// fan
fan_size = 30; fan_hole_pitch = 25;
fan_plate_y = 50; fan_plate_t = 3; fan_plate_z0 = wall;
fan_plate_h = 35; fan_plate_w = 36;
fan_open_dia = 28; fan_axis_z = 21;
fan_boss_dia = 6; fan_boss_h = 4; fan_screw_pilot = 2.5;
fan_grille_dia = 26;
// Moved from [0, 68] to the opposite side. The antenna mount's flange is a
// 40mm disc centred at y=ant_mount_y (88), so it covered this grille from
// y=68 to y=81 -- the vent was underneath the mount, which is no use to
// anybody. Directly opposite it is clear of the flange, the standoffs, the
// USB-C window and the screw ring.
fan_grille_pos = [0, -68];

// floor intake
intake_dia = 54; intake_hole = 3; intake_pitch = 6;

// No side exhaust (2026-10-01). The ears are hollow and open at the back, and
// their hollows reach into the head, so warm air leaves through them. The
// side slots the kitten inherited from the retro case ran into the ear
// bases, the whisker grilles and the cradle, and were blind dents anyway
// (centred on the outer face, 2.5mm into a 3mm wall). checks.scad's
// top_wall_solid holds this.

stand_angle = 18;           // how far the head leans back in the cradle

// cradle + retention rails
cradle_clearance = 1;
cradle_id = outer_dia + 2*cradle_clearance;
cradle_od = cradle_id + 26;
cradle_arc = 130;
arm_w   = 16;
arm_gap = 26;
arm_a_inner = shell_depth/2 - arm_gap/2;
arm_b_inner = shell_depth/2 + arm_gap/2;
retain_clear = 0.5;
retain_w = 4;
retain_h = 4;
retain_segs = [[207, 38], [295, 38]];
// The front rail's underside slopes at 45 degrees to a small square lip
// (2026-10-29), so it prints without support; the rear rail stays square,
// since its underside is what bears on the rear arm. See the retro case.
retain_lip = 0.8;
keel_arc = 46;
keel_reach = 80;

// ============================================================
// KITTEN STYLING
// ============================================================
// EARS. Angles are measured from straight up and were chosen against
// two hard constraints, not by eye:
//   - the 8 insert posts sit every 45deg starting at 0, so an ear
//     centred on 45 or 135 would land on one;
//   - the antenna turret occupies +/-11deg around straight up.
// 30deg either side of vertical threads between both. The ear CAVITY
// additionally stops below the front lip zone (see ear_hollow_top), so
// however the styling is nudged later it can never eat into a post.
ear_angle      = 30;   // degrees either side of straight up
ear_half_base  = 30;   // half-width of the ear base
ear_height     = 54;   // how far the tip stands above the head's circle
ear_base_sink  = 12;   // how far the base reaches inside the circle, to fuse
ear_base_r     = 11;   // base corner rounding
ear_tip_r      = 8;    // tip rounding — a blunt tip prints far better than a point
ear_lean       = 9;    // tip offset outboard, so they splay rather than sit parallel
ear_front_skin = 4;    // solid skin left at the front of each ear
inner_ear_inset = 10;  // how much smaller the inner-ear recess is
inner_ear_depth = 2;   // must stay < ear_front_skin or it breaks through

// WHISKER GRILLES. The speakers keep their exact bracket and footprint;
// only the hole pattern over them changes, from a rectangular mesh to
// three drooping rows of dots that read as whiskers on each cheek.
whisker_rows      = 3;
whisker_per_row   = 7;
whisker_dot_dia   = 3.6;
whisker_dx        = 11;   // spacing along the cheek
whisker_dz        = 11;   // spacing between rows
whisker_droop     = 1.6;  // each step outboard drops this far, giving the curve

// NOSE + MUZZLE on the bezel. Everything here lives in the rim band
// (r 101.67..111.67) so it can never encroach on the glass or the
// active area, and the bezel's OUTER profile stays a true circle —
// a muzzle bulging past outer_dia would foul the front cradle arm,
// which reaches to z=57, a millimetre past the shell's front face.
nose_w = 17; nose_h = 11; nose_proud = 2.6; nose_r = 3;
// Where nose() puts itself: translate([0, -screw_r, ..]) is straight down.
// The whiskers are placed off this rather than off a literal, because the
// first version of them was rotated about 0 degrees instead and all six
// landed on the right-hand side of the face, ninety degrees from the nose
// they were supposed to flank. It printed that way before anyone noticed.
nose_angle = 270;
whisker_groove_w = 1.6;
whisker_groove_d = 0.9;
whisker_arc      = 9;     // degrees swept by each groove
// Offsets from the nose. Bounded at both ends: the nose is 17mm wide at this
// radius, which is +-4.6 degrees, and the neighbouring screw holes sit at
// +-45. So the usable band is roughly 6 to 42 degrees, and these three sit
// inside it with clearance at both ends -- see whisker_vs_screws and
// whisker_vs_nose in checks.scad.
whisker_offsets  = [7, 18, 29];

// Smallest angle between two bearings, in degrees. Used to find which screw
// position the nose is sitting on, so the answer tracks nose_angle instead
// of being written out as an index that stops being right the moment the
// nose moves.
function ang_gap(a, b) = abs(((a - b + 180) % 360 + 360) % 360 - 180);

// STAND — a sitting cat. Plinth is rounded rather than a slab.
base_w = outer_dia*0.86; base_d = 150; base_h = 16;
base_corner_r = 18;
// ---------- THE CHARGER CABLE'S CLIP (2026-10-29) ----------
// Nothing held the cable, so its weight and every tug levered the plug in the
// trigger board's socket, and a moving cable is what set off the power cuts.
// The plug points straight back, 18 degrees down, from the window at
// usbc_cut_pos; its end is about (60, 45) and 70mm above the desk, and the
// cable drops from it onto the back of the plinth, where the tail's root is.
// The root is solid from the desk up to z 25.5 there, so a groove under it
// would be a closed tunnel that no plug can be threaded through, and a mouth
// cut down through it to let the cable in would split the tail. So the groove
// runs along the root's inboard foot instead, 18mm inboard of the plug, which
// the slack loop takes up: the retro case's clip, the same section and the
// same numbers under the same names, from level with the root's front to the
// back edge, then round the edge and down the back face. With a slack loop of
// 40-50mm left up to the plug, a pull moves the stand before it moves the
// plug. Measure your cable first: this is for one about 4mm thick.
stand_cable_d    = 4;                 // the charger's cable: about 4mm, measure yours
stand_clip_grip  = 0.2;               // the groove is this much under the cable
stand_clip_mouth = stand_cable_d - 0.7;   // so it snaps in past 0.35mm a side
stand_clip_sink  = 2.5;               // from the top face, and the back face, to the cable's axis
stand_clip_bend  = 4;                 // the radius it turns down over the back edge, on its axis
cable_clip_x     = 41.4;              // the groove's side 0.2mm clear of the root at its widest (x 43.5)
cable_clip_y0    = 44;                // the groove's front end, level with the root's front
// PAWS. A real foreleg is not a flat capsule with domes stuck on: it is
// narrow and taller at the ankle, spreading and flattening forward into a
// pad, with four toes splayed across the front and visible clefts between
// them. Built from hulled ellipsoids rather than cylinders so the top is
// domed rather than a flat disc, and the toes are separate lobes that break
// the outline rather than bumps sitting on it.
// Bigger than the single-colour version by roughly 15%. In two colours the
// paws stop being a silhouette detail and become the thing the eye lands on,
// so they have to carry that attention. How far this can go is decided by
// the head, not by taste: the cradled shell's underside comes down to about
// z=27, and paws_vs_head / tail_vs_head in checks.scad are what say when it
// has gone too far.
paw_x      = 46;    // paws either side of centre
paw_w      = 43;    // across the toes, the widest point
paw_reach  = 40;    // how far they stretch forward of the plinth
paw_h      = 18;    // at the ankle, where it is tallest
paw_ankle_w = 0.62; // ankle width as a fraction of paw_w -- forelegs taper
n_toes     = 4;
toe_dia    = 13.5;
toe_splay  = 21;    // degrees between toe centres, fanned across the front
// The clefts grow with the toes or the bigger lobes merge back into one pad:
// the groove is the only thing making four toes read as four.
cleft_w    = 3.0;   // width of the groove between toes
cleft_d    = 6;     // how deep the groove cuts

// ---- Claws ------------------------------------------------------------
// Real claws standing off the front of each toe, not the grooves between
// them. The grooves were being read as the nails, which they were never
// meant to be -- they are only what makes four toes read as four.
//
// Their own colour body, so they can be a third filament (white claws on
// black toes reads best, since the toes are already black on white pads).
//
// Slightly down as well as forward: a cat's claw curves toward the ground.
// The tip comes down onto the desk (2026-10-29). It stopped 1.2mm short of it
// so the claws would not carry the stand and rock, but the pads are flat on
// the desk too, so a claw cut flat at z = 0 is level with them and carries
// nothing; held off, each claw began 1.2mm up in mid-air, on a first layer of
// 1mm2, and every toe 0.47mm up. Now both start on the bed (claws_on_the_bed
// in checks.scad).
claw_len     = 6.5;   // how far it stands off the toe
claw_base_d  = 3.6;   // where it leaves the toe
claw_tip_d   = 1.2;   // rounded rather than needle-sharp: printable, and safe
claw_base_dz = -1.8;  // relative to the toe centre
claw_tip_dz  = -5.6;  // tip drops this far: the droop, through the desk (-4.4 until 2026-10-29)

// TAIL. Thicker at the root and tapering to a rounded tip. It hugs the
// plinth around the right side, then climbs the right paw's outboard flank
// and comes to rest DRAPED OVER the foot -- which is what a sitting cat
// actually does with its tail, and reads far better than a tail held out at
// arm's length in front.
//
// Resting on the paw means tail and paw deliberately meet. The thing that
// must not happen is the tail passing THROUGH the foot at pad height, which
// reads as one fused lump; it has to cross over the top. tail_over_paw in
// checks.scad pins exactly that -- the tail must not intrude below z=11,
// the paw's lower half.
//
// It still has to stay clear of the cradled head, whose underside comes
// down to about z=27.
// Thicker than the single-colour version, and pushed out and up to match: a
// fatter tail on the same path would foul the plinth edge on the way round,
// and would sit lower on a paw that is now taller. The tip carries the white
// and is the part most meant to be seen, so it stays proud of the foot
// rather than sinking into it.
//
// It lies on the desk until it reaches the paw (2026-10-29). From the plinth's
// corner it used to rise gently, so it crossed about 25mm of air 3-14mm up
// before the paw, all of it printed on support. Now the three points before
// the paw sit 1.2mm into the desk, deep enough that the tube's sides leave it
// at about 30 degrees and need no support of their own, and from there it
// climbs at about 40 degrees beside the paw, which prints on its own. Over
// the paw it is as it was: it rises off the pad and the tip flicks up, and
// that part still wants a little support. tail_on_the_desk in checks.scad
// holds it.
tail_pts = [
    [ 58,  58,  11, 29],   // root, buried in the plinth
    [ 87,  48,  11, 28],
    [102,  22,  11, 25],   // hugging the plinth edge rather than standing off it
    [106, -10,  11, 23],
    [102, -40, 9.3, 21],   // on the desk (11 until 2026-10-29: 0.5mm up)
    [ 93, -66, 7.8, 18],   // on the desk (was 12)
    [ 82, -85, 6.8, 16],   // on the desk beside the right paw (was 16), then climbing
    [ 68, -98,  21, 14],   // up the paw's outboard flank
    [ 53, -104, 26, 12],   // draped across the pad
    [ 41, -103, 33, 10],   // and the tip flicked UP off the foot
];
// The tip lifts instead of lying flat, and that is a colour decision rather
// than a styling one. Resting on the pad put the white tip on top of a white
// paw, where it vanished -- the whole point of a white tip is that it reads
// against what surrounds it. Lifted, it is silhouetted against the
// background from every angle, and a flicked tail tip is what a sitting cat
// does anyway. tail_vs_head in checks.scad is what bounds how far it can go.

// How much the coloured bodies deliberately interfere along every seam.
// See the colour separation section: this is what stops two parts sharing a
// surface at identical coordinates, which is what makes a slicer stipple a
// white paw with black.
colour_overlap = 0.3;

// Where the black tail becomes the white tip, as a fraction of the path
// measured back from the end. A cat's tail tip is a short dip, not a
// gradient: too long and it reads as a two-tone tail rather than a black
// tail with a white end.
tail_tip_frac = 0.20;

// ============================================================
// SHARED HELPERS
// ============================================================
module screw_ring_holes(dia, h) {
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), -h/2 - 1])
            cylinder(d=dia, h=h+2);
    }
}

// Everything strictly outside the head's outer surface. Used to clip
// styling cuts so they can only ever touch the ears, never the rim, the
// shelf or the insert posts.
//
// The clip diameter must be outer_dia exactly, not a few mm inside it.
// An earlier version used outer_dia - 4 to make the inner-ear dish blend
// into the face, which left the 2mm band between r=109.67 and the wall
// at r=111.67 fair game -- and the insert posts reach r=111.17, so the
// dish could shave the outer sliver off a post. Caught by the
// recess_vs_rim check in checks.scad; the dish now stops cleanly at the
// line where the ear meets the face, which also reads better.
module outside_head() {
    difference() {
        translate([-400,-400,-50]) cube([800,800,shell_depth+100]);
        translate([0,0,-60]) cylinder(d=outer_dia, h=shell_depth+120);
    }
}

// ============================================================
// EARS
// ============================================================
// A rounded triangle: hull of two base circles and one tip circle.
// `lean` shifts the tip sideways so the pair splays outward.
module ear_profile_2d(lean) {
    R = outer_dia/2;
    hull() {
        translate([-ear_half_base, R - ear_base_sink]) circle(r=ear_base_r);
        translate([ ear_half_base, R - ear_base_sink]) circle(r=ear_base_r);
        translate([ lean, R + ear_height - ear_tip_r]) circle(r=ear_tip_r);
    }
}

module ears_solid() {
    for (s = [-1, 1])
        rotate([0, 0, -s * ear_angle])
            linear_extrude(height = shell_depth)
                ear_profile_2d(s * ear_lean);
}

// Hollow, so the ears are not 54mm of solid plastic each. Stops short
// of the front lip zone so the shelf and the 8 posts are untouchable
// from here regardless of how the ear styling is later adjusted.
ear_hollow_top = shell_depth - lip_height - 2;
// The hollow's top is a 45-degree tent (2026-10-29). It was flat at
// ear_hollow_top, 4,550 mm2 of roof printed on 53mm-tall supports inside each
// ear. Now, ear_tent_rise below that, every side of the hollow slopes inward
// at 45 degrees, so its top comes to a point at ear_hollow_top: the hollow's
// outline is 25.1mm from side to middle at its widest. Nothing of it is
// flat, so nothing in the ear needs support. The plastic it adds prints as
// infill, and comes to less than the support it saves.
ear_tent_rise = 25;
ear_tent_step = 1;   // each hull spans this much of the rise
// The two front posts that the hollows open over, at 45 and 135 degrees
// (2026-10-29). The hollows cut the head wall away from the back collar up to
// ear_hollow_top, so those two posts hung free there: each cone's tip was an
// island 45mm above the bed. ears_hollow() leaves the head wall standing from
// the edge of each ear's opening to ear_post_strip past its post, the whole
// height, so the cone lands on wall that grows from the back collar, as on
// the retro case. ear_post_strip past the post rather than either side of
// it, because the opening's edge is only 4.6-5.3 degrees beyond the post: a
// strip either side would leave a slit 2-4mm wide between them.
ear_posts      = [45, 135];   // for the right-hand ear (s = 1) and the left (s = -1)
ear_post_strip = 3;           // degrees, toward the middle of the ear

// One ear's hollow, face on: the ear's outline, a wall in.
module ear_hollow_2d(s) { offset(r = -wall) ear_profile_2d(s * ear_lean); }

// The head wall kept beside an ear's post: from the post, 10 degrees outboard
// (past the opening's edge) to ear_post_strip inboard, out to 0.01 past the
// head's outer face so no face of it lies on the head's own.
module ear_post_strip_kept(s) {
    a = s > 0 ? ear_posts[0] : ear_posts[1];
    rotate([0, 0, s > 0 ? a - 10 : a - ear_post_strip])
        rotate_extrude(angle = 10 + ear_post_strip)
            translate([0, -2]) square([outer_dia/2 + 0.01, shell_depth + 4]);
}

module ears_hollow() {
    z_e = ear_hollow_top - ear_tent_rise;   // where the tent's slopes start
    for (s = [-1, 1])
        difference() {
            rotate([0, 0, -s * ear_angle]) {
                translate([0,0,-1])
                    linear_extrude(height = z_e + 1 + 0.01) ear_hollow_2d(s);
                // the tent: the outline shrunk by u at z_e + u, hulled a step at a
                // time, its top no higher than ear_hollow_top
                for (t = [0 : ear_tent_step : ear_tent_rise - ear_tent_step])
                    hull() for (u = [t, t + ear_tent_step])
                        translate([0, 0, min(z_e + u, ear_hollow_top - 0.01)])
                            linear_extrude(height = 0.01) offset(r = -u) ear_hollow_2d(s);
            }
            ear_post_strip_kept(s);
        }
}

// The inner-ear dish, recessed into the front face. Clipped to
// outside_head() so it exists only where the ear stands clear of the
// bezel — it cannot reach the rim band or a post.
module inner_ear_recess() {
    intersection() {
        for (s = [-1, 1])
            rotate([0, 0, -s * ear_angle])
                translate([0,0, shell_depth - inner_ear_depth])
                    linear_extrude(height = inner_ear_depth + 1)
                        offset(r = -inner_ear_inset) ear_profile_2d(s * ear_lean);
        outside_head();
    }
}

// ============================================================
// INTERNALS — carried over unchanged from the validated build
// ============================================================
module intake_grille() {
    n = ceil(intake_dia / intake_pitch) + 2;
    for (row = [-n:n]) {
        y = row * intake_pitch * 0.866;
        x_off = (row % 2 == 0) ? 0 : intake_pitch/2;
        for (col = [-n:n]) {
            x = col * intake_pitch + x_off;
            if (x*x + y*y < (intake_dia/2)*(intake_dia/2))
                translate([x, y, -1]) cylinder(d=intake_hole, h=wall+2, $fn=10);
        }
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

module fan_mount() {
    difference() {
        union() {
            translate([-fan_plate_w/2, fan_plate_y, fan_plate_z0])
                cube([fan_plate_w, fan_plate_t, fan_plate_h]);
            for (dx = [-fan_hole_pitch/2, fan_hole_pitch/2])
                for (dz = [-fan_hole_pitch/2, fan_hole_pitch/2])
                    translate([dx, fan_plate_y + fan_plate_t, fan_axis_z + dz])
                        rotate([-90,0,0]) cylinder(d=fan_boss_dia, h=fan_boss_h, $fn=24);
            for (x = [-15, 15])
                translate([x - 1.5, fan_plate_y + fan_plate_t, fan_plate_z0])
                    cube([3, 15, 14]);
        }
        translate([0, fan_plate_y - 1, fan_axis_z])
            rotate([-90,0,0]) cylinder(d=fan_open_dia, h=fan_plate_t + 2, $fn=48);
        for (dx = [-fan_hole_pitch/2, fan_hole_pitch/2])
            for (dz = [-fan_hole_pitch/2, fan_hole_pitch/2])
                translate([dx, fan_plate_y - 1, fan_axis_z + dz])
                    rotate([-90,0,0])
                        cylinder(d=fan_screw_pilot, h=fan_plate_t + fan_boss_h + 2, $fn=16);
    }
}

module cradle_rails() {
    for (seg = retain_segs) {
        // the rear rail, square: its underside bears on the rear arm
        translate([0,0,arm_a_inner + retain_clear])
            rotate([0,0,seg[0]])
                rotate_extrude(angle=seg[1])
                    translate([outer_dia/2, 0])
                        square([retain_h, retain_w]);
        // the front rail, its underside sloped to a lip (retain_lip). The
        // profile starts 0.3mm inside the wall so it overlaps it.
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

// Whiskers that are also the speaker grille. Since the bracket became a
// hollow sleeve (2026-10-23) the dots need cross only the wall; they start
// inside the sleeve just past the screw pads, as the retro grille's holes do.
module whisker_grille(angle) {
    r_mount = outer_dia/2 - wall - speaker_bracket_depth;
    z0 = (shell_depth - speaker_d)/2;
    zc = z0 + speaker_d/2;
    rotate([0,0,angle])
        for (r = [0:whisker_rows-1]) {
            dz = (r - (whisker_rows-1)/2) * whisker_dz;
            for (i = [0:whisker_per_row-1]) {
                dy = (i - (whisker_per_row-1)/2) * whisker_dx;
                droop = -abs(i - (whisker_per_row-1)/2) * whisker_droop;
                translate([r_mount - speaker_boss_h + speaker_boss_len + 0.1, dy, zc + dz + droop])
                    rotate([0,90,0])
                        cylinder(d=whisker_dot_dia,
                                 h=speaker_bracket_depth + speaker_boss_h - speaker_boss_len - 0.1 + wall + 3, $fn=12);
            }
        }
}

// ============================================================
// FRONT TRIM — the face
// ============================================================
module nose() {
    // A rounded triangle standing proud of the bezel at the chin,
    // entirely inside the rim band.
    translate([0, -screw_r, front_trim_h])
        linear_extrude(height=nose_proud, scale=0.72)
            hull() {
                translate([-nose_w/2 + nose_r,  nose_h/2 - nose_r]) circle(r=nose_r);
                translate([ nose_w/2 - nose_r,  nose_h/2 - nose_r]) circle(r=nose_r);
                translate([0, -nose_h/2 + nose_r]) circle(r=nose_r);
            }
}

// Short arcs either side of the nose, engraved into the bezel face.
//
// Each groove sweeps AWAY from the nose, so the two sides mirror properly.
// rotate_extrude always sweeps counter-clockwise from where it starts, so
// the clockwise side has to start a full arc further round and sweep back
// toward its offset -- without that the two sides are not mirror images,
// which is subtle enough on a render to miss and obvious on the part.
module whisker_grooves() {
    for (s = [-1, 1])
        for (i = [0 : len(whisker_offsets) - 1]) {
            off   = whisker_offsets[i];
            start = (s > 0) ? nose_angle + off
                            : nose_angle - off - whisker_arc;
            rotate([0, 0, start])
                translate([0, 0, front_trim_h - whisker_groove_d])
                    rotate_extrude(angle = whisker_arc)
                        translate([screw_r - 3 + i*2.5, 0])
                            square([whisker_groove_w, whisker_groove_d + 1]);
        }
}

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
            nose();
        }
        translate([0,0,-rabbet_depth-1]) cylinder(d=retention_opening, h=total_h+2);
        // Seven screws, not eight. The nose stands on the screw ring at
        // nose_angle and caps that hole with 2.6mm of solid, so the screw
        // could never be fitted -- and a hole that cannot take a screw is
        // worse than no hole, because it reads as a moulding defect under
        // the nose. The eighth is not cut at all. The shell keeps all eight
        // posts: an unused boss is invisible and keeps that part identical
        // to the retro build it was copied from.
        for (i = [0:n_screws-1]) {
            a = i * 360/n_screws;
            if (ang_gap(a, nose_angle) > 1)
                translate([screw_r*cos(a), screw_r*sin(a), -rabbet_depth-1])
                    cylinder(d=screw_clear_dia, h=total_h+2);
        }
        whisker_grooves();
    }
}

// ============================================================
// RETAINER — unchanged from the retro build (it is never seen)
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
// SHELL — the head
// ============================================================
// Eight insert posts standing inside the case at the back, mirroring the
// front's. They straddle the bore wall, so each merges into it rather than
// standing free.
// Solid band around the back rim, deep enough to cover the posts. Nothing
// may be cut out of this.
module back_collar() {
    difference() {
        cylinder(d=outer_dia, h=back_post_h + 2);
        translate([0,0,-1]) cylinder(d=outer_dia - 2*wall, h=back_post_h + 4);
    }
}

module back_posts() {
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), 0])
            cylinder(d=post_od, h=back_post_h);
    }
}

// Drilled in shell()'s difference stage, NOT inside back_posts(). The
// speaker brackets reach the wall at 0 and 180 degrees, exactly where two of
// these posts are, so a hole subtracted inside the post module gets unioned
// shut again by the bracket landing on it. Subtracting after everything is
// unioned is the only order that leaves eight open holes.
module back_post_holes() {
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), -0.01])
            cylinder(d=insert_hole_dia, h=back_insert_d);
    }
}

// ============================================================
// BACK PLATE — the electronics tray, screwed on like the faceplate,
// carrying the antenna mount on its outer face
// ============================================================

// Where the socket mouth sits, and which way it looks.
//
// The arm reaches STRAIGHT BACK from the plate, and only then does a barrel
// rise from its end along the antenna's own axis. That two-stage shape is
// forced: a barrel coaxial with the antenna and rooted on the plate would
// have to climb toward the head the whole way and would run into it, which
// is why the first attempt hulled a pad on the plate to a disc at the mouth
// instead -- and that produced a cone with the socket bored into its flank,
// opening sideways-and-down rather than up. A stub plus a barrel gives a
// real cylindrical socket with a flat face square to the antenna.
//
// rotate([-90,0,0]) lays a +Z cylinder along +Y; rotate([stand_angle,0,0])
// then tilts it back by exactly what the cradle tilts the case forward, so
// the two cancel and the antenna stands vertical on the desk.
function ant_barrel_base() = [0, ant_mount_y, -back_plate_t - ant_stub_len];

module ant_axis_frame() {
    translate(ant_barrel_base())
        rotate([stand_angle, 0, 0])
            rotate([-90, 0, 0])
                children();
}

// Bolt positions, shared by the mount's flange and the plate it lands on so
// the two cannot drift apart.
module ant_bolt_holes(h, z0) {
    for (i = [0 : n_ant_bolts - 1]) {
        // +30, not +90. At +90 one bolt points straight up the plate, putting
        // its insert boss at y=103 with an outer edge at 106.5 -- into the
        // locating lip, whose inner face is at 106.3. Clocking the circle by
        // 30 degrees puts two bolts at y=95.5 and one at y=73, all clear.
        a = i * 360/n_ant_bolts + 30;
        translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), z0])
            cylinder(d=ant_bolt_d, h=h);
    }
}

// The cable drops out of the socket and runs straight forward through the
// stub, the flange and the plate into the case.
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

// ---- the bolt-on part itself ----
module antenna_mount() {
    difference() {
        union() {
            // flange against the plate's outer face
            translate([0, ant_mount_y, -back_plate_t - ant_flange_t])
                cylinder(d=ant_flange_d, h=ant_flange_t);
            // arm reaching back
            translate([0, ant_mount_y, -back_plate_t - ant_stub_len])
                cylinder(d=ant_stub_dia, h=ant_stub_len);
            // socket barrel, rooted 6mm inside the arm so the joint is solid
            ant_axis_frame() translate([0,0,-6])
                cylinder(d=ant_boss_dia, h=ant_barrel_len + 6);
        }
        // the socket the antenna's base sits in, square to its axis, with a
        // chamfered mouth so the base can be tipped in and levered under the
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
            // the space behind it. Deliberately reaches DOWN past -6 so it
            // meets the cable bore's sweep rather than relying on the two
            // happening to touch: an unconnected cavity looks identical in
            // preview and is a solid wall in the print. It starts 1mm below
            // the boss (2026-10-29), so it cuts clean through the boss's
            // end. It started on that end, the two faces in one plane, and
            // the cut left a sheet of no thickness over half the opening,
            // whose edges a slicer reports as non-manifold.
            translate([0, 0, ant_sma_boss_h - ant_sma_panel_t - ant_sma_cavity_d - 1])
                cylinder(d=ant_sma_cavity, h=ant_sma_cavity_d + 1);
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


// Eight arcs at bore diameter, one per gap between the insert posts, with a
// lead-in chamfer on the outer top edge so the plate finds its own centre
// as it goes on rather than catching square.

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
        // the second: the window's rectangle, its ends square, and each end
        // 0.01mm past the window's (2026-10-29). Drawn the window's length,
        // one end touched the tip of the window's round end along a line,
        // and the plate's mesh had edges there that a slicer reports as
        // non-manifold. At the other end the circle has no corner on the
        // axis, so that end already stood 0.01 clear.
        translate([0, 0, fl + usbc_bridge_layer - 0.01])
            linear_extrude(height = usbc_bridge_layer + 0.01)
                square([usbc_cut_w + 0.02, usbc_cut_h], center = true);
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


// Bosses on the INNER face at the antenna bolt circle, each taking an M3
// heat-set insert.

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

// The matching bores. Two diameters on purpose: the insert pocket stops on a
// shoulder 1mm above the plate rather than running out through it, so the
// insert cannot be pressed too deep and the bolt still passes freely from
// the outside.
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
            // No Pi posts: the four 58x49 standoffs went unused for a year
            // (the Pi mounts on the display) and were removed 2026-10-07.
            // pi_posts() is left defined, as the retro case does.
            back_lip();
        }
        for (i = [0:n_screws-1]) {
            a = i * 360/n_screws;
            translate([screw_r*cos(a), screw_r*sin(a), -back_plate_t-1])
                cylinder(d=screw_clear_dia, h=back_plate_t+2);
        }
        // One pass-through, for the trigger board's socket (2026-10-29).
        usbc_cutout();
        // and the charger it needs, engraved above it (2026-10-29)
        translate([0, 0, -0.01]) usbc_label_solid(usbc_label_depth + 0.01);
        // Kept as plain vents. There is no fan mount on the plate any
        // more -- the fan goes on the Pi -- but the openings still help.
        translate([0,0,-back_plate_t]) intake_grille();
        translate([0,0,-back_plate_t]) fan_grille();
        // the antenna mount screws into inserts here, and its cable passes through
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

// Cut after the whole shell is unioned, so nothing landing in a post (a
// speaker bracket at 0 and 180) can fill its hole.
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
            difference() {
                union() {
                    cylinder(d=outer_dia, h=shell_depth);
                    ears_solid();
                }
                // Bored straight through: the back is a separate plate now.
                translate([0,0,-1]) cylinder(d=outer_dia - 2*wall, h=shell_depth + 2);
                // The ear cavities open into the case, and at 45 and 135
                // degrees they were eating the wall exactly where two back
                // posts attach -- leaving those two as loose islands in the
                // mesh, unprintable and unnoticed until the shell was
                // checked for connected components. Protect a collar around
                // the back rim so every post has wall to hold on to.
                difference() { ears_hollow(); back_collar(); }
            }
            back_posts();
            back_key();
            cradle_rails();
            for (a = speaker_angles) speaker_bracket(a);
        }
        for (a = speaker_angles) whisker_grille(a);
        inner_ear_recess();
        back_post_holes();
    }

    // Continuous shelf the retainer seats on, and the face front_trim's
    // rabbeted band lands against. Relieved on the same bottom arc as
    // the retainer for the driver board's cabling.
    difference() {
        // The shelf runs 0.01mm into the wall (2026-10-29). It stopped at
        // the bore, so the two shared the bore's face, and along a few
        // strips of it the union left that face in place: a sheet of the
        // wall's and a sheet of the shelf's with nothing between them,
        // edges a slicer reports as non-manifold and as reversed faces.
        // No more than 0.01: the shelf goes on after the wall's openings
        // are cut, so whatever of it lies in the wall would fill an opening
        // later cut at its height.
        translate([0,0,shell_depth - lip_height])
            difference() {
                cylinder(d=outer_dia - 2*wall + 0.02, h=shelf_h);
                cylinder(d=retention_opening, h=shelf_h+0.02);
            }
        rotate([0,0, relief_center_deg - relief_arc_deg/2])
            rotate_extrude(angle = relief_arc_deg)
                translate([retention_opening/2 - 1, shell_depth - lip_height - 1])
                    square([outer_dia/2 - retention_opening/2 + 2, shelf_h + 2]);
    }
    // Its underside slopes from r 103 to the wall, as the retro's does
    // (2026-10-29), except where an ear's hollow opens into the head: the
    // wall below the shelf is gone there, so the slope would start in
    // mid-air. See shelf_slope_r0. Since the hollows' tops are tented, none
    // comes up as far as the slope; this stays so that a taller one can't
    // leave it hanging.
    difference() { shelf_slope(); ears_hollow(); }

    // 8 front insert posts, below the shelf's top face; holes cut in shell()
    front_posts();

}

// ============================================================
// STAND — a sitting cat
// ============================================================
module plinth() {
    hull()
        for (sx = [-1,1]) for (sy = [-1,1])
            translate([sx*(base_w/2 - base_corner_r), sy*(base_d/2 - base_corner_r), 0])
                cylinder(r=base_corner_r, h=base_h);
}

// One toe lobe: an egg pointing forward, sitting low so its crown is the
// highest thing at the front of the paw.
// y_front is the TOE TIP line, not the pad's front. The first version put
// the toes at y_front + 0.55*toe_dia while the pad's front sphere reached
// 6.7mm further forward still, so every toe sat entirely inside the pad
// hull and contributed nothing -- the paws rendered as plain teardrops.
// The toes now lead, and the pad stops behind them.
function toe_a(i) = (i - (n_toes - 1) / 2) * toe_splay;
// The toe's centre is its half-height up, 0.85 of its radius (toe() squashes
// it so), so its underside is on the bed, level with the pads' flat bottoms
// (2026-10-29). At 0.46 it began 0.47mm up in mid-air.
function toe_pos(i, y_front) = [
    sin(toe_a(i)) * paw_w * 0.40,
    y_front + toe_dia * 0.62 + (1 - cos(toe_a(i))) * 6,   // outer toes sit back
    toe_dia * 0.425
];
// `shrink` insets the toe slightly. It exists for the colour split: see
// colour_overlap below.
module toe(i, y_front, shrink = 0) {
    translate(toe_pos(i, y_front))
        rotate([0, 0, -toe_a(i)])
            scale([1, 1.35, 0.85])
                sphere(d = max(toe_dia - shrink, 0.2));
}

// The pad without its toes. paw() below is still the whole foot, because the
// fit checks care about the foot as an object; the split exists so the toes
// can be printed in a different filament from the pad they sit in.
module paw_pad(x, shrink = 0) {
    y_back  = -base_d/2 + 10;                 // buried in the plinth
    y_front = -base_d/2 - paw_reach;
    translate([x, 0, 0]) {
        // the leg/pad, domed and tapering: narrow and tall at the ankle,
        // wide and low at the toes
        hull() {
            translate([0, y_back, paw_h * 0.46])
                scale([1, 1, 0.95]) sphere(d = paw_w * paw_ankle_w - shrink);
            translate([0, (y_back + y_front) / 2, paw_h * 0.40])
                scale([1.04, 1, 0.80]) sphere(d = paw_w * 0.84 - shrink);
            // pad front, held BACK so the toes lead it
            translate([0, y_front + toe_dia * 1.95, paw_h * 0.33])
                scale([1.10, 1, 0.68]) sphere(d = paw_w * 0.92 - shrink);
        }
    }
}

module paw_toes(x, shrink = 0) {
    y_front = -base_d/2 - paw_reach;
    translate([x, 0, 0])
        for (i = [0 : n_toes - 1]) toe(i, y_front, shrink);
}

// One claw off the front of toe i, following that toe's splay so the fan
// carries through, and drooping toward the desk.
//
// The base sits INSIDE the toe (at 0.5*toe_dia, against a toe half-length of
// 0.675*toe_dia) rather than on its surface. Two reasons: a claw butted
// against the toe would share a surface with it, which is the coincidence
// that stipples the slicer preview -- see the colour-split notes below -- and
// a spike joined only at a tangent point is a weak spot in the print.
// The base is offset in GLOBAL -y and only then is the claw's direction
// rotated to the toe's splay. Rotating first and offsetting along the toe's
// OWN axis is the obvious way round and it is wrong: moving forward along a
// splayed toe also moves inward, so the four bases converge from 5.9mm apart
// at the toe centres to 3.56mm at the claw bases -- closer together than a
// 3.6mm base is wide. They then merge in pairs, and eight claws export as
// four lumps. Caught by counting connected components, not by any volume or
// seam check, all of which passed.
module claw(i, y_front, shrink = 0) {
    translate(toe_pos(i, y_front))
        translate([0, -toe_dia * 0.50, claw_base_dz])
            rotate([0, 0, -toe_a(i)])
                hull() {
                    sphere(d = max(claw_base_d - shrink, 0.2));
                    translate([0, -claw_len, claw_tip_dz - claw_base_dz])
                        sphere(d = max(claw_tip_d - shrink, 0.2));
                }
}

module paw_claws(x, shrink = 0) {
    y_front = -base_d/2 - paw_reach;
    translate([x, 0, 0])
        for (i = [0 : n_toes - 1]) claw(i, y_front, shrink);
}

module paw(x) { paw_pad(x); paw_toes(x); paw_claws(x); }

// Clefts between the toes. Cut at stand level rather than unioned away
// here, because a difference inside a module that is later intersected with
// the desk plane would be undone by the union around it.
module paw_clefts(x) {
    y_front = -base_d/2 - paw_reach;
    // one cleft per gap, placed midway between adjacent toe centres so it
    // tracks the fan however toe_splay is tuned
    translate([x, 0, 0])
        for (i = [0 : n_toes - 2]) {
            pa = toe_pos(i, y_front);
            pb = toe_pos(i + 1, y_front);
            mid = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, (pa[2] + pb[2]) / 2];
            ang = (toe_a(i) + toe_a(i + 1)) / 2;
            translate([mid[0], mid[1], mid[2] + cleft_d * 0.5])
                rotate([0, 0, -ang])
                    hull() {
                        translate([0, -toe_dia * 0.75, 0]) sphere(d = cleft_w);
                        translate([0,  toe_dia * 0.85, cleft_d * 0.5]) sphere(d = cleft_w * 1.6);
                    }
        }
}

// Catmull-Rom through the control points. Hulling straight between them
// left a visible kink at every joint -- fine for a bracket, wrong for a
// tail, where the whole point is that it flows. Interpolating also carries
// the diameter, so the taper is smooth rather than stepped.
function cr(p0, p1, p2, p3, t) =
    0.5 * ((2 * p1)
         + (-p0 + p2) * t
         + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
         + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);

// Interpolated points per control segment. The tail is hulls between
// consecutive spheres, so every sphere leaves a crease running around the
// tube -- and once the circumference was smoothed those creases stopped
// being masked by the general faceting and read as rings. More points means
// a smaller direction change at each, so the creases shallow out: 6 put a
// joint every 5.6mm, 14 puts one every 2.4mm, for about a megabyte.
tail_smooth_steps = 14;

function tail_curve() = concat(
    [ for (i = [0 : len(tail_pts) - 2])
        for (j = [0 : tail_smooth_steps - 1])
            cr(tail_pts[max(i - 1, 0)],
               tail_pts[i],
               tail_pts[i + 1],
               tail_pts[min(i + 2, len(tail_pts) - 1)],
               j / tail_smooth_steps) ],
    [ tail_pts[len(tail_pts) - 1] ]);

// One run of the tail, from control point i0 to i1 along the interpolated
// curve. Splitting by index rather than by a cutting plane keeps the join
// square to the tail's own axis: a plane cut would slice it at whatever
// angle the tail happened to be travelling, which on a curve that is still
// turning at the tip reads as a chipped end rather than a marking.
module tail_run(i0, i1, shrink = 0) {
    pts = tail_curve();
    for (i = [i0 : i1 - 1])
        hull() {
            translate([pts[i][0],   pts[i][1],   pts[i][2]])   sphere(d = max(pts[i][3]   - shrink, 0.5));
            translate([pts[i+1][0], pts[i+1][1], pts[i+1][2]]) sphere(d = max(pts[i+1][3] - shrink, 0.5));
        }
}

function tail_split_i() = len(tail_curve()) - 1
                        - max(1, round((len(tail_curve()) - 1) * tail_tip_frac));

module tail(shrink = 0)     { tail_run(0, len(tail_curve()) - 1, shrink); }
module tail_tip(shrink = 0) { tail_run(tail_split_i(), len(tail_curve()) - 1, shrink); }
// The two runs share the sphere at the split index, so the black part has
// the tip cut out of it rather than merely stopping short. Overlapping
// bodies are a coin toss in a slicer -- whichever is assigned last wins,
// and the seam moves depending on load order.
module tail_body() { difference() { tail_run(0, tail_split_i() + 1); tail_tip(colour_overlap); } }

module cradle_arm(depth_offset) {
    arm_t = (cradle_od - cradle_id) / 2;
    r_mid = (cradle_id + cradle_od) / 4;
    translate([0, 0, depth_offset]) {
        rotate([0,0, 270 - cradle_arc/2])
            rotate_extrude(angle = cradle_arc)
                translate([cradle_id/2, 0]) square([arm_t, arm_w]);
        for (a = [270 - cradle_arc/2, 270 + cradle_arc/2])
            translate([r_mid*cos(a), r_mid*sin(a), 0]) cylinder(d=arm_t, h=arm_w);
    }
}

// The charger cable's clip, cut from the plinth beside the tail's root
// (2026-10-29): see stand_cable_d. The retro case's stand_cable_clip() at
// cable_clip_x, less its notch through the ridges, which this plinth hasn't
// got. Along the top a round groove a little under the cable, with a mouth
// narrower than it; then a turn down over the back edge, its mouth on the
// outside of the turn; then a channel down the back face as wide as the
// groove but open to the back, so the cable leaves it wherever it bends away
// to the desk. None of it needs support: under the mouths' lips the groove's
// curve is 60 degrees or more from flat, and the channel down the back face
// is upright.
module root_cable_clip() {
    r  = (stand_cable_d - stand_clip_grip) / 2;
    zc = base_h - stand_clip_sink;      // the top groove's axis
    yc = base_d/2 - stand_clip_sink;    // the back channel's axis
    R  = stand_clip_bend;
    y1 = yc - R;                        // where the groove starts to turn down
    translate([cable_clip_x, cable_clip_y0, zc]) {
        rotate([-90, 0, 0]) cylinder(r = r, h = y1 - cable_clip_y0 + 0.01);
        sphere(r = r);
    }
    hull() for (y = [cable_clip_y0, y1])
        translate([cable_clip_x, y, zc]) cylinder(d = stand_clip_mouth, h = stand_clip_sink + 1);
    translate([cable_clip_x, y1, zc - R]) rotate([0, 90, 0]) rotate([0, 0, 90])
        rotate_extrude(angle = 90) {
            translate([R, 0]) circle(r = r);
            translate([R, -stand_clip_mouth/2]) square([2*stand_clip_sink + 1, stand_clip_mouth]);
        }
    translate([cable_clip_x, yc, -1]) cylinder(r = r, h = zc - R + 1 + 0.01);
    translate([cable_clip_x - r, yc, -1]) cube([2*r, base_d/2 - yc + 0.01, zc - R + 1 + 0.01]);
}

module stand() {
    difference() {
        stand_solid();
        paw_clefts( paw_x);
        paw_clefts(-paw_x);
        root_cable_clip();   // the charger cable's clip (2026-10-29)
    }
}

// Everything that is not a paw or a tail: the plinth, the cradle arms and
// the keel. Split out so the black body can be built by subtracting the
// coloured parts from it rather than by rebuilding it from scratch, which
// would leave the two definitions free to drift apart.
module stand_frame() {
    // rotate([90 - stand_angle,0,0]) lays the ring axis horizontal and
    // tips it back so the head leans at stand_angle. Rotating by only
    // stand_angle leaves the rings nearly flat, floating above the
    // plinth and never touching it.
    arm_lift = base_h + cradle_od/2 - 3;
    union() {
        plinth();
        translate([0, 0, arm_lift])
                rotate([90 - stand_angle, 0, 0]) {
                    cradle_arm(-(arm_gap/2 + arm_w));
                    cradle_arm(arm_gap/2);
                    // keel tying both arms down into the plinth; starts at
                    // the bowl's own inner radius so it can never intrude
                    // into the space the head occupies
                    translate([0, 0, -(arm_gap/2 + arm_w)])
                        rotate([0, 0, 270 - keel_arc/2])
                            rotate_extrude(angle = keel_arc)
                                translate([cradle_id/2, 0])
                                    square([keel_reach, arm_gap + 2*arm_w]);
            }
    }
}

// Standing on a desk: nothing below z=0 survives.
module desk_clip() { translate([-400, -400, 0]) cube([800, 800, 400]); }

module stand_solid() {
    intersection() {
        desk_clip();
        union() {
            stand_frame();
            paw( paw_x);
            paw(-paw_x);
            tail();
        }
    }
}

// ---- Colour separation ---------------------------------------------
// Five bodies in one coordinate frame. Load them together in the slicer and
// assign a filament each; on a single-extruder printer they are also
// printable separately and glued, since every split is along a real seam in
// the shape rather than an arbitrary plane.
//
// The parts deliberately INTERFERE by colour_overlap along every boundary,
// and getting this wrong is what the first version got wrong. Cutting each
// part with the exact shape of its neighbour is the tidy-looking answer and
// it is the broken one: it leaves the two bodies sharing a surface at
// identical coordinates. Mathematically that is a perfect partition -- zero
// volume in common, which is exactly what the volume checks reported -- but
// a renderer cannot decide which of two coincident faces is in front, so
// the slicer preview stipples the seam with the other colour and a white
// paw comes out speckled black. The buried half of the paw, sunk into the
// plinth, is a large coincident area and stipples worst of all.
//
// So each part is cut with a slightly INSET copy of whatever takes
// precedence over it, leaving a thin shell of shared material instead of a
// shared surface. Nothing is coplanar, nothing z-fights, and the colour
// boundary moves by at most colour_overlap/2 -- far below a nozzle width,
// so which body a slicer awards the shell to cannot be seen in the print.
//
// Precedence, outermost first: tail, then toes, then pads, then the body.
// Where the tail lies across the paw the TAIL wins, because it is the thing
// on top in the real shape.
module part_stand_body() {                      // BLACK
    difference() {
        intersection() { desk_clip(); stand_frame(); }
        paw_pad(  paw_x, colour_overlap); paw_pad( -paw_x, colour_overlap);
        paw_toes( paw_x, colour_overlap); paw_toes(-paw_x, colour_overlap);
        tail(colour_overlap);
        root_cable_clip();   // only the plinth: it clears the tail's root
    }
}

module part_stand_paws() {                      // WHITE
    difference() {
        intersection() { desk_clip(); union() { paw_pad(paw_x); paw_pad(-paw_x); } }
        paw_toes( paw_x, colour_overlap); paw_toes(-paw_x, colour_overlap);
        tail(colour_overlap);
        paw_clefts( paw_x); paw_clefts(-paw_x);
    }
}

module part_stand_toes() {                      // BLACK
    difference() {
        intersection() { desk_clip(); union() { paw_toes(paw_x); paw_toes(-paw_x); } }
        tail(colour_overlap);
        paw_clefts( paw_x); paw_clefts(-paw_x);
        paw_claws( paw_x, colour_overlap); paw_claws(-paw_x, colour_overlap);
    }
}

module part_stand_claws() {                     // WHITE (or whatever you like)
    difference() {
        intersection() { desk_clip(); union() { paw_claws(paw_x); paw_claws(-paw_x); } }
        paw_clefts( paw_x); paw_clefts(-paw_x);
    }
}

// The tail seam needs the opposite treatment to the others, and it is worth
// saying why. Everywhere else, two parts meet across a boundary and an inset
// cut leaves them overlapping with no shared surface. Here they are two runs
// of the SAME tapering tube, so wherever they overlap they carry the same
// outer skin -- and an overlap of identical skin is exactly the coincidence
// being avoided. Insetting the cut just moved the stipple from the joint to
// a band beside it.
//
// So the tip is grown instead of the body being shrunk: over the shared
// stretch the white tip is colour_overlap/2 proud of the black tail it
// continues, which is 0.15mm on a tail 10mm thick. Nothing coincides, and
// the step is a fifth of a nozzle width.
module part_stand_tail() {                      // BLACK
    intersection() { desk_clip(); tail_body(); }
}

module part_stand_tail_tip() {                  // WHITE
    intersection() { desk_clip(); tail_tip(-colour_overlap); }
}

module stand_colour_parts() {
    part_stand_body();
    part_stand_paws();
    part_stand_toes();
    part_stand_claws();
    part_stand_tail();
    part_stand_tail_tip();
}

// ============================================================
if (part == "front_trim") front_trim();
else if (part == "retainer") retainer_print();   // glass face down, as it prints
else if (part == "shell") shell();
else if (part == "stand") stand();
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
else if (part == "stand_body")     part_stand_body();
else if (part == "stand_paws")     part_stand_paws();
else if (part == "stand_toes")     part_stand_toes();
else if (part == "stand_claws")    part_stand_claws();
else if (part == "stand_tail")     part_stand_tail();
else if (part == "stand_tail_tip") part_stand_tail_tip();
else if (part == "test_ear") {
    // one ear plus the head around its base — a fit/appearance test
    // that prints in minutes instead of hours
    intersection() {
        shell();
        rotate([0,0,-ear_angle]) translate([-55, 70, -1]) cube([110, 110, shell_depth + 2]);
    }
}
else if (part == "test_clip") {
    // The stand's cable clip in a 20 x 37 mm piece of the plinth's back, cut
    // off at the plinth's top, to try the charger's cable in before printing
    // the stand (2026-10-29).
    intersection() {
        stand();
        translate([cable_clip_x - 10, cable_clip_y0 - 6, -1])
            cube([20, base_d/2 - cable_clip_y0 + 6 + 1, base_h + 1]);
    }
}
else if (part == "exploded") {
    color("Pink")       translate([0,0,shell_depth + 40]) front_trim();
    color("LightBlue",0.4) translate([0,0,shell_depth + 25]) cylinder(d=panel_diameter, h=panel_glass_depth);
    color("Gray")       translate([0,0,shell_depth + 10]) retainer();
    color("Gainsboro")  shell();
    color("DimGray")    translate([0,0,-140]) stand();
}
else {
    // the head with its face on: placed by front_stack_placed() since
    // 2026-10-29, which seats the retainer on the shelf (it was drawn at
    // shell_depth - lip_height, inside the shelf) and shows the glass
    color("Gainsboro")  shell();
    color("Gray")       front_stack_placed("retainer");
    color("LightBlue",0.4) front_stack_placed("glass");
    color("Pink")       front_stack_placed("trim");
}
