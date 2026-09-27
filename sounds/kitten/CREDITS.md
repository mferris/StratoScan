# Kitten theme sound credits

All four files are CC0 (public domain dedication) recordings from
[Freesound](https://freesound.org), downloaded via each sound's own hq
preview — the same audio Freesound's own embeddable player uses, not a
redistribution of the original upload. CC0 permits copying, modifying and
redistributing for any purpose, including commercial, without asking
permission or crediting the author; this file exists anyway, so the source of
each recording and what was done to it stays traceable.

| file | source | duration as recorded |
|---|---|---|
| `nearby.ogg` | [Cat Meow by Mafon2](https://freesound.org/people/Mafon2/sounds/436541/) | 0.57s |
| `emergency.ogg` | [catHisses1.wav by Zabuhailo](https://freesound.org/people/Zabuhailo/sounds/146963/) | 1.51s |
| `landing.ogg`, `takeoff.ogg` | [Cat trill 4 by MBPL](https://freesound.org/people/MBPL/sounds/668825/) | 0.86s |

## Processing

Each file was re-encoded to mono Opus-in-Ogg at 32kbps, 48kHz — small enough
that all four together are 20KB, and Opus is native to Chromium, the kiosk's
only target. Beyond format conversion:

- **`nearby.ogg`** — gain +1.8dB. The source was already close to full range;
  this was matching level, not repair.
- **`emergency.ogg`** — trimmed to the actual hiss (the source carried ~0.2s
  of lead-in silence and ~0.34s of trailing silence around a 0.98s hiss), then
  gain +14.5dB. The raw recording peaked at -16.7dBFS, quiet enough that this
  sound would have read as the least urgent of the three rather than the
  intended most.
- **`landing.ogg`** / **`takeoff.ogg`** — both derived from the same trill,
  gain -6.6dB (deliberately the quietest mastering of the three, since this
  sound fires on every landing and takeoff — the most frequent of the events
  by far), then pitch-shifted via `asetrate` + `atempo` to preserve duration:
  `landing.ogg` down by a factor of 0.87, `takeoff.ogg` up by 1.15. This
  mirrors the down-for-landing/up-for-takeoff convention the classic theme's
  synthesized tones already use (720Hz vs 1040Hz), so the two stay
  distinguishable by ear without looking at the screen.

All fades and gain changes were applied with `ffmpeg`; the exact filter
chains are in the session history that produced this commit, not reproduced
here since they are a means to the file, not part of its identity.

## Why not the exact source files

Freesound's hq preview is itself a re-encode (128kbps MP3) of whatever the
uploader submitted, not the original bit-for-bit upload — fetching the
original master requires an authenticated API call, and CC0 does not require
using the highest-fidelity copy available, only that the recording itself is
what's claimed. For four sub-second sound effects played through a small
speaker, the preview's fidelity is not the limiting factor in how they sound.
