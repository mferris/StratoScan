# Enclosures

Two cases for the same radar. They use identical hardware — the 203.34mm round
panel, a Raspberry Pi 5, two 100×45mm speakers, a 30mm fan, an RTL-SDR dongle —
and identical fasteners, so a build can be moved from one to the other.

| | |
|---|---|
| [Retro Radar Enclosure](Retro%20Radar%20Enclosure/) | The original: ribbed, riveted, ship's-instrument look. Printed and validated. |
| [Kitten Enclosure Two-Tone](Kitten%20Enclosure%20Two-Tone/) | The round display as a cat's face — ears, whisker-dot speaker grilles, a nose on the bezel, and a stand with white paws, black toes and a black tail with a white tip. |

Neither has the old antenna turret. Both take the same bolt-on antenna mount,
screwed into brass inserts in the back plate, with the coax coming up through
the middle of the bolt circle. The retro's `antenna_turret_*` modules are
still in the file on purpose: they are the positive control for the
`no_turret` check, which cannot tell "the turret is gone" from "the probe
missed" without something for the probe to find.

## One case, two costumes

The interior and the back are the *same design*, not two designs that
resemble each other. Everything the hardware touches — the back plate and its
lip, USB-C cutout and grilles; the cradle rails, fan mount, speaker brackets
and back posts; the display retainer; the exhaust slots; the whole antenna
mount — is character-for-character identical in both `.scad` files, and all
115 shared parameters carry the same values. A back plate printed for one unit
fits the other; rendered from either file it is the same 15,474-triangle mesh.

Only three modules differ, and only outside: `shell` (rivets and ribs vs ears),
`front_trim` (the kitten adds a nose and whisker grooves, and omits the one
screw the nose sits on) and `stand`.

This is enforced, because drift here is invisible — both files still render,
and both still pass their own `checks.scad`. It went wrong once already: the
kitten's exhaust slots were upgraded to 12mm rounded slots and the retro was
left on the old flat rectangles for long enough that the retro still defined
`exhaust_slot_h = 12` without using it. `tests/test_enclosure_core.py` now
fails if a core module or a shared parameter diverges, or if a newly shared
module starts to.

STLs are committed alongside the source so each folder is self-contained, but
they are generated. Change a `.scad` and both must be re-exported and
committed together, or the mesh quietly stops matching the source it claims to
come from.

A single-colour kitten design lived here too and has been removed; the
two-tone one supersedes it, and `stand.stl` in that folder is the whole stand
in one piece if you do not want two filaments.
