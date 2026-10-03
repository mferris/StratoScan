# Retro radar enclosure

The 3D-printable case for the retro build, as a single parametric
OpenSCAD source. Everything is driven from the measured values at the top of
[`retro-enclosure.scad`](retro-enclosure.scad) — change those and
the rest follows.

## Parts

| part | what it is |
|---|---|
| `shell` | the body: Pi, dongle, wiring, speakers |
| `front_trim` | bezel in front of the glass, rabbeted so it seats flush |
| `retainer` | ring behind the glass; the glass rests on its front face |
| `stand` | desk cradle — two ring-arc arms on a plinth with two ridges all the way round, standing 4mm proud so the slicer supports their undersides (BambuStudio skipped the old 1mm strips and they printed rough) |
| `back_plate` | removable back — locating lip, PCB standoffs, both vent grilles, one USB-C pass-through, antenna-mount inserts |
| `antenna_mount` | bolt-on arm carrying the antenna socket (identical to the kitten's) |
| `antenna_mount_sma` | alternative mount: same flange, arm and counter-tilt, ending in a panel-mount SMA jack instead of a socket cut for one antenna's base |
| `antenna_mount_twin` | **the one to print for the FlyCatcher:** same flange and three bolts, ending in a crossbar with two SMA jacks 80 mm apart, for the 1090 and 978 MHz whips; counter-tilted so both stand vertical with their hinges straight |
| `usbc_gauge` | test coupon: five candidate USB-C cutouts, to fit the connector before printing a whole plate |

Two extra targets, `test_antenna` and `test_speaker`, clip the real shell
geometry to a small box so a fit test prints in minutes instead of hours.

## Rendering and exporting

Set `part` at the top of the file, or override it from the command line:

```bash
openscad --backend=manifold --export-format binstl \
         -D 'part="shell"' -o shell.stl retro-enclosure.scad
```

Binary STL: the shell is 75,000 facets, which is far smaller as binary than
as ascii for byte-identical geometry, and every slicer reads both.

`part="preview"` shows the whole stack assembled; `part="exploded"` separates
it.

Exporting an STL already forces a full geometry evaluation, and OpenSCAD
prints the result on stderr — check for `Status: NoError` and the
`Top level object is a 3D object (manifold)` line before printing. (Earlier
notes here said to pass `--render`; as of OpenSCAD 2026.06 that flag takes an
argument and a bare `--render` just prints the usage text, so a script using
it silently exports nothing.)

## Things that are easy to get wrong

These are all mistakes that were actually made and fixed here, kept as
warnings rather than as history:

- **`glass_thickness` is the glass sheet alone (1.62mm), not
  `panel_glass_depth`** (6.45mm, the whole panel module). The rabbet spans
  the glass; using the module depth leaves a gap you have to squeeze shut.
- **The antenna mount is counter-tilted forward by `stand_angle`.** The case
  leans back by that same angle in the cradle, so the two cancel and the
  antenna ends up vertical. Get the sign wrong and it is off by double.
- **The cradle only cups the case; the retention rails are what hold it.**
  With the bowl's axis tilted, gravity pushes the case straight down that
  axis, and nothing else opposes it.
- **Speaker brackets must be clipped to the outer cylinder.** They are flat
  slabs across a curved wall, so their corners otherwise punch through it.
- **Grille holes have to cut through the bracket as well as the wall**, or
  they dead-end in solid plastic and no sound gets out.

## The back comes off

The back used to be a fixed floor with the electronics standing on it, which
meant the only way to a Pi was through the glass. It is a separate plate now,
screwed to eight insert posts exactly as the faceplate is, and everything
that stood on the floor went with it. Undo eight screws and the tray lifts
out as one assembly.

**This plate is the same part as the kitten's.** Both cases are the same
223.34mm diameter, both use the same eight-post ring, and both lean back by
the same 18°, so one plate and one antenna mount serve both builds. That is
checked rather than asserted: exported from each design, the two meshes are
15,410 facets that compare equal as sets — the same solid, differing only in
triangle order.

**There is no fan mount.** There was a plate standing perpendicular to the
tray carrying a 30mm fan; the fan goes on the Pi instead. `fan_mount()` and
its variables are left defined but unused — the same treatment the wall-mount
keyhole code above gets — so putting it back is a one-line change. Both
grille patterns stay as plain vents.

The insert holes are drilled in `shell()`'s difference stage rather than
inside the post module. The speaker brackets reach the wall at 0° and 180°,
exactly where two of the posts stand, so a hole subtracted inside the module
gets unioned shut again by the bracket landing on top of it — two of the
eight would have printed solid. `back_inserts_open` is the check that holds
this, and it is a positive control: it has to *find* eight open bores.

### The locating lip

A rib on the plate's inner face drops into the bore, so the plate lands
centred and square and stays put while the screws go in, instead of being
juggled against eight holes at once. The outer top edge is chamfered by
1.2mm so it finds its own centre rather than catching square.

It is eight arcs, not a ring. A continuous ring at bore diameter is the
obvious shape and it is unbuildable here: the insert posts span r=102.2–111.2
and the bore wall is r=108.7–111.7, so the posts straddle the wall and a ring
would run through all eight of them. One arc per gap between posts locates
just as well — three points fix a circle and this has eight.

Three checks hold it, because a single "does the plate fit" test passes just
as happily when the lip is missing: `lip_present` (a positive control — it
must find the lip at all), `lip_clears_posts`, and `lip_inside_bore`, since a
lip larger than the bore does not locate anything, it just stops the plate
seating.

### One pass-through, not two

The USB-C power gland and the SMA antenna gland are replaced by a single
opening for a panel-mount USB-C cable. The antenna no longer needs a bulkhead
here at all — its coax comes in through the antenna mount's own cable bore,
inside the bolt circle.

**The cutout has been fitted to the real connector** (2026-09-29): it fits
the window, and its two mounting screws are 16.5mm apart. Those screws are
M3, so the holes are M3 clearance (3.4mm) like every other screw hole. The
listing publishes no cutout size, so for a different connector print
`usbc_gauge` — the cutout plus four neighbours at ±0.5 and ±1.0mm — and fit
it before committing a back plate. A coupon is minutes; a plate is hours.

### The plate fits one way only

The plate's locating rib is eight identical arcs between eight evenly
spaced posts, so it used to seat at any of eight positions 45° apart, and
only one of them puts the antenna mount at the top. A small block on the
shell's bore wall at 247.5° (lower left, between the posts at 225° and 270°)
now meets a matching notch in one arc of the rib: upright, the plate drops
in; turned to any other position, the block lands on the rib and the plate
stands proud before a screw goes in. It sits well clear of the antenna-mount
bosses at the top and the USB-C window, and both shells put it at the same
angle, so the one plate still fits both cases.

`key_fits` proves the upright plate meets the block with no volume, and
`key_blocks_45` … `key_blocks_315` prove each of the other seven positions
collides (43.7 mm³ each), each as its own check, because a key that blocked
only some angles would still let the plate in wrong.

### The antenna mounts on the back, and the turret is gone

The turret grew the socket out of the top of the case wall. The socket now
lives on a bolt-on arm on the removable plate, which is the same part the
kitten build uses — so both cases carry the identical antenna assembly, and
the angle can be changed without reprinting a shell.
`antenna_turret_solid()`/`antenna_turret_cuts()` are left defined but unused,
the same treatment the wall-mount keyhole code gets.

`no_turret` holds it, and its first version was wrong in an instructive way:
"nothing may stand proud of `outer_dia`" reported 13,632mm³ of turret that
was actually the decorative rivets and the cradle rails, which stand proud on
purpose out to r=115.7. The turret reached r=128, so the probe sits at 116.67
— outside the rivets, well inside a turret. `turret_probe_works` is its
paired control: the retired turret module has to be *caught* by that same
probe, or an empty result would only prove the probe was set too wide.

### The antenna mount screws into inserts

Three bosses on the plate's inner face take M3 heat-set inserts, so the mount
screws into the plate rather than needing a nut held inside the case while
the bolt is turned outside. The bores are two diameters on purpose: the
insert pocket stops on a shoulder 1mm above the plate rather than running out
through it, so the insert cannot be pressed too deep and the bolt still
passes freely from outside.

The bolt circle is clocked 30° off the vertical, which is not cosmetic. At
the obvious 0° one bolt points straight up the plate, putting its boss at
y=103 with an outer edge at 106.5 — into the locating lip, whose inner face
is at 106.3.

### The vents moved

Both grille patterns stay as plain vents, but the upper one moved from
y=+68 to y=−68. The antenna mount's flange is a 40mm disc centred at y=88, so
at +68 the grille sat underneath it from y=68 to y=81 — venting into the back
of a solid disc. `vents_clear_of_mount` holds the new position and
`vents_were_under_mount` is its paired control, finding the 257mm³ overlap
the old position had.

### Side slots: top only, and cut through

The shell's side slots were cut all the way round. At each speaker, three of them ran across the grille. Underneath, six landed on the cradle's retention rails. None of them were vents: each cut was centred on the outer face, so it went only 2.5mm into the 3mm wall.

Now there are nine, across the top between the speakers (`exhaust_a0`..`exhaust_a1`, 30–150°), and they go right through. That gives the fan's air a way out at the top, where warm air goes anyway.

- `exhaust_top_only` checks that nothing is cut outside that arc.
- `exhaust_reaches_inside` checks that each slot breaks out past the wall's inner face. It finds about 115mm³, about 13 per slot; a blind dent finds nothing.

### Speaker grilles: one clean block each

Each speaker's grille is now only the rows in front of the ribs: five rows of 21 holes. Two things went:

- **The single row between the two ribs.** It read as a stray line of holes, not part of the grille.
- **The three rivets of the front ring that fell on each grille.** They stood up among the holes. The ring keeps its other 18.

These checks hold the change:
- `grille_in_front_of_ribs` and `rivets_clear_of_grilles` must come out empty. Both find the old geometry when run against it.
- `grille_present` and `rivets_present` are their positive controls.

## Heat-set inserts

Every screw that gets undone goes into a brass M3 heat-set insert. The holes are sized for the Kadrick M2–M5 kit: its M3 inserts are 4.5 mm across the knurl and 3.9 mm at the lead-in. Every insert hole is **4.0 mm**, so the lead-in drops in square and the knurl melts 0.25 mm a side into the plastic. (They were 4.2, which left a 4.5 mm insert only 0.15 mm of bite.)

| Where | Count | Insert | Screw | Notes |
|---|---|---|---|---|
| Front posts in the shell (front trim and retainer screw into these) | 8 | M3 × 5 | M3 × 14 | Pressed from the front, flush with the shelf the retainer sits on |
| Back posts in the shell (back plate screws into these) | 8 | M3 × 6 | M3 × 8 | Pressed from the back face, flush |
| Antenna mount flange | 3 | M3 × 5 | M3 × 8 | The pocket is in the mount; the screws come from inside the case, through the back plate |
| Speaker bosses (optional) | 8 | M2 × 3 | M2 × 6 | The 2.6 mm pilot takes an M2 insert or the speaker's self-tapping screws |

**The front posts are new.** They used to be only 2 mm tall: an insert sat in 2 mm of plastic with open air under it and the wall on one side only (measured: a third of the ring round it was solid). Now each post hangs 8 mm below the shelf, merged into the wall, with a 45° cone under it so it prints without support. The holes are cut after the whole shell is unioned, so the speaker brackets at 0° and 180° can't fill them.

- `front_inserts_surrounded` proves every front insert has a 1.75 mm ring of plastic all round it for its full length. Run against the old shell, it finds 545 mm³ missing.
- `front_insert_holes_open` is its positive control.

**Pressing them:** a soldering iron with an M3 insert tip, at about 220 °C for PLA or 245 °C for PETG.
1. Start the insert square in the hole.
2. Let it sink under its own weight plus light pressure. Don't push hard.
3. Stop when it is flush.
4. Hold a flat, cool piece of metal on it for a few seconds while the plastic sets, so it stays square.

### The twin mount: 1090 and 978 MHz

The FlyCatcher has two antenna inputs, 1090 and 978 MHz, and the Nooelec bundle has a hinged whip for each. `antenna_mount_twin` holds both.
- **Same base as the others:** the flange and three bolts, so nothing else changes.
- **A crossbar** with a bulkhead jack at each end, 80 mm apart. Antennas this close in frequency detune each other when bunched together.
- **Counter-tilted,** like the single mounts, so the whips stand vertical with their hinges straight. Hinges hold firmly only at their stops, and part-way they sag over time.

**Cables:** two SMA male to SMA female bulkhead jumpers, RG316, about 30 cm (SMA, not RP-SMA). The small right-angle pigtails in the antenna bundle are MCX, for Nooelec's USB sticks, and aren't used.

**Whip or external antenna, the user's choice:** each tower's jack is an ordinary SMA socket on the outside of the case. Screw on the Nooelec whip, or the coax from an antenna mounted outside or in a window; nothing inside changes. An outdoor antenna with an N-type connector needs an N-male to SMA-male cable. Leave the FlyCatcher's bias-tee switch off unless the outdoor antenna has a powered amplifier that needs it.

**Fitting the cables:** thread each one plug-first, down its tower, along the tunnel in the crossbar, down the arm, and through the back plate's 11 mm hole. Then push the bulkhead up through its tower's panel and put the nut on top. The 1090 whip is the shorter one.

**Checks:**
- `twin_plug_path_clear`: an SMA plug's width is open along the whole route. A probe 12.5 mm across, too fat for the bore, does hit it.
- `twin_antennas_clear_case`: both whips, swept 220 mm up, miss the case (and the kitten's ears). The same envelopes moved 60 mm down do hit it.
- `twin_vs_plate`, `twin_vs_stand`: no collisions with the back plate or the stand.
- `twin_panels_present`, `twin_holes_open`: positive controls; the panels are there and the jack holes are open.

## Checks

`sh run-checks.sh`. Every target must come out with no real volume except
`back_inserts_open`, which must find geometry, and `canary`, which proves
the modules are being found at all — without it a typo in the `use <>` path
makes every other check pass against nothing.

## Smoothness

Curve resolution is set by `$fs` (0.4mm) and `$fa` (0.5°), not a fixed facet
count.

A fixed count makes the flats grow with the feature, so the biggest surfaces
come out roughest. At the old `$fn = 96` this shell's 223mm rim carried
**7.3mm flats** and the cradle 8.2mm, while every 3mm screw hole also got 96
sides it had no use for. `$fs` caps the chord — the width of one flat, which
is what the eye reads as faceting — so a big curve gets the facets and a
small hole does not.

**This is the only design here that has actually been printed**, so the small
fit-critical features keep their own explicit `$fn` and are untouched. What
changed is the geometry that had no explicit setting, plus the four wide
arcs. Measured against the previous meshes, the largest dimensional change
anywhere is **+0.064mm** on the shell's outer diameter — the flats moving
outward toward the true circle, which is the direction that matters — and
every other extent moves by 0.003mm or less. Volumes rise 0.08–0.15%. All of
that is an order of magnitude under print tolerance, so nothing about the
fit changes.

## Generated STLs

Committed alongside the source so the folder is self-contained, but they are
generated. Change the `.scad` and both must be re-exported and committed
together, or the mesh quietly stops matching the source it claims to come
from.

### The connector has to fit through, not just the cable

The bore was 9mm and the coax **connector** is 9.15mm across its widest
point, so it did not pass at all. Worse, the straight bore is cut along the
plate's normal while the socket above it is tilted by `stand_angle`, so the
two were not coaxial and the socket floor met the bore at an angle — leaving
a shoulder across the opening for the antenna's base to land on. Widening the
bore alone would not have removed that; it is a consequence of the two axes
disagreeing.

The socket floor is now opened square to the **antenna's** axis and hulled
down onto the straight run, so there is one continuous passage with no step
anywhere across it. `connector_passes` sweeps a 9.15mm plug gauge along that
path and must touch nothing; `connector_gauge_works` is its paired control,
an oversized gauge that must be caught. Swept by hand the passage clears
10.5mm and blocks at 11.0mm, so the connector has 1.35mm of margin.

Note for anyone tuning this: `-D` on the command line reaches `echo` but not
the CSG tree for these files, so a gauge sweep driven by `-D` silently
measures the file's own value at every step and reports that everything
passes. Edit the number instead.

### The antenna socket, and the lip that holds the base

The socket was Ø33 and a printed mount would not take the antenna at all: the
base is a flared cone slightly wider than that where it has to pass, so it
never got under the rim. It perched on top and tipped over — while the cable
underneath ran through perfectly, which is the part that had been checked.

Then the second printed one had its **rim snap off** while a base was being
levered under it, which says the approach was wrong and not just the number.
A 2mm chamfer left 2.5mm of wall at the edge, and a printed rim that thin,
pried outwards across its layer lines, is weak. Stiffness goes as thickness
cubed, so the barrel went 45 → 48 and the chamfer 2 → 1.2mm: 4.8mm of wall at
the edge, roughly seven times stiffer.

The deeper point is that **the base is held by depth, not by an overhang**.
The socket is 8mm deep, the antenna sits down inside it, and the chamfer is a
lead-in for a base that is already smaller than the hole — not a ramp for
forcing an oversized one past. If it has to be levered, the socket is too
small; make it bigger rather than pushing harder.

### What was actually stopping it, after three wrong guesses

The base measures **31.25mm across its flared bottom**, and **the lead leaves
the SIDE of the base 7.98mm above it** — both measured. The original socket was
Ø33, already 1.75mm of clearance, so *the bore was never what stopped it*, and
three attempts to fix the bore were fixing the wrong thing: that the base was
wider than the hole, that it was a cone flaring above a narrow bottom, that
the connector needed room beneath. None of them were true.

With the base seated, the lead is 7.98mm above the socket floor — and it
cannot go down through that floor, because the base is sitting on it. It has
to leave sideways. The printed mount gave it nowhere to go, so the connector
ended up jammed in the notch where the cable passage happens to break through
the wall, holding the base up at an angle. That notch was an accident of the
geometry; there is now a deliberate slot, 7mm wide, running from the floor up
past the rim.

It faces local +Y in the antenna's frame, which works out to world
(0, +0.309, −0.951) — down and back toward the plate — so the lead drops
straight into the passage that was already there instead of being led around
the barrel. `cable_slot_open` checks a rod at the measured exit height passes
out through the wall, and `cable_slot_other_side` is its control: the same rod
on the far side must be blocked, or "the slot is open" would be
indistinguishable from "the probe missed the mount".

`socket_takes_base` holds it, with `socket_gauge_works` as its paired control.
Its first version was wrong in a way worth recording: it ran a full-diameter
disc 12mm into the air above the mouth and failed at 283mm³, which was the
arm alongside. A 35mm cylinder held 12mm above the socket really does overlap
the arm — and means nothing, because the base is a cone that narrows and comes
in from outside. The question is whether the base fits the socket.

## Two antenna mounts, and which to print

`antenna_mount` holds the antenna itself: a 33mm socket cut around the
FlightAware desktop puck's 31.25mm base, with a slot for the lead that leaves
the side 7.98mm up. It fits that antenna beautifully and nothing else, which
makes the case choose the antenna.

`antenna_mount_sma` inverts that. Same flange, same three bolts into the same
inserts, same counter-tilt -- only the far end changes, to a panel-mount SMA
jack. Anything with an SMA plug now works: the same puck, a tuned whip
standing straight off the back, or coax running to an antenna somewhere with
a view of the sky. Swapping it is three screws; the back plate and both
shells are untouched.

Print the SMA one unless you specifically want the puck held on the case.
Measured on this hardware, an indoor puck saw **1 aircraft** while a properly
sited antenna saw **14 of the same sky at the same moment** -- so the ability
to put the antenna somewhere else is worth more than any mount that holds it
here.

The counter-tilt is the part not to touch. ADS-B is vertically polarised, and
`ant_axis_frame()` is what keeps the jack vertical while the case leans back
18 degrees in its cradle.

Four things are checked rather than assumed, and the interesting one is
`sma_passage_joins`: the cavity behind the jack has to actually meet the
cable bore, or the jack threads into a sealed pocket and the coax has nowhere
to go. That failure is invisible in preview -- both volumes are cut, the part
looks hollow, and the wall between them only exists in the print.
