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
| `front_trim` | the face — bezel ring with a nose and whisker grooves |
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
- **Nose** is a rounded triangle standing proud of the bezel at the chin, with
  short engraved whisker grooves either side.
- **Paws** stretch forward from the plinth, each with three toe domes.
- **Tail** curls flat around the right side and forward.

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
openscad -D 'part="shell"' -o shell.stl kitten-enclosure.scad
```

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

```bash
openscad -D 'check="ear_vs_post"' -o /tmp/x.stl checks.scad
```

There is also `check="canary"`, which must produce geometry. **Run it.** It
exists because `use <>` resolves relative to the file containing it: a check
file kept anywhere other than beside the design silently finds no modules, and
then every intersection test "passes" against nothing. That happened here, and
five green results turned out to be meaningless.

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
- **Keep the tail outboard of x=62.** The right paw occupies x 25..59; an
  earlier curl swept in to x=36 and merged into it, reading as one lump.
