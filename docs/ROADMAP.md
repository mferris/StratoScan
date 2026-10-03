# Roadmap: the five phases

**Baseline:** [v2.0.0](https://github.com/mferris/StratoScan/releases/tag/v2.0.0),
identical to OTA release `2026.09.27.15`. It is the revert point for
everything below.

Progress is tracked as GitHub
[milestones](https://github.com/mferris/StratoScan/milestones) and
[issues](https://github.com/mferris/StratoScan/issues). This file holds
the design decisions those issues depend on.

## Ground rules

- **Open source, license-clean.** Nothing is added without checking its
  license and terms first, and recording it in
  [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Anything
  non-commercial-only (such as RainViewer) is labelled as such.
- **The radar never depends on a cloud service.** The relay (below) adds
  push and fleet health. A unit that can't reach it keeps working exactly
  as it does today.
- **Privacy by default.** The exact home location never leaves the device.
  Anything sent off-device is opt-in, minimal and rounded.
- **No secrets on units.** Gifted units are in other people's houses. Keys
  that can act for the whole fleet (such as Apple's push key) live only in
  the relay.
- **Every fix is verified on the running device**, not just installed.

## What to buy

The parts each item needs are in [SHOPPING.md](SHOPPING.md).

## Architecture: the relay

One small **Cloudflare Worker** (`relay/`) with a D1 database. It is the
only server the project runs.

```
unit ──(signed heartbeat, events)──▶ relay ──(APNs)──▶ iPhone / Watch
unit ◀────(nothing: units only ever call out)──────────┘
phone ──(pairing, notification rules)──▶ relay
```

- **Unit identity:** each unit generates an Ed25519 keypair at install, and
  signs every request with it. The relay stores public keys only. Nothing
  shared or fleet-wide is baked into images.
- **Pairing:** the unit's screen shows a QR code with its ID plus a
  one-time pairing secret (valid 10 minutes). The phone scans it, and the
  relay links that phone's push token to the unit.
- **Heartbeat (opt-in):** every 6 h the unit sends its version, uptime,
  receiver health, SD wear estimate and last-error class. **No location.**
  A fleet page shows the maintainer every unit's health.
- **Events:** the unit decides locally what matters (notable aircraft,
  emergency squawk, low overhead…) and posts a small event. The relay fans
  it out to paired devices over APNs. Payloads carry aircraft data only,
  never the home location: identity, type, altitude, and distance rounded
  to half a nautical mile with a compass direction. That still hints where
  a unit is, so events are off until the owner pairs a phone, and the relay
  keeps them only 48 hours. A factory reset turns them off.
- **Failure mode:** if the relay is down, units keep a short queue, drop it
  on overflow, and the radar is unaffected.

## Phase 1: reliability you can see

| # | Item | Done when |
|---|---|---|
| 1.1 | RTC battery support: installer sets `dtparam=rtc_bbat_vchg` when a rechargeable cell is fitted; clock health in status | A unit keeps correct time across a power cut with no network |
| 1.2 | Storage off the SD card: NVMe boot via the Pi 5 M.2 HAT+ (or CM5 eMMC). Migration script, enclosure fit, installer checks | A unit boots and runs from NVMe; the enclosure fits |
| 1.3 | Relay foundation: Worker, D1 schema, signed-request auth, heartbeat endpoint, fleet status page | Deployed; tests pass; RDU's heartbeat shows on the fleet page |
| 1.4 | Unit side: keypair generation, opt-in heartbeat (setup toggle), sent every 6 h | RDU reports; turning it off stops it |
| 1.5 | Factory image: pi-gen build in GitHub Actions (Arm runner); first boot runs the installer; GPL source offer for readsb/tar1090 included | A fresh SD flashed from the release boots to the setup hotspot |
| 1.6 | Re-measure SD writes after the storage fixes (scheduled 2026-09-28) | Result recorded; any remaining large writer fixed |
| 1.7 | Recover a hung radio without a human: the watchdog power-cycles USB (uhubctl) before it reboots, since a Pi 5 reboot keeps USB powered | A hung SDR comes back on its own on a real unit |
| 1.8 | Core feed on the device: one service merges the antenna's and the network's aircraft, labels them once (operator, type, route, owner, notable), caches the lookups, and serves `/api/aircraft` to every screen; no antenna-relative fields | Live on RDU; labels match the kiosk's on a recorded sample |
| 1.9 | Kiosk and public page read the core feed; route and owner lookups move off visitors' browsers onto the unit | Same picture as before; public visitors no longer contact adsb.im or adsbdb |
| 1.10 | ~~`events.py` reads the core feed;~~ the copied classification tables are deleted. **Done 2026-09-30:** the tables are shared from `labels.py`; `events.py` stays on readsb's `aircraft.json` on purpose (it needs the antenna-relative fields, and alerts shouldn't depend on the core feed) | Same alerts from the same fixtures, with no tables of its own |
| 1.11 | Cut the radar's drawing cost: static layers drawn once, the sweep rotated by the compositor, only moving things redrawn | Measured on RDU: the GPU process well under half its current ~94% of a core, and cooler |
| 1.12 | Visitor counts for each radar's public page, for its owner: views, unique visitors (a daily-salted hash, never stored), the owner's app counted apart, hour of day, device type, referring site; no cookies, no stored addresses; on the radar's screen, setup page and app (#50) | Visits from a phone on mobile data show within a minute; nothing stored holds an address |
| 1.13 | Fleets with their own administrators on the relay: radars join by their owner's invite code and can leave any time; administrators see health and visit counts per radar and in total, never locations, phones or alerts; per-administrator sign-in (#51) | The family fleet with RDU in it; a second fleet sees none of it |

## Phase 2: the pocket

| # | Item | Done when |
|---|---|---|
| 2.1 | Relay push: APNs token auth, fan-out, per-phone rules, rate limits | A test event reaches a real iPhone |
| 2.2 | Unit events: notable / emergency / low overhead / helicopter, decided on the unit and queued to the relay | Events arrive for real traffic at RDU |
| 2.3 | QR pairing on the device screen, and in the app | Pair and unpair with a phone, end to end |
| 2.4 | iOS app v2: notification rules, home and lock-screen widgets, Live Activity (inbound overhead), StandBy radar | Each feature working on a real phone |
| 2.5 | iOS app v2: away mode (community feed when not home), logbook/collection, AR sky view fed by the unit | Each feature working on a real phone |
| 2.7 | Location-aware app: a "You" marker relative to the antenna and a centre-on-me map; opt-in alerts for aircraft approaching the phone, its location end-to-end encrypted to the paired radar, which runs the prediction | Alerts for aircraft near the phone arrive on a real iPhone away from home, within the radar's coverage |
| 2.8 | App shows the network's aircraft too (the kiosk's "not heard" ghosts from `/network`), marked distinctly, with matching counts and the ODbL credit; setting to turn off | The app and the kiosk show the same sky on a real iPhone |
| 2.9 | Zoom in the app: pinch from 20 nm to about 1 nm, centred on the radar, the phone, or a followed aircraft; optionally the same on the kiosk, returning to full view by itself | A real aircraft sits on the right street at full zoom on a real iPhone |
| 2.10 | Logo and app icon: a round radar-sweep mark with a nod to altitude, legible at 16 px and in one colour; app icon (with dark and tinted variants), favicons, README header, repo social preview; logo files under their own notice, not MIT | Claude | The icon on a real iPhone home screen, and favicons everywhere the project shows its face |
| 2.11 | iPad app: a big radar with details, logbook and settings in a side panel; landscape and portrait; optional full-screen wall mode | On a real iPad, both orientations, nothing changed on the iPhone |
| 2.12 | Sky view tracks: a fading line where each aircraft has been and a dotted one where it's going, projected across the sky like the labels | Outdoors on a real iPhone, the lines follow the aircraft's real path |
| 2.13 | The app without a radar: live aircraft around the phone from adsb.lol (opt-in, rounded location), radar view and Sky view; alerts and the logbook stay radar-only | On a real iPhone with no radar: real aircraft around you; pairing later switches cleanly |
| 2.14 | Weather in the app: the kiosk's precipitation radar (RainViewer) and lightning (RealEarth) on the iPhone and iPad map, with the same switches | On a real iPhone, rain shows where the kiosk shows it |
| 2.15 | The kiosk's four colour themes in the app, Daylight by default (the kiosk's default too, from 2026-10-01), and a lighter map | Each theme matches the kiosk on a real iPhone; new installs open in Daylight |
| 2.16 | Alerts about where I am, the radar, or both: low overhead, helicopter and notable alerts measured from the phone's (encrypted) location as well as the antenna, by the owner's choice; within the radar's reach first | Away from home, a helicopter near the phone alerts "near you"; one over the house doesn't |
| 2.17 | Radar names: set during setup (default from the place), shown on the radar and carried to phones by the pairing link; a rename on the radar reaches phones that haven't named it themselves | A new radar pairs and shows its own name on the phone |
| 2.18 | Set up a new radar from the app: one QR code on the first-boot screen, the app joins the setup hotspot, sends home WiFi, the phone's location, time zone and name, and pairs in the same session; the browser and on-screen setup stay | A radar fresh from the factory image is set up and paired from the app alone |
| 2.19 | Public web address during first setup: nothing to type or renew; proposed: the relay mints a one-time `tag:stratoscan` Tailscale key for a radar being set up (Cloudflare Tunnel the alternative) | A radar set up from the app is reachable away from home, and can reach nothing on the tailnet |
| 2.20 | CarPlay, within what Apple allows without an entitlement: the approach Live Activity in CarPlay (iOS 26) and a text-only nearest-aircraft widget; alerts already reach CarPlay. No CarPlay app: a radar isn't one of Apple's CarPlay categories | In a CarPlay car or the CarPlay simulator: the Live Activity, the widget, an alert |

## Phase 3: the wrist

| # | Item | Done when |
|---|---|---|
| 3.1 | watchOS app: nearest-plane complication, glance radar | Complication live on a real Watch |
| 3.2 | Distinct wrist taps per alert type; Smart Stack Live Activity | Felt on a real Watch |
| 3.3 | "Look up" mode: a compass arrow toward the aircraft, and a countdown to overhead | Arrow points correctly outdoors |
| 3.4 | Approach compass on the phone as well as the Watch: where the aircraft is, where it is coming from and heading, in the notification, a north-up dial on the Live Activity, and a live compass in the app | The needle points at a real aircraft outdoors, on a phone and a Watch |

## Phase 4: delight

| # | Item | Done when |
|---|---|---|
| 4.1 | "What was that?": the unit keeps a rolling hour of tracks in RAM; tap to rewind and see what passed overhead | Rewind works on the kiosk and in the app |
| 4.2 | Notable aircraft from plane-alert-db (**license check first**) | Categories show and alert; notices updated |
| 4.3 | Empty-sky mode: clock, weather (source license checked), today's tally | Shows when nothing is in range, and leaves when traffic returns |
| 4.4 | Spoken announcements with offline TTS (Piper; **voice license checked**, permissive only) | Announces real traffic with no internet |
| 4.5 | Yearly "Wrapped" from the sighting store, shareable from the app | Generated from RDU's real history |
| 4.6 | Opt-in feeding to FlightAware / FR24 (their feeder licenses checked; precise-location sharing is explicit) | A unit feeds; the perk account activates |
| 4.7 | Quiet hours: silence the unit's alert sounds (chimes and speech) in a set window or sunset to sunrise; alerts still show on screen; emergencies can still sound | No sound inside the window on RDU, and sound returns on time |

## Phase 5: hardware v2

| # | Item | Done when |
|---|---|---|
| 5.1 | Rotating bezel (rotary encoder) for range and paging: enclosure redesign plus input handling | Turning the bezel changes range on the kiosk |
| 5.2 | Presence wake (LD2410 mmWave over UART, or PIR) replacing the 20-min idle timer | The screen wakes on approach and sleeps when the room is empty |
| 5.3 | 978 MHz UAT receiver for US units (dump978 into readsb) | UAT-only GA aircraft appear on the radar |
| 5.4 | Retro stand: ridges all the way round the plinth, standing out ~4 mm so the slicer supports them (as the case ribs were fixed) | Printed, with clean ridges on all four sides |
| 5.5 | Ambient light sensor: dim the display with the room, with an adjustable darkest level; a sensor window on both cases; first find a real backlight control (the panel's HID report 9, or DDC) | The display follows the room on RDU, down to the owner's floor |
| 5.6 | Key the back plate so it seats only upright (antenna at the top): a key on each shell's bore wall and a matching gap in one arc of the plate's locating rib; checks prove the seven wrong orientations are blocked | The plate goes in only upright, on both cases |

## Work order (agreed 2026-09-30)

The open items are done in this order, chosen so the display is never
at risk for long.

**Rules**

- **One change to the unit at a time.** Each goes out as a small signed
  update, which rolls itself back if the screen stops painting. Leave 2–3 days
  on RDU between updates.
- **Add, then switch, then delete.** A new service runs alongside the old
  path with nothing depending on it. Screens move onto it one at a time,
  riskiest last. Old code goes only once the new path has proved itself.
- **The phone app goes first.** App changes cannot break the radar, so the
  app is where a new foundation is tested for real.
- **Hardware features change nothing without the part.** A unit without the
  sensor, bezel or receiver behaves exactly as it does today.

| Step | Items | Why here | Risk to the display |
|---|---|---|---|
| 0. Quick wins, anytime | 5.4 stand ridges, 5.6 back-plate key (CAD only); 4.7 quiet hours (off by default); 1.1 RTC cell and 1.7 radio recovery (confirm when the cell arrives or a hang happens) | Small and independent | None, or minimal |
| 1. Measure, then cool it down | **1.11** drawing cost | Its measurement script is how every later step is checked. It changes only drawing, not data | Low: screenshot comparison |
| 2. Core service, alongside | **1.8** core feed | Nothing reads it yet. Run for days with a live comparison against the kiosk's labels | None |
| 3. First user: the app | 2.8 network aircraft in the app | Real use; a bug only affects the app, which falls back to the old feed | None |
| 4. Alerts, trial run first | 1.10 `events.py` | Run the old and new logic side by side for days, logging disagreements, then switch | Alerts only |
| 5. The kiosk, last | 1.9 kiosk and public page | Riskiest change, after a week or more of the feed. Tried on the public page first; the old path kept for one release | Medium, contained |
| 6. App features | 2.9 zoom, the map part of 2.7, 3.4 (phone), the rest of 2.4/2.5, then the alerts part of 2.7 | Map parts are app-only; 3.4's direction of travel and 2.7's alerts need step 4 | None (app); low (alerts) |
| 7. Watch | 3.1 → 3.2 → 3.3 / 3.4 (Watch) | Straightforward once there is one feed to read | None |
| 8. Hardware v2 | 5.5 light sensor, 5.1 bezel, 5.2 presence, 5.3 978 MHz | As parts arrive: case, print, then software that changes nothing without the part. 5.5's first step (finding a real backlight control) is read-only and can be done anytime | Low |
| Factory image | 1.5 | Test-flash today's image soon, to prove the pipeline; rebuild after step 5 so gifted units carry the new architecture | None |

**Next, agreed 2026-10-03** (after the radar names and app setup work):
1. **Releases to RDU**, 2–3 days apart: the location-polling fix with the radar side of 2.18 (about Oct 4–5), then 1.9's switch to the core feed on its own (about Oct 7).
2. **1.12** visitor counts (#50).
3. **1.13** fleets (#51). Moved ahead of CarPlay because the family gift units need them.
4. **2.20** CarPlay (#49).

**Dependencies** (still true within the order above)

- 1.8 comes before 1.9, 1.10 and 2.8. 1.11 is independent.
- 2.7's alerts and 3.4's direction of travel need 1.10.
- 3.x needs 3.1 first; 3.4 extends 3.3.
- 1.5's final image comes after 1.9.

## Status

| Item | State | Waiting on |
|---|---|---|
| 1.1 RTC battery | Software done: the installer reports the battery; `RTC_RECHARGEABLE=1` enables charging | Fitting a cell and checking the clock survives a power cut |
| 1.3 Relay | **Done.** Live at relay.stratoscan.io (D1 attached; the old workers.dev address still answers); RDU reporting; fleet page password-protected | — |
| 1.4 Health reports | **Live**; RDU opted in and reporting every 6 h | — |
| 1.6 SD re-measure | **Done.** 2.25 GB/day in steady state (was 8.8): about 8 TB over 10 years against a rough 40–70 TB ceiling for a 128 GB card. Last fixes: 2-minute writeback batching, no Chromium shader disk cache. Remaining: journald ~1 GB/day, kept on purpose (logs that survive a crash are worth more) | — |
| 1.2 Storage off the SD card | **Not needed**, from the 1.6 measurement. Gift units use high-endurance SD cards. The fleet page flags any unit writing over 5 GB/day | Reopen #2 if a unit is ever flagged |
| 4.1 "What was that?" | Done: rewind button, closest passes from tar1090's in-RAM hour, track on radar | — |
| 4.2 Notable aircraft | Done: plane-alert-db weekly on each unit; neutral labels; no private names; PIA dropped | — |
| 4.3 Empty-sky screen | Done: clock, weather (Open-Meteo), today's tally after 30 s of empty sky | — |
| 4.4 Spoken announcements | Done: Piper + LJSpeech voice on the unit; setting off by default | — |
| 4.5 Year in review | Done: per-year counters; RDU's history carried over (44,332 visits in 2026) | — |
| 4.6 FlightAware feeding | Done: opt-in setup-page card; PiAware relays readsb; remote updates off; FR24 linked, not automated | Owner turns it on and claims the feeder |
| 2.2 Unit events | **Done.** `deploy/events.py` service on RDU; relay `POST /v1/events` live. First real events 2026-09-28: a US Army helicopter (ZEUS11), sent as notable + helicopter. Off by default on new units until a phone pairs (2.3) | — |
| 2.3 QR pairing | **Done.** A real iPhone paired with RDU from its screen (2026-09-28); RDU listed it and switched its events on. Unpairing from either side verified in the simulator | — |
| 2.1 Relay push | **Done.** Token-based APNs from the relay. Verified in the simulator, then on a real iPhone paired with RDU: the test notification arrived (2026-09-28) | — |
| 2.4 Widgets, Live Activity, StandBy | Widget done. **Live Activity done** and verified on a real iPhone (2026-09-28): RDU predicts a close pass (low, helicopter or notable, within 2 mi in the next 3 min), the relay starts a lock-screen / Dynamic Island countdown by push-to-start and ends it after the pass. Opt-in (Settings › Alerts › Approaching aircraft). Also: tap-for-details, compact labels, demo mode. **StandBy radar built** (181c308): a Radar widget (small and large) for StandBy and the home screen | A real-iPhone check of the StandBy widget |
| 2.5 Away mode, logbook, AR sky view | Away mode done and verified on a real iPhone (2026-09-28): the app and widget switch between the radar's home address and its public HTTPS page (Tailscale Funnel) as the phone leaves and rejoins home WiFi; the away address is learned from the radar. **Sky view verified on a real iPhone** (2026-09-30): hold the phone up and each aircraft's label (callsign, type, altitude, range) sits where it is in the sky, upright however the phone is held; tap for details, sideways too. Motion sensors plus the camera picture (ARKit never started on the phone). Away from the radar, opt-in: the aircraft around the phone from adsb.lol, location rounded to ~5 km. **Logbook built** (2fbf5cd) and installed on the owner's iPhone: today, all-time totals, records, what flies over, arrivals by hour, the regulars, this year | Sky view's "around me" away from home; the owner's look at the logbook |
| 1.8 Core feed | **Live on RDU** (2026-09-30, release 2026.09.30.8 plus the installer): `deploy/core-feed.py` serves `/api/aircraft`, labelled by `deploy/labels.py`, the one shared copy; `?network=1` adds the network's aircraft. Read-only on the public address (POST refused). 23 service checks, 14 parity checks | — |
| 2.8 Network aircraft in the app | Built (c8e25d9): the app reads the core feed, draws the network's aircraft hollow, counts "not heard", falls back to aircraft.json on radars without the feed. **Verified on a real iPhone with RDU** (2026-09-30): hollow network blips and the "not heard" count | — |
| 4.7 Quiet hours | **Done** (2026-09-30): Settings › Alerts › Quiet hours silences chimes and speech in a set window (default 22:00–07:00, half-hour steps) or sunset to sunrise; alerts still show; emergencies can sound; sounds you trigger in Settings still play. Off by default | — |
| 1.7 Hung-radio recovery | **Done: recovered a real failure on RDU** (2026-09-30): the FlyCatcher dropped off USB at 16:50 ("Cannot enable", error -71; no under-voltage); the watchdog restarted readsb three times, then power-cycled USB at 16:57 and the radio came back, data flowing again within a minute. About 7 minutes of "No signal" in all | — |
| 2.10 Logo and app icon | **Done** (2026-09-30): the Climb mark in Stratosphere colours. App icon (light, dark, tinted) verified on a real iPhone; Watch icon. The logo on the radar's start-up and empty-sky screens, its settings and the setup page (live on RDU); in the app's header and Settings, the Watch glance, the widget and the Live Activity. Favicons; README header; social preview ("Window to the Sky"). Files in `assets/brand/`, all rights reserved, not MIT | The social preview uploaded on GitHub; the fleet page favicon with the next relay deploy |
| 2.11 iPad app | First version built (38352db): scaled-up radar and controls, details in a side panel, wall mode. Simulator only | A real iPad; landscape layout with the panel; night dimming in wall mode |
| 2.7 Approaching me | **Live** (2026-10-01): relay deployed, RDU on 2026.10.01.1, the owner's phone opted in; RDU decrypts its location and watches for approaches to it. One countdown per aircraft per phone (3b46f89) | A real "approaching you" alert |
| 2.13 App without a radar | Built (45cf2ff): live aircraft around the phone from adsb.lol (opt-in, rounded location), centred on you; radar view, Sky view, weather, themes; logbook and alerts explained as radar-only | On a real iPhone with no radar paired |
| 2.14 App weather | Built (b7a5f81): rain and storms (RainViewer) and lightning (RealEarth) on the app's map, with switches; RainViewer is personal-use only, so a commercial release needs another source | Seen with real rain in view |
| 2.15 App colour themes | Built (826a16e): the kiosk's four themes, Daylight by default; map filter and labels follow; logo light/dark | The owner's look on the real phone |
| 2.16 Alerts about where I am | Built and live (relay 5b11035 deployed, unit release 2026.10.01.4 on RDU, app 9276216): Settings › Alerts › "Nearby alerts are about" My radar / Where I am / Both. Low overhead, helicopter and notable alerts measured from the phone's encrypted location, titled "near you"; emergencies still go to every phone. Within the radar's reach only | Away from home: an alert near the phone, none for the house |
| 2.17 Radar names | **Verified** on a real iPhone and RDU (2026-10-02): a Name setting on the radar (its screen and the setup page), suggested from the home airport's city; carried in the pairing code; a paired phone follows a rename when it's home, unless it was named on the phone. LAN only: not on the public page, not on the relay | — |
| 2.18 Set up from the app | Built: one QR code on the first-run screen; the app joins the setup network, claims the radar (admin password kept in the Keychain), sets location, airport, time zone, region and name from the phone, sends the home WiFi (the radar joins and confirms in the background), and pairs with a code only the phone holds. Tested in the simulator against the real setup server with a stand-in for setupd; also fixed the setup page's time-zone and update buttons, which had never saved | A real first-time setup: needs a radar that hasn't been set up (a gift unit) |
| 1.11 Radar drawing cost | **Done** (2026-09-30, release 2026.09.30.12): GPU process 96% → 37% of a core, Chromium total 128% → 52%. Aircraft canvas at 5 fps with the sweep on the compositor (smooth), and labels that touch the page only when something changed. Measurements on #35 | — |
| 1.12 Visitor counts | Built (d4ad828), not on RDU yet: counts in the public gateway (daily-salted hash, kept in memory only; counts saved 90 days), the owner's app counted apart; on the radar's Statistics, the setup page and the app | RDU release after #33; whether Funnel passes the visitor's address; installer re-run for 90-day storage |
| 1.13 Fleets | Relay **live** (72ee808, 2026-10-03): fleets created on /fleet with a shown-once invite code and administrator link; administrators' page at /f. Radar side built, not on RDU yet: join or leave on the setup page, health reports on while in a fleet | RDU release with 1.12; create the family fleet and join RDU |
| 2.9 Zoom | **Verified on a real iPhone** (2026-09-30): pinch from 20 nm to 1 nm on any spot (it stays under the fingers), double-tap to zoom in on a spot, drag to move, follow an aircraft, centre on the phone. The app's map is now at the radar's true scale (63e21ed; it had been drawn at twice it) | Kiosk zoom (optional) |
| 2.7 Location-aware app | Map part **verified on a real iPhone** (2026-09-30): a "You" marker where the phone is, and centre-on-me; location stays on the phone. The alerts near the phone are 2.7 Approaching me and 2.16, both live | — |
| 3.4 Approach compass | Built: the approach alert says where the aircraft comes from and heads (258778f, relay deployed 2026-09-30); a live compass in the app (a165624, **verified on a real iPhone** 2026-09-30: it points at the aircraft); a north-up dial on the Live Activity | A real approach alert with the new wording; the Watch |
| 3.1 watchOS app | Built (037b07a): a glance radar and complications, fed by the phone; runs in the Watch simulator. The maintainer's Watch can't be reached by Xcode (2026-09-30): not listed after re-pairing, Bluetooth off, the iPhone's hotspot, and everything on one Wi-Fi; the Watch never offers itself for pairing on the network, so Developer Mode never appears. A development build is refused without it | Install through TestFlight once the App Store Connect record exists |
| 3.2 Wrist taps, Smart Stack | Smart Stack Live Activity built (4853ebc); distinct taps not started | A real Watch |
| 5.4, 5.5 | Planned 2026-09-29 as issues #26, #27 | — |
| 1.5 Factory image | Built: CI produces a 1.6 GB image that passes its checks (working unit, no per-unit secrets, GPL sources attached). Last built 2026.09.28 under the old name; to be rebuilt as StratoScan after 1.9. Not yet published | A test flash on a spare SD card |
