// The network cache (performance audit 2026-10-09): one fetch per disc,
// route or owner however many radars ask; only reporting units and paired
// phones may ask; upstream refusals are passed on, never retried in a burst.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import worker from '../src/index.js';
import {
  latticeCentre, isLatticeCentre, latticeCols, LATTICE_ROWS, DISC_SPACING_NM, DISC_R_NM,
  DISC_TTL_S, LEASE_TTL_S, ROUTE_TTL_S, NO_ROUTE_TTL_S, OWNER_TTL_S, LIMITS, tune,
  GRANT_TTL_S, DISC_MAX_AIRCRAFT, discLooksRight, nearOf,
} from '../src/netcache.js';
import { sha256Hex, signedMessage } from '../src/auth.js';
import { makeD1 } from './d1-sqlite.js';

const SCHEMA = fileURLToPath(new URL('../schema.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');
let clock = 1_800_000_000;
Date.now = () => clock * 1000;
tune.upstreamGapMs = 0;

async function newUnit() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  const raw = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  return { id: b64url(raw), key: kp.privateKey };
}

async function signed(unit, body, { ts = clock, path = '/v1/heartbeat', method = 'POST', as = 'X-FR-Unit' } = {}) {
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  // the signature covers the path, not a query (relay/src/auth.js)
  const msg = signedMessage(ts, method, path.split('?')[0], await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, unit.key, new TextEncoder().encode(msg)));
  return new Request(BASE + path, {
    method,
    headers: { [as]: unit.id, 'X-FR-Time': String(ts), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    ...(method === 'GET' ? {} : { body }),
  });
}

// A stand-in for the data centre's cache: honours s-maxage against the test clock.
function fakeCache() {
  const store = new Map();
  const ttlOf = h => Number((/s-maxage=(\d+)/.exec(h.get('Cache-Control') || '') || [])[1] || 0);
  return {
    store,
    async match(key) {
      const e = store.get(String(key));
      if (!e) return undefined;
      if (Date.now() >= e.at + e.ttl * 1000) { store.delete(String(key)); return undefined; }
      return new Response(e.body.slice(0), { headers: e.headers });
    },
    async put(key, res) {
      const body = await res.arrayBuffer();
      store.set(String(key), { body, headers: new Headers(res.headers), ttl: ttlOf(res.headers), at: Date.now() });
    },
    async delete(key) { return store.delete(String(key)); },
  };
}

// A stand-in for the outside services: answers from `answer`, records every call.
function fakeFetch(answer) {
  const calls = [];
  const f = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    const a = await answer(String(url), init, calls.length);
    if (a instanceof Response) return a;
    return new Response(JSON.stringify(a.body ?? a), { status: a.status || 200, headers: { 'Content-Type': 'application/json' } });
  };
  f.calls = calls;
  return f;
}

const DISC = { ac: [{ hex: 'a1b2c3', flight: 'UAL1', lat: 36, lon: -79, alt_baro: 35000 }], now: 1 };
const envOf = (answer, extra = {}) => {
  const fetch = fakeFetch(answer), cache = fakeCache();
  return { DB: makeD1(SCHEMA), NET_FETCH: fetch, NET_CACHE: cache, fetch, cache, ...extra };
};
const hb = () => JSON.stringify({ version: '2026.10.09.5', uptime_s: 3600 });
const reporting = async (e, u) => { clock += 1000; assert.equal((await worker.fetch(await signed(u, hb()), e)).status, 200); };
const paired = (e, u, phone) => e.DB.raw.prepare('INSERT INTO pairings (unit, phone, name, created) VALUES (?, ?, ?, ?)').run(u.id, phone.id, null, clock);
const ask = async (e, who, path, as = 'X-FR-Unit') => worker.fetch(await signed(who, '', { path, method: 'GET', as }), e);
const post = async (e, who, path, body, as = 'X-FR-Unit') => worker.fetch(await signed(who, JSON.stringify(body), { path, as }), e);
const put = async (e, who, path, text, as = 'X-FR-Unit') => worker.fetch(await signed(who, text, { path, method: 'PUT', as }), e);

function nm(lat1, lon1, lat2, lon2) {
  const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180, dl = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 3440.065 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

test('the lattice leaves no gap: every point is inside its nearest disc, and centres are shareable', () => {
  assert.equal(LATTICE_ROWS, 31);
  let worst = 0;
  for (let lat = -89.9; lat <= 89.9; lat += 3.7) {
    for (let lon = -180; lon < 180; lon += 4.3) {
      const c = latticeCentre(lat, lon);
      assert.ok(isLatticeCentre(c.lat, c.lon), `${c.lat},${c.lon} is on the lattice`);
      assert.deepEqual(latticeCentre(c.lat + 1e-5, c.lon - 1e-5), c, 'a centre maps to itself');
      worst = Math.max(worst, nm(lat, lon, c.lat, c.lon));
    }
  }
  assert.ok(worst < DISC_R_NM, `the farthest point from its centre is ${worst.toFixed(0)} nm, inside the 250 nm disc`);
  assert.ok(!isLatticeCentre(35.8776, -78.7875), 'a radar\'s own position is not a lattice centre');
  const row = latticeCentre(35.8, -78.8);
  const next = latticeCentre(35.8, -78.8 + 360 / latticeCols(row.lat));
  const gap = nm(row.lat, row.lon, next.lat, next.lon);
  assert.ok(gap <= DISC_SPACING_NM + 1 && gap > 300, `neighbours ${gap.toFixed(0)} nm apart`);
});

test('a disc is fetched by one reporting unit and served to every other that asks', async () => {
  const e = envOf(() => { throw new Error('the relay never asks adsb.lol itself'); });
  const u = await newUnit(), other = await newUnit(), stranger = await newUnit();
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  assert.equal((await worker.fetch(new Request(BASE + path), e)).status, 401, 'unsigned: refused');
  assert.equal((await ask(e, stranger, path)).status, 403, 'a unit that does not report: refused');
  assert.equal((await put(e, stranger, path, JSON.stringify(DISC))).status, 403, 'nor may it hand one up');
  await reporting(e, u); await reporting(e, other);
  const first = await ask(e, u, path);
  assert.equal(first.status, 404);
  assert.deepEqual(await first.json(), { error: 'not cached', fetch: true }, 'the first asker is told to fetch it');
  const waiting = await ask(e, other, path);
  assert.equal(waiting.status, 404);
  assert.equal((await waiting.json()).fetching, true, 'the next asker is told someone is on it');
  assert.equal(waiting.headers.get('Retry-After'), '2');
  assert.equal((await put(e, u, path, '<html>')).status, 400, 'what is handed up must look like a disc');
  assert.equal((await put(e, u, path, JSON.stringify(DISC))).status, 204);
  clock += 3;
  const served = await ask(e, other, path);
  assert.equal(served.status, 200);
  assert.equal(served.headers.get('X-Net-Cache'), 'hit');
  assert.equal(served.headers.get('Age'), '3');
  assert.deepEqual(await served.json(), DISC, 'adsb.lol\'s answer, untouched');
  clock += DISC_TTL_S;
  assert.deepEqual(await (await ask(e, u, path)).json(), { error: 'not cached', fetch: true }, 'past its keep time it is fetched again, and the old lease is gone');
  assert.equal(e.fetch.calls.length, 0);
});

test('a lease that produced nothing expires, so the disc is not stuck', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(), v = await newUnit(); await reporting(e, u); await reporting(e, v);
  const c = latticeCentre(51.5, -0.1);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  assert.equal((await (await ask(e, u, path)).json()).fetch, true);
  assert.equal((await (await ask(e, v, path)).json()).fetching, true);
  clock += LEASE_TTL_S + 1;
  assert.equal((await (await ask(e, v, path)).json()).fetch, true, 'after the lease: the next asker fetches');
  const big = await put(e, v, path, '{' + 'x'.repeat(9 * 1024 * 1024));
  assert.equal(big.status, 413);
});

test('only lattice centres are discs; the refusal says which is nearest', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(); await reporting(e, u);
  const r = await ask(e, u, '/v1/net/disc/35.8776/-78.7875');
  assert.equal(r.status, 400);
  assert.deepEqual((await r.json()).nearest, latticeCentre(35.8776, -78.7875));
  assert.equal((await ask(e, u, '/v1/net/disc/abc/def')).status, 400);
  assert.equal((await ask(e, u, '/v1/net/disc/35.8/-78.8/250')).status, 404, 'no radius: the relay decides it');
  assert.equal(e.fetch.calls.length, 0);
});

test('an upstream refusal (routes) is passed on as 503 with Retry-After and what the service said', async () => {
  const e = envOf(() => new Response('<html><title>429 Too Many Requests</title>', { status: 429 }));
  const u = await newUnit(); await reporting(e, u);
  const r = await post(e, u, '/v1/net/routes', { planes: [{ callsign: 'DAL2164', lat: 0, lng: 0 }] });
  assert.equal(r.status, 503);
  assert.equal(r.headers.get('Retry-After'), '3');
  assert.match((await r.json()).detail, /429 Too Many Requests/);
  assert.equal(e.cache.store.size, 0);
});

test('a paired phone may ask; an unpaired one may not', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(), phone = await newUnit(), loner = await newUnit();
  await reporting(e, u);
  paired(e, u, phone);
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  assert.equal((await ask(e, u, path)).status, 404, 'the radar is asked to fetch it');
  assert.equal((await put(e, u, path, JSON.stringify(DISC))).status, 204);
  assert.equal((await ask(e, phone, path, 'X-FR-Phone')).status, 200);
  assert.equal((await ask(e, loner, path, 'X-FR-Phone')).status, 403);
});

// #68: phones ask for the view on their screen. They may not hand a disc up,
// so they are never asked to fetch one, and a phone's miss must not hold up
// the radars with a lease nobody will fill.
test('a phone is never asked to fetch a disc, and takes no lease from the radars', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(), phone = await newUnit();
  await reporting(e, u); paired(e, u, phone);
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  const miss = await ask(e, phone, path, 'X-FR-Phone');
  assert.equal(miss.status, 404);
  assert.deepEqual(await miss.json(), { error: 'not cached' }, 'just "not here": it asks adsb.lol itself');
  assert.deepEqual(await (await ask(e, u, path)).json(), { error: 'not cached', fetch: true }, 'the radar after it is asked to fetch, not told to wait');
  assert.equal((await put(e, phone, path, JSON.stringify(DISC), 'X-FR-Phone')).status, 403, 'and a phone still may not hand one up');
  assert.equal(e.fetch.calls.length, 0);
});

test('near: a phone gets only the aircraft in its view, from the whole disc the radars share', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(), phone = await newUnit();
  await reporting(e, u); paired(e, u, phone);
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  const disc = { now: 5, total: 4, ac: [
    { hex: 'aaaaaa', lat: 35.88, lon: -78.79 },           // over the airport
    { hex: 'bbbbbb', lat: 36.10, lon: -78.79 },           // 13 nm north
    { hex: 'cccccc', lat: 34.0, lon: -78.0 },             // a long way off
    { hex: 'dddddd' },                                    // no position
  ] };
  assert.equal((await ask(e, u, path)).status, 404);
  assert.equal((await put(e, u, path, JSON.stringify(disc))).status, 204);
  const view = await ask(e, phone, `${path}?near=35.9,-78.8,26`, 'X-FR-Phone');
  assert.equal(view.status, 200);
  assert.equal(view.headers.get('X-Net-Cache'), 'hit');
  const got = await view.json();
  assert.deepEqual(got.ac.map(a => a.hex), ['aaaaaa', 'bbbbbb'], 'within 26 nm of the middle, and only with a position');
  assert.equal(got.total, 2);
  assert.equal(got.now, 5, 'the rest of adsb.lol\'s answer as it was');
  assert.deepEqual((await (await ask(e, phone, `${path}?near=35.9,-78.8,5`, 'X-FR-Phone')).json()).ac.map(a => a.hex), ['aaaaaa']);
  assert.deepEqual(await (await ask(e, u, path)).json(), disc, 'the shared disc itself is untouched');
  for (const bad of ['35.875,-78.8,26', '35.9,-78.8', '35.9,-78.8,0', '35.9,-78.8,251', '95,-78.8,26', 'x', '35.9,-78.8,26,1']) {
    assert.equal((await ask(e, phone, `${path}?near=${bad}`, 'X-FR-Phone')).status, 400, `near=${bad} refused`);
  }
  assert.deepEqual(nearOf('-33.85,151.2,250'), { lat: -33.85, lon: 151.2, nm: 250 });
  assert.equal(nearOf(null), null);
});

test('routes: misses go to adsb.im in one batch, hits come from the cache, "no route" is kept shorter', async () => {
  const e = envOf((url, init) => {
    assert.equal(url, 'https://adsb.im/api/0/routeset');
    const asked = JSON.parse(init.body).planes.map(p => p.callsign);
    return asked.filter(cs => cs !== 'NOROUTE').map(cs => ({
      callsign: cs, plausible: true, number: 'x', _airports: [{ location: 'Raleigh', iata: 'RDU', icao: 'KRDU', extra: 'dropped' }, { location: 'Atlanta', iata: 'ATL', icao: 'KATL' }],
    }));
  });
  const u = await newUnit(); await reporting(e, u);
  const planes = [{ callsign: 'DAL2164', lat: 35.85, lng: -78.75 }, { callsign: ' ual123 ', lat: 36, lng: -79 }, { callsign: 'NOROUTE', lat: 0, lng: 0 },
    { callsign: 'bad callsign!', lat: 0, lng: 0 }, { callsign: 'DAL2164', lat: 1, lng: 1 }];
  const r = await post(e, u, '/v1/net/routes', { planes });
  assert.equal(r.status, 200);
  const list = await r.json();
  assert.deepEqual(list.map(x => x.callsign), ['DAL2164', 'UAL123', 'NOROUTE'], 'cleaned, upper case, no duplicates, no nonsense');
  assert.deepEqual(list[0]._airports.map(a => a.location), ['Raleigh', 'Atlanta']);
  assert.equal(list[0]._airports[0].extra, undefined, 'only the fields the screens read are kept');
  assert.equal(list[2]._airports.length, 0);
  assert.equal(e.fetch.calls.length, 1);
  assert.deepEqual(JSON.parse(e.fetch.calls[0].init.body).planes.map(p => p.callsign), ['DAL2164', 'UAL123', 'NOROUTE']);
  assert.deepEqual(JSON.parse(e.fetch.calls[0].init.body).planes[0], { callsign: 'DAL2164', lat: 35.9, lng: -78.8 }, 'positions go upstream rounded to 0.1 degrees');
  clock += 60;
  const v = await newUnit(); await reporting(e, v);
  const r2 = await post(e, v, '/v1/net/routes', { planes: [{ callsign: 'DAL2164', lat: 0, lng: 0 }, { callsign: 'NOROUTE', lat: 0, lng: 0 }] });
  assert.equal((await r2.json()).length, 2);
  assert.equal(e.fetch.calls.length, 1, 'another radar asking the same callsigns costs adsb.im nothing');
  clock += NO_ROUTE_TTL_S;
  await post(e, v, '/v1/net/routes', { planes: [{ callsign: 'DAL2164', lat: 0, lng: 0 }, { callsign: 'NOROUTE', lat: 0, lng: 0 }] });
  assert.equal(e.fetch.calls.length, 2, 'past an hour the callsign with no route is asked about again');
  assert.deepEqual(JSON.parse(e.fetch.calls[1].init.body).planes.map(p => p.callsign), ['NOROUTE'], 'the known route is still cached');
  clock += ROUTE_TTL_S;
  await post(e, v, '/v1/net/routes', { planes: [{ callsign: 'DAL2164', lat: 0, lng: 0 }] });
  assert.equal(e.fetch.calls.length, 3, 'and after six hours so is the route');
  const tooMany = await post(e, v, '/v1/net/routes', { planes: Array.from({ length: 51 }, (_, i) => ({ callsign: `CS${i}`, lat: 0, lng: 0 })) });
  assert.equal(tooMany.status, 400);
  assert.equal((await post(e, v, '/v1/net/routes', { nope: 1 })).status, 400);
});

test('routes: when adsb.im is down the radar is told, not handed "no route" for everything', async () => {
  const e = envOf(() => ({ status: 500, body: {} }));
  const u = await newUnit(); await reporting(e, u);
  const r = await post(e, u, '/v1/net/routes', { planes: [{ callsign: 'DAL2164', lat: 0, lng: 0 }] });
  assert.equal(r.status, 502);
  assert.equal(e.cache.store.size, 0, 'nothing cached from a failure');
});

test('owners: adsbdb\'s answer trimmed and kept a week; "unknown" (404) is remembered too', async () => {
  const e = envOf(url => (url.endsWith('/ae74e8')
    ? { body: { response: { aircraft: { registered_owner: 'United States Army', registered_owner_country_name: 'United States', mode_s: 'AE74E8', secret: 'x' } } } }
    : { status: 404, body: { response: 'unknown aircraft' } }));
  const u = await newUnit(); await reporting(e, u);
  const r = await ask(e, u, '/v1/net/owner/ae74e8');
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { response: { aircraft: { registered_owner: 'United States Army', registered_owner_country_name: 'United States' } } });
  assert.equal(e.fetch.calls[0].url, 'https://api.adsbdb.com/v0/aircraft/ae74e8');
  assert.equal((await ask(e, u, '/v1/net/owner/ae74e8')).headers.get('Content-Type'), 'application/json');
  assert.equal(e.fetch.calls.length, 1, 'served from the cache');
  assert.equal((await ask(e, u, '/v1/net/owner/000001')).status, 404);
  assert.equal((await ask(e, u, '/v1/net/owner/000001')).status, 404);
  assert.equal(e.fetch.calls.length, 2, 'an unknown aircraft is not asked about twice');
  clock += OWNER_TTL_S + 1;
  await ask(e, u, '/v1/net/owner/ae74e8');
  assert.equal(e.fetch.calls.length, 3, 'after a week it is asked again');
  assert.equal((await ask(e, u, '/v1/net/owner/AE74E8')).status, 400, 'lower case only, so one entry per aircraft');
});

test('an asker that will not stop is refused for a minute', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(); await reporting(e, u);
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  assert.equal((await ask(e, u, path)).status, 404);
  assert.equal((await put(e, u, path, JSON.stringify(DISC))).status, 204);
  let last;
  for (let i = 0; i < LIMITS.disc; i++) last = await ask(e, u, path);
  assert.equal(last.status, 429);
  clock += 61;
  assert.deepEqual(await (await ask(e, u, path)).json(), { error: 'not cached', fetch: true }, 'a minute later it may ask again');
  assert.equal((await put(e, u, path, JSON.stringify(DISC))).status, 204);
  assert.equal((await ask(e, u, path)).status, 200);
});

// Audit 2026-10-12, from Codex's scan: any reporting radar, or any paired
// phone, could hand up any disc, with anything starting "{" in it, as often
// as it liked, and every other radar drew it.
test('only the radar asked to fetch a disc may hand it up, once, and it must look like one', async () => {
  const e = envOf(() => DISC);
  const asked = await newUnit(), other = await newUnit(), phone = await newUnit();
  await reporting(e, asked); await reporting(e, other); paired(e, asked, phone);
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  assert.equal((await put(e, other, path, JSON.stringify(DISC))).status, 409, 'a radar nobody asked: refused');
  assert.equal((await ask(e, asked, path)).status, 404, 'one radar is asked to fetch it');
  assert.equal((await put(e, other, path, JSON.stringify(DISC))).status, 409, 'another radar still may not');
  assert.equal((await put(e, phone, path, JSON.stringify(DISC), 'X-FR-Phone')).status, 403, 'a phone never may');
  const far = { ac: [{ hex: 'abc123', lat: c.lat + 8, lon: c.lon }] };
  assert.equal((await put(e, asked, path, JSON.stringify(far))).status, 400, 'aircraft outside the disc: refused');
  assert.equal((await put(e, asked, path, JSON.stringify({ msg: 'No error' }))).status, 400, 'no aircraft list: refused');
  assert.equal((await put(e, asked, path, JSON.stringify({ ac: [1, 2] }))).status, 400, 'entries that are not aircraft: refused');
  const body = JSON.stringify(DISC);
  const upload = await signed(asked, body, { path, method: 'PUT' });
  const again = upload.clone();
  assert.equal((await worker.fetch(upload, e)).status, 204, 'the real answer is shared');
  assert.equal((await worker.fetch(again, e)).status, 409, 'and the same upload sent again is refused');
  assert.equal((await put(e, asked, path, body)).status, 409, 'as is a fresh one: the ask was used up');
  assert.deepEqual(await (await ask(e, other, path)).json(), DISC, 'what others draw is what was fetched');
});

test('a grant to hand up a disc lapses', async () => {
  const e = envOf(() => DISC);
  const u = await newUnit(); await reporting(e, u);
  const c = latticeCentre(35.8, -78.8);
  const path = `/v1/net/disc/${c.lat}/${c.lon}`;
  assert.equal((await ask(e, u, path)).status, 404);
  clock += GRANT_TTL_S + 1;
  assert.equal((await put(e, u, path, JSON.stringify(DISC))).status, 409);
});

test('discLooksRight: the real thing passes, near misses do not', () => {
  const c = latticeCentre(35.8, -78.8);
  const enc = o => new TextEncoder().encode(JSON.stringify(o));
  assert.ok(discLooksRight(enc({ ac: [{ hex: 'a', lat: c.lat, lon: c.lon }, { hex: 'b' }], now: 1 }), c), 'positions inside, and an aircraft with none');
  assert.ok(discLooksRight(enc({ ac: [] }), c), 'an empty sky is a real answer');
  assert.ok(!discLooksRight(new TextEncoder().encode('{"ac":[{"lat":'), c), 'truncated');
  assert.ok(!discLooksRight(enc([{ ac: [] }]), c), 'an array');
  assert.ok(!discLooksRight(enc({ ac: [{ lat: 'x', lon: 1 }] }), c), 'a position that is not a number');
  assert.ok(!discLooksRight(enc({ ac: [{ lat: 95, lon: 0 }] }), c), 'a position off the planet');
  assert.ok(!discLooksRight(enc({ ac: Array.from({ length: DISC_MAX_AIRCRAFT + 1 }, () => ({})) }), c), 'too many aircraft');
});
