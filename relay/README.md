# StratoScan relay

The one small server the project runs: a Cloudflare Worker with a D1
database. It receives **opt-in health reports** and **events** from units,
pairs phones with units by QR code, sends push alerts and Live Activities to
those phones through Apple (APNs), and shows the maintainer a fleet page. The design is
in [docs/ROADMAP.md](../docs/ROADMAP.md#architecture-the-relay).

**The radar never depends on it.** A unit that can't reach the relay, or has
reporting switched off, works exactly as before.

## What it stores

For each unit:
- its public key (which is its id);
- a name the maintainer gives it;
- first and last report times;
- its software version;
- its last ~30 days of health reports: uptime, receiver health, storage
  wear, temperature, clock battery, update state.

For each unit that sends **events** (roadmap 2.2; only once its owner
pairs a phone): the moments it decided a paired phone should hear about.
There are four kinds: emergency squawks, notable aircraft, low aircraft
overhead and helicopters. Each carries the aircraft's identity, type,
altitude, its distance from the unit rounded to half a nautical mile with
a compass direction, and its track (the direction it's travelling, which it
broadcasts itself). Events are kept for **48 hours** at most (500 per
unit), only long enough to deliver them. The fleet page shows how many
arrived, never what they were.

For **pairing** (roadmap 2.3): which phones are paired with which unit,
each phone's public key (its id) and the name it gave itself ("iPhone"),
and while a code is showing on a unit's screen, that code's SHA-256. The
code itself reaches the relay only when a phone presents it, is compared
and then discarded; it works once, and expires after 10 minutes or five
wrong guesses. A unit stops sending events when its last phone unpairs,
and the relay drops events from a unit with no phones.

For **push** (roadmap 2.1): each paired phone's APNs device token, whether
it is a development or App Store build, and which alert kinds it wants.
A token is only an address for Apple's push service. Apple tells the relay
when a token stops working, and the relay then forgets it. Each phone gets
at most 30 ordinary alerts an hour; emergencies always go through.

For **alerts about aircraft approaching a phone** (roadmap 2.7; only for
phones whose owner turns on "Approaching me"):
- each unit's X25519 "box" key, signed by the unit's own Ed25519 key;
- each such phone's latest location for each of its units, **as an opaque
  encrypted blob**. The phone seals it to that unit's box key, after
  checking the key's signature against the unit id it scanned at pairing,
  so the relay can neither read it nor substitute a key of its own. Kept 6
  hours at most, and deleted when the phone unpairs or turns the option
  off. The unit decrypts it and runs its approach prediction for that
  point; the approach event it sends back names the phone (it goes to that
  phone alone) and the aircraft, without distance or direction.

**No locations in the clear.** Reports or events carrying a latitude or
longitude field are rejected outright. No network addresses are stored either. An event
still says roughly where its unit is ("a helicopter passed within 2
miles"), which is why events are opt-in and kept so briefly.

## Fleets

A fleet is a group of radars with its own administrators (roadmap 1.13): for example, the radars one person has given to their family, or a club's radars.

**Making one** (the maintainer, on `/fleet` behind `FLEET_TOKEN`):
1. Use **Create fleet** to get an **invite code** and an **administrator link**. Each is shown **once**; the relay keeps only their SHA-256.
2. Send the invite code to radar owners. Send the link only to the administrator.
3. From the same section, **New invite code** replaces the code (the old one stops working), and **New administrator link** adds an administrator.

**Joining:** a radar's owner enters the invite code on the radar's setup page, under *Fleet*. The radar sends it, signed with its own key, to `POST /v1/unit/fleet`. It leaves with `POST /v1/unit/fleet/leave`, from the same card. A radar is in at most one fleet. Joining turns its health reports on, and leaving puts them back the way they were.

**Administrators:** opening the link sets an `HttpOnly`, `Secure`, `SameSite=Strict` cookie and redirects to `/f`, so the secret doesn't stay in the address bar. `/f` shows that fleet's radars only:
- name, software version, last report and health;
- the public page's views and visitors over the last 7 days.

It never shows a location (health reports carry none), phones or alerts. An administrator can remove a radar or replace the invite code.

**Storage:** three tables, `fleets`, `fleet_admins` and `fleet_members`, in `schema.sql`. On the live database they were created with `wrangler d1 execute --command`, because `--file` needs an API permission the maintainer's login doesn't have.

## Security model

- Each unit signs every request with its own Ed25519 key, generated on the
  unit and never copied off it. No shared secret is baked into images.
- Requests are bound to their timestamp, method, path and body. The relay
  rejects anything more than 5 minutes off or replayed. Health reports may
  come at most every 10 minutes. Events are capped at 120 an hour per unit
  and 20 per request, and every field is validated and length-limited
  before it is stored.
- An unknown key registers on first contact. The number of units is capped,
  so this can't grow without bound.
- Phones sign the same way with their own Ed25519 key (CryptoKit on iOS),
  named in `X-FR-Phone`. A phone can only pair by presenting the code on a
  unit's screen, and can only unpair itself. A unit can list and remove its
  own phones.
- The fleet page requires HTTP Basic auth against the `FLEET_TOKEN` secret.
  With no secret set, the page doesn't exist at all. Its only form refuses
  cross-site posts.

## Deploy (once, by the maintainer)

```bash
cd relay
npm install
npx wrangler login                                  # opens a browser
npx wrangler d1 create stratoscan-relay             # copy the id into wrangler.toml
npm run db:init                                     # applies schema.sql
npx wrangler secret put FLEET_TOKEN                 # choose a long random password
npx wrangler secret put APNS_KEY < AuthKey_XXXX.p8  # the APNs auth key from developer.apple.com
                                                    # (key id, team id and app id go in wrangler.toml [vars])
npm run deploy                                      # serves the custom domain in wrangler.toml (and https://stratoscan-relay.<you>.workers.dev)
```

After a change to `schema.sql` (new tables only, never altered ones), run
`npm run db:init` again before `npm run deploy`. It is safe to repeat.

Then set `RELAY_URL` in `deploy/heartbeat.py` to that address and cut a
release; units that have opted in start reporting within a few minutes. The
fleet page is at `/fleet`.

The free Cloudflare plan covers this comfortably: one small request per unit
every 6 hours.

## Test

```bash
npm test
```

The tests run the Worker and its real SQL (Node's built-in SQLite behind a
D1 stand-in). They include a request signed by the Python unit client on a
real device, so the two sides can't silently drift apart.
