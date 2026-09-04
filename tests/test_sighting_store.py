#!/usr/bin/env python3
"""
Checks for deploy/sighting-store.py.

This file guards accumulated history that cannot be regenerated: a unit that
has been running for months has a sightings.json nobody can rebuild, and the
v1 -> v2 migration is the one code path that could quietly throw it away. It
also pins the legacy GET shape, because an older cached page still reads it.

Run: python3 tests/test_sighting_store.py
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "deploy", "sighting-store.py")

failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def load_module(state_dir):
    os.environ["STATE_DIRECTORY"] = state_dir
    spec = importlib.util.spec_from_file_location("sighting_store", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


with tempfile.TemporaryDirectory() as tmp:
    store_path = os.path.join(tmp, "sightings.json")

    # ---- v1 history survives the migration -------------------------------
    legacy = {
        "a145b7": {"total": 11, "nearby": 2},
        "abc123": {"total": 3, "nearby": 0},
        "NOTAHEX": {"total": 99, "nearby": 99},   # junk that v1 could contain
    }
    with open(store_path, "w") as f:
        json.dump(legacy, f)

    m = load_module(tmp)
    s = m.load_store()
    check("migration keeps the version", s["v"] == 2)
    check("migration keeps totals", s["ac"]["a145b7"]["t"] == 11)
    check("migration keeps nearby", s["ac"]["a145b7"]["n"] == 2)
    check("migration keeps every real aircraft", len(s["ac"]) == 2)
    check("migration drops a non-ICAO key", "NOTAHEX" not in s["ac"])

    # the legacy view is what an older page still reads
    view = m.legacy_view(s)
    check("legacy view keeps its shape", view["a145b7"] == {"total": 11, "nearby": 2})

    # ---- migrating twice must not double or reset anything ---------------
    m.save_store(s)
    again = m.load_store()
    check("re-loading a v2 store is stable", again["ac"]["a145b7"]["t"] == 11)
    check("re-loading keeps the hour histogram sized", len(again["hours"]) == 24)

    # ---- a corrupt file starts clean rather than crashing -----------------
    with open(store_path, "w") as f:
        f.write("{not json")
    check("corrupt store falls back to empty", m.load_store()["ac"] == {})

    # a v2 file with a mangled interior must not take the service down
    with open(store_path, "w") as f:
        json.dump({"v": 2, "ac": {"a145b7": {"t": 4}}, "hours": "nope"}, f)
    repaired = m.load_store()
    check("mangled hours are repaired", len(repaired["hours"]) == 24)
    check("mangled file keeps its counts", repaired["ac"]["a145b7"]["t"] == 4)

    # ---- classification is a closed set ----------------------------------
    entry = {}
    m.apply_class(entry, {"op": "com", "k": "jet", "cs": "dal1234"})
    check("a valid class is stored", entry == {"op": "com", "k": "jet", "cs": "DAL1234"})

    entry = {}
    m.apply_class(entry, {"op": "<script>", "k": "spaceship", "cs": "<b>x</b>"})
    check("an unknown operator is dropped", "op" not in entry)
    check("an unknown kind is dropped", "k" not in entry)
    check("a callsign with markup is dropped", "cs" not in entry)

    entry = {}
    m.apply_class(entry, {"cs": "N61LH"})
    check("a registration is a valid callsign", entry.get("cs") == "N61LH")

    # ---- records are compare-and-keep, and bounded ------------------------
    store = m.fresh_store()
    m.apply_records(store, "a145b7", {"cs": "AAA1"}, {"far": 120.0})
    check("a first record is kept", store["rec"]["far"]["v"] == 120.0)

    m.apply_records(store, "bbb222", {"cs": "BBB2"}, {"far": 90.0})
    check("a weaker distance does not displace it", store["rec"]["far"]["hex"] == "a145b7")

    m.apply_records(store, "bbb222", {"cs": "BBB2"}, {"far": 150.0})
    check("a stronger distance takes over", store["rec"]["far"]["hex"] == "bbb222")

    # "near" is the one where smaller wins
    m.apply_records(store, "a145b7", {}, {"near": 3.0})
    m.apply_records(store, "bbb222", {}, {"near": 8.0})
    check("a farther closest-approach is ignored", store["rec"]["near"]["v"] == 3.0)
    m.apply_records(store, "ccc333", {}, {"near": 0.4})
    check("a nearer closest-approach wins", store["rec"]["near"]["v"] == 0.4)

    # a single bad sample must not set a permanent record
    m.apply_records(store, "ddd444", {}, {"high": 300000, "fast": 4000})
    check("an impossible altitude is refused", "high" not in store["rec"])
    check("an impossible speed is refused", "fast" not in store["rec"])
    m.apply_records(store, "ddd444", {}, {"high": 41000, "fast": 520})
    check("a plausible altitude is kept", store["rec"]["high"]["v"] == 41000)

    m.apply_records(store, "eee555", {}, {"far": "150", "high": True})
    check("a string is not a record", store["rec"]["far"]["hex"] == "bbb222")
    check("a boolean is not an altitude", store["rec"]["high"]["hex"] == "ddd444")

    # ---- the summary separates heard from network-only --------------------
    store = m.fresh_store()
    store["ac"] = {
        "aaa111": {"t": 5, "n": 2, "op": "com", "k": "jet", "cs": "DAL1"},
        "bbb222": {"t": 3, "n": 0, "op": "pri", "k": "heli"},
        "ccc333": {"t": 1, "n": 1, "op": "mil", "k": "prop"},
        "ddd444": {"g": 4},                       # never once heard here
        "eee555": {"t": 2, "g": 1, "op": "com", "k": "jet"},
    }
    summary = m.summarise(store)
    check("distinct aircraft counted", summary["aircraft"] == 5)
    check("aircraft actually heard counted", summary["heard"] == 4)
    check("network-only aircraft counted", summary["networkOnly"] == 1)
    check("network visits summed", summary["networkVisits"] == 5)
    check("visits summed", summary["visits"] == 11)
    check("nearby summed", summary["nearby"] == 3)
    check("commercial aircraft grouped", summary["byOp"]["com"]["ac"] == 2)
    check("commercial visits grouped", summary["byOp"]["com"]["visits"] == 7)
    check("military nearby grouped", summary["byOp"]["mil"]["nearby"] == 1)
    check("an unclassified aircraft lands in unk", summary["byOp"]["unk"]["ac"] == 1)
    check("helicopters grouped", summary["byKind"]["heli"]["ac"] == 1)
    check("an unclassified airframe is unknown", summary["byKind"]["unknown"]["ac"] == 1)
    check("the top list is ordered", summary["top"][0]["hex"] == "aaa111")
    check("the top list excludes never-heard aircraft",
          all(r["hex"] != "ddd444" for r in summary["top"]))
    check("days is at least one", summary["days"] >= 1)
    check("undated aircraft are counted", summary["undated"] == 5)

    # ---- a migrated store must not claim its history started today -------
    with open(store_path, "w") as f:
        json.dump({"a145b7": {"total": 400, "nearby": 9}}, f)
    migrated = m.load_store()
    check("a migrated store has no start date", migrated["since"] is None)
    check("a migrated store reports no day count",
          m.summarise(migrated)["days"] is None)
    check("a migrated store reports its undated backlog",
          m.summarise(migrated)["undated"] == 1)
    check("a fresh store does have a start date", m.fresh_store()["since"] is not None)

    # ---- batched backfill ------------------------------------------------
    # The batch exists to fill in history that predates classification, so the
    # rule that matters is that it never invents a sighting.
    with open(store_path, "w") as f:
        json.dump({"v": 2, "ac": {"aaa111": {"t": 4}, "bbb222": {"t": 1}},
                   "hours": [0] * 24, "rec": {}, "since": 1700000000}, f)
    store = m.load_store()
    unclassified = [h for h, e in store["ac"].items() if not e.get("k")]
    check("both aircraft need classifying", set(unclassified) == {"aaa111", "bbb222"})

    m.apply_class(store["ac"]["aaa111"], {"k": "heli"})
    still = [h for h, e in store["ac"].items() if not e.get("k")]
    check("a classified aircraft leaves the list", still == ["bbb222"])

print(f"{checks - len(failures)}/{checks} sighting store checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
