# FlightWall — Handoff Notes

## Status
`index.html` is a matured version of `docs/original-prototype.html` that renders
**live** aircraft on the round radar instead of the fake demo data. It has been
tested against the real receiver at `http://<radar>/tar1090/` and confirmed
working: live positions, altitude-coded colors, smooth interpolation between
1s polls, a "NO SIGNAL" banner on connection loss (tested by killing the feed),
and clean recovery on reconnect.

Covers milestones 3–4 (and part of 7) from `docs/project-spec.md`. Not done yet:
milestone 6 (Chromium kiosk + systemd on the Pi) and milestone 5 (optional tap
detail panel).

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
- SSH to the Pi (`<radar>`) was attempted but blocked on host key
  verification / no credentials available in this session — deployment to the
  Pi has not happened yet.

## Open question for the user
Asked how they want to handle Pi deployment (kiosk mode + systemd boot service):
SSH in and do it live, hand over files/instructions to do it manually, or hold
off entirely. Not yet answered — pick this back up before doing milestone 6.

## Dev-only files
`dev-server.py` is a local-only static file server + reverse proxy
(`/tar1090/*` → `<radar>`) used purely to test `index.html` with the same
relative paths it'll use in production, without hitting CORS on a dev machine.
It is **not** part of the deployed app — don't copy it to the Pi. Run it with
`python3 dev-server.py` and open `http://localhost:8000/index.html`.
