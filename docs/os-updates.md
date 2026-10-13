# Operating-system updates

Every radar installs the operating system's security updates by itself, every
day: Debian's security fixes, the Raspberry Pi packages (OpenSSL among them)
and Tailscale (`deploy/52stratoscan-unattended-upgrades`).

A few packages are held back from that, because a bad one leaves a radar in
someone else's house unable to boot, off the network, or with a broken screen.
They are updated on a tested path instead (`deploy/os-update.py`, #73):

| Held | How it moves |
|---|---|
| Chromium, which draws the radar | The versions it replaces are kept as .debs. After the upgrade the kiosk restarts, and the new browser must paint a frame, or the kept versions go back. |
| The kernel, its boot files and the Wi-Fi firmware | One trial boot from its own folder on the boot partition (the Pi firmware's `tryboot`). It is kept only if the radar boots, paints and has a network. Otherwise the next boot is the old kernel, and the new one is removed. A power cycle always brings back the old kernel. |
| The EEPROM bootloader (`rpi-eeprom`) | Not moved. |

A version that fails on a radar is never tried again on that radar.

Patched libraries take effect only when the programs using them restart. At
04:30, a radar with programs still running replaced libraries restarts. It
does this only when the panel is asleep, the radar has been up a day, and it
hasn't restarted for this in six days.

Each radar's heartbeat reports:
- its last security run;
- the updates waiting;
- its Chromium and kernel versions;
- the outcome of the last held update.

The fleet page flags a radar in three cases:
- it hasn't patched in a week;
- security updates have been waiting a week;
- a held update was put back.

## Moving the held packages to new versions

The versions are named in `deploy/os-packages.json`. It ships with each
signed release, so it reaches radars through the release rings like
everything else. Ring 0 is where a new version is tried first.

1. On the ring 0 radar, list what apt offers:

   ```
   sudo /opt/stratoscan/os-update.py candidates
   ```

   This prints an `os-packages.json` with the newest version of each held
   package installed there. `_newer_than_installed` shows what would change.
2. Put the `packages` you want into `deploy/os-packages.json` and set
   `tested_on`. Leave out a package to keep it where it is.
3. Commit, and cut a release at ring 0 (`sh scripts/release.sh VERSION`).
4. On the ring 0 radar, apply the release, then run the update now rather
   than waiting for 17:00:

   ```
   sudo systemctl start stratoscan-os-update
   ```

   A kernel reboots the radar once onto its trial. Afterwards, check:
   - `os-update.py status`;
   - `journalctl -u stratoscan-os-update -u stratoscan-os-confirm`.
5. After a day on ring 0, widen the release ring by ring as usual
   (`sh scripts/release.sh rollout VERSION --ring N`).

The listed version must still be in the archive when a radar runs. Debian's
security archive keeps only the latest version, so widen promptly, and cut a
new release if a version has been replaced.

## The page's own libraries

The radar page bundles one third-party library, MapLibre GL JS, in `vendor/`
(#74). Releases carry `vendor/` like the rest of the page, so a new version
reaches radars through the rings. `vendor/VERSIONS.json` records each file's
npm package, version and hash. Before every release, `scripts/check-vendor.py`
asks GitHub's advisory database about those versions. An advisory with a fix
available stops the release unless `VERSIONS.json` accepts it, with a reason
and an end date.

To update a library: replace the file in `vendor/`, update its record (`npm
pack` gives the official file; `shasum -a 256` its hash), run
`python3 tests/test_vendor.py` and `python3 scripts/check-vendor.py`, and
release as usual.
