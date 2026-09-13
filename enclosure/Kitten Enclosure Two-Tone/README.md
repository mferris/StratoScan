# Kitten enclosure — two-tone

The round display as a cat's face, in two colours: black stand, **white paws
with black toes**, and a **black tail with a white tip**. Ears, whisker-dot
speaker grilles, a nose on the bezel, and a stand with paws and a curled
tail.

![two-tone stand](two-tone-preview.png)

Every dimension that touches a physical part comes verbatim from the
[Retro Radar Enclosure](../Retro%20Radar%20Enclosure/), which is printed and
validated: the 203.34mm round panel, the Pi's 58×49 standoff pattern, the two
100×45mm speakers, the 30mm fan, the M3 screw ring, the USB-C and SMA
bulkheads. Only the shape is new, so the two cases are interchangeable on the
same hardware.

This began as a fork of a single-colour kitten design, which has since been
removed — the paws and tail here are about 15% larger than they were in it,
because at two colours they stop being a silhouette detail and become the
thing the eye lands on. `stand.stl` is the whole stand as one piece if you
want it in a single filament.

## Parts

The head is one colour and prints as before:

| part | colour | what it is |
|---|---|---|
| `shell` | black | the head — body cylinder plus two ears, and all the internals |
| `front_trim` | black | the face — bezel ring with a nose, whisker grooves and seven screw holes |
| `retainer` | — | ring behind the glass (identical to the retro part) |
| `back_plate` | black | removable back — locating lip, standoffs, vents, one USB-C pass-through, antenna-mount inserts |
| `antenna_mount` | black | bolt-on arm carrying the antenna socket |
| `usbc_gauge` | — | test coupon: five candidate USB-C cutouts, to fit the connector before printing a plate |

The stand is split into five bodies, one per colour region:

| part | colour | what it is |
|---|---|---|
| `stand_body` | **black** | plinth, cradle arms, keel |
| `stand_paws` | **white** | both foot pads |
| `stand_toes` | **black** | the eight toe lobes |
| `stand_claws` | **white** | eight real claws, one per toe |

`kitten-stand-twotone.3mf` is all six of the above in one project file with
the filaments already assigned — the easiest way in, and the one that avoids
the multi-lump selection problem described under *Printing it in two colours*.
| `stand_tail` | **black** | the tail from root to the white tip |
| `stand_tail_tip` | **white** | the flicked-up end |

`stand` is the whole stand as one piece, the same shape in a single
filament — useful if you are not printing in two colours, and it is also the
reference the five coloured parts are checked against.

## The back comes off, and carries the antenna

The back used to be a fixed floor with the electronics standing on it, so the
only way in was through the glass. It is a separate plate now, screwed to
eight insert posts exactly as the faceplate is.

**This plate is the same part as the retro build's**, and so is the antenna
mount. Both cases are the same 223.34mm diameter, use the same eight-post
ring, and lean back by the same 18°. That is checked rather than asserted:
exported from each design, the two back plates are 15,410 facets that compare
equal as sets — the same solid, differing only in triangle order.

A rib on the inner face drops into the bore so the plate lands centred and
square and holds itself there while the screws go in, with a 1.2mm chamfer on
its outer top edge so it finds its own centre. It is eight arcs rather than a
ring: the insert posts span r=102.2–111.2 against a bore wall at
r=108.7–111.7, so they straddle the wall and a continuous ring would run
through all eight. Three checks hold it — `lip_present` as a positive
control, `lip_clears_posts`, and `lip_inside_bore`, since a lip larger than
the bore does not locate anything, it just stops the plate seating.

The two cable glands are gone, replaced by a single opening for a panel-mount
USB-C cable; the antenna's coax comes in through the mount's own bore
instead. **The cutout dimensions are a placeholder** — the connector's
listing publishes no cutout size — so print `usbc_gauge`, a coupon carrying
the nominal cutout plus four neighbours at ±0.5 and ±1.0mm, and fit the
connector before committing a plate.

The mount screws into three M3 heat-set inserts on the plate's inner face
rather than through bare holes, so it can be removed without holding a nut
inside the case. The insert pocket stops on a shoulder 1mm above the plate so
the insert cannot be pressed too deep. The bolt circle is clocked 30° off
vertical for clearance, not looks: at 0° one boss reaches y=106.5, into the
locating lip at 106.3.

The upper vent moved from y=+68 to y=−68. The mount's flange is a 40mm disc
centred at y=88, so at +68 the grille sat underneath it from y=68 to y=81,
venting into the back of a solid disc — which is what prompted this.
`vents_clear_of_mount` holds the new position, and `vents_were_under_mount`
is its paired control, finding the 257mm³ overlap the old one had.

The Pi is mounted to the LCD panel rather than to those standoffs, so taking
the plate off exposes the back of the Pi and its cabling rather than removing
it. **There is no fan mount** — the fan goes on the Pi. The two grille
patterns stay as plain vents.

The antenna mounts on the back of the plate rather than on a turret, since a
turret out of a cat's skull is a spike. It is a **bolt-on**: three M3 bolts
on a 30mm circle. That keeps both parts flat and support-free on the bed, and
lets the antenna angle change later without reprinting the tray. The cable
drops out of the socket and runs straight through the arm, the flange and the
plate into the case.

The mount sits inside the head's outline and cannot be seen from the front;
only the antenna shows, rising between the ears.

### Why the arm reaches straight back before the barrel rises

The arm goes **back** from the plate, and only then does a barrel rise from
its end along the antenna's own axis. That two-stage shape is forced, not
styled. A barrel coaxial with the antenna and rooted on the plate would have
to climb toward the head the whole way and would run into it.

The first attempt avoided that by hulling a pad on the plate to a disc at the
socket — which produced a *cone* with the socket bored into its flank, so the
antenna pointed sideways and down rather than up. A stub plus a barrel gives
a real cylindrical socket with a flat face square to the antenna.

The arm is 30mm because that is what the clearance costs. Swept against the
antenna's own envelope: at 22mm it fouls the head's top rim even at nominal
diameter, at 26mm it clears nominal but not +2mm, and at 30mm it still clears
with 6mm of radial slack. `antenna_clears_head` holds it.

## Printing it in two colours

The five stand bodies share one coordinate frame, so they occupy their true
positions relative to each other. That gives you two routes:

**Multi-material (AMS, MMU, tool changer).** Open
`kitten-stand-twotone.3mf`. It is the whole stand as one object with the six
bodies already inside it and a filament already assigned to each — nothing to
position, nothing to select.

That file exists because loading the STLs separately does not work well, for
a reason that is not obvious. Three of the bodies are physically several
disconnected lumps: two paws, two clumps of toes, and eight separate claws,
because that is what the shapes are. Slicers split a multi-lump mesh into
separate parts on import, so picking a filament for "the claws" colours **one
claw** and leaves the other seven — which looks like the tool ignoring you.
There is no way to fix that from the STL side; eight claws cannot be one
connected lump. So the assignment lives in the project file instead.

The filament slots are 1 for the black (body, toes, tail), 2 for the white
(paws, tail tip) and 3 for the claws, kept on their own slot so they can be a
third colour. Change any of them in the slicer.

If you would rather load the STLs by hand anyway: load the first, then "add
part"/"load as part" for the rest, which preserves their positions, and
assign a filament to each.
No supports needed for the paws or toes; the tail tip lifts off the paw and
wants a little support under the flick.

**Single extruder.** Print them as separate objects and glue. Every split
follows a real seam in the shape — pad to toe, tail to tip — so the joins
land where the eye already expects a line. Print `stand_body` flat on its
base; the paws, toes and tail parts are all small and sit stably on their cut
faces.

### Why the parts overlap slightly

The bodies deliberately interfere by 0.3mm (`colour_overlap`) along every
seam, and the first version of this design got that exactly backwards.

Cutting each part with the precise shape of its neighbour is the tidy answer
and it is the broken one. It produces a perfect partition — zero shared
volume — while leaving the two bodies sharing a *surface* at identical
coordinates. No renderer can decide which of two faces at the same depth is
in front, so the slicer stipples the seam with the other colour: a white paw
arrives speckled black, worst over the buried half of the paw where the
shared area is largest.

So each part is cut with a slightly inset copy of whatever takes precedence
over it, leaving a thin shell of shared material instead of a shared surface.
Nothing is coplanar, and the colour boundary moves by at most 0.15mm — a
fifth of a nozzle width, so which body a slicer awards the shell to cannot be
seen in the print.

The tail needed the opposite treatment. Its two parts are runs of the same
tapering tube, so wherever they overlap they carry the same outer skin —
and an overlap of identical skin is the very coincidence being avoided.
There the tip is grown rather than the body shrunk, so over the shared
stretch the white tip sits 0.15mm proud of the black tail it continues.

## The whisker grooves

Three short arcs engraved into the bezel face either side of the nose.

They were briefly in the wrong place, and it is worth recording how. The
nose sits at −y, the bottom of the face; the grooves were rotated about 0°
instead — the right-hand side — so all six landed 90° from the nose they
were meant to flank. That printed before anyone noticed, as six unexplained
indentations down one side of a faceplate.

They are now placed off `nose_angle` rather than a literal, and each sweeps
away from the nose so the two sides mirror. `whisker_off_nose` in
`checks.scad` pins it: the grooves must lie entirely within a 90° wedge
centred on where `nose()` actually puts itself. That wedge is written as a
literal 270 on purpose — deriving it from `nose_angle` would make the check
vacuous, since moving the angle would move the wedge along with the grooves.

## Where the colour goes, and why

- **Paws white, toes black.** The toes are the detail that makes a paw read
  as a paw, and they are small — they need the contrast more than the pad
  does. The clefts between them grew with the toes; the groove is the only
  thing making four toes read as four rather than one lumpy pad.
- **Claws are their own body, and they are real geometry.** The grooves
  between the toes were being read as the nails; they were never that — they
  are the only thing making four toes read as four. There are now eight
  actual claws, one off the front of each toe, following that toe's splay and
  drooping toward the desk the way a cat's does. Their base sits *inside* the
  toe rather than butted against it: a spike joined at a tangent point is a
  weak spot in the print, and a butted joint would share a surface with the
  toe, which is the coincidence that stipples the preview. The tip stops
  clear of the desk on purpose — claws that reached z=0 would carry the
  stand's weight on eight little points and rock, which `claws_off_the_desk`
  holds. `claws_stand_proud` is the paired positive control: a claw entirely
  buried in its toe passes every seam and volume check while being invisible
  on the print, which is exactly what the grooves-as-nails problem looked
  like.
- **Tail black, tip white, and the tip lifts.** The first version had the tip
  resting flat on the pad, which is what a sitting cat does — but that put a
  white tip on top of a white paw, where it vanished. The whole point of a
  white tip is that it reads against what surrounds it. Lifted, it is
  silhouetted from every angle, and a flicked tail tip is cat-like anyway.
  This was caught by rendering it and looking, not by any check.

## Smoothness

Curve resolution is set by `$fs` (0.4mm) and `$fa` (0.5°) in the `.scad`,
not by a fixed facet count.

A fixed count was what this had, and it makes the flats grow with the
feature — so the biggest, most looked-at surfaces come out roughest. At the
old `$fn = 96` the head's 223mm rim carried **7.3mm flats** and the cradle
8.2mm, while every 3mm screw hole also got 96 sides it had no use for. `$fs`
caps the chord — the width of one flat, which is what the eye reads as
faceting — so a large curve gets the facets and a small hole does not. The
head is now at 0.97mm and every sphere in the paws, toes and tail at 0.4mm,
which is one extrusion width: below that a 0.4mm nozzle cannot reproduce the
difference.

The meshes are exported as **binary STL**. At this resolution the stand is
173,000 facets, which is 52MB as ascii and 8.3MB as binary for byte-identical
geometry. Every slicer reads both.

`tail_smooth_steps` is the other half of it. The tail is hulls between
consecutive spheres, so every sphere leaves a crease running around the
tube. At the old resolution those creases were masked by the general
faceting; once the circumference was smooth they read as rings. 14 points
per control segment puts a joint every 2.4mm instead of 5.6mm, for about a
megabyte.

To go finer, lower `$fs` — but check the file sizes, because sphere cost
grows as the square.

**`use <>` does not carry `$fa`/`$fs`.** It imports modules and functions
only, so `checks.scad` and the preview files set them again at the top. Miss
that and they silently render at OpenSCAD's defaults, showing a faceting the
exported mesh does not have — or, worse, validating geometry that is not what
gets printed.

## Seven screws, not eight

The bezel has seven screw holes. There is an eighth insert post in the shell
at the same angle as the nose, and the nose stands on top of it — 2.6mm of
solid capping the hole, so that screw could never have been fitted. Rather
than leave a hole that cannot take a screw and reads as a moulding defect
under the chin, it is not cut at all.

The shell keeps all eight posts. An unused boss is invisible from outside and
keeps that part identical to the retro build it was copied from.

Found by probing the screw ring after a faceplate had already been printed.
`nose_screw_removed` now proves the hole is absent, and `other_screws_present`
is its paired positive control — an empty result from the first would also be
what a probe in the wrong place produces, so a probe at a normal position has
to find a real hole for the pair to mean anything.

## Checks

`sh run-checks.sh` runs every target in `checks.scad` and reports the
**volume** each produces.

Volume, not facet count. A boolean between parts that touch leaves
zero-thickness films along the boundary — thousands of facets and no volume —
so counting facets calls a correct model broken. The threshold is 1mm³
against a paw of roughly 27,000mm³, and a real interference has nowhere to
hide in that gap.

Volume alone is not enough either, which is what the speckled first version
proved: a shared surface has no volume at all. That is what
`check-coincident.py` below is for.

Alongside the fit checks on the head and cradle, the colour split adds:

- `material_lost` — must be **zero**: a region of the one-piece stand that no
  coloured part claims. That would print as a hole.
- `material_gained`, `paws_vs_toes`, `body_vs_paws`, `tail_vs_tip` — must be
  **small but non-zero**: these are the colour seams, and zero here means the
  parts share surfaces instead of overlapping, which is the speckling bug.
  Bounded at 1500mm³, which is 0.15mm of thickness over 10,000mm² of shared
  surface — far more than these parts have.
- `canary` — must produce geometry. Without it, a typo in the `use <>` path
  makes every check above pass against nothing, which has happened here
  before.

`check-coincident.py` makes the check the volume tests cannot: it compares
the exported meshes face by face and counts triangles two parts have at
identical coordinates. Two parts sharing a surface have zero shared volume
and still stipple, so nothing about that bug is visible in a volume
measurement. All ten pairs must come out at zero. With the overlap disabled
(`-D colour_overlap=0`) the same check reports 3,502 shared faces between the
paws and the toes, which is precisely the speckling.

Run everything with `sh run-checks.sh`, which also runs the coincidence
check.

## Regenerating

```sh
for p in shell front_trim retainer stand back_plate antenna_mount usbc_gauge \
         stand_body stand_paws stand_toes stand_claws stand_tail stand_tail_tip; do
  openscad --backend=manifold --export-format binstl \
           -D "part=\"$p\"" -o "$p.stl" kitten-enclosure-twotone.scad
done
```

**The exporter is not deterministic.** Two consecutive exports of unchanged
source differ — 135 facets out of 210,448 on the stand, and even the facet
count moves (210,758 vs 210,448 across runs). It shows up on the stand and
not on the simple parts, which is consistent with it coming from the hundreds
of hulls the paws and tail are built from. Two consequences: re-exporting
everything makes the stand files show as modified whether or not anything
changed, so only re-export what actually changed; and comparing two STLs byte
for byte is not a test of whether they are the same shape — compare the
triangle sets instead.

The `.stl` files are committed alongside the source so the folder is
self-contained, but they are generated. Change the `.scad` and both must be
re-exported and committed together, or the mesh quietly stops matching the
source it claims to come from.

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

### Why the seat is stepped

Two measurements of the same base disagreed: it mikes **31.25mm** across the
bottom, and it would not pass a **34mm** gauge ring. Both are true, because
the base is a cone — the calipers caught the narrow bottom disc, the rim was
catching the flare above it.

A single bore cannot serve both. Sized for the flare, the bottom rattles;
sized for the bottom, the flare never gets in — which is precisely the mount
that came back with its rim snapped off. So there are two bores: **Ø32.75 for
4mm** locating the bottom disc with 0.75mm of radial slack, then **Ø36.5**
clearing the flare, then the chamfer. `socket_takes_base` and `flare_clears`
check one each, because they are different questions.

**`antenna_socket_gauge` is the cheap way to confirm it** — five sockets in
half-millimetre steps (34.5 to 36.5 by default; change `gauge_from` and
`gauge_step` to re-aim) with the real chamfer, the real depth and the real
cable hole, each rim carrying as many notches as its position.
Find the smallest one the base levers into and sits square in, and set
`ant_socket_dia` to that. Smallest, not easiest: the rim is what stops the
base falling out sideways, so slack is not free.

`socket_takes_base` holds it, with `socket_gauge_works` as its paired control.
Its first version was wrong in a way worth recording: it ran a full-diameter
disc 12mm into the air above the mouth and failed at 283mm³, which was the
arm alongside. A 35mm cylinder held 12mm above the socket really does overlap
the arm — and means nothing, because the base is a cone that narrows and comes
in from outside. The question is whether the base fits the socket.
