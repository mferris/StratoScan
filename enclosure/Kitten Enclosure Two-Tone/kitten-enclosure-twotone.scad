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

part = "preview";  // front_trim | retainer | shell | stand | preview | exploded | test_ear
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
// gland that used to sit side by side here. The antenna no longer needs a
// bulkhead on the plate at all: its coax comes in through the antenna
// mount's own cable bore.
//
// Fitted against the real connector on 2026-09-29: it fits this window, and
// its mounting holes are 16.5mm apart, centre to centre. The listing
// publishes no cutout size, so these started as the usual values for that
// style of part; part="usbc_gauge" (this window plus four neighbours) is
// still the quick way to re-fit a different connector.
usbc_cut_w       = 11.0;   // window width  (across the connector body)
usbc_cut_h       = 6.5;    // window height (through the connector body)
usbc_cut_r       = 1.2;    // corner radius
usbc_screw_pitch = 16.5;   // centre-to-centre of the two mounting screws
usbc_screw_dia   = screw_clear_dia;   // M3 clearance (3.4), same as every other M3 hole
// 37 mm below where it was ([60, -14]): the owner's ask, 2026-10-10. At
// the old spot the power jumper bent hard against the Pi's USB ports; the
// bottom centre, tried first, did not suit either.
usbc_cut_pos     = [60, -51];
// The connector's body is a rectangular boss, 22.25 x 11 (measured
// 2026-10-10), mounted from inside against the plate; through a 3 mm plate
// its socket sat 3 mm below the outer face and a plug would not seat. A
// pocket in the OUTER face, the boss's size with a little clearance and
// usbc_recess_d deep, leaves a 1 mm web the two screws clamp through and
// puts the socket 1 mm below the pocket floor. The screw heads sit in the
// pocket; M3 x 6 still reach (2 mm further into the connector).
usbc_boss_w      = 22.25;
usbc_boss_h      = 11.0;
usbc_boss_clear  = 0.3;    // a side
usbc_recess_d    = 2.0;    // of back_plate_t: the web is what is left

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
// The tip stays clear of the desk plane on purpose -- a claw that reached
// z=0 would carry the stand's weight on four little points and rock.
claw_len     = 6.5;   // how far it stands off the toe
claw_base_d  = 3.6;   // where it leaves the toe
claw_tip_d   = 1.2;   // rounded rather than needle-sharp: printable, and safe
claw_base_dz = -1.8;  // relative to the toe centre
claw_tip_dz  = -4.4;  // tip drops this far: the droop

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
tail_pts = [
    [ 58,  58,  11, 29],   // root, buried in the plinth
    [ 87,  48,  11, 28],
    [102,  22,  11, 25],   // hugging the plinth edge rather than standing off it
    [106, -10,  11, 23],
    [102, -40,  11, 21],
    [ 93, -66,  12, 18],
    [ 82, -85,  16, 16],   // starts climbing as it reaches the right paw
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
module ears_hollow() {
    for (s = [-1, 1])
        rotate([0, 0, -s * ear_angle])
            translate([0,0,-1])
                linear_extrude(height = ear_hollow_top + 1)
                    offset(r = -wall) ear_profile_2d(s * ear_lean);
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
    for (seg = retain_segs)
        for (z = [arm_a_inner + retain_clear, arm_b_inner - retain_clear - retain_w])
            translate([0,0,z]) rotate([0,0,seg[0]])
                rotate_extrude(angle=seg[1])
                    translate([outer_dia/2, 0]) square([retain_h, retain_w]);
}

module speaker_bracket(angle) {
    r_wall  = outer_dia/2 - wall;
    r_mount = r_wall - speaker_bracket_depth;
    z0 = (shell_depth - speaker_d)/2;
    rotate([0,0,angle]) {
        // Clipped to the outer cylinder: a flat slab across a curved
        // wall otherwise punches through it at the corners.
        intersection() {
            hull() {
                translate([r_wall - 0.2, -speaker_w/2, z0]) cube([0.2, speaker_w, speaker_d]);
                translate([r_mount, -speaker_w/2, z0])     cube([0.2, speaker_w, speaker_d]);
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

// Whiskers that are also the speaker grille. The cut has to clear BOTH
// solids in the sound path — the wall AND the bracket slab behind it —
// so it starts at r_mount, exactly as the retro grille does. A cut
// sized to `wall` alone looks open from outside and is sealed inside.
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
                translate([r_mount, dy, zc + dz + droop])
                    rotate([0,90,0])
                        cylinder(d=whisker_dot_dia,
                                 h=speaker_bracket_depth + wall + 3, $fn=12);
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

// The single pass-through: a rounded window for the connector body plus its
// two mounting screws. Cut through the plate from below.
module usbc_cutout() {
    translate([usbc_cut_pos[0], usbc_cut_pos[1], -back_plate_t - 1]) {
        linear_extrude(height = back_plate_t + 2)
            offset(r = usbc_cut_r) offset(delta = -usbc_cut_r)
                square([usbc_cut_w, usbc_cut_h], center = true);
        for (sx = [-1, 1])
            translate([sx * usbc_screw_pitch/2, 0, 0])
                cylinder(d = usbc_screw_dia, h = back_plate_t + 2);
        // the pocket for the connector's boss, in the outer face (z = -back_plate_t)
        linear_extrude(height = usbc_recess_d + 1)
            offset(r = usbc_cut_r) offset(delta = -usbc_cut_r)
                square([usbc_boss_w + 2*usbc_boss_clear, usbc_boss_h + 2*usbc_boss_clear], center = true);
    }
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

// A 5-minute test coupon: the real cutout, flanked by four neighbours at
// +/-0.5 and +/-1.0mm on both dimensions. Fit the connector to it before
// printing a whole back plate, then set usbc_cut_w/h to the window that
// worked. Cutting one of these is minutes; a back plate is hours.
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
        usbc_cutout();
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
function toe_pos(i, y_front) = [
    sin(toe_a(i)) * paw_w * 0.40,
    y_front + toe_dia * 0.62 + (1 - cos(toe_a(i))) * 6,   // outer toes sit back
    toe_dia * 0.46
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

module stand() {
    difference() {
        stand_solid();
        paw_clefts( paw_x);
        paw_clefts(-paw_x);
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
else if (part == "retainer") retainer();
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
else if (part == "exploded") {
    color("Pink")       translate([0,0,shell_depth + 40]) front_trim();
    color("LightBlue",0.4) translate([0,0,shell_depth + 25]) cylinder(d=panel_diameter, h=panel_glass_depth);
    color("Gray")       translate([0,0,shell_depth + 10]) retainer();
    color("Gainsboro")  shell();
    color("DimGray")    translate([0,0,-140]) stand();
}
else {
    color("Gainsboro")  shell();
    color("Gray")       translate([0,0,shell_depth - lip_height]) retainer();
    color("Pink")       translate([0,0,shell_depth + rabbet_depth]) front_trim();
}
