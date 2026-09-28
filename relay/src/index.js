// Radome relay (Cloudflare Worker + D1). See docs/ROADMAP.md.
//
// POST /v1/heartbeat   signed by a unit; records its health (never a location)
// GET  /fleet          the maintainer's view of every unit (HTTP Basic auth)
// GET  /fleet.json     the same, as JSON
// POST /fleet/name     name a unit ("Dad's radar")
// GET  /health         liveness
//
// A unit that cannot reach this keeps working exactly as before: the radar
// never depends on it.

import { verifyRequest } from './auth.js';
// Only `default` may be exported from this file: the Workers runtime treats
// every named export of the main module as an entrypoint and refuses to
// start on anything else. Shared constants and helpers live in limits.js.
import { MAX_BODY, MIN_INTERVAL_S, MAX_UNITS, HISTORY_PER_UNIT, assess } from './limits.js';

const nowS = () => Math.floor(Date.now() / 1000);

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

async function readBody(request) {
  const len = Number(request.headers.get('Content-Length') || 0);
  if (len > MAX_BODY) return null;
  const buf = new Uint8Array(await request.arrayBuffer());
  return buf.length > MAX_BODY ? null : buf;
}

async function heartbeat(request, env) {
  const body = await readBody(request);
  if (!body) return json(413, { error: 'too large' });
  const auth = await verifyRequest(request, body, nowS());
  if (auth.error) return json(401, { error: auth.error });

  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(body));
  } catch {
    return json(400, { error: 'not json' });
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return json(400, { error: 'expected an object' });
  }
  // A location has no business here. Refuse rather than silently store one
  // if a future client bug ever included it.
  const text = JSON.stringify(payload);
  if (/"(lat|lon|latitude|longitude)"\s*:/i.test(text)) {
    return json(400, { error: 'location fields are not accepted' });
  }

  const db = env.DB;
  const existing = await db.prepare('SELECT last_ts FROM units WHERE id = ?').bind(auth.unit).first();
  if (existing) {
    if (auth.ts <= existing.last_ts) return json(409, { error: 'replayed or out of order' });
    if (auth.ts - existing.last_ts < MIN_INTERVAL_S) return json(429, { error: 'too frequent' });
  } else {
    const { n } = await db.prepare('SELECT COUNT(*) AS n FROM units').first();
    if (n >= MAX_UNITS) return json(503, { error: 'fleet full' });
  }

  const version = typeof payload.version === 'string' ? payload.version.slice(0, 32) : null;
  const seen = nowS();
  await db.batch([
    db.prepare(
      `INSERT INTO units (id, first_seen, last_seen, last_ts, version, payload)
       VALUES (?1, ?2, ?2, ?3, ?4, ?5)
       ON CONFLICT(id) DO UPDATE SET last_seen = ?2, last_ts = ?3, version = ?4, payload = ?5`
    ).bind(auth.unit, seen, auth.ts, version, text),
    db.prepare('INSERT INTO heartbeats (unit, ts, payload) VALUES (?, ?, ?)').bind(auth.unit, auth.ts, text),
    db.prepare(
      `DELETE FROM heartbeats WHERE unit = ?1 AND ts NOT IN
         (SELECT ts FROM heartbeats WHERE unit = ?1 ORDER BY ts DESC LIMIT ?2)`
    ).bind(auth.unit, HISTORY_PER_UNIT),
  ]);
  return json(200, { ok: true });
}

// ---- fleet view (maintainer only) -----------------------------------------

function timingSafeEqual(a, b) {
  const ea = new TextEncoder().encode(a), eb = new TextEncoder().encode(b);
  let diff = ea.length ^ eb.length;
  for (let i = 0; i < Math.max(ea.length, eb.length); i++) diff |= (ea[i] || 0) ^ (eb[i] || 0);
  return diff === 0;
}

function maintainer(request, env) {
  // Never open by default: with no token configured, the fleet view does
  // not exist rather than being public.
  if (!env.FLEET_TOKEN) return 'unconfigured';
  const h = request.headers.get('Authorization') || '';
  const m = /^Basic\s+(.+)$/i.exec(h);
  if (!m) return 'denied';
  let decoded = '';
  try { decoded = atob(m[1]); } catch { return 'denied'; }
  const password = decoded.slice(decoded.indexOf(':') + 1);
  return timingSafeEqual(password, env.FLEET_TOKEN) ? 'ok' : 'denied';
}

function needAuth(state) {
  if (state === 'unconfigured') return new Response('fleet view not configured\n', { status: 503 });
  return new Response('authentication required\n', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="Radome fleet", charset="UTF-8"' },
  });
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function ago(s) {
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 172800) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

async function listUnits(env) {
  const { results } = await env.DB.prepare(
    'SELECT id, name, first_seen, last_seen, version, payload FROM units ORDER BY last_seen DESC'
  ).all();
  return results || [];
}

async function fleetPage(env) {
  const now = nowS();
  const rows = (await listUnits(env)).map(u => {
    const { flags, p } = assess(u, now);
    const uptimeD = p.uptime_s ? (p.uptime_s / 86400).toFixed(1) + 'd' : '—';
    return `<tr class="${flags.length ? 'warn' : 'ok'}">
      <td><b>${esc(u.name || '(unnamed)')}</b><br><code>${esc(u.id.slice(0, 10))}…</code></td>
      <td>${esc(u.version || '—')}</td>
      <td>${esc(ago(now - u.last_seen))}</td>
      <td>${esc(uptimeD)}</td>
      <td>${flags.length ? esc(flags.join(', ')) : 'healthy'}</td>
      <td><form method="post" action="/fleet/name"><input type="hidden" name="unit" value="${esc(u.id)}">
        <input name="name" maxlength="40" value="${esc(u.name || '')}" placeholder="name"><button>Save</button></form></td>
    </tr>`;
  }).join('');
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Radome fleet</title>
<style>
  body{font:15px/1.4 system-ui,sans-serif;margin:16px;background:#0f1417;color:#e6e6e6}
  table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #2a3338;text-align:left;vertical-align:top}
  tr.warn td:nth-child(5){color:#ffb44d} tr.ok td:nth-child(5){color:#6fd08c} code{color:#8aa}
  input{background:#1b2226;color:#e6e6e6;border:1px solid #2a3338;padding:4px}
  button{background:#23424f;color:#e6e6e6;border:0;padding:5px 10px;margin-left:4px}
</style></head><body>
<h1>Radome fleet</h1><p>${rows ? '' : 'No unit has reported yet.'}</p>
<table><tr><th>Unit</th><th>Version</th><th>Last report</th><th>Uptime</th><th>Status</th><th></th></tr>${rows}</table>
</body></html>`;
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

async function nameUnit(request, env) {
  // Browsers resend Basic credentials to any page that posts here, so a form
  // on another site could rename units. Only accept this site's own form.
  const origin = request.headers.get('Origin');
  if (!origin || origin !== new URL(request.url).origin) {
    return new Response('cross-site request refused\n', { status: 403 });
  }
  const form = await request.formData();
  const unit = String(form.get('unit') || '');
  const name = String(form.get('name') || '').trim().slice(0, 40) || null;
  await env.DB.prepare('UPDATE units SET name = ? WHERE id = ?').bind(name, unit).run();
  return new Response(null, { status: 303, headers: { Location: '/fleet' } });
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    const m = request.method;
    if (pathname === '/health' && m === 'GET') return json(200, { ok: true });
    if (pathname === '/v1/heartbeat' && m === 'POST') return heartbeat(request, env);
    if (pathname === '/fleet' || pathname === '/fleet.json' || pathname === '/fleet/name') {
      const state = maintainer(request, env);
      if (state !== 'ok') return needAuth(state);
      if (pathname === '/fleet' && m === 'GET') return fleetPage(env);
      if (pathname === '/fleet.json' && m === 'GET') {
        const now = nowS();
        return json(200, (await listUnits(env)).map(u => ({ ...u, payload: undefined, ...assess(u, now) })));
      }
      if (pathname === '/fleet/name' && m === 'POST') return nameUnit(request, env);
    }
    return json(404, { error: 'not found' });
  },
};
