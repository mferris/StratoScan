// The daily cleanup (security review 2026-11-03, SR-05 and SR-22), run by
// the Worker's cron trigger (wrangler.example.toml, [triggers]).
//
// Most of these are also pruned as requests arrive, but only for whoever
// sends one: the alerts of a radar that stopped reporting, or the replay
// records of a quiet day, stayed until something else touched them, and
// privacy.md promises how long each is kept. This keeps every promise
// whether or not anyone is sending anything, and forgets keys that made
// first contact and then went silent.
//
// What it never touches: a named radar, a radar in a fleet, fleets
// themselves, and a pairing either side has used in PAIRING_IDLE_S. A
// pairing neither side has shown any sign of in that long -- no report, no
// box key (a running, paired radar republishes it daily), no alert, no
// registration or location from the phone -- is forgotten, so keys minted
// in pairs no longer keep each other forever (the 2026-11-04 re-review).
// A box key is forgotten once its radar has neither a report nor a pairing
// and hasn't republished it in a month (a radar republishes it daily).
import {
  ACTIVE_UNIT_S, HEARTBEAT_RETENTION_S, EVENT_RETENTION_S, LOCATION_TTL_S, PAIRING_IDLE_S,
} from './limits.js';
import { budgetDay } from './budget.js';

export function cleanupStatements(db, now) {
  return [
    db.prepare('DELETE FROM replay_guard WHERE expires < ?').bind(now),
    db.prepare('DELETE FROM pairing_offers WHERE expires <= ?').bind(now),
    db.prepare('DELETE FROM events WHERE received < ?').bind(now - EVENT_RETENTION_S),
    db.prepare('DELETE FROM heartbeats WHERE ts < ?').bind(now - HEARTBEAT_RETENTION_S),
    db.prepare('DELETE FROM write_budget WHERE day < ?').bind(budgetDay(now)),
    // Pairings neither side has used in PAIRING_IDLE_S (before the units
    // below, which a pairing keeps).
    db.prepare(
      `DELETE FROM pairings WHERE created < ?1
         AND NOT EXISTS (SELECT 1 FROM units u WHERE u.id = pairings.unit AND u.last_seen >= ?1)
         AND NOT EXISTS (SELECT 1 FROM unit_box_keys k WHERE k.unit = pairings.unit AND k.updated >= ?1)
         AND NOT EXISTS (SELECT 1 FROM event_senders s WHERE s.unit = pairings.unit AND s.last_ts >= ?1)
         AND NOT EXISTS (SELECT 1 FROM phones p WHERE p.id = pairings.phone AND p.updated >= ?1)
         AND NOT EXISTS (SELECT 1 FROM phone_locations l WHERE l.phone = pairings.phone AND l.updated >= ?1)`
    ).bind(now - PAIRING_IDLE_S),
    // A key heard from once, a month or more ago, and nothing else.
    db.prepare(
      `DELETE FROM units WHERE last_seen < ? AND name IS NULL
         AND id NOT IN (SELECT unit FROM fleet_members)
         AND id NOT IN (SELECT unit FROM pairings)`
    ).bind(now - ACTIVE_UNIT_S),
    db.prepare('DELETE FROM heartbeats WHERE unit NOT IN (SELECT id FROM units)'),
    db.prepare(
      `DELETE FROM unit_box_keys WHERE updated < ?
         AND unit NOT IN (SELECT id FROM units) AND unit NOT IN (SELECT unit FROM pairings)`
    ).bind(now - ACTIVE_UNIT_S),
    // Its replay guard is a timestamp that would be refused as stale anyway.
    db.prepare('DELETE FROM event_senders WHERE last_ts < ?').bind(now - ACTIVE_UNIT_S),
    db.prepare('DELETE FROM live_activities WHERE created < ?').bind(now - 3600),
    db.prepare('DELETE FROM live_activity_ends WHERE at < ?').bind(now - 900),
    db.prepare('DELETE FROM phone_locations WHERE updated < ?').bind(now - LOCATION_TTL_S),
    // Phones no longer paired with anything, as unpairing does.
    db.prepare('DELETE FROM phones WHERE id NOT IN (SELECT phone FROM pairings)'),
    db.prepare('DELETE FROM live_activity_phones WHERE phone NOT IN (SELECT phone FROM pairings)'),
    db.prepare('DELETE FROM live_activities WHERE phone NOT IN (SELECT phone FROM pairings)'),
    db.prepare('DELETE FROM live_activity_ends WHERE phone NOT IN (SELECT phone FROM pairings)'),
    db.prepare(`DELETE FROM phone_locations WHERE NOT EXISTS
      (SELECT 1 FROM pairings p WHERE p.phone = phone_locations.phone AND p.unit = phone_locations.unit)`),
  ];
}

export async function cleanup(db, now) {
  await db.batch(cleanupStatements(db, now));
}
