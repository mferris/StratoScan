// Fleets (roadmap 1.13): a group of radars with its own administrators.
//
// * The maintainer creates a fleet on /fleet and gets two secrets, each shown
//   once: an INVITE CODE for radar owners, and an ADMINISTRATOR LINK. Only
//   their SHA-256s are stored.
// * A radar joins only when its owner enters the invite code (on its setup
//   page): the unit sends it, signed, to /v1/unit/fleet. It can leave the same
//   way at any time. A radar is in at most one fleet.
// * An administrator opens their link once; it sets a cookie and redirects,
//   so the secret doesn't stay in the address bar. Their page shows their
//   fleet's radars and nothing else: health (from the opt-in health reports,
//   which joining turns on), the radar's name and its public page's visit
//   counts. Never a location -- reports carry none -- nor phones or alerts.
//
// Kept separate from index.js, which hands in the helpers it shares.

import { sha256Hex } from './auth.js';

export const FLEET_COOKIE = 'stratoscan_fleet';
export const MAX_FLEETS = 200;
const CODE_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';   // Crockford base32: no I, L, O, U

function randomCode() {
  const b = crypto.getRandomValues(new Uint8Array(12));
  const c = [...b].map(x => CODE_ALPHABET[x % 32]).join('');
  return `${c.slice(0, 4)}-${c.slice(4, 8)}-${c.slice(8)}`;   // 60 bits
}

// What an owner types: any case, spaces or dashes, and the usual slips.
export function normaliseCode(v) {
  if (typeof v !== 'string') return null;
  const c = v.toUpperCase().replace(/[\s-]/g, '').replace(/O/g, '0').replace(/[IL]/g, '1');
  return /^[0-9A-HJKMNP-TV-Z]{12}$/.test(c) ? c : null;
}

function randomToken() {
  const b = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

const hashOf = async s => sha256Hex(new TextEncoder().encode(s));

function cookieToken(request) {
  const m = /(?:^|;\s*)stratoscan_fleet=([A-Za-z0-9_-]{43})(?:;|$)/.exec(request.headers.get('Cookie') || '');
  return m ? m[1] : null;
}

const HTML_HEADERS = {
  'Content-Type': 'text/html; charset=utf-8',
  'Cache-Control': 'no-store',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
};

const STYLE = `body{font:15px/1.4 system-ui,sans-serif;margin:16px;background:#0f1417;color:#e6e6e6}
  table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #2a3338;text-align:left;vertical-align:top}
  .warn{color:#ffb44d}.ok{color:#6fd08c}code{color:#8aa}.secret{font-size:1.3em;letter-spacing:.06em;color:#fff;background:#1b2226;padding:6px 10px;display:inline-block}
  input{background:#1b2226;color:#e6e6e6;border:1px solid #2a3338;padding:4px}
  button{background:#23424f;color:#e6e6e6;border:0;padding:5px 10px;margin-left:4px}`;

function page(title, body, status = 200) {
  return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${title}</title><style>${STYLE}</style></head>
<body>${body}</body></html>`, { status, headers: HTML_HEADERS });
}

function sameSite(request) {
  const origin = request.headers.get('Origin');
  return !!origin && origin === new URL(request.url).origin;
}

export function fleetRoutes({ json, signedJson, nowS, maintainer, needAuth, assess, esc, ago }) {
  // ---- the radar's side -------------------------------------------------------
  async function unitJoin(request, env) {
    const { auth, payload, error } = await signedJson(request, 'X-FR-Unit');
    if (error) return error;
    const code = normaliseCode(payload.code);
    if (!code) return json(400, { error: 'That doesn’t look like an invite code.' });
    const fleet = await env.DB.prepare('SELECT id, name FROM fleets WHERE invite_hash = ?')
      .bind(await hashOf(code)).first();
    if (!fleet) return json(404, { error: 'That invite code isn’t right, or has been replaced.' });
    await env.DB.prepare(
      `INSERT INTO fleet_members (unit, fleet, joined) VALUES (?1, ?2, ?3)
       ON CONFLICT(unit) DO UPDATE SET fleet = ?2, joined = ?3`
    ).bind(auth.unit, fleet.id, nowS()).run();
    return json(200, { ok: true, fleet: { name: fleet.name } });
  }

  async function unitLeave(request, env) {
    const { auth, error } = await signedJson(request, 'X-FR-Unit');
    if (error) return error;
    await env.DB.prepare('DELETE FROM fleet_members WHERE unit = ?').bind(auth.unit).run();
    return json(200, { ok: true, fleet: null });
  }

  async function unitStatus(request, env) {
    const { auth, error } = await signedJson(request, 'X-FR-Unit');
    if (error) return error;
    const row = await env.DB.prepare(
      'SELECT f.name FROM fleet_members m JOIN fleets f ON f.id = m.fleet WHERE m.unit = ?'
    ).bind(auth.unit).first();
    return json(200, { fleet: row ? { name: row.name } : null });
  }

  // ---- the maintainer's side: creating fleets and their secrets ---------------
  async function fleetsSection(env) {
    const { results } = await env.DB.prepare(
      `SELECT f.id, f.name, f.created, (SELECT COUNT(*) FROM fleet_members m WHERE m.fleet = f.id) AS radars,
              (SELECT COUNT(*) FROM fleet_admins a WHERE a.fleet = f.id) AS admins
         FROM fleets f ORDER BY f.created`
    ).all();
    const rows = (results || []).map(f => `<tr><td><b>${esc(f.name)}</b></td><td>${f.radars}</td><td>${f.admins}</td>
      <td><form method="post" action="/fleet/fleets/invite"><input type="hidden" name="fleet" value="${esc(f.id)}"><button>New invite code</button></form></td>
      <td><form method="post" action="/fleet/fleets/admin"><input type="hidden" name="fleet" value="${esc(f.id)}">
        <input name="label" maxlength="40" placeholder="who (optional)"><button>New administrator link</button></form></td></tr>`).join('');
    return `<h2>Fleets</h2>
      <table><tr><th>Fleet</th><th>Radars</th><th>Administrators</th><th></th><th></th></tr>${rows}</table>
      <form method="post" action="/fleet/fleets/new" style="margin-top:10px">
        <input name="name" maxlength="40" placeholder="New fleet's name" required>
        <input name="label" maxlength="40" placeholder="its first administrator (optional)">
        <button>Create fleet</button></form>`;
  }

  async function newInvite(env, fleetId) {
    const code = randomCode();
    await env.DB.prepare('UPDATE fleets SET invite_hash = ? WHERE id = ?').bind(await hashOf(normaliseCode(code)), fleetId).run();
    return code;
  }

  async function newAdmin(env, fleetId, label) {
    const token = randomToken();
    await env.DB.prepare('INSERT INTO fleet_admins (fleet, label, token_hash, created) VALUES (?, ?, ?, ?)')
      .bind(fleetId, label || null, await hashOf(token), nowS()).run();
    return token;
  }

  function shownOnce(request, fleetName, code, token) {
    const link = token ? `${new URL(request.url).origin}/f/${token}` : null;
    return page('StratoScan fleet', `<h1>${esc(fleetName)}</h1>
      <p>These are shown <b>once</b>. Copy them now: only their fingerprints are kept, so they can be replaced but not shown again.</p>
      ${code ? `<p>Invite code, for radar owners to enter on their radar's setup page:<br><span class="secret">${esc(code)}</span></p>` : ''}
      ${link ? `<p>Administrator link. Whoever opens it can see this fleet's radars; send it only to the administrator:<br><span class="secret"><code>${esc(link)}</code></span></p>` : ''}
      <p><a href="/fleet" style="color:#8cf">Back to the fleet page</a></p>`);
  }

  async function maintainerPost(request, env, pathname) {
    if (!sameSite(request)) return new Response('cross-site request refused\n', { status: 403 });
    const form = await request.formData();
    const name = String(form.get('name') || '').trim().slice(0, 40);
    const label = String(form.get('label') || '').trim().slice(0, 40);
    const fleetId = String(form.get('fleet') || '');
    if (pathname === '/fleet/fleets/new') {
      if (!name) return new Response('a fleet needs a name\n', { status: 400 });
      const { n } = await env.DB.prepare('SELECT COUNT(*) AS n FROM fleets').first();
      if (n >= MAX_FLEETS) return new Response('too many fleets\n', { status: 503 });
      const id = randomToken().slice(0, 16);
      const code = randomCode();
      await env.DB.prepare('INSERT INTO fleets (id, name, invite_hash, created) VALUES (?, ?, ?, ?)')
        .bind(id, name, await hashOf(normaliseCode(code)), nowS()).run();
      return shownOnce(request, name, code, await newAdmin(env, id, label));
    }
    const fleet = await env.DB.prepare('SELECT id, name FROM fleets WHERE id = ?').bind(fleetId).first();
    if (!fleet) return new Response('no such fleet\n', { status: 404 });
    if (pathname === '/fleet/fleets/invite') return shownOnce(request, fleet.name, await newInvite(env, fleet.id), null);
    if (pathname === '/fleet/fleets/admin') return shownOnce(request, fleet.name, null, await newAdmin(env, fleet.id, label));
    return null;
  }

  // ---- the administrator's side -----------------------------------------------
  async function adminFleet(request, env) {
    const token = cookieToken(request);
    if (!token) return null;
    return env.DB.prepare(
      'SELECT f.id, f.name FROM fleet_admins a JOIN fleets f ON f.id = a.fleet WHERE a.token_hash = ?'
    ).bind(await hashOf(token)).first();
  }

  function signInFirst() {
    return page('StratoScan fleet', `<h1>StratoScan fleet</h1>
      <p>Open the administrator link you were sent to sign in to your fleet.</p>`, 401);
  }

  async function adminPage(env, fleet, now) {
    const { results } = await env.DB.prepare(
      `SELECT u.id, u.name, u.last_seen, u.version, u.payload, m.joined
         FROM fleet_members m LEFT JOIN units u ON u.id = m.unit
        WHERE m.fleet = ? ORDER BY m.joined`
    ).bind(fleet.id).all();
    const members = results || [];
    let views7 = 0, visitors7 = 0, healthy = 0;
    const rows = members.map(u => {
      if (!u.last_seen) {
        return `<tr><td><b>Joined, no report yet</b><br><code>${esc(String(u.id || '').slice(0, 10))}…</code></td>
          <td colspan="5">Its first health report should arrive within a few minutes of joining.</td></tr>`;
      }
      const { flags, p } = assess(u, now);
      if (!flags.length) healthy++;
      const days = Array.isArray(p.visits) ? p.visits.slice(-7) : [];
      const v7 = days.reduce((n, d) => n + (Number(d.views) || 0), 0);
      const u7 = days.reduce((n, d) => n + (Number(d.unique) || 0), 0);
      views7 += v7; visitors7 += u7;
      const name = typeof p.name === 'string' && p.name ? p.name.slice(0, 32) : (u.name || '(unnamed)');
      return `<tr><td><b>${esc(name)}</b><br><code>${esc(u.id.slice(0, 10))}…</code></td>
        <td>${esc(u.version || '—')}</td><td>${esc(ago(now - u.last_seen))}</td>
        <td class="${flags.length ? 'warn' : 'ok'}">${flags.length ? esc(flags.join(', ')) : 'healthy'}</td>
        <td>${days.length ? `${v7} views${u7 ? `, ${u7} visitors` : ''}` : '—'}</td>
        <td><form method="post" action="/f/remove"><input type="hidden" name="unit" value="${esc(u.id)}"><button>Remove</button></form></td></tr>`;
    }).join('');
    return page(`${esc(fleet.name)}: StratoScan fleet`, `<h1>${esc(fleet.name)}</h1>
      <p>${members.length} radar${members.length === 1 ? '' : 's'}, ${healthy} healthy.
         Public pages: ${views7} views${visitors7 ? `, ${visitors7} visitors` : ''} in the last 7 days.</p>
      <table><tr><th>Radar</th><th>Version</th><th>Last report</th><th>Status</th><th>Public page, 7 days</th><th></th></tr>${rows}</table>
      <p>Radars join with this fleet's invite code, entered on their own setup page, and their owners can leave at any time.
         You see each radar's health and how many people view its public page; never its location, its phones or its alerts.</p>
      <form method="post" action="/f/invite"><button>Make a new invite code</button> (the old one stops working)</form>`);
  }

  async function route(request, env, pathname, m) {
    // radars
    if (pathname === '/v1/unit/fleet' && m === 'POST') return unitJoin(request, env);
    if (pathname === '/v1/unit/fleet/leave' && m === 'POST') return unitLeave(request, env);
    if (pathname === '/v1/unit/fleet' && m === 'GET') return unitStatus(request, env);

    // the maintainer, behind the fleet page's own password
    if (pathname.startsWith('/fleet/fleets/') && m === 'POST') {
      const state = maintainer(request, env);
      if (state !== 'ok') return needAuth(state);
      return (await maintainerPost(request, env, pathname)) || json(404, { error: 'not found' });
    }

    // administrators: the link signs in once, then a cookie carries it
    const signIn = /^\/f\/([A-Za-z0-9_-]{43})$/.exec(pathname);
    if (signIn && m === 'GET') {
      const ok = await env.DB.prepare('SELECT 1 FROM fleet_admins WHERE token_hash = ?').bind(await hashOf(signIn[1])).first();
      if (!ok) return page('StratoScan fleet', '<h1>StratoScan fleet</h1><p>That link isn’t valid any more. Ask for a new one.</p>', 404);
      return new Response(null, {
        status: 303,
        headers: {
          Location: '/f',
          'Set-Cookie': `${FLEET_COOKIE}=${signIn[1]}; Path=/f; HttpOnly; Secure; SameSite=Strict; Max-Age=31536000`,
          'Referrer-Policy': 'no-referrer',
        },
      });
    }
    if (pathname === '/f' || pathname === '/f/invite' || pathname === '/f/remove') {
      const fleet = await adminFleet(request, env);
      if (!fleet) return signInFirst();
      if (pathname === '/f' && m === 'GET') return adminPage(env, fleet, nowS());
      if (m === 'POST') {
        if (!sameSite(request)) return new Response('cross-site request refused\n', { status: 403 });
        if (pathname === '/f/invite') return shownOnce(request, fleet.name, await newInvite(env, fleet.id), null);
        if (pathname === '/f/remove') {
          const unit = String((await request.formData()).get('unit') || '');
          await env.DB.prepare('DELETE FROM fleet_members WHERE unit = ? AND fleet = ?').bind(unit, fleet.id).run();
          return new Response(null, { status: 303, headers: { Location: '/f' } });
        }
      }
    }
    return null;
  }

  return { route, fleetsSection };
}
