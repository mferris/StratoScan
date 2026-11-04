-- Relay hardening (security review 2026-11-03: SR-03, SR-04, SR-05, SR-17,
-- SR-22). Run ONCE on a database made from an older schema.sql, before
-- deploying the Worker that uses it:
--
--   npx wrangler d1 execute stratoscan-relay --remote --file=migrations/2026-11-04-relay-harden.sql
--
-- If the login may not use --file (as the fleet tables found, README), run
-- each statement below in order with --command="...".
--
-- Additive only: two new columns with defaults and five indexes. No row is
-- changed except to fill units.reports from the history already kept, so
-- every unit that has been reporting stays a member of the shared network
-- cache at once. A fresh database needs none of this: schema.sql has it all.
-- ALTER TABLE ... ADD COLUMN is not repeatable; a second run fails on the
-- first line with "duplicate column name" and changes nothing.

ALTER TABLE units ADD COLUMN reports INTEGER NOT NULL DEFAULT 0;
ALTER TABLE pairing_offers ADD COLUMN net TEXT;

-- Each unit has sent at least as many reports as it has kept, and an
-- established unit (a week or more) is given the cache's minimum outright.
UPDATE units SET reports = MAX(
  (SELECT COUNT(*) FROM heartbeats h WHERE h.unit = units.id),
  CASE WHEN first_seen <= CAST(strftime('%s', 'now') AS INTEGER) - 7 * 86400 THEN 4 ELSE 0 END
);

CREATE INDEX IF NOT EXISTS units_last_seen ON units (last_seen);
CREATE INDEX IF NOT EXISTS pairing_offers_net ON pairing_offers (net);
CREATE INDEX IF NOT EXISTS pairing_offers_expires ON pairing_offers (expires);
CREATE INDEX IF NOT EXISTS events_received ON events (received);
CREATE INDEX IF NOT EXISTS heartbeats_ts ON heartbeats (ts);
