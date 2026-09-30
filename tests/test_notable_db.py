#!/usr/bin/env python3
"""
Checks for deploy/notable-db.py (plane-alert-db -> /data/notable.json).

The rules that matter are privacy rules, enforced on the unit because the
resulting file is served publicly through the Funnel: PIA aircraft never
appear, and no private person's name survives conversion.

Run: python3 tests/test_notable_db.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
failures, checks = [], 0


def check(label, cond):
    global checks
    checks += 1
    if not cond:
        failures.append(label)


tmp = tempfile.mkdtemp()
os.environ["STRATOSCAN_WEB_ROOT"] = tmp
os.environ["STRATOSCAN_NOTABLE_STATE"] = os.path.join(tmp, "state")
spec = importlib.util.spec_from_file_location("nd", os.path.join(HERE, "..", "deploy", "notable-db.py"))
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)

HEADER = "$ICAO,$Registration,$Operator,$Type,$ICAO Type,#CMPG,$Tag 1,$#Tag 2,$#Tag 3,Category,$#Link\n"
rows = [
    "AE1234,00-1234,USAF,Boeing C-17,C17,Mil,Cargo,,,USAF,",
    "A00001,N1,Some Hospital,Bell 407,B407,Civ,Medevac,,,Flying Doctors,",
    "A00002,N2,City Police,Airbus H125,AS50,Pol,Police,,,Police Forces,",
    "A00003,N3,A Famous Person,Gulfstream G650,GLF6,Civ,Celebrity,,,Don't you know who I am?,",
    "A00004,N4,Rich Person LLC,Boeing BBJ,B737,Civ,,,,Oligarch,",
    "A00005,N5,Private Owner,Cessna 172,C172,Civ,,,,PIA,",
    "A00006,N6,Gov Dept,King Air,BE20,Gov,,,,Dictator Alert,",
    "NOTHEX,N7,X,Y,Z,Mil,,,,USAF,",
]
doc = nd.convert(HEADER + "\n".join(rows) + "\n")
ac = doc["ac"]
check("military keeps its operator", ac["ae1234"][2] == "USAF")
check("police keeps its operator", ac["a00002"][2] == "City Police")
check("a civilian air ambulance keeps no operator name", ac["a00001"][2] == "")
check("a famous person's jet keeps no name", ac["a00003"][2] == "")
check("an 'Oligarch' entry keeps no name", ac["a00004"][2] == "")
check("a person-centred category drops the name even when government-registered", ac["a00006"][2] == "")
check("PIA aircraft never appear", "a00005" not in ac)
check("a malformed hex is dropped", all(len(h) == 6 for h in ac))
check("hexes are lower-cased", "ae1234" in ac and "AE1234" not in ac)
check("the licence is recorded in the file", doc["license"] == "ODbL-1.0")

# ---- a truncated upstream file must not replace a good list ---------------
nd.SOURCE_URL = "file://" + os.path.join(tmp, "tiny.csv")
with open(os.path.join(tmp, "tiny.csv"), "w") as f:
    f.write(HEADER + "\n".join(rows))
os.makedirs(os.path.dirname(nd.OUT), exist_ok=True)
with open(nd.OUT, "w") as f:
    json.dump({"ac": {"keep": 1}}, f)
check("a suspiciously small source is refused", nd.main(["x", "build"]) == 1)
with open(nd.OUT) as f:
    check("and the previous list stays in place", json.load(f)["ac"] == {"keep": 1})
check("a failure is recorded for back-off", os.path.exists(nd.FAILED_STAMP))

# ---- refresh timing ---------------------------------------------------------
now = time.time()
os.utime(nd.OUT, (now, now))
check("a fresh list is left alone", nd.needs_refresh(now) is False)
old = now - nd.REFRESH_EVERY_S - 10
os.utime(nd.OUT, (old, old))
os.utime(nd.FAILED_STAMP, (now, now))
check("a recent failure backs off even when stale", nd.needs_refresh(now) is False)
os.utime(nd.FAILED_STAMP, (old, old))
check("a stale list with no recent failure refreshes", nd.needs_refresh(now) is True)

print(f"{checks - len(failures)}/{checks} notable-db checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
