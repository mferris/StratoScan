// Request rate limits (security review 2026-11-03, SR-04).
//
// Every signed request that changes something used to write to D1 (its
// replay record) before any limit was checked, so a script minting keys
// could use up the free plan's daily D1 writes, and with them heartbeats,
// pairing and pushes for everyone, until midnight UTC. These limits are
// checked first: per address on every request, tighter per address on
// anything that can write or that guesses a password, and per signing key
// once a signature has verified (never before: anyone can name someone
// else's key in a header, and that must not use up the real one's limit).
//
// With Cloudflare's Workers Rate Limiting bindings configured (see
// wrangler.example.toml) the counts are kept by Cloudflare for each data
// centre. Without them -- or if a binding ever fails -- the same limits are
// counted in this isolate's memory, which stops a burst at one machine but
// not a spread-out flood; a rate-limiting rule on the relay's domain is the
// owner's backstop for that, and for floods of /health, which use up the
// daily request quota however cheaply they are answered.
//
// Nothing here is stored anywhere: the counts last a minute and are keyed by
// address or key only for that minute.

export const RATES = {
  // Any request at all, per address. Radars and phones behind one home
  // connection share this; a busy radar's shared-cache traffic is a few
  // hundred a minute at most (netcache.js LIMITS are per asker).
  ip:     { binding: 'RL_IP', limit: 600, period: 60 },
  // Requests that can write to the database, and the fleet pages' password
  // checks (SR-18), per address.
  strict: { binding: 'RL_STRICT', limit: 60, period: 60 },
  // Signed requests that change something, per signing key, checked after
  // the signature. A radar sends at most one event batch every 5 s.
  key:    { binding: 'RL_KEY', limit: 30, period: 60 },
};

const local = new Map();          // which -> Map(key -> { start, n })
const LOCAL_MAX_KEYS = 20_000;    // per limit; a flood of distinct keys starts the minute again

function localAllow(which, key) {
  const { limit, period } = RATES[which];
  let m = local.get(which);
  if (!m) local.set(which, (m = new Map()));
  const now = Date.now();
  let b = m.get(key);
  if (!b || now - b.start >= period * 1000) {
    if (!b && m.size >= LOCAL_MAX_KEYS) m.clear();
    b = { start: now, n: 0 };
    m.set(key, b);
  }
  b.n += 1;
  return b.n <= limit;
}

// Whether one more request counted against `which` for `key` is allowed.
export async function allow(env, which, key) {
  const binding = env && env[RATES[which].binding];
  if (binding && typeof binding.limit === 'function') {
    try {
      const r = await binding.limit({ key: `${which}:${key}` });
      return !!(r && r.success);
    } catch { /* counted here instead */ }
  }
  return localAllow(which, key);
}

// For tests: forget every in-memory count.
export function resetLocalLimits() { local.clear(); }

// The caller's address, as Cloudflare saw it. Absent only when the request
// did not come through Cloudflare's edge (tests, local development): the
// per-address limits are then not applied.
export const clientIp = request => request.headers.get('CF-Connecting-IP') || null;

function expandV6(a) {
  const [head, tail = ''] = a.split('::');
  const h = head ? head.split(':') : [], t = tail ? tail.split(':') : [];
  if (a.includes('::')) return [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill('0'), ...t];
  return h;
}

// The network block an address is in: its /24 for IPv4, its /48 for IPv6
// (one home or one small business, roughly). null when it isn't an address.
export function netBlock(ip) {
  if (typeof ip !== 'string') return null;
  const v4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(ip);
  if (v4) return v4.slice(1, 5).every(x => Number(x) <= 255) ? `${v4[1]}.${v4[2]}.${v4[3]}.0/24` : null;
  if (!/^[0-9a-fA-F:]+$/.test(ip) || !ip.includes(':')) return null;
  const g = expandV6(ip.toLowerCase());
  if (g.length !== 8 || g.some(x => !/^[0-9a-f]{1,4}$/.test(x))) return null;
  return `${g.slice(0, 3).map(x => x.replace(/^0+(?=.)/, '')).join(':')}::/48`;
}
