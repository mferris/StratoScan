# FlightWall enclosure

The 3D-printable case for the wall/desk build, as a single parametric
OpenSCAD source. Everything is driven from the measured values at the top of
[`flightwall-enclosure.scad`](flightwall-enclosure.scad) — change those and
the rest follows.

## Parts

| part | what it is |
|---|---|
| `shell` | the body: Pi, dongle, wiring, speakers, fan bracket, antenna turret |
| `front_trim` | bezel in front of the glass, rabbeted so it seats flush |
| `retainer` | ring behind the glass; the glass rests on its front face |
| `stand` | desk cradle — two ring-arc arms on a plinth |

Two extra targets, `test_antenna` and `test_speaker`, clip the real shell
geometry to a small box so a fit test prints in minutes instead of hours.

## Rendering and exporting

Set `part` at the top of the file, or override it from the command line:

```bash
openscad -D 'part="shell"' -o shell.stl enclosure/flightwall-enclosure.scad
```

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
- **The antenna turret is counter-tilted forward by `stand_angle`.** The case
  leans back by that same angle in the cradle, so the two cancel and the
  antenna ends up vertical. Get the sign wrong and it is off by double.
- **The cradle only cups the case; the retention rails are what hold it.**
  With the bowl's axis tilted, gravity pushes the case straight down that
  axis, and nothing else opposes it.
- **Speaker brackets must be clipped to the outer cylinder.** They are flat
  slabs across a curved wall, so their corners otherwise punch through it.
- **Grille holes have to cut through the bracket as well as the wall**, or
  they dead-end in solid plastic and no sound gets out.

## Generated STLs

Not committed — they are build output, regenerate them from the source.
