// One cache for every radar (performance audit 2026-10-09, §3 and §7.4).
//
// Each radar used to ask the public services itself -- adsb.lol for the
// network's aircraft round its view, adsb.im for routes, adsbdb for the
// registered owner of a private aircraft -- so their load was the fleet's
// size times a radar's questions, and the fleet's growth was their problem.
// Here the relay asks once and serves every unit and phone that wants the
// same thing:
//
//   GET  /v1/net/disc/<lat>/<lon>   the aircraft in a 250 nm disc on a FIXED
//                                   world lattice (below), kept DISC_TTL_S
//   POST /v1/net/routes             {"planes":[{callsign,lat,lng}]}, as adsb.im
//                                   takes it; each callsign kept ROUTE_TTL_S
//   GET  /v1/net/owner/<hex>        adsbdb's registered owner, kept OWNER_TTL_S
//
// The discs are on a lattice rather than round each radar on purpose: two
// radars looking at the same part of the sky then ask for the same disc,
// and it is fetched once. A radar asks for the discs that cover its view
// and filters them itself; the relay passes adsb.lol's answer through
// untouched (no parsing of megabytes on every request).
//
// WHO FETCHES A DISC. Not the relay: adsb.lol rate-limits by address, and a
// Worker's address is Cloudflare's, shared with everyone else's Workers --
// the first disc asked for from here came back "429 Too Many Requests"
// (2026-10-09) while the same request from a home connection was fine. So
// the unit that finds a disc missing fetches it from adsb.lol with its own
// address, exactly as it always did, and hands it up (PUT) for the others;
// a short lease tells the next radar to wait a moment rather than fetch
// too. adsb.lol sees one fetch per disc per DISC_TTL_S whoever is looking,
// and never a burst from one address. Routes and owners the relay does
// fetch itself; adsb.im and adsbdb answer it.
//
// Who may ask: a unit that reports to the relay (it is in `units`, which
// only a signed health report puts it in) or a phone paired with one. The
// signature is the same as every other request's; membership keeps this
// from being an open proxy to three volunteer-run services. The relay
// keeps nothing about who asked for what: the cache is keyed by the thing
// asked for, never by the asker.
//
// Toward the upstream services the relay behaves as one well-mannered
// client: one fetch at a time per key (single-flight), a short gap between
// fetches (adsb.lol refuses bursts, 420/429 measured on the unit), and a
// refusal passed on as 503 with a Retry-After rather than retried.
//
// Both the cache (Cloudflare's, per data centre) and the upstream fetch can
// be handed in through env (NET_CACHE, NET_FETCH) so the tests run the
// real code against a fake of each.
import { verifyRequest } from './auth.js';

export const DISC_R_NM = 250;                      // what adsb.lol serves at most
export const DISC_SPACING_NM = DISC_R_NM * Math.SQRT2;   // discs this far apart leave no gap
export const LATTICE_ROWS = Math.ceil(10800 / DISC_SPACING_NM);   // 31 rows of discs pole to pole
export const DISC_TTL_S = 10;
export const DISC_MAX_BYTES = 8 * 1024 * 1024;
export const LEASE_TTL_S = 6;                      // how long "a radar is fetching it" holds
export const LEASE_RETRY_S = 2;                    // what a waiting radar is told
export const ROUTE_TTL_S = 6 * 3600;
export const NO_ROUTE_TTL_S = 3600;
export const ROUTES_PER_ASK = 50;
export const OWNER_TTL_S = 7 * 86400;
export const LIMITS = { disc: 120, routes: 30, owner: 90 };   // per asker, per minute
export const MEMBER_TTL_MS = 60_000;               // how long "is a member" is remembered
export const tune = { upstreamGapMs: 250 };        // tests set it to 0

const ADSB_IM = 'https://adsb.im/api/0/routeset';
const ADSBDB = 'https://api.adsbdb.com/v0/aircraft/';
const USER_AGENT = 'StratoScan-relay/1 (+https://github.com/mferris/StratoScan; one cache for every StratoScan radar)';
// Cache keys are URLs on our own origin that nothing serves; they only
// name entries in the data centre's cache.
const CACHE_ORIGIN = 'https://relay.stratoscan.io/_cache/';

// ---- the lattice ------------------------------------------------------------
// Rows of disc centres every 180/LATTICE_ROWS degrees of latitude (about
// 348 nm), and in each row as many columns as fit DISC_SPACING_NM apart at
// that latitude, so a disc's nearest neighbour is at most ~354 nm away and
// every point on Earth is inside at least one 250 nm disc. The unit computes
// the same lattice (deploy/network-compare.py) and must land on the same
// centres to four decimals, so the two formulas are kept identical.
const ROW_STEP = 180 / LATTICE_ROWS;

export function latticeCols(lat) {
  return Math.max(1, Math.ceil(21600 * Math.cos(lat * Math.PI / 180) / DISC_SPACING_NM));
}

// The lattice centre whose cell holds (lat, lon): the nearest one.
export function latticeCentre(lat, lon) {
  const k = Math.min(LATTICE_ROWS - 1, Math.max(0, Math.floor((lat + 90) / ROW_STEP)));
  const clat = -90 + (k + 0.5) * ROW_STEP;
  const n = latticeCols(clat), dlon = 360 / n;
  const j = ((Math.floor((lon + 180) / dlon) % n) + n) % n;
  return { lat: Number(clat.toFixed(4)), lon: Number((-180 + (j + 0.5) * dlon).toFixed(4)) };
}

export function isLatticeCentre(lat, lon) {
  const c = latticeCentre(lat, lon);
  return Math.abs(c.lat - lat) < 1e-3 && Math.abs(c.lon - lon) < 1e-3;
}

// ---- small in-isolate state ---------------------------------------------------
// Workers keep a module's state between requests on the same machine, not
// across machines, so these are best-effort: enough to stop one busy radar
// from turning into a burst upstream.
const members = new Map();      // "unit:<id>" / "phone:<id>" -> remembered until (ms)
const buckets = new Map();      // "<id>|<kind>" -> {n, start}
let lastUpstream = 0;

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function paced(fn) {
  const wait = lastUpstream + tune.upstreamGapMs - Date.now();
  if (wait > 0) await sleep(wait);
  lastUpstream = Date.now();
  return fn();
}

function allow(id, kind) {
  const key = `${id}|${kind}`, now = Date.now();
  let b = buckets.get(key);
  if (!b || now - b.start >= 60_000) {
    if (buckets.size > 10_000) buckets.clear();
    b = { n: 0, start: now };
    buckets.set(key, b);
  }
  b.n += 1;
  return b.n <= LIMITS[kind];
}

async function isMember(env, kind, id) {
  const key = `${kind}:${id}`, now = Date.now();
  const until = members.get(key);
  if (until && until > now) return true;
  const row = kind === 'phone'
    ? await env.DB.prepare('SELECT 1 AS x FROM pairings WHERE phone = ? LIMIT 1').bind(id).first()
    : await env.DB.prepare('SELECT 1 AS x FROM units WHERE id = ? LIMIT 1').bind(id).first();
  if (!row) return false;
  if (members.size > 10_000) members.clear();
  members.set(key, now + MEMBER_TTL_MS);
  return true;
}

// ---- the cache ----------------------------------------------------------------
const cacheOf = env => env.NET_CACHE || caches.default;
const fetchOf = env => env.NET_FETCH || ((...a) => fetch(...a));

async function cacheGet(env, name) {
  const hit = await cacheOf(env).match(CACHE_ORIGIN + name);
  if (!hit) return null;
  const at = Number(hit.headers.get('X-Fetched-At') || 0);
  return { body: await hit.arrayBuffer(), ageS: at ? Math.max(0, Math.round((Date.now() - at) / 1000)) : 0 };
}

function cachePut(env, ctx, name, body, ttlS, contentType = 'application/json') {
  const res = new Response(body, {
    headers: {
      'Content-Type': contentType,
      'Cache-Control': `public, s-maxage=${ttlS}, max-age=${ttlS}`,
      'X-Fetched-At': String(Date.now()),
    },
  });
  const p = cacheOf(env).put(CACHE_ORIGIN + name, res);
  if (ctx && ctx.waitUntil) ctx.waitUntil(p);
  return p;
}

const cacheDrop = (env, name) => cacheOf(env).delete(CACHE_ORIGIN + name);

// A disc handed up by a unit: bigger than any other body the relay takes.
async function readDisc(request) {
  const len = Number(request.headers.get('Content-Length') || 0);
  if (len > DISC_MAX_BYTES) return null;
  const buf = new Uint8Array(await request.arrayBuffer());
  return buf.length > DISC_MAX_BYTES ? null : buf;
}

const dec = new TextDecoder();
const parse = buf => JSON.parse(dec.decode(buf));

// ---- the routes ---------------------------------------------------------------
export function netRoutes({ json, readBody, nowS }) {
  // `detail` is the first line of what the service said (its status page,
  // never a secret): the one clue when a volunteer-run service changes its
  // mind about serving a cache.
  const upstreamDown = (status, detail = '') =>
    [420, 429, 503].includes(status)
      ? new Response(JSON.stringify({ error: 'the service asked us to slow down', status, detail }),
          { status: 503, headers: { 'Content-Type': 'application/json', 'Retry-After': '3', 'Cache-Control': 'no-store' } })
      : json(502, { error: 'the service did not answer', status, detail });
  const snippet = async r => { try { return (await r.text()).replace(/\s+/g, ' ').slice(0, 160); } catch { return ''; } };

  // The asker: a unit that reports, or a phone that is paired. Both sign.
  async function who(request, body, env) {
    const asPhone = request.headers.has('X-FR-Phone');
    const auth = await verifyRequest(request, body, nowS(), asPhone ? 'X-FR-Phone' : 'X-FR-Unit');
    if (auth.error) return { error: json(401, { error: auth.error }) };
    const kind = asPhone ? 'phone' : 'unit';
    if (!(await isMember(env, kind, auth.unit))) {
      return { error: json(403, { error: asPhone ? 'pair with a radar first' : 'turn health reports on first' }) };
    }
    return { id: auth.unit, kind };
  }

  async function disc(request, env, ctx, latRaw, lonRaw) {
    const lat = Number(latRaw), lon = Number(lonRaw);
    if (!/^-?\d{1,2}(\.\d{1,4})?$/.test(latRaw) || !/^-?\d{1,3}(\.\d{1,4})?$/.test(lonRaw)
        || !Number.isFinite(lat) || !Number.isFinite(lon) || !isLatticeCentre(lat, lon)) {
      return json(400, { error: 'not a disc on the lattice', nearest: Number.isFinite(lat) && Number.isFinite(lon) ? latticeCentre(lat, lon) : null });
    }
    const putting = request.method === 'PUT';
    const body = putting ? await readDisc(request) : await readBody(request);
    if (!body) return json(413, { error: 'too large' });
    const w = await who(request, body, env);
    if (w.error) return w.error;
    if (!allow(w.id, 'disc')) return json(429, { error: 'too many discs; a view is a few a minute' });
    const c = latticeCentre(lat, lon);
    const name = `disc/${c.lat}/${c.lon}`, lease = `lease/${c.lat}/${c.lon}`;
    if (putting) {
      // What a unit hands up must at least look like adsb.lol's answer; the
      // unit is a signed, reporting radar, and the entry lives DISC_TTL_S.
      if (!/^\s*\{/.test(dec.decode(body.slice(0, 32)))) return json(400, { error: 'not a disc' });
      await cachePut(env, ctx, name, body, DISC_TTL_S);
      await cacheDrop(env, lease);
      return new Response(null, { status: 204 });
    }
    const hit = await cacheGet(env, name);
    if (hit) return discResponse(hit.body, 'hit', hit.ageS);
    if (await cacheOf(env).match(CACHE_ORIGIN + lease)) {
      return new Response(JSON.stringify({ error: 'not cached', fetching: true, retry_after: LEASE_RETRY_S }),
        { status: 404, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Retry-After': String(LEASE_RETRY_S) } });
    }
    await cachePut(env, ctx, lease, '1', LEASE_TTL_S, 'text/plain');
    return json(404, { error: 'not cached', fetch: true });
  }

  function discResponse(body, how, ageS) {
    return new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Net-Cache': how, 'Age': String(ageS) },
    });
  }

  const CALLSIGN = /^[A-Z0-9]{2,8}$/;

  async function routes(request, env, ctx) {
    const body = await readBody(request);
    if (!body) return json(413, { error: 'too large' });
    const w = await who(request, body, env);
    if (w.error) return w.error;
    if (!allow(w.id, 'routes')) return json(429, { error: 'too many route lookups' });
    let payload;
    try { payload = parse(body); } catch { return json(400, { error: 'not json' }); }
    const planes = payload && Array.isArray(payload.planes) ? payload.planes : null;
    if (!planes) return json(400, { error: 'expected {"planes": [...]}' });
    if (planes.length > ROUTES_PER_ASK) return json(400, { error: `at most ${ROUTES_PER_ASK} callsigns at once` });
    const wanted = new Map();
    for (const p of planes) {
      const cs = String(p && p.callsign || '').trim().toUpperCase();
      if (!CALLSIGN.test(cs) || wanted.has(cs)) continue;
      const lat = Number(p.lat), lng = Number(p.lng);
      wanted.set(cs, { callsign: cs, lat: Number.isFinite(lat) ? Number(lat.toFixed(1)) : 0, lng: Number.isFinite(lng) ? Number(lng.toFixed(1)) : 0 });
    }
    const out = [], misses = [];
    for (const [cs, plane] of wanted) {
      const hit = await cacheGet(env, `route/${cs}`);
      if (hit) out.push(parse(hit.body)); else misses.push(plane);
    }
    if (misses.length) {
      const got = await paced(() => fetchOf(env)(ADSB_IM, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'User-Agent': USER_AGENT },
        body: JSON.stringify({ planes: misses }),
        signal: AbortSignal.timeout(9000),
      })).catch(() => null);
      if (!got || !got.ok) return upstreamDown(got ? got.status : 0, got ? await snippet(got) : 'unreachable');
      let list;
      try { list = await got.json(); } catch { return json(502, { error: 'the service did not answer' }); }
      const byCs = new Map((Array.isArray(list) ? list : []).filter(x => x && typeof x.callsign === 'string').map(x => [x.callsign.toUpperCase(), x]));
      for (const m of misses) {
        const x = byCs.get(m.callsign);
        const stops = x && Array.isArray(x._airports) ? x._airports : [];
        // Only what the screens read, so a cached entry stays small.
        const slim = {
          callsign: m.callsign,
          plausible: x ? x.plausible !== false : false,
          _airports: stops.map(a => ({ location: a && a.location, name: a && a.name, iata: a && a.iata, icao: a && a.icao })),
        };
        out.push(slim);
        await cachePut(env, ctx, `route/${m.callsign}`, JSON.stringify(slim), stops.length >= 2 ? ROUTE_TTL_S : NO_ROUTE_TTL_S);
      }
    }
    return json(200, out);
  }

  async function owner(request, env, ctx, hex) {
    if (!/^[0-9a-f]{6}$/.test(hex)) return json(400, { error: 'a hex address is six hex digits, lower case' });
    const w = await who(request, await readBody(request), env);
    if (w.error) return w.error;
    if (!allow(w.id, 'owner')) return json(429, { error: 'too many owner lookups' });
    const name = `owner/${hex}`;
    const hit = await cacheGet(env, name);
    const answer = v => (v === null ? json(404, { response: 'unknown aircraft' }) : json(200, v));
    if (hit) return answer(parse(hit.body));
    const got = await paced(() => fetchOf(env)(ADSBDB + hex, {
      headers: { 'User-Agent': USER_AGENT, 'Accept': 'application/json' }, signal: AbortSignal.timeout(9000),
    })).catch(() => null);
    if (!got) return upstreamDown(0);
    let value;
    if (got.status === 404) {
      value = null;
    } else if (got.ok) {
      let d;
      try { d = await got.json(); } catch { return json(502, { error: 'the service did not answer' }); }
      const a = (d && d.response && d.response.aircraft) || {};
      value = { response: { aircraft: {
        registered_owner: typeof a.registered_owner === 'string' ? a.registered_owner.slice(0, 120) : null,
        registered_owner_country_name: typeof a.registered_owner_country_name === 'string' ? a.registered_owner_country_name.slice(0, 60) : null,
      } } };
    } else {
      return upstreamDown(got.status, await snippet(got));
    }
    await cachePut(env, ctx, name, JSON.stringify(value), OWNER_TTL_S);
    return answer(value);
  }

  async function route(request, env, ctx, pathname, m) {
    let mm;
    if ((mm = pathname.match(/^\/v1\/net\/disc\/([^/]+)\/([^/]+)$/)) && (m === 'GET' || m === 'PUT')) return disc(request, env, ctx, mm[1], mm[2]);
    if (pathname === '/v1/net/routes' && m === 'POST') return routes(request, env, ctx);
    if ((mm = pathname.match(/^\/v1\/net\/owner\/([^/]+)$/)) && m === 'GET') return owner(request, env, ctx, mm[1]);
    return null;
  }

  return { route };
}
