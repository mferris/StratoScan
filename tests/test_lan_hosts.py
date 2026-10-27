#!/usr/bin/env python3
"""The radar answers only to its own names (security review 2026-10-26).

A web page elsewhere, opened by a browser at home, must not be able to reach
the radar under a name of its own and read what the radar shows only at home.
deploy/84-stratoscan-hosts.conf sends every other name to the setup page on
the hotspot instead -- which is also what the hotspot's captive portal needs
-- and the two stores check the same names. These checks run the conf's own
pattern against the names the radar really is reached by (the kiosk, the
gateway, the app, Bonjour, the tailnet, the hotspot) and against others.

And the stores' private-address rule (92-stratoscan-managed-writes.conf) is
installed on every unit, not only managed ones.

Run: python3 tests/test_lan_hosts.py
"""
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


def text(path):
    try:
        return path.read_text()
    except OSError:
        return ""


conf = text(D / "84-stratoscan-hosts.conf")
m = re.search(r'^\$HTTP\["host"\] !~ "([^"]+)" \{\n(.*?)^\}', conf, re.M | re.S)
check(m is not None, "84-stratoscan-hosts.conf has one $HTTP[\"host\"] !~ block")
pattern = m.group(1) if m else "(?!)"
block = m.group(2) if m else ""
# lighttpd's PCRE and Python agree on everything this pattern uses; fullmatch
# because lighttpd's search is anchored by the pattern's own ^ and $.
answered = re.compile(pattern)


def answers(host):
    return answered.fullmatch(host) is not None


def host_of(url):
    return urllib.parse.urlsplit(url).netloc


# ---- the names the radar is reached by ------------------------------------------
own = {
    "no Host at all (HTTP/1.0 tools)": "",
    "the kiosk": host_of(re.search(r'"(http://localhost/[^"]*)"', text(D / "stratoscan-kiosk.service")).group(1)),
    "the public gateway's upstream": host_of(re.search(r'^UPSTREAM = "([^"]+)"', text(D / "funnel-gateway.py"), re.M).group(1)),
    "the updater's wake call": host_of(re.search(r'"STRATOSCAN_WAKE_URL", "([^"]+)"', text(D / "ota.py")).group(1)),
    "the app's factory default": host_of(re.search(r'defaultBaseURL = "([^"]+)"',
                                                   text(ROOT / "ios" / "Shared" / "APIConfig.swift")).group(1)),
    "the hotspot address (the captive redirect's target)": "10.42.0.1",
    "a LAN address": "192.168.1.23",
    "a LAN address, https on 4443": "192.168.1.23:4443",
    "loopback with its port": "127.0.0.1:80",
    "IPv6 loopback": "[::1]",
    "IPv6 link-local": "[fe80::1c2b:3cff:fe4d:5e6f]",
    "the tailnet address": "100.101.102.103",
    "a Bonjour name": "stratoscan-rdu.local",
    "a Bonjour name, any case, trailing dot": "StratoScan-RDU.LOCAL.",
    "the tailnet name": "stratoscan-rdu.example-tailnet.ts.net",
    "MagicDNS's short name, or a router's bare name": "stratoscan-rdu",
    "a router's name under home.arpa": "stratoscan-rdu.home.arpa",
    "a router's name under lan": "stratoscan-rdu.lan",
    "localhost with a port": "localhost:8080",
}
for what, host in own.items():
    check(answers(host), "answered: %s (%r)" % (what, host))

# ---- names a page elsewhere could have -------------------------------------------
foreign = ["attacker.example", "rebind.attacker.example", "192.168.1.23.attacker.example",
           "localhost.attacker.example", "stratoscan.local.attacker.example", "ts.net.attacker.example",
           "stratoscan.lan.attacker.example", "192.168.1.23.nip.io", "example.com:80", "ts.net",
           "captive.apple.com", "connectivitycheck.gstatic.com", "www.msftconnecttest.com",
           "detectportal.firefox.com", "x.y.z.example",
           # A FRITZ!Box's names, but .box is a public top-level domain and
           # fritz.box a registered name in it, so anyone could have one.
           "stratoscan-rdu.fritz.box", "fritz.box"]
for host in foreign:
    check(not answers(host), "not answered: %r" % host)

# ---- what a name it does not answer to gets --------------------------------------
captive = text(D / "99-stratoscan-captive.conf")
target = re.search(r'url\.redirect = \( "" => "([^"]+)" \)', captive)
check(target is not None and 'url.redirect = ( "" => "%s" )' % target.group(1) in block
      and "url.redirect-code = 302" in block,
      "any other name is redirected to the captive portal's own setup page")
check(target is not None and answers(host_of(target.group(1))),
      "and the page it is sent to is answered (no redirect loop)")
check("url.access-deny" not in block and "proxy.server" not in block,
      "nothing else: a redirect, so a phone checking for a sign-in page by name still gets one")

# ---- the stores check the same names -----------------------------------------------
for store in ("sighting-store.py", "approach-store.py"):
    sm = re.search(r'^RADAR_HOST_RE = re\.compile\(r"([^"]+)"\)', text(D / store), re.M)
    check(sm is not None and sm.group(1) == pattern, "%s checks the same names as lighttpd" % store)

# ---- installed, on every unit ----------------------------------------------------
inst = text(D / "install-setup-server.sh")
loop = re.search(r"^for c in (.*?); do\n  lighttpd_conf \"\$c\"\ndone", inst, re.M | re.S)
confs = loop.group(1).replace("\\\n", " ").split() if loop else []
for c in ("84-stratoscan-hosts.conf", "88-stratoscan-tar1090.conf", "92-stratoscan-managed-writes.conf"):
    check(c in confs, "the installer enables %s on every unit" % c)
managed = inst.split('if [ "${MANAGED:-0}" = "1" ]; then', 1)[-1].split("\nfi\n\n", 1)[0]
check("92-stratoscan-managed-writes.conf" not in managed,
      "the stores' private-address rule is no longer only for MANAGED=1")
check("answers example.com / 302" in inst and "answers 127.0.0.1 / 200" in inst,
      "the installer checks the running lighttpd answers its own name and redirects another")
check("writes http://10.42.0.1 400" in inst and "writes https://example.com 403" in inst,
      "and that the stores, through lighttpd, take the radar's own page and refuse another site's")

# ---- the private-address rule ----------------------------------------------------
writes = text(D / "92-stratoscan-managed-writes.conf")
rm = re.search(r'\$HTTP\["remoteip"\] !~ "([^"]+)"', writes)
private = re.compile(rm.group(1) if rm else "(?!)")
for ip in ("127.0.0.1", "::1", "10.42.0.17", "192.168.1.23", "172.16.4.5", "100.101.102.103",
           "fd7a:115c:a1e0::1", "fe80::1c2b:3cff:fe4d:5e6f", "fd12:3456:789a::1"):
    check(private.match(ip) is not None, "a write from %s (private) is taken" % ip)
for ip in ("203.0.113.5", "8.8.8.8", "172.32.0.1", "100.128.0.1", "2001:db8::1", "2001:db8:1::5"):
    check(private.match(ip) is None, "a write from %s (routed) is refused" % ip)

print("lan host checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
