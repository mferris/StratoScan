#!/usr/bin/env python3
"""The app's setup flow over https with the radar's own certificate
(security review 2026-10-04, item 9): a per-unit certificate made on first
boot, lighttpd serving https with it, the setup link naming it (f=...), and
the installer and updater carrying all of it. The app side (RadarSetup.swift)
accepts only the named certificate."""
import hashlib
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent.parent
D = root / "deploy"
fails = 0


def check(cond, msg):
    global fails
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


sh = (D / "tls-cert.sh").read_text()
check("set -eu" in sh and '[ -s "$DIR/unit.pem" ] && exit 0' in sh, "tls-cert.sh is strict and makes the certificate once")
check("openssl req -x509 -newkey ec" in sh and "-nodes" in sh and "-days 7300" in sh, "an EC key, no passphrase, long-lived")
check('install -m 0640 -o root -g www-data "$TMP/unit.pem"' in sh and 'install -m 0644 "$TMP/crt.pem" "$DIR/unit.crt"' in sh,
      "the key is readable by lighttpd only; the certificate by all")
check('install -d -m 0755 -o root -g www-data "$DIR"' in sh, "the directory is open, so the setup server (its own user) can reach the certificate")
svc = (D / "stratoscan-tls-cert.service").read_text()
check("ConditionPathExists=!/etc/stratoscan/tls/unit.pem" in svc and "Before=lighttpd.service" in svc, "the service runs once, before lighttpd")
drop = (D / "lighttpd-stratoscan-tls.conf").read_text()
check("After=stratoscan-tls-cert.service" in drop and "Wants=stratoscan-tls-cert.service" in drop, "lighttpd waits for it")
conf = (D / "85-stratoscan-tls.conf").read_text()
check('$SERVER["socket"] == ":443"' in conf and 'ssl.pemfile = "/etc/stratoscan/tls/unit.pem"' in conf and "mod_openssl" in conf,
      "lighttpd serves https with the certificate")
inst = (D / "install-setup-server.sh").read_text()
for needle in ("lighttpd-mod-openssl", "tls-cert.sh", "stratoscan-tls-cert.service", "lighttpd-stratoscan-tls.conf", "85-stratoscan-tls.conf"):
    check(needle in inst, "the installer carries %s" % needle)
check(inst.index("if live; then sh deploy/tls-cert.sh; fi") < inst.index("lighttpd -tt -f /etc/lighttpd/lighttpd.conf"),
      "on a live unit the certificate exists before lighttpd is checked and reloaded")
check("chmod 0755 /etc/stratoscan/tls" in inst, "the installer opens the directory on a unit built before")
check('"tls-cert.sh",' in (D / "ota.py").read_text(), "an update may carry tls-cert.sh")
swift = (root / "ios" / "StratoScan" / "Setup" / "RadarSetup.swift").read_text()
check("fingerprint" in swift and "SecTrustCopyCertificateChain" in swift and "cancelAuthenticationChallenge" in swift,
      "the app pins the named certificate")

# The link names the certificate when there is one.
tmp = tempfile.mkdtemp()
crt = os.path.join(tmp, "unit.crt")
os.environ["STRATOSCAN_TLS_CERT"] = crt
os.environ.setdefault("STRATOSCAN_SETUP_STATE", tmp)
spec = importlib.util.spec_from_file_location("ss", D / "setup-server.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
link = ss.setup_link("ABCD-1234", {"active": True, "ssid": "StratoScan-Setup", "psk": "secretsecret", "address": "10.42.0.1"})
check(link and "&f=" not in link, "no certificate, no f= in the link (older units keep http)")
# A certificate that exists but can't be read is not the same as none: it is said out loud.
import io, contextlib, stat as _stat
closed = os.path.join(tmp, "closed"); os.makedirs(closed); open(os.path.join(closed, "unit.crt"), "w").write("x")
os.chmod(closed, 0)
ss.TLS_CERT = os.path.join(closed, "unit.crt")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    fp_unreadable = ss.tls_fingerprint()
os.chmod(closed, 0o755)
if os.getuid() == 0:
    print("skip the unreadable-certificate check needs an unprivileged user")
else:
    check(fp_unreadable is None and "exists but can't be used" in buf.getvalue() and "PermissionError" in buf.getvalue(),
          "an unreadable certificate is reported, not passed off as none")
ss.TLS_CERT = crt
made = subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                       "-days", "2", "-subj", "/CN=test", "-keyout", os.path.join(tmp, "k.pem"), "-out", crt],
                      capture_output=True).returncode == 0
if made:
    der = subprocess.run(["openssl", "x509", "-in", crt, "-outform", "DER"], capture_output=True).stdout
    fp = hashlib.sha256(der).hexdigest()
    check(ss.tls_fingerprint() == fp, "the fingerprint is the SHA-256 of the certificate's DER form")
    link = ss.setup_link("ABCD-1234", {"active": True, "ssid": "StratoScan-Setup", "psk": "secretsecret", "address": "10.42.0.1"})
    check(link.endswith("&f=" + fp) and len(fp) == 64, "and the link ends with it")
else:
    print("skip openssl not usable here; fingerprint checks skipped")
print("setup tls checks passed" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
