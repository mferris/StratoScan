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
- its last ~30 days of health reports (only 3 while the unit is under a
  week old): uptime, receiver health, storage wear, temperature, clock
  battery, update state. Only those fields are kept, about 1 KB a report
  (`cleanHeartbeat` in `src/limits.js`); anything else a report carries is
  dropped.

A unit not heard from for 30 days is forgotten by the daily cleanup,
unless the maintainer has named it, it is in a fleet, or a phone is paired
with it.

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
and then discarded; it works once, and expires after 10 minutes. A wrong
guess changes nothing (the code is 128 random bits), so a stranger who
knows a unit's id can't void its code. While a code is open the relay
also keeps a fingerprint of the network block it came from (the /24 of
an IPv4 address, the /48 of an IPv6 one), to allow only a few open codes
per network; it goes with the code. A unit stops sending events when its last phone unpairs,
and the relay drops events from a unit with no phones.

For **push** (roadmap 2.1): each paired phone's APNs device token, whether
it is a development or App Store build, and which alert kinds it wants.
A token is only an address for Apple's push service. Apple tells the relay
when a token stops working, and the relay then forgets it. Each phone gets
at most 30 ordinary alerts an hour; emergencies go past that, up to 60,
except from a radar paired less than a day ago, whose emergencies and tests
are capped at 5 an hour.

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
longitude field are rejected outright. No network addresses are stored
either (only the network-block fingerprint of an open pairing code, above). An event
still says roughly where its unit is ("a helicopter passed within 2
miles"), which is why events are opt-in and kept so briefly.

For **the shared cache** (`src/netcache.js`, 2026-10-09): nothing per
unit. The relay keeps, in Cloudflare's per-data-centre cache, the public
network's aircraft in 250 nm discs on a fixed world lattice (10 seconds),
flight routes from adsb.im by callsign (6 hours; "no route" for 1 hour)
and registered owners from adsbdb by aircraft address (7 days). Entries
are keyed by the thing asked for, never by who asked (a route by its
callsign and the one-degree cell the flight is in, since adsb.im's verdict
depends on where it is); a unit that has reported for two days (at least 4
reports) and still does, or a phone paired with one, may ask, and nothing
else. Others are told 403 and ask the services themselves, as before. A disc is fetched from adsb.lol
by the unit that first finds it missing (adsb.lol rate-limits Cloudflare's
shared addresses) and handed up for the others; routes and owners the
relay fetches itself.

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

**Storage:** three tables, `fleets`, `fleet_admins` and `fleet_members`, in `schema.sql`. On the live database they were created with `wrangler d1 execute --command`, because `--file` needs an API permission the maintainer's login doesn't have. An administrator's link can be replaced, by the administrator ("Replace my link" on their page) or by the maintainer: the old one stops working at once and says so when opened; `fleet_admins.replaced_hash` and `replaced` were added the same way on 2026-10-08.

## Security model

- Each unit signs every request with its own Ed25519 key, generated on the
  unit and never copied off it. No shared secret is baked into images.
- Requests are bound to their timestamp, method, path and body. The relay
  rejects anything more than 5 minutes off or replayed. Health reports may
  come at most every 10 minutes. Events are capped at 120 an hour per unit
  and 20 per request, and every field is validated and length-limited
  before it is stored.
- An unknown key registers on first contact. The number of units heard from
  in the last 30 days is capped, so this can't grow without bound, and keys
  that go silent stop counting after a month. Enrolment (#65) is still to
  decide who may report at all.
- Every request is rate-limited per address before anything else, more
  tightly for anything that can write and for the fleet pages; signed
  changes are also limited per signing key once the signature verifies,
  before the database is touched (`src/ratelimit.js`). An IPv6 address
  counts as its /64, and writes from IPv6 are limited per /48 as well.
  Event batches are left out of the tighter per-address limit, so several
  radars behind one address (a fleet site) aren't held up. The route's own
  checks run before the replay record is written, and may read the
  database: a request that would change nothing (a wrong pairing guess,
  leaving a radar the phone isn't paired with) writes nothing at all.
  Bodies are read only up to their limit, and only after the signing
  headers look right.
- What new keys write is also budgeted per address for the whole UTC day
  (`src/budget.js`): 250 changes per IPv4 address or IPv6 /64, 1,000 per
  /48. A key is new until its radar has two days of reports or a pairing a
  day old, or its phone has such a pairing. See the quota arithmetic below.
- Open pairing codes from new radars are capped at 8 per network block and
  500 in all (the oldest go first). A settled radar's code is never pushed
  out. A brand-new radar's code still can be, by a flood from many networks
  in the minutes before its phone pairs; enrolment (#65) is the real fix.
- Emergencies and tests from a pairing less than a day old are capped at 5
  an hour, counted for that pairing alone.
- A daily cron (`scheduled()` in `src/index.js`, `src/cleanup.js`) prunes
  replay records, expired codes, alerts past 48 hours, reports past 30
  days, yesterday's budget counts, silent keys, box keys of radars with no
  report or pairing that went a month without republishing, pairings
  neither side has used in 90 days, and phones no longer paired with
  anything.

### D1 quota arithmetic

The free plan allows 100,000 rows written a day, for everyone. A real
radar writes about 3 rows per report (4 a day), and a few per alert; a
household is a few hundred rows a day at most. Anyone can mint keys, so:

- From one address in one minute: 60 writes (`RL_STRICT`), but over a day
  only 250 changes from new keys (`src/budget.js`), about 750 rows with
  their replay records and the budget's own counter. Using up the day's
  writes takes about 130 IPv4 addresses or /64s, or 33 IPv6 /48s.
- At most 500 radars that reported in the last 30 days are accepted
  (`MAX_UNITS`), and a minted radar becomes settled (unbudgeted) only after
  two days of reports or a day-old pairing, each through the budget.
- What is left: a patient attacker with many addresses can still settle
  hundreds of keys and then write as fast as the per-key limits allow
  (one report per 10 minutes, 120 alerts an hour). Only enrolment (#65)
  closes that; the dashboard rate-limiting rule below is the backstop.
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
npx wrangler d1 create stratoscan-relay             # copy the id into wrangler.toml (start from wrangler.example.toml)
npm run db:init                                     # applies schema.sql
npx wrangler secret put FLEET_TOKEN                 # choose a long random password
npx wrangler secret put APNS_KEY < AuthKey_XXXX.p8  # the APNs auth key from developer.apple.com
                                                    # (key id, team id and app id go in wrangler.toml [vars])
npm run deploy                                      # serves the custom domain in wrangler.toml (and https://stratoscan-relay.<you>.workers.dev)
```

After a change to `schema.sql` (new tables only, never altered ones), run
`npm run db:init` again before `npm run deploy`. It is safe to repeat.
A change to an existing table comes as a file in `migrations/`, run once
on the live database before deploying the Worker that needs it; each file
says how. `schema.sql` already includes every migration, so a new database
needs none of them (and `db:init` fails on an older database until its
migrations have run).

`wrangler.example.toml` has the daily cleanup's cron trigger and the four
rate-limit bindings (`RL_IP`, `RL_STRICT`, `RL_KEY`, `RL_NET`); copy both sections
into your `wrangler.toml`. Without the bindings the same limits are
counted in memory per machine. Also add a rate-limiting rule for the
relay's domain in the Cloudflare dashboard (for example 120 requests per
10 seconds per address, tighter on `/fleet*` and `/f/*`): a request the
Worker refuses still counts toward the daily quota.

Then set `RELAY_URL` in `deploy/heartbeat.py` to that address and cut a
release; units that have opted in start reporting within a few minutes. The
fleet page is at `/fleet`.

The free Cloudflare plan covers this comfortably: one small request per unit
every 6 hours.

## Scale test

`node scale-test.mjs [radars] [phones per radar]` runs a simulated day for a
fleet against the real Worker code and SQL (the D1 stand-in from `test/`),
and prints requests, statements, rows and the worst status. Measured
2026-10-04: a radar with one phone sharing its location costs about 1,750
relay requests a day (1,440 of them location polls, every minute); one with
none sharing about 175. Five radars and fifteen phones: 8,835 requests and
19,205 D1 statements a day, every one answered 200. A hundred radars:
175,308 a day, which is past the Workers free plan's 100,000, so a fleet of
more than about 50 radars with phones sharing needs the $5 paid plan.

## Test

```bash
npm test
```

The tests run the Worker and its real SQL (Node's built-in SQLite behind a
D1 stand-in). They include a request signed by the Python unit client on a
real device, so the two sides can't silently drift apart.
