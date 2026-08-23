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
full-screen, on a small round touch panel mounted on a wall — but it's also
just a web page, so it runs fine in a normal browser too.

- **Live tracking** — polls a local [`readsb`](https://github.com/wiedehopf/readsb)
  instance every second; altitude-coded blips, smooth interpolation between
  polls, a "NO SIGNAL" banner on connection loss
- **Airline & route lookup** — badges each flight with its airline and shows
  its city-pair route where one's known, including multi-stop regional
  rotations
- **Aircraft type & photo** — human-readable type names ("Bombardier Regional
  Jet CRJ-900") and a real photo when one exists, falling back to a
  representative photo of the type
- **Background map** — real terrain, roads, and runway outlines, darkened and
  centered on the receiver, with a live weather radar overlay
- **RDU approach visualization** — a faint outline tracing real accumulated
  landing tracks, built up from actual observed traffic over time
- **Nearby-aircraft alert** — auto-pops flight details (with a chime) for
  anything passing within a couple of miles of the receiver
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
kiosk mode on boot, plus the two small same-origin proxy services (aircraft
photos, and a shared store for the accumulated approach-track visualization).

**iOS app**: `ios/` is an [XcodeGen](https://github.com/yonaskolb/XcodeGen)
project. Run `xcodegen generate` inside `ios/` if you change `project.yml`,
then open `FlightRadar.xcodeproj` in Xcode. Set your own signing team under
Signing & Capabilities, and point it at your receiver's address in the app's
Settings screen.

## Project structure

```
index.html      the whole web app — single file, no build step
dev-server.py   local-only dev proxy (not deployed)
deploy/         systemd units + same-origin proxy services for the kiosk
docs/           hardware/software spec, original prototype, screenshots
vendor/         vendored MapLibre GL JS (self-hosted, no CDN dependency)
ios/            native SwiftUI companion app
```

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

Please respect each service's own terms of use if you build on this.

## License

MIT — see [LICENSE](LICENSE).
