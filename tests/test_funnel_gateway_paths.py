#!/usr/bin/env python3
"""Regression test for the Funnel gateway's local-only path filter.

This exists because the original filter compared the RAW request path, and
three bypasses were live-exploitable against the deployed device: /./wake,
/x/../wake and /%77ake all returned 204 (the endpoint powering on the
display) instead of 404, reachable by anyone holding the public Funnel URL.

lighttpd percent-decodes and collapses traversal before routing, so the
gateway must normalise to the same form the upstream will act on BEFORE
deciding. Run: python3 tests/test_funnel_gateway_paths.py
"""
import importlib.util
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fg", root / "deploy" / "funnel-gateway.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)
is_local_only = fg.Handler._is_local_only

MUST_BLOCK = [
    "/wake", "/wake/", "//wake", "///wake", "/./wake", "/.//wake",
    "/x/../wake", "/a/b/../../wake", "/%77ake", "/%2577ake",
    "/WAKE", "/Wake", "/wake?x=1", "/wake#frag", "/wake/now",
    "/setup", "/setup/", "//setup", "/./setup", "/%73etup",
    "/setup/api/wifi", "/SETUP", "/setup?x=1", "/x/../setup",
]

# Paths that merely start with the same letters must NOT be caught.
MUST_ALLOW = [
    "/", "/index.html", "/wakeup", "/wake-up", "/awake", "/setupx",
    "/sightings", "/approaches", "/network", "/network/stats", "/config.json",
    "/sightings/stats", "/sightings/unclassified",
    "/tar1090/data/receiver.json", "/my/wake/board",
]

# Paths that may be READ publicly but must never be WRITTEN publicly. The
# stores accept unauthenticated POSTs, and /network makes an outbound call
# on this device's behalf, so a public write path would let a stranger both
# pollute months of data and drive traffic at a community-run API.
MUST_BE_READ_ONLY = [
    "/sightings", "/approaches", "/network",
    # The statistics endpoints hang off /sightings, and the batched write
    # added for the classification backfill lands on /sightings itself -- a
    # public POST there could rewrite the classification of every aircraft
    # in months of history in one request.
    "/sightings/stats", "/sightings/unclassified",
]


def main():
    failures = []
    for p in MUST_BLOCK:
        if not is_local_only(p):
            failures.append(f"NOT BLOCKED (public bypass): {p!r}")
    for p in MUST_ALLOW:
        if is_local_only(p):
            failures.append(f"wrongly blocked (app breakage): {p!r}")

    # the deny list itself must not be silently emptied by a future edit
    for required in ("/wake", "/setup"):
        if required not in fg.LOCAL_ONLY_PATHS:
            failures.append(f"{required} missing from LOCAL_ONLY_PATHS")

    # Asserts the behaviour, not the literal list: a sub-path like
    # /sightings/stats is covered by its parent's prefix rule and is never
    # going to appear in READ_ONLY_PUBLIC_PATHS by name. What matters is that
    # a public write to it is refused.
    for required in MUST_BE_READ_ONLY:
        if not fg.Handler._is_read_only_public(required):
            failures.append(f"{required} is not treated as read-only "
                            "(public traffic could WRITE to it)")

    for f in failures:
        print("FAIL:", f)
    total = len(MUST_BLOCK) + len(MUST_ALLOW) + len(MUST_BE_READ_ONLY)
    print(f"{total - len(failures)}/{total} path checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
