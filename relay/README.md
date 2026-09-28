# Radome relay

The one small server the project runs: a Cloudflare Worker with a D1
database. Today it receives **opt-in health reports** from units and shows
the maintainer a fleet page. Phase 2 adds push notifications. The design is
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

**No locations.** Reports carrying a latitude or longitude field are
rejected outright. No network addresses are stored either.

## Security model

- Each unit signs every request with its own Ed25519 key, generated on the
  unit and never copied off it. No shared secret is baked into images.
- Requests are bound to their timestamp, method, path and body. The relay
  rejects anything more than 5 minutes off, replayed, or sent more often
  than every 10 minutes.
- An unknown key registers on first contact. The number of units is capped,
  so this can't grow without bound.
- The fleet page requires HTTP Basic auth against the `FLEET_TOKEN` secret.
  With no secret set, the page doesn't exist at all. Its only form refuses
  cross-site posts.

## Deploy (once, by the maintainer)

```bash
cd relay
npm install
npx wrangler login                                  # opens a browser
npx wrangler d1 create flightradar-relay            # copy the id into wrangler.toml
npm run db:init                                     # applies schema.sql
npx wrangler secret put FLEET_TOKEN                 # choose a long random password
npm run deploy                                      # prints https://flightradar-relay.<you>.workers.dev
```

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
