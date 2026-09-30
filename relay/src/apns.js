// Apple Push Notification service, token-based (roadmap 2.1).
//
// The .p8 signing key lives only in the relay's secrets (APNS_KEY), set by
// the maintainer with `wrangler secret put`; units never hold anything that
// can push. Key id, team id and topic are not secret (wrangler.toml [vars]).
//
// APNs speaks only HTTP/2. A Worker's fetch() is HTTP/1.1 to Cloudflare's
// edge, which talks HTTP/2 to Apple on its behalf -- so this works deployed,
// and cannot be exercised against Apple from a local runtime.

const enc = new TextEncoder();
const b64url = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

let cached = null;   // { jwt, iat, keyId }: Apple wants one token reused for 20-60 minutes

async function signingKey(pem) {
  const b64 = String(pem).replace(/-----[^-]+-----/g, '').replace(/\s+/g, '');
  const der = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  return crypto.subtle.importKey('pkcs8', der, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
}

export async function providerToken(env, nowS) {
  if (cached && cached.keyId === env.APNS_KEY_ID && nowS - cached.iat < 45 * 60) return cached.jwt;
  const header = b64url(enc.encode(JSON.stringify({ alg: 'ES256', kid: env.APNS_KEY_ID })));
  const claims = b64url(enc.encode(JSON.stringify({ iss: env.APNS_TEAM_ID, iat: nowS })));
  const key = await signingKey(env.APNS_KEY);
  // WebCrypto's ECDSA signature is already the raw r||s form JWS wants.
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, enc.encode(`${header}.${claims}`));
  cached = { jwt: `${header}.${claims}.${b64url(sig)}`, iat: nowS, keyId: env.APNS_KEY_ID };
  return cached.jwt;
}

export const configured = env => !!(env.APNS_KEY && env.APNS_KEY_ID && env.APNS_TEAM_ID && env.APNS_TOPIC);

// Sends one notification. Returns { ok, status, reason, dead } -- dead means
// the token will never work again (the app was deleted, or the token is
// for the other environment) and should be forgotten.
export async function send(env, phone, notification, nowS, fetchImpl = fetch) {
  const host = phone.env === 'sandbox' ? 'api.sandbox.push.apple.com' : 'api.push.apple.com';
  const live = notification.liveActivity === true;
  const headers = {
    authorization: `bearer ${await providerToken(env, nowS)}`,
    // Live Activity pushes have their own type and topic.
    'apns-topic': live ? `${env.APNS_TOPIC}.push-type.liveactivity` : env.APNS_TOPIC,
    'apns-push-type': live ? 'liveactivity' : 'alert',
    'apns-priority': notification.urgent ? '10' : '5',
    // A stale "helicopter nearby" is worse than none.
    'apns-expiration': String(nowS + (notification.urgent ? 3600 : 600)),
  };
  if (notification.collapseId) headers['apns-collapse-id'] = notification.collapseId.slice(0, 64);
  let r;
  try {
    r = await fetchImpl(`https://${host}/3/device/${notification.token || phone.token}`, {
      method: 'POST', headers, body: JSON.stringify(notification.payload),
    });
  } catch (e) {
    return { ok: false, status: 0, reason: 'unreachable', dead: false };
  }
  if (r.status === 200) return { ok: true, status: 200 };
  let reason = '';
  try { reason = (await r.json()).reason || ''; } catch { /* no body */ }
  const dead = r.status === 410 || (r.status === 400 && ['BadDeviceToken', 'DeviceTokenNotForTopic'].includes(reason));
  return { ok: false, status: r.status, reason, dead };
}

// ---- what a notification says --------------------------------------------------
// Aircraft only, like the event it comes from: never a position.

const ft = n => `${Number(n).toLocaleString('en-US')} ft`;

function details(e) {
  const who = e.flight || e.reg || e.hex?.toUpperCase();
  const parts = [who, e.type].filter(Boolean);
  if (typeof e.alt_ft === 'number') parts.push(e.alt_ft <= 0 ? 'on the ground' : ft(e.alt_ft));
  if (typeof e.dist_nm === 'number') {
    const mi = e.dist_nm * 1.15078;
    parts.push(`${mi < 1 ? 'under a mile' : `${Math.round(mi)} mi`}${e.dir ? ' ' + e.dir : ''}`);
  }
  return parts.join(' · ');
}

const TITLES = {
  emergency: e => `Emergency${e.squawk ? ` · squawk ${e.squawk}` : ''}`,
  notable: e => e.label || 'Notable aircraft',
  low_overhead: () => 'Low overhead',
  helicopter: () => 'Helicopter nearby',
  test: () => 'StratoScan test',
};

export function notificationFor(event, unit) {
  const title = (TITLES[event.kind] || (() => 'StratoScan'))(event);
  let body = event.kind === 'test' ? (event.label || 'Notifications from this radar are working.') : details(event);
  if (event.kind === 'emergency' && event.label) body = `${event.label[0].toUpperCase()}${event.label.slice(1)} · ${body}`;
  if (event.kind === 'notable' && event.operator) body = `${event.operator} · ${body}`;
  return {
    urgent: event.kind === 'emergency',
    collapseId: event.hex ? `${event.kind}-${event.hex}` : undefined,
    payload: {
      aps: {
        alert: { title, body },
        sound: event.kind === 'emergency' ? 'default' : undefined,
        'thread-id': unit,
        'interruption-level': event.kind === 'emergency' ? 'time-sensitive' : 'active',
      },
      radome: { unit, kind: event.kind, hex: event.hex },
    },
  };
}

// When one request carries more alerts than a phone should get at once.
export function summaryFor(n, unit) {
  return {
    urgent: false,
    collapseId: `summary-${unit.slice(0, 20)}`,
    payload: {
      aps: { alert: { title: 'More aircraft', body: `${n} more alert${n === 1 ? '' : 's'} from this radar` },
             'thread-id': unit, 'interruption-level': 'passive' },
      radome: { unit, kind: 'summary' },
    },
  };
}

// ---- Live Activity: an aircraft about to pass over ------------------------------
// ContentState and Attributes mirror ios/Shared/ApproachActivity.swift exactly.
// The card counts down on the phone by itself; the relay only starts and ends it.

function approachState(e, nowS, passed) {
  const s = { etaUnix: nowS + (e.eta_s || 0), passed };
  if (typeof e.alt_ft === 'number') s.altFt = e.alt_ft;
  if (typeof e.dist_nm === 'number') s.distNm = e.dist_nm;
  if (e.dir) s.dir = e.dir;
  return s;
}

export function approachStart(e, unit, startToken, nowS) {
  const who = e.flight || e.reg || e.hex.toUpperCase();
  return {
    liveActivity: true,
    urgent: true,
    token: startToken,
    payload: {
      aps: {
        timestamp: nowS,
        event: 'start',
        'attributes-type': 'ApproachAttributes',
        attributes: { unit, hex: e.hex, callsign: who, type: e.type || '', reason: e.label || '' },
        'content-state': approachState(e, nowS, false),
        'stale-date': nowS + (e.eta_s || 0) + 120,
        alert: { title: `${e.label || 'Aircraft'} approaching`, body: `${who}${e.type ? ' · ' + e.type : ''} · overhead in about ${Math.max(1, Math.round((e.eta_s || 0) / 60))} min` },
      },
    },
  };
}

export function approachEnd(e, activityToken, nowS) {
  return {
    liveActivity: true,
    urgent: false,
    token: activityToken,
    payload: {
      aps: {
        timestamp: nowS,
        event: 'end',
        'content-state': { etaUnix: nowS, passed: true },
        'dismissal-date': nowS + 120,
      },
    },
  };
}
