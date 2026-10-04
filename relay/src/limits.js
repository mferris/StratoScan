// Limits and fleet assessment, shared by the Worker and its tests.

export const MAX_BODY = 8192;
export const MIN_INTERVAL_S = 10 * 60;   // a unit reports every 6 h; this only stops floods
export const MAX_UNITS = 500;            // bounds what an unauthenticated first contact can create
export const HISTORY_PER_UNIT = 120;     // ~30 days at one report per 6 h
export const STALE_AFTER_S = 13 * 3600;  // two missed reports

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
  if (p.thermal && p.thermal.throttled && p.thermal.throttled !== '0x0') flags.push('throttled');
  if (p.thermal && p.thermal.temp_c > 80) flags.push('hot');
  if (p.storage && p.storage.gb_per_day > 5) flags.push('heavy writes');
  if (p.storage && p.storage.free_pct < 10) flags.push('disk full');
  if (p.rtc && p.rtc.fitted && p.rtc.battery_mv < 2500) flags.push('RTC battery low');
  // Only the states that mean something went wrong. 'checked' is the normal
  // state after the nightly check finds nothing new, 'staged' and 'applying'
  // are an update in progress, 'ok' is one installed; flagging those made
  // every healthy radar look wrong (seen on the fleet page 2026-10-04).
  if (p.ota && ['error', 'rolled_back'].includes(p.ota.state)) flags.push(`update ${p.ota.state.replace('_', ' ')}`);
  return { flags, p };
}


// Pairing (roadmap 2.3).
export const PAIRING_TTL_S = 10 * 60;
export const PAIRING_MAX_ATTEMPTS = 5;   // wrong secrets before an offer is void
export const MAX_PHONES_PER_UNIT = 10;
export const MAX_UNITS_PER_PHONE = 20;

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
