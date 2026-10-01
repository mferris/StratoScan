# StratoScan brand

The StratoScan mark is called **Climb**: a radar scope with its sweep, and
three blips climbing toward it. They change colour with height, the way the
radar colours altitude: green near the ground, cyan, then white where the air
runs out.

These files are **not MIT**: see [LICENSE](LICENSE). Use them to refer to
StratoScan. A fork needs its own name and icon.

## Files

| File | What it's for |
|---|---|
| `symbol.svg` | The mark on a transparent background, full detail (above about 32 px) |
| `symbol-small.svg` | The mark for 32 px and below: two larger blips and a heavier ring, so it doesn't smudge |
| `symbol-mono.svg`, `symbol-mono-small.svg` | One colour (`currentColor`): widgets, embossing, printing on a case |
| `icon.svg` | The app icon: the mark on the sky background. iOS rounds the corners |
| `icon-small.svg` | The favicon (inlined into the kiosk, setup and fleet pages) |
| `icon-dark.svg`, `icon-tinted.svg` | iOS's dark and tinted home-screen icons |
| `logo-on-dark.svg`, `logo-on-light.svg` | The mark with the wordmark, for dark and light pages |
| `social-preview.png` | GitHub's social preview, 1280×640 |

The PNG app icons in `ios/Radome/App/Assets.xcassets/AppIcon.appiconset` and
`ios/RadomeWatch/Assets.xcassets` are 1024 px renders of `icon*.svg`.

## Colours

| | Hex |
|---|---|
| Sky (background) | `#0a1a3a` |
| Ring | `#274a86` |
| Sweep | `#5ee7ff` |
| Blips, low to high | `#3ddc97`, `#5ee7ff`, `#ffffff` |
| "Scan" on a light page | `#0e7fa3` |

The wordmark is Chakra Petch SemiBold (SIL Open Font License, `FONT-OFL.txt`),
with its letters converted to outlines, so nothing depends on the font being
installed.

## Changing the mark

Edit `make.py`, the one place the shapes and colours are defined, and run it:

```sh
python3 assets/brand/make.py --font path/to/ChakraPetch-SemiBold.ttf
```

The `--font` flag needs `fontTools` (`pip install fonttools`) and is only
needed to rebuild the wordmark. Then re-render the PNGs from the SVGs at
1024 px (app icons) and 1280×640 (social preview). Any browser screenshot does
it; the originals were made with headless Chrome. Then update the favicon
`data:` URIs in `index.html`, `deploy/setup-ui.html` and `relay/src/index.js`.

## Where it came from

Designed on 2026-09-30 with Claude (Anthropic), from the brief in issue #38.
The owner chose the direction and colours from generated options. The
shapes are simple geometric primitives; no third-party artwork was used.
