# What an aircraft shows

One aircraft is described the same way on the radar's own screen
(`index.html`) and in the app (`ios/`): the same lines on its tag, the same
fields in its details, in the same order, with the same words (#77).
`tests/test_aircraft_fields.py` reads both sides and fails if they drift.

## The tag

Beside the blip, top to bottom:

| Line | Example | When |
|---|---|---|
| Callsign, in its altitude colour | `DAL54` | always |
| Operator badge | `Delta Air Lines`, `Private Aircraft` | always |
| Seen before | `SEEN ×14` | when seen more than once |
| Type | `Airbus A330-200` | when known |
| Altitude · speed | `33,000 ft · 495kt` | always (`On ground`, `--` for no speed) |
| Route | `Atlanta → Lagos`, `… (unconfirmed)` in the warning colour | when known |
| Owner | `WHEELS TO WINGS LLC (United States)` | private aircraft, when known |

The app's compact label setting (callsign and altitude only, until tapped) is
the phone's own. The app also puts the airline's logo in the badge; the radar
does not, as that would have every public visitor's browser ask Google and
DuckDuckGo for icons.

## The details

| Field | Example |
|---|---|
| Photo | planespotters.net, with its credit; the kiosk falls back to a stock photo of the type (its own lookup), every other viewer to a "No photo available" picture |
| Callsign | in its altitude colour |
| Operator badge | as on the tag |
| Type · registration | `Airbus A330-200 · N851NW` (`Unknown type` when not known) |
| Owner | `Registered to …` (private aircraft) |
| Route | as on the tag |
| Altitude | `33,000 ft`, `On ground`, `—` |
| Speed | `495 kt` |
| Heading | `112°`, or `—` when none is reported |
| Vert. rate | `↑ 1200 ft/min`, `↓ 800 ft/min`, `Level` |
| Squawk | `1200` |
| Distance | `12.3 nm · 245°` |
| Heard on | `1090 MHz`, `978 MHz (UAT)`, `978 MHz, re-sent on 1090` (heard by this radar only) |
| Notable | `US military`, `Boeing 747`, `Never seen here before`, or the plane-alert-db category and who flies it (when notable) |
| Sightings | `14` |
| Within 2 mi | `3` |
| ICAO | `ICAO A1B2C3`, last |

Notable is the strongest reason, in this order: listed in plane-alert-db, a
military operator, a rare type, first time here (once the radar has seen
2,000 aircraft). The radar works it out once (`labels.rare_reason`) for the
core feed and the phone alerts. A well-known person's name appears only on the
owner's own screens: the kiosk and the app at home read it from the radar's
`/data/notable-people.json`, which the public address refuses.

Each side's own controls are not fields: the kiosk's Follow; the app's Follow,
Compass and Find in the sky. The app also says plainly when an aircraft came
from the network (adsb.lol) rather than this radar's antenna.

## Where the data comes from

The core feed (`deploy/core-feed.py`, `/api/aircraft`) carries every field the
app needs: `operator`, `type`, `reg`, `owner`, `route`, `squawk`, `vrate`,
`band`, `rare` and `sightings` (the sighting store's counts, refreshed once a
minute). The radar's page reads the sighting store and its own lists directly.
