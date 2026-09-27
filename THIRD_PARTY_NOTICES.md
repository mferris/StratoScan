# Third-party notices

FlightRadar's own code, enclosure designs and documentation are MIT-licensed
(see [LICENSE](LICENSE)). This file lists everything else the project ships
or uses, under what terms, and how each obligation is met. Reviewed
2026-09-27; re-check it whenever a dependency or data source is added.

## Shipped in this repository

| Component | Where | License | How the obligation is met |
|---|---|---|---|
| [MapLibre GL JS](https://github.com/maplibre/maplibre-gl-js) 5.24.0 | `vendor/maplibre-gl.js`, `.css` | BSD-3-Clause | The license header is kept intact at the top of the vendored file. |
| [MapLibre Native (iOS distribution)](https://github.com/maplibre/maplibre-gl-native-distribution) | `ios/` (Swift package, resolved at build time) | BSD-2-Clause | Not vendored. The iOS app's About/credits must carry its notice when the app ships. |
| Sound effects (kitten, plane themes) | `sounds/` | CC0 1.0 | No obligation. Sources and processing are still credited in each theme's `CREDITS.md`. |
| [OurAirports](https://ourairports.com/data/) airport table | `deploy/airports.json` | Public domain | None required; credited in the README. |
| Screenshot | `docs/screenshots/kiosk.png` | Map is an OpenStreetMap-derived work (ODbL) via OpenFreeMap / OpenMapTiles | Credited under the image in the README. Centred on RDU airport, not a private address. |

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
| [RainViewer](https://www.rainviewer.com/api.html) | Weather radar overlay | **Free for personal or educational use**; they ask to be credited. | Credited in the map attribution while the overlay is on. The project is a personal, non-commercial device. **Anyone building a commercial product from this code must replace this source.** |
| [SSEC RealEarth](https://ssec.wisc.edu/realearth/terms-of-use) (UW-Madison) | Lightning overlay (GOES-East GLM) | Free public use; the acknowledgement "Source: SSEC RealEarth, UW-Madison" is required. | That exact text is shown in the map attribution while the overlay is on. |
| [planespotters.net](https://www.planespotters.net/legal/termsofuse) | Aircraft photos | Photos must be hotlinked and credited to the photographer. | The image is loaded from planespotters' own servers and credited "© photographer · planespotters.net", linked to the photo page in a normal browser. The on-device proxy relays only the API's metadata, never the image. |
| [Wikimedia Commons](https://commons.wikimedia.org/) via the Wikipedia API | "Representative photo" of a type when no tail photo exists | Per-file free licenses (CC BY, CC BY-SA, GFDL, public domain…) requiring author and license credit | Only Commons-hosted files are shown (never English-Wikipedia-local, possibly non-free, files). Each is credited "Photo: author · license · Wikimedia Commons", linked to the file page in a normal browser. |
| [plane-alert-db](https://github.com/sdr-enthusiasts/plane-alert-db) | Notable-aircraft list (air ambulances, police, military, historic…) | ODbL 1.0 (database), DbCL 1.0 (contents) | Fetched weekly by each unit (`deploy/notable-db.py`), never copied into this repository, so no share-alike obligation attaches to it. Credited "Notable list: plane-alert-db (ODbL)" wherever an entry is shown. PIA aircraft are dropped, and names are kept only for military, government and police. |
| [adsb.lol](https://www.adsb.lol/privacy-license/) | Network comparison ("ghost" aircraft, receiver scorecard) | ODbL 1.0 | "Network data © ADSB.lol contributors, ODbL 1.0" appears on the scorecard. Queried at most every 15 s per unit, with rounded coordinates. |
| [adsb.im route API](https://adsb.im/) | Flight route (city pair) | Free public API | Batched and cached per callsign for the session, as tar1090 does. |
| [adsbdb](https://www.adsbdb.com/) | Registered owner of private aircraft | Free public API | Looked up once per aircraft when needed, with failures backed off. |
| [LiveATC.net](https://www.liveatc.net/) | ATC audio | Streams may not be used in third-party products. | **Not embedded or streamed.** The ATC option opens LiveATC's own player page in a normal browser tab, which is ordinary use of their website. It is disabled on the kiosk. |
| [Google Fonts](https://fonts.google.com/) | JetBrains Mono and Inter | SIL Open Font License 1.1 | Loaded from Google's CDN, not redistributed. |
| [tar1090 aircraft database](https://github.com/wiedehopf/tar1090-db) | Aircraft type and registration from the ICAO hex | No license stated upstream | Read from the device's own tar1090 install at runtime; never copied into this repository. |
| [GitHub Releases API](https://docs.github.com/) | Signed OTA update delivery | GitHub Terms of Service | Unauthenticated, twice-daily checks per unit. |

## Software the device image depends on (installed, not shipped here)

`readsb` (GPL-3.0-or-later) and `tar1090` (GPL-2.0-or-later), Raspberry
Pi OS / Debian packages, Chromium, Tailscale, and lighttpd are installed on the
device from their own distributions. This repository contains no code from
them. **A pre-built device image would redistribute these**, and must then
include their licenses and offer the GPL components' source. See the
factory-image work in [docs/ROADMAP.md](docs/ROADMAP.md).

## Not a license issue, but worth knowing

- **Trademark.** "Flightradar24" is a registered trademark of Flightradar24 AB,
  and this project's name, "FlightRadar", is close to it. Fine for a personal
  project; reconsider the name before any commercial or large-scale public
  launch.
- **Registered-owner names** shown for private aircraft come from public
  national registries (via adsbdb). They are shown on the device, never
  stored in this repository.
