# Third-party notices

StratoScan's own code, enclosure designs and documentation are MIT-licensed
(see [LICENSE](LICENSE)). This file lists everything else the project ships
or uses, under what terms, and how each obligation is met. Reviewed
2026-09-27 and audited 2026-10-09 against each service's current terms;
re-check it whenever a dependency or data source is added.

## Shipped in this repository

| Component | Where | License | How the obligation is met |
|---|---|---|---|
| [MapLibre GL JS](https://github.com/maplibre/maplibre-gl-js) 5.24.0 | `vendor/maplibre-gl.js`, `.css` | BSD-3-Clause | The license header is kept intact at the top of the vendored file. |
| [MapLibre Native (iOS distribution)](https://github.com/maplibre/maplibre-gl-native-distribution) | `ios/` (Swift package, resolved at build time) | BSD-2-Clause | Not vendored. The iOS app's About/credits must carry its notice when the app ships. |
| Sound effects (kitten, plane themes) | `sounds/` | CC0 1.0 | No obligation. Sources and processing are still credited in each theme's `CREDITS.md`. |
| [OurAirports](https://ourairports.com/data/) airport table | `deploy/airports.json` | Public domain | None required; credited in the README. |
| [Chakra Petch](https://github.com/m4rc1e/Chakra-Petch) typeface (outlined in the wordmark) | `assets/brand/logo-*.svg`, `social-preview.png` | SIL Open Font License 1.1 | The licence travels with the outlines as `assets/brand/FONT-OFL.txt`. The font itself is not shipped. |
| Screenshot | `docs/screenshots/kiosk.png` | Map is an OpenStreetMap-derived work (ODbL) via OpenFreeMap / OpenMapTiles | Credited under the image in the README. Centred on RDU airport, not a private address. |

The StratoScan logo and icons (`assets/brand/`, the app icons, the favicons)
are the project's own, all rights reserved rather than MIT: see
[assets/brand/LICENSE](assets/brand/LICENSE).

Airline names and colours in `index.html` are factual identification of the
operator, not logos or artwork.

## The relay (`relay/`)

| Component | License / terms | Notes |
|---|---|---|
| [Cloudflare Workers + D1](https://www.cloudflare.com/terms/) | Cloudflare's Terms of Service | Runs on the maintainer's own account. Units call it only if their owner opts in. |
| [Wrangler](https://github.com/cloudflare/workers-sdk) | MIT OR Apache-2.0 | A development and deploy tool (`devDependencies`); not shipped to units or deployed. |

On the unit, health reports are signed with
[python3-cryptography](https://github.com/pyca/cryptography) (Apache-2.0 OR
BSD-3-Clause), installed from Debian, not vendored here.

## Fetched at runtime (not redistributed)

These are called by a running unit or browser. The project redistributes
none of their content; each is used within its published terms.

| Service | Used for | Terms | How we comply |
|---|---|---|---|
| [OpenFreeMap](https://openfreemap.org/) | Basemap style and tiles | Free, including commercial use. Attribution "OpenFreeMap © OpenMapTiles Data from OpenStreetMap" is required. | Shown in the map's attribution control (from the style's own source attribution). |
| [Protomaps daily builds](https://maps.protomaps.com/builds/) | The per-unit offline fallback map (`deploy/offline-map.py`) | ODbL Produced Work of OpenStreetMap. Free; "© OpenStreetMap" must be visible. | The offline style's attribution reads "© OpenStreetMap contributors · Protomaps". Only this unit's own area is extracted, on the device. |
| [Protomaps basemaps-assets](https://github.com/protomaps/basemaps-assets) fonts | Offline map labels (Noto Sans) | SIL Open Font License 1.1 | Downloaded to the device, not redistributed by this repo. |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) via [Overpass API](https://overpass-api.de/) | Runway and taxiway outlines | ODbL | Covered by the map's OpenStreetMap attribution. Queried once per location, with retries, well within fair use. |
| [Nominatim](https://nominatim.org/) | Geocoding the address typed during setup | [Usage policy](https://operations.osmfoundation.org/policies/nominatim/): ≤1 request/s, identifying User-Agent, attribution | Setup-only and user-initiated, one request per address, with a descriptive User-Agent (`deploy/setupd.py`). |
| [RainViewer](https://www.rainviewer.com/api.html) | Weather radar overlay | **Free for personal or educational use**; they ask to be credited. | Credited in the map attribution while the overlay is on, and in the iPhone/iPad app's About (the app shows the same layer since 2026-10-01). The project is a personal, non-commercial device. **Anyone building a commercial product from this code -- including an App Store release by a company -- must replace this source.** |
| [Open-Meteo](https://open-meteo.com/en/terms) | Current weather on the empty-sky screen | **Free for non-commercial use** (≤10,000 calls/day); data CC BY 4.0 | Credited "Weather: Open-Meteo.com" on screen. Asked every 20 min at most, only while the screen is showing, with the position rounded to ~1 km. **A commercial product must use their paid API or another source.** |
| [SSEC RealEarth](https://ssec.wisc.edu/realearth/terms-of-use) (UW-Madison) | Lightning overlay (GOES-East GLM) | Free public use; the acknowledgement "Source: SSEC RealEarth, UW-Madison" is required. | That exact text is shown in the map attribution while the overlay is on, and in the app's About. |
| [planespotters.net](https://www.planespotters.net/photo/api) | Aircraft photos | Photo API terms (read 2026-10-09): free, no key; the photographer credited in text beside the image; the thumbnail must lead to the photo's page (a plain link in a browser; on a kiosk "an NFC tag or a QR code", not a URL as text); images loaded straight from their CDN by the browser or device that shows them, URLs unchanged, nothing stored; API JSON cached at most 24 h; a device must send a descriptive User-Agent with a contact; re-exposing the API through your own API is prohibited. | The kiosk (a device) asks through the unit's photo proxy, which sends `StratoScan/1.0 (+contact; ADS-B radar display)` (the contact from `STRATOSCAN_CONTACT`), caches JSON 24 h, and returns a QR code of the photo's page that the panel shows beside the credit. A browser -- the public page, the LAN, the iPhone app -- asks their API itself (CORS, with Origin or a contact User-Agent), so the unit's proxy is local-only (the gateway refuses `/photo` on the tunnel). Images come from their CDN unchanged; the thumbnail and the credit link to the photo's page. |
| [Wikimedia Commons](https://commons.wikimedia.org/) via the Wikipedia API | "Representative photo" of a type when no tail photo exists. Looked up by the unit (`deploy/photo-proxy.py`), not the viewer's browser, which loads only the image itself | Per-file free licenses (CC BY, CC BY-SA, GFDL, public domain…) requiring author and license credit | Only Commons-hosted files are shown (never English-Wikipedia-local, possibly non-free, files). Each is credited "Photo: author · license · Wikimedia Commons", linked to the file page in a normal browser. |
| [plane-alert-db](https://github.com/sdr-enthusiasts/plane-alert-db) | Notable-aircraft list (air ambulances, police, military, historic…) | ODbL 1.0 (database), DbCL 1.0 (contents) | Fetched weekly by each unit (`deploy/notable-db.py`), never copied into this repository, so no share-alike obligation attaches to it. Credited "Notable list: plane-alert-db (ODbL)" wherever an entry is shown. PIA aircraft are dropped, and names are kept only for military, government and police. |
| [adsb.lol](https://www.adsb.lol/privacy-license/) | Network comparison ("ghost" aircraft, receiver scorecard) | ODbL 1.0 | "Network data © ADSB.lol contributors, ODbL 1.0" appears on the scorecard. Queried at most every 15 s per unit, with rounded coordinates. |
| [adsb.im route API](https://adsb.im/) | Flight route (city pair) | Free public API | Batched and cached per callsign for the session, as tar1090 does. |
| [adsbdb](https://www.adsbdb.com/) | Registered owner of private aircraft | Free public API (MIT code; "be reasonable"); its aircraft data comes from PlaneBase, a members-only database whose terms are not public | Looked up once per aircraft by the unit, with failures backed off. Owner names are personal data: the audit of 2026-10-09 recommends showing them only on the owner's own screens, never the public page, and sourcing US tails from the FAA's public registry before any sale. |
| [Google Fonts](https://fonts.google.com/) | JetBrains Mono and Inter | SIL Open Font License 1.1 | Loaded from Google's CDN, not redistributed. |
| Google's favicon service (`www.google.com/s2/favicons`) and DuckDuckGo's icon service (`icons.duckduckgo.com`) | The iPhone app's airline marks (#60): an airline's own site icon beside its name on labels, details and alerts | Undocumented endpoints with no published terms; free today, revocable without notice. The marks are the airlines' trademarks, used only to identify the airline (nominative use). | Fetched by the phone and kept there; nothing about the owner is sent. Behind the "Airline marks" switch in Settings; `AirlineLogos.defaultOn` is false for a build meant for sale until marks with clear rights exist, and the name alone is shown without them. |
| [python-qrcode](https://github.com/lincolnloop/python-qrcode) (Debian `python3-qrcode`) | Draws the phone-pairing QR code on the unit | BSD-3-Clause | Installed from Debian on the unit; not copied into this repository. |
| [uhubctl](https://github.com/mvp/uhubctl) (Debian `uhubctl`) | Lets the watchdog cut USB power to revive a hung radio | GPL-2.0 | Installed from Debian on the unit and run as a separate program; not copied into this repository. Source via Debian (image `MANIFEST.txt`). |
| [tar1090 aircraft database](https://github.com/wiedehopf/tar1090-db) (the Mictronics aircraft database) | Aircraft type and registration from the ICAO hex | ODC-By 1.0, as the sdr-enthusiasts projects credit it; upstream's README names Mictronics as the source and states no licence itself | Read from the device's own tar1090 install at runtime, never copied. Credited "Aircraft types and registrations: Mictronics aircraft database via tar1090-db, ODC-By 1.0" on the kiosk's statistics screen and in the app's Credits. |
| [GitHub Releases API](https://docs.github.com/) | Signed OTA update delivery | GitHub Terms of Service | Unauthenticated, twice-daily checks per unit. |

## Software the device image depends on (installed, not shipped here)

`readsb` (GPL-3.0-or-later) and `tar1090` (GPL-2.0-or-later), Raspberry
Pi OS / Debian packages, Chromium, Tailscale, and lighttpd are installed on the
device from their own distributions. This repository contains no code from
them. **A pre-built device image would redistribute these**, and must then
include their licenses and offer the GPL components' source. See the
factory-image work in [docs/ROADMAP.md](docs/ROADMAP.md).

## Spoken alerts (installed by the installer, not shipped here)

| Component | License | Notes |
|---|---|---|
| [Piper](https://github.com/OHF-voice/piper1-gpl) `piper-tts` 1.8.0 | GPL-3.0-or-later | Installed from PyPI into its own virtualenv, and run as a separate program (`deploy/tts-service.py` talks to it); not linked into or shipped with this MIT code. It bundles espeak-ng data (GPL-3.0). |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT | Piper's dependency, installed from PyPI. |
| [LJSpeech voice](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ljspeech) `en_US-ljspeech-medium` | Trained on the public-domain LJ Speech dataset | Chosen because many Piper voices come from non-commercial datasets. Downloaded by the installer. |

A pre-built device image would redistribute these, and must then include
the GPL source offer (see the factory-image item in the roadmap).

## Opt-in FlightAware feeding (installed only when the owner turns it on)

| Component | License / terms | Notes |
|---|---|---|
| [PiAware](https://github.com/flightaware/piaware) | BSD-2-Clause | Installed from FlightAware's own apt repository, via their `flightaware-apt-repository` package, pinned by SHA-256 in `deploy/feeding.py`. Not shipped here, and must not be baked into a device image. |
| [FlightAware](https://www.flightaware.com/about/termsofuse) data sharing | FlightAware's terms of use | The owner accepts them by turning the option on. The setup page says plainly that the antenna's exact location is shared. |
| [Flightradar24 feeder](https://www.flightradar24.com/build-your-own) | Proprietary | **Not installed or automated by this project.** The setup page links to FR24's own instructions. |

## Not a license issue, but worth knowing

- **Trademark.** "Flightradar24" is a registered trademark of Flightradar24 AB.
  This project was called "FlightRadar" until 2026-09-28 and was renamed
  "StratoScan" to stay clear of it. Some internal identifiers (the
  `/opt/flightradar` install path, `flightradar-*` service names,
  `FLIGHTRADAR_*` settings) keep the old name so units already in service
  update cleanly; none of them is shown to people using the device.
- **Registered-owner names** shown for private aircraft come from public
  national registries (via adsbdb). They are shown on the device, never
  stored in this repository.
