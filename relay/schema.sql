-- Radome relay: the only server the project runs. See docs/ROADMAP.md.
-- Nothing here identifies where a unit is: units never send a location.

CREATE TABLE IF NOT EXISTS units (
  id          TEXT PRIMARY KEY,   -- base64url Ed25519 public key; the unit's identity
  name        TEXT,               -- set by the maintainer on the fleet page
  first_seen  INTEGER NOT NULL,   -- unix seconds
  last_seen   INTEGER NOT NULL,
  last_ts     INTEGER NOT NULL,   -- last accepted signed timestamp (replay guard)
  version     TEXT,
  payload     TEXT                -- latest heartbeat body, JSON
);

CREATE TABLE IF NOT EXISTS heartbeats (
  unit     TEXT NOT NULL,
  ts       INTEGER NOT NULL,
  payload  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS heartbeats_unit_ts ON heartbeats (unit, ts);

-- Unit events (roadmap 2.2): moments a unit decided are worth telling its
-- paired phones about. Kept only long enough to deliver (EVENT_RETENTION_S):
-- an event says, roughly, where a unit is to anyone who reads it.
CREATE TABLE IF NOT EXISTS event_senders (
  unit          TEXT PRIMARY KEY,   -- same id as units.id; a unit may send events without health reports
  last_ts       INTEGER NOT NULL,   -- last accepted signed timestamp (replay guard)
  window_start  INTEGER NOT NULL,   -- rate-limit window
  window_count  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  unit      TEXT NOT NULL,
  ts        INTEGER NOT NULL,       -- when the unit saw it
  received  INTEGER NOT NULL,       -- when the relay accepted it
  kind      TEXT NOT NULL,
  payload   TEXT NOT NULL           -- the validated event, JSON
);
CREATE INDEX IF NOT EXISTS events_unit_received ON events (unit, received);
