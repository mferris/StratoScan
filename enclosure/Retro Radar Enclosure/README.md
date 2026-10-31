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
| `retainer` | ring behind the glass; the glass rests on its front face. Keyed, so it goes in only one way: its relief at the bottom, over the gap in the shelf ([below](#the-retainer-goes-in-one-way-only)). `retainer.stl` is glass face down, the way it prints |
| `stand` | desk cradle — two ring-arc arms on a plinth with two ridges all the way round, 4mm proud, their undersides sloped at 45° to a small lip like the case's rings (the old 1mm strips printed rough unsupported, and square 4mm ridges needed supports all round). A clip at the back of the plinth, directly under the plug, holds the charger's cable ([below](#the-stand-holds-the-chargers-cable)). **Watch the lips on the first print:** since the clip's notch, the slicer no longer supports the ridges' 0.8 mm lips, and no print has yet shown how they come out (2026-10-30). Print `test_clip` first and look under its lips |
| `back_plate` | removable back — locating lip, both vent grilles, the trigger board's USB-C window with a pocket for the plug's moulding and two insert holes for its mount, the charger it needs engraved above it, the antenna mount's bolt holes and cable hole, two insert bosses for the regulator's tray, ten cable-tie bridges for its leads and the coax, and two low curbs that keep the slack of the pigtail and the coax on their own sides ([below](#the-regulators-place)). Prints outer face down, supports off |
| `back_plate_twotone.3mf` | the same plate with its charger label in a second colour: one object, the plate on filament 1 and the lettering (`back_plate_text`) on filament 2. Built by `make-cover-3mf.py` from binary STL exports ([below](#the-label-in-a-second-colour)) |
| `antenna_mount` | bolt-on arm carrying the antenna socket (identical to the kitten's) |
| `antenna_mount_sma` | alternative mount: same flange, arm and counter-tilt, ending in a panel-mount SMA jack instead of a socket cut for one antenna's base |
| `antenna_mount_twin_8`, `antenna_mount_twin_11` | **the one to print for the FlyCatcher:** same flange and three bolts, ending in a crossbar with two SMA jacks 80 mm apart, for the 1090 and 978 MHz whips; counter-tilted so both stand vertical with their hinges straight. Two styles, for jumpers whose bulkhead body is an 8 mm hex or an 11 mm hex; two parts each, this body and the cover below (`antenna_mount_twin` is whichever `ant_twin_jack_af` names) |
| `antenna_mount_twin_cover_8`, `antenna_mount_twin_cover_11` | the 3 mm cover that closes the twin body's cable channel, on five M2 screws, with each side's frequency engraved in it (`twin_assembled` and `twin_assembled_11` show both parts on the plate, for pictures only) |
| `antenna_mount_twin_cover_8_twotone.3mf`, `antenna_mount_twin_cover_11_twotone.3mf` | the same covers with the frequencies in a second colour: one object, the cover on filament 1 and the lettering (`antenna_mount_twin_cover_text_8` / `_11`) on filament 2. Built by `make-cover-3mf.py` from binary STL exports |
| `test_lettering_plate.3mf`, `test_lettering_cover.3mf` | two-colour test coupons, a 1.2 mm slice of the plate's and the cover's faces round their lettering, about 11 minutes each: print one before a whole plate or cover, to see the slicer lay every letter down whole ([below](#lettering-in-two-colours-print-settings)) |
| `usbc_gauge` | test coupon: a 36 × 18 mm piece of the back plate round the USB-C window, its window, pocket and insert holes exactly the plate's, so the charger's plug can be tried in the trigger board before a whole plate is printed (about ten minutes) |
| `power_trigger_mount` | the power fix's 12 V trigger board's mount: a sleeve round the board, two crush ribs in its roof holding the board down, on two M3 screws into inserts in the plate, with the board's socket through the plate's USB-C window, so the charger plugs straight into it ([below](#the-power-fix-the-charger-plugs-into-the-trigger-board)) |
| `power_trigger_stop` | the block behind the trigger board in its mount, locked by two M2 screws through the mount's walls, so the board has no play; keyed, so it goes in only the right way round. Print three: one for the trial fit on `usbc_gauge`, one for the plate and a spare. Its crush ribs are spent once squeezed, so a stop that comes out is never fitted again |
| `power_regulator_tray` | the power fix's 5 V regulator's tray, screwed to two insert bosses at its one place across the bottom of the plate's inner face, a saddle with a cable-tie slot at each open end for the leads, `OUT` and `IN` engraved at its two ends, and a tie groove under each half of its floor (since 2026-10-29, [below](#the-regulators-place)). Prints floor down, supports off |

Four extra targets, `test_antenna`, `test_speaker`, `test_rings` and
`test_clip`, clip the real geometry to a small piece so a test prints in
minutes instead of hours. `test_rings` is a 40° slice of both rings, for
trying a new material on the rings' slope and lip. `test_clip` is the stand's
cable clip in a 24 × 33 mm piece of the plinth's back, for trying the
charger's cable in it before printing the stand (18 minutes, 4 g).

## Lettering in two colours: print settings

The back plate's charger label, the twin antenna covers' frequencies and the
Retro with Dials' control arc are inlaid in a second colour, and each part
prints face down, so its letters are its first three layers (2026-10-31).
The first two-colour arc printed with broken letters: SCREEN's C almost gone,
STATUS's S half there, and a pale ring round each word. Its strokes were
0.5 mm wide, about one first-layer line, and Bambu Studio's default classic
walls leave out a stroke too narrow for two of them. Sliced with the
defaults, the old lettering's first layer is thin and patchy in its narrow
strokes, the C and S among them. What caused the pale ring is not yet known;
print a coupon (below) to see whether these settings cure it.

Two things changed. The lettering is larger and bolder, with every stroke at
least 1.0 mm wide and every counter and gap between letters at least 0.8 mm
open (`tests/test_enclosure_core.py` measures them, check 13). And the
first three settings below go on the part, set by hand once the 3MF is
open: Arachne walls, elephant-foot compensation 0 and a monotonic line
bottom surface. For a few hours on 2026-10-31 the 3MFs carried them as
per-object settings, but Bambu Studio's desktop app then opened the files
as geometry only ("The 3mf file has invalid config"), losing the filaments,
so the 3MFs now hold only the parts and their filaments. Sliced with the
settings, the first layer now lays two lines or more across most of each
stroke, and one wider Arachne line, up to 0.7 mm, across most of the rest. Arachne walls and the larger lettering
are what fill the first layer.

**Print a coupon first.** `test_lettering_plate.3mf` and
`test_lettering_cover.3mf` (in the Retro and Kitten folders) and
`test_lettering_arc.3mf` (Retro with Dials) are 1.2 mm slices of the faces
round their lettering, cut from the parts themselves. Each prints in about
11 to 12 minutes on an X1C, against 25 minutes for a cover, 52 for the arc
and 2 h 40 min for the plate. When a coupon's letters come out whole with
clean edges, its part will too.

The settings, with their names in Bambu Studio 2.08 and the keys in its own
profiles. Set the first three on the object (right-click it in the object
list, then Process, and add them under Quality and Strength) or, with only
the face on the plate, in the print settings; the 3MF does not set them.

| Setting | Where | Value | Key | Who sets it |
|---|---|---|---|---|
| Wall generator | Quality | Arachne | `wall_generator` | you, per object or for the plate |
| Elephant foot compensation | Quality > Precision | 0: keeps the face's outer edge from being pulled in 0.15 mm; it does not touch the lettering | `elefant_foot_compensation` | you, per object or for the plate |
| Bottom surface pattern | Strength | Monotonic line | `bottom_surface_pattern` = `monotonicline` | you, per object or for the plate |
| First layer line width | Quality > Line width | 0.42 mm | `initial_layer_line_width` | you, in the print settings |
| First layer speed, and first layer infill | Speed | 30 to 40 mm/s | `initial_layer_speed`, `initial_layer_infill_speed` | you, in the print settings |
| Prime tower | Others | on (the default) | `enable_prime_tower` | you, in the print settings |
| Z-hop | Printer > Extruder | 0.4 mm, Auto Lift (the X1C's default) | `z_hop`, `z_hop_types`; a filament can override it with `filament_z_hop` | the printer |
| Plate | the plate's type | Smooth PEI ("Smooth PEI Plate / High Temp Plate"), clean, preferred over the Engineering plate for a face | `curr_bed_type` | you |
| Filament | | dry ASA: 65 °C for 12 h, or 80 °C for 8 h where the dryer allows it (Bambu's ASA profile) | | you |

What slicing with Bambu Studio 2.08's command line showed:

- Bambu Studio honours the first three settings per object. With Arachne
  alone, the old cover's first layer laid down much more of its lettering.
- Elephant-foot compensation acts only on a part's outside edge, not on the
  edge the two colours share. Sliced with it at 0.15 and at 0, the
  lettering's first layer came out the same, and only the face's outline
  grew 0.15 mm a side. It is off so the face's edge prints true.
- Set per object, first-layer line width and speed did nothing. They work
  only as print settings, so set them there.
- A first-layer width of 0.42 instead of 0.5 hardly changed the coverage:
  90 to 94% either way. It lays a third line in more of the wider strokes,
  at the cost of more short lines under 0.4 mm. Arachne's walls do the
  work.
- The slow first layer and the Z-hop keep the nozzle from catching the
  first layer's edges. The gouge beside the SCREEN hole on the first arc
  looks like that kind of drag. Wet ASA strings and blobs on those travels.
- The prime tower takes each colour change's purge, three changes on the
  way up and one back to filament 1, off the part.

## Rendering and exporting

Set `part` at the top of the file, or override it from the command line:

```bash
openscad --backend=manifold --export-format binstl \
         -D 'part="shell"' -o shell.stl retro-enclosure.scad
```

Binary STL: the shell is 75,000 facets, which is far smaller as binary than
as ascii for byte-identical geometry, and every slicer reads both.

The two-colour projects are built from those exports: after exporting
`back_plate` and `back_plate_text`, or a cover and its `_text_` part,
`python3 make-cover-3mf.py back_plate_twotone.3mf` (or a cover's or a
coupon's 3MF; no name builds them all). `tests/test_enclosure_core.py` (check 12) fails
while a 3MF no longer holds its folder's STLs, so rebuild it after any
re-export of its parts.

`part="preview"` shows the whole stack assembled; `part="exploded"` separates
it. The preview places the retainer, the glass and the trim with
`front_stack_placed()`, the one place the stack is worked out, and the
trim's face is at `z_trim_face`, 66.62 mm (2026-10-29). The trim used to
stand on the panel's whole 6.45 mm depth there, 4.9 mm too far forward.
`front_stack_seats`, `front_stack_retainer_down` and `front_stack_trim_down`
hold it: the stack meets the shell with no volume, and lowered 0.2 mm the
retainer runs into the shelf and the trim into the rim.

Exporting an STL already forces a full geometry evaluation, and OpenSCAD
prints the result on stderr — check for `Status: NoError` and the
`Top level object is a 3D object (manifold)` line before printing. (Earlier
notes here said to pass `--render`; as of OpenSCAD 2026.06 that flag takes an
argument and a bare `--render` just prints the usage text, so a script using
it silently exports nothing.)

That line is not the slicer's check (2026-10-29). Where two solids in a part
only touch, along a line or a face, instead of overlapping, the export still
says manifold, and Bambu Studio reports non-manifold edges and reversed faces
when it opens it: `shell_dials.stl` did. `python3 tests/test_enclosure_core.py`
checks every print file's edges as a slicer does, so run it after an export.

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
- **Speaker brackets must be clipped at the wall.** Each is a flat box across
  a curved wall, so its ends otherwise poke out through the shell.
- **The speaker brackets are hollow sleeves**, so the grille holes cross only
  the wall. They were solid blocks until 2026-10-23, and the holes had to be
  drilled right through them as tubes.

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
USB-C opening. The antenna no longer needs a bulkhead here at all — its coax
comes in through the antenna mount's own cable bore, inside the bolt circle.

**Since 2026-10-29 the opening is the 12 V trigger board's own** (the power
fix, [below](#the-power-fix-the-charger-plugs-into-the-trigger-board)): a
window the shape of the board's socket, a pocket round it in the outer face
for the plug's moulding, and two insert holes for the board's mount. Until
then it took a panel-mount USB-C extension, in an 11 × 8 mm window with two
M3 holes 16.5 mm apart (slots to 17 mm from 2026-10-13); that extension
doesn't fit this plate. Print `usbc_gauge`, the 36 × 18 mm piece of the plate
round the window, to try the board and the charger's plug before printing a
plate. A coupon is minutes; a plate is hours.

### The front: trim, glass, retainer

Eight M3 × 14 screws go through the front trim's M3 clearance holes (3.4mm),
past the retainer, and into the M3 inserts in the shell's front posts.

**The retainer slips into the shell with 0.4mm to spare all round**
(`retainer_clear`). It was drawn at exactly the bore's diameter, and the
first print, PETG in an ASA shell, had to be forced in (2026-10-09). ASA
shrinks a little more than PETG, which made the zero clearance worse, but the
missing clearance was the cause. Its screw holes are **open notches** at the
rim: the screws sit where the shell's inserts are, which leaves less than a
hole's width of ring outside them, and closed holes printed as a 0.3mm
sliver. The notches also stop the ring turning. Checks: `retainer_clears_bore`,
`retainer_screws_pass`, `trim_screws_pass`.

**The connector is 37 mm lower than it first was** (2026-10-10), at `[60, -51]`, so the power jumper no longer bends against the Pi's USB ports beside the old spot; a check proves a plug there clears the stand with the case leaning back.

**The plug's moulding goes into a pocket** (since 2026-10-10; 14 × 10 mm and
1.4 mm deep since 2026-10-29). The trigger board's socket stands 0.4 mm proud
of the pocket's floor, so a moulding meets the socket and never the plate.
Checks: `usbc_recess_open`, `usbc_recess_web`, `usbc_inserts_clear_pocket`
(with `usbc_insert_probe_works`).

### The retainer goes in one way only

The retainer's relief, the 50° gap in its inner band, has to be at the
bottom, over the display's driver board, which is taped to the back of the
glass there. The ring's eight screw notches let it go in eight ways, and in
the other seven, solid ring sits under the board: tightening the trim's
screws then presses the glass, and the board, onto it.

Since 2026-10-29 a 2 mm tab on its back face (the face that sits on the
shelf), at 250-258° and r 102.7-107 mm, outboard of the glass's edge, drops
into the gap in the shelf at the bottom only when the relief is there too.
Turned to any other position, the tab lands on the shelf, and the ring
stands 2 mm proud before a screw goes in. So: **relief at the bottom, over
the gap in the shelf.** Seen from behind, the tab is a little right of the
bottom.

**Check the leads before fitting a keyed ring.** The tab hangs 2 mm into the
shelf's gap, the channel left for the display's cabling, at 250-258° and
r 102.7-107 mm, between the glass's edge and the wall, so a display cable or
speaker lead running through there would be pinched under it. No built unit
has been checked for one yet (2026-10-29). If one has to run there, move the
tab instead: set `retainer_key_a` to another 8° of the gap (245-295°), clear
of the lead and at least 3° from the screw at 270°, in both cases' designs,
since the retainer is shared; re-export `retainer.stl` in both case folders;
and re-run `retainer_key_fits` and `retainer_key_blocks_45` …
`retainer_key_blocks_315`, which must still find all seven wrong positions
blocked.

`retainer.stl` is exported glass face down, the way it prints: the tab
stands up off its top, and nothing overhangs.

**Check it is the right way up before the glass goes on (2026-10-30).** The
tab faces the shelf, away from you as you fit the ring from the front. Seated
the right way up and round, the ring lies flat with its relief at the
bottom, and from the front no tab shows anywhere. If you can see a 2 mm tab
standing up off the ring's front face, it is upside down: take it out and
turn it over. Flatness alone doesn't prove it: upside down, the tab is on
the glass's side, so the ring lies flat on the shelf in all eight positions,
and in seven of them solid ring sits under the driver board. Once the glass
and trim are on, the only sign is the trim standing about 2 mm proud at one
spot, over the tab; if it does, take the trim and glass off and turn the
ring over. `retainer_flipped_meets_trim` holds that sign: the ring upside
down, under the glass and trim, runs into the trim (about 126 mm³).

`retainer_key_fits` proves the ring seated the right way round meets the
shell with no volume, and `retainer_key_blocks_45` … `retainer_key_blocks_315`
that each of the other seven positions lands the tab on the shelf (125.9 mm³
each), each as its own check, as for the plate's key below.

### The plate fits one way only

The plate's locating rib is eight identical arcs between eight evenly
spaced posts, so it used to seat at any of eight positions 45° apart, and
only one of them puts the antenna mount at the top. A small block on the
shell's bore wall at 247.5° (lower right seen from behind, between the posts at 225° and 270°)
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
y=+68 to y=−68. The antenna mount's flange is a 40mm disc centred at y=88 (y=81 since 2026-10-07, see below), so
at +68 the grille sat underneath it from y=68 to y=81 — venting into the back
of a solid disc. `vents_clear_of_mount` holds the new position and
`vents_were_under_mount` is its paired control, finding the overlap the old
position had (487 mm³ with the flange at y=81).

**The low grille moved again on 2026-10-29,** from (0, −68) up to (6, −46),
just under the central grille, with the owner's OK: the bottom of the plate is
the regulator's tray's now ([The regulator's place](#the-regulators-place)).
It keeps its 19 holes, so the same area of intake, but 22 mm higher: its air
has that much less height to rise through the case before it leaves at the
top, and nothing now lets air in below the regulator, which loses 1-1.5 W
there. The nearest holes of the two grilles are 10.1 mm apart, centre to
centre, so 7 mm of plate between them. The 53-63 °C the Pi ran at with no
fan were measured with the grille at the bottom, so **measure the Pi's and
the regulator's temperatures again** once a unit is built this way, with the
panel lit. The 12 V pair crosses the low grille on the decks of two tie
bridges, 4.4 mm off the plate, so its holes stay open. `tray_clear_of_grilles` keeps the tray off
both grilles; its control, `tray_grille_probe_works`, puts the low grille back
where it was and finds it under the tray.

### Side slots: top only, and cut through

The shell's side slots were cut all the way round. At each speaker, three of them ran across the grille. Underneath, six landed on the cradle's retention rails. None of them were vents: each cut was centred on the outer face, so it went only 2.5mm into the 3mm wall.

Now there are nine, across the top between the speakers (`exhaust_a0`..`exhaust_a1`, 30–150°), and they go right through. That gives the fan's air a way out at the top, where warm air goes anyway.

- `exhaust_top_only` checks that nothing is cut outside that arc.
- `exhaust_reaches_inside` checks that each slot breaks out past the wall's inner face. It finds about 115mm³, about 13 per slot; a blind dent finds nothing.

### Speaker grilles: one clean block each

Each speaker's grille is now only the rows in front of the ribs: five rows of 21 holes, less the four at the front post. Three things went:

- **The single row between the two ribs.** It read as a stray line of holes, not part of the grille.
- **The three rivets of the front ring that fell on each grille.** They stood up among the holes. The ring kept its other 18; since 2026-10-29 it keeps the nine across the top (next section).
- **The four holes at the front post** (2026-10-29). The front screw post on each speaker's axis hangs from the shelf down to z 45, in the way of the grille's front rows: it filled 64% of the front row's middle hole, cut into the two beside it, and the tip of its cone reached into the middle hole of the row behind. The holes run parallel to the speaker's axis, past the post, so any hole whose edge comes within 0.5 mm of the post, seen along the hole (`grille_post_clear`), is dropped. Each grille keeps 101 holes, 496 mm² of opening where it had 515, and every one is clear right through.

These checks hold the change:
- `grille_in_front_of_ribs` and `rivets_clear_of_grilles` must come out empty. Both find the old geometry when run against it.
- `grille_clear_of_posts` must come out empty: every hole, widened by 0.5 mm, misses the front posts. The grille as it was finds 182 mm³.
- `grille_present`, `rivets_present` and `grille_post_probe_works` are their positive controls; the last is the same widened holes with the posts moved one row back, where they meet holes that are kept (47 mm³).

### The case sits on its wall, not on rivets

The front ring had nine rivets under the case, 205-335°, inside the stand's
front arm. The arm hid them, and they stood 0.7 mm proud into the cradle's
1 mm clearance, so the case's front sat on the tips of two or three of them
rather than on its wall. They are gone (2026-10-29), and the ring keeps the
nine across the top, where they are seen.

`shell_seats_in_stand` must come out empty: the case dropped 1 mm in the
cradle, straight down across its axis, meets the stand with no volume, so
nothing on it stands into the clearance where the arms are. The old rivets
found 54 mm³. `shell_seats_probe_works` is its control: dropped 1.5 mm, the
case's own wall runs into the arms (3,071 mm³).

### The rings print without support

The two rings round the body were square bands, 4 mm proud and 5 mm wide. The
shell prints back-down, so each ring's underside was a 4 mm shelf in mid-air,
and the slicer supported it all round: the first ring from the plate, the
second from the top of the first. Those supports welded on. On an ASA shell
(2026-10-24) they came off leaving the band below the first ring, and the top
of the first ring, torn.

Now each underside slopes at 45° from the wall to a 0.8 mm square lip at the
outer edge (`rib_lip`). The slope prints on its own, and a lip that small is
too little for the slicer to support and prints clean. The lip keeps the sharp
shadow line under each ring; a plain slope loses it, and the rings read as
moulded bands. From the front nothing changes: each ring's front face is
square and 4 mm deep.

- `rib_slopes_present` finds the slope just below each ring. It finds nothing
  against the square rings.
- `rib_lip_kept` must come out empty: under the outer half millimetre of each
  ring is air. A full 45° slope fills it.
- The stand's two plinth ridges have the same profile, and the same pair of
  checks: `plinth_slopes_present` and `plinth_lip_kept`. They sit only 3 mm
  apart, so the upper ridge's slope fills most of the gap between them.

### The shelf, the sleeves and the front rail need less support

Three more undersides inside the shell were flat and in mid-air as it
prints, back down (2026-10-29):

- **The shelf** the retainer sits on was an 11 mm flat ledge all round at
  z 55, supported from the plate 55 mm below. Its underside now slopes at 45°
  from r 103 out to the wall (`shelf_slope()`), so only its inner 5 mm needs
  support. Not over the speakers (next), nor over 30-75°, where the Retro
  with Dials has two screw heads and its wire hole inside the wall at
  z 49-50, nor in the shelf's gap at the bottom.
- **Over each speaker**, the sleeve's top wall stopped 2 mm under the shelf,
  and support in a slot that size can hardly be got out. The top wall now
  carries on up to the shelf wherever the shelf is over it.
- **The front rail** (z 39-43) had a square underside, supported from the
  top of the rear rail: the same ASA-on-ASA weld that tore the rings. It now
  has the rings' 45° underside and 0.8 mm lip (`retain_lip`); its top, the
  face that bears on the front arm, is unchanged. The rear rail stays
  square, because its underside is what bears on the rear arm.

Sliced in Bambu Studio 2.08 (X1C 0.4 mm, 0.20 mm Standard, Bambu ASA, tree
supports at 30°), the shell's support went from 42.0 to 33.7 cm³ and the
print from 8.5 to 7.7 hours. (Those are the figures for that step. The
shell as committed now, with the changes after it, slices at 34.0 cm³:
checked 2026-10-30.) Measured on the mesh, the flat overhang went
from 14,650 to 10,680 mm²: the shelf's from 5,800 to 2,310, and the front
rail's from 603 to its lip's 122. The speaker sleeves' roofs (2,730 mm²) and
floors (2,910) are still supported. Fins inside each sleeve, to cut its roof
into 31 mm bridges, were tried and left out: this profile supports bridges of
any length, so they saved 0.6 cm³ of support and cost 1.6 g and 4 minutes.

- `shelf_slope_present` finds the slope under the shelf, by the wall. It
  finds nothing in the old shell.
- `speaker_slot_closed` must come out empty: where the slot was, all is
  solid (the old shell leaves 1,632 mm³ there). `speaker_slot_probe_works` is
  its control.
- `rail_slope_present` finds the front rail's slope, and `rail_lip_kept` must
  come out empty, as for the rings: a full slope with no lip puts 13.5 mm³
  there.
- `rear_rail_square` must come out empty: under the rear rail is air (a
  sloped rear rail puts 250 mm³ there). `rear_rail_probe_works` is its
  control.

#### For a later shell print

Two changes that would take more support out of the shell, left for a
later print so that the shells committed now stay as they are (2026-10-30).
Each changes shared core: make it in both designs, re-export `shell.stl` in both
case folders and `shell_dials.stl`, and re-run every check.

- **Slope the shelf's inner strip too.** The slope starts at r 103
  (`shelf_slope_r0`), leaving a 5 mm flat strip, r 97.7-103, that still
  takes about 6.7-7.4 cm³ of each shell's support outside the speakers and
  the 30-75° skip. Set `shelf_slope_r0` to `retention_opening/2` and a 45°
  slope from r 97.67 meets the bore at z 44: 2.75 mm above the side slots'
  tops at z 41.25, merged with the posts' cones, and still cut away at the
  speakers, 30-75° and the shelf's gap. Over the kitten's ears the hollows'
  tents trim it. Check the cable runs inside the wall at z 44-55 first. It
  would save about 7 cm³ of support and 20 minutes a shell.
- **Start the front posts' cones on the wall.** For the six posts away from
  the speakers, a 45° corbel hulled onto the bore in place of the cone would
  start on the wall at about z 42.5, so no tip begins in mid-air
  ([Heat-set inserts](#heat-set-inserts)). The posts at 0° and 180° keep
  their cones, where a corbel would reach into the speaker grilles' rows.
  That saves only the eight small trees, about 0.5 cm³.

### Speakers: a hollow sleeve, not a solid block

Each speaker used to sit on a solid block 15 mm deep, with the grille drilled
through it as long tubes: about 38 cm³ of plastic a side for nothing (the
owner noticed, 2026-10-23). Now a 1.6 mm sleeve with the speaker's own
100 × 45 mm outline runs from the speaker's face to the wall. It keeps the
sound going out through the grille instead of into the case. Four 6 mm screw
pads in its corners take the same 92 × 36 mm screws. The shell went from
251.5 to 175.7 cm³.

`speaker_sleeve_hollow` must come out empty: nothing in the sleeve between
the speaker's face and the wall, clear of the pads. `speaker_probe_works`,
the same probe reaching 1 mm into the wall, is its positive control.

### The regulator's place

**`power_regulator_tray`** holds the regulator (63.5 × 27.25 mm, measured on
the first unit's regulator on 2026-10-30, and 12.3 mm from its underside to
the top of its tallest capacitor, measured on 2026-10-17, so about 16 mm off
the plate in the tray) at one place on the plate's inner face, screwed down,
and its two leads and the coax run along set routes, tied to bridges on the
plate (since 2026-10-29). The tray used to be stuck on with VHB tape wherever
the case had room. Nothing checked where that was, every plate removal flexed
the tape through the leads, its only tie went round the board's middle, 15 mm
from the terminals, so a pull on the pigtail landed on the terminal screws,
and nothing said where the leads ran.

**Left and right here are as seen from behind the case**, where anyone
fitting the plate stands. Seen that way, on the first unit: the trigger
board's socket is at the lower left; the Pi's USB-C power plug goes in at the
upper right, pointing up; and the FlyCatcher's two SMA jacks are on its
right-hand edge, their plugs pointing right, toward the right-hand speaker.
The coax comes in at the top, at the cable hole, and has to get down the
right to those jacks. So the power keeps to the lower half and the left:

- **The regulator** lies across the bottom of the plate, turned 8° to follow
  the rim, its middle at (−10.5, −75.5) in the design: 76 mm below the
  middle of the plate and 157 mm from the cable hole, as far from the
  FlyCatcher and the antenna leads as the plate allows. The regulator
  switches, and the 978 MHz band is the sensitive one. Its **output (OUT) is
  at the left-hand end** and its **input (IN) at the right-hand end**, seen
  from behind, and the tray says so: `OUT` and `IN` are engraved in its two
  tongues.
- **The 12 V pair** leaves the trigger board's mount, crosses over the
  pigtail once (both are power) and comes down onto its first bridge, between
  the trigger board and the low vent. It crosses the vent on the decks of that
  bridge and the next, 4.4 mm off the plate, so the vent's holes stay open
  under it, drops past the tray's upper ear to a third bridge, up the plate
  from the tray's right-hand end, and goes round that end on a fourth, onto
  the saddle there, to IN. It runs above the tray, never across the
  regulator, and the fourth bridge holds its loop round the end, so the loop
  can't rise toward the SMA plugs.
- **The pigtail** leaves OUT at the tray's left-hand end, turns up past the
  trigger board's mount on a bridge, crosses the gap between the mount and
  the Pi on another, runs up the left side of the Pi, between its USB ports
  and the left-hand speaker, on a third, and turns along the Pi's top edge at
  a fourth, at the Pi's top left corner. From there it lies free along the
  top of the Pi, between the Pi and its curb, with the ferrite on it, to
  the plate under its plug, and up into the Pi's USB-C port.
- **The coax**, both jumpers together, goes from the cable hole to the right
  through two bridges, then down the right-hand side, between its curb and
  the right-hand speaker, to the SMA jacks.

**The curbs** are two low walls on the plate, 8 mm tall, beside the two runs
that are tied at one end only: the pigtail's, from its last bridge to its
plug, and the jumpers', from their last bridge to the SMA plugs. Each of
those runs carries the slack that lets the plate be eased back 5 cm before
its plug comes out, and as the plate goes home the slack goes wherever it is
pushed. Each curb stands on the side toward the other cable. The pigtail's
slack stays between the Pi's top edge and its curb, or arches off the plate
toward the Pi; the jumpers' stays between their curb and the right-hand
speaker, above the SMA plugs: their spare length is folded into the second
bridge's tie, so no loop hangs below the plugs toward the 12 V pair. Nobody has to judge a bow by
eye, and the checks hold the whole strip each run can take, not just the line
drawn along it, 20 mm from the other cable.

Measured between the cables' surfaces on the routes as the design draws them,
with the SMA jacks anywhere along the FlyCatcher's edge they could be (nobody
has measured where they are): the 12 V pair is 24 mm from the SMA plugs' zone
at its nearest and 68 mm from the coax; the pigtail's whole strip under its
curb is 30 mm from the coax and the cable hole and 25 mm from the SMA plugs'
zone; the coax is 24 mm from the Pi's USB-C plug, and its whole strip 21 mm;
and no power lead crosses the coax. In plan the routes are 16.3 cm long for
the 12 V pair, from the trigger board's pads to IN; 23.6 cm for the pigtail,
from OUT to the plate under its plug; and 9.3 cm for the coax, from the cable
hole to the top of the SMA plugs' zone.

**The one exception is the Pi's own.** Its USB-C socket is 11 mm from the
FlyCatcher's right-hand edge, and nothing on the plate can move either. The
pigtail's plug, its drop from the plug to the plate, past the height of the
SMA jacks, and its first 13 mm along the plate, 3 to 4 cm of cable in all,
come within 20 mm of where an SMA plug could be: the plug's moulding is 8 mm
from the SMA plugs' zone in plan (5 mm from the HAT's corner). That is with
a jack as high on the edge as one can stand. With both jacks below the edge's
middle it is about 30 mm, and there is no exception; so measure where yours
are (below).

- **Why there:** every spot was tried against the speakers, the trigger
  board's 70 × 13.5 mm strip
  ([the power fix](#the-power-fix-the-charger-plugs-into-the-trigger-board)),
  the vents, 50 mm round the cable hole, the Pi and its HAT
  (`hat_envelope`, below), the rim and the posts, leaving room past each end
  for ferruled leads. The lower left is the trigger board's strip; the lower
  right, upright, where the case review first put it, fits the tray alone
  with under a millimetre to spare, its ends against the Pi and the rim. The
  bottom centre is the best place, and the low grille was there, so the
  grille moved up under the central one ([The vents moved](#the-vents-moved))
  and the tray took the bottom. Within the bottom, the place is the one that
  keeps OUT short of the trigger mount's nearer ear, so the pigtail can turn
  up beside it, and IN low enough that the 12 V pair passes above it 20 mm or
  more from the SMA plugs, with 2.5 mm or more of plate to the lip, the
  posts, the strip and the low vent's holes.
- **The fixing:** two ears, one on each long side. Each is a cap over a
  7.5 mm boss on the plate, and an **M3 × 8 button-head** screw goes down
  through the cap into an **M3 × 5 heat-set insert** in the boss, with 5 mm of
  thread. The caps fit over the bosses with 0.3 mm to spare, so the tray is
  in its place before a screw goes in. The ears are offset along the tray, the
  upper one clear of the low vent and the 12 V pair's way, the lower one off
  the post at the bottom of the rim, so the tray goes on one way only. The
  regulator itself would still lie in it either way round, and reversed, the
  pigtail would start below the SMA plugs: hence `OUT` and `IN` on the
  tongues. Screws, not VHB tape and locating pegs: tape on a part whose leads
  pull on it every time the plate comes off creeps and peels, and pegs stop
  it sliding but not lifting. The tray comes off with the regulator still in
  it and goes back in the same place. The bosses' holes stop 2 mm short of
  the plate's outer face, so nothing shows outside.
- **The pocket:** 0.5 mm bigger than the board all round, 64.5 × 28.25 mm.
  A printed pocket comes out about 0.1 mm a side smaller than it is drawn,
  and if the ASA shrinks half a percent as it cools, that takes another
  0.3 mm off its length, which still leaves the board about 0.25 mm a side
  along it and 0.3 across it: it drops in without forcing. Drawn for the
  published 63 × 27 mm, as it was until 2026-10-30, the pocket would have
  left the measured board 0.25 mm a side along it before printing, and next
  to nothing after. The board rests on a rib along each long side, and the
  tongues' ends stand 1.1 mm over its underside, so it can't slide out of
  either end.
- **The ties at its ends:** a tongue past each open end, low enough to pass
  under the leads' ferrules, ends in a saddle with a slot through its foot
  for a cable tie round the saddle and the leads on it. The saddle starts
  just past a ferrule's collar (8 mm out of its terminal), so the tie grips
  each lead's insulation, not its collar, and its top is level with the
  terminals' wire entries, less half a lead, so each lead runs straight from
  its terminal to its tie. A pull on a lead then lands on the tray, not on
  the terminal's screw. **Put each tie's head on top, over the leads:** the
  tray's lower side is 4 mm from the plate's lip, and a head there would hit
  it. The terminals were measured on the first unit's regulator, with its
  leads in (2026-10-30): the leads leave them about 2 mm over the board's top
  face, to their middle, and nothing stands past either end of the board,
  neither the terminals nor the input jack and the USB socket. So the
  saddles' tops are 6.1 mm off the plate, and each tie grips its leads 8.5
  to 13.1 mm past the board's end. Until then the design guessed the entries
  at 4 mm, which put the saddles 2 mm too high: each lead would have been
  bent up 2 mm onto its saddle right where it leaves its ferrule. The tongues
  stay 0.5 mm under the ferrules, whose collars come down to the board's top
  face. The board's thickness isn't measured (`pwr_reg_pcb_t`, 1.6 mm, the
  usual): measure it before printing, since the entries go up or down with
  its top face.
- **The ties at its middle:** a groove under the floor at each quarter of the
  tray's length, **one tie through each**, round the tray and the board. Fit
  both: in the case the plate stands nearly upright, and nothing else keeps
  the board in the tray.
- **The plate's tie bridges:** ten on the inner face, each a deck on two legs
  with a tunnel under it for a tie: four for the 12 V pair, four for the
  pigtail and two for the coax, where the routes above say. The deck over
  each tunnel is 1.0 mm, the five top layers a slicer prints solid, so all of
  it prints solid; a thicker deck would only get sparse infill in its middle,
  and a tie pulled tight squeezes the deck between itself and the cable
  rather than bending it. **Put each tie's head on top, over the cable,
  except at the pigtail's third bridge,** beside the Pi's USB ports: there,
  put it on the speaker's side, on the plate, so nothing there stands more
  than 10.7 mm up, under the plugs in those ports. On the first unit a
  regulator lead ended up wrapped round an antenna cable and 1090 MHz fell to
  a few messages a minute; the routes keep them apart.
- **Ties:** 14 in all, **150 mm long and 3.6 mm wide**: one at each saddle
  and one through each groove (their loops are 82–100 mm round, more than a
  100 mm tie closes on), and one at each bridge. One size for all of them.
- **Printing:** the plate outer face down and the tray floor down, both with
  **supports off**. The tunnels through the bridges and the saddles have
  tented roofs, two 45° slopes, so they need no support whatever the setting:
  with supports on, Bambu Studio puts none in them. The plate needs supports
  off for the USB-C pocket's stepped floor (with supports on, Bambu Studio
  fills the pocket, 56 mm³), and the tray for its two grooves and the caps'
  bores, which are bridges (with supports on, 234 mm³ in them). Nothing else
  needs setting: the bridges' decks print solid. Sliced in Bambu Studio 2.08
  (X1C, 0.4 mm nozzle, 0.20 mm Standard, Bambu ASA, supports off): the plate
  2.6 h and 81 g, the tray 22 minutes and 9 g.

**Cut the leads to length**, so no spare length ends up near the antenna
leads:
- **The 12 V pair:** cut each wire 21 cm and twist them together before
  soldering ([power-fix.md](../../docs/power-fix.md), step 2). In the case the
  pair takes about 20 cm, from the trigger board's pads through its four
  bridges to IN. If any is left over, leave it as a gentle bend above the
  trigger board's mount, the far side of the plate from the antenna jacks,
  never in the loop round the tray's end.
- **The pigtail:** 32 cm from the plug's tip (power-fix.md, step 4). It
  takes about 30 cm: 23.6 cm in plan from OUT to the plate under its plug,
  the climb over its bridges, the drop from the plug to the plate and the plug
  itself, and leaves 1 to 2 cm of slack to ease the plate back. How high the
  plug stands off the plate, 15 to 25 mm, depends on the standoffs, so if
  yours are measured, measure that too and adjust.

To fit it, with the plate outer face down on the bench: you're looking at its
inner face, the mirror image of what you see behind the case, so go by the
trigger board's window, the vents and the cable hole rather than by left and
right:
1. Press an M3 × 5 insert into each of the two bosses at the bottom of the
   plate, flush with the top of the boss.
2. Wire the regulator on the bench first ([power-fix.md](../../docs/power-fix.md),
   steps 2 to 5), with ferrules on its four wires, and lay it in the tray with
   its output terminals at the end marked `OUT`, the end nearer the trigger
   board. It should drop in onto its two ribs, between the walls and the
   tongues' ends, without forcing. If it has to be forced, or sits on a
   tongue, measure your regulator's board: the pocket is drawn 0.5 mm bigger
   all round than the first unit's, 63.5 × 27.25 mm (`pwr_reg_l`,
   `pwr_reg_w`).
3. Put a tie through each of the two grooves under the floor, round the tray
   and the board, and pull them snug.
4. Set the tray over the two bosses (it fits one way only) and screw it down
   with two M3 × 8 button-head screws, snug.
5. At each end, put a tie through the saddle's slot, round the saddle and the
   leads on it, its head on top of the leads, never on the side toward the
   rim, and pull it tight. Each lead should come straight out of its terminal
   onto the saddle, its ferrule clear of the tongue under it. If a lead has
   to bend up or down more than a millimetre to reach the saddle, your
   terminals' wire entries are not 2 mm over the board, as on the first unit,
   or your board is not 1.6 mm thick: measure them and set `pwr_reg_term_h`
   and `pwr_reg_pcb_t`.
6. Run the twisted 12 V pair from the trigger board through its four bridges,
   tying it at each: the one between the trigger board and the low vent; the
   one on the vent's far side, so the pair crosses the vent on the two, off
   the plate; the one up the plate from the tray's far end, past the tray's
   upper ear; and the one beside that end, round which it turns onto the
   saddle there. It runs above the tray, never across the regulator.
7. Run the pigtail from `OUT` through its four bridges: just past that end of
   the tray, beside the trigger board's mount; between the mount and the
   central vent; up beside where the Pi's USB ports will be, inboard of the
   speaker; and at that top corner of the Pi. Tie it at each, the third tie's
   head on the speaker's side, and leave the rest free for now, on the Pi's
   side of its curb.

When the plate goes on, hold it about 5 cm behind the case:
1. Plug the coax into the FlyCatcher, 1090 and 978 as marked
   ([the twin mount](#the-twin-mount-1090-and-978-mhz)), its free run down the
   right-hand side, between its curb and the speaker.
2. Plug the pigtail into the Pi, its plug's cable pointing at the plate, and
   lay its free run along the top of the Pi, between the Pi and its curb,
   with the ferrite on it about 5 cm from the plug.
3. With every plug in the Pi (the FlyCatcher's USB lead, and the display's
   USB and HDMI leads), check that the pigtail, and the tie at its third
   bridge, pass under the USB plugs without touching them, and that no
   angled USB or HDMI cable points down onto the pigtail or the ferrite. Keep
   the FlyCatcher's USB lead off the pigtail: on the first unit a disturbed
   USB plug has already dropped the receiver.
4. Ease the plate home. Each run's slack arches off the plate on its own side
   of its curb.

**To open the case again:** undo the eight screws, ease the plate back about
5 cm, unplug the pigtail and unscrew both SMA plugs, then lift the plate away.
The slack in the pigtail and the coax is what lets the plate come that far
before anything is unplugged.

**Measure on your own unit, before printing if you can:** where the
FlyCatcher's two SMA jacks are along its edge (then narrow `hat_sma_span` to
them: it gains the 12 V pair and the pigtail's plug real room), the standoffs
between the Pi and the FlyCatcher, and the thickness of the regulator's board
(`pwr_reg_pcb_t`). The regulator's size and its terminals were measured on
the first unit (2026-10-30); if yours differs, measure those too
(`pwr_reg_l`, `pwr_reg_w`, `pwr_reg_term_*`, `pwr_reg_overhang`).

`hat_envelope` is the box the checks keep everything on the plate out of, for
the Pi and its HAT: the Pi 5's 85 × 56 mm board on the display's 58 × 49
holes, long side across the case, its USB and Ethernet end on the left seen
from behind (the owner's unit, 2026-10-29), its ports standing about 3 mm
past that end and its USB-C and micro-HDMI sockets 1.2 mm past its top edge,
and a standard 65 × 56.5 mm HAT for the FlyCatcher, from the plate's inner face
to the shelf under the display. The plugs in the Pi's USB ports aren't in it:
they hang toward the plate with the ports, to somewhere about 11 to 20 mm off
it, depending on the standoffs, and the pigtail passes under them, 10.7 mm up
at most at its third bridge (step 3 above checks it). `sma_plug_zone` is where
the FlyCatcher's two SMA plugs can be: from its right-hand edge (seen from
behind) out to the speaker, and within 23 mm of the edge's middle, since a
jack can't stand over the HAT's mounting holes. `hat_stack` is the stack's
height, measured on the first unit (2026-10-29): the Pi, the FlyCatcher and
its switches stand 46 mm from the back of the display. Taken from the display
module's metal back, the reading that leaves the least room, the switches'
tops are 10.2 mm off the plate's inner face (15 mm if it was from the glass);
the design asserts that `shell_depth` leaves 2 mm or more, and
`hat_stack_clear` that nothing on the plate rises within 2 mm of them.

Checks that must come out empty: `tray_vs_plate`, `tray_holds_board` (the
regulator lies clear of the tray's walls, tongues and caps), `tray_screws_pass`,
`tray_screws_inside_plate` (nothing of a screw or an insert within 1.5 mm of
the outer face), `tray_inserts_surrounded` (1.5 mm of boss all round each
insert, its whole length), `tray_holes_blind` (1.5 mm of plate under each
hole), `tray_vs_shell`, `tray_vs_speakers`, `tray_vs_trigger` (the mount, the
stop, the board, the screws, the wires and the M2 screwdriver's way in),
`tray_off_strip`, `tray_clear_of_grilles` (no vent hole under the tray or its
bosses), `tray_clear_of_coax` (50 mm), `tray_vs_hat`, `tray_tie_slots_open`,
`tray_ferrules_clear` (the collars are clear of the tray and of the ties),
`tray_leads_straight`, `tray_ties_clear` (each saddle's tie, its head on top,
clears the plate and the shell), `tray_labels_on_tongues` (`OUT` and `IN`
stay on the tongues' tops), `tie_tunnels_open`, `tie_decks_whole` (each deck
1.0 mm thick over its tunnel's apex, right across it), `tie_tents_open`,
`tie_bridges_on_plate` (no hole under a bridge), `tie_bridges_clear` (each
bridge, with room for its cable and tie, clears the tray, the trigger board's
parts and the screwdriver's way, the Pi's box, the USB-C plug, the speakers,
the shell, the cable hole, the antenna mount's screws and the curbs),
`curbs_on_plate` (no hole under a curb), `curbs_clear`, `coupon_unchanged`,
`routes_power_20mm_from_coax` (every power lead, the pigtail's whole slack
strip and the tray, 20 mm or more from the coax and its slack strip, the
cable hole and the SMA plugs' zone, over the case's whole depth),
`routes_port_20mm_from_coax` (the coax and its strip 20 mm from the USB-C plug
and the pigtail's last run to it), `routes_leads_clear` and
`routes_coax_clear` (each route clear of everything else on the plate, the
curbs included) and `hat_stack_clear`. Their controls must find real
geometry: `tray_caps_on_bosses`, `tray_located` (moved 1.5 mm sideways, the
caps run into the bosses), `tray_one_way_round` (turned end for end, they
land on them), `tray_board_on_ribs`, `tray_screws_bite`,
`tray_insert_holes_open`, `tray_speaker_probe_works` (the tray at (−44, −50),
across, where one review proposed it, lands on the speaker),
`tray_strip_probe_works` (upright at (+29, −62), another of the review's
spots, it lands on the strip), `tray_grille_probe_works` (the low grille back
at (0, −68) is under it), `tray_coax_probe_works` (it is 131 mm from the cable
hole at its nearest), `tray_hat_probe_works` (25 mm further up it meets the
Pi's box), `tray_tie_probe_works`, `tray_ferrule_probe_works`,
`tray_leads_on_saddles`, `tray_tie_head_probe_works` (a saddle's tie with its
head toward the rim hits the plate's lip), `tray_labels_cut`,
`tie_tunnel_probe_works`, `tie_spans_short`, `tie_roofs_tented` (each
tunnel's roof is two slopes, not flat), `tie_zone_probe_works` (40 mm lower,
a coax bridge is in the Pi's box), `tie_bridges_present`,
`tray_bosses_present`, `curbs_present`, `curbs_probe_works` (the pigtail's
curb 15 mm lower runs into the Pi's box), `routes_20mm_probe_works` (the
pigtail carried on into its plug comes within 20 mm of the SMA plugs' zone:
the probe sees the one exception), `routes_pigtail_slack_probe_works`
(without its curb, the pigtail's slack, bowed as far as 12 mm of it lets it,
comes within 20 mm of the coax), `routes_coax_slack_probe_works` (without
theirs, the jumpers' slack 10 mm toward the Pi's USB-C plug comes within
20 mm of it), `routes_port_probe_works` (a straight plug, 20 mm long, would
be within 20 mm of the coax: the right-angle plug is what makes room),
`routes_leads_probe_works` (5 mm lower, the leads meet the tray and the
trigger board's mount), `routes_coax_probe_works` (tied at a bridge at
(−22, 52), right of the cable hole seen from behind, and aimed straight down,
the coax would run over the USB-C plug) and `hat_stack_probe_works`. The
design asserts the rest: each tie past a ferrule's collar and within 15 mm of
the board's end, the saddles' decks 1.5 mm or thicker and the bridges'
1.0 mm, the slots wide and tall enough for a 3.6 mm tie, the ears clear of
the grooves, the tongues 0.5 mm under the leads' ferrules and 1 mm or more
over the board's underside, `OUT` and `IN` inside the tongues, the curbs
2 mm or more above a cable lying beside them, the screws ending inside their
inserts with 3 mm of thread or more, and 2 mm or more under the HAT's
switches.

## The power fix: the charger plugs into the trigger board

Roadmap 5.7 ([#53](https://github.com/mferris/StratoScan/issues/53)) feeds
the Pi from a 12 V USB-C trigger board and a 5 V regulator
([docs/power-fix.md](../../docs/power-fix.md)). The charger plugs straight
into the trigger board, whose socket comes out through the back plate, so no
panel-mount extension is needed. Three small parts fit the boards.

**The socket goes through the plate** (since 2026-10-29). Until then the
socket's face sat at the plate's inner face, behind the whole 3 mm plate, so
a plug's moulding had to go through a 2 mm pocket and an 8 mm tall window in
a 1 mm web before the plug was home. A moulding a little too big, or a board
a little off-centre, and it never got there: the power cut out whenever the
cable moved. Now:

- **The board's front edge bears on the plate's inner face**, and its socket,
  which stands 2 mm past that edge, goes out through a window its own shape:
  the socket's 8.94 × 3.26 mm round-ended outline, 0.3 mm bigger all round
  (9.54 × 3.86 mm), since a printed hole comes out a little small. The window
  locates the socket, and the plate takes the pull of unplugging straight
  from the board's edge, on 1.27 mm of plate below the window.
- **The pocket in the outer face is 14 × 10 mm and 1.4 mm deep**, its floor
  0.4 mm behind the socket's face, so a moulding meets the socket and never
  the plate. The USB-C standard allows a moulding up to 12.35 × 6.5 mm, and
  real ones run bigger; this takes anything up to about 13.4 × 9.4 mm. The
  floor prints as a bridge over the pocket, and a bridge sags, so a floor
  level with the socket's face could stop a moulding just short of it again.
  That leaves 1.6 mm of web round the window, 60 % more than the old 1 mm.
- **The pocket's floor bridges in two steps** (since 2026-10-29). Without
  the steps, Bambu Studio started the floor with the window's two outlines
  in mid-air, held by nothing, and bridged up to them in short stubs held at
  one end, so whatever sagged hung into the pocket where a moulding's face
  lands. Now the first layer over the pocket is open in a slot as tall as the
  window and as wide as the pocket, so every line of it spans the pocket from
  wall to wall; the second is open in the window's rectangle, so it bridges
  only the slot's ends, 3.86 mm; and the window's round ends start on the
  third. Look into the pocket and you see the two steps: they are meant to be
  there. Slice with **counterbore hole bridging off**, Bambu Studio's
  default; that option does worse with this shape.
- **The plate says which charger it needs** (since 2026-10-29): `USB-C PD`
  over `12V 27W`, engraved 0.6 mm deep in the outer face above the pocket,
  in bold capitals 6 mm tall that read the right way from behind the case
  (5 mm until 2026-10-31, when every stroke was fattened to 1 mm or more so
  the label prints whole in a second colour: [lettering in two
  colours](#lettering-in-two-colours-print-settings)).
  The trigger board asks the charger for 12 V, and one without it, such as
  a 5 V-only Pi-style supply, never starts the radar. The plate prints outer
  face down, so the letters are its first three layers and need no support.
  They stand 1.5 mm above the coupon's 36 × 18 mm patch, so `usbc_gauge` is
  unchanged.
- <a id="the-label-in-a-second-colour"></a>**The label in a second colour**
  (since 2026-10-31), the way the antenna cover's lettering is: print
  `back_plate_twotone.3mf` instead of `back_plate.stl`. It is one object, the
  plate on filament 1 and the lettering, `back_plate_text`, on filament 2;
  give filament 2 a colour that stands out from the plate's. Supports off,
  outer face down, as the plate always prints. The lettering fills the
  engraving exactly, so the two colours change only in the first three
  layers, 0.6 mm; above that the plate is all filament 1. Bambu Studio on an
  X1C (0.20 mm, ASA, prime tower on) gives about 2 h 40 min, against 2 h 33
  min for the one-colour plate. Its settings and its coupon are in
  [lettering in two colours](#lettering-in-two-colours-print-settings). It swaps filament at the start of each of
  the three lettering layers and once more, back to filament 1, at the
  fourth; its own summary counts three changes, not the first load. The
  lettering itself is under 0.1 g, and filament 2 comes to about 1.5 g in
  all, the rest purge and tower, more or less with the colours chosen.
  The project keeps the plate in its design's frame, with no placement of
  its own, as the 3MFs Bambu Studio's desktop app loads with their
  filaments do; the app puts it on the bed as it opens it (on the command
  line, slice with `--arrange 1`). The checks
  `plate_text_vs_plate`, `plate_text_fills_engraving` (with its control
  `plate_text_gap_probe_works`) and `plate_text_on_face` prove the lettering
  meets the plate face to face, no overlap and no gap. Since 2026-10-31 the
  label is larger, so `back_plate.stl` is too: a plate printed before then
  fits and works the same, with the old, smaller label.
- **`power_trigger_mount`** is a sleeve round the board, 0.2 mm clear of it
  either side, its flat face on the plate's inner face, level with the
  board's front edge: no flange, since the plate is the front stop now. The
  board lies on the sleeve's floor, and two crush ribs along its roof, over
  the socket's flat top for the first 4 mm, press the socket down, so the
  board cannot rock (since 2026-10-29: until then it had 0.4 mm of room up
  and down, enough to tip about 2.3° about the window's edge, and each
  jiggle of the cable worked the stop's ribs). Two **M3 × 8
  button-head** screws come from inside the case, through its two ears and
  into **M3 × 3 heat-set inserts** in the plate, 24 mm apart, so nothing of
  them is in the outer face, and each clamps its ear, 5.5 mm of plastic. They
  used to come from outside, 16.5 mm apart, their heads in the old pocket;
  with the pocket 1.4 mm deep and wide enough for a moulding, the heads would
  have stood in the moulding's way. The ear nearer the speaker is under the
  speaker's corner, so use button heads, not socket caps, and M3 × 8 only: an
  M3 × 10 would come out of the plate's outer face.
- **`power_trigger_stop`** slides into the mount behind the board, and two
  **M2 × 8** screws through the mount's side walls lock it there. Its two
  crush ribs press the board's back edge forward, so the board is held
  between the plate and the stop with no play: each screw lands on a
  countersink in the stop and draws it the last 0.3 mm forward, squeezing the
  ribs onto the board, before it threads in. The screws thread through the
  walls as well as into the stop, so they have no slack to give, and the stop
  is a T that only goes in the right way up. It replaced a 1.75 mm filament
  pin, which let the board move.
- **The stop only goes in the right way round** (since 2026-10-29). Back to
  front it used to go in as easily: its two pilots sit a pitch apart about
  the middle of its length, and their countersinks change sides as it turns,
  so both screws found one and drew the stop 0.5 mm back off the board,
  leaving the board loose. Now a key, a 1 mm 45° ridge along the bottom of
  one side at its back end, runs in a slot in the mount's wall. The right way
  round the key goes in last, into its slot; back to front it leads, on the
  side with no slot, and stops at the end of the mount before the stop is in,
  a long way short of where a screw could start in it. The ridge prints on
  top, its slope facing the bed, so it needs no support.
- **The ribs print short.** The stop's ribs, and the roof's, are drawn 0.1 mm
  taller than the squeeze needs: in Bambu Studio's slice a printed rib's tip
  comes out about 0.09 mm short, rounded off by the nozzle's line, so the
  stop's ribs, 0.8 mm until 2026-10-29, squeezed the board by only 0.21 mm,
  not 0.3. They are 0.9 mm now, and print 0.81.

To fit it (the plate lying outer face down):

1. Press an M3 × 3 insert into each of the two holes beside the window, from
   the inner face, with the outer face on a flat board, until it stops on the
   board: it is as long as the plate is thick, so it ends flush with both
   faces. Each ear's hole is chamfered underneath, room for any plastic the
   insert raises.
2. Solder the 12 V pair to the trigger board.
3. Set the mount on the plate's inner face over the window, ears on the
   inserts, and put in the two M3 × 8 screws from inside, a turn short of
   tight.
4. Drop the board into the mount from the back, socket first, the socket's
   side toward the roof's two ribs, the wires trailing out of the back. For
   the last 6 mm or so the socket goes under the ribs: push the board's back
   edge firmly, with a small flat screwdriver below the wires, until its
   socket goes into the window and its front edge rests on the plate.
   Tighten the two M3 screws.
5. Slide the stop in behind the board, ribs first and its ridge toward the
   slot in the mount's wall, until the ribs touch the board. It only goes in
   that way.
6. Drive the two M2 × 8 screws through the mount's side walls into the stop,
   snug and no harder. They draw it the last 0.3 mm onto the board as they
   seat. Past that, each strips the thread it cut in the 2.2 mm wall, and
   the slack comes back.

Print `usbc_gauge` first and fit the mount to it the same way: the
charger's plug must click fully home, its moulding down in the pocket. Go by
the click: a plug that stops without one is not home, however close it looks.
The coupon is the plate's own geometry round the window, bridge steps and
all, so a plug that seats there seats in the plate. If it won't click home:

1. Trim any strand of plastic on the pocket's floor and round the window's
   edge with a sharp knife. Leave the two steps in the floor: they are meant
   to be there.
2. Check that the board's front edge is down on the plate. From outside, the
   socket's face should stand 0.4 mm proud of the pocket's floor, not level
   with it or below it. If it doesn't, undo the stop's two screws and slide
   it out, push the board's back edge until its front edge is on the plate,
   and fit a fresh stop with steps 5 and 6. Not the same one: its ribs were
   squeezed with the board out of place, and they don't spring back, so it
   would leave the board loose by however far it was out. A plug can then
   push the board back instead of clicking home, so a test with that stop
   proves nothing.
3. Try another cable, one with a slimmer moulding round its plug.

If it still won't, the plate needs to change, and the coupon is reprinted
first. A moulding too big for the 14 × 10 mm pocket needs `usbc_recess_w`
and `usbc_recess_h` bigger: `usbc_recess_w` can go to 16.8 mm before the
inserts lose their 1.6 mm of plate. A moulding that goes into the pocket
but stops on its floor needs `usbc_seat_margin` up from 0.4 to 0.6 mm, a
pocket one layer deeper. That is as deep as it goes: the window's wall above
the floor's two steps is then 1 mm, and the plate the board's front edge
bears on 1.4 mm instead of 1.6, the least the design allows for each. The
asserts in the design hold all three limits. `checks.scad` restates the
pocket's size, so change it there too (`usbc_recess_w`, or `usbc_recess_d`,
1.6 for the deeper pocket) before running the checks; they pass at either
limit.

The trial fit spends some parts. Its two inserts stay in the coupon, and the
stop's crush ribs, once squeezed, don't spring back, so a stop is good for
one fitting: whenever one comes out, a fresh one goes in. So the plate needs
two more M3 × 3 inserts and a fresh stop, never the coupon's; the mount, the
board and the screws move across. Undo the stop's screws and slide it out,
then lift the mount off the coupon with the board still in it, so the roof's
ribs keep their hold on the socket. Fit it to the plate with steps 1 to 6
and the fresh stop; in step 4 the board is already in, so just push its back
edge until its front edge is on the plate. The third stop is the spare, for
a board that has to be re-seated.

**`power_regulator_tray`** holds the regulator at its own place on the plate,
screwed down: see [The regulator's place](#the-regulators-place), above. The
70 × 13.5 mm strip across the window stays clear of it: the trigger board's
mount stands in the middle of the strip, and the rest is the M2 screwdriver's
way in, 25 mm out either side along the screws, so the stop can be locked or
freed with the tray in place (since 2026-10-29; it was a 33 × 13.5 mm patch,
the mount alone). The pigtail crosses the strip at its end nearer the middle
of the plate, lying on the plate under the screwdriver's way, 15 mm below
it, and one of its tie bridges stands at the strip's edge there: the checks
keep both clear of the mount, its screws and the way itself.

The trigger board's size was measured: 19.19 × 10.72 × 4.83 mm, from its
socket's face to its back edge, across it, and from its underside to the top
of the socket. Its socket stands about 2 mm past the board's front edge
(`pwr_trig_proud`). All three parts print in minutes and need no supports:
print the mount flat face down, the stop on its wide face, and the plate and
the coupon outer face down, supports off (with supports on, the slicer fills
the pocket).

Checks that must come out empty: `power_mount_vs_plate`, `power_board_held`,
`power_edge_on_plate` (the plate is solid in front of the board's edge below
the window, from its inner face to the pocket's floor, at any pocket depth
the design allows), `power_socket_clears_window` (the socket, 0.25 mm
bigger all round, clears the window), `usbc_bridge_steps_open` (the first
layer over the pocket is open from wall to wall, and the second across the
window's rectangle), `power_plug_reaches` and `power_moulding_reaches`
(an 8.4 × 2.6 mm plug shell and a 13.4 × 9.4 mm moulding reach the socket's
face), `power_m3_pass`, `power_m3_inside_plate` (nothing of the screws or
inserts comes out of the outer face), `usbc_inserts_surrounded`,
`power_mount_vs_shell`, `power_mount_vs_speakers`,
`power_m3_clear_of_speakers`, `power_stop_fits_tube`,
`power_stop_clear_of_board`, `power_m2_holes_line_up`,
`power_m2_clear_of_board`, `power_m2_threads_held`, `power_wires_out`,
`power_stop_vs_shell`, `power_stop_vs_speakers`, `power_parts_vs_stand`,
`power_parts_in_patch` (everything at the window, and the M2 screwdriver's
way in either side, stays in its 70 × 13.5 mm strip),
`power_m2_drivers_clear` (that way in, 6 mm across, meets nothing), and
`usbc_label_cut`, `usbc_label_inside_plate`, `usbc_label_off_gauge` and
`usbc_label_clear_of_holes` (the engraving is cut, lies inside the plate and
no more than 1 mm deep, keeps off the coupon's patch, and stays 1.5 mm or
more from every other hole: the pocket, the window, the inserts, the vents,
the antenna holes and the screws). `power_ribs_squeeze_board` and
`power_top_ribs_squeeze_socket` must find only a sliver: the stop's ribs in
the board's edge, and the roof's in the socket's top.
`power_board_cannot_rock` must find more than a film: the board tipped 1°
about the window's edge runs into the roof's ribs (0.16 mm³; without them,
0.003). Their positive controls: `power_mount_on_plate`,
`power_plate_holds_board`, `power_board_on_floor` (the board moved 0.1 mm
down meets the tube's floor), `power_edge_strip_works`,
`power_window_is_close`, `usbc_bridge_steps_held` (from the second layer up
the slot's ends are solid), `power_plug_probe_works`,
`power_moulding_probe_works` (a moulding 1 mm bigger than the pocket stops on
the outer face), `power_m3_bite`, `usbc_insert_holes_open`,
`power_speaker_drawing_works`, `power_stop_takes_push`,
`power_m2_threads_bite`, `power_wire_probe_works`, `power_m2_drivers_reach`
(the screwdriver's way in, begun 3 mm further in, meets the screws' heads),
`usbc_label_present` (the letters, 80 mm³) and `usbc_label_probe_works` (the
clearance probe, moved 12 mm down over the pocket, finds it).

`power_stop_back_to_front_blocked`, `power_stop_upside_down_blocked` and
`power_stop_end_over_end_blocked` must run into the mount: the stop the
wrong way round, turned about its pilots so they stay in line with the
walls', 4.4 mm short of home, the furthest out a screw could start in it,
and pushed over by its play to whichever side frees it most. Back to front
its key runs 0.7 mm into the wall (0.7 mm³); upside down, or end over end,
its T does (about 2 mm³). Their controls must meet nothing at all, under
0.01 mm³ rather than the 1 mm³ the other empty checks allow:
`power_stop_slides_home` (the stop, slid in the right way round from outside
the mount all the way home, 0.25 mm at a time) and
`power_stop_key_is_what_blocks` (back to front without its key, posed as
above). Where the key runs into the wall it is only about 0.36 mm² across,
so under 1 mm³ a slot begun 2.5 mm late passed, with the stop jammed
2.35 mm short of home and its ribs off the board (until 2026-10-29).
`power_stop_jam_probe_works` shows the limit is tight enough: with the slot
begun 0.5 mm late, the stop jams 0.35 mm short, and the sweep finds it
(0.13 mm³).

### The stand holds the charger's cable

Nothing held the cable, so its weight and every tug levered the plug in the
trigger board's socket, and a moving cable is what set off the power cuts.
The plug points straight back from the window, 18° down; its end is about
69 mm above the desk, and the cable drops from it onto the back of the
plinth. A clip there takes it (2026-10-29), directly under the plug at
x = 60:

- **A groove along the plinth's top**, from y 52 to the back edge, round and
  0.2 mm under the cable, so it grips, with a mouth 0.7 mm narrower than the
  cable, so it snaps in and stays. The cable lies just under the top face.
- **Over the back edge** the groove turns down round a 4 mm radius, so the
  cable bends round a curve rather than over an edge, still behind the mouth.
- **Down the back face** a channel as wide as the groove, open to the back,
  and a notch as wide through both ridges, so the cable hangs flat to the
  back and leaves it wherever it bends away along the desk.

To fit the cable, plug it in with the case in the stand and leave a slack
loop of 40-50 mm between the plug and the clip, so a pull on the cable moves
the stand before it reaches the plug. Press the cable into the groove from
its front end back, round the edge, and let it hang down the channel. **Take
the cable out of the clip before lifting the case out of the stand:** the
loop is too short for the case to come out with the cable still in it.

The clip is sized for a cable about 4 mm thick (`stand_cable_d`). Measure
yours before printing the stand: a thinner one won't grip, and a thicker one
won't go in. Set `stand_cable_d` to it in four places: this design, the
kitten's design, and the `checks.scad` in both folders (the core test holds
all four to one cable, and fails if any differs). Or print `test_clip` and
try the cable in that first.
The clip needs no support.

**The ridges' lips now print unsupported, and that is the slicer's choice,
not the clip's (2026-10-30).** Sliced in Bambu Studio 2.08 (X1C 0.4 mm,
0.20 mm Standard, Bambu ASA, tree supports at 30°), the stand's support went
from 8.2 to 1.3 cm³, all of what is left under the arms, and the print from
5.9 to 5.1 h. Almost all of the saving, 7 cm³, is support the slicer used to
put under the two ridges' 0.8 mm lips and, once the notch broke the ridges,
no longer does. The lips' shape is unchanged. At each lip the slicer prints a
step of about 0.9 mm out from the slope below as bridge and overhang wall,
with nothing under it. The same lip prints clean on the case's rings, but no
print of the stand's has been checked yet. Before printing the whole stand,
print `test_clip` (18 minutes): it has 24 mm of both ridges and their lips
beside the notch. Look at the lips' undersides. If they come out rough,
accept it, or paint support under them in the slicer for the stand.

`stand_clip_takes_cable` must come out empty: a cable 3.6 mm across passes
all the way along the groove, round the turn and down the back with nothing
in its way (the stand as it was finds 317 mm³). `stand_clip_grips` and
`stand_clip_snaps` are its controls: a 4 mm cable is squeezed along the top
and round the turn (25 mm³; under 1 with no grip), and lifted 1 mm out of the
groove it still meets the mouth's lips (13 mm³; nothing with a mouth as wide
as the cable).

## Heat-set inserts

Every screw that gets undone goes into a brass M3 heat-set insert. The holes are sized for the Kadrick M2–M5 kit: its M3 inserts are 4.5 mm across the knurl and 3.9 mm at the lead-in. Every insert hole is **4.0 mm**, so the lead-in drops in square and the knurl melts 0.25 mm a side into the plastic. (They were 4.2, which left a 4.5 mm insert only 0.15 mm of bite.)

| Where | Count | Insert | Screw | Notes |
|---|---|---|---|---|
| Front posts in the shell (front trim and retainer screw into these) | 8 | M3 × 5 | M3 × 14 | Pressed from the front, flush with the shelf the retainer sits on |
| Back posts in the shell (back plate screws into these) | 8 | M3 × 6 | M3 × 8 | Pressed from the back face, flush |
| Antenna mount flange | 3 | M3 × 5 | M3 × 8 | The pocket is in the mount; the screws come from inside the case, through the back plate |
| Back plate, beside the USB-C window (the trigger board's mount screws into these) | 2 | M3 × 3 | M3 × 8 button head | Pressed from the inner face with the outer face on a flat board, so each ends flush with both faces; the screws come from inside the case, through the mount's ears (since 2026-10-29) |
| Back plate, the regulator tray's two bosses | 2 | M3 × 5 | M3 × 8 button head | Pressed from the top of each boss, flush with it; the holes stop 2 mm short of the outer face. The screws go down through the tray's two caps (since 2026-10-29) |
| `usbc_gauge`, for the trial fit before the plate | 2 | M3 × 3 | the mount's own two M3 × 8 | Pressed the same way. They stay in the coupon, so the plate needs two of its own |
| Twin antenna mount's cover | 5 | M2 × 3 | M2 × 6 | 3.0 mm holes in the cover seat (for a 3.2 mm knurl; 3.2 if the kit's inserts are the 3.5 mm kind — measure them). The cover's holes are counterbored 4.4 mm × 1.5 mm, so the cap heads stand only 0.5 mm proud (since 2026-10-10) |
| Speaker bosses (optional) | 8 | M2 × 3 | M2 × 6 | The 2.6 mm pilot takes the speaker's self-tapping screws; drill it to 3.0 for an M2 insert |

**The front posts are new.** They used to be only 2 mm tall: an insert sat in 2 mm of plastic with open air under it and the wall on one side only (measured: a third of the ring round it was solid). Now each post hangs 8 mm below the shelf, merged into the wall, with a 45° cone under it. The cone is centred 2 mm inside the bore, so it meets the wall only from z 46.5 up: its lowest 1.5 mm, from its 1 mm tip at z 45, is a small island in mid-air, and the slicer grows one small tree from the bed to each of the eight tips, about 0.5 cm³ of support a shell in all (checked 2026-10-30). Harmless so far; [For a later shell print](#for-a-later-shell-print) has the change that would remove it. The holes are cut after the whole shell is unioned, so the speaker brackets at 0° and 180° can't fill them.

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

**Cables:** two SMA male to SMA female bulkhead jumpers, RG316, about 40 cm (16") (SMA, not RP-SMA): a bulkhead end has a threaded barrel with a nut and washer, which is what holds the antenna. 40 cm since 2026-10-29: inside the case each takes 18 to 21 cm, its route down the right-hand side and the slack to ease the plate back, and a 30 cm one gives only about 18 cm once the mount has its share. The small right-angle pigtails in the antenna bundle are MCX, for Nooelec's USB sticks, and aren't used.

**Whip or external antenna, the user's choice:** each tower's jack is an ordinary SMA socket on the outside of the case. Screw on the Nooelec whip, or the coax from an antenna mounted outside or in a window; nothing inside changes. An outdoor antenna with an N-type connector needs an N-male to SMA-male cable. Leave the FlyCatcher's bias-tee switch off unless the outdoor antenna has a powered amplifier that needs it.

**Two parts since 2026-10-07: a body and a flat cover.** The first version ran each cable through an internal tunnel and could not be assembled: both ends of a jumper are rigid metal about 9 mm across and 15–20 mm long, and that cannot turn a right-angle corner inside an 11 mm bore. The checks had only ever passed a straight probe down each leg. Now the crossbar and towers have an open channel on the side away from the case, closed by a cover on five M2 screws, so everything is laid in and nothing is threaded round a corner. The arm's bore runs straight on through the crossbar and out of the channel floor; it is 13 mm, and so is the plate's hole, because both plugs share it and the second has to pass the first cable. Under each tower's panel is a slot that is a close fit on the jack's hex body, so the jack cannot turn while its nut is tightened. The panel is 2 mm: the bulkhead's thread is 10 mm from its shoulder, and 2 of panel, 0.6 of washer and 2.5 of nut leave 4.9 mm for the whip's own coupling nut.

**The plate's cable hole grew from 11 to 13 mm the same day.** A back plate printed before that — including one printed from the y=81 plate committed earlier on 2026-10-07 — will not pass the second plug and must be reprinted.

**Two styles, by the jumper's bulkhead body.** Measure the body behind the shoulder across its flats: the jumpers on hand come as 8 mm and as 11 mm hexes, and `antenna_mount_twin_8` / `antenna_mount_twin_11` (with their covers) are cut for each — slot = flats + 0.8, a pocket the hex's size under the panel, the tower, bar and cover sized to suit. Both take the same 6.35 mm barrel. Any other size is one number: `antenna_mount_twin([9, 9])`, or a mixed pair. A round body has nothing for the slot to hold; the jack is then held with thin pliers through the open channel while its nut goes on, before the cover.

**Which side is which:** the cover carries each tower's frequency, engraved under it and read from behind the case — `1090` on the left, `978` on the right (`ant_twin_labels`; `ant_twin_label_on = false` for a plain cover). The 1090 whip is the shorter one.

**Printing:** body flange-down with tree supports (Bambu Support for ABS interface), as the other mounts print. The towers and bar have 6 mm corners and rounded edges, like the cases, rather than a box. The channel, slots, insert holes and jack holes all face up or sideways and need nothing; the towers' outboard ends and the bar's top edge start in mid-air, so the supports go on the face toward the case, where nobody sees the scars. Cover flat, counterbored face down, no support. ASA on a clean Engineering plate, no glue.

**Fitting the cables** (cover off, body held channel-up — or the flange hanging over the bench edge, since the plugs come out of its underside). First mark the two jumpers at both ends, so they can't be swapped later: one band of heat-shrink on the 1090 one, two on the 978 one (2026-10-29).
1. Push each plug end into the bore at the centre of the channel, straight down the arm and out through the flange — the second plug goes in beside the first cable with a wiggle. Pull each cable through beyond the bore's mouth as far as it goes once the mount has its share, about 28 cm of a 40 cm jumper (it was 10 cm until 2026-10-29). Inside the case the route takes 15 to 19 cm to the jack, depending on how low the jack is on the FlyCatcher's edge, and 2 to 3 cm more is the slack that lets the plate come back 5 cm before the plugs are undone; the rest lies in the jumpers' free run (step 5). A 30 cm jumper gives only about 18 cm: keep one only if, with the plate held 5 cm back, its plug still reaches its jack.
2. Lay one cable along the channel to each tower. Hold the jack's hex body with the barrel pointing up its tower and slide it sideways into the open slot until it stops.
3. Push the jack up with a fingertip through the open channel: the top of the slot is a closed pocket the hex's size, and the barrel comes through the panel when the body is in it. Washer and nut on from the top, finger tight, then a quarter turn with an 8 mm (5/16") spanner — the pocket holds the jack, so nothing inside has to be held. Don't crank it; the panel is 2 mm of ASA. Check the nuts again after a week; ASA relaxes a little.
   Set each whip so its hinge folds towards or away from the wall, not towards the other whip: that's the direction the mount is weakest, so the hinge gives before the panel does, and a folded whip then clears the other tower.
4. Tidy the cables into the channel and fit the cover: five M2 × 6 into the M2 inserts.

**Lettering in a second colour.** Open the cover's `_twotone.3mf` rather than its STL, and see [lettering in two colours](#lettering-in-two-colours-print-settings) for its settings and its test coupon. Since 2026-10-31 the numbers are 7 mm and MHz 5.6 mm, fattened so every stroke is 1 mm or more; MHz's strokes were 0.45 mm. The lettering is many separate letters, and a slicer splits a multi-lump STL into one part per letter, so picking a colour for "the text" would colour one letter; the project file already has the cover on filament 1 and every letter on filament 2. Change either in the slicer. The cover prints outer face down, so the lettering is its first 0.6 mm, three 0.2 mm layers: a change at the start of each, and one back to filament 1 above them, nothing after. The plain STL still prints the engraved, one-colour cover.
5. Pass both plugs through the plate's 13 mm hole, bolt the flange on from inside the plate with the three M3 × 8, plug 1090 and 978 into the FlyCatcher, and screw the whips on (the 1090 whip is the shorter one). Inside, tie both jumpers together at the two bridges that lead from the cable hole to the right and down the right-hand side, seen from behind, with 150 × 3.6 mm cable ties. Below the second bridge they run free down the right-hand side, between their curb and the speaker, to the FlyCatcher: fold any spare length back on itself just below the second bridge and take it into that bridge's tie, so only the planned slack runs on to the SMA plugs, on the speaker's side of the curb, never across it. Never leave the spare as a loose loop: the plate stands nearly upright, and a loop that sags below the SMA plugs comes within 20 mm of the 12 V pair at the lower right (since 2026-10-29; [the regulator's place](#the-regulators-place)). That keeps them 20 mm or more from the regulator's leads, which keep to the lower half and the left, and from the Pi's USB-C plug. For an outdoor antenna, screw its coax onto the same barrel instead, and give the coax its own strain relief within a few centimetres of the tower.

To replace a cable: back plate off, cover off, nut off, slide the jack out of its slot, pull the plug back up through the bore. The mount stays bolted to the plate.

**Checks:**
- `twin_bore_straight`: a plug beside a cable (12 mm) passes straight down the 13 mm bore from the flange face to below the crossbar.
- `twin_slot_takes_jack`: an 8 mm-across-flats hex body stands in each slot under its panel.
- `twin_cover_fits`: the cover sits in its seat without touching the body; `twin_cover_seats` (control) finds the body when the cover is pushed 2 mm in. `twin_channel_open` and `twin_cover_screws_open` (controls) find a rod along the channel and rods through the cover's holes whole, and `twin_channel_probe_clear` and `twin_screw_probes_clear` are their complements: the same rods meet no body at all.
- `top_screw_clear_of_twin`: the plate's top screw and a hex key clear the mount.
- `twin_antennas_clear_case`: both whips, swept 220 mm up, miss the case (and the kitten's ears); `twin_antennas_probe_works` (control): the same envelopes moved 60 mm down the axis and 40 mm toward the case do hit it.
- `twin_vs_plate`, `twin_vs_stand`: no collisions with the back plate or the stand.
- `twin_panels_present`, `twin_holes_open`: positive controls; the panels are there and the jack holes are open.
- `twin_cover_text_room`, `twin_cover_text_room_11`: the lettering keeps 1 mm inside the cover's edge and 1 mm clear of the screws' counterbores (since 2026-10-31, when it grew); `twin_cover_text_room_probe_works` (control): moved 8 mm down the cover, it runs off the edge.

## Checks

`sh run-checks.sh`. The script keeps these lists: targets that must come
out with no real volume (an interference, or a probe that should pass
through air); squeezes, which must find a sliver and no more (the power fix's
crush ribs in its board); contacts, which must find more than a film (the
power fix's board, tipped, meeting its ribs); blocks, which must run into
the part they meet (the power fix's stop, the wrong way round, in its
mount); clears, which must meet nothing at all, not just under 1 mm³ (the
same stop slid home, where a jam is only a sliver), and a control for them
that must not; positive controls that must
find geometry (the holes a probe should find open, the paired "same probe,
wrong place" controls such as `vents_were_under_mount`,
`top_screw_was_under_mount` and `twin_antennas_probe_works`); and `canary`,
which proves the modules are being found at all — without it a typo in the
`use <>` path makes every other check pass against nothing.

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
