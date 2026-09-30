// Quiet hours (roadmap 4.7): the window logic in index.html, run under Node.
// Usage: node tests/test_quiet_hours.cjs [index.html]
const s = require("fs").readFileSync(process.argv[2] || require("path").join(__dirname, "..", "index.html"), "utf8");
const grab = re => s.match(re)[0];
eval([grab(/function minutesToClock[\s\S]*?\n\}/), grab(/function inQuietHours[\s\S]*?\n\}/), grab(/function soundAllowedNow[\s\S]*?\n\}/)].join("\n"));
var alertSettings = { quietHours: true, quietFrom: 1320, quietTo: 420, quietSunset: false, muted: false };
var quietEmergencyUntil = 0;
function isNightAtReceiver() { return true; }
const at = (h, m) => new Date(2026, 8, 30, h, m);
let fails = 0;
const check = (ok, what) => { console.log((ok ? "ok   " : "FAIL ") + what); if (!ok) fails++; };
for (const [h, m, want] of [[21,59,false],[22,0,true],[23,30,true],[0,0,true],[6,59,true],[7,0,false],[12,0,false]])
  check(inQuietHours(at(h, m)) === want, `22:00-07:00 at ${minutesToClock(h*60+m)} -> ${want}`);
Object.assign(alertSettings, { quietFrom: 780, quietTo: 840 });
check(inQuietHours(at(13,30)) && !inQuietHours(at(14,0)), "same-day window 13:00-14:00");
Object.assign(alertSettings, { quietFrom: 600, quietTo: 600 });
check(!inQuietHours(at(10,0)), "equal times mean no quiet, not all day");
alertSettings.quietSunset = true;
check(inQuietHours(at(12,0)), "sunset-to-sunrise follows isNightAtReceiver");
alertSettings.quietHours = false;
check(!inQuietHours(at(23,0)), "off means never quiet");
Object.assign(alertSettings, { quietHours: true, quietSunset: false, quietFrom: 0, quietTo: 1439 });
check(!soundAllowedNow(), "silent inside the window");
quietEmergencyUntil = Date.now() + 5000;
check(soundAllowedNow(), "an emergency window lets sound through");
alertSettings.muted = true;
check(!soundAllowedNow(), "mute still wins over everything");
process.exit(fails ? 1 : 0);
