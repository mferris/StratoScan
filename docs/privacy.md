# StratoScan privacy policy

*Last updated 2026-09-29.*

StratoScan is an open-source radar for the aircraft flying over your home,
built around a receiver you own. This page covers the StratoScan radar, the
StratoScan iPhone app, and the small StratoScan relay service that connects them.
The code for all three is public at
[github.com/mferris/StratoScan](https://github.com/mferris/StratoScan).

## The short version

- Your radar's exact location never leaves it.
- The app doesn't ask for your location, doesn't track you, and shows no ads.
- The relay keeps the minimum it needs to deliver alerts, and deletes it
  when it's no longer needed.

## The radar

The radar receives aircraft broadcasts with its own antenna and keeps that
data on the device. It sends data off the device only for features you
turn on:

- **Phone alerts** (on when you pair a phone): short messages about notable
  aircraft, emergencies, helicopters and low aircraft nearby. Each message
  names the aircraft and gives its distance rounded to half a nautical
  mile with a compass direction. It never includes a position.
- **Health reports** (off unless you turn them on): software version,
  receiver health, storage wear, temperature. No location, no network
  details, nothing about what flew over.
- **Network comparison** (off unless you turn it on): sends an approximate
  location to adsb.lol, to compare what your antenna hears with theirs.
- **Map tiles, routes, photos and weather** are fetched from the public
  services credited on the radar and in the app. Like any web request,
  they see an IP address and the area or aircraft being looked up.

## The iPhone app

The app reads your radar directly on your home network. To deliver alerts
it gives the StratoScan relay:

- a random key it generates (so your radars can recognise your phone);
- Apple's push-notification address for your phone;
- the generic device name iOS provides (for example "iPhone").

It collects nothing else: no location, contacts, usage analytics or
advertising identifiers.

## The relay

The relay is a small service run by the StratoScan maintainer on Cloudflare.

| What | Kept for |
|---|---|
| Which phones are paired with which radar | Until either side unpairs |
| A phone's push address and alert choices | Until it is no longer paired with any radar |
| Alerts waiting to be delivered | At most 48 hours (500 per radar) |
| Health reports (only if turned on) | About 30 days |
| A one-time pairing code's fingerprint (never the code itself) | Until used, or 10 minutes |

A factory reset of a radar unpairs its phones and gives it a new identity.
Nothing on the relay is sold or shared, or used for advertising or
tracking.

## Contact

Questions or requests:
[github.com/mferris/StratoScan/issues](https://github.com/mferris/StratoScan/issues).
