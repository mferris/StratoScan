# Kitten enclosure — two-tone

A tuxedo version of the [Kitten Enclosure](../Kitten%20Enclosure/): black
stand, **white paws with black toes**, and a **black tail with a white tip**.
The paws and tail are also about 15% larger, because at two colours they stop
being a silhouette detail and become the thing the eye lands on.

![two-tone stand](two-tone-preview.png)

The original is untouched and still printable — this is a fork, not a
replacement. Every dimension that touches a physical part is unchanged from
it, and therefore from the
[Retro Radar Enclosure](../Retro%20Radar%20Enclosure/) it inherited them from:
the 203.34mm round panel, the Pi's 58×49 standoff pattern, the two 100×45mm
speakers, the 30mm fan, the M3 screw ring, the USB-C and SMA bulkheads. The
head is identical. **Only the stand differs**, so a head printed from either
design sits in either stand.

## Parts

The head is one colour and prints as before:

| part | colour | what it is |
|---|---|---|
| `shell` | black | the head — body cylinder plus two ears, and all the internals |
| `front_trim` | black | the face — bezel ring with a nose and whisker grooves |
| `retainer` | — | ring behind the glass (identical to the retro part) |

The stand is split into five bodies, one per colour region:

| part | colour | what it is |
|---|---|---|
| `stand_body` | **black** | plinth, cradle arms, keel |
| `stand_paws` | **white** | both foot pads |
| `stand_toes` | **black** | the eight toe lobes |
| `stand_tail` | **black** | the tail from root to the white tip |
| `stand_tail_tip` | **white** | the flicked-up end |

`stand` is still there as a single-piece, single-colour version of exactly the
same shape — useful as a fallback, and as the reference the five parts are
checked against.

## Printing it in two colours

The five stand bodies share one coordinate frame, so they occupy their true
positions relative to each other. That gives you two routes:

**Multi-material (AMS, MMU, tool changer).** Import all five as a single
object — in most slicers, load the first, then "add part"/"load as part" for
the rest, which preserves their positions — and assign a filament to each.
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

Alongside the fit checks inherited from the single-colour design, the split
adds:

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
for p in shell front_trim retainer stand \
         stand_body stand_paws stand_toes stand_tail stand_tail_tip; do
  openscad --backend=manifold --export-format binstl \
           -D "part=\"$p\"" -o "$p.stl" kitten-enclosure-twotone.scad
done
```

The `.stl` files are committed alongside the source so the folder is
self-contained, but they are generated. Change the `.scad` and both must be
re-exported and committed together, or the mesh quietly stops matching the
source it claims to come from.
