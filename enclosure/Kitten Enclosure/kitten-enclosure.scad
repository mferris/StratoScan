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
$fn = 96;

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
whisker_groove_w = 1.6;
whisker_groove_d = 0.9;

// STAND — a sitting cat. Plinth is rounded rather than a slab.
base_w = outer_dia*0.86; base_d = 150; base_h = 16;
base_corner_r = 18;
paw_x      = 42;    // paws either side of centre
paw_w      = 34;
paw_reach  = 26;    // how far they stretch forward of the plinth
paw_h      = 13;
toe_dia    = 9;
// The tail curls flat around the right side and forward. It stays
// below z=16 deliberately: the cradled head's underside comes down to
// about z=27, so a tail that swept upward would collide with it.
// The last three points stay outboard of x=62: the right paw occupies
// x 25..59, and an earlier curl that swept in to x=36 simply merged into
// it, reading as one lump rather than a tail beside a paw.
tail_pts = [
    [ 66,  52,  7, 17],
    [ 92,  40,  7, 16],
    [104,  12,  7, 15],
    [ 99, -22,  7, 14],
    [ 88, -48,  6, 12],
    [ 78, -66,  6, 10],
    [ 68, -78,  5,  8],
];

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
                rotate_extrude(angle=seg[1], $fn=96)
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

module whisker_grooves() {
    // Short arcs either side of the nose, engraved into the bezel face.
    for (s = [-1, 1])
        for (i = [0:2])
            rotate([0, 0, s * (18 + i*11)])
                translate([0, 0, front_trim_h - whisker_groove_d])
                    rotate_extrude(angle = 9, $fn=120)
                        translate([screw_r - 3 + i*2.5, 0])
                            square([whisker_groove_w, whisker_groove_d + 1]);
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
        for (i = [0:n_screws-1]) {
            a = i * 360/n_screws;
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
module shell() {
    difference() {
        union() {
            difference() {
                union() {
                    cylinder(d=outer_dia, h=shell_depth);
                    ears_solid();
                }
                translate([0,0,wall]) cylinder(d=outer_dia - 2*wall, h=shell_depth);
                ears_hollow();
            }
            cradle_rails();
            fan_mount();
            for (a = speaker_angles) speaker_bracket(a);
        }
        translate([back_holes_x, back_holes_y1, -1]) cylinder(d=usbc_hole_dia, h=wall+2);
        translate([back_holes_x, back_holes_y2, -1]) cylinder(d=antenna_hole_dia, h=wall+2);
        intake_grille();
        fan_grille();
        exhaust_slots();
        for (a = speaker_angles) whisker_grille(a);
        inner_ear_recess();
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

    // standoffs for the panel's rear PCB
    for (x = [-mount_hole_x/2, mount_hole_x/2])
        for (y = [-mount_hole_y/2, mount_hole_y/2])
            translate([x, y, 0])
                difference() {
                    cylinder(d=7, h=8);
                    cylinder(d=2.5, h=9);
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

module paw(x) {
    y_front = -base_d/2 - paw_reach;
    translate([x, 0, 0]) {
        hull() {
            translate([0, -base_d/2 + 8, 0]) cylinder(d=paw_w, h=paw_h);
            translate([0, y_front + paw_w/2, 0]) cylinder(d=paw_w, h=paw_h);
        }
        // three toe domes, sunk so only their crowns show
        for (t = [-1, 0, 1])
            translate([t * paw_w/3.4, y_front + paw_w/2 + 2, paw_h - 2])
                sphere(d=toe_dia, $fn=32);
    }
}

module tail() {
    for (i = [0 : len(tail_pts) - 2])
        hull() {
            translate([tail_pts[i][0],   tail_pts[i][1],   tail_pts[i][2]])   sphere(d=tail_pts[i][3],   $fn=32);
            translate([tail_pts[i+1][0], tail_pts[i+1][1], tail_pts[i+1][2]]) sphere(d=tail_pts[i+1][3], $fn=32);
        }
}

module cradle_arm(depth_offset) {
    arm_t = (cradle_od - cradle_id) / 2;
    r_mid = (cradle_id + cradle_od) / 4;
    translate([0, 0, depth_offset]) {
        rotate([0,0, 270 - cradle_arc/2])
            rotate_extrude(angle = cradle_arc, $fn=96)
                translate([cradle_id/2, 0]) square([arm_t, arm_w]);
        for (a = [270 - cradle_arc/2, 270 + cradle_arc/2])
            translate([r_mid*cos(a), r_mid*sin(a), 0]) cylinder(d=arm_t, h=arm_w, $fn=48);
    }
}

module stand() {
    // rotate([90 - stand_angle,0,0]) lays the ring axis horizontal and
    // tips it back so the head leans at stand_angle. Rotating by only
    // stand_angle leaves the rings nearly flat, floating above the
    // plinth and never touching it.
    arm_lift = base_h + cradle_od/2 - 3;
    intersection() {
        translate([-400, -400, 0]) cube([800, 800, 400]);
        union() {
            plinth();
            paw( paw_x);
            paw(-paw_x);
            tail();
            translate([0, 0, arm_lift])
                rotate([90 - stand_angle, 0, 0]) {
                    cradle_arm(-(arm_gap/2 + arm_w));
                    cradle_arm(arm_gap/2);
                    // keel tying both arms down into the plinth; starts at
                    // the bowl's own inner radius so it can never intrude
                    // into the space the head occupies
                    translate([0, 0, -(arm_gap/2 + arm_w)])
                        rotate([0, 0, 270 - keel_arc/2])
                            rotate_extrude(angle = keel_arc, $fn=96)
                                translate([cradle_id/2, 0])
                                    square([keel_reach, arm_gap + 2*arm_w]);
                }
        }
    }
}

// ============================================================
if (part == "front_trim") front_trim();
else if (part == "retainer") retainer();
else if (part == "shell") shell();
else if (part == "stand") stand();
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
