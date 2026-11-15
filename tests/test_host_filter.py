#!/usr/bin/env python3
"""Nobody on the internet opens a connection to a radar over IPv6, and IPv4
is not filtered at all (security review 2026-11-03, SR-10; IPv6-only since
2026-11-15).

The radar's page and SSH listen on every address it has, a global IPv6 one
among them. deploy/stratoscan-filter.nft is the radar's own filter for that.
Here its rules are read and run, in order, against packets a radar meets:
every IPv4 packet gets in, what the house sends over IPv6 gets in, what the
internet sends over IPv6 does not, and nothing the radar needs to stay on
its network is caught. And the ways it could do harm are closed: it has one
table and one hook, it fails open, the installer switches it on apart from
everything else and never stops over it, and the check that guards an
owner's SSH session leaves the filter off whenever it cannot tell.

Run: python3 tests/test_host_filter.py
"""
import ipaddress
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
NFT = D / "stratoscan-filter.nft"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


text = NFT.read_text()
code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))

# ---- its own table, the input hook, nothing else ----------------------------
lines = [l.strip() for l in code.splitlines() if l.strip()]
check(lines[:3] == ["table inet stratoscan_filter", "delete table inet stratoscan_filter", "table inet stratoscan_filter {"],
      "it replaces its own table and only that (declare, delete, define)")
check("flush" not in code, "it never flushes the ruleset: Tailscale's tables and the other StratoScan ones stay")
check(len(re.findall(r"\btable\b", code)) == 3 and len(re.findall(r"\bchain\b", code)) == 1,
      "one table, one chain")
hooks = re.findall(r"type (\w+) hook (\w+) priority ([^;]+);\s*policy (\w+);", code)
check(hooks == [("filter", "input", "10", "accept")], "the chain is a filter on input only: no forwarding, no NAT, nothing outbound")
for other in ("stratoscan-https.nft", "stratoscan-managed.nft"):
    names = set(re.findall(r"^table (\w+ \w+)", (D / other).read_text(), re.M))
    check("inet stratoscan_filter" not in names and names, f"{other} has a table of its own, by another name")
check(not re.search(r"\b(masquerade|redirect|dnat|snat|forward|output|prerouting|postrouting)\b", code),
      "no rule forwards, redirects or translates")

# ---- the rules, run in order ------------------------------------------------
sets = {name: [ipaddress.ip_network(t.strip()) for t in body.split(",")]
        for name, body in re.findall(r"set (\w+) \{.*?elements = \{([^}]*)\}", code, re.S)}
chain = re.search(r"policy accept;(.*?)\n    \}\n\}", code, re.S).group(1)
rules = [r.strip() for r in chain.splitlines() if r.strip()]
PROTO = {"tcp", "udp", "icmp", "ipv6-icmp", "igmp"}


def matches(rule, p):
    """Whether every condition of one rule holds for packet p; None for a
    condition this test does not know, which fails the test. The whole rule
    is read even after a condition fails, so an unknown one is always found."""
    toks = rule.replace("{", " { ").replace("}", " } ").replace(",", " ").split()
    v6 = ":" in p["src"]
    i, ok = 0, True
    while i < len(toks):
        t = toks[i]
        if t in ("accept", "drop", "counter"):
            i += 1
        elif toks[i:i + 4] == ["reject", "with", "tcp", "reset"]:
            i += 4
        elif toks[i:i + 2] == ["meta", "nfproto"] and toks[i + 2] in ("ipv4", "ipv6"):
            ok = ok and v6 == (toks[i + 2] == "ipv6")
            i += 3
        elif toks[i:i + 2] == ["ct", "state"]:
            j = i + 2
            states = set()
            while toks[j] in ("established", "related", "new", "invalid"):
                states.add(toks[j])
                j += 1
            ok = ok and p["state"] in states
            i = j
        elif t == "iifname":
            ok = ok and p["iif"] == toks[i + 1].strip('"')
            i += 2
        elif toks[i:i + 2] == ["meta", "l4proto"]:
            if toks[i + 2] == "{":
                j = toks.index("}", i)
                want, i = set(toks[i + 3:j]), j + 1
            else:
                want, i = {toks[i + 2]}, i + 3
            if not want <= PROTO:
                return None
            ok = ok and p["proto"] in want
        elif t in ("ip", "ip6") and toks[i + 1] in ("saddr", "daddr"):
            addr = ipaddress.ip_address(p["src" if toks[i + 1] == "saddr" else "dst"])
            v = toks[i + 2]
            nets = sets[v[1:]] if v.startswith("@") else [ipaddress.ip_network(v)]
            ok = ok and addr.version == (4 if t == "ip" else 6) and any(addr in n for n in nets if n.version == addr.version)
            i += 3
        elif t == "udp" and toks[i + 1] in ("sport", "dport"):
            ok = ok and p["proto"] == "udp" and p[toks[i + 1]] == int(toks[i + 2])
            i += 3
        else:
            return None
    return ok


RADAR4, RADAR6, RADAR_LL = "192.168.1.50", "2001:db8::50", "fe80::50"


def verdict(**p):
    """What the chain does with one packet. The defaults are a new TCP
    connection to the page, arriving on the home network's interface, from
    192.168.1.23; a packet with an IPv6 source goes to the radar's global
    IPv6 address unless it says otherwise."""
    p = dict({"state": "new", "iif": "wlan0", "proto": "tcp", "src": "192.168.1.23", "sport": 50000, "dport": 80}, **p)
    p.setdefault("dst", RADAR6 if ":" in p["src"] else RADAR4)
    for rule in rules:
        m = matches(rule, p)
        if m is None:
            return "unknown rule: " + rule
        if m:
            return "reject" if "reject" in rule else "drop" if rule.endswith("drop") else "accept"
    return "accept"       # the chain's policy


unknown = [r for r in rules if matches(r, {"state": "new", "iif": "x", "proto": "sctp", "src": "192.0.2.1",
                                           "dst": "192.0.2.2", "sport": 1, "dport": 1}) is None]
check(not unknown, "every rule is one this test can run" + (": " + "; ".join(unknown) if unknown else ""))
check(rules[0] == "meta nfproto ipv4 accept", "the first rule accepts every IPv4 packet, before anything else is looked at")
check(rules[1] == "ct state established,related accept", "then answers to what the radar asked for")
check(rules[-2:] == ["meta l4proto tcp counter reject with tcp reset", "counter drop"],
      "it ends by refusing what is left: TCP with a reset, the rest dropped")
check(all(r.endswith("accept") for r in rules[:-2]), "every rule before that only lets something in")
check(not re.search(r"\bip (saddr|daddr)\b", code) and "house4" not in code and not re.search(r"\b(icmp|igmp)\b", code.replace("ipv6-icmp", "")),
      "no rule looks at an IPv4 address or an IPv4-only protocol: there is nothing left that could tell one IPv4 packet from another")
check(sorted(sets) == ["house6"] and sorted(map(str, sets["house6"])) == ["fc00::/7", "fe80::/10"],
      "the one set is the house's IPv6 addresses: link-local and unique-local")
check("unshare -rn nft -c -f" in text and "AFTER ANY EDIT" in text,
      "the file says it must be checked again by nft, in a private network namespace, after any edit")

GLOBAL6, PUBLIC4 = "2001:db8::99", "198.51.100.7"
# IPv4 is not filtered. A home router shares one IPv4 address (NAT), so the
# internet does not reach the radar over IPv4 unless the owner forwards a
# port; and the review of the first version of this filter found that letting
# IPv4 in only from the private ranges would lock an owner out of a radar on
# a home network numbered outside them, where SSH from that network is the
# only way in. So every IPv4 source, private or public, reaches every port,
# in every state, on every interface, whatever the protocol.
V4 = ("192.168.1.23", "10.0.0.5", "172.16.4.4", "169.254.7.7", "10.42.0.17", "100.100.1.2", "0.0.0.0",
      PUBLIC4, "203.0.113.200", "11.0.0.1", "172.32.0.1", "192.169.0.1", "25.1.2.3", "1.1.1.1")
for src in V4:
    for port in (22, 80, 443, 4443, 8085, 8090, 30005, 1, 65535):
        check(verdict(src=src, dport=port) == "accept", f"IPv4 from {src} reaches port {port}")
for src in (PUBLIC4, "192.168.1.23"):
    check(all(verdict(src=src, proto=proto, state=state, iif=iif, dport=53) == "accept"
              for proto in ("tcp", "udp", "icmp", "igmp") for state in ("new", "invalid", "established")
              for iif in ("wlan0", "eth0", "tailscale0")),
          f"and any other IPv4 packet from {src}: any protocol, state or interface")
check(verdict(src="0.0.0.0", dst="255.255.255.255", proto="udp", sport=68, dport=67) == "accept"
      and verdict(src="192.168.1.23", dst="224.0.0.251", proto="udp", sport=5353, dport=5353) == "accept",
      "so the setup hotspot's DHCP and IPv4 Bonjour need no rule of their own")

# the finding: the page, the app's setup ports and SSH, from the internet over IPv6
for port in (22, 80, 443, 4443, 8085, 8090, 30005, 1, 65535):
    check(verdict(src=GLOBAL6, dport=port) == "reject", f"a new connection to port {port} from a global IPv6 address is refused")
check(verdict(src=GLOBAL6, iif="eth0", dport=22) == "reject", "on the wired interface as well")
check(verdict(src=GLOBAL6, proto="udp", dport=53) == "drop" and verdict(src=GLOBAL6, proto="udp", dport=41641) == "drop"
      and verdict(src=GLOBAL6, proto="sctp", dport=80) == "drop", "other new IPv6 traffic from outside is dropped")
check(verdict(src=GLOBAL6, state="invalid", dport=80) == "reject", "and a packet that belongs to no connection")
check(verdict(src="2001:db8:0:1::7", dport=80) == "reject",
      "a device in the house using its own global IPv6 address is refused too (it gets the reset and moves on to IPv4)")
check(verdict(src="::ffff:c0a8:117", dport=22) == "reject" and verdict(src="64:ff9b::c633:6407", dport=22) == "reject",
      "an IPv6 packet whose source only looks like an IPv4 address is still IPv6")
# the house, over IPv6
for src in ("fe80::1c2d:3e4f:5a6b:7c8d", "fd12:3456:789a::5", "fc00::1", "fd7a:115c:a1e0::12"):
    for port, dst in ((22, RADAR_LL), (80, RADAR6), (443, RADAR6), (4443, RADAR6)):
        check(verdict(src=src, dst=dst, dport=port) == "accept", f"{src} reaches port {port}")
check(verdict(src="fec0::1", dport=22) == "reject" and verdict(src="fe00::1", dport=22) == "reject"
      and verdict(src="fbff::1", dport=22) == "reject", "the house's IPv6 ranges end where they should")
check(verdict(iif="lo", src="::1", dst="::1", dport=8090) == "accept"
      and verdict(iif="lo", src=RADAR6, dst=RADAR6, dport=80) == "accept", "the radar reaches itself over IPv6: its own screen and services")
check(verdict(iif="tailscale0", src="fd7a:115c:a1e0::12", dst="fd7a:115c:a1e0::50", dport=80) == "accept"
      and verdict(iif="tailscale0", src=GLOBAL6, dport=22) == "accept",
      "anything arriving on tailscale0 is let in (the tailnet's own policy decides there)")
# what a radar needs to stay on its IPv6 network
check(verdict(state="established", src=GLOBAL6, sport=443, dport=51000) == "accept"
      and verdict(state="related", src=GLOBAL6, proto="udp", dport=51000) == "accept",
      "answers to the radar's own connections come back from anywhere")
check(verdict(src="fe80::1", dst="ff02::1", proto="ipv6-icmp") == "accept", "router advertisements (ICMPv6 to all nodes)")
check(verdict(src="fe80::1", dst="ff02::1:ff00:50", proto="ipv6-icmp") == "accept"
      and verdict(src="::", dst="ff02::1:ff00:50", proto="ipv6-icmp") == "accept"
      and verdict(src=GLOBAL6, dst=RADAR6, proto="ipv6-icmp") == "accept",
      "neighbour discovery, from a link-local, an unspecified (address check) or a global source")
check(verdict(src=GLOBAL6, state="invalid", proto="ipv6-icmp") == "accept", "ICMPv6 always: ping and path MTU as well")
check(verdict(src="fe80::1", dst=RADAR_LL, proto="udp", sport=547, dport=546) == "accept"
      and verdict(src=GLOBAL6, dst=RADAR_LL, proto="udp", sport=547, dport=546) == "accept",
      "DHCPv6 answers to the radar's link-local address")
check(verdict(src=GLOBAL6, dst=RADAR6, proto="udp", sport=547, dport=546) == "drop",
      "but not a packet for the DHCPv6 client port sent to the radar's global address")
check(verdict(src="fe80::9", dst="ff02::fb", proto="udp", sport=5353, dport=5353) == "accept"
      and verdict(src=GLOBAL6, dst="ff02::fb", proto="udp", sport=5353, dport=5353) == "accept",
      "Bonjour sent to its IPv6 multicast group, from any address on the link")
check(verdict(src=GLOBAL6, dst=RADAR6, proto="udp", sport=5353, dport=5353) == "drop", "but not mDNS sent straight to the radar from outside")

# ---- fails open ---------------------------------------------------------------
unit = (D / "stratoscan-filter.service").read_text()
check("ExecStart=/usr/sbin/nft -f /etc/stratoscan/filter.nft" in unit and "ExecStop=-/usr/sbin/nft delete table inet stratoscan_filter" in unit,
      "its unit loads the file, and stopping it takes only its own table away")
check("After=nftables.service" in unit and "PartOf=nftables.service" in unit,
      "it loads after Debian's nftables (whose config flushes everything) and again when that restarts")
check(not re.search(r"^(Requires|BindsTo|Before|RequiredBy|OnFailure)=", unit, re.M) and "WantedBy=multi-user.target" in unit,
      "it holds nothing else up, and nothing is asked of it but to be tried at boot")
for f in sorted(D.iterdir()):
    if f.suffix in (".service", ".timer", ".conf") and f.name != "stratoscan-filter.service":
        check("stratoscan-filter" not in f.read_text(), f"{f.name} does not depend on the filter")
ota = (D / "ota.py").read_text()
check("stratoscan-filter" not in ota and "filter-peers" not in ota, "an update cannot install or change it (unit files and /etc are the installer's)")

# ---- the installer -------------------------------------------------------------
inst = (D / "install-setup-server.sh").read_text()
check("install -m 0644 deploy/stratoscan-filter.nft /etc/stratoscan/filter.nft" in inst
      and "install -m 0644 deploy/stratoscan-filter.service /etc/systemd/system/" in inst, "the installer puts the file and its unit in place")
check("/etc/nftables.conf" not in inst.split("deploy/stratoscan-filter.nft")[1].split("echo \"== managed unit")[0]
      and "filter" not in inst.split('echo "== managed unit')[1].split('echo "== rollout ring ==')[0],
      "and leaves /etc/nftables.conf and the managed unit's rule to themselves")
on = inst.split("# The connection filter (SR-10), apart from the rest")[1].split('echo "  enabled; nothing started')[0]
on = "\n".join(l for l in on.splitlines() if not l.startswith("#"))
order = [on.find(s) for s in ('HOST_FILTER:-1', "! live", "nft -c -f /etc/stratoscan/filter.nft", "filter-peers.py",
                              "systemctl enable stratoscan-filter.service >/dev/null 2>&1 && systemctl restart stratoscan-filter.service")]
check(all(i >= 0 for i in order) and order == sorted(order),
      "it is switched on last: skipped on request, enabled only in an image build, else checked by nft, then against the open SSH sessions, then loaded")
check("exit 1" not in on and on.count("elif") == 4 and on.strip().endswith("if ! live; then"),
      "and no outcome there stops the install: the radar stays reachable as it was")
check("elif ! python3 deploy/filter-peers.py --file /etc/stratoscan/filter.nft; then" in on,
      "any answer but 'every session is let in' from filter-peers.py (refused, or could not tell) leaves the filter off")
for loop in re.findall(r"for u in ([^;]*); do\s*\n\s*(?:enable_unit|restart_unit|install -m 0644 \"deploy/\$u\")", inst):
    check("stratoscan-filter" not in loop, "it is not in a list of units the install fails over")
check(inst.count("nft -c -f /etc/stratoscan/filter.nft") == 1, "nft's check of it is only ever a condition, never a bare command under set -e")
build = (ROOT / "image" / "build.sh").read_text()
for f in ("/etc/stratoscan/filter.nft", "/etc/systemd/system/multi-user.target.wants/stratoscan-filter.service"):
    check(f in build.split("do must")[0], f"the factory image must have {f}")
check('cmp -s "$REPO/deploy/stratoscan-filter.nft" "$MNT/etc/stratoscan/filter.nft"' in build, "and the same file as this tree's")
nftcheck = re.search(r'\nfor f in ([^;]+); do\n  unshare -n chroot "\$MNT" /usr/sbin/nft -c -f "/etc/stratoscan/\$f\.nft" \\\n    \|\| \{ [^}]*fail=1; \}\ndone\n', build)
check(bool(nftcheck) and nftcheck.group(1).split() == ["filter", "https"],
      "the image build has nft itself check the filter and the https file, in a network namespace of its own, and an error fails the build")
check(bool(nftcheck) and build.index(nftcheck.group(0)) < build.index('[ "$fail" = 0 ] || { echo "IMAGE CHECKS FAILED"; exit 1; }'),
      "before the checks are counted")

# ---- will I still get in? -----------------------------------------------------
PEERS = D / "filter-peers.py"
peers = [sys.executable, str(PEERS)]


def said(*args, env=None):
    r = subprocess.run(peers + list(args), capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


rc, out = said("192.168.1.23", "10.42.0.17", PUBLIC4, "11.0.0.1", "100.100.1.2", "::ffff:192.168.1.23", "[::ffff:198.51.100.7]")
check(rc == 0 and out.count("let in") == 7 and "REFUSED" not in out,
      "filter-peers.py: an IPv4 address is always let in, private or public, also as ss prints one on an IPv6 socket")
rc, out = said("[fe80::1%wlan0]", "fd12::1", "fd7a:115c:a1e0::12")
check(rc == 0 and out.count("let in") == 3, "link-local and unique-local IPv6 addresses (a tailnet's among them) are let in")
rc, out = said("192.168.1.23", GLOBAL6, "fe80::9", "2001:db8:0:1::7")
check(rc == 1 and out.count("REFUSED") == 2 and out.count("let in") == 2, "a global IPv6 address is refused: it says so, and exits 1")
for a in ("192.168.1.23", "172.20.1.1", "11.0.0.1", PUBLIC4, "100.100.1.2", GLOBAL6, "fe80::9", "fd00::1", "fec0::1", "::1"):
    check((said(a)[0] == 0) == (verdict(src=a, dst=RADAR_LL if ":" in a else RADAR4, dport=22) == "accept"),
          f"it and the rules agree about {a}")
src = PEERS.read_text()
check("stratoscan-filter.nft" in src and "house6" in src and not re.search(r"fe80::/10|fc00::/7|192\.168\.0\.0", src),
      "it reads the addresses from the filter's own file, so the two cannot drift apart")
check(re.findall(r"subprocess\.run\(\[\"(\w+)\"", src) == ["ss"] and "open(path)" in src
      and not re.search(r"open\([^)]*[\"']w", src), "and it changes nothing: it only lists sockets")

# It fails closed: whenever it cannot tell, it says so and exits non-zero, and
# the installer (above) then leaves the filter off. `ss` is stood in for.
tmp = pathlib.Path(tempfile.mkdtemp())


def with_ss(script):
    d = pathlib.Path(tempfile.mkdtemp(dir=tmp))
    if script is not None:
        (d / "ss").write_text("#!/bin/sh\n" + script)
        (d / "ss").chmod(0o755)
    # only the stand-in's folder and python's own: no real ss can answer
    return dict(os.environ, PATH=f"{d}:/usr/bin:/bin" if script is not None else str(d))


def sessions(*lines):
    return "cat <<'EOF'\n" + "\n".join(lines) + "\nEOF\n"


rc, out = said(env=with_ss(sessions("0      0      192.168.1.50:22      192.168.1.23:51234",
                                    "0      0      [fe80::50%wlan0]:22  [fe80::1c2d:3e4f:5a6b:7c8d%wlan0]:51235",
                                    "0      0      [::ffff:203.0.113.50]:22 [::ffff:198.51.100.7]:40022")))
check(rc == 0 and out.count("let in") == 3, "open sessions from IPv4 (any address) and link-local IPv6: let in, exit 0")
rc, out = said(env=with_ss(sessions("0      0      192.168.1.50:22      192.168.1.23:51234",
                                    "0      0      [2001:db8::50]:22    [2001:db8::99]:51235")))
check(rc == 1 and "SSH from 2001:db8::99: REFUSED" in out, "an open session from a global IPv6 address: refused, exit 1")
rc, out = said(env=with_ss(sessions()))
check(rc == 0 and "no SSH sessions open" in out, "no session open (the installer run from first boot): exit 0")
for what, script in (("ss fails", "echo 'Cannot open netlink socket' >&2\nexit 1\n"),
                     ("there is no ss", None),
                     ("a session it cannot understand", sessions("0      0      192.168.1.50:22      192.168.1.23:51234",
                                                                 "0      0      192.168.1.50:22      something-else")),
                     ("a line that is not a session", sessions("Netid State Recv-Q Send-Q"))):
    rc, out = said(env=with_ss(script))
    check(rc not in (0, 1) and "CANNOT TELL" in out and "let in" not in out,
          f"{what}: it says it cannot tell and exits non-zero, with no session called let in")
good = with_ss(sessions("0      0      192.168.1.50:22      192.168.1.23:51234"))
for what, rules_text in (("no rules file", None),
                         ("rules that do not accept all of IPv4 first", text.replace("        meta nfproto ipv4 accept\n", "")),
                         ("rules with no house6 set", re.sub(r"    set house6 \{.*?\n    \}\n", "", text, flags=re.S)),
                         ("a house6 set it cannot read", text.replace("fe80::/10", "fe80::/200")),
                         ("an empty file", "")):
    f = tmp / "rules.nft"
    if rules_text is None:
        f = tmp / "not-there.nft"
    else:
        f.write_text(rules_text)
    rc, out = said("--file", str(f), env=good)
    check(rc not in (0, 1) and "CANNOT TELL" in out and "let in" not in out, f"{what}: it cannot tell, exits non-zero")
    rc, out = said("--file", str(f), "192.168.1.23")
    check(rc not in (0, 1), "and the same when asked about an address")
rc, out = said("not-an-address")
check(rc not in (0, 1) and "CANNOT TELL" in out, "something that is not an address: it cannot tell")
rc, out = said("--file", str(NFT), env=good)
check(rc == 0, "(with the shipped rules and that session it does tell: let in)")

# ---- nft itself, where there is one -------------------------------------------
if shutil.which("nft"):
    r = subprocess.run(["nft", "-c", "-f", str(NFT)], capture_output=True, text=True)
    if "Operation not permitted" in r.stderr:
        print("skip nft -c needs root here")
    else:
        check(r.returncode == 0, "nft accepts the file" + ("" if r.returncode == 0 else ": " + r.stderr.strip()[:200]))
else:
    print("skip no nft on this machine: the file's syntax is checked by nft on a radar and in the image build, not here")

print("host filter checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
