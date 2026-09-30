# Source code for the StratoScan factory image

The factory image is Raspberry Pi OS with StratoScan installed on top. It
contains software under the GNU GPL and other copyleft licences. As its
distributor, the StratoScan project offers the corresponding source as
follows.

**StratoScan itself** (MIT): https://github.com/mferris/StratoScan, at the
project commit named in `MANIFEST.txt`.

**Attached to this release**, as built into the image:
- `src/readsb-source.tar.gz`: readsb (GPL-3.0-or-later), at the tag and commit
  in `MANIFEST.txt`.
- `src/tar1090-source.tar.gz`: tar1090 (GPL-2.0-or-later), at the commit in
  `MANIFEST.txt`.
- `src/piper_tts-*.tar.gz`: Piper TTS (GPL-3.0-or-later), the source release
  of the version in `MANIFEST.txt`. Upstream is
  https://github.com/OHF-voice/piper1-gpl.

**Raspberry Pi OS and Debian packages:** every package in the image, with its
exact version, is listed in `MANIFEST.txt`. Their source packages are
published by their distributors at https://archive.raspberrypi.com/debian/
and https://deb.debian.org/debian/ (older versions at
https://snapshot.debian.org/). The base image is Raspberry Pi's own, named in
`MANIFEST.txt`.

**Written offer.** For at least three years from the date of this release, the
StratoScan project will provide, on request, a complete machine-readable copy
of the corresponding source for any GPL- or LGPL-licensed software in this
image, for no more than the cost of physically performing the distribution.
Ask through https://github.com/mferris/StratoScan/issues.
