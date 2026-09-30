#!/usr/bin/env python3
"""
What an aircraft is: the one copy of the tables and rules that label it.

Shared by core-feed.py (the labelled feed every screen reads, roadmap 1.8)
and events.py (alerts), so a label can't differ between the radar, the
phone and an alert. Moved here from events.py, where they were copied from
index.html; tests/test_labels.py keeps them identical to the page's own
copies until the page reads the feed instead (roadmap 1.9).

  operator(hex, flight)  who is flying it: military / airline / private /
                         unknown ("Identifying..."), with a label and a colour
  TypeDb                 registration and type from tar1090's aircraft database
  NotableDb              plane-alert-db's notable list (notable-db.py keeps it)
"""
import collections
import glob
import gzip
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TAR1090_DB_GLOB = os.environ.get("STRATOSCAN_TAR1090_DB", "/usr/local/share/tar1090/html/db-*")
NOTABLE_JSON = os.environ.get("STRATOSCAN_NOTABLE_JSON", "/var/www/html/data/notable.json")
AIRLINES_JSON = os.environ.get("STRATOSCAN_AIRLINES_JSON", os.path.join(HERE, "airlines.json"))

# ---- tables: tests/test_labels.py keeps them identical to index.html's ----

MILITARY_HEX_RANGES = [
    (0x33ff00, 0x33ffff, "Italian military"),
    (0x350000, 0x37ffff, "Spanish military"),
    (0x3aa000, 0x3affff, "French military"),
    (0x3b7000, 0x3bffff, "French military"),
    (0x3ea000, 0x3ebfff, "German military"),
    (0x3f4000, 0x3fbfff, "German military"),
    (0x400000, 0x40003f, "UK military"),
    (0x43c000, 0x43cfff, "UK military"),
    (0x480000, 0x480fff, "Dutch military"),
    (0x4b7000, 0x4b7fff, "Swiss military"),
    (0xadf7c8, 0xafffff, "US military"),
    (0xc20000, 0xc3ffff, "Canadian military"),
    (0xe40000, 0xe41fff, "Brazilian military"),
]

NOTABLE_TYPES = {
    "A388": "Airbus A380", "A124": "Antonov An-124", "A225": "Antonov An-225",
    "B741": "Boeing 747", "B742": "Boeing 747", "B743": "Boeing 747",
    "B744": "Boeing 747", "B748": "Boeing 747-8", "B74S": "Boeing 747SP",
    "C17": "C-17 Globemaster", "C5M": "C-5 Galaxy", "C5": "C-5 Galaxy",
    "B52": "B-52 Stratofortress", "B1": "B-1 Lancer", "B2": "B-2 Spirit",
    "K35R": "KC-135 Stratotanker", "KC46": "KC-46 Pegasus", "KC10": "KC-10 Extender",
    "E3TF": "E-3 Sentry (AWACS)", "E3CF": "E-3 Sentry (AWACS)", "P8": "P-8 Poseidon",
    "V22": "V-22 Osprey", "U2": "U-2 Dragon Lady", "R135": "RC-135",
    "VC25": "VC-25 (Air Force One)", "C32": "C-32 (Air Force Two)",
    "DC3": "Douglas DC-3", "C47": "Douglas C-47", "B17": "B-17 Flying Fortress",
    "P51": "P-51 Mustang", "B29": "B-29 Superfortress", "SPIT": "Supermarine Spitfire",
}

# plane-alert-db's category names are in-jokes, and a few pass judgement on
# people; an event only ever carries the neutral description.
NOTABLE_LABELS = {
    "Aerial Firefighter": "Firefighting aircraft", "Aerobatic Teams": "Aerobatic display team",
    "Army Air Corps": "UK Army Air Corps", "As Seen on TV": "Company aircraft",
    "Big Hello": "Heavy helicopter", "Bizjets": "Private jet", "CAP": "Civil Air Patrol",
    "Climate Crisis": "Large business jet", "Coastguard": "Coast guard or border patrol",
    "Da Comrade": "Russian- or Soviet-built aircraft", "Dictator Alert": "VIP aircraft",
    "Distinctive": "One-of-a-kind aircraft", "Dogs with Jobs": "Special-mission aircraft",
    "Don't you know who I am?": "Aircraft of a well-known person", "Flying Doctors": "Air ambulance",
    "Football": "Sports team aircraft", "GAF": "German Air Force", "Gas Bags": "Balloon or airship",
    "Governments": "Government aircraft", "Gunship": "Attack aircraft", "Head of State": "Head of state aircraft",
    "Hired Gun": "Military contractor", "Historic": "Historic aircraft",
    "Jesus he Knows me": "Religious organisation aircraft", "Joe Cool": "Notable aircraft",
    "Jump Johnny Jump": "de Havilland Chipmunk", "Nuclear": "Nuclear emergency support",
    "Oligarch": "VIP private jet", "Other Air Forces": "Air force", "Other Navies": "Navy",
    "Oxcart": "Surveillance aircraft", "Perfectly Serviceable Aircraft": "Skydiving aircraft",
    "Police Forces": "Police aircraft", "Ptolemy would be proud": "Aerial survey aircraft",
    "Quango": "International organisation (NATO, UN…)", "Radiohead": "Presidential or VIP transport",
    "RAF": "Royal Air Force", "Royal Aircraft": "Royal Family aircraft", "Royal Navy Fleet Air Arm": "Royal Navy",
    "Special Forces": "Special operations aircraft", "Toy Soldiers": "Army aircraft", "UAV": "Drone (UAV)",
    "UK National Police Air Service": "Police aircraft (UK NPAS)", "Ukraine": "Ukrainian aircraft",
    "United States Marine Corps": "US Marine Corps", "United States Navy": "US Navy", "USAF": "US Air Force",
    "Vanity Plate": "Distinctive registration", "Watch Me Fly": "Flight school aircraft",
    "You came here in that thing?": "Microlight or very small aircraft", "Zoomies": "Fast jet",
}

# ---- what an aircraft is --------------------------------------------------------

def military_operator(hex_):
    try:
        v = int(hex_, 16)
    except (TypeError, ValueError):
        return None
    for lo, hi, who in MILITARY_HEX_RANGES:
        if lo <= v <= hi:
            return who
    return None


def humanize_type(s):
    return " ".join(w[0] + w[1:].lower() if w.isalpha() and w.isupper() else w for w in s.split(" "))


class TypeDb:
    """Registration and type from tar1090's on-disk aircraft database.

    The same prefix-trie of gzipped JSON shards the kiosk reads over HTTP
    (index.html lookupType). Missing or unreadable: every lookup is empty and
    events just carry less detail.
    """
    SHARD_CACHE = 8
    HEX_CACHE = 5000

    def __init__(self, pattern=TAR1090_DB_GLOB):
        dirs = sorted(glob.glob(pattern), key=lambda d: os.path.getmtime(d))
        self.dir = dirs[-1] if dirs else None
        self.shards = collections.OrderedDict()
        self.hexes = collections.OrderedDict()
        self.types = {}
        if self.dir:
            raw = self._load("icao_aircraft_types2") or {}
            for code, e in raw.items():
                if isinstance(e, list) and e:
                    self.types[code.upper()] = (e[0], e[1] if len(e) > 1 else None)

    def _load(self, name):
        try:
            with open(os.path.join(self.dir, name + ".js"), "rb") as f:
                raw = f.read()
            return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        except (OSError, ValueError, EOFError):
            return None

    def _shard(self, key):
        if key in self.shards:
            self.shards.move_to_end(key)
            return self.shards[key]
        data = self._load(key)
        self.shards[key] = data
        if len(self.shards) > self.SHARD_CACHE:
            self.shards.popitem(last=False)
        return data

    def lookup(self, hex_):
        """{"reg", "type", "type_code", "desc"}; values None when unknown."""
        hex_ = (hex_ or "").upper()
        if hex_ in self.hexes:
            return self.hexes[hex_]
        entry = None
        level = 1
        while self.dir and hex_ and level <= len(hex_):
            bkey = hex_[:level]
            data = self._shard(bkey)
            if not isinstance(data, dict):
                break
            dkey = hex_[level:]
            if dkey in data:
                entry = data[dkey]
                break
            if dkey and bkey + dkey[0] in (data.get("children") or []):
                level += 1
                continue
            break
        out = {"reg": None, "type": None, "type_code": None, "desc": None}
        if isinstance(entry, list):
            reg = entry[0] if len(entry) > 0 else None
            code = (entry[1] or "").upper() if len(entry) > 1 and entry[1] else None
            long_ = entry[3] if len(entry) > 3 else None
            meta = self.types.get(code) if code else None
            out = {"reg": reg or None, "type_code": code,
                   "type": humanize_type(long_) if long_ else (humanize_type(meta[0]) if meta and meta[0] else None),
                   "desc": meta[1] if meta else None}
        self.hexes[hex_] = out
        if len(self.hexes) > self.HEX_CACHE:
            self.hexes.popitem(last=False)
        return out


class NotableDb:
    """hex -> [category, kind, operator, type], reloaded when notable-db.py refreshes it."""

    def __init__(self, path=NOTABLE_JSON):
        self.path, self.mtime, self.ac = path, None, {}

    def get(self, hex_):
        try:
            m = os.path.getmtime(self.path)
        except OSError:
            return None
        if m != self.mtime:
            try:
                with open(self.path) as f:
                    self.ac = json.load(f).get("ac") or {}
            except (OSError, ValueError):
                self.ac = {}
            self.mtime = m
        return self.ac.get(hex_)


# ---- who is flying it ------------------------------------------------------------
# The same rules, in the same order, as the page's airlineFor() (index.html):
#   1. an address in a military block is military, whatever the callsign says
#      -- the block can't be changed by typing a different callsign;
#   2. a callsign that is three letters then a digit, for a known airline, is
#      that airline;
#   3. any other real callsign is a private aircraft;
#   4. no real callsign yet: unknown, shown as "Identifying...".
# A "real" callsign has at least one letter: transponders configured with a
# placeholder send "00000000", which is not an identity.

PRIVATE_LABEL, PRIVATE_COLOR = "Private Aircraft", "#44494e"
ACQUIRING_LABEL, ACQUIRING_COLOR = "Identifying\u2026", "#33393e"
MILITARY_COLOR = "#4b5a3c"
_AIRLINE_CS = re.compile(r"^([A-Z]{3})\d")


def _load_airlines(path=AIRLINES_JSON):
    try:
        with open(path) as f:
            return json.load(f).get("airlines") or {}
    except (OSError, ValueError):
        return {}


AIRLINES = _load_airlines()


def real_callsign(flight):
    cs = (flight or "").strip()
    return cs if re.search(r"[A-Za-z]", cs) else None


def operator(hex_, flight):
    """{"kind": military|airline|private|unknown, "label", "icao", "color"}."""
    mil = military_operator(hex_)
    if mil:
        return {"kind": "military", "label": mil, "icao": None, "color": MILITARY_COLOR}
    cs = real_callsign(flight)
    if not cs:
        return {"kind": "unknown", "label": ACQUIRING_LABEL, "icao": None, "color": ACQUIRING_COLOR}
    m = _AIRLINE_CS.match(cs)
    airline = AIRLINES.get(m.group(1)) if m else None
    if airline:
        return {"kind": "airline", "label": airline["name"], "icao": m.group(1), "color": airline["color"]}
    return {"kind": "private", "label": PRIVATE_LABEL, "icao": None, "color": PRIVATE_COLOR}
