#!/usr/bin/env python3
"""Package changes and the clock need an administrator (security review
2026-11-03, SR-12 and SR-39).

Raspberry Pi OS's gui-pkinst, gui-updater and rp-prefapps polkit rules let a
sudo-group user install or remove packages through PackageKit with no
password, given a command line the caller chooses, and let any user stop
systemd-timesyncd. On a radar the kiosk's user is in the sudo group. The
installer puts deploy/polkit-stratoscan.rules first in polkit's order, and
here it is run under node against stand-ins for those stock rules, the way
polkit runs them: in name order, the first answer wins.

Run: python3 tests/test_polkit_rule.py
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULE = ROOT / "deploy" / "polkit-stratoscan.rules"
INSTALLER = (ROOT / "deploy" / "install-setup-server.sh").read_text()
BUILD = (ROOT / "image" / "build.sh").read_text()
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


check(RULE.exists(), "the rule ships in deploy/")
m = re.search(r"install -m 0644 deploy/polkit-stratoscan\.rules (/etc/polkit-1/rules\.d/(\S+))", INSTALLER)
check(bool(m), "the installer puts it in /etc/polkit-1/rules.d, root's and read-only to others")
name = m.group(2) if m else ""
# polkit sorts every rules file by name across both directories; ours must
# come before Raspberry Pi OS's 10- files and packagekit's own.
for stock in ("10-gui-pkinst.rules", "10-gui-updater.rules", "10-rp-prefapps.rules",
              "org.freedesktop.packagekit.rules"):
    check(bool(name) and name < stock, f"{name or 'it'} is read before {stock}")
block = INSTALLER[INSTALLER.find("polkit-stratoscan.rules"):]
block = block[:block.find("stratoscan-firstboot.log")]
check("pkcheck --action-id org.freedesktop.packagekit.package-remove" in block and "exit 1" in block,
      "on a running unit the installer proves the rule against a kiosk-user process, and stops if it isn't working")
check("/etc/polkit-1/rules.d/05-stratoscan.rules" in BUILD, "the factory image is checked for it")

# Stand-ins for the stock rules (same conditions as Raspberry Pi OS's files).
STOCK = r"""
polkit.addRule(function(action, subject) {   // 10-gui-pkinst / -updater / rp-prefapps
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        action.lookup("unit") == "systemd-timesyncd.service") return polkit.Result.YES;
});
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.packagekit.package-") == 0 &&
        action.lookup("cmdline") == "gui-pkinst" && subject.isInGroup("sudo")) return polkit.Result.YES;
});
polkit.addRule(function(action, subject) {   // org.freedesktop.NetworkManager.rules
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" &&
        subject.local && subject.active &&
        (subject.isInGroup("sudo") || subject.isInGroup("netdev"))) return polkit.Result.YES;
});
polkit.addRule(function(action, subject) {   // org.freedesktop.packagekit.rules
    if (action.id == "org.freedesktop.packagekit.upgrade-system" &&
        subject.active && subject.local && subject.isInGroup("sudo")) return polkit.Result.YES;
});
"""
JS = r"""
const rules = [];
const polkit = { Result: { YES: 'yes', NO: 'no', AUTH_ADMIN: 'auth_admin' },
                 addRule: (f) => rules.push(f) };
OURS
STOCK
function decide(id, details, user, groups) {
  const action = { id, lookup: (k) => details[k] };
  const subject = { user, local: true, active: true, isInGroup: (g) => groups.includes(g) };
  for (const r of rules) { const v = r(action, subject); if (v !== undefined && v !== null) return v; }
  return 'default';
}
const kiosk = ['<user>', ['sudo', 'netdev', 'adm']];
const nobody = ['stratoscan-events', []];
console.log(JSON.stringify({
  pkinst: decide('org.freedesktop.packagekit.package-remove', { cmdline: 'gui-pkinst' }, ...kiosk),
  install: decide('org.freedesktop.packagekit.package-install', { cmdline: 'gui-pkinst' }, ...kiosk),
  upgrade: decide('org.freedesktop.packagekit.upgrade-system', {}, ...kiosk),
  timesync: decide('org.freedesktop.systemd1.manage-units', { unit: 'systemd-timesyncd.service' }, ...nobody),
  otherUnit: decide('org.freedesktop.systemd1.manage-units', { unit: 'cups-browsed.service' }, ...kiosk),
  rootPk: decide('org.freedesktop.packagekit.package-install', { cmdline: 'gui-pkinst' }, 'root', ['root']),
  rootTime: decide('org.freedesktop.systemd1.manage-units', { unit: 'systemd-timesyncd.service' }, 'root', []),
  nm: decide('org.freedesktop.NetworkManager.settings.modify.system', {}, ...kiosk),
  nmControl: decide('org.freedesktop.NetworkManager.network-control', {}, ...kiosk),
  nmOwn: decide('org.freedesktop.NetworkManager.settings.modify.own', {}, ...kiosk),
  nmShare: decide('org.freedesktop.NetworkManager.wifi.share.protected', {}, ...kiosk),
  nmScan: decide('org.freedesktop.NetworkManager.wifi.scan', {}, ...kiosk),
  rootNm: decide('org.freedesktop.NetworkManager.settings.modify.system', {}, 'root', ['root']),
}));
"""


def run(ours):
    src = JS.replace("OURS", ours).replace("STOCK", STOCK)
    p = subprocess.run(["node", "-e", src], capture_output=True, text=True, timeout=30)
    if p.returncode:
        print(p.stderr)
        return {}
    return json.loads(p.stdout)


o = run(RULE.read_text() if RULE.exists() else "")
check(o.get("pkinst") == "auth_admin", "the kiosk's user, posing as gui-pkinst, can't remove a package without a password")
check(o.get("install") == "auth_admin" and o.get("upgrade") == "auth_admin",
      "nor install one, or upgrade the system")
check(o.get("timesync") == "auth_admin", "no ordinary user can stop or start time sync")
check(o.get("rootPk") not in ("auth_admin", "no", None) and o.get("rootTime") == "yes",
      "root is left to the rules after ours (and polkit always allows root anyway)")
check(o.get("otherUnit") == "default", "other units are left alone")
# NetworkManager: the kiosk's user is in sudo and netdev, so the stock rule
# let it add or change a system profile, joining the radar to another network
# quietly, which the on-screen setup asks the admin password for (SR-11).
check(o.get("nm") == "auth_admin", "the kiosk's user can't add or change a network profile without a password")
check(o.get("nmControl") == "auth_admin" and o.get("nmOwn") == "auth_admin" and o.get("nmShare") == "auth_admin",
      "nor bring one up, keep one of its own, or share a network")
check(o.get("nmScan") == "default", "a WiFi scan changes nothing and is left alone")
check(o.get("rootNm") not in ("auth_admin", "no", None), "root (setupd, net-watchdog) is left to the rules after ours")
bare = run("")
check(bare.get("pkinst") == "yes" and bare.get("nm") == "yes",
      "(the stand-in stock rules do allow both without ours, as on a stock radar)")

# ---- the installer's live proof counts only a real refusal ---------------------------
# pkcheck exits 1, 2 or 3 for refused, needs-a-password or dismissed; 127 when
# it couldn't ask at all, which proves nothing and must not pass.
import os
import tempfile
start = INSTALLER.index("  if live && command -v pkcheck")
end = INSTALLER.index("\nfi\n", INSTALLER.index("packages: polkit rule installed")) + 1
snippet = INSTALLER[start:end]


def proof(rc):
    d = tempfile.mkdtemp()
    for name, body in (("pkcheck", f"exit {rc}"), ("setpriv", "exec sleep 5"), ("sleep", "exit 0")):
        with open(os.path.join(d, name), "w") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(os.path.join(d, name), 0o755)
    sh = "live() { return 0; }\nKIOSK_USER=$(id -un)\n" + snippet
    env = dict(os.environ, PATH=d + ":" + os.environ["PATH"])
    p = subprocess.run(["sh", "-c", sh], env=env, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout


rc, out = proof(1)
check(rc == 0 and "need an administrator" in out, "a refusal from pkcheck passes the proof")
rc, out = proof(0)
check(rc != 0 and "FAIL" in out, "an allowed removal fails the install")
rc, out = proof(127)
check(rc != 0 and "FAIL" in out, "and so does a pkcheck that couldn't ask polkit at all (exit 127)")

print("polkit rule checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
