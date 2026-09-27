# Roadmap: the five phases

**Baseline:** [v2.0.0](https://github.com/mferris/FlightRadar/releases/tag/v2.0.0),
identical to OTA release `2026.09.27.15`. It is the revert point for
everything below.

Progress is tracked as GitHub
[milestones](https://github.com/mferris/FlightRadar/milestones) and
[issues](https://github.com/mferris/FlightRadar/issues). This file holds
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
  never the home location.
- **Failure mode:** if the relay is down, units keep a short queue, drop it
  on overflow, and the radar is unaffected.

## Phase 1: reliability you can see

| # | Item | Owner | Done when |
|---|---|---|---|
| 1.1 | RTC battery support: installer sets `dtparam=rtc_bbat_vchg` when a rechargeable cell is fitted; clock health in status | Claude (code) | A unit keeps correct time across a power cut with no network |
| 1.2 | Storage off the SD card: NVMe boot via the Pi 5 M.2 HAT+ (or CM5 eMMC). Migration script, enclosure fit, installer checks | Claude | A unit boots and runs from NVMe; the enclosure fits |
| 1.3 | Relay foundation: Worker, D1 schema, signed-request auth, heartbeat endpoint, fleet status page | Claude | Deployed; tests pass; RDU's heartbeat shows on the fleet page |
| 1.4 | Unit side: keypair generation, opt-in heartbeat (setup toggle), sent every 6 h | Claude | RDU reports; turning it off stops it |
| 1.5 | Factory image: pi-gen build in GitHub Actions (Arm runner); first boot runs the installer; GPL source offer for readsb/tar1090 included | Claude | A fresh SD flashed from the release boots to the setup hotspot |
| 1.6 | Re-measure SD writes after the storage fixes (scheduled 2026-09-28) | Claude | Result recorded; any remaining large writer fixed |

## Phase 2: the pocket

| # | Item | Owner | Done when |
|---|---|---|---|
| 2.1 | Relay push: APNs token auth, fan-out, per-phone rules, rate limits | Claude | A test event reaches a real iPhone |
| 2.2 | Unit events: notable / emergency / low overhead / helicopter, decided on the unit and queued to the relay | Claude | Events arrive for real traffic at RDU |
| 2.3 | QR pairing on the device screen, and in the app | Claude | Pair and unpair with a phone, end to end |
| 2.4 | iOS app v2: notification rules, home and lock-screen widgets, Live Activity (inbound overhead), StandBy radar | Claude | Each feature working on a real phone |
| 2.5 | iOS app v2: away mode (community feed when not home), logbook/collection, AR sky view fed by the unit | Claude | Each feature working on a real phone |
| 2.6 | App Store readiness: bundle IDs, privacy labels, credits screen (MapLibre Native BSD-2, map attribution), screenshots, review notes | Claude | Approved on the App Store |

## Phase 3: the wrist

| # | Item | Owner | Done when |
|---|---|---|---|
| 3.1 | watchOS app: nearest-plane complication, glance radar | Claude | Complication live on a real Watch |
| 3.2 | Distinct wrist taps per alert type; Smart Stack Live Activity | Claude | Felt on a real Watch |
| 3.3 | "Look up" mode: a compass arrow toward the aircraft, and a countdown to overhead | Claude | Arrow points correctly outdoors |

## Phase 4: delight

| # | Item | Owner | Done when |
|---|---|---|---|
| 4.1 | "What was that?": the unit keeps a rolling hour of tracks in RAM; tap to rewind and see what passed overhead | Claude | Rewind works on the kiosk and in the app |
| 4.2 | Notable aircraft from plane-alert-db (**license check first**) | Claude | Categories show and alert; notices updated |
| 4.3 | Empty-sky mode: clock, weather (source license checked), today's tally | Claude | Shows when nothing is in range, and leaves when traffic returns |
| 4.4 | Spoken announcements with offline TTS (Piper; **voice license checked**, permissive only) | Claude | Announces real traffic with no internet |
| 4.5 | Yearly "Wrapped" from the sighting store, shareable from the app | Claude | Generated from RDU's real history |
| 4.6 | Opt-in feeding to FlightAware / FR24 (their feeder licenses checked; precise-location sharing is explicit) | Claude · recipient (their accounts) | A unit feeds; the perk account activates |

## Phase 5: hardware v2

| # | Item | Owner | Done when |
|---|---|---|---|
| 5.1 | Rotating bezel (rotary encoder) for range and paging: enclosure redesign plus input handling | Claude (CAD, code) | Turning the bezel changes range on the kiosk |
| 5.2 | Presence wake (LD2410 mmWave over UART, or PIR) replacing the 20-min idle timer | Claude (code) | The screen wakes on approach and sleeps when the room is empty |
| 5.3 | 978 MHz UAT receiver for US units (dump978 into readsb) | Claude (code) | UAT-only GA aircraft appear on the radar |

## Order and dependencies

- 1.3 comes before 1.4 and 2.1–2.3.
- 2.1 and 2.3 come before 2.4.
- 2.x comes before 3.x.
- 1.5 should come after 1.1, 1.2 and 1.4 settle, so the image carries them.
- Phase 4 items are independent, and can be interleaved whenever Phase 1–3
  items are blocked on an owner action.

## Status

| Item | State | Waiting on |
|---|---|---|
| 1.1 RTC battery | Software done: the installer reports the battery; `RTC_RECHARGEABLE=1` enables charging | ML-2020 cells |
| 1.3 Relay | Built; 10 tests; verified end to end under the Workers runtime with RDU | Cloudflare login, then deploy (`relay/README.md`) |
| 1.4 Health reports | Built; 23 checks on the Pi; setup-page switch; inert until `RELAY_URL` is set | 1.3 deploy |
| 1.6 SD re-measure | Scheduled for 2026-09-28 13:00 | — |
| 4.1 "What was that?" | Done: rewind button, closest passes from tar1090's in-RAM hour, track on radar | — |
| 4.2 Notable aircraft | Done: plane-alert-db weekly on each unit; neutral labels; no private names; PIA dropped | — |
| 4.3 Empty-sky screen | Done: clock, weather (Open-Meteo), today's tally after 30 s of empty sky | — |
