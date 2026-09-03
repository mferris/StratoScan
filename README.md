# FlightRadar

A live ADS-B flight radar for a wall-mounted round display, built on a
Raspberry Pi and a cheap SDR dongle — no subscription, no cloud service,
just a local receiver and a browser.

![FlightRadar running on the physical kiosk display](docs/screenshots/kiosk.png)

## What it does

Point an RTL-SDR dongle and a small antenna at the sky, and FlightRadar turns
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
  no known network raises its own `FlightRadar-Setup` WiFi and displays what
  to join, what address to open and a claim code. A captive portal makes the
  setup page open automatically on a phone
- **Connectivity status** — a pill at the bottom of the display says whether
  the radar is actually working: online, on a network that is not reaching
  the internet, running its own setup WiFi, or receiving no aircraft data.
  On the device it reports what NetworkManager concludes about the
  connection; viewed remotely it falls back to whether data is still flowing
- **Restart from the screen** — a Restart row under Device setup, so a stuck
  unit does not need someone to find and pull the plug
- **Touch detail panel** — tap any aircraft for registration, squawk, vertical
  rate, and more
- **Native iOS companion app** — a SwiftUI rebuild of the same radar for
  iPhone, talking to the same receiver over Tailscale

## How it works

```
[Antenna] → [RTL-SDR dongle] → [readsb] → aircraft.json (local)
                                                 │
                                                 ▼
                                   [FlightRadar: fetch + render]
                                                 │
                                                 ▼
                              [Chromium kiosk, full-screen] → [round display]
```

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
endpoint, and (only relevant if you expose the page to the public internet,
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

1. It finds no known WiFi, so after ~45s it raises `FlightRadar-Setup`
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
session's `WAYLAND_DISPLAY`. A `flightradar-netwatchdog` timer rolls back any
unconfirmed network change at boot and raises the hotspot when there is no
usable connection — so a mistyped WiFi password reverts itself rather than
stranding the device.

**The enclosure**: [`enclosure/`](enclosure/) has two printable cases for the
same hardware — the original ship's-instrument look, and one shaped like a
sitting cat with the round display as its face. Both are parametric OpenSCAD,
everything deriving from the measured values at the top of each file. Each
folder's README covers how to export the parts, the interference checks, and
the dimensional mistakes that are easy to repeat.

**iOS app**: `ios/` is an [XcodeGen](https://github.com/yonaskolb/XcodeGen)
project. Run `xcodegen generate` inside `ios/` if you change `project.yml`,
then open `FlightRadar.xcodeproj` in Xcode. Set your own signing team under
Signing & Capabilities, and point it at your receiver's address in the app's
Settings screen.

## Project structure

```
index.html      the whole web app — single file, no build step
dev-server.py   local-only dev proxy (not deployed)
deploy/         systemd units, same-origin services, and the setup server
docs/           hardware/software spec, original prototype, screenshots
enclosure/      parametric OpenSCAD source for the printed cases (two designs)
tests/          regression tests for the security-critical paths
vendor/         vendored MapLibre GL JS (self-hosted, no CDN dependency)
ios/            native SwiftUI companion app
```

See [CHANGELOG.md](CHANGELOG.md) for release notes and
[HANDOFF.md](HANDOFF.md) for the detailed development history.

## Data sources

FlightRadar leans entirely on free, no-key-required public data, same as
[tar1090](https://github.com/wiedehopf/tar1090) (which inspired several of
these choices, though no code is shared — its license is unclear):

- **[readsb](https://github.com/wiedehopf/readsb)** — ADS-B decoding
- **[MapLibre GL JS](https://maplibre.org/)** (BSD-3-Clause, vendored under [`vendor/`](vendor/) — self-hosted, no CDN dependency) + **[OpenFreeMap](https://openfreemap.org/)** — background map tiles/style
- **[OpenStreetMap](https://www.openstreetmap.org/) via Overpass** — real runway/taxiway geometry
- **[adsb.im](https://adsb.im/)** — route (city-pair) lookups
- **[RainViewer](https://www.rainviewer.com/)** — live weather radar overlay
- **[planespotters.net](https://www.planespotters.net/)** — aircraft photos
- **[Wikipedia / Wikimedia Commons](https://www.wikipedia.org/)** — representative type photos when no tail-specific one exists
- **[adsbdb.com](https://www.adsbdb.com/)** — registered-owner lookups for confirmed-private aircraft
- **[LiveATC.net](https://www.liveatc.net/)** — ATC audio for the configured airport, opened as a link to their own player (see [Security](#security) below for why it's a link, not an embed)
- **[SSEC RealEarth](https://realearth.ssec.wisc.edu/)** (UW-Madison) — satellite-observed lightning strike density (GOES-East GLM)
- **[OurAirports](https://ourairports.com/data/)** (public domain) — the bundled airport table in [`deploy/airports.json`](deploy/airports.json)

Please respect each service's own terms of use if you build on this.

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
  directly.
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
- **Erasing a unit removes the accumulated data too.** The sighting counts
  and approach heatmap are a record of which aircraft passed over the
  previous owner's house, so a full reset clears them along with the
  credentials and coordinates. A settings-only reset keeps them, and keeps
  the network, so it is safe to run remotely.
- **No secrets or API keys anywhere.** Every external service this app talks
  to is free and keyless (see [Data sources](#data-sources) above), so
  there's nothing to leak.
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

MIT — see [LICENSE](LICENSE).
