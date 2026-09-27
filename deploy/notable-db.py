#!/usr/bin/env python3
"""
Notable-aircraft list for this unit, from plane-alert-db.

plane-alert-db (github.com/sdr-enthusiasts/plane-alert-db) is a community
list of ~17,000 specific aircraft worth knowing about -- air ambulances,
police, military, historic, one-offs -- by ICAO hex. It is licensed ODbL 1.0
(database) and DbCL 1.0 (contents), so it is fetched by each unit rather
than copied into this repository, and the page credits it wherever it shows
an entry.

The 2.4 MB CSV is converted to a compact JSON the page loads once:
/var/www/html/data/notable.json. Refreshed weekly by net-watchdog when
online; a failed fetch leaves the previous file in place and backs off.

Privacy, decided here rather than only in the page, so the file served
publicly through the Funnel never carries it:
  - "PIA" entries are skipped entirely: those owners enrolled in the FAA's
    Privacy ICAO Address programme precisely so they are not singled out.
  - Operator names are kept only for military, government and police
    aircraft, and never for the categories about private individuals
    (famous people, "Oligarch", "Dictator Alert", corporate and vanity).

  notable-db.py ensure   refresh if missing or older than a week
  notable-db.py build    refresh now
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request

SOURCE_URL = "https://raw.githubusercontent.com/sdr-enthusiasts/plane-alert-db/main/plane-alert-db.csv"
WEB_ROOT = os.environ.get("FLIGHTRADAR_WEB_ROOT", "/var/www/html")
OUT = os.path.join(WEB_ROOT, "data", "notable.json")
STATE_DIR = os.environ.get("FLIGHTRADAR_NOTABLE_STATE", "/var/lib/flightradar-notable")
FAILED_STAMP = os.path.join(STATE_DIR, "last-failure")
REFRESH_EVERY_S = 7 * 86400
RETRY_AFTER_FAILURE_S = 6 * 3600
MAX_BYTES = 20_000_000
USER_AGENT = "FlightRadar/1.0 (+https://github.com/mferris/FlightRadar; weekly notable-aircraft refresh)"

SKIP_CATEGORIES = {"PIA"}
# Categories about private people or companies: never keep a name.
NO_OPERATOR_CATEGORIES = {
    "As Seen on TV", "Bizjets", "Climate Crisis", "Dictator Alert",
    "Don't you know who I am?", "Football", "Jesus he Knows me", "Oligarch",
    "Vanity Plate",
}
OPERATOR_KINDS = {"Mil", "Gov", "Pol"}
HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$")


def log(msg):
    print(f"notable-db: {msg}", flush=True)


def convert(text):
    """CSV text -> the compact document the page loads."""
    reader = csv.DictReader(io.StringIO(text))
    out = {}
    for row in reader:
        hexcode = (row.get("$ICAO") or "").strip()
        cat = (row.get("Category") or "").strip()
        if not HEX_RE.match(hexcode) or not cat or cat in SKIP_CATEGORIES:
            continue
        kind = (row.get("#CMPG") or "").strip()
        operator = (row.get("$Operator") or "").strip()
        if kind not in OPERATOR_KINDS or cat in NO_OPERATOR_CATEGORIES:
            operator = ""
        out[hexcode.lower()] = [cat[:40], kind[:3], operator[:60], (row.get("$Type") or "").strip()[:60]]
    return {
        "v": 1,
        "source": "plane-alert-db",
        "license": "ODbL-1.0",
        "url": "https://github.com/sdr-enthusiasts/plane-alert-db",
        "built": int(time.time()),
        "fields": ["category", "kind", "operator", "type"],
        "ac": out,
    }


def build():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("source larger than expected")
    doc = convert(raw.decode("utf-8", "replace"))
    if len(doc["ac"]) < 1000:
        # A truncated or reshaped upstream file must not replace a good list.
        raise ValueError(f"only {len(doc['ac'])} entries; keeping the previous list")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT)
    try:
        os.unlink(FAILED_STAMP)
    except OSError:
        pass
    log(f"{len(doc['ac'])} aircraft")
    return doc


def needs_refresh(now=None):
    now = now or time.time()
    try:
        if now - os.path.getmtime(OUT) < REFRESH_EVERY_S:
            return False
    except OSError:
        pass
    try:
        if now - os.path.getmtime(FAILED_STAMP) < RETRY_AFTER_FAILURE_S:
            return False
    except OSError:
        pass
    return True


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "ensure"
    if cmd == "ensure" and not needs_refresh():
        return 0
    if cmd not in ("ensure", "build"):
        print("usage: notable-db.py ensure|build", file=sys.stderr)
        return 2
    try:
        build()
        return 0
    except Exception as e:
        log(f"refresh failed: {type(e).__name__}: {e}")
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            open(FAILED_STAMP, "w").close()
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
