# Enclosures

Two cases for the same radar. They use identical hardware — the 203.34mm round
panel, a Raspberry Pi 5, two 100×45mm speakers, a 30mm fan, an RTL-SDR dongle —
and identical fasteners, so a build can be moved from one to the other.

| | |
|---|---|
| [Retro Radar Enclosure](Retro%20Radar%20Enclosure/) | The original: ribbed, riveted, ship's-instrument look, with a turret on top for the FlightAware antenna. Printed and validated. |
| [Kitten Enclosure Two-Tone](Kitten%20Enclosure%20Two-Tone/) | The round display as a cat's face — ears, whisker-dot speaker grilles, a nose on the bezel, and a stand with white paws, black toes and a black tail with a white tip. No antenna turret; use the SMA bulkhead. |

STLs are committed alongside the source so each folder is self-contained, but
they are generated. Change a `.scad` and both must be re-exported and
committed together, or the mesh quietly stops matching the source it claims to
come from.

A single-colour kitten design lived here too and has been removed; the
two-tone one supersedes it, and `stand.stl` in that folder is the whole stand
in one piece if you do not want two filaments.
