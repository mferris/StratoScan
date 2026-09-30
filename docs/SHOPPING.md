# Shopping list

Everything Radome still needs bought, what is on order, and what is already
in hand. Claude keeps this current: an item is added when a roadmap item or
issue first needs a part, moved to **Ordered** when you say you've ordered
it, and to **Have** when it arrives or is fitted.

*Last updated 2026-09-30.*

## To buy

| Item | For | Where | Approx. | Notes |
|---|---|---|---|---|
| Adafruit VEML7700 lux sensor (#4162) | [5.5 light sensor](https://github.com/mferris/Radome/issues/27) | [Adafruit](https://www.adafruit.com/product/4162) | $5 | I²C, STEMMA QT. Fits the case window planned in #27 |
| STEMMA QT to female-socket cable, 150 mm (#4397) | 5.5 light sensor | [Adafruit](https://www.adafruit.com/product/4397) | $1 | Plugs onto the Pi's GPIO pins 1, 3, 5, 9 with no soldering |
| Rotary encoder | [5.1 rotating bezel](https://github.com/mferris/Radome/issues/22) | — | ~$5 | Exact part chosen when the bezel is designed |
| Presence sensor: LD2410 mmWave, or a PIR | [5.2 presence wake](https://github.com/mferris/Radome/issues/23) | — | ~$10 | Exact part chosen when 5.2 starts |
| 978 MHz SDR (US units) | [5.3 UAT receiver](https://github.com/mferris/Radome/issues/24) | — | ~$25–40 | A UAT-tuned stick, for example FlightAware's 978 MHz Pro Stick Plus. The antenna is already covered: the NooElec bundle below includes a 978 MHz whip |
| High-endurance microSD card, 128 GB | Each unit you give away (1.2) | — | ~$20 each | Replaces NVMe, which the 1.6 wear measurement showed isn't needed |
| Apple Watch, if you don't have one | [Phase 3](https://github.com/mferris/Radome/milestone/3) testing | — | — | Series 5 / SE or later for the compass (3.3, 3.4) |
| Filament | [5.4 stand ridges](https://github.com/mferris/Radome/issues/26) reprint | — | — | Reprint the retro stand once the ridges are redesigned |

## Not needed

| Item | Why |
|---|---|
| NVMe HAT / CM5 (1.2) | SD writes measured at 2.25 GB/day, fine for a high-endurance card over ten years |
