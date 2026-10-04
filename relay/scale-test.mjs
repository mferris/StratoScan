// A day in the life of a fleet, against the real Worker code and its real
// SQL (the D1 stand-in from test/), to see what one radar and one phone cost
// the relay and that no cap is hit at a given size.
//
//   node scale-test.mjs                 # the family: 5 radars, 3 phones each
//   node scale-test.mjs 100 2           # 100 radars, 2 phones each
//
// Each radar: a health report every 6 h, 12 alerts a day in bursts, its box
// key once, location polls every 60 s while a phone shares (one per radar
// does) and every 10 min otherwise. Each phone: paired once, registered once,
// the app opened 10 times a day (which lists its radars), and the sharing
// phone posts its location every 5 min. Pushes go to a fake Apple that
// answers 200. Prints requests, D1 statements, rows and the worst status.
import { fileURLToPath } from 'node:url';
import worker from './src/index.js';
import { sha256Hex, signedMessage } from './src/auth.js';
import { BOX_KEY_CONTEXT } from './src/limits.js';
import { makeD1 } from './test/d1-sqlite.js';

const UNITS = Number(process.argv[2] || 5), PHONES = Number(process.argv[3] || 3);
const SCHEMA = fileURLToPath(new URL('./schema.sql', import.meta.url));
const BASE = 'https://relay.example';
const b64url = bytes => Buffer.from(bytes).toString('base64url');
let clock = 1_900_000_000;
Date.now = () => clock * 1000;

const stats = { requests: 0, statements: 0, byPath: {}, status: {}, pushes: 0 };
const d1 = makeD1(SCHEMA);
const rawPrepare = d1.prepare;
d1.prepare = sql => { stats.statements++; return rawPrepare(sql); };

async function p256Pem() {
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign']);
  const der = Buffer.from(await crypto.subtle.exportKey('pkcs8', kp.privateKey)).toString('base64');
  return `-----BEGIN PRIVATE KEY-----\n${der.match(/.{1,64}/g).join('\n')}\n-----END PRIVATE KEY-----\n`;
}
const env = {
  DB: d1, FLEET_TOKEN: 'x', APNS_KEY: await p256Pem(), APNS_KEY_ID: 'KEY', APNS_TEAM_ID: 'TEAM', APNS_TOPIC: 'app',
  APNS_FETCH: async () => { stats.pushes++; return new Response('{}', { status: 200 }); },
};
const ctx = { waitUntil: p => pending.push(p) };
const pending = [];

async function newKey() {
  const kp = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify']);
  return { id: b64url(new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey))), key: kp.privateKey };
}
async function call(who, as, method, path, body) {
  const bytes = new TextEncoder().encode(method === 'GET' ? '' : body);
  const msg = signedMessage(clock, method, path, await sha256Hex(bytes));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, who.key, new TextEncoder().encode(msg)));
  const req = new Request(BASE + path, {
    method, headers: { [as]: who.id, 'X-FR-Time': String(clock), 'X-FR-Sig': b64url(sig), 'Content-Type': 'application/json' },
    ...(method === 'GET' ? {} : { body }),
  });
  const r = await worker.fetch(req, env, ctx);
  stats.requests++;
  stats.byPath[path] = (stats.byPath[path] || 0) + 1;
  stats.status[r.status] = (stats.status[r.status] || 0) + 1;
  if (r.status >= 400 && r.status !== 429) {
    stats.failures = stats.failures || [];
    if (stats.failures.length < 5) stats.failures.push(`${method} ${path} -> ${r.status} ${await r.text()}`);
  }
  return r;
}
const unitCall = (u, m, p, b) => call(u, 'X-FR-Unit', m, p, b);
const phoneCall = (ph, m, p, b) => call(ph, 'X-FR-Phone', m, p, b);

const hb = () => JSON.stringify({ v: 1, version: '2026.10.04.4', uptime_s: 86400, receiver: { age_s: 1, aircraft: 12, messages_per_min: 2500, signal_db: -15, noise_db: -32, restarts: 0 },
  storage: { device: 'mmcblk0', gb_per_day: 2.2, free_pct: 70, lifetime_gb: 40 }, rtc: { fitted: true, battery_mv: 2990 }, thermal: { temp_c: 62, throttled: '0x0' },
  memory_mb: { MemTotal: 8000, MemAvailable: 5000 }, name: 'Radar', visits: [{ date: 'd', views: 3, unique: 2 }] });
const alert = (i) => ({ kind: ['notable', 'low_overhead', 'helicopter'][i % 3], ts: clock, hex: (0xa00000 + i).toString(16).padStart(6, '0'),
  flight: 'N' + (1000 + i), type: 'Bombardier Challenger', label: 'Helicopter', alt_ft: 900, dist_nm: 1.5, dir: 'N', trk: 90 });
const blob = () => b64url(crypto.getRandomValues(new Uint8Array(32 + 12 + 90 + 16)));

// ---- set up the fleet: pairing, registration, box keys -----------------------
const units = [];
for (let i = 0; i < UNITS; i++) {
  const u = await newKey(); u.phones = [];
  for (let j = 0; j < PHONES; j++) {
    const ph = await newKey(); ph.shares = j === 0;
    const secret = b64url(crypto.getRandomValues(new Uint8Array(16)));
    await unitCall(u, 'POST', '/v1/unit/pairing', JSON.stringify({ secret_hash: await sha256Hex(new TextEncoder().encode(secret)) }));
    await phoneCall(ph, 'POST', '/v1/pair', JSON.stringify({ unit: u.id, secret, name: 'iPhone' }));
    await phoneCall(ph, 'POST', '/v1/phone/register', JSON.stringify({ token: 'ab'.repeat(32), env: 'production',
      kinds: ph.shares ? ['emergency', 'notable', 'low_overhead', 'helicopter', 'approach', 'approach_me', 'near_me'] : undefined }));
    u.phones.push(ph);
    clock += 1;
  }
  units.push(u);
}
const setupRequests = stats.requests, setupStatements = stats.statements;

// ---- one simulated day, in 60 s steps --------------------------------------------
const DAY = 86400, STEP = 60;
let eventsSent = 0;
for (let t = 0; t < DAY; t += STEP) {
  clock += STEP;
  for (const [i, u] of units.entries()) {
    const sharing = u.phones.some(p => p.shares);
    if ((t + i * 60 * 7) % (6 * 3600) === 0) await unitCall(u, 'POST', '/v1/heartbeat', hb());
    if (t === i * 60) {
      // the box key, signed by the unit's identity as the real unit does
      const key = b64url(crypto.getRandomValues(new Uint8Array(32)));
      const sig = new Uint8Array(await crypto.subtle.sign({ name: 'Ed25519' }, u.key, new TextEncoder().encode(BOX_KEY_CONTEXT + key)));
      await unitCall(u, 'POST', '/v1/unit/boxkey', JSON.stringify({ key, sig: b64url(sig) }));
    }
    if (t % (sharing ? 60 : 600) === 0) await unitCall(u, 'GET', '/v1/unit/locations', '');
    // 12 alerts a day: four bursts of three, an hour apart from the next radar's
    if ((t + i * 3600) % (6 * 3600) === 1800) {
      const r = await unitCall(u, 'POST', '/v1/events', JSON.stringify({ events: [alert(i * 10 + 1), alert(i * 10 + 2), alert(i * 10 + 3)] }));
      if (r.status === 200) eventsSent += 3;
    }
    for (const [j, ph] of u.phones.entries()) {
      if (ph.shares && t % 300 === 0) await phoneCall(ph, 'POST', '/v1/phone/location', JSON.stringify({ unit: u.id, blob: blob() }));
      if ((t + j * 600) % (DAY / 10) === 0) await phoneCall(ph, 'GET', '/v1/phone/units', '');
    }
  }
  await Promise.all(pending.splice(0));
}

const rows = {};
for (const tbl of ['units', 'heartbeats', 'events', 'event_senders', 'pairings', 'phones', 'phone_locations', 'unit_box_keys', 'pairing_offers']) {
  rows[tbl] = d1.raw.prepare(`SELECT COUNT(*) AS n FROM ${tbl}`).get().n;
}
const dayRequests = stats.requests - setupRequests, dayStatements = stats.statements - setupStatements;
console.log(JSON.stringify({
  fleet: { units: UNITS, phonesPerUnit: PHONES, phones: UNITS * PHONES, sharingPhones: UNITS },
  setup: { requests: setupRequests, statements: setupStatements },
  day: { requests: dayRequests, perUnit: +(dayRequests / UNITS).toFixed(1), statements: dayStatements, statementsPerRequest: +(dayStatements / dayRequests).toFixed(2),
         eventsSent, pushesSent: stats.pushes, byPath: stats.byPath, status: stats.status, failures: stats.failures || [] },
  rows,
}, null, 1));
