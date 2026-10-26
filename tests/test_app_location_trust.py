#!/usr/bin/env python3
"""The phone's location goes only to radars it paired itself (security review,
2026-10-26).

"Approaching me", and nearby alerts about where the phone is, send the
phone's position sealed to each radar's box key. The key's signature was
checked against the radar's id, but the ids came from the relay's list of
radars for the phone, so the check said nothing about whether the phone had
chosen that radar. Now:

- the relay's list is checked against the phone's own, the radars it saved
  when it paired (by their code, scanned or opened with a yes, or by setting
  one up from the phone), which the relay can't add to;
- while the relay lists a radar the phone never paired, no radar gets the
  location; Settings says so, and offers to unpair it;
- box keys kept for radars no longer paired here are forgotten;
- a pairing link says, before the yes, that the radar gets the phone's
  location while those alerts are on, flags a name another paired radar
  already has, and takes only a home-network address. Its addresses set the
  radar view only when the app has none of its own: it never moves the radar
  view off the radar it reads, nor replaces the away address.

The first part reads the app's Swift. Where swiftc is installed the second
compiles the shared LocationBox and runs it with a radar the relay lists on
its own, carrying a box key its own id signs.

Run: python3 tests/test_app_location_trust.py
"""
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def code(text):
    """The Swift without its comments (a // after a colon is a URL)."""
    return "\n".join(re.sub(r"(?<![:\"])//.*$", "", line) for line in text.splitlines())


def body(text, start):
    """From `start` to the end of its braces; empty when it isn't there."""
    i = text.find(start)
    if i < 0:
        return ""
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        depth += {"{": 1, "}": -1}.get(text[k], 0)
        if depth == 0:
            return text[i:k + 1]
    return text[i:]


def before(text, a, b):
    """`a` comes before `b` in `text`, and both are there."""
    return a in text and b in text and text.index(a) < text.index(b)


SWIFT = {p.relative_to(ROOT).as_posix(): code(p.read_text()) for p in sorted(IOS.rglob("*.swift"))
         if ".xcodeproj" not in p.parts and "build" not in p.parts}
ar = SWIFT["ios/StratoScan/Location/ApproachReporter.swift"]
ps = SWIFT["ios/StratoScan/Pairing/PairingStore.swift"]
cv = SWIFT["ios/StratoScan/Views/ContentView.swift"]
box = SWIFT["ios/Shared/LocationBox.swift"]

# ---- the location goes only to radars paired here ------------------------------------
rep = body(ar, "private func report(")
check("let recipients = vet(units.map(\\.unit))" in rep and "for unit in recipients" in rep and "for u in units" not in rep,
      "a report seals only to the radars vet() allows, not to every radar the relay lists")
check(before(rep, "vet(units.map", "LocationBox.seal(") and "relay.location(unit: unit, blob: blob)" in rep,
      "and vets the relay's list before anything is sealed")
vet = body(ar, "func vet(")
check("PairingStore.savedUnits()" in vet and "LocationBox.recipients(listed: listed, paired: paired)" in vet,
      "vet() checks the relay's list against the radars this phone saved when pairing")
check(before(vet, "PairingStore.savedUnits()", "LocationBox.recipients("), "read when the relay has answered, so a pairing just made counts")
check("listed.filter { !paired.contains($0) }" in vet and "UserDefaults.standard.set(now, forKey: Self.strangersKey)" in vet,
      "a radar the relay lists that was never paired here is noted, and kept for Settings")
check("cache.filter { paired.contains($0.key) }" in vet, "box keys kept for radars no longer paired here are forgotten")
rec = body(box, "static func recipients(")
check("listed.allSatisfy(paired.contains) ? listed : nil" in rec,
      "with any such radar listed, no radar gets the location")
bk = body(ar, "private func boxKey(")
check(before(bk, "guard PairingStore.savedUnits().contains(unit) else { return nil }", "cache[unit]")
      and before(bk, "PairingStore.savedUnits()", "relay.boxKey(unit: unit)"),
      "a box key is used, or asked for, only for a radar paired here")
sealers = [f for f, s in SWIFT.items() if "LocationBox.seal(" in s]
check(sealers == ["ios/StratoScan/Location/ApproachReporter.swift"], "nothing else seals the location: %s" % sealers)
check("for u in units { try? await relay.location(unit: u.unit, blob: nil) }" in body(ar, "private func withdraw()"),
      "turning it off still withdraws it from every radar the relay lists (a withdrawal carries nothing)")

saved = body(ps, "nonisolated static func savedUnits()")
check("UserDefaults.standard.data(forKey: storeKey)" in saved and 'storeKey = "radome.pairedRadars"' in ps,
      "the phone's own list is what pairing saved, readable in the background")
pair = body(ps, "func pair(_ link: Link)")
adopt = body(ps, "func adopt(")
check(len(re.findall(r"radars\.append\(", ps)) == 2 and "radars.append(" in pair and "radars.append(" in adopt,
      "the list grows only by pairing with a code or setting a radar up")
refresh = body(ps, "func refresh()")
check("ApproachReporter.shared.vet(listed)" in refresh and "radars.append" not in refresh,
      "the relay's list only takes from it, and anything it adds is noted, not taken on")
check("ApproachReporter.shared.forgetStranger(link.unit)" in pair and "ApproachReporter.shared.forgetStranger(unit)" in adopt,
      "a radar paired here is no longer a stranger")
check("try await relay.unpair(unit: unit)" in body(ps, "func unpair(stranger unit: String)"),
      "a stranger can be unpaired at the relay")
prs = SWIFT["ios/StratoScan/Views/PairedRadarsSection.swift"]
check("ForEach(reporter.strangers" in prs and "pairing.unpair(stranger: unit)" in prs and "location" in prs,
      "Settings shows each one, says the location goes nowhere meanwhile, and offers to unpair it")
check("reporter.strangers.isEmpty" in SWIFT["ios/StratoScan/Views/AlertsSection.swift"],
      "and the alerts settings say the location isn't being sent")

# ---- a pairing link --------------------------------------------------------------------
parse = body(ps, "nonisolated static func parse(")
check('q("h").flatMap { RadarSetup.isPrivateHost($0) ? $0 : nil }' in parse,
      "a pairing link's home address is a home-network one only, as a setup link's")
unset = body(pair, "if Self.radarViewUnset")
rest = pair.replace(unset, "")
check('APIConfig.baseURL = "http://\\(h)"' in unset and "APIConfig.awayURL = p" in unset
      and "APIConfig.awayURL =" not in rest and "APIConfig.baseURL =" not in rest,
      "a link sets the radar view's addresses only inside the no-radar-yet case")
check("APIConfig.baseURL == APIConfig.defaultBaseURL && APIConfig.awayURL == nil" in body(ps, "nonisolated static var radarViewUnset"),
      "which is: home still the factory default, and no away address")
pm = body(cv, "private var pairingMessage: String")
check("Approaching me" in pm and "this phone's location" in pm,
      "the pairing question says the radar gets this phone's location while those alerts are on")
check("You already have a radar by that name" in pm and "$0.unit != link.unit" in pm,
      "and flags a name another paired radar already has")
check("PairingStore.radarViewUnset" in pm and "The radar view stays on the radar it reads now." in pm,
      "and says whether the radar view moves to it")
check("Text(pairingMessage)" in cv and 'confirmationDialog("Pair with this radar?"' in cv, "it is the question asked before pairing")

# ---- compiled ----------------------------------------------------------------------------
swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc or platform.system() != "Darwin":
    print("skip the compiled checks: no swiftc here (they run on the Mac that builds the app)")
else:
    work = pathlib.Path(tempfile.mkdtemp())
    (work / "main.swift").write_text("""import CryptoKit
import Foundation
// a radar paired here, one the relay lists on its own, and one paired here the relay doesn't list
func radar() -> (id: String, key: String, sig: String) {
    let id = Curve25519.Signing.PrivateKey()
    let box = Curve25519.KeyAgreement.PrivateKey().publicKey.rawRepresentation.base64urlString
    let sig = try! id.signature(for: Data((LocationBox.boxKeyContext + box).utf8)).base64urlString
    return (id.publicKey.rawRepresentation.base64urlString, box, sig)
}
let mine = radar(), added = radar(), other = radar()
func names(_ r: [String]?) -> String {
    guard let r else { return "none" }
    return r.isEmpty ? "-" : r.map { $0 == mine.id ? "mine" : $0 == added.id ? "added" : "other" }.joined(separator: ",")
}
print("SIGNED", LocationBox.verifiedBoxKey(unit: added.id, key: added.key, sig: added.sig) != nil)
print("ADDED", names(LocationBox.recipients(listed: [mine.id, added.id], paired: [mine.id])))
print("ONLY", names(LocationBox.recipients(listed: [added.id], paired: [mine.id])))
print("MINE", names(LocationBox.recipients(listed: [mine.id], paired: [mine.id, other.id])))
print("NONE", names(LocationBox.recipients(listed: [], paired: [mine.id])))
print("REINSTALLED", names(LocationBox.recipients(listed: [mine.id], paired: [])))
""")
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    built = subprocess.run([swiftc, "-target", arch + "-apple-macos14", "-o", str(work / "box"),
                            str(IOS / "Shared" / "LocationBox.swift"), str(work / "main.swift")],
                           capture_output=True, text=True, timeout=300)
    check(built.returncode == 0, "LocationBox compiles on its own" + ("" if built.returncode == 0 else ": " + built.stderr[-600:]))
    if built.returncode == 0:
        ran = subprocess.run([str(work / "box")], capture_output=True, text=True, timeout=60)
        out = {l.split()[0]: l.split()[1:] for l in ran.stdout.splitlines() if l.strip()}
        check(out.get("SIGNED") == ["true"], "a radar the relay lists on its own can carry a box key its id signs: %s" % out.get("SIGNED"))
        check(out.get("ADDED") == ["none"], "so with it listed beside the paired radar, no radar gets the location: %s" % out.get("ADDED"))
        check(out.get("ONLY") == ["none"], "nor when it is the only one listed: %s" % out.get("ONLY"))
        check(out.get("MINE") == ["mine"], "the paired radar the relay lists gets it, the one it doesn't list doesn't: %s" % out.get("MINE"))
        check(out.get("NONE") == ["-"], "nothing listed, nothing sent: %s" % out.get("NONE"))
        check(out.get("REINSTALLED") == ["none"],
              "with nothing paired here (the app reinstalled) a listed radar is a stranger until paired again: %s" % out.get("REINSTALLED"))
        if ran.returncode != 0:
            check(False, "the run ended badly: " + ran.stderr[-400:])

print("app location trust checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
