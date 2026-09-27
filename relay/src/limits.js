// Limits and fleet assessment, shared by the Worker and its tests.

export const MAX_BODY = 8192;
export const MIN_INTERVAL_S = 10 * 60;   // a unit reports every 6 h; this only stops floods
export const MAX_UNITS = 500;            // bounds what an unauthenticated first contact can create
export const HISTORY_PER_UNIT = 120;     // ~30 days at one report per 6 h
export const STALE_AFTER_S = 13 * 3600;  // two missed reports


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
  if (p.ota && p.ota.state && !['ok', 'up_to_date'].includes(p.ota.state)) flags.push(`update ${p.ota.state}`);
  return { flags, p };
}

