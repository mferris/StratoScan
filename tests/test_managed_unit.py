#!/usr/bin/env python3
"""A managed (gift) unit's hardening (security review 2026-10-04, items 6
and 8): SSH only over the tailnet, the shared stores written only from
private addresses, a narrow sudo rule for the maintainer's login and one
SSH key per fleet -- and none of it unless the installer is told MANAGED=1."""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.path.join(ROOT, "deploy")
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


nft = open(os.path.join(D, "stratoscan-managed.nft")).read()
rules = [l.strip() for l in nft.splitlines() if l.strip() and not l.strip().startswith("#")]
check("table inet stratoscan {" in rules and "policy accept;" in nft, "its own table, and it only ever touches port 22")
accepts = [r for r in rules if r.startswith("tcp dport 22") and r.endswith("accept")]
check(any('iifname "tailscale0"' in r for r in accepts) and any("100.64.0.0/10" in r for r in accepts), "SSH is accepted from Tailscale")
check(rules.index("tcp dport 22 drop") > max(rules.index(r) for r in accepts), "and dropped from everywhere else, after the accepts")
check(not any(re.search(r"dport (80|443|8\d{3})", r) for r in rules), "no other port is touched")

sud = open(os.path.join(D, "stratoscan-maintainer.sudoers")).read()
body = "\n".join(l for l in sud.splitlines() if not l.startswith("#"))
check("NOPASSWD: ALL" not in body and "__USER__ ALL=(root) NOPASSWD: STRATOSCAN_MAINTAIN" in body, "the rule names the commands, never ALL")
check("/opt/stratoscan/ota.py apply" in body and "systemctl restart stratoscan-*" in body, "updates and service restarts are allowed")
check("install-setup-server" not in body and "setupd" not in body and "/bin/sh" not in body and "python3" not in body,
      "no command that is root in all but name")

conf = open(os.path.join(D, "92-stratoscan-managed-writes.conf")).read()
check('$HTTP["request-method"] =~ "^(POST|PUT|DELETE|PATCH)$"' in conf and "url.access-deny" in conf, "writes from outside private ranges are refused")
check("sightings|approaches|network" in conf and "GET" not in conf.split("request-method")[1][:60], "reads are untouched")

inst = open(os.path.join(D, "install-setup-server.sh")).read()
block = inst.split('if [ "${MANAGED:-0}" = "1" ]; then', 1)
check(len(block) == 2, "the installer has a MANAGED=1 block")
managed = block[1].split("\nfi\n\n", 1)[0] if len(block) == 2 else ""
for needle in ("stratoscan-managed.nft", "nft -c -f /etc/nftables.conf", "92-stratoscan-managed-writes.conf",
               "visudo -cf", "rm -f /etc/sudoers.d/010_pi-nopasswd", 'deluser "$M" sudo', "grep -qxF \"$MAINTAINER_PUBKEY\""):
    check(needle in managed, "the block does: %s" % needle)
before = "\n".join(l for l in block[0].split("== managed unit")[0].splitlines() if not l.lstrip().startswith("#"))
check("MANAGED" not in before, "nothing before the block depends on MANAGED")
doc = open(os.path.join(ROOT, "docs", "gifting-a-unit.md")).read()
check("MANAGED=1" in doc and "MAINTAINER_PUBKEY" in doc, "the gifting notes say how")
print("managed unit checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
