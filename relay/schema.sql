-- StratoScan relay: the only server the project runs. See docs/ROADMAP.md.
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

-- Pairing (roadmap 2.3). A unit's screen shows a QR code holding its id and
-- a one-time secret; the unit registers only the secret's SHA-256 here. A
-- phone that presents the secret within PAIRING_TTL_S is linked to the unit.
CREATE TABLE IF NOT EXISTS pairing_offers (
  unit         TEXT PRIMARY KEY,
  secret_hash  TEXT NOT NULL,       -- hex sha256 of the secret; the secret itself never reaches the relay until a phone uses it
  expires      INTEGER NOT NULL,
  attempts     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pairings (
  unit     TEXT NOT NULL,
  phone    TEXT NOT NULL,           -- base64url Ed25519 public key; the phone's identity
  name     TEXT,                    -- what the phone calls itself ("Alex's iPhone")
  created  INTEGER NOT NULL,
  PRIMARY KEY (unit, phone)
);
CREATE INDEX IF NOT EXISTS pairings_phone ON pairings (phone);

-- Push (roadmap 2.1): where each phone receives notifications, and what it
-- wants. A token is only an address for Apple's push service; it is not
-- tied to the phone's identity key and says nothing about its owner.
CREATE TABLE IF NOT EXISTS phones (
  id            TEXT PRIMARY KEY,   -- same id as pairings.phone
  token         TEXT,               -- APNs device token (hex); NULL once Apple says it is dead
  env           TEXT NOT NULL,      -- 'sandbox' (development builds) or 'production'
  kinds         TEXT NOT NULL,      -- JSON array of event kinds this phone wants
  updated       INTEGER NOT NULL,
  window_start  INTEGER NOT NULL DEFAULT 0,   -- per-phone push rate limit
  window_count  INTEGER NOT NULL DEFAULT 0
);

-- Live Activities (roadmap 2.4): a card on the phone's lock screen for an
-- aircraft about to pass over. A phone's push-to-start token lets the relay
-- start one; each running activity then has its own token, used to end it.
CREATE TABLE IF NOT EXISTS live_activity_phones (
  phone        TEXT PRIMARY KEY,
  start_token  TEXT NOT NULL,        -- APNs push-to-start token (hex)
  updated      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS live_activities (
  phone    TEXT NOT NULL,
  unit     TEXT NOT NULL,
  hex      TEXT NOT NULL,            -- the aircraft
  token    TEXT NOT NULL,            -- this activity's update token (hex)
  created  INTEGER NOT NULL,
  PRIMARY KEY (phone, hex)
);

-- An approach can end before the phone has reported its Live Activity's
-- token (the phone reports it within about a minute of the start). The end
-- is kept here briefly and sent the moment the token arrives.
CREATE TABLE IF NOT EXISTS live_activity_ends (
  phone  TEXT NOT NULL,
  hex    TEXT NOT NULL,
  at     INTEGER NOT NULL,
  PRIMARY KEY (phone, hex)
);

-- Alerts for aircraft approaching where a phone is (roadmap 2.7). The phone's
-- location is end-to-end encrypted to the one radar that runs the prediction:
-- this relay stores and forwards it, and can never read it.
--
-- Each radar's X25519 "box" key, which phones encrypt to, signed by the
-- radar's Ed25519 identity. A phone checks that signature against the radar
-- id it scanned when pairing, so this relay can't hand it a key of its own.
CREATE TABLE IF NOT EXISTS unit_box_keys (
  unit     TEXT PRIMARY KEY,
  key      TEXT NOT NULL,          -- base64url X25519 public key
  sig      TEXT NOT NULL,          -- base64url Ed25519 signature by the unit
  updated  INTEGER NOT NULL
);

-- A phone's latest location for one radar: an opaque, encrypted blob. Kept
-- only LOCATION_TTL_S, and gone when the pairing is.
CREATE TABLE IF NOT EXISTS phone_locations (
  phone    TEXT NOT NULL,
  unit     TEXT NOT NULL,
  blob     TEXT NOT NULL,          -- base64url: ephemeral X25519 key, nonce, ChaCha20-Poly1305 ciphertext
  updated  INTEGER NOT NULL,
  PRIMARY KEY (phone, unit)
);

-- Fleets (roadmap 1.13): groups of radars with their own administrators. A
-- radar joins only when its owner enters the fleet's invite code, and can
-- leave at any time. Only fingerprints of the invite code and of each
-- administrator's sign-in link are stored; both are shown once when made.
CREATE TABLE IF NOT EXISTS fleets (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  invite_hash  TEXT NOT NULL,   -- SHA-256 of the normalised invite code
  created      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS fleets_invite ON fleets (invite_hash);

CREATE TABLE IF NOT EXISTS fleet_admins (
  fleet       TEXT NOT NULL,
  label       TEXT,
  token_hash  TEXT NOT NULL UNIQUE,   -- SHA-256 of the administrator's link token
  created     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fleet_members (
  unit    TEXT PRIMARY KEY,   -- a radar is in at most one fleet
  fleet   TEXT NOT NULL,
  joined  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS fleet_members_fleet ON fleet_members (fleet);
