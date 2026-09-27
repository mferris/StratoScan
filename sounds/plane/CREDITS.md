# Plane theme sound credits

All four files derive from one CC0 (public domain dedication) recording on
[Freesound](https://freesound.org), downloaded via its own hq preview:

- **Source**: [Airplane, Seatbelt Sign Beep by Kinoton](https://freesound.org/people/Kinoton/sounds/670297/) — "a clean recreation" of the classic Airbus/Boeing seatbelt-sign chime, described by its creator as "a sinus tone with a short attack and long release time, notes D and B." 2.93s, mono, 48kHz.

Everything in this theme is a trim, gain, or pitch shift of that one file —
CC0 permits all three without asking. Structure of the source, found with
`ffmpeg`'s `silencedetect` before cutting anything: note 1 (the "ding") runs
0.29–1.07s, a gap, then note 2 (the "dong") 1.33–2.09s, then a long decay
tail out to 2.93s.

| file | what it is | source range | processing |
|---|---|---|---|
| `nearby.ogg` | just the "ding" (note 1), cut short | 0.28–0.70s | +6dB, fade out at 0.32s |
| `landing.ogg` | full two-note chime, pitched down | 0.28–2.10s | −2dB, `asetrate`×0.87 + `atempo`÷0.87 |
| `takeoff.ogg` | full two-note chime, pitched up | 0.28–2.10s | −2dB, `asetrate`×1.15 + `atempo`÷1.15 |
| `emergency.ogg` | note 1's attack, repeated 3× | 0.28–0.95s ×3 | +3dB, concatenated back-to-back |

Down-for-landing/up-for-takeoff mirrors the convention the classic theme's
synthesized tones and the kitten theme's trill already use, so all three
sound themes agree on which direction means which event.

## Why `emergency.ogg` is three repeats of ONE note, not the two-note chime

The first attempt repeated the full "ding-dong" phrase three times and it was
wrong on two counts. It ran 4.7 seconds — by far the longest sound in the
app for the one event that is supposed to demand the fastest reaction, the
same mistake avoided in `sounds/kitten/CREDITS.md`'s emergency sound for the
same reason. And a repeated two-note melody reads as pleasant and
informational (which is exactly why it is the seatbelt-sign chime), not
urgent — real aircraft caution systems use a single repeated tone for
elevated alerts precisely because repetition of ONE note is what reads as an
alarm, not a phrase. Three quick identical dings, ~2 seconds total, is both
shorter and more alarm-shaped than the two-note version was.

## Why not a real cockpit warning sound

Freesound has genuine CC0 "cockpit warning" recordings, including a
synthesized "terrain, pull up"-style voice alert. Not used: it borrows a
real, currently-in-use aviation safety-critical signal for a home device, and
someone unfamiliar with it hearing it unexpectedly could reasonably think
something is actually wrong, rather than "a plane is squawking an emergency
code on the map." Everything in this theme is either an authentic-but-benign
airline cabin sound (the seatbelt chime) or a derivative of it.
