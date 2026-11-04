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
// What it never touches: a radar's pairings (only its owner or a phone
// removes those), a named radar, a radar in a fleet, fleets themselves, and
// box keys (a radar publishes its key once; a phone paired later needs it).
import {
  ACTIVE_UNIT_S, HEARTBEAT_RETENTION_S, EVENT_RETENTION_S, LOCATION_TTL_S,
} from './limits.js';

export function cleanupStatements(db, now) {
  return [
    db.prepare('DELETE FROM replay_guard WHERE expires < ?').bind(now),
    db.prepare('DELETE FROM pairing_offers WHERE expires <= ?').bind(now),
    db.prepare('DELETE FROM events WHERE received < ?').bind(now - EVENT_RETENTION_S),
    db.prepare('DELETE FROM heartbeats WHERE ts < ?').bind(now - HEARTBEAT_RETENTION_S),
    // A key heard from once, a month or more ago, and nothing else.
    db.prepare(
      `DELETE FROM units WHERE last_seen < ? AND name IS NULL
         AND id NOT IN (SELECT unit FROM fleet_members)
         AND id NOT IN (SELECT unit FROM pairings)`
    ).bind(now - ACTIVE_UNIT_S),
    db.prepare('DELETE FROM heartbeats WHERE unit NOT IN (SELECT id FROM units)'),
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
