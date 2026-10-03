<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-on-dark.svg">
    <img src="assets/brand/logo-on-light.svg" alt="StratoScan" width="420">
  </picture>
</p>

# StratoScan

*Formerly Radome, and before that FlightRadar.*

A live ADS-B flight radar on a round display, built on a
Raspberry Pi and a cheap SDR dongle — no subscription and no API keys. The
radar needs nothing but its own receiver and a browser; an optional iPhone
app brings it to your pocket.

![StratoScan running on the physical kiosk display](docs/screenshots/kiosk.png)

<sub>Centred on RDU airport. Map: OpenFreeMap © OpenMapTiles, data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).</sub>

## Status

*As of 2026-10-03.* One unit (RDU) runs around the clock on release
`2026.10.02.1`. The plan is in [docs/ROADMAP.md](docs/ROADMAP.md), tracked
as [issues](https://github.com/mferris/StratoScan/issues), and the parts it still
needs are in the [shopping list](docs/SHOPPING.md).

| Area | State |
|---|---|
| The radar (kiosk) | Running unattended; updates itself from signed releases. One labelled aircraft feed on the unit for every screen (`/api/aircraft`); drawing cost halved |
| Phase 4 extras | Done: rewind, notable aircraft, empty-sky screen, spoken announcements, year in review, opt-in FlightAware feeding |
| Relay (push, fleets, health) | Live on Cloudflare Workers. Fleets: groups of radars with their own administrators, who see health and visit counts, never locations |
| iPhone and iPad app | Working on a real iPhone: QR pairing, push alerts (about the radar, where you are, or both, including aircraft approaching *you*), widgets, Live Activity (also on CarPlay), home/away switching, the network's aircraft, zoom, a compass, Sky view with tracks, the logbook, weather, colour themes, radar names. Setting up a new radar from the app, one QR code to paired (simulator-tested). A no-radar mode and an iPad layout (simulator-tested) |
| Apple Watch app | Built (glance radar, complications, Smart Stack); waiting for TestFlight to reach a real Watch |
| Security review | Full scan done 2026-09-28; every finding fixed and verified on the running unit |
| Factory SD image | Builds and passes its checks in CI; not yet test-flashed or published |
| Built, rolling out to the unit | Visitor counts for the public page (counts, not tracking), fleets on the radar's setup page, setting up from the app; the kiosk's switch to the core feed |
| Cases | Retro and Kitten: heat-set insert posts, a twin antenna mount (1090 and 978 MHz, or external antennas), cleaner speaker grilles |
| Next up | Factory image test, the Watch on a real wrist, hardware v2 (light sensor, bezel), a second receiver for 978 MHz |

## What it does

Point an RTL-SDR dongle and a small antenna at the sky, and StratoScan turns
whatever ADS-B traffic it hears into a live circular radar display: bearing,
range, altitude, speed, heading, airline, aircraft type, route, and (when
available) a real photo of the airframe. It's designed to run unattended,
full-screen, on a small round touch panel — on a wall, or in the printed desk
cradle — but it's also just a web page, so it runs fine in a normal browser
too.

- **Live tracking** — polls a local [`readsb`](https://github.com/wiedehopf/readsb)
  instance every second; altitude-coded blips, smooth interpolation between
  polls, a "NO SIGNAL" banner on connection loss
- **Airline & route lookup** — badges each flight with its airline and shows
  its city-pair route where one's known, including multi-stop regional
  rotations
- **Aircraft type & photo** — human-readable type names ("Bombardier Regional
  Jet CRJ-900") and a real photo when one exists, falling back to a
  representative photo of the type
- **Background map** — real terrain, roads, and runway outlines (cached once
  fetched, so a restart doesn't wait on a fresh query), darkened and centered
  on the receiver, with an always-on live weather radar overlay and an
  optional satellite lightning-strike overlay
- **Approach visualization** — a real density heatmap of your home airport,
  built from actually observed landings over time rather than a canned
  flight-path overlay — busier stretches of the corridor read as more
  visually distinct than lightly-used ones, and it keeps sharpening the
  longer the receiver runs
- **Altitude-scaled blips** — a blip grows with altitude, from 0.68x on the
  ground to 1.30x at cruise, so height reads at a glance alongside the
  existing altitude colour. Deliberately not perspective: a higher aircraft
  is further away and would be smaller if this were about distance
- **Sighting counts** — every aircraft tracks how many distinct times this
  receiver has picked it up, and how many of those came within the
  nearby-alert radius; shown as a "SEEN ×N" badge once it's more than one,
  and as fields in the detail panel always
- **Registered-owner lookup** — for aircraft confirmed private (a real
  callsign, just not an airline one), the detail panel shows who the plane
  is registered to, pulled from public aircraft-registry data
- **Nearby-aircraft alert** — auto-pops flight details (with a chime) for
  anything passing within 2 miles of the receiver
- **Lightning proximity alert** — a chime + banner when a satellite-observed
  strike is detected within 15nm of the receiver, independent of the map's
  lightning overlay toggle
- **Rare aircraft alert** — a chime and an auto-popped panel for something
  worth walking outside for: an airframe on a military/government ICAO
  address, or an unusual type (747, A380, C-17, warbirds). Once the receiver
  has met enough traffic to know what normal looks like locally, it also
  flags aircraft it has never seen before
- **Emergency squawk alert** — an unmistakable alert (distinct chime + a red
  auto-popped panel) for 7500 (hijack), 7600 (radio failure), or 7700
  (general emergency)
- **Landing/takeoff highlight** — a bright green ring around the blip and
  label of anything currently landing or departing at your home airport, plus
  an optional quiet chime; pairs with an optional link to LiveATC.net's live
  approach/departure audio
- **Volume, mute, and a choice of alert sound** — every chime above goes
  through one master gain, adjustable up to 300% (with a limiter, so louder
  never means distorted) plus mute, and can play the original synth tones or
  real CC0-licensed recordings: cat sounds for a kitten-cased unit, or a real
  airline cabin chime for anyone — see `sounds/*/CREDITS.md` for what was
  recorded and how
- **Night dimming** — the display darkens between sunset and sunrise,
  computed from the receiver's own coordinates so it tracks the seasons
  without any configuration; alerts can optionally undim it
- **Screensaver** — the panel genuinely powers off after a configurable idle
  period (see [`deploy/`](deploy/)) and wakes on touch, or on an alert if
  you've enabled that
- **Settings menu** — a gear icon opens a menu grouped into short screens
  (Alerts, Map overlays, Display, ATC audio, Device setup) rather than one
  long list; every setting is one tap from the top, and the panel scrolls by
  dragging anywhere on it. Choices persist per-device
- **Configurable home airport** — 433 continental-US airports are bundled, so
  a unit can be moved or given away and re-pointed at a different field. The
  landing highlight, approach heatmap and ATC link all follow it
- **Set up entirely from the touchscreen** — WiFi (with an on-screen
  keyboard), receiver location, home airport, remote access and a factory
  reset, all without a phone or a shell. This is also the recovery path if
  the admin password is ever forgotten
- **First-run provisioning for a device you did not configure** — a unit with
  no known network raises its own `StratoScan-Setup` WiFi and displays what
  to join, what address to open and a claim code. A captive portal makes the
  setup page open automatically on a phone
- **Connectivity status** — a pill at the bottom of the display says whether
  the radar is actually working: online, on a network that is not reaching
  the internet, running its own setup WiFi, or receiving no aircraft data.
  On the device it reports what NetworkManager concludes about the
  connection; viewed remotely it falls back to whether data is still flowing
- **Restart from the screen** — a Restart row under Device setup, so a stuck
  unit does not need someone to find and pull the plug
- **Frozen-display watchdog** — the radar reports each painted frame to a
  local endpoint, and the device restarts the kiosk if the panel is powered
  on but nothing has been drawn for two and a half minutes. Chromium can
  lose its GPU context and stop painting while the page stays alive by every
  other measure, which otherwise leaves a stale radar on screen until
  somebody walks up to it. A blanked screen is not a fault: the watchdog
  checks the panel's real power state first
- **Statistics** — a Settings section that reads the accumulated flight
  history back: how many distinct aircraft have been heard and how many
  separate passes they made, how many came within two miles, and how much
  of it the antenna heard versus only saw through the network comparison.
  Broken down by operator (commercial / private / military — military
  recognised from the address block, so a military aircraft flying a
  civil-looking callsign still counts) and by airframe (heavy jets, jets,
  propeller, helicopters), using the same type database that decides each
  blip's shape. Plus all-time records — farthest contact, closest approach,
  highest, fastest — the busiest hour of the day and the busiest day of the
  week, and the most frequent visitors. The receiver scorecard lives here too
- **Network comparison** (on by default, and switchable off) — outlines the aircraft a public
  ADS-B network can see in your ring that your antenna did not hear, and
  keeps a scorecard of how you compare: overall coverage, which altitude
  bands and which bearings you are blind in, and position freshness against
  the network's. They are tracked, not just plotted: each keeps its identity
  between polls, is dead-reckoned forward from its last fix, and draws a
  dashed trail. Tap one to see what the network knows about it, clearly
  marked as reported rather than received. Measured here, the receiver was hearing 44% of the traffic
  in range, and 8 of the 9 it missed were below 4,000ft — the signature of a
  blocked horizon rather than a deaf receiver
- **Touch detail panel** — tap any aircraft for registration, squawk, vertical
  rate, and more
- **"What was that?"** — a rewind button lists the closest passes of the last
  hour and draws the chosen aircraft's track back onto the radar
- **Notable aircraft** — air ambulances, police, military and historic
  aircraft are labelled from [plane-alert-db](https://github.com/sdr-enthusiasts/plane-alert-db),
  refreshed weekly on each unit. Labels are neutral, and private owners'
  names are never shown
- **Empty-sky screen** — after 30 seconds with nothing overhead, a clock,
  the current weather and today's tally
- **Spoken announcements** (off by default) — a local
  [Piper](https://github.com/OHF-voice/piper1-gpl) voice names what is
  passing, generated on the unit with no cloud speech service
- **Year in review** — per-year counts of what the receiver heard
- **FlightAware feeding** (opt-in) — a setup-page card installs PiAware to
  share this receiver's data with FlightAware; it says plainly that the
  antenna's exact location is shared

### The iPhone app

A native SwiftUI app and widget ([`ios/`](ios/)), paired with a radar by
scanning a QR code on its screen:

- **The same radar in your pocket** — live aircraft, tap for details, and
  a label mode that keeps the map readable on a small screen
- **Alerts wherever you are** — emergency squawks, notable aircraft, low
  aircraft overhead and helicopters, pushed through the relay. Choose which
  kinds you want
- **Live Activity** (opt-in) — when the radar predicts a close pass (within
  2 miles in the next 3 minutes), a countdown appears on the lock screen and
  in the Dynamic Island, and closes itself after the pass
- **Home-screen and lock-screen widget** — how many aircraft are overhead and
  the nearest few; a radar widget for StandBy
- **Every aircraft, not just the ones the antenna hears** — the aircraft a
  public network (adsb.lol) reports are drawn hollow, with a "not heard" count
- **Zoom** — pinch on any spot, down to about a mile; the rings stay true
  distances from the radar. Follow an aircraft, or centre on yourself
- **Compass** — turn and the needle points at an aircraft, with which way it's
  coming from and going
- **Sky view** — hold the phone up and each aircraft's label sits where it is
  in the sky; tap one for its details. Away from home it can show the
  aircraft around you instead (opt-in; see [privacy](docs/privacy.md))
- **Logbook** — what your radar has seen: today, all-time totals, records
  (farthest, closest, highest, fastest), what flies over, when, and the
  regulars
- **Sky view tracks and Find in the sky** — each aircraft's path drawn
  across the sky; from any aircraft on the radar, a big arrow guides you to
  it in the camera view
- **Approaching you** (opt-in) — alerts for aircraft about to pass over
  where *you* are, not just the radar; your location is end-to-end
  encrypted to your own radar
- **Weather and themes** — rain, storms and lightning on the map, and the
  radar's four colour themes (Daylight by default)
- **iPad** — a big radar with details alongside, and a wall mode that dims
  at night
- **No radar yet?** — see live aircraft around you from the public
  adsb.lol network (opt-in), or play the demo
- **Home and away** — on your WiFi the app talks to the radar directly; away
  from home it switches to the radar's public HTTPS page by itself. The away
  address is learned from the radar
- **Demo mode** — a few minutes of real traffic recorded near RDU, so the
  app can be tried without a radar

## How it works

```
[Antenna] → [RTL-SDR dongle] → [readsb] → aircraft.json (local)
                                                 │
                                                 ▼
                                   [StratoScan: fetch + render]
                                                 │
                                                 ▼
                              [Chromium kiosk, full-screen] → [round display]

 Optional, for the phone app:

 [events.py on the unit] ──signed──▶ [relay: Cloudflare Worker + D1] ──APNs──▶ [iPhone]
        (what's worth an alert)        (pairing, push, fleet health)     (alerts, Live Activity)
```

The **relay** ([`relay/`](relay/)) is the project's one server. Units send it
signed events and opt-in health reports; it pairs phones with units and holds
Apple's push key, so no unit ever carries a secret that can act for the whole
fleet. The radar never depends on it: a unit that cannot reach the relay
works exactly as before. What it stores, and for how long, is in
[relay/README.md](relay/README.md).

`readsb` decodes raw ADS-B signals and writes `aircraft.json` to disk.
`index.html` is a single self-contained page — plain HTML/CSS/JS, Canvas for
the radar itself, [MapLibre GL JS](https://maplibre.org/) for the background
map — that polls that file and renders everything. No build step, no
framework, no server-side code beyond a couple of tiny same-origin proxies
(see [`deploy/`](deploy/)) for things browsers can't do directly, like
setting a custom User-Agent.

## Getting started

**Hardware and receiver setup** (Pi, RTL-SDR dongle, antenna, `readsb`
installation) is covered in [`docs/project-spec.md`](docs/project-spec.md),
including a suggested two-wave purchase plan so you can confirm reception
before buying a display.

One thing worth doing before you chase any reception problem: install
[`deploy/blacklist-rtlsdr.conf`](deploy/blacklist-rtlsdr.conf) to
`/etc/modprobe.d/`. The RTL2832U is sold as a TV tuner, so without it the
kernel's DVB-T driver claims the dongle on every plug and fights readsb for
it, producing `error -71` and constant disconnects.

**Running the web app locally**, against a receiver on your network:

```bash
python3 dev-server.py
```

Then open `http://localhost:8000/index.html`. `dev-server.py` proxies
`/tar1090/*` requests to your receiver so the page can be tested with the
exact same relative paths it uses once deployed — edit `PI_HOST` at the top
of the file to point at your own receiver. It's dev-only and isn't part of
the deployed app.

**Deploying as a kiosk**: `index.html` is a static file — copy it to your
receiver's web server docroot (same origin as `readsb`'s own web UI, to avoid
CORS). [`deploy/`](deploy/) has a systemd unit for launching Chromium in
kiosk mode on boot, plus small same-origin services: aircraft photos, the
shared approach-track store, the shared sighting-count store, the display-wake
endpoint, the optional network-comparison proxy, and (only relevant if you
expose the page to the public internet,
e.g. via Tailscale Funnel) a filtering gateway that rounds the receiver's
exact coordinates before they leave your network — see
[Security](#security) below.

**Device setup (optional)**: everything above works on a receiver you
configured yourself. If you want a unit someone *else* can set up — moved to a
new house, or given away — install the setup server:

```bash
sudo sh deploy/install-setup-server.sh
```

That adds a web setup page at `http://<device>/setup`, the same screens on the
radar's own touchscreen, and the pieces that make a device with no network
recoverable. The installer refuses to finish unless it can prove the public
gateway is refusing `/setup`, since that page accepts a WiFi password and a
Tailscale auth key.

How a fresh unit behaves:

1. It finds no known WiFi, so after ~45s it raises `StratoScan-Setup`
2. Its screen shows that network's name and password, the address to open,
   and an 8-character claim code
3. A phone joining that network gets the setup page automatically, via the
   captive portal
4. WiFi, receiver location, home airport and an admin password are set; the
   setup screen disappears

The same things can be done on the touchscreen instead, which is the only
route if the admin password is ever forgotten. **Erase everything** clears the
WiFi, the Tailscale identity, the password, the coordinates *and* the
accumulated flight history and approach heatmap — the last two are a record of
what flew over the previous owner's house — then raises the hotspot so the
next person can claim it.

Two services run as `systemctl --user` rather than system units (the
screensaver and display-wake endpoint) because they need the graphical
session's `WAYLAND_DISPLAY`. A `stratoscan-netwatchdog` timer rolls back any
unconfirmed network change at boot and raises the hotspot when there is no
usable connection — so a mistyped WiFi password reverts itself rather than
stranding the device.

**The 4am restart, and why it is a workaround.** Chromium on this platform
leaks unlinked `/dev/shm` mappings at roughly 200–300 MB/h of daytime
rendering. Left alone it fills the 4GB tmpfs in five to twelve hours, GPU
allocations start failing with `TransferBuffer::Initialize() failed`, and the
panel freezes on a stale frame — twice in one 34-hour stretch here.
`stratoscan-kiosk-restart.timer` restarts the kiosk at 04:00, when the panel
is already blanked and the sky is empty, returning `/dev/shm` from ~2GB to
~200MB. The frozen-display watchdog in `wake-listener.py` stays as the
backstop.

A second timer, `stratoscan-shmguard`, closes the gap the daily restart
leaves: it samples every five minutes and acts on the measurement rather than
the clock. **It reloads the page before it restarts the browser.** Tearing
down the document releases a third to a half of the accumulated shared memory
(151MB → 72MB and 124MB → 79MB, measured) without killing Chromium — no black
screen, no risk of coming back windowed — and the restart is kept as the
escalation for when a reload is not enough. Two marks, because a restart is only free when nobody is
looking — at **900MB it restarts only while the panel is blanked**, so most
restarts happen invisibly, and at **1500MB it restarts regardless**, which is
the one that actually prevents the freeze. It measures both `/dev/shm` usage
and the sum of Chromium's renderer shm mappings and acts on whichever is
larger, because the two diverge: `/etc/chromium.d/dev-shm` adds
`--disable-dev-shm-usage` when `/dev/shm` has under 3.8GB free at launch, so
after one bad day Chromium moves its backing to `/tmp` and the `df` number
stops tracking the leak. Restarts are rate-limited to one per 30 minutes — if
something other than the leak fills the arena, a guard that restarts forever
is worse than the freeze it was written to prevent. The 04:00 restart runs
through the same script (with `SHMGUARD_FORCE=1`) so both share that one rate
limit.

**Chromium must not be restarted while the panel is blanked.** It comes up
windowed — tab bar, address bar, desktop wallpaper — even with `--kiosk` on
its command line, because it cannot take an output that is off and does not
retry when the output returns. Reproduced both ways on the device: panel off
gives a windowed browser every time, panel on gives fullscreen every time.
This mattered most for the 04:00 restart, which by design runs when the
screensaver has blanked the panel, so it would have left the display windowed
every morning. The guard now wakes the panel, restarts, waits for Chromium to
take the display, and only then puts the panel back as it found it.

It also **repairs a windowed browser however it happens**, not just when the
guard itself caused it — that is the failure a recipient would simply live
with. Every run it grabs the screen and measures the top-left corner:
fullscreen reads 0 on this panel, windowed reads 232, so the threshold sits
at 60 with a wide margin. Verified by breaking it deliberately and watching
the guard put it back.

**A reload cannot be delivered while the panel is blanked**, and that took
two wrong diagnoses to see. The instruction rides the paint heartbeat, and
`reportPainted()` is driven by `requestAnimationFrame` — with nothing being
composited there are no frames, so the page never posts `/wake/alive` and
never collects the flag. Six attempts told the story cleanly: five with the
panel off freed 0MB each, with the listener logging no delivery at all, while
the one with the panel on freed **597MB of 700MB**.

The apparent pattern before that — "reloads stop working above ~600MB" — was
an artifact: every failed attempt happened to be panel-off. Memory level was
never the variable.

So the guard reloads only when the panel is on (at 700MB), and when the panel
is off it restarts outright at 600MB, which is invisible precisely because
the panel is off. A restart at 1400MB remains the backstop with the panel on.

The reload is requested without any control channel of its own. The page
already POSTs `/wake/alive` every 20 seconds as the frozen-display heartbeat;
the guard drops a file in `$XDG_RUNTIME_DIR`, and the listener answers that
next heartbeat with `{"reload":1}` instead of `204`. So there is no debug
port, no key-injection helper and no new listener: only a local process
running as the kiosk user can ask for a reload. Nothing is lost by reloading —
sightings, statistics and the approach heatmap all live in the server-side
stores — beyond trails and ghost tracks, which rebuild within a sweep.

It is a workaround and not a fix, because the cause is not in this codebase:
a blank page leaks the same way, the mappings are invisible to Chromium's own
`memory-infra` accounting, and a critical memory-pressure signal reclaims
none of them. Removing the map, the weather overlays and the canvas render
loop each failed to stop it. One caveat worth keeping in view: the observed
time-to-freeze was as short as 5.2 hours, so a single daily restart is not
guaranteed to cover a long, busy day on its own.

**The enclosure**: [`enclosure/`](enclosure/) has two printable cases for the
same hardware — the original ship's-instrument look, and one shaped like a
sitting cat with the round display as its face, printed in two colours. Both are parametric OpenSCAD,
everything deriving from the measured values at the top of each file. Each
folder's README covers how to export the parts, the interference checks, and
the dimensional mistakes that are easy to repeat.

**iOS app**: `ios/` is an [XcodeGen](https://github.com/yonaskolb/XcodeGen)
project (app plus widget extension, iOS 17.2 or later). Run `xcodegen generate`
inside `ios/` if you change `project.yml`, then open `StratoScan.xcodeproj` in
Xcode. To build your own, set your signing team, bundle id and App Group in
`project.yml`. On the radar, open Settings › Phone & Watch to show a pairing
code, then scan it from the app. Push alerts need your own relay and an APNs
key (see [relay/README.md](relay/README.md)); without them the app still
shows the live radar.

**Relay**: a Cloudflare Worker on the free plan. From `relay/`:
`npm test`, then `npm run db:init && npx wrangler deploy`. Apple's `.p8` key
goes in with `wrangler secret put APNS_KEY`, never into the repo.

## Project structure

```
index.html      the whole web app — single file, no build step
dev-server.py   local-only dev proxy (not deployed)
deploy/         systemd units, same-origin services, events, pairing and the setup server
docs/           roadmap, spec, privacy policy, gifting guide, screenshots
enclosure/      parametric OpenSCAD source for the printed cases (two designs)
tests/          regression tests for the security-critical paths
vendor/         vendored MapLibre GL JS (self-hosted, no CDN dependency)
sounds/         CC0 audio for the alert sound themes (see sounds/*/CREDITS.md)
ios/            native SwiftUI app, widget and Live Activity
relay/          Cloudflare Worker: pairing, push, fleet health
scripts/        signed release script
image/          factory SD-card image build (run in CI)
```

See [CHANGELOG.md](CHANGELOG.md) for release notes and
[HANDOFF.md](HANDOFF.md) for the detailed development history.

## Data sources

StratoScan leans entirely on free, no-key-required public data, same as
[tar1090](https://github.com/wiedehopf/tar1090) (GPL-2.0-or-later; it inspired
several of these choices, but no code is shared):

- **[readsb](https://github.com/wiedehopf/readsb)** — ADS-B decoding
- **[MapLibre GL JS](https://maplibre.org/)** (BSD-3-Clause, vendored under [`vendor/`](vendor/) — self-hosted, no CDN dependency) + **[OpenFreeMap](https://openfreemap.org/)** — background map tiles/style
- **[OpenStreetMap](https://www.openstreetmap.org/) via Overpass** — real runway/taxiway geometry
- **[adsb.im](https://adsb.im/)** — route (city-pair) lookups
- **[RainViewer](https://www.rainviewer.com/)** — live weather radar overlay (their API is free for personal/educational use only)
- **[planespotters.net](https://www.planespotters.net/)** — aircraft photos
- **[Wikimedia Commons](https://commons.wikimedia.org/)** — representative type photos when no tail-specific one exists, credited with author and license
- **[adsbdb.com](https://www.adsbdb.com/)** — registered-owner lookups for confirmed-private aircraft
- **[LiveATC.net](https://www.liveatc.net/)** — ATC audio for the configured airport, opened as a link to their own player (see [Security](#security) below for why it's a link, not an embed)
- **[SSEC RealEarth](https://realearth.ssec.wisc.edu/)** (UW-Madison) — satellite-observed lightning strike density (GOES-East GLM)
- **[Protomaps](https://protomaps.com)** OpenStreetMap builds (© OpenStreetMap contributors, ODbL) — the per-unit offline fallback map built by [`deploy/offline-map.py`](deploy/offline-map.py)
- **[OurAirports](https://ourairports.com/data/)** (public domain) — the bundled airport table in [`deploy/airports.json`](deploy/airports.json)
- **[plane-alert-db](https://github.com/sdr-enthusiasts/plane-alert-db)** (ODbL) — the notable-aircraft list
- **[tar1090-db](https://github.com/wiedehopf/tar1090-db)** — aircraft type and registration from the ICAO address, read from the unit's own tar1090 install
- **[Open-Meteo](https://open-meteo.com/)** — current weather on the empty-sky screen (free for non-commercial use)
- **[adsb.lol](https://adsb.lol/)** — community-run ADS-B aggregation, used only by the network comparison, which can be switched off. Queried at most once every 15s no matter how many people are viewing, with coordinates rounded to ~1.1km

Every obligation these carry, and how each is met, is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Please respect each
service's own terms if you build on this; RainViewer in particular is not
for commercial use.

## Security

If you expose this beyond your own LAN (e.g. a Tailscale Funnel URL, like the
live deployment this repo was built against), a few things are worth knowing
before you do:

- **The receiver's exact coordinates are not something you want publicly
  reachable.** `readsb`'s own `receiver.json` endpoint returns
  survey-precision lat/lon, and by default that's reachable by anyone who
  finds the URL. [`deploy/funnel-gateway.py`](deploy/funnel-gateway.py) sits
  in front of whatever you expose publicly and rounds those coordinates to
  ~0.7 mile precision for public traffic only — your LAN/kiosk always sees
  the exact value, which `readsb` itself needs for its own signal-range math.
  Point your public tunnel at this gateway instead of at `readsb`/lighttpd
  directly. The gateway also strips each aircraft's distance and bearing
  *from the antenna* (`r_dst`, `r_dir`) out of the public `aircraft.json`:
  with two or three aircraft positions, those fields pinpoint the receiver, which undid the rounding entirely.
- **External data (route text, photo credits, aircraft type) is escaped
  before it touches the DOM.** Some of it — a photographer's display name on
  planespotters.net, for instance — is third-party user-submitted content
  this app doesn't control.
- **The shared same-origin stores are read-only for public traffic.**
  `deploy/approach-store.py` and `deploy/sighting-store.py` have no
  authentication of their own, which was fine while only the LAN could reach
  them. Once the page is exposed through a tunnel they become writable by
  anyone holding the URL — confirmed by injecting a fake sighting through it
  — so the gateway now refuses any non-GET to `/sightings` and `/approaches`
  from public traffic (`READ_ONLY_PUBLIC_PATHS`). Reads stay open, because
  public viewers need them; the kiosk and LAN still write normally. They also
  cap request body size and validate input shape.
- **Privileged endpoints are refused for public traffic**, and the check
  normalises the path first. `/wake` (which powers the kiosk's panel on) and
  `/setup` are listed in `LOCAL_ONLY_PATHS` in
  [`deploy/funnel-gateway.py`](deploy/funnel-gateway.py) and 404 for anything
  arriving through the tunnel. The normalising matters: an earlier version
  compared the raw path, and because lighttpd percent-decodes and collapses
  traversal before routing, `/./wake`, `/x/../wake` and `/%77ake` all reached
  the endpoint anyway. [`tests/test_funnel_gateway_paths.py`](tests/test_funnel_gateway_paths.py)
  pins the behaviour — run it after touching that filter.
- **The setup server is split across a privilege boundary.** The HTTP tier
  runs unprivileged and can only ask a small root helper
  ([`deploy/setupd.py`](deploy/setupd.py)) to perform a closed list of verbs
  over a unix socket — there is no "run nmcli" passthrough, so compromising
  the HTTP parser does not yield arbitrary root. The root helper re-validates
  every parameter rather than trusting the caller, uses no shell, and keeps
  secrets out of argv (where any local user could read them from `/proc`).
  [`tests/test_setupd_validation.py`](tests/test_setupd_validation.py) pins
  the validation table and the `/etc/default/readsb` rewriter, which is a
  root-sourced shell file and therefore a command-execution sink.
- **On-device setup deliberately needs no password**, and the endpoint behind
  it is bound to loopback and not proxied, so reaching it means already being
  on the device. That is the same physical assumption every appliance makes,
  and it has to be true: it is the only way back in for someone who has
  forgotten the admin password. The web route, which *is* reachable across
  the LAN, still requires it.
- **Erasing a unit removes the accumulated data too.** The flight history
  and approach heatmap are a record of which aircraft passed over the
  previous owner's house — and the history now carries each aircraft's
  callsign and classification alongside its counts, which makes it more
  identifying than a bare tally, not less — so a full reset clears them
  along with the credentials and coordinates. A settings-only reset keeps them, and keeps
  the network, so it is safe to run remotely.
- **The network comparison is on by default and sends only a rounded
  position.** It can be switched off in Settings, and switching it off stops
  the device contacting adsb.lol at all. The device-side proxy makes
  no request of its own — it only fetches when a page with the setting on
  asks it to — and it queries with coordinates rounded to 2dp, the same
  precision the public gateway already exposes. Asking a stranger "what is
  near me" with survey-precision coordinates would undo the rounding the
  rest of this project does deliberately. `/network` is readable publicly
  but refuses writes, so nobody holding the URL can drive traffic at a
  community-run service on this device's behalf.
- **The display-wake endpoint answers only the device itself.** lighttpd
  refuses `/wake` from anything but `127.0.0.1` and `::1`, so a LAN device
  cannot power the panel on or fake the frozen-display heartbeat.
- **SSH is key-only.** The installer drops
  [`deploy/10-stratoscan-ssh.conf`](deploy/10-stratoscan-ssh.conf) into
  `sshd_config.d`: no passwords, no root login, no X11 forwarding. It
  validates the config with `sshd -t` before reloading.
- **Downloaded code is pinned.** The Piper speech engine installs with
  `pip --require-hashes` from
  [`deploy/tts-requirements.txt`](deploy/tts-requirements.txt), and its voice
  model is checked against [`deploy/tts-voice.sha256`](deploy/tts-voice.sha256).
- **Units and phones prove who they are to the relay.** Every unit request is
  signed with the unit's own Ed25519 key, and every phone request with a key
  generated on the phone. Pairing takes a one-time code shown on the radar's
  screen, which expires in 10 minutes or after five wrong guesses. Only a
  hash of it is stored.
- **No secrets in the repository or on units.** The radar's data sources are
  free and keyless (see [Data sources](#data-sources) above). The one secret
  the project has, Apple's push key, lives only in the relay as a Cloudflare
  secret.
- **ATC audio is a link, not an embed.** LiveATC.net's
  [Terms of Use](https://www.liveatc.net/legal/) require consulting them
  before linking directly to a raw audio stream, and separately bar making
  their service "directly available" through another dedicated application,
  for profit or not. The ATC toggle opens their own player page in a normal
  browser tab instead — ordinary use of their site, same as bookmarking it
  yourself — and is disabled outright on the kiosk itself (`?kiosk=1` on its
  launch URL), since a new browser window/tab inside `--kiosk` Chromium has
  no touch-reachable way back to the radar.

## License

StratoScan™ and the StratoScan logo are trademarks of Michael Ferris.
© 2026 Michael Ferris.

The code is MIT — see [LICENSE](LICENSE). The StratoScan name, logo and icons are not:
they identify the project, so a fork should use its own (see
[assets/brand/LICENSE](assets/brand/LICENSE)). Third-party components and data sources keep
their own licenses and terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Setting one up somewhere else

The first build assumed the continental US in more places than was obvious,
and each one was a hard stop rather than a rough edge:

- **Coordinates were forced into the northern and western hemispheres.** The
  setup page and the touchscreen both "helpfully" made latitude positive and
  longitude negative, on the reasoning that a sign left off a US coordinate is
  unambiguous. It is — and it silently moved a receiver in the Netherlands
  (4.49°E) to 4.49°W, in the Atlantic, while making the entire southern
  hemisphere unreachable. `setupd` agreed, rejecting anything outside
  24–49.5°N and 66.5–125°W as "outside the continental US".
- **The airport list was 433 US airports.** Now 3,269 worldwide (large and
  medium fields with scheduled service, from OurAirports), so Schiphol and
  San Carlos are both a search away.
- **Time zone and WiFi region were baked into the image** as
  America/New_York and US, with no way to change either from setup. A unit
  abroad timestamped every sighting wrongly and ran its radio on the wrong
  channel set.
- **The lightning overlay is GOES-East**, which only sees the Americas.
  Outside that footprint every tile is a 404, so the setting now hides itself
  and says why rather than offering a toggle that cannot work.

**Location is entered as an address by default.** Nobody knows their
coordinates; everybody knows their address. The lookup runs on the *device*
rather than in the browser, because during first-time setup the phone is
joined to the device's own hotspot and has no route to the internet, while
the Pi was put on WiFi in the previous step — a browser-side lookup would
fail exactly when it is needed. The address reaches OpenStreetMap's
Nominatim and nothing else, the position it returns stays on the device, and
typing coordinates by hand remains one tap away for anyone who would rather
not send an address anywhere.

Picking the home airport sets the country, which seeds the time-zone step
with the one or two zones that country actually uses instead of all 485, and
sets the WiFi regulatory region to match. Both the phone page and the
touchscreen can complete setup on their own.

**The WiFi region only takes effect after a restart**, and both UIs say so.
Two things about `raspi-config nonint do_wifi_country` were found by running
it on the device rather than reading about it:

- **It exits non-zero on success.** Its NetworkManager and `wpa_cli` steps try
  to reach a session message bus, which does not exist when the call comes
  from a daemon, so it prints an error and returns 1 *after* writing the
  setting. Judging it by its exit code reports failure for a change that
  worked, so the result is judged by reading the value back instead.
- **The running regulatory domain does not change.** The Pi's Broadcom radio
  registers a custom regulatory table — `phy#0` reports `country 99` — so the
  driver overrides `iw reg set` and the global domain reads `98` until the
  next boot, when `cfg80211.ieee80211_regdom` on the kernel command line
  applies it for real.

The change is safe to make over WiFi: tested on a live link, the SSID, IP
address, connectivity, channel and an active SSH session were all unaffected
throughout.

Because it needs a restart, both surfaces offer one — but **only when the
region actually changed**. `set_wifi_country` reads the country before and
after and reports `changed`, so re-saving the same region never sends anyone
to power-cycle a working device. The prompt says the setting is stored, that
the radio still follows the old region until then, and that nothing else is
waiting on it, so leaving it until the next power-on is a legitimate choice
rather than an unfinished step.

## Updating a unit that has been given away

A gifted radar cannot be fixed by SSH, so it can update itself — carefully.

**Signed, or refused.** A release is accepted only if its manifest carries an
Ed25519 signature (`ssh-keygen -Y`) from the key in
`deploy/allowed_signers`, which is baked in before a unit ships. The private
half lives on the maintainer's machine and never touches a device, GitHub, or
CI. GitHub is delivery, not trust: a compromised account or token could
publish a release, it could not sign one. `ssh-keygen` rather than minisign or
gpg because it is already installed — no new dependency on a box nobody can
log into.

**Newer, or refused.** The device compares an integer serial, not a version
string. An old release stays correctly signed forever, so without this a unit
could be walked backwards onto a build whose bugs are already fixed.

**It undoes itself.** After installing, the display must paint a frame within
90 seconds or the previous files go back and the kiosk restarts again. This
reuses the heartbeat the frozen-display watchdog already depends on, so an
update that blanks the screen is caught by the thing already watching the
screen — with nobody in the room. Verified by signing and applying a build
that throws before rendering: it was staged, installed, failed to paint, and
rolled back, and the previous `index.html` came back byte-identical.

**It cannot install anywhere it likes.** Only an allowlisted set of
destinations is writable, which excludes `allowed_signers` itself — an update
must not be able to replace the key that vouches for it, or one bad release
owns the device forever.

Checking is a timer (twice a day, randomised). **Installing is a deliberate
act** from the settings screen or the setup page: a unit that silently
replaced its own software overnight would be a different thing to give
somebody. Neither surface ever claims "up to date" for a device that has
simply never looked.

The manifest carries each file's **executable bit** as well as its hash, and
only that bit — a manifest that could set arbitrary permissions on root-owned
files would be a much larger thing to sign off on than one that can say "this
is a program". It is there because the first real update installed a new
`ota.py` without its executable bit and broke its own updater; the services
survived only because their units run `python3 <script>` rather than exec'ing
it.

The paint check refuses to run at all if the heartbeat file is missing, rather
than rolling back every update. That, too, is from experience: the stamp
originally lived in `/run/stratoscan`, which is setupd's `RuntimeDirectory=`
— systemd recreates it root-owned whenever the root helper restarts, so the
kiosk user silently lost the ability to write it, and a perfectly good release
was reverted because nothing could record that the screen was painting. It now
lives in the kiosk user's own runtime directory.

To cut a release: `sh scripts/release.sh <version>`. It builds the bundle,
writes a manifest of per-file hashes, signs it, **verifies its own output with
the public key the devices carry**, and only then publishes to GitHub
Releases.

**Changed services are restarted.** A long-running service keeps its old code
until it restarts, and the updater originally restarted only the kiosk — so a
security fix to `funnel-gateway.py` was reported installed while the old
gateway kept running for hours. It now compares each file with the one it
replaces and restarts exactly the services whose code changed (and restarts
them again on a rollback). Like any change to `ota.py`, that behaviour starts
with the release *after* the one that installs it.

The serial is the commit count, so two releases cut from the same commit carry
the same serial and the second is refused as "not newer" — commit first.

## Built to run for ten years

Measured on the first unit and reviewed for a decade of unattended running at
busy sites (SFO, Schiphol) as well as quiet ones:

- **SD card wear.** The stores keep their data in memory and write at most
  every 10 minutes and on shutdown; they used to rewrite the whole file on
  every sighting (3.5 GB in 17 hours, ~100 GB/day at a busy site once full).
  Chromium's HTTP cache lives in RAM, and it keeps no shader cache on disk.
  Dirty pages are batched for two minutes before writeback. The history store evicts the aircraft
  seen *least recently*, so daily regulars survive a full store. Measured in
  steady state: 2.25 GB/day, about 8 TB over ten years, well under a 128 GB
  high-endurance card's rating.
- **Recovery without a person.** The hardware watchdog reboots a hung kernel;
  `kernel.panic=10` reboots a panicked one. `net-watchdog.py` also restarts
  `readsb` when its output goes stale and reboots after repeated failed
  restarts, and reboots when the frozen-display watchdog's browser restarts
  keep failing — never more than once every 6 hours, so a fault a reboot
  cannot fix degrades to a few reboots a day, not a loop.
- **A hung radio is power-cycled, not just rebooted.** The Pi 5 keeps USB
  power on through a reboot, so a wedged SDR stays wedged. Before rebooting,
  the watchdog cuts USB power with [uhubctl](https://github.com/mvp/uhubctl)
  for a few seconds and turns it back on (at most once every 30 minutes).
- **Security updates** via unattended-upgrades (Debian security and point
  releases, the Raspberry Pi archive, Tailscale), holding Chromium, the
  kernel and firmware — a bad unattended update to those strands a unit.
- **An offline map.** When the location is set or changed, the unit
  downloads its own area (2–7 MB) from [Protomaps](https://protomaps.com)'
  OpenStreetMap builds into `/offline-map/`, and the page falls back to it
  whenever OpenFreeMap can't be reached — so a dead tile service or a boot
  before WiFi is up shows a real map, not a blank disc.

These system-level pieces (unattended-upgrades, sysctl, unit files) are
installed by `deploy/install-setup-server.sh`, never by an update — re-run it
on any unit before it leaves the house. What remains is hardware: an RTC
battery (ML-2020, with `dtparam=rtc_bbat_vchg`) keeps the clock across power
cuts, and a high-endurance SD card or an NVMe drive is the better medium for
a decade.
