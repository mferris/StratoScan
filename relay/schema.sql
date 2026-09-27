-- FlightRadar relay: the only server the project runs. See docs/ROADMAP.md.
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
