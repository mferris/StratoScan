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
check(o.get("otherUnit") == "default" and o.get("nm") == "default",
      "nothing else is changed (other units, NetworkManager)")
bare = run("")
check(bare.get("pkinst") == "yes", "(the stand-in stock rules do allow it without ours, as on a stock radar)")

print("polkit rule checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
