# FlightWall — Handoff Notes

## Status
`index.html` is a matured version of `docs/original-prototype.html` that renders
**live** aircraft on the round radar instead of the fake demo data. It has been
tested against the real receiver at `http://<radar>/tar1090/` and confirmed
working: live positions, altitude-coded colors, smooth interpolation between
1s polls, a "NO SIGNAL" banner on connection loss (tested by killing the feed),
and clean recovery on reconnect.

It is now **deployed and running on the Pi** (`flightwall`, `<radar>`,
the login user) as a Chromium kiosk launched by systemd, verified to survive a
full reboot with no manual intervention.

## Display center override
`index.html` has a `HOME_OVERRIDE` constant that, when set, centers the
radar/map/runway lookup on a fixed point instead of the receiver's real
position — deliberately **display-only**, never touching `readsb`'s actual
configured position (`/etc/default/readsb`, `--lat`/`--lon`), which needs to
stay accurate to the real antenna for its own signal-range/MLAT math.

**Currently `null`** — back to auto-detecting the real receiver position
from `receiver.json` (confirmed to be **[address redacted]** — its
geocoded coordinates, [lat-redacted]/[lon-redacted], match readsb's configured
~[lat-redacted]/[lon-redacted] to within normal geocoding precision). It was briefly set to
[address redacted], Durham NC for a one-off request, then reverted.

If it's ever set again: `loadHome()` skips fetching `receiver.json` and uses
the override synchronously instead, and `normalizeAircraft()` always
computes bearing/range via haversine from raw lat/lon rather than trusting
readsb's precomputed `r_dst`/`r_dir` — those are relative to the *real*
antenna position, not an override point, and would silently produce a
geometrically-inconsistent display if trusted while overridden. (Verified by
hand while it was active: an aircraft readsb reported `r_dst: 3.77` for
showed up correctly as `14.53` in FlightWall — its true haversine range from
the override point.) Also worth knowing: a override point far from the real
antenna shifts the visible 40nm disc so it only partially overlaps the
antenna's actual reception area.

## Remote access (Tailscale Funnel)
The page is also reachable from outside the local network at
**https://[funnel-hostname-redacted]/** via Tailscale Funnel — publicly
reachable HTTPS, no login/app required for whoever you send the link to, no
router port-forwarding involved. `tailscale` is installed on the Pi, signed
into the maintainer's tailnet, with `tailscale funnel --bg 80` proxying that
public URL to lighttpd on `127.0.0.1:80` (the same server `index.html` and
`/tar1090/` are already deployed to, so this is the exact same page, not a
separate copy). Funnel exposes the **whole** site, not just `index.html` —
`/tar1090/` itself is also reachable at that URL, fine for this use case
since it's just flight data, but worth remembering before deploying anything
more sensitive to this docroot later.
- Check status: `ssh <user>@<radar> tailscale funnel status`
- Turn off: `ssh <user>@<radar> sudo tailscale funnel --https=443 off`
- The Funnel/serve config is stored in tailscaled's persistent state, so it
  should come back automatically on reboot (not yet verified with an actual
  reboot test the way the kiosk service was — worth confirming if this
  matters going forward).

### Hardening done after enabling Funnel
Turning Funnel on prompted a quick look at what else was reachable on the
Pi. Two things worth knowing:
- **readsb's raw/Beast/SBS ports (30001-30005, 30104) are now bound to
  `127.0.0.1` only** (`--net-bind-address 127.0.0.1` added to `NET_OPTIONS`
  in `/etc/default/readsb`, original backed up alongside as
  `readsb.bak`). They used to listen on `0.0.0.0` — reachable from the whole
  LAN — but nothing on the network was actually connected to them, and
  FlightWall/tar1090 don't use them at all (they read the JSON files readsb
  writes to disk, not these TCP ports). If you ever want to feed a live raw
  feed to another device on your LAN (Virtual Radar Server, a second
  receiver dashboard, etc.), you'll need to revert this
  (`sudo cp /etc/default/readsb.bak /etc/default/readsb && sudo systemctl
  restart readsb`).
- **Deliberately left the login user's passwordless sudo as-is.** Requiring a
  password would block the non-interactive SSH commands this whole project's
  deployment workflow depends on. This is a real trade-off, not an
  oversight — revisit if that workflow ever changes (e.g. moving deploys to
  a proper CI pipeline instead of ad-hoc SSH).
- **Network segmentation (router guest network) was suggested but not done**
  — the Pi's on `wlan0` (WiFi, not Ethernet), so a guest network
  feature would apply cleanly, but doing this yourself: it isolates the Pi
  from the rest of the LAN, which also means your other devices lose
  ad-hoc local access to `http://<radar>/` — Tailscale (already set up
  for Funnel) would keep working as the way to reach the Pi afterward,
  network-topology-independent.

The radar also now has a **background map** (MapLibre GL JS, vendored under
`vendor/` — BSD-3-Clause, v5.24.0, self-hosted so the only runtime network
dependency is the tile/style fetch itself). The map is non-interactive
(`interactive: false`), centered on `home`, and zoomed so its visible extent
matches the radar's `RANGE_NM` ring exactly (`zoomForRange()` in
`index.html` derives the zoom level from the standard Web Mercator
meters-per-pixel formula — recomputes correctly if `RANGE_NM` or the
receiver location ever changes, nothing hardcoded). Requires the Pi to have
internet access for tiles (confirmed working); the ADS-B tracking itself has
no such dependency and keeps working if the map layer fails to load (falls
back to the original solid dark background via CSS).

**Style is OpenFreeMap's `liberty`**, not their `dark` style — `dark` turned
out to be near-grayscale by design (checked the actual style JSON: water,
parks, and woods are all defined at ~0% saturation), so no amount of CSS
`saturate()` could pull color out of it. `liberty` has real color (blue
water, green parks, warm orange/yellow road tones) which we darken ourselves
via `#mapbg`'s CSS `filter: brightness(0.3) saturate(1.5)` — tuned live in a
few iterations to land on "still reads as a dark backdrop" without going all
the way back to washed-out or invisible. Since `liberty` is styled for a
light background (place-name labels are black text with a white halo),
`recolorLabels()` flips city/town/village/water-name labels to light
text/dark halo after the style loads, via the same `setPaintProperty`
pattern already used for the runway layer colors — otherwise the labels
would darken along with everything else and become illegible.

The map also shows **real runway outlines** at airports in range (e.g. RDU's
crossing-runway pattern). The OpenFreeMap tileset's own `aeroway-*` layers
turned out to be a dead end — confirmed via `queryRenderedFeatures()` that the
vector tiles simply carry no runway/taxiway geometry below zoom ~11, and our
fixed radar zoom is ~9.7, so raising the style's `minzoom` did nothing (the
data isn't in the tile, not just hidden). Runways instead come from a
one-time query to OSM's public Overpass API (`loadRunways()`, fired once from
`map.on('load', ...)` since the receiver's home location never changes at
runtime), added as our own GeoJSON source/layers — this bypasses the vector
tileset's zoom restriction entirely since a GeoJSON source isn't tile-paginated.
Purely additive: if Overpass is unreachable the map/radar work exactly as
before, just without runway outlines.

Each tracked aircraft now shows a **color-coded airline badge** (full name,
e.g. "Piedmont Airlines" — or "Private Aircraft" for GA/unidentified flights),
a **human-readable aircraft type** (e.g. "Bombardier Regional Jet CRJ-900",
"Bell 429 GlobalRanger"), and its **route** as city names (e.g. "Tampa →
London") when one's known. A few deliberate choices here, worth preserving:
- **No real airline logos.** They're trademarked, and this project is meant
  to be published under MIT — bundling them would ship trademarked assets in
  an openly-redistributable repo. The `AIRLINES` table in `index.html` instead
  has a small hand-picked set of ICAO designators (ICAO Doc 8585, a public
  standard) mapped to a full name/IATA code/loosely-associated color, rendered
  as a generated text badge. Not exhaustive — unmapped carriers just fall
  back to the airline's ICAO code not being in the table (rare); anything
  whose callsign doesn't match the airline-flight-number pattern at all
  (`/^[A-Z]{3}\d/`) gets "Private Aircraft" instead.
- **Route data comes from `https://adsb.im/api/0/routeset`** — the same free,
  no-key API `tar1090` itself already uses on this Pi (confirmed by reading
  `planeObject_*.js`'s `routeDoLookup()` on the box). ADS-B itself carries no
  route info at all. Lookups are batched/cached/throttled in `index.html`
  (`queueRouteLookup`/`flushRouteQueue`) the same way tar1090 does it: one
  POST per `ROUTE_BATCH_MS` (4s), results cached for the rest of the session
  (including negative "no route found" results, so unknown callsigns aren't
  re-queried every cycle). Routes the API itself flags `plausible: false` are
  treated as unknown rather than displayed (tar1090 doesn't bother with this
  check, but showing a route the API itself doubts felt worse than omitting
  it). Displays city names (`_airports[].location`) rather than IATA codes.
- **Aircraft type also has no field in `aircraft.json`** — readsb doesn't
  populate `t`/`desc` there. tar1090 solves this the same way it solves
  routes: a local same-origin database, this time already sitting on the Pi
  as a prefix-trie of small JSON shards under `/tar1090/db-<hash>/` (the hash
  changes whenever tar1090's assets rebuild, so `index.html` discovers the
  current folder name at runtime by regexing it out of `/tar1090/index.html`
  rather than hardcoding it — see `discoverDatabaseFolder()`). `lookupType()`
  walks that trie itself (own implementation, not copied — tar1090's own code
  license is unclear ["Other"/NOASSERTION on GitHub], so this reads the same
  public same-origin data files but isn't a port of their `dbloader.js`).
  Falls back to `icao_aircraft_types2.js` (ICAO type-code -> description) when
  a specific tail's entry has no `typeLong` of its own. `humanizeType()` just
  re-cases ALL-CAPS manufacturer names ("CIRRUS SR-22" -> "Cirrus SR-22")
  without touching model numbers.

**Labels live in a ring around the edge of the dial**, not floating next to
their plane — each label's natural position is its own bearing angle
(`LABEL_RING_RADIUS = R + 60`), eased there via `LABEL_SPRING_TAU` as the
plane moves, and a color-matched SVG leader line (`#leaders`) always
connects the label back to its actual plane position (attached to whichever
edge of the box faces the plane, via `closestPointOnRect()`). Overlap
resolution (`LABEL_SEPARATION_PASSES` iterations) only ever adjusts a
label's *angle* along the ring, never pulls it off — and always resolves
bearing-adjacent neighbors in bearing-sorted cyclic order. That order
preservation is what guarantees leader lines never cross (a standard
property: connecting points on an inner circle to points on an outer ring
in the same cyclic order can't produce crossing chords), not just an
approximation of "minimized." `R` was shrunk from `0.44*W` to `0.38*W` to
free up a real outer band for the ring to live in. One known rough edge:
a label very close to due-north bearing can lightly touch the HUD text at
the top of the stage — rare, and it's a HUD/label interaction rather than
label-on-label overlap, but not yet fixed. This replaced an earlier
version that eased each label toward a fixed offset next to its plane with
plain 2D AABB separation — that avoided label-on-label overlap fine but had
no concept of leader-line crossings at all.

Covers milestones 3–6 and part of 7 from `docs/project-spec.md` — **the round
panel is physically connected now** (HDMI + USB-C touch + its own 5V power via
a USB-C PD charger, confirmed working: `xrandr` shows `HDMI-A-1 connected
1080x1080`, touch enumerates as `Waveshare Waveshare-079-HD` at USB ID
`0712:000a`), and milestone 5 (tap detail panel) is done too. Backlight
brightness has a physical button on the driver board (per Waveshare's docs,
it also supports "HID software dimming" but no public documentation of that
protocol was findable — button is the practical path for now). Not done:
physically mounting the finished enclosure (that's fabrication, not
software).

## Touch interaction (milestone 5)
Tap a plane's blip or label → detail panel (registration, heading, vertical
rate, squawk, precise range/bearing, and now a real photo — see below). Tap
empty space → cycles three display modes (full / map off / map+labels off)
with a toast confirming the mode. Hit-testing is manual coordinate math on
one delegated `pointerup` listener on `.stage`, not per-element
`pointer-events` (the tag divs are `pointer-events:none` by design, and
label positions move every frame anyway). See `findPlaneAtStagePoint()` —
worth knowing: it returns the *first* match in `planes` iteration order, not
the *nearest*, so two blips/labels overlapping within the ~22px hit radius
could occasionally resolve to the "wrong" one of the two. Not fixed, low
stakes (tapping again elsewhere and retrying works fine).

**Aircraft photo**: `deploy/photo-proxy.py` is a small local-only (127.0.0.1)
Python service on the Pi, proxying planespotters.net's photo API — their API
requires a descriptive custom `User-Agent` naming the app, which browser
`fetch()` can never set itself (browsers own that header exclusively), so
this has to happen server-side. `deploy/89-flightwall-photo-proxy.conf`
(lighttpd, `mod_proxy`) routes `/photo/<hex>` to it so the browser's fetch
stays same-origin. Runs as `flightwall-photo-proxy.service`
(`DynamicUser=yes`, no privileges needed), in-memory cache per hex, 24h TTL.
Attribution (required by planespotters.net's terms — photographer credit +
naming the source) is shown as **plain non-clickable text**, not a real
`<a>` link — deliberate, since this same `index.html` also runs unattended
in the kiosk's own Chromium, and risking a tap navigating the kiosk away
from the app with no way back wasn't acceptable, even though a real link
would be fine in a normal browser tab (e.g. via the Funnel URL). Gracefully
shows nothing if planespotters has no photo for that airframe.

## Key facts learned this session
- Receiver home location comes from `http://<radar>/tar1090/data/receiver.json`
  (`lat`/`lon`) — the app fetches this itself at startup rather than hardcoding it.
  Currently ~[lat-redacted]°N, [lon-redacted]°W (Raleigh-Durham area).
- `aircraft.json` entries already include `r_dst` (range, nm) and `r_dir` (bearing,
  deg) precomputed by readsb relative to the receiver — `index.html` uses these
  directly and only falls back to a haversine calc from raw `lat`/`lon` if they're
  ever missing.
- The Pi's web server (lighttpd) does **not** send CORS headers, so `index.html`
  must be deployed same-origin (i.e. copied onto the Pi itself, served from the
  same host as `/tar1090/`) — it uses relative fetch paths (`/tar1090/data/...`)
  for exactly this reason.
- SSH login is `<user>@<radar>` (not `pi` — that user doesn't exist on this
  image). Passwordless sudo is configured for that user.
- The Pi runs full Raspberry Pi OS (Debian 13 "trixie") with a Wayland desktop
  (`labwc` compositor, `rpd-labwc` session), lightdm with autologin already
  configured for that user. Not a Lite/headless image.
- The round display was **not physically connected** during this session (both
  HDMI ports read `disconnected` via `/sys/class/drm/*/status`) — the compositor
  falls back to a virtual/no-op 1920x1080 output. Everything was verified via
  `grim` screenshots of that virtual output; the app has not yet been visually
  confirmed on the real 1080x1080 round panel.

## Deployment (milestone 6 — done)
- `index.html` lives at `/var/www/html/index.html` on the Pi (root-owned,
  lighttpd's docroot), served at `http://localhost/` — same-origin with
  `/tar1090/`, satisfying the CORS constraint above.
- Kiosk launcher is a **systemd user service**, checked into this repo at
  `deploy/flightwall-kiosk.service` and deployed to
  `~/.config/systemd/user/flightwall-kiosk.service` on the Pi (as the login user).
  - Launches `chromium --kiosk ... http://localhost/index.html`
  - `ExecStartPre` waits (up to 60s) for a `wayland-*` socket in
    `$XDG_RUNTIME_DIR` before starting Chromium — needed because the compositor
    isn't up yet at the instant lightdm opens the session. **Important:** don't
    wait on the `$WAYLAND_DISPLAY` env var itself (e.g.
    `-S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"`) — that variable is imported into
    the systemd user manager *after* labwc starts, so a process forked right at
    session-open captures it empty and waits forever. Glob for `wayland-*[0-9]`
    instead.
  - `Restart=always`, `RestartSec=5` for crash recovery.
  - Enabled via `systemctl --user enable` (symlinked into
    `default.target.wants`), plus `sudo loginctl enable-linger <user>` so the
    user's systemd instance starts at boot even before an interactive login
    completes.
- Verified with an actual `sudo reboot`: service came up ~30s after boot with
  zero restarts, no manual login needed, and was rendering live traffic.
- To redeploy `index.html` after future edits:
  `scp index.html <user>@<radar>:/tmp/ && ssh <user>@<radar> 'sudo cp /tmp/index.html /var/www/html/index.html && rm /tmp/index.html'`
  (Chromium will pick it up on next reload/kiosk restart — no service restart
  needed unless the launch flags/URL change.)

## Map/radar alignment bug (found via the trail feature)
Trying out the new trail near RDU surfaced a real bug: the background map's
zoom was miscalibrated, so real ground features (like RDU's runways) rendered
increasingly far from where the radar independently plots aircraft at the
same true bearing/range, the farther from `home` you looked — accurate right
at the center, visibly "shifted" a few nm out. Two compounding causes in
`zoomForRange()`/`initMap()`:
1. The 156543.03392 constant is meters-per-pixel-at-zoom-0 for the classic
   256px slippy-tile convention, but MapLibre/Mapbox GL define zoom for 512px
   tiles (whole world = 512px at zoom 0) — a well-known porting gotcha
   ("Mapbox GL zoom = Leaflet zoom - 1" for the same visual scale). Using the
   256px constant unmodified renders one zoom level too far in, a *scale*
   error (not a fixed offset), so it's small near `home` and grows with
   distance. Fixed by subtracting 1 from the computed zoom.
2. `zoomForRange` was fed `R`, the radar's radius in the canvas's fixed
   1080-unit *internal* space — but MapLibre's zoom is calibrated against the
   container's actual rendered *CSS* pixel size, which only equals 1080 when
   the stage happens to render at exactly 1080px. True on the physical
   1080x1080 kiosk panel (masking this entirely there, which is why it went
   unnoticed until now), but not for anyone viewing the same page at a
   different size via the Funnel URL. `initMap()` now converts `R` to real
   CSS pixels (`R * stage.getBoundingClientRect().width / W`) before calling
   `zoomForRange()`.
Verified by comparing MapLibre's own `map.project([lon,lat])` for RDU's real
coordinates against the radar's independently-computed `polarToXY()` position
for the same point (via `haversineBearingRange()`) — before the fix these
diverged by a factor tied directly to the test viewport's CSS-vs-canvas
pixel ratio (proving cause #2), after fixing both, they match to ~0.1-0.15%
(the tiny residual being genuine, unavoidable Mercator scale variation across
the visible disc, not a bug). Not yet reconciled: zoom is calibrated once at
`initMap()` time and never recalculated, so a browser window resized *after*
load (e.g. via Funnel, on a desktop) would need a reload to stay aligned —
fine for the kiosk itself (fixed physical resolution, never resized), not
yet handled for the general case.

## Per-type aircraft icons + tap-to-show flight path trail
Prompted by looking at tar1090's own map (`http://<radar>/tar1090/`), which
draws distinct shapes for large commercial jets/smaller jets/prop planes and
shows a flight-path trail when you tap a plane.

**Icons**: didn't port tar1090's actual icon set (`markers.js` on the Pi at
`/usr/local/share/tar1090/git/html/markers.js`, ~100+ hand-drawn SVG paths) —
its code license is unclear ("Other"/NOASSERTION on GitHub, same concern
already noted above for the aircraft-type database), and importing ~100
detailed bezier paths would also be needlessly heavy for a canvas redrawn
every frame on a Pi. Instead, `classifyAircraft()` buckets each plane into
`heavy` / `jet` / `prop` / `heli` / `lta` / `unknown` and `drawBlipShape()`
draws a small hand-coded canvas path for each — same kite/arrowhead as always
for `jet`/`unknown` (no visual change for most traffic), just bigger for
`heavy`, a distinct cross/plus silhouette for `prop`, a rotor-ring-plus-tail
for `heli`, an ellipse for `lta`. Classification prefers the specific tail's
ICAO type info when known (`typeDesc`/`wtc`, from the same
`icao_aircraft_types2.js` database `lookupType()` already reads for the
aircraft-type-string feature above — just two more fields off the same
entries, `[typeLong, typeDescription, wtc]`), falling back to the raw ADS-B
`category` field readsb reports per-aircraft (A1 light .. A5 heavy, A7
rotorcraft, B2 lighter-than-air) when type info isn't known yet or at all —
common for GA tails with no database entry.

**Trail**: tar1090's tap-to-show trail comes from readsb's own trace history
(`data/traces/<hex-suffix>/trace_recent_<hex>.json`), but **this Pi's readsb
doesn't have that enabled** — confirmed via `curl` (404) and `find` (no
`trace_*.json` files anywhere on disk). So the trail is built client-side
instead: each poll's already-computed bearing/range (the same values the live
blip uses) gets pushed onto that plane's `p.trail` array in `applyUpdate()`,
pruned to the last 10 minutes (`TRAIL_MAX_MS`). `drawSelectedTrail()` draws it
as a fading polyline, only while the detail panel is open for that plane.
Real limitation, not a bug: **this only covers time since the page was last
loaded** — there's no real flight history before that, unlike tar1090's
server-backed trail. Worth reconsidering if trace storage is ever enabled on
this receiver.

**Bug fix along the way**: `p.bearing` (the smoothed/eased live bearing used
for blip position) was never wrapped back into `[0, 360)` after each frame's
`+= bearingDelta(...)` — harmless for the actual blip *position* since
`Math.cos`/`Math.sin` are periodic, but the detail panel's `Range/Brg` display
could show something like "482°" for a contact that's been tracked long
enough to accumulate past a full revolution (e.g. a tight holding pattern
near the receiver). Found via testing with a synthetic aircraft deliberately
orbiting fast to exercise the new trail code — real traffic would hit this
rarely, but it's a real latent bug. Fixed by wrapping `p.bearing` the same
way `p.labelAngle` already was two lines below it.

**Testing note**: this sandbox's browser preview can reach the public
internet but not the Pi's private LAN address (<radar>) — `dev-server.py`'s
proxy got `No route to host` even though direct `curl`/`ssh` from a shell
in the same session worked fine. Verified instead with a small mock server
(`/tar1090/data/*` stubbed with synthetic aircraft spanning every category)
so all five shapes and the trail could actually be checked visually and via
canvas pixel sampling, rather than waiting for real traffic to happen to
include a helicopter or blimp. Deployed and confirmed byte-identical on the
Pi, but not yet visually confirmed against live traffic in a real browser —
worth a look next time the kiosk/Funnel URL is checked.

## Open — not yet done
- **Milestone 5** (optional): tap-an-aircraft detail panel.
- **Physical verification on the real panel**: the round 1080x1080 display
  needs to actually be connected via HDMI to confirm rendering, sizing, and
  touch input work on real hardware — not yet possible since it isn't wired up
  in the enclosure yet.

## Dev-only files
`dev-server.py` is a local-only static file server + reverse proxy
(`/tar1090/*` → `<radar>`) used purely to test `index.html` with the same
relative paths it'll use in production, without hitting CORS on a dev machine.
It is **not** part of the deployed app — don't copy it to the Pi. Run it with
`python3 dev-server.py` and open `http://localhost:8000/index.html`.
