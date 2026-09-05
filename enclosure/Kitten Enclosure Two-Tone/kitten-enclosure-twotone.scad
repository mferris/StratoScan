// ============================================================
// FlightWall — KITTEN enclosure
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

shell_depth = 56;           // front glass face to back of the tallest component
rim = 10;
outer_dia = panel_diameter + 2*rim;   // 223.34
wall = 3;

glass_overlap     = 4;
retention_opening = panel_diameter - 2*glass_overlap;
front_trim_h  = 4;
retainer_h    = 4;
lip_height    = 6;
shelf_h       = lip_height - retainer_h;
rabbet_depth  = glass_thickness;

screw_r = panel_diameter/2 + rim/2;
n_screws = 8;
screw_clear_dia = 3.4;
insert_hole_dia = 4.2;
post_od = 9;

relief_center_deg = 270;
relief_arc_deg    = 50;

// ---- Removable back plate --------------------------------------------
// The back was a fixed floor with the electronics standing on it, so the
// only way in was through the glass. It is now a separate screwed plate,
// and everything that stood on the floor went with it: the standoffs, the
// fan mount, the intake and fan grilles, and the two cable glands.
//
// The Pi itself is mounted to the LCD panel rather than to these standoffs,
// so taking the plate off exposes the back of the Pi and its cabling rather
// than removing it. The 58x49 standoffs are kept as an alternative mounting
// position; they cost nothing and removing them is a one-line change.
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
ant_flange_t   = 4;
ant_bolt_pcd   = 30;
ant_bolt_d     = 3.4;
n_ant_bolts    = 3;

ant_mount_y        = 88;   // up the plate, still well inside its rim
ant_mount_standoff = 26;   // how far the socket sits back from the plate
// 26 is not a guess. Swept against the antenna's own 33mm envelope: 12mm
// fouls the head's top rim by 876mm3, 18mm by 205mm3, and it comes clear at
// 24mm. 26 keeps a margin. The number is this large because a vertical
// antenna rising from a plate the same diameter as the head has to travel
// outward past a 111.7mm radius to clear it, gaining z the whole way -- the
// standoff is what buys the height to do that behind the head rather than
// through it.
ant_socket_dia     = 33;   // as the retro turret
ant_socket_depth   = 6;
ant_boss_dia       = 42;
ant_cable_dia      = 9;
back_post_h    = 9;    // insert post standing inside the case
back_insert_d  = 8;    // depth of the heat-set insert hole

// back-panel bulkheads
usbc_hole_dia    = 23;
antenna_hole_dia = 6.5;
back_holes_x  = 60;
back_holes_y1 = -20;
back_holes_y2 = 6;

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
fan_grille_dia = 26; fan_grille_pos = [0, 68];

// floor intake
intake_dia = 54; intake_hole = 3; intake_pitch = 6;

// side exhaust
exhaust_slot_w = 2.2; exhaust_slot_h = 12;
exhaust_z = shell_depth / 2;
n_exhaust = 24;
exhaust_skip_deg = 50;

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
    relief_w  = panel_diameter/2 - retention_opening/2 + 2;
    difference() {
        cylinder(d=outer_dia - 2*wall, h=retainer_h);
        translate([0,0,-1]) cylinder(d=retention_opening, h=retainer_h+2);
        screw_ring_holes(screw_clear_dia, retainer_h);
        rotate([0,0, relief_center_deg - relief_arc_deg/2])
            rotate_extrude(angle = relief_arc_deg)
                translate([relief_r0, -1]) square([relief_w, retainer_h+2]);
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
        a = i * 360/n_ant_bolts + 90;
        translate([ant_bolt_pcd/2*cos(a), ant_mount_y + ant_bolt_pcd/2*sin(a), z0])
            cylinder(d=ant_bolt_d, h=h);
    }
}

// The cable drops out of the socket and runs straight forward through the
// stub, the flange and the plate into the case.
module ant_cable_bore(z_top) {
    translate([0, ant_mount_y, -back_plate_t - ant_stub_len - 2])
        cylinder(d=ant_cable_dia, h=ant_stub_len + z_top + 2);
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
        // the socket the antenna's base drops into, square to its axis
        ant_axis_frame()
            translate([0, 0, ant_barrel_len - ant_socket_depth])
                cylinder(d=ant_socket_dia, h=ant_socket_depth + 1);
        ant_cable_bore(0);
        ant_bolt_holes(ant_flange_t + 2, -back_plate_t - ant_flange_t - 1);
        // nothing may stand proud of the plate's outer face
        translate([-300, -300, -back_plate_t]) cube([600, 600, 600]);
    }
}

module back_plate() {
    difference() {
        union() {
            translate([0,0,-back_plate_t])
                cylinder(d=outer_dia, h=back_plate_t);
            // everything that used to stand on the floor, shifted down so
            // what sat on the floor's top face now sits on the plate's
            for (x = [-mount_hole_x/2, mount_hole_x/2])
                for (y = [-mount_hole_y/2, mount_hole_y/2])
                    translate([x, y, 0])
                        difference() {
                            cylinder(d=7, h=8);
                            cylinder(d=2.5, h=9);
                        }
        }
        for (i = [0:n_screws-1]) {
            a = i * 360/n_screws;
            translate([screw_r*cos(a), screw_r*sin(a), -back_plate_t-1])
                cylinder(d=screw_clear_dia, h=back_plate_t+2);
        }
        translate([back_holes_x, back_holes_y1, -back_plate_t-1])
            cylinder(d=usbc_hole_dia, h=back_plate_t+2);
        translate([back_holes_x, back_holes_y2, -back_plate_t-1])
            cylinder(d=antenna_hole_dia, h=back_plate_t+2);
        // Kept as plain vents. There is no fan mount on the plate any
        // more -- the fan goes on the Pi -- but the openings still help.
        translate([0,0,-back_plate_t]) intake_grille();
        translate([0,0,-back_plate_t]) fan_grille();
        // the antenna mount bolts on here, and its cable passes through
        ant_bolt_holes(back_plate_t + 2, -back_plate_t - 1);
        translate([0, ant_mount_y, -back_plate_t - 1])
            cylinder(d=ant_cable_dia, h=back_plate_t + 2);
    }
}

module shell() {
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
            cradle_rails();
            for (a = speaker_angles) speaker_bracket(a);
        }
        exhaust_slots();
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

    // 8 insert posts, entirely below the shelf
    for (i = [0:n_screws-1]) {
        a = i * 360/n_screws;
        translate([screw_r*cos(a), screw_r*sin(a), shell_depth - lip_height])
            difference() {
                cylinder(d=post_od, h=shelf_h);
                translate([0,0,shelf_h-8]) cylinder(d=insert_hole_dia, h=9);
            }
    }

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

module paw(x) { paw_pad(x); paw_toes(x); }

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
else if (part == "stand_body")     part_stand_body();
else if (part == "stand_paws")     part_stand_paws();
else if (part == "stand_toes")     part_stand_toes();
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
