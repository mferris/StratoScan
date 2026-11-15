#!/usr/bin/env python3
"""What a radar calls a paired phone (2026-11-15).

A radar lists the phones paired with it by name. The app sent
UIDevice.current.name, which since iOS 16 is "iPhone" on every phone, so two
paired phones were both "iPhone" and the one to unpair could only be told by
its date. Now the app sends the phone's model ("iPhone 16 Pro"), or a name
its owner types in Settings, at pairing and whenever it registers for
alerts; the relay renames that phone's pairings then, so a phone paired
before this doesn't have to pair again.

These read the app's Swift, the relay and the privacy page. The relay's own
behaviour is tested in relay/test/relay.test.js.

Run: python3 tests/test_app_phone_name.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios" / "StratoScan"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


name = (IOS / "Pairing" / "PhoneName.swift").read_text()
store = (IOS / "Pairing" / "PairingStore.swift").read_text()
client = (IOS / "Pairing" / "RelayClient.swift").read_text()
push = (IOS / "Pairing" / "PushManager.swift").read_text()
section = (IOS / "Views" / "PairedRadarsSection.swift").read_text()
relay = (ROOT / "relay" / "src" / "index.js").read_text()
relay_test = (ROOT / "relay" / "test" / "relay.test.js").read_text()
privacy = (ROOT / "docs" / "privacy.md").read_text()

setup = (IOS / "Setup" / "RadarSetup.swift").read_text()
everywhere = "".join(p.read_text() for p in IOS.rglob("*.swift") if p.name != "PhoneName.swift")
check("name: PhoneName.current" in store and "name: PhoneName.current" in setup and "UIDevice.current.name" not in everywhere,
      "pairing sends the phone's model or its owner's name for it, not iOS's one name for every phone")
check("static var current: String { custom ?? model }" in name and 'sysctlbyname("hw.machine"' in name
      and "?? UIDevice.current.model" in name,
      "the name is the one typed, else the model, else the kind of device for a model not listed")
models = dict(re.findall(r'"(iP(?:hone|ad)\d+,\d+)": "([^"]+)"', name))
check(len(models) >= 70 and models.get("iPhone17,1") == "iPhone 16 Pro" and models.get("iPhone19,4") == "iPhone Duo"
      and models.get("iPad16,6") == "iPad Pro 13-inch (M4)" and sum(k.startswith("iPad") for k in models) >= 30
      and all(v.startswith(("iPhone", "iPad")) for v in models.values()),
      f"{len(models)} models are named, from Apple's identifiers")
limits = (ROOT / "relay" / "src" / "limits.js").read_text()
check("while t.utf16.count > 40 { t.removeLast() }" in name and "controlCharacters" not in name.split("static func clean")[1].split("\n    }")[0]
      and "0x2028" in name and ".replace(/[\\ud800-\\udbff]$/, '').trim()" in limits,
      "a typed name is cut as the relay cuts it: 40 UTF-16 units, never through an emoji, joiners kept")
check("func syncName(paired: Bool) async {" in push and "relay.setName(name)" in push and '"/v1/phone/name"' in client
      and "PushManager.shared.syncName(paired: !pairing.radars.isEmpty)" in (IOS / "App" / "StratoScanApp.swift").read_text()
      and "if (pathname === '/v1/phone/name' && m === 'POST') return phoneName(request, env);" in relay,
      "a phone with notifications off still tells its radars its name, by a route that needs no push token")
check('if let name { body["name"] = name }' in client and "name: PhoneName.current)" in push and "func nameChanged()" in push,
      "the name goes with every registration for alerts, and again when it is changed")
check('LabeledContent("This phone")' in section and "TextField(PhoneName.model, text: $phoneName)" in section
      and "PushManager.shared.nameChanged()" in section,
      "Settings has the field, showing the model until a name is typed")
check("const name = cleanPhoneName(payload.name);" in relay
      and "UPDATE pairings SET name = ?1 WHERE phone = ?2 AND (name IS NULL OR name != ?1)" in relay,
      "the relay renames that phone's own pairings when it registers with a name")
check("another phone's name is not touched" in relay_test and "no name, or not a name, changes nothing" in relay_test,
      "and the relay's tests hold it to that phone alone")
check('the generic device name iOS provides' not in privacy and 'a name for the phone' in privacy and 'or a name you type in Settings' in privacy
      and "Alex's iPhone" not in privacy + (ROOT / "relay" / "README.md").read_text() + (ROOT / "relay" / "schema.sql").read_text(),
      "the privacy page says what name is sent")

print("app phone-name checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
