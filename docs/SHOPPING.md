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
| [Raspberry Pi 5, 4 GB](https://www.raspberrypi.com/products/raspberry-pi-5/) (or 8 GB) | 1 | $85 (8 GB: $130) | Measured on a radar after a day running everything (2026-10-04): 2.3 GB used, no swap. 4 GB leaves 1.6 GB spare; 8 GB leaves 5.7 GB nothing uses. 2 GB is too small. Prices rose sharply in 2026 |
| [Raspberry Pi Active Cooler](https://www.raspberrypi.com/products/active-cooler/) | 1 | $5 | Needed: it drives the radar full-time, and the case holds heat in. The FlyCatcher sits above it on tall standoffs |
| [Raspberry Pi RTC battery](https://www.raspberrypi.com/products/rtc-battery/) (ML-2020, rechargeable) | 1 | $5 | Keeps the clock through power cuts. Plugs into the Pi 5's BAT socket; the installer enables charging with `RTC_RECHARGEABLE=1`. **Never enable charging for a CR2032** |
| [Raspberry Pi 27 W USB-C power supply](https://www.raspberrypi.com/products/27w-power-supply/) | 1 | $12 | A weaker supply causes under-voltage and USB drop-outs |
| High-endurance microSD card, 64–128 GB | 1 | $15–25 | For example SanDisk High Endurance or Samsung PRO Endurance. Writes measure about 2.25 GB/day, fine for about 10 years on an endurance card |
| ADS-B receiver: **[Nooelec FlyCatcher](https://www.nooelec.com/store/flycatcher.html)** | 1 | $110 | What RDU uses, and the choice for every unit (2026-10-04): it mounts on the Pi as a HAT, which the cases and the twin antenna mount are built around, and it has a 978 MHz input for later. The [FlightAware Pro Stick Plus](https://flightaware.store/products/pro-stick-plus) ($45) hears the same from a USB port, for anyone building a kit on a budget |
| M2.5 standoffs and screws for the FlyCatcher, tall enough to clear the Active Cooler (~16–20 mm) | 4 | $0–4 | Check the FlyCatcher's box first; most HATs include a set, but not always tall enough for the cooler |
| Short **one-piece** micro-USB to USB-A cable with a right-angle USB-A end, 15–20 cm (for example the CableCreation 2-pack) | 1 | $5 | FlyCatcher to the Pi. The angled plug clears the side speakers; the straight jumper in the FlyCatcher's box doesn't. One moulded cable, never an adapter (see below) |
| [NooElec ADS-B Discovery 5 dBi antenna bundle](https://www.amazon.com/NooElec-ADS-B-Discovery-Antenna-Bundle/dp/B01J9DH9U2) | 1 | $25 | Hinged whips for 1090 and 978 MHz; the FlyCatcher has an input for each. Its small right-angle pigtails are MCX, for USB-stick receivers, and aren't needed. **Placement matters more than any part:** a window or outdoor spot heard 14 aircraft where an indoor puck heard 1 |

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
| Pre-crimped 1.25 mm 4-pin cable (sold as "Micro JST 1.25" or "Molex PicoBlade compatible"), 10–15 cm | 1 (packs of 10) | $8 a pack | The panel's speaker socket is this plug. Solder its wires to the speaker leads and heat-shrink them: hand-crimped plugs come apart |
| Pi mounting to the display's back: 4 × M2.5 standoffs and screws | 4 | included | In the display's box |

### 3. The case (3D printed)

Two designs, both in [`enclosure/`](../enclosure/):
- **Retro:** a ship's-instrument look.
- **Kitten:** a cat with the display as its face.

They share the back plate and antenna mount.

| Part | Qty | Approx. | Notes |
|---|---|---|---|
| SMA male to SMA female **bulkhead** jumper, RG316, ~30 cm (12") | 2 | ~$8–10 a pair | One per antenna, for the twin antenna mount (`antenna_mount_twin`): the bulkhead end in the mount, the plug on the FlyCatcher. **SMA, not RP-SMA** (RP-SMA has no centre pin) |
| Filament: **ASA** recommended | ~1 kg | $25–30 | Retro: one colour. Kitten: two colours for the head, more for the stand; see its README. **Why ASA:** a radar usually sits in a window for reception, where sun on a dark case can pass 60 °C. PLA starts to soften around 55–60 °C, so it's fine for a test fit but can sag or warp in a sunny window. PETG holds to about 75–80 °C; ASA and ABS hold to about 95–100 °C. ASA also doesn't yellow or go brittle in sunlight, and prints as cleanly as ABS. It needs an enclosed printer (the Bambu H2D is one). On a two-nozzle printer, print the support *interface* in a material that won't bond, so supports lift off cleanly. **For ASA/ABS: Bambu Support for ABS** (Bambu's store only) **or HIPS** (eSUN, on Amazon). Bambu Studio refuses PETG with ASA on one plate (low- and high-temperature filaments can't mix). Without either, ASA can support itself with a 0.2 mm top Z gap. For PETG: PLA, or Bambu Support for PLA/PETG. **Bought on Amazon:** Polymaker ASA, Dark Grey Green for the retro case (Grey if it sits in full sun) |
| Heat-set inserts and screws | see the table below | $10 in kits | Every hole, counted from the design files |
| Panel-mount USB-C extension cable, **rated 5 A / 100 W (e-marked)**, with two M3 screw holes 16.5 mm apart | 1 | $10–15 | Brings power in through the back plate. **The rating matters:** a thin extension dropped the Pi's 5 V supply to 4.96 V and caused under-voltage several times an hour, gone when the supply was plugged straight in (5.08 V). The cutout is 11 × 6.5 mm; print `usbc_gauge` to test-fit a different connector first |
| **Antenna mounting, choose one:** | | | |
| · puck socket (`antenna_mount`) | — | — | Holds FlightAware's desktop puck antenna directly. Nothing extra to buy |
| · SMA jack (`antenna_mount_sma`), **recommended** | | | Takes any SMA antenna, such as the whip above, or coax to a better spot |
| SMA female-to-female bulkhead barrel, with O-ring and nut | 1 | $8 (2-pack) | For example [onelinkmore](https://www.amazon.com/onelinkmore-Female-Waterproof-Bulkhead-Adapter/dp/B0GTV677Z4). **Not RP-SMA** |
| SMA male-to-male RG316 jumper, about 20 cm | 1 | $8 (2-pack) | Barrel to receiver. For example [HCFeng](https://www.amazon.com/HCFeng-Extension-Coaxail-coaxial-Assembly/dp/B0C2KQB1H3). **Not RP-SMA** |

**Every screw and insert, per hole** (counted from the design files, 2026-10-04). Inserts are brass heat-set, M3 ones 4.5 mm across the knurl (the Kadrick M2–M5 kit fits); holes are 4.0 mm.

| Where | Holes | Insert | Screw | Note |
|---|---|---|---|---|
| Front: the trim and the retainer, into the shell's front posts | 8 (the kitten uses 7) | M3 × 5 | M3 × 14 socket head | Press from the front, flush with the shelf |
| Back plate, into the shell's back posts | 8 | M3 × 6 | M3 × 8 | Press from the back face |
| Antenna mount (any of the three), into its flange | 3 | M3 × 5 | M3 × 8 | The screws come from inside the case, through the plate |
| USB-C panel connector, to the back plate | 2 | none | M3 × 6 with nuts, or the connector's own | Holes 16.5 mm apart |
| Speakers, to their brackets | 4 each, 8 | optional M2 × 3 | M2 × 6, or M2 self-tapping | 2.6 mm pilots for the self-tappers; drill to 3.0 for inserts |
| Pi, to the display's back | 4 | none | M2.5 × 6 and standoffs, in the display's box | |
| FlyCatcher, onto the Pi | 4 | none | M2.5 standoffs, ~16–20 mm, and screws | tall enough to clear the cooler |
| Twin antenna mount's two SMA bulkheads | 2 | none | the jumpers' own nuts | an 8 mm (5/16") open-ended spanner, a quarter to half a turn past finger tight |
| Twin antenna mount's cover | 5 | M2 × 3 | M2 × 6 | 3.0 mm holes for a 3.2 mm knurl (measure the kit's) |
| **To buy per radar** | | **19 × M3 (11 of 5 mm, 8 of 6 mm); 5 × M2; 8 × M2 optional** | **8 × M3×14, 11 × M3×8, 2 × M3×6 (+2 nuts), 13 × M2×6, 8 × M2.5** | one M3 kit and one M2/M2.5 kit cover several radars |

**Everything for one radar, totalled:** about **$500** in parts with the 4 GB Pi (about $545 with 8 GB), of which the display is $160, the FlyCatcher $110 and the Pi $85; the forty-odd dollars of cables, standoffs, cells and fasteners are easy to forget and are all listed above. Printer time: about 20 hours; filament about 700 g.

**Tools (once):**
- a 3D printer (designed on a Bambu Lab printer, with an AMS for the kitten's colours);
- a soldering iron with a heat-set insert tip, and a flat piece of metal to press inserts flush;
- hex keys (1.5, 2 and 2.5 mm), an 8 mm (5/16") open-ended spanner for the antenna jacks' nuts, a small Phillips, a microSD reader;
- glue stick for the print bed; hot glue or Kapton tape for the speaker plug's strain relief; heat-shrink; a few zip ties.

### 4. Optional

| Part | For | Approx. | Notes |
|---|---|---|---|
| Rubber feet for the stand | Desk use | $2 | Self-adhesive, 4 |
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
