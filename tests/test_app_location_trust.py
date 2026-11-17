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

Since 2026-11-15 (security review 2026-11-03, SR-06) a radar set up from the
phone starts without the phone's location, until the owner turns it on for
that radar; and nothing but the setup flow's own switch sends the phone's
position to a radar's home address. So does a radar new to the phone by a
pairing link opened from outside the app; a code read in the app's own
scanner pairs as before, and pairing again never changes a radar's setting.
The question before pairing says which of these will hold, and the alerts
settings give a count of the radars not told and where the switch is, with
no radar's name and no urging.

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
wd = body(ar, "private func withdraw()")
check(before(wd, "for u in units {", "try await relay.location(unit: u.unit, blob: nil)") and "vet(" not in wd,
      "turning it off still withdraws it from every radar the relay lists (a withdrawal carries nothing)")

saved = body(ps, "nonisolated static func savedUnits()")
check("UserDefaults.standard.data(forKey: storeKey)" in saved and 'storeKey = "radome.pairedRadars"' in ps,
      "the phone's own list is what pairing saved, readable in the background")
pair = body(ps, "func pair(_ link: Link, fromOutside: Bool)")
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

# ---- a radar set up from the phone starts without it (SR-06, 2026-11-15) ---------------
check("for unit in recipients where !withheld.contains(unit)" in rep
      and before(rep, "let withheld = PairingStore.locationWithheld()", "LocationBox.seal("),
      "a report leaves out the radars the owner keeps the location from")
wh = body(ps, "nonisolated static func locationWithheld()")
check("$0.shareLocation == false" in wh and "UserDefaults.standard.data(forKey: storeKey)" in wh,
      "which are those saved with sharing off, readable in the background")
check("var shareLocation: Bool?" in body(ps, "struct Radar:"), "radars saved before this still decode, and go on as they were")
check("shareLocation: false" in adopt, "a radar new to the phone by setup starts with sharing off")
check("shareLocation: fromOutside ? false : nil" in pair and "func pair(_ link: Link, fromOutside: Bool) async" in ps,
      "one new by a pairing link opened from outside starts with it off; by a code read in the app's scanner, as before")
check("await pair(link, fromOutside: true)" in body(ps, "func confirmPending()")
      and "pairing.pair(link, fromOutside: false)" in SWIFT["ios/StratoScan/Views/SettingsView.swift"]
      and sum(len(re.findall(r"\bpair\(link\b", t)) for t in SWIFT.values()) == 2,
      "the outside dialog's yes is the one, the scanner the other, and nothing else pairs by a link")
known = body(pair, "if let i = radars.firstIndex(where: { $0.unit == link.unit })")
check(known != "" and "shareLocation" not in known.split("} else {")[0] and not re.search(r"radars\[i\]\.shareLocation\s*=", pair),
      "pairing again with a radar already here leaves the owner's choice alone")
check("withheld = fromOutside" in pair and before(pair, "if withheld {", "message = said")
      and "turn that on under Settings › Paired radars" in body(pair, "if withheld {"),
      "and the closing message says where to turn it on")
check(not re.search(r"radars\[i\]\.shareLocation\s*=", adopt), "setting up a radar already paired here leaves the owner's choice alone")
check("turn that on under Settings" in adopt, "and the phone says so when the setup ends")
ssl = body(ps, "func setShareLocation(")
check("radars[i].shareLocation = on" in ssl and "ApproachReporter.shared.sharingChanged(unit: unit, on: on)" in ssl
      and len(re.findall(r"\.shareLocation\s*=[^=]", ps)) == 1,
      "only the owner's switch changes it")
sc = body(ar, "func sharingChanged(")
check("relay.location(unit: unit, blob: nil)" in sc, "switching it off takes back what the relay holds for that radar")
check("pairing.setShareLocation($0, unit: radar.unit)" in prs and "Share this phone's location" in prs,
      "the switch is on the radar's own page in Settings")
als = SWIFT["ios/StratoScan/Views/AlertsSection.swift"]
wl = body(als, "static func withheldLine(")
check("if push.needsLocation, let line = Self.withheldLine(pairing.radars.filter { $0.shareLocation == false }.count)" in als,
      "the alerts settings count the radars not told where the phone is, only while an alert that needs it is on")
check(wl != "" and ".name" not in als and "kept" not in als, "with no radar's name in the line")
check("guard count > 0 else { return nil }" in wl and "page" in wl and "Paired radars" in wl,
      "which says where the switch is, and nothing when every radar is told")
check(not re.search(r"[Tt]urn (that|it|this) on|can't send|should|so it can't", wl) and "Turn that on" not in als,
      "and doesn't urge turning it on")

# ---- nothing of the phone's goes to the home address (SR-44) -----------------------------
# The home address is plain http and whatever answers is taken for the radar.
# The app only reads from it; the one flow that writes to a radar is setup,
# on the session pinned to the radar's certificate when the code names one.
posters = sorted(f for f, s in SWIFT.items() if re.search(r'httpMethod = (method|"POST"|"PUT")', s))
check(posters == ["ios/StratoScan/Networking/RouteLookupClient.swift", "ios/StratoScan/Networking/RunwayClient.swift",
                  "ios/StratoScan/Pairing/RelayClient.swift", "ios/StratoScan/Setup/RadarSetup.swift"],
      "only setup, the relay client and two look-ups send a body anywhere: %s" % posters)
for f in ("ios/StratoScan/Networking/RouteLookupClient.swift", "ios/StratoScan/Networking/RunwayClient.swift"):
    s = SWIFT[f]
    at = s.index('httpMethod = "POST"')
    req = s[s.rfind("URLRequest(", 0, at):at]
    name = re.match(r"URLRequest\(url: (\w+URL)\)", req)
    check(name is not None and re.search(name.group(1) + r' = URL\(string: "https://', s) is not None and "CLLocation" not in s,
          "%s sends its body to a fixed https service, not the radar's address, and never reads the phone's position" % f.rsplit("/", 1)[1])
readers = sorted(f for f, s in SWIFT.items() if "AdminPassword.load(" in s)
check(readers == [], "the radar's admin password is sent nowhere after setup: %s" % readers)
rs = SWIFT["ios/StratoScan/Setup/RadarSetup.swift"]
check(len(re.findall(r"\boneLocation\(", rs)) == 2 and "Self.oneLocation(" in body(rs, "private func sendPhoneLocation("),
      "in setup, the phone's position is read in one place")
save = body(rs, "func saveName()")
check(len(re.findall(r"sendPhoneLocation\(", rs)) == 2 and "if usePhoneLocation {" in save
      and save.index("if usePhoneLocation {") < save.index("await sendPhoneLocation(stillWanted:"),
      "and sent only from the name screen, with the owner's switch on")

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
check("that radar also gets this phone's location" not in pm
      and "if let known = pairing.radars.first(where: { $0.unit == link.unit })" in pm,
      "but doesn't promise it: it goes by whether the radar is new to this phone")
new_case = pm[pm.index("} else {", pm.index("if let known")):] if "if let known" in pm else ""
check("It won't get this phone's location unless you turn that on afterwards" in new_case.split("if let name")[0],
      "a new radar is said to start without it, and where to turn it on")
check(re.search(r'known\.shareLocation == false\s*\? "[^"]*not told where this phone is\."\s*: "[^"]*gets this phone\'s location\."', pm) is not None,
      "and one already paired is said to stay as its switch has it")
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
enum AlertsSection {
""" + (body((IOS / "StratoScan" / "Views" / "AlertsSection.swift").read_text(), "static func withheldLine(")
       or "static func withheldLine(_ count: Int) -> String? { \"missing\" }") + """
}
for n in [0, 1, 3] { print("LINE\\(n)", AlertsSection.withheldLine(n) ?? "nil") }
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
        lines = {n: " ".join(out.get("LINE%d" % n, [])) for n in (0, 1, 3)}
        check(lines[0] == "nil" and lines[1].startswith("1 paired radar isn't told where this phone is.")
              and lines[3].startswith("3 paired radars aren't told where this phone is."),
              "the alerts line gives the count, and nothing when no radar is kept from it: %s" % lines)
        if ran.returncode != 0:
            check(False, "the run ended badly: " + ran.stderr[-400:])

print("app location trust checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
