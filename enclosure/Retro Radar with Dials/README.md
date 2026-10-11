# Retro Radar with Dials

The retro radar case with a control arc on its upper right. The arc carries
three controls:

| Control | What it does |
|---|---|
| **STATUS** jewel lamp | Green while the radar hears aircraft. Amber when the receiver has gone deaf. Red when the power supply is dipping. |
| **SCREEN** button | A press turns the screen on or off. Holding it for 2 s switches between "sleeps when idle" and "always on". |
| **RANGE** dial | Turning it zooms the radar out or in; pinch still works. Pushing it returns to the home view. |

![The case in its stand](images/stand-left.png)

Everything except the arc is the retro case, unchanged:
`retro-dials.scad` includes `../Retro Radar Enclosure/retro-enclosure.scad`.
The shell gains three holes through its wall: two screws and a wire hole.
Print the front trim, retainer, back plate, antenna mount and stand from the
retro folder.

| Front | The arc | Exploded |
|---|---|---|
| ![Front](images/front.png) | ![The arc close up](images/arc-closeup.png) | ![Exploded](images/exploded.png) |

## Print

| File | What | Notes |
|---|---|---|
| `shell_dials.stl` | The retro shell with the arc's three holes | Replaces `shell.stl`. Print it the same way, in ASA. |
| `control_arc_twotone.3mf` | The arc, with its lettering and two rivet dots in a second colour | Face down. The lettering is the first 0.6 mm, so there is one filament change per layer for three layers. |
| `control_arc.stl`, `control_arc_text.stl` | The same arc and lettering as separate meshes | For a printer without two colours: print `control_arc.stl` and paint the lettering. |
| `control_arc_cover.stl` | The flat cover that closes the arc's back | Flat side down. |
| `knob.stl` | The RANGE knob, for a 6 mm D shaft | Skirt down. Print it in ASA or PETG. |
| `jewel_lens.stl` | The STATUS lamp's faceted lens | Clear or translucent PETG, shank down. A drop of glue holds it. |

## Buy

| Part | Qty | Notes |
|---|---|---|
| EC11 rotary encoder with push switch, 20 mm D shaft (6 mm), M7 bushing | 1 | Snap off its small locating tab, or the face will not let it sit flat. |
| 12 mm momentary push button, normally open, metal, flat cap | 1 | Not a latching switch: alerts and the idle timer also turn the screen on and off, so a switch that stays down would often point the wrong way. |
| 5 mm RGB LED, common cathode, diffused | 1 | Diffused looks better behind the lens. |
| 220 Ω resistors | 3 | One in each colour leg of the LED. |
| M3 x 10 screws | 2 | From inside the case, into the arc's pads. |
| M3 x 5 heat-set inserts | 2 | The same inserts as the rest of the case. |
| M2.5 x 8 countersunk self-tapping screws | 2 | They hold the cover. |
| Thin hook-up wire (26–28 AWG), or an 8-way ribbon, about 30 cm | 1 | Eight wires go through the 7 mm hole. |
| Female jumper housings for the Pi's header, and heat-shrink | — | To plug onto the GPIO pins. |

## Wire

Every control switches to ground, using the Pi's internal pull-ups, so no
other parts are needed apart from the LED's resistors. Use the Pi 5's 40-pin
header; the numbers are physical pin numbers.

| From | To | Pin |
|---|---|---|
| Encoder A | GPIO 17 | 11 |
| Encoder B | GPIO 27 | 13 |
| Encoder common (C) | Ground | 9 |
| Encoder push switch | GPIO 22 | 15 |
| Encoder push switch, other leg | Ground | 14 |
| SCREEN button | GPIO 23 | 16 |
| SCREEN button, other leg | Ground | 20 |
| LED red, through 220 Ω | GPIO 12 | 32 |
| LED green, through 220 Ω | GPIO 13 | 33 |
| LED blue, through 220 Ω | GPIO 18 | 12 |
| LED common cathode | Ground | 34 |

These pins leave I2C (GPIO 2 and 3) free for the light sensor (roadmap 5.5),
and the UART (GPIO 14 and 15) free for the presence sensor (5.2).

**The FlyCatcher sits over the header.** If its board covers the pins you need,
fit a 2 × 20 stacking header under it, or take the pins out from beside it
with a short ribbon to a breakout.

## Assemble

1. Press the two M3 inserts into the arc's pads from the drum side.
2. Fit the encoder, the button and the lens through the arc's face. The
   encoder's nut goes on from the front, under the knob.
3. Solder the wires (the LED's resistors inline, under heat-shrink), pass them
   through the arc's neck and the case wall, and screw the cover on.
4. Hold the arc against the case and drive the two M3 screws from inside.
5. Plug the wires onto the header, push the knob onto the encoder shaft, and
   turn the controls on: `sudo sh deploy/install-setup-server.sh` with
   `CONTROLS=1`, or write `{"enabled": true}` to `/etc/stratoscan/controls.json`
   and restart `stratoscan-controls`.

## Checks

`sh run-checks.sh` runs 19 fit checks; each measures volume, as the retro
case's checks do. They check that:

- the arc clears the shell, front trim, stand, side vents and speaker grille;
- the screw heads and wires clear the posts and shelf inside the case;
- the button, encoder and lamp fit behind the face;
- the pads really land on the drum, the holes are really open, and the
  lettering is present.

`sh render-views.sh` remakes the pictures in `images/`.
`python3 make-arc-3mf.py` remakes the two-colour file, after exporting
`control_arc.stl` and `control_arc_text.stl` as binary STL.

## Design references

The arc follows a general practice of radar consoles from the 1940s to the 1970s:

- controls set beside the round scope;
- a small indicator lamp;
- rivets;
- plain engraved labels.

Each of these is functional and generic, so the design copies no particular
product's shape, knob, panel layout, badge, name or typeface. One arc is used
rather than a pod on each shoulder, because two round pods on the upper
shoulders of a round drum would make a well-known three-circle silhouette. The
photographs below were consulted and are linked here, not copied:

- [Decca radar display unit](https://collection.sciencemuseumgroup.org.uk/objects/co55824/decca-display-unit), Science Museum Group
- [Philips SGR radar console](https://commons.wikimedia.org/wiki/File:Philips_SGR_radar_1.JPG), Wikimedia Commons, public domain
- [WSR-57 weather radar console](https://commons.wikimedia.org/wiki/File:WSR-57_Weather_Radar_Console_-_51167475916.jpg), Wikimedia Commons, CC BY 2.0
- [US Navy SG radar console, 1945](https://commons.wikimedia.org/wiki/File:SG_Radar_Console_1945.jpg), Wikimedia Commons, public domain
- [RCAF radar display unit](https://collection.ingenium.ca/en/id/1968.0935.001), Ingenium
