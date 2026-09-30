# StratoScan privacy policy

*Last updated 2026-09-29.*

StratoScan is an open-source radar for the aircraft flying over your home,
built around a receiver you own. This page covers the StratoScan radar, the
StratoScan iPhone app, and the small StratoScan relay service that connects them.
The code for all three is public at
[github.com/mferris/StratoScan](https://github.com/mferris/StratoScan).

## The short version

- Your radar's exact location never leaves it.
- The app uses your phone's location only if you ask it to show you on the
  radar, and only on the phone. One exception, off unless you turn it on:
  Sky view away from home asks adsb.lol for the aircraft around you, with
  your location rounded to about 5 km. It doesn't track you and shows no ads.
- The relay keeps the minimum it needs to deliver alerts, and deletes it
  when it's no longer needed.

## The radar

The radar receives aircraft broadcasts with its own antenna and keeps that
data on the device. It sends data off the device only for features you
turn on:

- **Phone alerts** (on when you pair a phone): short messages about notable
  aircraft, emergencies, helicopters and low aircraft nearby. Each message
  names the aircraft and gives its distance rounded to half a nautical
  mile with a compass direction, and the direction the aircraft is
  travelling (which it broadcasts itself). It never includes a position.
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

It collects nothing else: no location (but see Sky view below), contacts,
usage analytics or advertising identifiers.

**Your location.** If you tap the location button to see yourself on the
radar, iOS asks whether the app may use your location while it's open. It
is used on your phone, to place a "YOU" marker, centre the view and aim the
compass and Sky view. It is never sent to your radar or the relay. You can
turn it off at any time in the iPhone's Settings.

**Sky view away from home** (off unless you turn it on). When the phone is
more than 3 nm from your radar, Sky view offers to show the aircraft around
you instead. If you say yes, the app asks adsb.lol, a public ADS-B network,
for the aircraft within 25 nm of your location **rounded to about 5 km**
(0.05° of latitude and longitude), every 5 seconds while Sky view is open.
adsb.lol sees that rounded location and your IP address, like any web
request. Nothing else is sent, and a button in Sky view turns it off again.
The camera picture in Sky view is never recorded or sent.

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
