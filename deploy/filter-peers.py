#!/usr/bin/env python3
"""Would the radar's connection filter let these addresses in?

deploy/stratoscan-filter.nft refuses new IPv6 connections to the radar from
anywhere but the house and the tailnet, and leaves IPv4 alone (security
review 2026-11-03, SR-10; IPv6-only since 2026-11-15). The one way into a
radar with no keyboard is SSH from the home network, so before the filter is
switched on, this says whether the SSH sessions open right now come from
addresses it lets in. Run from one of those sessions, that answers "will I
still get in" before anything changes. It reads the rules out of the
filter's own file, so the two cannot disagree, and changes nothing.

An IPv4 address is always let in: the filter accepts all of IPv4. An IPv6
address is let in when it is link-local or unique-local (the file's house6
set; a tailnet's IPv6 addresses are unique-local too).

Usage:  filter-peers.py [--file FILTER.nft]             the SSH sessions open now
        filter-peers.py [--file FILTER.nft] ADDRESS...  these addresses

Exit 0: every one is let in (or there are no sessions).
Exit 1: at least one would be refused, each named on its own line.
Exit 2: it could not tell: the rules could not be read, the sessions could
        not be listed, or one of them could not be understood. It says which.
The installer switches the filter on only after exit 0: when this cannot
tell, the radar stays as reachable as it was.
"""
import ipaddress
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALL_IPV4 = "meta nfproto ipv4 accept"


class CannotTell(Exception):
    pass


def house_networks(path):
    """The IPv6 networks the filter's house6 set holds. CannotTell unless the
    file is the filter this program knows: all of IPv4 accepted by its first
    rule, and a house6 set of IPv6 networks."""
    try:
        with open(path) as f:
            text = "\n".join(line for line in f if not line.lstrip().startswith("#"))
    except OSError as e:
        raise CannotTell(f"could not read the filter's rules ({path}): {e.strerror}")
    rules = re.search(r"policy accept;\s*\n\s*([^\n]*)", text)
    if not rules or rules.group(1).strip() != ALL_IPV4:
        raise CannotTell(f"{path} does not start by accepting all of IPv4; these are not rules this check knows")
    sets = re.findall(r"set house6\s*\{.*?elements\s*=\s*\{([^}]*)\}", text, re.S)
    try:
        nets = [ipaddress.ip_network(tok.strip()) for body in sets for tok in body.split(",") if tok.strip()]
    except ValueError as e:
        raise CannotTell(f"could not read the house6 addresses in {path}: {e}")
    if not nets or any(n.version != 6 for n in nets):
        raise CannotTell(f"no house6 set of IPv6 addresses in {path}")
    return nets


def address(text):
    """An address as ss prints a peer: 192.168.1.23, [fe80::1%wlan0],
    [::ffff:192.168.1.23] (IPv4 arriving on an IPv6 socket: IPv4)."""
    a = ipaddress.ip_address(text.strip().strip("[]").split("%")[0])
    return a.ipv4_mapped or a if a.version == 6 else a


def let_in(addr, nets):
    return addr.version == 4 or any(addr in n for n in nets)


def ssh_peers():
    """The far end of each SSH connection open to this radar now."""
    try:
        p = subprocess.run(["ss", "-Htn", "state", "established", "( sport = :22 )"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        raise CannotTell(f"could not list the open SSH sessions (ss): {e}")
    if p.returncode != 0:
        raise CannotTell("could not list the open SSH sessions (ss): " + (p.stderr.strip()[-200:] or f"exit {p.returncode}"))
    peers = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        try:
            peers.append(address(line.split()[-1].rsplit(":", 1)[0]))
        except (ValueError, IndexError):
            raise CannotTell(f"could not understand this SSH session as ss lists it: {line.strip()!r}")
    return peers


def main(argv):
    args = argv[1:]
    path = os.path.join(HERE, "stratoscan-filter.nft")
    if args[:1] == ["--file"] and len(args) >= 2:
        path, args = args[1], args[2:]
    try:
        nets = house_networks(path)
        if args:
            try:
                peers = [(a, address(a)) for a in args]
            except ValueError as e:
                raise CannotTell(f"not an address: {e}")
        else:
            peers = [(f"SSH from {p}", p) for p in ssh_peers()]
    except CannotTell as e:
        print(f"CANNOT TELL: {e}. Nothing was checked, so the filter should stay as it is")
        return 2
    refused = 0
    for label, addr in peers:
        if let_in(addr, nets):
            print(f"{label}: let in" + (" (IPv4 is not filtered)" if addr.version == 4 else ""))
        else:
            print(f"{label}: REFUSED. The filter would turn new connections from this IPv6 address away")
            refused += 1
    if not peers:
        print("no SSH sessions open")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
