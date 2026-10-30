# Shopping list

Everything you need to build a StratoScan from nothing: the radar, the case, and
optionally the iPhone app. After that is what is still to come for the
features in progress.

Claude keeps this current. A part is added when the design or an issue first
needs one, and moved along as it is ordered and fitted.

*Last updated 2026-10-29. Prices are approximate, in US dollars.*

## Build one StratoScan

### 1. The radar: receiver, computer, power

You need all of these. They also make a working radar on their own, in a web
browser, before any display or case.

| Part | Qty | Approx. | Notes |
|---|---|---|---|
| [Raspberry Pi 5, 4 GB](https://www.raspberrypi.com/products/raspberry-pi-5/) (or 8 GB) | 1 | $85 (8 GB: $130) | Measured on a radar after a day running everything (2026-10-04): 2.3 GB used, no swap. 4 GB leaves 1.6 GB spare; 8 GB leaves 5.7 GB nothing uses. 2 GB is too small. Prices rose sharply in 2026 |
| [Raspberry Pi Active Cooler](https://www.raspberrypi.com/products/active-cooler/) | 1 | $5 | Needed: it drives the radar full-time, and the case holds heat in. The FlyCatcher sits above it on tall standoffs |
| [Raspberry Pi RTC battery](https://www.raspberrypi.com/products/rtc-battery/) (ML-2020, rechargeable) | 1 | $5 | Keeps the clock through power cuts. Plugs into the Pi 5's BAT socket; the installer enables charging with `RTC_RECHARGEABLE=1`. **Never enable charging for a CR2032** |
| [Raspberry Pi 27 W USB-C power supply](https://www.raspberrypi.com/products/27w-power-supply/) | 1 | $12 | **Use this one, not a generic USB-C supply.** A weaker supply causes under-voltage and USB drop-outs. A generic 5 V supply tried on RDU (2026-10-10) held its voltage but put radio noise on it: with the FlyCatcher's amplifier on, the noise floor rose 9 dB and the radar heard 2 of 8 nearby aircraft instead of 7 of 10. The occasional under-voltage dips on this supply are the display drawing through the Pi ([#53](https://github.com/mferris/StratoScan/issues/53)), not the supply |
| High-endurance microSD card, 64–128 GB | 1 | $15–25 | For example SanDisk High Endurance or Samsung PRO Endurance. Writes measure about 0.8 GB/day (2026-10-14), fine for well over 10 years on an endurance card; an ordinary card is the likelier thing to wear out |
| ADS-B receiver: **[Nooelec FlyCatcher](https://www.nooelec.com/store/flycatcher.html)** | 1 | $110 | What RDU uses, and the choice for every unit (2026-10-04): it mounts on the Pi as a HAT, which the cases and the twin antenna mount are built around, and it has a 978 MHz input for later. The [FlightAware Pro Stick Plus](https://flightaware.store/products/pro-stick-plus) ($45) hears the same from a USB port, for anyone building a kit on a budget |
| Bootlace ferrules, an assortment with a crimper (0.75–1.5 mm²) | 1 kit | $15–20 | For the power fix's regulator ([#53](https://github.com/mferris/StratoScan/issues/53)): one on each wire under its screw terminals, 0.75–1.0 mm² on the 18 AWG pair and a 1.0–1.5 mm² one for the pigtail's black wires and braid together. Bare stranded wire splays and loosens under a screw clamp, and one stray strand at OUT+ shorts the 5 V; don't tin the ends either. Tug-test each, and re-tighten after a week (case design review, 2026-10-29) |
| M2.5 standoffs and screws for the FlyCatcher, tall enough to clear the Active Cooler (~16–20 mm) | 4 | $0–4 | Check the FlyCatcher's box first; most HATs include a set, but not always tall enough for the cooler. On the first unit the Pi, the FlyCatcher and its switches stand 46 mm from the back of the display in all (measured 2026-10-29), which leaves the back plate 10 mm or more behind the switches |
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
| SMA male to SMA female **bulkhead** jumper, RG316, ~40 cm (16") | 2 | ~$8–12 a pair | One per antenna, for the twin antenna mount: the bulkhead end in the mount, the plug on the FlyCatcher. The mount comes in two styles for the bulkhead's hex body, 8 mm (`antenna_mount_twin_8`) or 11 mm (`_11`); both are 6.35 mm barrels. Buy two of the same kind. **SMA, not RP-SMA** (RP-SMA has no centre pin). 40 cm since 2026-10-29: each runs down the right-hand side of the case, seen from behind, clear of the Pi's power lead, and takes 15 to 19 cm inside the back plate to its jack, depending on how low the jack is on the FlyCatcher's edge, and 2 to 3 cm more of slack, so the plate can be eased back 5 cm before the plugs are undone. A 30 cm jumper gives only about 18 cm once the mount has its share. The extra 10 cm of RG316 costs about 0.1 dB at 1090 MHz |
| Filament: **ASA** recommended | ~1 kg | $25–30 | Retro: one colour. Kitten: two colours for the head, more for the stand; see its README. **Why ASA:** a radar usually sits in a window for reception, where sun on a dark case can pass 60 °C. PLA starts to soften around 55–60 °C, so it's fine for a test fit but can sag or warp in a sunny window. PETG holds to about 75–80 °C; ASA and ABS hold to about 95–100 °C. ASA also doesn't yellow or go brittle in sunlight, and prints as cleanly as ABS. It needs an enclosed printer (the Bambu H2D is one). On a two-nozzle printer, print the support *interface* in a material that won't bond, so supports lift off cleanly. **For ASA/ABS: Bambu Support for ABS** (Bambu's store only) **or HIPS** (eSUN, on Amazon). Bambu Studio refuses PETG with ASA on one plate (low- and high-temperature filaments can't mix). Without either, ASA can support itself with a 0.2 mm top Z gap. For PETG: PLA, or Bambu Support for PLA/PETG. **Bought on Amazon:** Polymaker ASA, Dark Grey Green for the retro case (Grey if it sits in full sun) |
| Heat-set inserts and screws | see the table below | $10 in kits | Every hole, counted from the design files |
| **Power through the back plate** ([#53](https://github.com/mferris/StratoScan/issues/53)): every case needs these five. The charger plugs into a 12 V trigger board whose socket comes out through the back plate, and a regulator beside the Pi makes 5.2 V from it. At 5 V nothing tried got through a case well enough: through a panel-mount extension, even a 5 A / 100 W one, the Pi got 4.66–4.92 V and under-voltage warnings. Build steps: [power-fix.md](power-fix.md) | | | |
| · USB-C PD trigger board, **fixed at 12 V** | 1 | $5–10 (often a pack of several voltages) | Check its size before buying: `power_trigger_mount` is built round the board measured for it, 19.2 mm from its socket's face to its back edge, 10.7 mm across, 4.8 mm from its underside to the top of its socket, the socket standing 2 mm past its front edge. Check its voltage before wiring (power-fix.md, step 1). 9 V works with the official supply too; 20 V doesn't, because the official supply has no 20 V. The supply must offer 12 V (the official 27 W one does); a 5 V-only charger can't run this |
| · 5 V step-down regulator: 9–36 V in, 5.2 V out, 6 A at 9–24 V, 63 × 27 mm | 1 | $10–15 | `power_regulator_tray` is sized for it. Wire it from its screw terminals, never its USB socket, and keep it away from the receiver and its antenna leads. Plus about 25 cm each of red and black 18 AWG silicone wire, cut to 21 cm and twisted: from the trigger board across the lower half of the back plate to its input |
| · **Right-angled USB-C to USB-C cable, rated 5 A** (sold as 100 W or 240 W), its plugs the "up and down" angled kind (the cable leaves across the plug's flat face), 30 cm or longer, to cut a 32 cm pigtail from | 1 | $8–12 | Regulator to the Pi's own USB-C port (its 5 V pins sit under the FlyCatcher). Since 2026-10-29 it runs from the regulator at the bottom of the back plate up the left side of the Pi and along its top edge to the port, seen from behind, away from the antenna leads on the right: about 30 cm with the climb to the plug, plus 1 to 2 cm of slack so the plate can be eased back before the plug is pulled, so cut it 32 cm from the plug's tip (power-fix.md, step 4). A 5 A cable's power wires are usually 20 AWG: over 32 cm at 5 A they lose 0.11 V of the regulator's 5.2 V, at the limit (0.06 V at the 3 A the Pi seldom passes), and 18 AWG ones 0.07 V; the load reading in power-fix.md step 9 is the test. **Not** a ready-made right-angled pigtail with bare wires: the ones on sale are 22 AWG and 3 A, and lose 0.17 V at 5 A. Not a USB-A to USB-C cable either, whose power wires are thin. The right angle matters: in the Pi its cable points at the back plate and comes straight down beside the FlyCatcher; a straight plug stands 20 mm up toward the coax. Powered this way the Pi can't ask what the supply offers and limits its USB ports to 600 mA in all, too little for the display and the radios; the installer lifts that limit (`usb_max_current_enable=1` in config.txt) |
| · Snap-on ferrite clip, for a 4–5 mm cable | 1 | $1–2 | On the pigtail, about 5 cm from its plug |
| · Cable ties, **150 mm long, 3.6 mm wide** | 14 | $3–5 a pack | Since 2026-10-29: one through the saddle at each end of `power_regulator_tray`, gripping each lead just past its ferrule; one through each of the two grooves under the tray, round it and the regulator, which keeps the regulator in; and one at each of the back plate's ten tie bridges, four for the 12 V pair, four for the pigtail and two for the coax jumpers. The tray's loops are 85–100 mm round, more than a 100 mm tie closes on, so one size for all |
| Panel-mount USB-C extension cable | 0 | — | **For back plates printed before 2026-10-29 only**, which took one in their 11 × 8 mm window, and even then only with the power fix. Plates printed since have the trigger board's socket through their window instead, and the extension doesn't fit them: a new build doesn't need one |
| **Antenna mounting, choose one:** | | | |
| · puck socket (`antenna_mount`) | — | — | Holds FlightAware's desktop puck antenna directly. Nothing extra to buy |
| · SMA jack (`antenna_mount_sma`), **recommended** | | | Takes any SMA antenna, such as the whip above, or coax to a better spot |
| SMA female-to-female bulkhead barrel, with O-ring and nut | 1 | $8 (2-pack) | For example [onelinkmore](https://www.amazon.com/onelinkmore-Female-Waterproof-Bulkhead-Adapter/dp/B0GTV677Z4). **Not RP-SMA** |
| SMA male-to-male RG316 jumper, about 20 cm | 1 | $8 (2-pack) | Barrel to receiver. For example [HCFeng](https://www.amazon.com/HCFeng-Extension-Coaxail-coaxial-Assembly/dp/B0C2KQB1H3). **Not RP-SMA** |

**Every screw and insert, per hole** (counted from the design files, 2026-10-29). Inserts are brass heat-set, M3 ones 4.5 mm across the knurl (the Kadrick M2–M5 kit fits); holes are 4.0 mm.

| Where | Holes | Insert | Screw | Note |
|---|---|---|---|---|
| Front: the trim and the retainer, into the shell's front posts | 8 (the kitten uses 7) | M3 × 5 | M3 × 14 socket head | Press from the front, flush with the shelf |
| Back plate, into the shell's back posts | 8 | M3 × 6 | M3 × 8 | Press from the back face |
| Antenna mount (any of the three), into its flange | 3 | M3 × 5 | M3 × 8 | The screws come from inside the case, through the plate |
| The trigger board's mount, to the back plate | 2 | M3 × 3 | M3 × 8 button head | The inserts go in the plate beside the USB-C window, flush with both faces, and the screws come from inside the case through the mount's ears. Button heads, not socket caps: one is under a speaker |
| The regulator's tray, to the back plate | 2 | M3 × 5 | M3 × 8 button head | Since 2026-10-29. The inserts go in two bosses on the plate's inner face, flush with their tops; the screws go down through the tray's two caps |
| The stop behind the trigger board, through the mount's side walls | 2 | none | M2 × 8 | They cut their own thread in the walls and in `power_trigger_stop`, which replaced the 1.75 mm filament pin. Drive them snug, not hard: past seating they strip the wall's thread |
| The trial fit in `usbc_gauge`, before the plate | 2 | M3 × 3 | the mount's own, moved to the plate after | The inserts stay in the coupon, and the trial spends the stop's crush ribs. A stop that comes out is never fitted again, so print three `power_trigger_stop`s: the coupon's, the plate's and a spare |
| Older plates only (printed before 2026-10-29): a USB-C panel connector | 2 | none | M3 × 6 with nuts, or the connector's own | Not counted below. Holes 16.5–17 mm apart (short slots); the heads sit in the 2 mm pocket round the connector (plates printed from 2026-10-10 on) |
| Speakers, to their brackets | 4 each, 8 | optional M2 × 3 | M2 × 6, or M2 self-tapping | 2.6 mm pilots for the self-tappers; drill to 3.0 for inserts |
| Pi, to the display's back | 4 | none | M2.5 × 6 and standoffs, in the display's box | |
| FlyCatcher, onto the Pi | 4 | none | M2.5 standoffs, ~16–20 mm, and screws | tall enough to clear the cooler |
| Twin antenna mount's two SMA bulkheads | 2 | none | the jumpers' own nuts | an 8 mm (5/16") open-ended spanner, a quarter to half a turn past finger tight |
| Twin antenna mount's cover | 5 | M2 × 3 | M2 × 6 | 3.0 mm holes for a 3.2 mm knurl (measure the kit's) |
| **To buy per radar** | | **25 × M3 (13 of 5 mm, 8 of 6 mm, 4 of 3 mm); 5 × M2; 8 × M2 optional** | **8 × M3×14, 11 × M3×8, 4 × M3×8 button head, 2 × M2×8, 13 × M2×6, 8 × M2.5** | one M3 kit and one M2/M2.5 kit cover several radars |

**Everything for one radar, totalled:** about **$520** in parts with the 4 GB Pi (about $565 with 8 GB), of which the display is $160, the FlyCatcher $110 and the Pi $85; the forty-odd dollars of cables, standoffs, cells and fasteners, and the thirty or so of the power fix's boards and pigtail, are easy to forget and are all listed above. Printer time: about 20 hours; filament about 700 g.

**Tools (once):**
- a 3D printer (designed on a Bambu Lab printer, with an AMS for the kitten's colours);
- a soldering iron with a heat-set insert tip, and a flat piece of metal to press inserts flush;
- hex keys (1.5, 2 and 2.5 mm), an 8 mm (5/16") open-ended spanner for the antenna jacks' nuts, a small Phillips, a microSD reader;
- glue stick for the print bed; hot glue or Kapton tape for the speaker plug's strain relief; heat-shrink; a few spare cable ties.

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

**Rough total for one unit:** about $520 with the 4 GB Pi, filament
included (totalled above), plus the phone you already have.

## Coming later

These are for roadmap items that aren't built yet. **Wait until each item
starts before buying:** the exact part may change.

| Part | For | Approx. |
|---|---|---|
| [Adafruit VEML7700 lux sensor (#4162)](https://www.adafruit.com/product/4162) and [STEMMA QT cable (#4397)](https://www.adafruit.com/product/4397) | [5.5 light sensor](https://github.com/mferris/StratoScan/issues/27) | $6 |
| The control arc's parts (Retro with Dials case): an EC11 rotary encoder with push switch and 20 mm D shaft, a 12 mm momentary metal push button no more than 16 mm deep behind the panel, tags included (a short-body one; the common 21 mm one doesn't fit behind the arc's face), a 5 mm common-cathode RGB LED (diffused) with three 220 Ω resistors, 2 × M3 x 10 screws and M3 x 5 inserts, 2 × M2.5 x 8 countersunk self-tappers, thin wire and header jumpers; see [its README](../enclosure/Retro%20Radar%20with%20Dials/README.md#buy) | [5.1 control arc](https://github.com/mferris/StratoScan/issues/22) | ~$12 |
| Presence sensor: LD2410 mmWave, or a PIR | [5.2 presence wake](https://github.com/mferris/StratoScan/issues/23) | ~$10 |
| 978 MHz receiver: nothing to buy. The FlyCatcher's second radio is the 978 MHz one, and the Discovery bundle above has the 978 whip. The software has run since 2026-10-10, but RDU hasn't decoded a 978 message yet, not even a ground-station uplink: the antenna or where it sits | [5.3 UAT receiver, US only](https://github.com/mferris/StratoScan/issues/24) | $0 |
