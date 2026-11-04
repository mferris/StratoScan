// Limits and fleet assessment, shared by the Worker and its tests.

export const MAX_BODY = 8192;
export const MIN_INTERVAL_S = 10 * 60;   // a unit reports every 6 h; this only stops floods
export const MAX_UNITS = 500;            // bounds what an unauthenticated first contact can create
export const HISTORY_PER_UNIT = 120;     // ~30 days at one report per 6 h
export const STALE_AFTER_S = 13 * 3600;  // two missed reports

// Self-minted keys (security review 2026-11-03, SR-03 and SR-05), until
// enrolment (#65) decides who may report at all. Any key can still make
// first contact, but:
// - only units heard from in the last ACTIVE_UNIT_S count toward MAX_UNITS,
//   and the daily cleanup forgets units silent that long (unless they are
//   named, in a fleet or paired), so keys minted once and abandoned stop
//   filling the fleet after a month instead of for good;
// - a unit younger than YOUNG_UNIT_S keeps only HISTORY_YOUNG reports;
// - each stored report is a whitelisted copy (cleanHeartbeat), about 1 KB,
//   not whatever 8 KB the key sent;
// - the shared network cache serves a unit only after MEMBER_MIN_AGE_S and
//   MEMBER_MIN_REPORTS of reports, and while it still reports.
export const ACTIVE_UNIT_S = 30 * 86400;
export const HEARTBEAT_RETENTION_S = 30 * 86400;
export const YOUNG_UNIT_S = 7 * 86400;
export const HISTORY_YOUNG = 3;
export const MEMBER_MIN_AGE_S = 48 * 3600;
export const MEMBER_MIN_REPORTS = 4;     // a unit reports every 6 h: 8 in two days
export const MEMBER_RECENT_S = 2 * 86400;
export const HEARTBEAT_STORED_MAX = 2048;   // the whitelisted copy can never be bigger than this

// The fields of a health report the fleet pages read, and nothing else
// (SR-05; SR-20: a crafted list could break an administrator's page). Unknown
// fields are dropped rather than refused, so a newer unit can add one; it
// shows on the fleet pages once it is added here.
const str = max => v => (typeof v === 'string' ? v.replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, '').slice(0, max) : undefined);
const numv = v => (typeof v === 'number' && Number.isFinite(v) && Math.abs(v) <= 1e12 ? v : undefined);
const intv = v => (Number.isInteger(v) && Math.abs(v) <= 1e12 ? v : undefined);
const boolv = v => (typeof v === 'boolean' ? v : undefined);
const HEARTBEAT_SHAPE = {
  v: intv, version: str(32), serial: v => intv(v) ?? str(24)(v), uptime_s: numv, ring: intv, name: str(32),
  last_watchdog_reboot_age_s: numv,
  ota: { state: str(24), held: str(120) },
  receiver: { age_s: numv, aircraft: numv, messages_per_min: numv, signal_db: numv, noise_db: numv, restarts: numv },
  display: { painted_age_s: numv },
  storage: { device: str(24), gb_per_day: numv, rate_window_h: numv, lifetime_gb: numv, free_pct: numv },
  rtc: { fitted: boolv, battery_mv: numv, charging: boolv },
  thermal: { temp_c: numv, throttled: str(16) },
  power: { undervoltage_24h: numv },
  memory_mb: { MemTotal: numv, MemAvailable: numv, Shmem: numv },
  os: { last_patch_age_s: numv, pending: numv, pending_since: numv, chromium: str(40), kernel: str(64),
        restart_waiting: boolv, trial: boolv, held_update: str(16) },
};
const VISIT_DAY = { date: str(10), views: intv, unique: intv };

function shaped(v, shape) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return undefined;
  const out = {};
  for (const [k, f] of Object.entries(shape)) {
    if (!(k in v)) continue;
    if (v[k] === null) { out[k] = null; continue; }
    const x = typeof f === 'function' ? f(v[k]) : shaped(v[k], f);
    if (x !== undefined) out[k] = x;
  }
  return out;
}

// The copy of a health report the relay keeps.
export function cleanHeartbeat(p) {
  const out = shaped(p, HEARTBEAT_SHAPE) || {};
  if (Array.isArray(p.visits)) {
    out.visits = p.visits.slice(-7).map(d => shaped(d, VISIT_DAY)).filter(Boolean);
  }
  return out;
}

// Unit events (POST /v1/events). A unit caps itself at 60 ordinary events an
// hour plus any emergencies; these bound what a misbehaving one can do.
export const EVENT_KINDS = ['emergency', 'notable', 'low_overhead', 'helicopter', 'test', 'approach', 'approach_end'];
export const MAX_EVENTS_PER_REQUEST = 20;
export const EVENTS_PER_HOUR = 120;
export const EVENTS_PER_UNIT = 500;
export const EVENT_RETENTION_S = 48 * 3600;
export const EVENT_MAX_AGE_S = 3600;     // older than this relative to the request is refused

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
// Printable text only, bounded. These end up on a phone's lock screen.
const text = (v, max) => {
  if (typeof v !== 'string') return undefined;
  const t = v.replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, '').trim().slice(0, max);
  return t || undefined;
};
const num = (v, lo, hi) => (typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi ? v : undefined);

// The validated, whitelisted copy of one event, or null when it is unusable.
// Unknown fields are dropped rather than refused, so a newer unit can add
// one without breaking; a location is refused before this is ever called.
export function cleanEvent(e, requestTs) {
  if (!e || typeof e !== 'object' || Array.isArray(e)) return null;
  if (!EVENT_KINDS.includes(e.kind)) return null;
  if (!Number.isInteger(e.ts) || e.ts > requestTs + 60 || e.ts < requestTs - EVENT_MAX_AGE_S) return null;
  const out = { kind: e.kind, ts: e.ts };
  if (e.kind === 'test') {
    const label = text(e.label, 60);
    if (label) out.label = label;
    return out;
  }
  if (typeof e.hex !== 'string' || !/^[0-9a-f]{6}$/.test(e.hex)) return null;
  out.hex = e.hex;
  // An approach to one phone's location (roadmap 2.7), or a nearby alert
  // measured from it (#44), names that phone, and goes to it alone.
  if (['approach', 'approach_end', 'notable', 'low_overhead', 'helicopter'].includes(e.kind) && e.phone !== undefined) {
    if (typeof e.phone !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(e.phone)) return null;
    out.phone = e.phone;
  }
  if (e.kind === 'approach_end') return out;
  if (e.kind === 'approach') {
    if (!Number.isInteger(e.eta_s) || e.eta_s < 0 || e.eta_s > 600) return null;
    out.eta_s = e.eta_s;
  }
  const fields = {
    flight: text(e.flight, 8),
    reg: text(e.reg, 12),
    type: text(e.type, 40),
    type_code: typeof e.type_code === 'string' && /^[A-Z0-9]{1,6}$/.test(e.type_code) ? e.type_code : undefined,
    // Where it is going, as the unit's core feed has it ("Miami → Newark"), #59.
    route: text(e.route, 60),
    label: text(e.label, 60),
    operator: text(e.operator, 60),
    squawk: typeof e.squawk === 'string' && /^[0-7]{4}$/.test(e.squawk) ? e.squawk : undefined,
    alt_ft: Number.isInteger(e.alt_ft) ? num(e.alt_ft, -2000, 80000) : undefined,
    dist_nm: num(e.dist_nm, 0, 1000),
    dir: COMPASS.includes(e.dir) ? e.dir : undefined,
    // The aircraft's own track, whole degrees (roadmap 3.4).
    trk: Number.isInteger(e.trk) && e.trk >= 0 && e.trk < 360 ? e.trk : undefined,
  };
  for (const [k, v] of Object.entries(fields)) if (v !== undefined) out[k] = v;
  return out;
}


// Problems worth a maintainer's attention, derived from the latest report.
export function assess(unit, now) {
  const flags = [];
  if (now - unit.last_seen > STALE_AFTER_S) flags.push('silent');
  let p = {};
  try { p = JSON.parse(unit.payload || '{}'); } catch { /* shown as-is */ }
  if (p.receiver && typeof p.receiver.age_s === 'number' && p.receiver.age_s > 300) flags.push('receiver stale');
  // get_throttled: the low bits are now, bit 16 (under-voltage) and bit 18
  // (throttling) are "has happened since boot" and never clear. A unit that
  // counts its brown-outs (power.undervoltage_24h, 2026-10-09) is judged on
  // the day's count instead of the sticky bit, which on a unit up for weeks
  // says nothing about today.
  const thr = p.thermal && typeof p.thermal.throttled === 'string' ? parseInt(p.thermal.throttled, 16) || 0 : 0;
  if (thr & 0xf) flags.push('throttled now');
  if (p.power && typeof p.power.undervoltage_24h === 'number') {
    if (p.power.undervoltage_24h > 10) flags.push(`power dips (${p.power.undervoltage_24h}/day)`);
  } else if (thr & 0x50000) {
    flags.push('throttled');
  }
  if (p.thermal && p.thermal.temp_c > 80) flags.push('hot');
  if (p.storage && p.storage.gb_per_day > 5) flags.push('heavy writes');
  if (p.storage && p.storage.free_pct < 10) flags.push('disk full');
  if (p.rtc && p.rtc.fitted && p.rtc.battery_mv < 2500) flags.push('RTC battery low');
  // Only the states that mean something went wrong. 'checked' is the normal
  // state after the nightly check finds nothing new, 'staged' and 'applying'
  // are an update in progress, 'ok' is one installed; flagging those made
  // every healthy radar look wrong (seen on the fleet page 2026-10-04).
  if (p.ota && ['error', 'rolled_back'].includes(p.ota.state)) flags.push(`update ${p.ota.state.replace('_', ' ')}`);
  // Operating-system patching (#73). The daily security run touches its stamp
  // each day it runs; a week without one is a radar that has stopped
  // patching. Updates waiting a week means it runs but cannot install them.
  if (p.os && typeof p.os === 'object') {
    const DAY = 86400;
    if (typeof p.os.last_patch_age_s === 'number' && p.os.last_patch_age_s > 7 * DAY) {
      flags.push(`not patching (${Math.floor(p.os.last_patch_age_s / DAY)} days)`);
    }
    if (p.os.pending > 0 && typeof p.os.pending_since === 'number' && now - p.os.pending_since > 7 * DAY) {
      flags.push(`security updates waiting (${p.os.pending})`);
    }
    if (p.os.held_update === 'rolled back') flags.push('OS update rolled back');
  }
  return { flags, p };
}


// Pairing (roadmap 2.3).
export const PAIRING_TTL_S = 10 * 60;
export const MAX_PHONES_PER_UNIT = 10;
export const MAX_UNITS_PER_PHONE = 20;
// Open pairing codes (SR-03): at most MAX_OFFERS_PER_NET from one network
// block (/24 or /48) at a time, and only the newest MAX_OPEN_OFFERS kept in
// all, so minted keys re-offering every 10 minutes can no longer fill the
// table and stop every phone from pairing. A wrong secret no longer voids
// an offer (SR-17): strangers knew the unit id from any pair link, and a
// 128-bit secret is not guessed; the per-key and per-address limits bound
// the guessing anyway.
export const MAX_OFFERS_PER_NET = 8;
export const MAX_OPEN_OFFERS = 500;
// A pairing younger than this (SR-03): only YOUNG_PAIRING_URGENT_PER_HOUR of
// its radar's emergencies and tests reach the phone in an hour, counted for
// that pairing alone (pairings.urgent_*), so a busy older radar on the same
// phone doesn't use them up. A minted radar paired through a link sent to a
// stranger could otherwise send them 60 time-sensitive alerts an hour.
// Open codes from settled radars (budget.js) are neither capped per network
// nor pushed out by newer ones.
export const YOUNG_PAIRING_S = 86400;
export const YOUNG_PAIRING_URGENT_PER_HOUR = 5;
// A pairing neither side has shown any sign of life in for this long is
// forgotten by the daily cleanup (cleanup.js).
export const PAIRING_IDLE_S = 90 * 86400;

export function cleanPhoneName(v) {
  if (typeof v !== 'string') return null;
  const t = v.replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, '').trim().slice(0, 40);
  return t || null;
}

// Push (roadmap 2.1).
// 'approach' is an aircraft about to pass over the radar; 'approach_me', one
// about to pass over the phone itself (roadmap 2.7).
//
// 'near_radar' and 'near_me' (#44) aren't kinds of event but where the
// nearby alerts (notable, low_overhead, helicopter) are about: the radar,
// the phone, or both. A phone with neither -- every phone before #44 --
// gets the radar's, as it always did.
export const PUSH_KINDS = ['emergency', 'notable', 'low_overhead', 'helicopter', 'approach', 'approach_me',
  'near_radar', 'near_me'];
export const NEARBY_KINDS = ['notable', 'low_overhead', 'helicopter'];

// Phone locations (roadmap 2.7): encrypted on the phone, for one radar.
export const LOCATION_TTL_S = 6 * 3600;      // older than this, it no longer says where the phone is
export const LOCATION_MIN_GAP_S = 20;        // significant-change updates come minutes apart
export const LOCATION_BLOB_MAX = 400;        // a 32-byte key, 12-byte nonce, ~100 bytes of JSON, 16-byte tag
export const BOX_KEY_CONTEXT = 'stratoscan-boxkey-v1:';
export const PUSHES_PER_HOUR = 30;      // per phone, ordinary alerts
export const PUSHES_PER_HOUR_HARD = 60; // per phone, everything: emergencies and tests go past the
                                        // ordinary cap, but a misbehaving unit still cannot flood a phone
export const PUSHES_PER_BATCH = 3;      // per phone per request; the rest become one summary. Bounds the
                                        // outbound requests one invocation makes (Workers free plan: 50)

export function cleanKinds(v) {
  if (v === undefined) return [...PUSH_KINDS];
  if (!Array.isArray(v)) return null;
  const out = [...new Set(v)].filter(k => PUSH_KINDS.includes(k));
  return out.length === v.length ? out : null;
}
