# Shopping list

Everything you need to build a StratoScan from nothing: the radar, the case, and
optionally the iPhone app. After that is what is still to come for the
features in progress.

Claude keeps this current. A part is added when the design or an issue first
needs one, and moved along as it is ordered and fitted.

*Last updated 2026-09-30. Prices are approximate, in US dollars.*

## Build one StratoScan

### 1. The radar: receiver, computer, power

You need all of these. They also make a working radar on their own, in a web
browser, before any display or case.

| Part | Qty | Approx. | Notes |
|---|---|---|---|
| [Raspberry Pi 5, 8 GB](https://www.raspberrypi.com/products/raspberry-pi-5/) | 1 | $80 | What StratoScan is developed and measured on. The kiosk browser needs the headroom |
| [Raspberry Pi Active Cooler](https://www.raspberrypi.com/products/active-cooler/) | 1 | $5 | Needed: it drives the radar full-time, and the case holds heat in |
| [Raspberry Pi 27 W USB-C power supply](https://www.raspberrypi.com/products/27w-power-supply/) | 1 | $12 | A weaker supply causes under-voltage and USB drop-outs |
| High-endurance microSD card, 64–128 GB | 1 | $15–25 | For example SanDisk High Endurance or Samsung PRO Endurance. Writes measure about 2.25 GB/day, fine for about 10 years on an endurance card |
| ADS-B receiver (1090 MHz SDR with a built-in filter) | 1 | $30–46 | Either the Nooelec FlyCatcher (what RDU uses) or the [FlightAware Pro Stick Plus](https://flightaware.store/products/pro-stick-plus) |
| [NooElec ADS-B Discovery 5 dBi antenna bundle](https://www.amazon.com/NooElec-ADS-B-Discovery-Antenna-Bundle/dp/B01J9DH9U2) | 1 | $25 | 1090 MHz whip, plus a 978 MHz one for the future UAT receiver. **Placement matters more than any part:** a window or outdoor spot heard 14 aircraft where an indoor puck heard 1 |

**Check first:** set up the Pi, receiver and antenna, and confirm real
aircraft appear before you buy the display. See
[project-spec.md](project-spec.md), "Purchase Plan".

### 2. The display

| Part | Qty | Approx. | Notes |
|---|---|---|---|
| [Waveshare 7″ round LCD, 1080×1080](https://www.waveshare.com/7inch-1080x1080-lcd.htm) | 1 | $160 | HDMI video plus USB touch. The cases are designed around it |
| Micro-HDMI to HDMI cable, short (30 cm or less) | 1 | $8 | The Pi 5 has **micro**-HDMI ports. A slim or right-angle cable is easier to fit in the case |
| USB-A to USB-C **data** cable, short | 1 | $6 | Carries the touch signal from the panel to the Pi. **Charge-only cables leave touch dead** while the picture still works |
| Waveshare 8 Ω 5 W speaker pair | 1 pair | $10 | For the alert chimes and spoken announcements. They connect to the panel's driver board, and the sound travels over HDMI. The cases have brackets for them |

### 3. The case (3D printed)

Two designs, both in [`enclosure/`](../enclosure/):
- **Retro:** a ship's-instrument look.
- **Kitten:** a cat with the display as its face.

They share the back plate and antenna mount.

| Part | Qty | Approx. | Notes |
|---|---|---|---|
| Filament, PLA or PETG | ~1 kg | $20 | Retro: one colour. Kitten: two colours for the head, more for the stand; see its README |
| M3 brass heat-set inserts, short (fits a 4.2 mm hole) | 19 (buy 50) | $8 | 8 for the front, 8 for the back plate, 3 for the antenna mount. Pressed in with a soldering iron |
| M3 socket-head screws, assorted 6–20 mm | about 21 | $8 | 8 for the front trim, 8 for the back plate, 3 for the antenna mount, 2 for the USB-C connector. A kit is easiest; the exact lengths aren't listed yet |
| M2.5 screws, about 6 mm | 4 | — | Hold the Pi onto the back plate's standoffs. Usually in the same kit |
| Panel-mount USB-C extension cable, with two M3 screw holes 16.5 mm apart | 1 | $8 | Brings power in through the back plate. The cutout is 11 × 6.5 mm; print `usbc_gauge` to test-fit a different connector first |
| **Antenna mounting, choose one:** | | | |
| · puck socket (`antenna_mount`) | — | — | Holds FlightAware's desktop puck antenna directly. Nothing extra to buy |
| · SMA jack (`antenna_mount_sma`), **recommended** | | | Takes any SMA antenna, such as the whip above, or coax to a better spot |
| SMA female-to-female bulkhead barrel, with O-ring and nut | 1 | $8 (2-pack) | For example [onelinkmore](https://www.amazon.com/onelinkmore-Female-Waterproof-Bulkhead-Adapter/dp/B0GTV677Z4). **Not RP-SMA** |
| SMA male-to-male RG316 jumper, about 20 cm | 1 | $8 (2-pack) | Barrel to receiver. For example [HCFeng](https://www.amazon.com/HCFeng-Extension-Coaxail-coaxial-Assembly/dp/B0C2KQB1H3). **Not RP-SMA** |

**Tools:**
- a 3D printer (designed on a Bambu Lab printer, with an AMS for the kitten's colours);
- a soldering iron with a heat-set insert tip;
- hex keys.

### 4. Optional

| Part | For | Approx. | Notes |
|---|---|---|---|
| ML-2020 **rechargeable** RTC cell | Keeping the clock through power cuts | $5 | Plugs into the Pi 5's battery connector. Run the installer with `RTC_RECHARGEABLE=1`. **Never enable charging for a CR2032**, which isn't rechargeable |
| Wall anchors and screws | Wall mounting | — | Both cases also have a desk stand |

### 5. The iPhone app

| Need | Notes |
|---|---|
| An iPhone on iOS 17.2 or later | For the app, widget, alerts and Live Activity |
| An Apple Watch, Series 5 / SE or later | Only for the Watch app, still to come (Phase 3). Earlier models have no compass |
| **To build the app yourself:** a Mac with Xcode, and the Apple Developer Program ($99/yr) | Not needed once the app is on the App Store |
| **To run your own relay (push alerts):** a free Cloudflare account | See [relay/README.md](../relay/README.md) |

**Rough total for one unit:** about $400, plus filament and the phone you
already have.

## Coming later

These are for roadmap items that aren't built yet. **Wait until each item
starts before buying:** the exact part may change.

| Part | For | Approx. |
|---|---|---|
| [Adafruit VEML7700 lux sensor (#4162)](https://www.adafruit.com/product/4162) and [STEMMA QT cable (#4397)](https://www.adafruit.com/product/4397) | [5.5 light sensor](https://github.com/mferris/StratoScan/issues/27) | $6 |
| Rotary encoder | [5.1 rotating bezel](https://github.com/mferris/StratoScan/issues/22) | ~$5 |
| Presence sensor: LD2410 mmWave, or a PIR | [5.2 presence wake](https://github.com/mferris/StratoScan/issues/23) | ~$10 |
| 978 MHz SDR, for example FlightAware's 978 MHz Pro Stick Plus (the antenna is already in the bundle above) | [5.3 UAT receiver, US only](https://github.com/mferris/StratoScan/issues/24) | ~$25–40 |

