# The power fix: 12 V into the case, 5 V made beside the Pi

Roadmap 5.7, [#53](https://github.com/mferris/StratoScan/issues/53).
**Running on the first unit since 2026-10-17.** In its first minutes, with
the panel lit and both radios on, the Pi got 5.01–5.08 V (5.05 V on
average), with no under-voltage. The 1090 MHz noise floor was unchanged at
−32.4 dBFS, so the regulator adds no noise the receiver can hear. A longer
run's numbers come next.

## Why

The supply reaches the Pi through the back plate's panel-mount USB-C
extension, and at 5 V no extension tried is good enough. The official 27 W
supply plugged straight into the Pi gives 5.06–5.14 V. Through a thin
extension the Pi got 4.96 V, and under-voltage several times an hour.
Through a 5 A / 100 W e-marked one it got 4.66–4.92 V, with 9 under-voltage
warnings in 37 minutes.

The fix asks the supply for 12 V instead, carries that through the case, and
makes 5.2 V right beside the Pi. At 12 V the wires carry less than half the
current, and the regulator takes anything from 9 to 36 V, so the extension's
loss stops mattering.

```mermaid
flowchart LR
  A["Charger<br/>official 27 W"] -- "USB-C, 12 V<br/>(through the back plate)" --> B["USB-C trigger board<br/>fixed at 12 V"]
  B -- "18 AWG pair, 12 V" --> C["5 V regulator<br/>9–36 V in, 5.2 V out"]
  C -- "USB-C pigtail + ferrite, 5.2 V" --> D["Raspberry Pi 5<br/>its own USB-C port"]
```

## Parts

| Part | Notes |
|---|---|
| A charger that offers **12 V** over USB-C PD | The official Raspberry Pi 27 W supply does (12 V at 2.25 A). A 5 V-only charger, such as a Pi-style 5 V 5 A clone, can't power this: the trigger board gets 5 V, and the regulator needs at least 9 V (found on RDU, 2026-10-23). If the label lists no 12 V output, it won't work. A back plate printed since 2026-10-29 says so beside its socket: `USB-C PD 12V 27W` |
| USB-C PD trigger board, **fixed at 12 V** | 9 V also works with the official supply; 20 V doesn't, because the official supply has no 20 V. A 5 V board is no use here. Most come in packs of several voltages that look alike, so check before wiring (step 1) |
| 5 V step-down regulator: 9–36 V in, 5.2 V out, 6 A at 9–24 V | Wire it from its screw terminals, never its USB socket |
| 18 AWG silicone wire, red and black | About 25 cm of each, cut to 21 cm (step 2): in the case the twisted pair takes about 20 cm, from the trigger board across the lower half of the back plate, over the top of the low vent and round the far end of the regulator's tray to its input |
| A **right-angled USB-C to USB-C cable rated 5 A** (sold as 100 W or 240 W), its plugs the kind sold as "up and down" angled (the cable leaves across the plug's flat face, not out of its side), **50 cm or longer** (30 cm is too short for a 32 cm cut), to cut a **32 cm** pigtail from (step 4) | Its power wires are usually 20 AWG, rarely stated: over 32 cm at 5 A two of them lose 0.11 V of the regulator's 5.2 V, at the limit, though the Pi seldom draws more than 3 A (0.06 V); 18 AWG ones lose 0.07 V. Step 9's reading under load is the test. Don't use a ready-made right-angled pigtail with bare wires: the ones on sale are 22 AWG and rated 3 A, and lose 0.17 V at 5 A. Not a USB-A to USB-C cable either: its power wires are thin. The case needs the right angle (since 2026-10-29): in the Pi its cable points at the back plate, so it comes straight down to the plate beside the FlyCatcher and runs along it, away from the antenna leads; a straight plug stands 20 mm up toward them |
| Snap-on ferrite clip | For the pigtail, one that fits a 4-5 mm cable |
| Bootlace ferrules, a kit with a crimper | One on each wire under the regulator's screw terminals (steps 2 and 5): 0.75-1.0 mm² on the 18 AWG pair and the pigtail's red wire, and one 1.0-1.5 mm² for the pigtail's black wires and braid together. Bare stranded wire splays and loosens under a screw clamp, and one stray strand at OUT+ shorts the 5 V; don't tin the ends either. The tray's saddles are placed for a ferrule's 8 mm collar |
| Heat-shrink, a soldering iron, a multimeter | |
| For the case: a back plate printed from the design of 2026-10-29 or later, with the trigger board's window, the regulator tray's two bosses, ten tie bridges and two curbs, and `power_trigger_mount`, three `power_trigger_stop`s and `power_regulator_tray`, printed (`usbc_gauge` too, to try the fit first); four M3 × 8 button-head screws, four M3 × 3 heat-set inserts and two M3 × 5 ones; two M2 × 8 screws; **14 cable ties, 150 mm long and 3.6 mm wide** | In the case folders; see [In the case](#in-the-case). Two of the M3 × 8s and the M3 × 3 inserts hold the trigger board's mount, the other two and the M3 × 5s the regulator's tray. A trial fit on `usbc_gauge` spends two of the M3 × 3 inserts, which stay in it, and one stop's crush ribs. A stop is good for one fitting, so the third is a spare, for a board that has to be re-seated. The ties: one at each end of the tray, one through each of the two grooves under it, and one at each of the plate's ten tie bridges. The tray's loops are 82-100 mm round, too big for a 100 mm tie to close, so one size, 150 mm, for all |

The Pi's 5 V pins would also take the regulator's output, but they sit under
the FlyCatcher, so the 5.2 V goes into the Pi's own USB-C port instead.

## Before you start: the Pi's USB current

Powered this way, the Pi can't ask its supply what it offers, so it limits its
USB ports to 600 mA in all. That's too little for the display, which draws
through the Pi's USB, and the receiver's two radios. The installer lifts the
limit with `usb_max_current_enable=1` in `/boot/firmware/config.txt`. Check
that it's there:

```sh
grep usb_max_current_enable /boot/firmware/config.txt
```

Don't use `PSU_MAX_CURRENT` in the EEPROM for this. Writing the EEPROM also
flashes the newest bootloader, and this project never moves the bootloader.

## Build and test on the bench

The Pi isn't involved until step 6.

1. **Check the trigger board.** Plug the charger into it, with nothing on its
   output. The meter on its output pads should read about 12 V. If it reads
   5 V, it's a 5 V board, or a charger without 12 V. Unplug.
2. **Trigger to regulator.** Cut a red and a black wire 21 cm long, and
   twist them together, about a turn every 2 cm: in the case the pair takes
   about 20 cm, and a pair cut to length leaves no spare loop near the
   antenna leads. Solder red to the trigger's + pad (sometimes VOUT) and black
   to − (GND), and heat-shrink both joints. Crimp a 0.75-1.0 mm² ferrule on
   each free end and connect them to the regulator's input: red to IN+,
   black to IN−.
3. **Check the regulator.** Plug the charger back in. The regulator's output
   terminals should read 5.1–5.3 V, with + where its label says. Unplug.
4. **Make or check the pigtail.** To cut one from a cable:
   - cut it 32 cm from the plug's tip: in the case it takes about 30 cm, from
     the regulator's output through its four bridges to the plate under the
     Pi's USB-C port, up to the plug and into it, and leaves 1 to 2 cm of
     slack so the back plate can come away 5 cm before the plug is pulled. The
     plug stands 15 to 25 mm off the plate, depending on the standoffs under
     the FlyCatcher; if yours are measured, measure that too and adjust;
   - strip about 3 cm of the outer jacket;
   - red is 5 V, and black plus the bare braid are ground. If there are two
     reds, twist them together, and twist the blacks with the braid;
   - cut every other wire to about 2 cm, and tape over each one separately.

   Then, with the meter on continuity: black to the plug's metal shell should
   beep, red to the shell should not, and red to black should not. Stop if
   it's any other way: a reversed 5 V wire ruins a Pi.
5. **Regulator to pigtail.** Crimp a 0.75-1.0 mm² ferrule on the red wire,
   and one 1.0-1.5 mm² ferrule on the black wires and the braid together, with
   heat-shrink over the braid up to it. Red to the regulator's OUT+, black and
   braid to OUT−. Heat-shrink the cut end of the jacket, and snap the ferrite
   on about 5 cm from the plug. Tug-test each ferrule, and re-tighten the
   screws after a week.

## Switch the radar over

6. Shut the Pi down: `sudo poweroff`, or ask whoever looks after it.
7. Unplug the supply from the Pi (or the back plate's extension from the
   Pi's port), and plug the pigtail into the Pi's USB-C port.
8. Plug the charger into the trigger board: in the case, straight into its
   socket in the back plate. The Pi starts.
9. Check it:

   ```sh
   vcgencmd pmic_read_adc EXT5V_V        # about 5.1-5.2 V
   vcgencmd get_throttled                # throttled=0x0
   journalctl -k -b | grep -c "Undervoltage detected"   # 0
   lsusb                                 # the display and both radios
   ```

   With the panel lit and both radios on, `EXT5V_V` must still read 5.0 V or
   more (the first unit read 5.01-5.08 V, 5.05 V on average): any lower, and
   the pigtail's power wires are too thin or a terminal is loose. A switching
   regulator can add radio noise, so compare the receiver's noise floor
   (`"noise"` in `/run/readsb/stats.json`) with what it was before.

10. **Soak it for an hour** before it goes into the case or leaves the house.
    Keep the display at its normal brightness and the radar on its everyday
    screens. Then run the same checks again: `get_throttled` must still read
    `0x0`, and the kernel must have logged no "Undervoltage detected". The
    dips only show under the full load, so a radar that passes in the first
    minute can still fail here. After that, every health report carries the
    day's count of dips, and the fleet page flags a radar that has any.

A Pi 5 should start from the pigtail's two wires alone. If one doesn't, the
likely missing piece is the 56 kΩ pull-up that USB-A to USB-C cables carry
on their CC wire. A ready-made pigtail sold for powering devices avoids the
question.

## In the case

- **The trigger board's socket goes through the back plate** (since
  2026-10-29). The board's front edge bears on the plate's inner face, and its
  socket goes out through a window its own shape into a pocket in the outer
  face, so the charger's plug meets the socket and goes fully home. Until then
  the socket sat behind the plate, and a plug had to reach it through the
  plate; one whose moulding stopped short of it made a poor connection that
  cut out when the cable moved. `power_trigger_mount` holds the board, two
  crush ribs along its roof press the socket down so the board can't rock,
  and `power_trigger_stop` behind it presses it against the plate with no
  play. No extension is needed. Above the socket the plate says which
  charger it needs, `USB-C PD 12V 27W`, engraved in its outer face (plates
  printed since 2026-10-29); `back_plate_twotone.3mf` prints it in a second
  colour (since 2026-10-31). To fit them, with the plate outer face down:
  1. Press an M3 × 3 insert into each hole beside the window, from the inner
     face, with the outer face on a flat board, until it stops on the board.
  2. Solder the 12 V pair to the trigger board.
  3. Set the mount on the plate over the window, and screw it on with two
     M3 × 8 button-head screws from inside, into the inserts, a turn short of
     tight.
  4. Drop the board in from the back of the mount, socket first, the
     socket's side toward the two ribs in the mount. For the last 6 mm or so
     the socket goes under the ribs: push the board's back edge firmly, with
     a small flat screwdriver below the wires, until the socket goes into the
     window and the board's front edge rests on the plate. Tighten the two
     M3 screws.
  5. Slide the stop in behind the board until its ribs touch the board, ribs
     first and the ridge along one bottom edge toward the slot in the
     mount's wall. It only goes in that way round (since 2026-10-29: back to
     front it used to go in too, and its screws then held it 0.5 mm off the
     board).
  6. Drive two M2 × 8 screws through the mount's side walls into the stop,
     snug and no harder: they draw it the last 0.3 mm onto the board as they
     seat. Past that, each strips the thread it cut in the wall, and the
     slack comes back.

  The plate is what sets the board's place, so the board's front edge must be
  on it before the stop is locked; done on the bench, the socket would rest
  on the bench and the board would end up 2 mm too far back. Try it on
  `usbc_gauge` first, a ten-minute print of the plate round the window: the
  charger's plug must click fully home, and the click is the test, not how
  close the moulding looks. The two steps in the pocket's floor, a slot and
  a rectangle, are meant to be there: they let it print as a clean bridge,
  so slice with counterbore hole bridging off. If the plug won't click home:
  1. Trim any strand of plastic on the pocket's floor and round the window's
     edge.
  2. Check that the board's front edge is on the plate: from outside, the
     socket's face stands 0.4 mm proud of the pocket's floor. If it doesn't,
     undo the stop's screws and slide it out, push the board's back edge
     home, and fit a fresh stop. Not the same one: its ribs were squeezed
     with the board out of place and don't spring back, so the board would
     be loose, a plug could push it back instead of clicking home, and the
     test would prove nothing.
  3. Try another cable, one with a slimmer moulding round its plug.

  If it still won't, reprint the coupon with a bigger pocket: in the case's
  `.scad`, `usbc_recess_w` and `usbc_recess_h` set its size (14 × 10 mm;
  the width can go to 16.8). If the moulding goes into the pocket but stops
  on its floor, raise `usbc_seat_margin` from 0.4 to 0.6, which makes the
  pocket one layer deeper, as deep as it can go: the plate the board's front
  edge bears on is then 1.4 mm thick instead of 1.6, the least the design
  allows.

  The trial spends two of the inserts, which stay in the coupon, and the
  stop's crush ribs, which don't spring back: a stop is good for one
  fitting. Use the other two inserts and a fresh stop for the plate, never
  the coupon's, and move the mount across with the board still in it.
  Details and checks are in the
  [retro case's README](../enclosure/Retro%20Radar%20Enclosure/README.md#the-power-fix-the-charger-plugs-into-the-trigger-board).
- **The regulator goes in `power_regulator_tray`, at its one place across
  the bottom of the plate** (since 2026-10-29; until then it was stuck on
  with VHB tape wherever there was room), and its leads run along set routes,
  tied to bridges on the plate, away from the antenna leads. **Seen from
  behind the case**, the trigger board's socket is at the lower left, the
  Pi's USB-C port at the upper right, and the FlyCatcher's two antenna jacks
  on its right-hand edge, with the coax coming down to them from the cable
  hole at the top. So the power keeps to the lower half and the left:
  - the regulator lies across the bottom, its **output at the left-hand end**
    and its **input at the right-hand end**, seen from behind; the tray has
    `OUT` and `IN` engraved at its ends;
  - the twisted 12 V pair runs from the trigger board across the lower half
    of the plate: over the top of the low vent on two bridges, off the plate,
    past the tray's upper ear to a third, up the plate from the tray's
    right-hand end, and round that end on a fourth, onto the saddle there, to
    the input. It runs above the tray, never across the regulator;
  - the pigtail runs from the output up past the trigger board, up the left
    side of the Pi, between its USB ports and the speaker, and along the top
    of the Pi to its USB-C port, tied at four bridges, the last at the Pi's
    top left corner. From there it lies free, with the ferrite on it, between
    the Pi's top edge and a curb on the plate;
  - the coax runs from the cable hole to the right and down the right-hand
    side, tied at two bridges of its own, then free to the SMA jacks between a
    second curb and the right-hand speaker. Any length beyond the planned
    slack is folded back just below the second bridge and taken into its tie,
    never left as a loop, which would sag toward the 12 V pair.

  The two curbs are what hold the slack. The pigtail's run from its last
  bridge to its plug, and the coax's from its last bridge to the SMA plugs,
  each carry the slack that lets the plate be eased back 5 cm before the plug
  comes out; as the plate goes home that slack goes wherever it is pushed, and
  each curb keeps it on its own side, away from the other cable. Measured on
  the routes as the design draws them, every power lead, and all the room
  each free run's slack can take, is 20 mm or more from the coax and from the
  SMA plugs: the 12 V pair 24 mm from where an SMA plug could be, the pigtail
  25 mm, the coax 24 mm from the Pi's USB-C plug, and nothing crosses. The one
  exception is the Pi's own: its USB-C socket is 11 mm from the FlyCatcher's
  right-hand edge, so the pigtail's plug, its drop from the plug to the
  plate, past the jacks' height, and its first 13 mm along the plate, 3 to
  4 cm of cable in all, come within 20 mm of where an SMA plug could be, the
  plug's moulding 8 mm from it. Where the two jacks really are along the
  FlyCatcher's edge isn't measured yet, and the design allows for them
  anywhere they could be: with both below the edge's middle the plug would be
  about 30 mm from them, and the 12 V pair has only 4 mm to spare over its
  20 mm. So measure the jacks, and narrow `hat_sma_span` in the case's
  `.scad` to them.

  To fit the tray, with the plate outer face down (you're looking at its
  inner face, the mirror of the view from behind, so go by the trigger
  board's window and the vents, not by left and right):
  1. Press an M3 × 5 insert into each of the two bosses at the bottom of the
     plate, flush with the top of the boss.
  2. Lay the regulator, wired as in steps 2 to 5, in the tray with its output
     terminals at the end marked `OUT`, the end nearer the trigger board, and
     put a tie through each of the two grooves under the tray's floor, one tie
     in each, round the tray and the board: in the case the plate stands
     nearly upright, and nothing else keeps the board in. The board should
     drop in without forcing: the tray is drawn for the first unit's
     regulator, measured on 2026-10-30, a 63.5 × 27.25 mm board with 0.5 mm
     to spare all round. If yours has to be forced, measure its board.
  3. Set the tray over the bosses, its two caps over them (it fits one way
     only), and screw it down with two M3 × 8 button-head screws, snug.
  4. At each end, put a tie through the slot across the saddle, round the
     saddle and the leads on it, its head on top of the leads (on the tray's
     lower side it would hit the plate's lip), and pull it tight: the tie
     grips each lead just past its ferrule, and a pull on it lands on the
     tray, not on the screw. Each lead should run straight from its terminal
     onto the saddle. The saddles are set for leads that leave the terminals
     2 mm over the board, as the first unit's do, on a 1.6 mm board; if a
     lead has to bend more than a millimetre up or down to reach its saddle,
     measure your regulator's terminals and board.
  5. Tie the 12 V pair at its four bridges and the pigtail at its four, as
     the routes above say, each tie's head on top, except at the pigtail's
     third bridge, beside the Pi's USB ports: there, put the head on the
     speaker's side, on the plate, to stay under the plugs in those ports.
     Leave the pigtail free from its last bridge, at the Pi's top corner, on
     the Pi's side of its curb.

  When the plate goes on, hold it about 5 cm behind the case. Plug the coax
  in, its free run down the right-hand side between its curb and the
  speaker. Plug the pigtail into the Pi with its cable pointing at the
  plate, its free run along the top of the Pi, between the Pi and its curb,
  with the ferrite on it about 5 cm from the plug. With every plug in the Pi (the
  FlyCatcher's USB lead, the display's USB and HDMI leads), check that the
  pigtail and the tie at its third bridge pass under the USB plugs without
  touching them, and that no angled USB or HDMI cable points down onto the
  pigtail or the ferrite; keep the FlyCatcher's USB lead off the pigtail.
  Then ease the plate home: each run's slack arches off the plate, on its
  own side of its curb.
  To open the case: undo the eight screws, ease the plate back about 5 cm,
  unplug the pigtail and unscrew both SMA plugs, then lift the plate away.

  Details and checks are in the
  [retro case's README](../enclosure/Retro%20Radar%20Enclosure/README.md#the-regulators-place).
- **Never run the regulator's leads along an antenna cable.** On the first
  unit (2026-10-18) its lead had ended up wrapped round the external
  antenna's cable: 1090 MHz reception fell to a few messages a minute,
  against hundreds, and came back as soon as the two were apart. The routes
  above keep them 20 mm apart or more, but for the Pi's own plug: tie every
  lead at its bridges, and keep each free run on its own side of its curb.
- **Check the boards first.** The trigger board's size is measured, and so
  is the regulator's (2026-10-30): its board is 63.5 × 27.25 mm, its leads
  leave its terminals about 2 mm over the board, and nothing stands past the
  board's ends. Its board's thickness isn't measured (the design takes the
  usual 1.6 mm), so measure that before printing the tray: the saddles'
  height follows it. Each part is a short print, so print and fit them
  before the final assembly.
