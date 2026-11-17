#!/usr/bin/env python3
"""What the app declares to Apple matches what it does (2026-11-17).

Three things had drifted. The privacy manifest said only a push address and
a key left the phone, when the phone's name, its alert choices and (with
alerts about where the phone is) its sealed location go to the relay too.
The "Always" location question named only "Approaching me", when nearby
alerts set to "Where I am" or "Both" use it as well. And the background
mode had no word on why it is there.

These read the manifest, project.yml and the Info.plist xcodegen writes
from it, and the Swift that decides what is sent.

Run: python3 tests/test_app_store_declarations.py
"""
import pathlib
import plistlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


yml = (IOS / "project.yml").read_text()
info = plistlib.loads((IOS / "StratoScan" / "App" / "Info.plist").read_bytes())
manifest_text = (IOS / "StratoScan" / "App" / "PrivacyInfo.xcprivacy").read_text()
manifest = plistlib.loads(manifest_text.encode())
push = (IOS / "StratoScan" / "Pairing" / "PushManager.swift").read_text()
client = (IOS / "StratoScan" / "Pairing" / "RelayClient.swift").read_text()
reporter = (IOS / "StratoScan" / "Location" / "ApproachReporter.swift").read_text()
privacy = " ".join((ROOT / "docs" / "privacy.md").read_text().split())

# the app target's own part of project.yml
app_yml = yml[yml.index("  StratoScan:\n"):yml.index("  StratoScanWidget:\n")]


def yml_string(key):
    m = re.search(r'^\s*%s: "(.*)"$' % re.escape(key), app_yml, re.M)
    return m.group(1) if m else None


# 1. the privacy manifest
P = "NSPrivacyCollectedDataType"
declared = {d[P][len(P):]: d for d in manifest["NSPrivacyCollectedDataTypes"]}
check(sorted(declared) == ["CoarseLocation", "DeviceID", "OtherUsageData", "OtherUserContent", "PreciseLocation"],
      "the manifest declares the push address and key, the phone's name, the alert choices, and both locations")
check(all(d[P + "Purposes"] == [P + "PurposeAppFunctionality"] and d[P + "Tracking"] is False for d in declared.values())
      and manifest["NSPrivacyTracking"] is False and manifest["NSPrivacyTrackingDomains"] == [],
      "each is for the app's own working only, and nothing is for tracking")
check({k: d[P + "Linked"] for k, d in declared.items()}
      == {"DeviceID": True, "OtherUserContent": True, "OtherUsageData": True, "PreciseLocation": False, "CoarseLocation": False},
      "what the relay keeps readable against the phone is linked; the sealed location and the rounded one are not")
header = " ".join(manifest_text[manifest_text.index("<!--"):manifest_text.index("-->")].split())
check(all(w in header for w in ("APNs device token", "random public key", "phone's name", "alert choices",
                                "sealed", "at most 6 hours", "about 5 km", "to be safe"))
      and "The only thing that leaves the phone" not in header,
      "its comment lists each thing that leaves the phone, and says why the sealed location is declared")

# 1b. the app still sends what the manifest says, so a new thing sent gets a look here
check('var body: [String: Any] = ["token": token, "env": environment, "kinds": kinds]' in client
      and 'if let name { body["name"] = name }' in client and 'body["la_start_token"] = la' in client
      and 'send("POST", "/v1/phone/name", ["name": name])' in client
      and 'send("POST", "/v1/phone/kinds", ["kinds": kinds])' in client
      and 'send("POST", "/v1/phone/location", ["unit": unit, "blob": value])' in client,
      "to the relay go the push address, the name, the alert choices and a sealed location, as declared")
check("LocationBox.seal(lat: l.coordinate.latitude, lon: l.coordinate.longitude," in reporter
      and reporter.count("relay.location(unit: unit, blob: blob)") == 1,
      "the location goes only sealed to a radar's own key")
check("At most 6 hours" in privacy and "your alert choices" in privacy and "sealed for your own radar" in privacy,
      "the privacy policy says the same: the alert choices, and the sealed location for at most 6 hours")

# 2. the "Always" location question covers both uses
always = info["NSLocationAlwaysAndWhenInUseUsageDescription"]
check("var needsLocation: Bool { !effectiveKinds.isEmpty && (kinds.contains(.approach_me) || place != .radar) }" in push,
      "the location is wanted for Approaching me, and for nearby alerts about where the phone is")
check("approaching you" in always and "nearby alerts about where you are" in always,
      "the question iOS asks names both")
check("encrypted so only your own radar can read it" in always and "Turn it off any time in Settings." in always
      and len(re.findall(r"[.!?](?:\s|$)", always)) <= 2,
      "and still says it is encrypted for the owner's own radar and can be turned off, in two sentences")
check('"Where I am"' in privacy and "Approaching me" in privacy,
      "the privacy policy names both too")

# 3. project.yml and the plist xcodegen writes from it agree
for key in ("NSLocationAlwaysAndWhenInUseUsageDescription", "NSLocationWhenInUseUsageDescription",
            "NSCameraUsageDescription", "NSLocalNetworkUsageDescription"):
    check(yml_string(key) is not None and yml_string(key) == info.get(key), "%s is the same in project.yml and Info.plist" % key)
check(sorted(k for k in info if k.endswith("UsageDescription"))
      == sorted(re.findall(r"^\s*(NS\w+UsageDescription):", app_yml, re.M)),
      "neither has a usage string the other lacks")
modes = re.search(r"^\s*UIBackgroundModes: \[(.*)\]$", app_yml, re.M)
check(modes is not None and [m.strip() for m in modes.group(1).split(",") if m.strip()] == info.get("UIBackgroundModes", []),
      "the background modes are the same in project.yml and Info.plist")

# 4. the background mode says why it is there
if info.get("UIBackgroundModes"):
    above = app_yml[:modes.start()].rstrip().splitlines()
    note = []
    while above and above[-1].lstrip().startswith("#"):
        note.insert(0, above.pop().lstrip("# "))
    note = " ".join(note)
    check(info["UIBackgroundModes"] == ["remote-notification"]
          and "watchLiveActivities" in note and "To remove it" in note and "real phone" in note,
          "remote-notification is the only one, kept for the countdown's wake, with the test that would let it go")
    check("pushTokenUpdates" in push and "activityUpdates" in push,
          "the app still reports a countdown's token after that wake")
else:
    check("content-available" not in (ROOT / "relay" / "src" / "apns.js").read_text()
          and "didReceiveRemoteNotification" not in push,
          "with no background mode, nothing sends or takes a silent push")

print("app store declaration checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
