# Kitten enclosure

The same radar in the shape of a sitting cat. Every dimension that touches a
physical part is copied verbatim from the
[Retro Radar Enclosure](../Retro%20Radar%20Enclosure/), which is printed and
validated — the 203.34mm round panel, the Pi's 58×49 standoff pattern, the two
100×45mm speakers, the 30mm fan, the M3 screw ring, the USB-C and SMA
bulkheads. Only the shape is new, so the two cases are interchangeable on the
same hardware.

The organising idea is that **the round display is the face.** Everything else
follows from it.

## Parts

| part | what it is |
|---|---|
| `shell` | the head — body cylinder plus two ears, and all the internals |
| `front_trim` | the face — bezel ring with a nose, whisker grooves and seven screw holes |
| `retainer` | ring behind the glass (identical to the retro part) |
| `stand` | the body — plinth, cradle, two front paws, a curled tail |

`test_ear` clips one ear and the head around its base into a small coupon, so
an appearance/fit test prints in minutes rather than hours.

## Where the cat is

- **Ears** rise from the top of the head, splayed outward, with a recessed
  inner-ear dish.
- **Whiskers are the speaker grilles.** The speakers keep their exact bracket
  and footprint; only the hole pattern changed, from a rectangular mesh to
  three drooping rows of dots on each cheek.
- **Nose** is a rounded triangle standing proud of the bezel at the chin,
  with three short engraved whisker grooves either side of it. They were
  briefly in the wrong place: the nose sits at −y, and the grooves were
  rotated about 0° instead, so all six landed on the right-hand side of the
  face, 90° from the nose. That printed before anyone noticed. They are now
  placed off `nose_angle`, they sweep away from the nose so the two sides
  mirror, and three checks pin them there — including `whisker_off_nose`,
  which fails if they ever leave the nose's own quadrant again.
- **Paws** stretch forward from the plinth: a domed pad that tapers from a
  taller, narrower ankle to a wide, low front, with four splayed toe lobes
  leading it and a cleft cut between each pair.
- **Tail** is thick at the root and tapers to a rounded tip. It hugs the
  plinth around the right side, then climbs the right paw's outboard flank
  and comes to rest draped over the foot — the pose a sitting cat actually
  adopts. Interpolated through its control points with Catmull-Rom so it
  flows rather than kinking at every joint.

## The antenna is different here

The retro case has a turret on top of the head for the FlightAware antenna's
31.5mm magnetic base. **The kitten does not** — the ears occupy that space, and
a 42mm turret between them would sit exactly where the antenna needs to be.

The SMA bulkhead pass-through in the back floor is unchanged, so an external
antenna on a cable works exactly as before. If you want a mast on this version,
the tail is the obvious place for it and would need a redesign to carry the
weight; ask before printing if that matters to you.

## Rendering and exporting

```bash
openscad --backend=manifold --export-format binstl \
         -D 'part="shell"' -o shell.stl kitten-enclosure.scad
```

Binary STL, because at this resolution the stand is 172,000 facets: 52MB as
ascii against 8.2MB as binary, byte-identical geometry. Every slicer reads
both.

Exporting already forces a full geometry evaluation. Check OpenSCAD's stderr
for `Status: NoError` and `Top level object is a 3D object (manifold)` before
printing. (Do not pass a bare `--render`: as of OpenSCAD 2026.06 that flag
takes an argument, so it prints usage and exports nothing.)

`preview-assembly.scad` renders the head seated in the stand.

## Fit checks

`checks.scad` holds the interference tests. Each one is an intersection that
must come out **empty**:

| check | what it proves |
|---|---|
| `ear_vs_post` | the hollow ears never reach an M3 insert post |
| `recess_vs_post` | the inner-ear dish never reaches a post either |
| `whisker_through` | a whisker hole is a real through-path, not a blind hole |
| `head_in_cradle` | the head seats in the stand with no interference |
| `ears_vs_cradle` | the ears clear the cradle arms |
| `tail_over_paw` | the tail rests ON the right paw rather than through it |
| `tail_vs_left_paw` | it comes nowhere near the left paw |
| `tail_vs_head` | the tail stays under the cradled head |
| `paws_vs_head` | so do the paws |

```bash
sh run-checks.sh                                    # all of them
openscad -D 'check="ear_vs_post"' -o /tmp/x.stl checks.scad   # just one
```

`run-checks.sh` reports the **volume** each target produces rather than
whether it produced anything: a boolean between parts that touch can leave a
zero-thickness film with many facets and no volume, and counting facets would
call that a failure.

There is also `check="canary"`, which must produce geometry. **Run it.** It
exists because `use <>` resolves relative to the file containing it: a check
file kept anywhere other than beside the design silently finds no modules, and
then every intersection test "passes" against nothing. That happened here, and
five green results turned out to be meaningless.

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

## Things that are easy to get wrong

Mistakes actually made and fixed on this design, kept as warnings:

- **Ears must thread between the insert posts.** They sit every 45° starting at
  0, so an ear centred on 45° or 135° lands on one. 30° either side of vertical
  clears them. The ear cavity additionally stops below the front lip zone, so
  the posts stay safe even if the styling is later nudged.
- **Clip styling cuts at `outer_dia` exactly**, not a few mm inside. Clipping
  the inner-ear dish at `outer_dia - 4` left the band out to the wall fair
  game, and the posts reach r=111.17.
- **The bezel's outer profile has to stay a true circle.** A muzzle bulging
  past `outer_dia` would foul the front cradle arm, which reaches z=57 — one
  millimetre past the shell's front face. The nose lives inside the 10mm rim
  band instead.
- **Whisker holes must cut through the speaker bracket as well as the wall**,
  or they dead-end in solid plastic: open from outside, sealed from inside.
- **The tail has to stay below z≈16.** The cradled head's underside comes down
  to about z=27, so a tail that swept upward collides with it.
- **The tail rests ON the right paw, and must cross OVER it.** Tail and paw
  deliberately meet; what must not happen is the tail passing through the
  foot at pad height, which reads as one fused lump rather than a tail
  draped over a paw. `tail_over_paw` asserts the tail never intrudes below
  z=11, the paw's lower half — "must not touch" would be the wrong test here.
- **The toes have to LEAD the pad, not sit under it.** The first version put
  them behind the pad's front sphere, so every toe was swallowed by the hull
  and the paws rendered as plain teardrops. Toe tips now define `y_front`
  and the pad is held back behind them.

## Smoothness

Curve resolution is set by `$fs` (0.4mm) and `$fa` (0.5°), not by a fixed
facet count.

A fixed count makes the flats grow with the feature, so the biggest, most
looked-at surfaces come out roughest. At the old `$fn = 96` the head's 223mm
rim carried **7.3mm flats** and the cradle 8.2mm, while every 3mm screw hole
also got 96 sides it had no use for. `$fs` caps the chord — the width of one
flat, which is what the eye reads as faceting — so a big curve gets the
facets and a small hole does not. The head is now at 0.97mm and every sphere
in the paws, toes and tail at 0.4mm, one extrusion width.

It is cheaper than raising `$fn` would have been: the savings on small holes
pay for the big surfaces.

`tail_smooth_steps` is the other half. The tail is hulls between consecutive
spheres, so every sphere leaves a crease around the tube. Those creases were
masked by the general faceting before; once the circumference was smooth
they read as rings, so the interpolation went from 6 points per control
segment to 14 — a joint every 2.4mm instead of 5.6mm.

Meshes are exported as **binary STL**: the stand is 172,000 facets, which is
52MB as ascii and 8.2MB as binary for byte-identical geometry.

**`use <>` does not carry `$fa`/`$fs`.** It imports modules and functions
only, so `checks.scad` and `preview-assembly.scad` set them again at the top.
Miss that and they silently work at OpenSCAD's defaults — rendering a
faceting the mesh does not have, or validating geometry that is not what
gets printed.

