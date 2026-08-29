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
    "/sightings", "/approaches", "/config.json",
    "/tar1090/data/receiver.json", "/my/wake/board",
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

    for f in failures:
        print("FAIL:", f)
    total = len(MUST_BLOCK) + len(MUST_ALLOW)
    print(f"{total - len(failures)}/{total} path checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
