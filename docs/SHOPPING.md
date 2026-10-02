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

**Connect the receiver directly.** The FlyCatcher mounts on the Pi as a HAT,
but its data still goes over USB: use the short USB-A to micro-USB jumper that
comes with it, plugged straight into one of the Pi's ports. **Don't add a
USB adapter or extension** (a right-angle USB-A adapter, a panel-mount
passthrough). On RDU a right-angle adapter made the receiver drop off USB
dozens of times an evening ("Cannot enable. Maybe the USB cable is bad?");
the screen showed NO SIGNAL each time until the watchdog reset it. With the
adapter removed, the drop-outs stopped.

**If the speakers won't fit beside it** (2026-10-02): the straight USB-A plug in
the Pi, plus the curve of its cable, sticks out about 35–45 mm past the Pi's
edge, where the cases' side speakers sit. The fix to try first is a **one-piece
short micro-USB to USB-A cable, about 15–20 cm, with a right-angle (90°) USB-A
end**. It's moulded as one part, so unlike the adapter it adds no extra
connection. Angled ends come as "up" or "down"; which one turns the cable toward
the back plate depends on which of the Pi's ports it's in, so a pair of each is
the easy way (about $8–12). If the drop-outs come back with it, go back to the
FlyCatcher's own cable: the watchdog still recovers the receiver either way.

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
| M3 brass heat-set inserts: **have them** (Kadrick M2–M5 kit, 520 pcs) | 19 per case (18 for the kitten) | — | Holes sized for this kit (4.0 mm). 8 × M3×5 for the front, 8 × M3×6 for the back plate, 3 × M3×5 in the antenna mount; optionally 8 × M2×3 for the speakers. Pressed in with a soldering iron. Any M3 insert about 4.5 mm across fits |
| M3 socket-head screws | 21 per case (20 for the kitten) | $8 | **M3 × 14:** 8 for the front trim (7 on the kitten). **M3 × 8:** 8 for the back plate and 3 for the antenna mount. 2 more for the USB-C connector, if it doesn't come with its own. A kit with these lengths is easiest |
| M2 × 6 screws (optional) | 8 | — | Only if the speakers go on M2 inserts rather than their self-tapping screws |
| M2.5 screws, about 6 mm | 4 | — | Hold the Pi onto the back plate's standoffs. Usually in the same kit |
| Panel-mount USB-C extension cable, **rated 5 A / 100 W (e-marked)**, with two M3 screw holes 16.5 mm apart | 1 | $10–15 | Brings power in through the back plate. **The rating matters:** a thin extension dropped the Pi's 5 V supply to 4.96 V and caused under-voltage several times an hour, gone when the supply was plugged straight in (5.08 V). The cutout is 11 × 6.5 mm; print `usbc_gauge` to test-fit a different connector first |
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
| **To build the app yourself:** a Mac with Xcode, and the Apple Developer Program ($99/yr) | Only needed to build and install the app yourself |
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
