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
- **The radar's name** (from its home airport's city unless you choose one)
  stays on your home network. It's in the pairing code on the radar's
  screen, so a phone you pair shows it, and a paired phone reads it again
  when it's home. It's not on the public page and doesn't go to the relay.
- **Visitor counts for the public page** (when the radar has one): how many
  page views and visitors, by hour, device type and referring site, kept
  90 days on the radar for its owner. No cookies. A visitor is recognised
  for one day by a code made from their address with a key that is thrown
  away at midnight and never written down; only counts are saved. Nothing
  identifies a visitor, and the counts don't leave the radar unless it's in
  a fleet (roadmap 1.13).
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

**Alerts for aircraft approaching you** (off unless you turn on
"Approaching me" in the app's alert settings). So your radar can warn you of
an aircraft about to pass over where *you* are, the app tells your paired
radar where your phone is when it moves significantly (iOS's
significant-change service: roughly every 500 m or more, which needs the
"Always" location permission). The location is **end-to-end encrypted to
your radar**: the app seals it with your radar's own key, which it checks
against the identity it learned when you paired, so the StratoScan relay
that carries it only ever stores an unreadable blob, for at most 6 hours.
Your radar decrypts it, keeps it in memory to run the prediction, and
never writes it down, logs it or sends it on. The alert itself names the
aircraft and when it will pass, not how far or which way from you; but an
aircraft's track is public, so an alert does hint where you were, to
anyone who could read it on its way through the relay (it is kept only
briefly). Turning the option off withdraws your location from every radar.

**Aircraft around you, without a radar** (off unless you turn it on: "See
aircraft around you", or Settings › Without a radar). For someone with no
StratoScan radar, the app shows live traffic around the phone from adsb.lol,
centred on where you are. To ask for it, the app sends adsb.lol your
location **rounded to about 5 km** (0.05°), every 5 seconds while the app is
open. adsb.lol sees that rounded location and your IP address, like any web
request. Nothing goes to the StratoScan relay. The map is centred on your
exact position on the phone only. Pairing a radar switches this off.

**Sky view away from home** (off unless you turn it on). When the phone is
more than 3 nm from your radar, Sky view offers to show the aircraft around
you instead. If you say yes, the app asks adsb.lol, a public ADS-B network,
for the aircraft within 25 nm of your location **rounded to about 5 km**
(0.05° of latitude and longitude), every 5 seconds while Sky view is open.
adsb.lol sees that rounded location and your IP address, like any web
request. Nothing else is sent, and a button in Sky view turns it off again.
The camera picture in Sky view is never recorded or sent.

### Setting up a radar from the app

Scanning a new radar's first-run code lets the app set it up:
- It joins the radar's own setup network.
- It sends the radar **this phone's location** (you are standing next to it), time zone and region.
- It sends a name and your home WiFi password, over that network straight to the radar.
- It claims the radar with an admin password that it makes and keeps in this phone's Keychain.

Pairing needs no second code. The phone makes a one-time secret and gives the radar only a fingerprint of it, which the radar hands the relay once it's online. Nothing from setup is kept in the app beyond the paired radar and that password.

### Fleets

A radar can join a **fleet**, a group of radars looked after by one person (the relative who gave it to you, say), but only when its owner enters the fleet's invite code on the setup page. It can leave at any time from the same place.

While it's in one:
- health reports are on;
- its administrator sees the radar's health, its name and its public page's daily visit counts;
- the administrator never sees its location (reports carry none), its phones or its alerts.

Leaving puts health reports back the way they were. The relay keeps only fingerprints of invite codes and administrator links, never the secrets themselves.

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
