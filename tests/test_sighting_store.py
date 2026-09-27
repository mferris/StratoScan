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
    check("a store predating day-of-week gets an empty week",
          repaired["dows"] == [0] * 7)
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
    check("the week histogram is reported", len(summary["dows"]) == 7)
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

    # ---- an increment lands in the right hour and weekday ----------------
    import time as _time
    with open(store_path, "w") as f:
        json.dump(m.fresh_store(), f)
    before = m.load_store()
    entry = before["ac"].setdefault("aaa111", {"t": 0, "n": 0})
    now = int(_time.time())
    local = _time.localtime(now)
    entry["t"] += 1
    before["hours"][local.tm_hour] += 1
    before["dows"][local.tm_wday] += 1
    check("an hour bucket moves", sum(before["hours"]) == 1)
    check("a weekday bucket moves", sum(before["dows"]) == 1)
    check("the weekday bucket is the local one",
          before["dows"][local.tm_wday] == 1)
    check("Monday is index 0 (ISO weekday)", _time.strptime("2026-09-07", "%Y-%m-%d").tm_wday == 0)

    # ---- eviction drops the least-recently-seen, not the first-seen -------
    # Insertion-order eviction used to throw out the daily regulars, because
    # they were inserted first and updating a key never moves it.
    store = m.fresh_store()
    store["ac"]["regular"] = {"t": 900, "f": 1, "l": 5000}   # seen first, seen today
    for i in range(m.MAX_HEXES + 5):
        store["ac"]["x%05d" % i] = {"t": 1, "f": 100 + i, "l": 100 + i}
    m.evict(store)
    check("eviction brings the store under the cap", len(store["ac"]) <= m.MAX_HEXES)
    check("eviction evicts in a chunk, not one at a time",
          len(store["ac"]) == m.EVICT_TO)
    check("a regular seen first but seen recently survives", "regular" in store["ac"])
    check("the stalest transit is evicted", "x00000" not in store["ac"])
    check("a recent transit survives", "x%05d" % (m.MAX_HEXES + 4) in store["ac"])

    store = m.fresh_store()
    store["ac"]["undated"] = {"t": 3}
    for i in range(m.MAX_HEXES):
        store["ac"]["y%05d" % i] = {"t": 1, "l": 100 + i}
    m.evict(store)
    check("an undated v1 entry goes before any dated one", "undated" not in store["ac"])

    # ---- writes are batched: a flush writes only when something changed --
    with open(store_path, "w") as f:
        json.dump(m.fresh_store(), f)
    m._store = None
    m._dirty = False
    with m.lock:
        live = m.current()
    before_mtime = os.stat(store_path).st_mtime_ns
    _time.sleep(0.01)
    m.flush()
    check("a clean store is not rewritten", os.stat(store_path).st_mtime_ns == before_mtime)

    with m.lock:
        live["ac"]["abc123"] = {"t": 7, "n": 1, "l": 1}
        m.mark_dirty()
    check("a change is not written until flushed",
          "abc123" not in m.load_store()["ac"])
    m.flush()
    check("a flush persists the change", m.load_store()["ac"]["abc123"]["t"] == 7)
    check("a flush clears the dirty flag", m._dirty is False)
    check("no temp file is left behind", not os.path.exists(store_path + ".tmp"))

    # ---- today's tally ----------------------------------------------------
    store = m.fresh_store()
    check("a store with no day yet reports zero today", m.summarise(store)["today"] == {"total": 0, "nearby": 0})
    store["day"] = {"d": _time.strftime("%Y-%m-%d"), "t": 12, "n": 3}
    check("today's tally is reported", m.summarise(store)["today"] == {"total": 12, "nearby": 3})
    store["day"] = {"d": "2000-01-01", "t": 99, "n": 9}
    check("yesterday's tally is not reported as today", m.summarise(store)["today"]["total"] == 0)

    # ---- year in review ----------------------------------------------------
    store = m.fresh_store()
    t_2026 = int(_time.mktime((2026, 3, 14, 9, 30, 0, 0, 0, -1)))
    e1 = {"t": 1, "n": 0, "k": "jet"}
    m.bump_year(store, e1, "total", t_2026, True)
    m.bump_year(store, e1, "total", t_2026 + 60, False)
    m.bump_year(store, e1, "nearby", t_2026 + 60, False)
    e2 = {"t": 1, "n": 0, "k": "heli"}
    m.bump_year(store, e2, "total", t_2026, True)
    store["ac"] = {"aaa111": e1, "bbb222": e2}
    y = store["years"]["2026"]
    check("year visits counted", y["t"] == 3)
    check("year nearby counted", y["n"] == 1)
    check("first-ever aircraft counted as new", y["new"] == 2)
    check("visits land in their month", y["months"][2] == 3)
    check("visits land in their hour", y["hours"][9] == 3)
    ys = m.year_summary(store, 2026)
    check("the year summary is ready", ys["ready"] is True)
    check("most-seen aircraft of the year comes first", ys["top"][0]["hex"] == "aaa111" and ys["top"][0]["visits"] == 2)
    check("aircraft seen this year are counted", ys["aircraft"] == 2)
    check("kinds are broken down", ys["kinds"] == {"jet": 1, "heli": 1})
    check("busiest month found", ys["busiestMonth"] == 2)
    t_2027 = int(_time.mktime((2027, 1, 2, 12, 0, 0, 0, 0, -1)))
    m.bump_year(store, e1, "total", t_2027, False)
    check("a new year starts the tail's count over", e1["y"] == [2027, 1])
    check("last year's aggregates survive", store["years"]["2026"]["t"] == 3)
    check("an unknown year is reported as not ready", m.year_summary(store, 2031)["ready"] is False)
    for yr in range(2030, 2030 + m.YEARS_KEPT + 3):
        m.bump_year(store, {}, "total", int(_time.mktime((yr, 6, 1, 12, 0, 0, 0, 0, -1))), False)
    check("only YEARS_KEPT years are kept", len(store["years"]) == m.YEARS_KEPT)

    # ---- upgrading a store that predates per-year counting -------------------
    now = int(_time.mktime((2026, 9, 27, 18, 0, 0, 0, 0, -1)))
    old = m.fresh_store()
    del old["years"]   # as written before per-year counting existed
    old["since"] = int(_time.mktime((2026, 9, 3, 12, 0, 0, 0, 0, -1)))
    old["hours"] = [1] * 24
    old["ac"] = {"aaa111": {"t": 40, "n": 3, "f": old["since"] + 10},
                 "bbb222": {"t": 2, "n": 0, "f": old["since"] + 99}, "ccc333": {"g": 5}}
    check("a pre-yearly store is seeded", m.seed_current_year(old, now) is True)
    y = old["years"]["2026"]
    check("this year's visits are the all-time visits", y["t"] == 42 and y["n"] == 3)
    check("a history all in this month lands in this month", y["months"][8] == 42 and sum(y["months"]) == 42)
    check("every tail gets its count for the year", old["ac"]["aaa111"]["y"] == [2026, 40])
    check("a network-only aircraft gets none", "y" not in old["ac"]["ccc333"])
    check("the seed happens once", m.seed_current_year(old, now) is False)
    summ = m.year_summary(old, 2026)
    check("the year says counting began when the store did", summ["countingSince"] == old["since"])
    older = m.fresh_store()
    del older["years"]
    older["since"] = int(_time.mktime((2025, 6, 1, 12, 0, 0, 0, 0, -1)))
    older["ac"] = {"aaa111": {"t": 9}}
    m.seed_current_year(older, now)
    check("history reaching into last year is not passed off as this year's", older["years"] == {})
    check("a brand-new store needs no seeding", m.seed_current_year(m.fresh_store(), now) is False)
    late = m.fresh_store()
    late["since"] = old["since"]
    late["ac"] = {"aaa111": {"t": 40, "n": 3, "f": old["since"] + 10, "y": [2026, 2]}}
    late["years"] = {"2026": {"t": 2, "n": 0, "new": 0, "months": [0] * 8 + [2] + [0] * 3,
                              "hours": [0] * 24, "since": now - 3600}}
    check("a year that started counting after the store is rebuilt", m.seed_current_year(late, now) is True)
    check("from the all-time totals, which already include the later visits",
          late["years"]["2026"]["t"] == 40 and late["ac"]["aaa111"]["y"] == [2026, 40])
    check("and only once", m.seed_current_year(late, now) is False)
    first_build = m.fresh_store()
    first_build["since"] = old["since"]
    first_build["ac"] = {"aaa111": {"t": 40, "n": 3, "f": old["since"] + 10}}
    first_build["years"] = {"2026": {"t": 2, "n": 0, "new": 0, "months": [0] * 12, "hours": [0] * 24}}
    check("a year from the first build (no start time) is rebuilt too",
          m.seed_current_year(first_build, now) is True and first_build["years"]["2026"]["t"] == 40)

print(f"{checks - len(failures)}/{checks} sighting store checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)
