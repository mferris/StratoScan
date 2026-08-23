# Changelog

## v1.0.0 — 2026-08-23

First tagged release. FlightRadar has been under active development for a
while (see [HANDOFF.md](HANDOFF.md) for the full development history); this
tag marks the first point the project has a version number attached to it.

### Features

- **Live tracking** — polls a local `readsb` instance every second;
  altitude-coded blips, smooth interpolation between polls, a "NO SIGNAL"
  banner on connection loss
- **Airline & route lookup** — badges each flight with its airline and shows
  its city-pair route where one's known
- **Aircraft type & photo** — human-readable type names and a real photo
  when one exists, falling back to a representative photo of the type
- **Background map** — real terrain, roads, and cached runway outlines,
  darkened and centered on the receiver, with a live weather radar overlay
- **RDU approach visualization** — a real density heatmap built from
  actually observed landings over time
- **Sighting counts** — tracks how many distinct times each aircraft has
  been picked up, and how many of those came within the nearby-alert
  radius; shown as a "SEEN ×N" badge and in the detail panel
- **Registered-owner lookup** — for confirmed-private aircraft, shows who
  the plane is registered to
- **Nearby-aircraft alert** — auto-pops flight details with a chime for
  anything within 2 miles of the receiver
- **Emergency squawk alert** — a distinct urgent chime and a red auto-popped
  panel for 7500 (hijack), 7600 (radio failure), or 7700 (general emergency)
- **RDU landing/takeoff highlight** — a bright green ring around the blip
  and label of anything currently landing or departing at RDU, plus an
  optional quiet chime
- **RDU ATC audio link** — an optional link to LiveATC.net's live
  approach/departure audio for the airport (deliberately a link, not an
  embed — see [README's Security section](README.md#security) for why),
  automatically disabled on the physical kiosk itself since it can't be
  safely reopened there via touch
- **Settings panel** — a gear icon opens on-screen toggles for all of the
  above alert/sound behaviors, persisted per-device
- **Touch detail panel** — tap any aircraft for registration, squawk,
  vertical rate, precise range/bearing, and flight trail
- **Native iOS companion app** — a SwiftUI rebuild of the same radar for
  iPhone, talking to the same receiver over Tailscale

### Security

- Public exposure (e.g. via Tailscale Funnel) goes through a filtering
  gateway that rounds the receiver's exact coordinates before they leave
  the network
- External/third-party data is HTML-escaped before touching the DOM
- Shared same-origin stores (approach track, sighting counts) validate
  input shape and cap request body size
- No secrets or API keys anywhere — every external data source is free and
  keyless

See [README.md](README.md) for full setup/deployment docs and
[HANDOFF.md](HANDOFF.md) for the detailed development history behind each
of these.
