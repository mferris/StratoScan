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
| `stand` | desk cradle — two ring-arc arms on a plinth with two ridges all the way round, 4mm proud, their undersides sloped at 45° to a small lip like the case's rings, so they print without support (the old 1mm strips printed rough unsupported, and square 4mm ridges needed supports all round) |
| `back_plate` | removable back — locating lip, both vent grilles, the trigger board's USB-C window with a pocket for the plug's moulding and two insert holes for its mount, the charger it needs engraved above it, the antenna mount's bolt holes and cable hole |
| `antenna_mount` | bolt-on arm carrying the antenna socket (identical to the kitten's) |
| `antenna_mount_sma` | alternative mount: same flange, arm and counter-tilt, ending in a panel-mount SMA jack instead of a socket cut for one antenna's base |
| `antenna_mount_twin_8`, `antenna_mount_twin_11` | **the one to print for the FlyCatcher:** same flange and three bolts, ending in a crossbar with two SMA jacks 80 mm apart, for the 1090 and 978 MHz whips; counter-tilted so both stand vertical with their hinges straight. Two styles, for jumpers whose bulkhead body is an 8 mm hex or an 11 mm hex; two parts each, this body and the cover below (`antenna_mount_twin` is whichever `ant_twin_jack_af` names) |
| `antenna_mount_twin_cover_8`, `antenna_mount_twin_cover_11` | the 3 mm cover that closes the twin body's cable channel, on five M2 screws, with each side's frequency engraved in it (`twin_assembled` and `twin_assembled_11` show both parts on the plate, for pictures only) |
| `antenna_mount_twin_cover_8_twotone.3mf`, `antenna_mount_twin_cover_11_twotone.3mf` | the same covers with the frequencies in a second colour: one object, the cover on filament 1 and the lettering (`antenna_mount_twin_cover_text_8` / `_11`) on filament 2. Built by `make-cover-3mf.py` from binary STL exports |
| `usbc_gauge` | test coupon: a 36 × 18 mm piece of the back plate round the USB-C window, its window, pocket and insert holes exactly the plate's, so the charger's plug can be tried in the trigger board before a whole plate is printed (about ten minutes) |
| `power_trigger_mount` | the power fix's 12 V trigger board's mount: a sleeve round the board, two crush ribs in its roof holding the board down, on two M3 screws into inserts in the plate, with the board's socket through the plate's USB-C window, so the charger plugs straight into it ([below](#the-power-fix-the-charger-plugs-into-the-trigger-board)) |
| `power_trigger_stop` | the block behind the trigger board in its mount, locked by two M2 screws through the mount's walls, so the board has no play; keyed, so it goes in only the right way round. Print two: a trial fit on `usbc_gauge` spends one's crush ribs |
| `power_regulator_tray` | a tray for the power fix's 5 V regulator, stuck to the plate's inner face |

Three extra targets, `test_antenna`, `test_speaker` and `test_rings`, clip
the real shell geometry to a small piece so a test prints in minutes instead
of hours. `test_rings` is a 40° slice of both rings, for trying a new material
on the rings' slope and lip.

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
y=+68 to y=−68. The antenna mount's flange is a 40mm disc centred at y=88 (y=81 since 2026-10-07, see below), so
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
  in bold capitals 5 mm tall that read the right way from behind the case.
  The trigger board asks the charger for 12 V, and one without it, such as
  a 5 V-only Pi-style supply, never starts the radar. The plate prints outer
  face down, so the letters are its first three layers and need no support.
  They stand 1.5 mm above the coupon's 36 × 18 mm patch, so `usbc_gauge` is
  unchanged.
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
   with it or below it. If it doesn't, undo the stop's two screws, push the
   board's back edge until its front edge is on the plate, and screw the stop
   back.
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
stop's crush ribs, once squeezed, don't spring back. So the plate needs two
more M3 × 3 inserts and a second stop; the mount, the board and the screws
move across. Undo the stop's screws and slide it out, then lift the mount
off the coupon with the board still in it, so the roof's ribs keep their
hold on the socket. Fit it to the plate with steps 1 to 6 and the new stop;
in step 4 the board is already in, so just push its back edge until its
front edge is on the plate.

**`power_regulator_tray`** holds the regulator (63 × 27 mm, and 12.3 mm from
its underside to the top of its tallest capacitor, so about 16 mm off the
plate in the tray). Both ends stay open for its terminals, input jack and
USB socket. Stick it to the plate's inner face with VHB tape, away from the
receiver and its antenna leads, and where the pigtail reaches the Pi's power
port; keep it off the 70 × 13.5 mm strip across the window. The trigger
board's mount stands in the middle of the strip, and the rest is the M2
screwdriver's way in, 25 mm out either side along the screws, so the stop
can be locked or freed with the tray in place (since 2026-10-29; it was a
33 × 13.5 mm patch, the mount alone). Two grooves under its floor take an
optional cable tie round the board.

The trigger board's size was measured: 19.19 × 10.72 × 4.83 mm, from its
socket's face to its back edge, across it, and from its underside to the top
of the socket. Its socket stands about 2 mm past the board's front edge
(`pwr_trig_proud`). All three parts print in minutes and need no supports:
print the mount flat face down, the stop on its wide face, and the plate and
the coupon outer face down.

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
`power_m2_drivers_clear` (that way in, 6 mm across, meets nothing),
`power_stop_slides_home` (the stop, slid in the right way round from
outside the mount all the way home, meets nothing),
`power_stop_key_is_what_blocks` (back to front without its key, posed as
below, it meets nothing either), and `usbc_label_cut`,
`usbc_label_inside_plate`, `usbc_label_off_gauge` and
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
its T does (about 2 mm³). `power_stop_slides_home` and
`power_stop_key_is_what_blocks`, above, are their controls.

## Heat-set inserts

Every screw that gets undone goes into a brass M3 heat-set insert. The holes are sized for the Kadrick M2–M5 kit: its M3 inserts are 4.5 mm across the knurl and 3.9 mm at the lead-in. Every insert hole is **4.0 mm**, so the lead-in drops in square and the knurl melts 0.25 mm a side into the plastic. (They were 4.2, which left a 4.5 mm insert only 0.15 mm of bite.)

| Where | Count | Insert | Screw | Notes |
|---|---|---|---|---|
| Front posts in the shell (front trim and retainer screw into these) | 8 | M3 × 5 | M3 × 14 | Pressed from the front, flush with the shelf the retainer sits on |
| Back posts in the shell (back plate screws into these) | 8 | M3 × 6 | M3 × 8 | Pressed from the back face, flush |
| Antenna mount flange | 3 | M3 × 5 | M3 × 8 | The pocket is in the mount; the screws come from inside the case, through the back plate |
| Back plate, beside the USB-C window (the trigger board's mount screws into these) | 2 | M3 × 3 | M3 × 8 button head | Pressed from the inner face with the outer face on a flat board, so each ends flush with both faces; the screws come from inside the case, through the mount's ears (since 2026-10-29) |
| `usbc_gauge`, for the trial fit before the plate | 2 | M3 × 3 | the mount's own two M3 × 8 | Pressed the same way. They stay in the coupon, so the plate needs two of its own |
| Twin antenna mount's cover | 5 | M2 × 3 | M2 × 6 | 3.0 mm holes in the cover seat (for a 3.2 mm knurl; 3.2 if the kit's inserts are the 3.5 mm kind — measure them). The cover's holes are counterbored 4.4 mm × 1.5 mm, so the cap heads stand only 0.5 mm proud (since 2026-10-10) |
| Speaker bosses (optional) | 8 | M2 × 3 | M2 × 6 | The 2.6 mm pilot takes the speaker's self-tapping screws; drill it to 3.0 for an M2 insert |

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

**Cables:** two SMA male to SMA female bulkhead jumpers, RG316, about 30 cm (SMA, not RP-SMA): a bulkhead end has a threaded barrel with a nut and washer, which is what holds the antenna. The small right-angle pigtails in the antenna bundle are MCX, for Nooelec's USB sticks, and aren't used.

**Whip or external antenna, the user's choice:** each tower's jack is an ordinary SMA socket on the outside of the case. Screw on the Nooelec whip, or the coax from an antenna mounted outside or in a window; nothing inside changes. An outdoor antenna with an N-type connector needs an N-male to SMA-male cable. Leave the FlyCatcher's bias-tee switch off unless the outdoor antenna has a powered amplifier that needs it.

**Two parts since 2026-10-07: a body and a flat cover.** The first version ran each cable through an internal tunnel and could not be assembled: both ends of a jumper are rigid metal about 9 mm across and 15–20 mm long, and that cannot turn a right-angle corner inside an 11 mm bore. The checks had only ever passed a straight probe down each leg. Now the crossbar and towers have an open channel on the side away from the case, closed by a cover on five M2 screws, so everything is laid in and nothing is threaded round a corner. The arm's bore runs straight on through the crossbar and out of the channel floor; it is 13 mm, and so is the plate's hole, because both plugs share it and the second has to pass the first cable. Under each tower's panel is a slot that is a close fit on the jack's hex body, so the jack cannot turn while its nut is tightened. The panel is 2 mm: the bulkhead's thread is 10 mm from its shoulder, and 2 of panel, 0.6 of washer and 2.5 of nut leave 4.9 mm for the whip's own coupling nut.

**The plate's cable hole grew from 11 to 13 mm the same day.** A back plate printed before that — including one printed from the y=81 plate committed earlier on 2026-10-07 — will not pass the second plug and must be reprinted.

**Two styles, by the jumper's bulkhead body.** Measure the body behind the shoulder across its flats: the jumpers on hand come as 8 mm and as 11 mm hexes, and `antenna_mount_twin_8` / `antenna_mount_twin_11` (with their covers) are cut for each — slot = flats + 0.8, a pocket the hex's size under the panel, the tower, bar and cover sized to suit. Both take the same 6.35 mm barrel. Any other size is one number: `antenna_mount_twin([9, 9])`, or a mixed pair. A round body has nothing for the slot to hold; the jack is then held with thin pliers through the open channel while its nut goes on, before the cover.

**Which side is which:** the cover carries each tower's frequency, engraved under it and read from behind the case — `1090` on the left, `978` on the right (`ant_twin_labels`; `ant_twin_label_on = false` for a plain cover). The 1090 whip is the shorter one.

**Printing:** body flange-down with tree supports (Bambu Support for ABS interface), as the other mounts print. The towers and bar have 6 mm corners and rounded edges, like the cases, rather than a box. The channel, slots, insert holes and jack holes all face up or sideways and need nothing; the towers' outboard ends and the bar's top edge start in mid-air, so the supports go on the face toward the case, where nobody sees the scars. Cover flat, counterbored face down, no support. ASA on a clean Engineering plate, no glue.

**Fitting the cables** (cover off, body held channel-up — or the flange hanging over the bench edge, since the plugs come out of its underside):
1. Push each plug end into the bore at the centre of the channel, straight down the arm and out through the flange — the second plug goes in beside the first cable with a wiggle. Leave about 10 cm of each cable beyond the bore's mouth.
2. Lay one cable along the channel to each tower. Hold the jack's hex body with the barrel pointing up its tower and slide it sideways into the open slot until it stops.
3. Push the jack up with a fingertip through the open channel: the top of the slot is a closed pocket the hex's size, and the barrel comes through the panel when the body is in it. Washer and nut on from the top, finger tight, then a quarter turn with an 8 mm (5/16") spanner — the pocket holds the jack, so nothing inside has to be held. Don't crank it; the panel is 2 mm of ASA. Check the nuts again after a week; ASA relaxes a little.
   Set each whip so its hinge folds towards or away from the wall, not towards the other whip: that's the direction the mount is weakest, so the hinge gives before the panel does, and a folded whip then clears the other tower.
4. Tidy the cables into the channel and fit the cover: five M2 × 6 into the M2 inserts.

**Lettering in a second colour.** Open the cover's `_twotone.3mf` rather than its STL. The lettering is many separate letters, and a slicer splits a multi-lump STL into one part per letter, so picking a colour for "the text" would colour one letter; the project file already has the cover on filament 1 and every letter on filament 2. Change either in the slicer. The cover prints outer face down, so the lettering is its first 0.6 mm, three 0.2 mm layers: three filament changes, nothing after. The plain STL still prints the engraved, one-colour cover.
5. Pass both plugs through the plate's 13 mm hole, bolt the flange on from inside the plate with the three M3 × 8, plug 1090 and 978 into the FlyCatcher, and screw the whips on (the 1090 whip is the shorter one). For an outdoor antenna, screw its coax onto the same barrel instead, and give the coax its own strain relief within a few centimetres of the tower.

To replace a cable: back plate off, cover off, nut off, slide the jack out of its slot, pull the plug back up through the bore. The mount stays bolted to the plate.

**Checks:**
- `twin_bore_straight`: a plug beside a cable (12 mm) passes straight down the 13 mm bore from the flange face to below the crossbar.
- `twin_slot_takes_jack`: an 8 mm-across-flats hex body stands in each slot under its panel.
- `twin_cover_fits`: the cover sits in its seat without touching the body; `twin_cover_seats` (control) finds the body when the cover is pushed 2 mm in. `twin_channel_open` and `twin_cover_screws_open` (controls) find a rod along the channel and rods through the cover's holes whole, and `twin_channel_probe_clear` and `twin_screw_probes_clear` are their complements: the same rods meet no body at all.
- `top_screw_clear_of_twin`: the plate's top screw and a hex key clear the mount.
- `twin_antennas_clear_case`: both whips, swept 220 mm up, miss the case (and the kitten's ears); `twin_antennas_probe_works` (control): the same envelopes moved 60 mm down the axis and 40 mm toward the case do hit it.
- `twin_vs_plate`, `twin_vs_stand`: no collisions with the back plate or the stand.
- `twin_panels_present`, `twin_holes_open`: positive controls; the panels are there and the jack holes are open.

## Checks

`sh run-checks.sh`. The script keeps these lists: targets that must come
out with no real volume (an interference, or a probe that should pass
through air); squeezes, which must find a sliver and no more (the power fix's
crush ribs in its board); contacts, which must find more than a film (the
power fix's board, tipped, meeting its ribs); blocks, which must run into
the part they meet (the power fix's stop, the wrong way round, in its
mount); positive controls that must
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
