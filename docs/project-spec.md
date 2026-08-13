# FlightWall — Project Spec & Shopping List
*(Pi 5 build, two-wave purchase order)*

A wall-mounted, live ADS-B flight radar on a true round 7" display, built custom (not ported), 3D-printed enclosure on the Bambu H2D.

---

## 1. Concept

- Local RTL-SDR receiver picks up real ADS-B signals from aircraft overhead
- A small local web app renders a circular radar UI, full-screen on the round panel
- Runs as a kiosk — boots straight into the display, no desktop, no monitor/keyboard needed after setup
- Pi, dongle, and display all live together in one enclosure on the wall — only a power cord and antenna cable exit it

## 2. Architecture

```
[Antenna] --> [RTL-SDR USB dongle] --> [readsb/dump1090] --> aircraft.json (local)
                                                                    |
                                                                    v
                                          [Small web app: fetch + render]
                                                                    |
                                                                    v
                                    [Chromium kiosk, full-screen] --> [7" round HDMI panel]
```

All housed in one wall-mounted enclosure. Power cord runs down to the nearest outlet inside a paintable cord raceway. Antenna cable runs a short distance to the nearest window.

**Why this is simpler than it sounds:** your panel is HDMI (video) + USB-C (touch as a standard USB input). To the Pi, it's just a monitor. No custom drivers, no ribbon cables, no firmware overlays.

## 3. Purchase Plan — Two Waves

**Wave 1 — validate reception before the big spend (~$168):**
Confirms you actually receive real aircraft at your location before committing to the display.

| Item | Spec | Approx. Price | Buy |
|---|---|---|---|
| Raspberry Pi 5, 8GB | — | $80 | [pishop.us](https://www.pishop.us/product/raspberry-pi-5-8gb/) |
| Official Active Cooler | — | $5 | [pishop.us](https://www.pishop.us/product/raspberry-pi-active-cooler/) |
| Official 27W USB-C PSU | — | $12 | [pishop.us](https://www.pishop.us/product/raspberry-pi-27w-usb-c-power-supply-black-us/) |
| microSD card | 32–64GB, A2 rated | $8 | Amazon, generic is fine |
| FlightAware Pro Stick Plus (RTL-SDR) | Built-in 1090MHz filter/amp, SMA input | $46 | [flightaware.store](https://flightaware.store/products/pro-stick-plus) |
| Basic indoor/window 1090MHz antenna | SMA, short cable | $18 | [Amazon bundle](https://www.amazon.com/1090MHz-ADS-B-Antenna-Filter-FlightAware/dp/B01F8DQV24) |

**→ Checkpoint:** install `readsb`, confirm real aircraft show up in `aircraft.json`. Only proceed to Wave 2 once this is working.

**Wave 2 — the display and finishing hardware (~$195):**

| Item | Spec | Approx. Price | Buy |
|---|---|---|---|
| Waveshare 7" Round LCD | 1080×1080 IPS, HDMI, 10-pt capacitive touch, USB-C | $160 | [waveshare.com](https://www.waveshare.com/7inch-1080x1080-lcd.htm) |
| Short HDMI + USB-C cables (panel to Pi) | — | $12 | Amazon |
| Paintable cord raceway (3–6ft) | For the power cable run to the outlet | $12 | Amazon / hardware store |
| Wall anchors / mounting screws | Skip if you already have some on hand | $10 | any hardware store |
| Filament for enclosure | Matte PLA/PETG, 2 colors via AMS2 Pro | — | you already have this |

**Total: roughly $360–370**

## 4. Software Project Spec (for Claude Code)

**Goal:** a local web app, rendered full-screen in a Chromium kiosk on the Pi, showing a live circular radar of aircraft overhead using local ADS-B data.

**Stack:**
- Backend: `readsb` (or `dump1090-fa`) for signal decoding → serves `aircraft.json` on localhost
- App: single-page web app (plain HTML/CSS/JS), Canvas for the radar — a working prototype of the renderer already exists and proves the circular geometry, sweep animation, and bearing/range plotting
- Display: Chromium `--kiosk` pointed at `http://localhost:PORT`, launched by systemd on boot
- Target hardware: Raspberry Pi 5 (8GB) — comfortable headroom for the renderer, with room to add live map tiles later if desired

**Milestones — build in this order:**
1. **Environment** — flash Raspberry Pi OS, confirm the panel works as a plain HDMI monitor + USB touch device, nothing custom needed
2. **ADS-B pipeline** — install `readsb`, confirm `aircraft.json` is populating with real aircraft; note your home lat/long for range/bearing math *(this is Wave 1's checkpoint)*
3. **Wire up the existing prototype** — replace the prototype's fake `planes` array with a `fetch()` against the local `aircraft.json`, convert lat/lon to bearing/range from home
4. **Live data validation** — confirm real aircraft plot correctly, basic altitude/speed labels
5. **Interaction (optional)** — tap an aircraft for a detail panel
6. **Kiosk + boot** — Chromium kiosk mode + systemd service, auto-restart on crash, comes up clean on power-on
7. **Polish** — color-coded altitude (already in the prototype), plane icons, dark theme matching your enclosure finish

**Hand this section to Claude Code as-is**, along with the existing prototype file, to kick off the build — it's scoped as incremental steps with a visual checkpoint at each stage.

**License:** plan to publish the finished app on GitHub under MIT — the foundation (`readsb`, Raspberry Pi OS, Chromium) is all open source, and this makes your renderer a contribution back rather than just a consumer of it.

## 5. Enclosure Plan (Bambu H2D)

- **All-in-one housing** — Pi, dongle, and cabling live inside the same enclosure as the display; only power and antenna cables exit
- **Bezel ring** — thin, flush frame around the glass edge; this is the part people see, worth the extra print time for a clean fit
- **Rear shell** — houses the Pi 5, RTL-SDR dongle, and cable routing; leave an access panel for the microSD card
- **Cable exits** — two small grommeted openings at the bottom edge: one for power (feeding into the cord raceway), one for the antenna cable
- **Wall mount** — French cleat or keyhole slots printed directly into the rear shell
- **Two-tone option** (AMS2 Pro) — matte black bezel with a thin accent-color ring for a premium finish
- **Ventilation** — a few discreet slots on the rear shell near the active cooler; don't seal it up completely for 24/7 operation
