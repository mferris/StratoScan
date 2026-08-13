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

Covers milestones 3–4, 6, and part of 7 from `docs/project-spec.md`. Not done
yet: milestone 5 (optional tap detail panel), and physically mounting/connecting
the round panel (see below).

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
- Kiosk launcher is a **systemd user service**:
  `~/.config/systemd/user/flightwall-kiosk.service` (on the Pi, as the login user).
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
