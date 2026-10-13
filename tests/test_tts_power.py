#!/usr/bin/env python3
"""Speech synthesis is held to one core (#53, 2026-10-13).

Measured on RDU: Piper on all four cores pulled the 5 V supply to 4.67 V
for 1.6 s on every spoken alert, at the moment the chime played and the
backlight came on; on one core the supply stayed above 4.82 V.

Run: python3 tests/test_tts_power.py
"""
import pathlib
import re
import sys

unit = (pathlib.Path(__file__).resolve().parent.parent / "deploy" / "stratoscan-tts.service").read_text()
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


body = "\n".join(l for l in unit.splitlines() if not l.lstrip().startswith("#"))
check(re.search(r"^AllowedCPUs=\d$", body, re.M) is not None, "the speech service may use one core")
check(re.search(r"^CPUQuota=100%$", body, re.M) is not None, "and no more than one core's worth")
check("Nice=5" in body and "MemoryMax=600M" in body, "its other limits stay")
print("tts power checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
