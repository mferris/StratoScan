#!/bin/sh
# Installs the FlightRadar setup server. Idempotent; safe to re-run.
#
# Run from the repo root on the device:
#   sudo sh deploy/install-setup-server.sh
set -e

echo "== creating the unprivileged service account =="
if ! getent group frsetup >/dev/null; then groupadd --system frsetup; fi
if ! getent passwd frsetup >/dev/null; then
  useradd --system --gid frsetup --no-create-home --shell /usr/sbin/nologin frsetup
fi

echo "== installing files =="
install -d -m 0755 /opt/flightradar
install -m 0755 deploy/setupd.py           /opt/flightradar/setupd.py
install -m 0755 deploy/setup-server.py     /opt/flightradar/setup-server.py
install -m 0644 deploy/setup-ui.html       /opt/flightradar/setup-ui.html
install -m 0644 deploy/airports.json       /opt/flightradar/airports.json
install -m 0644 deploy/funnel-gateway.py   /opt/flightradar/funnel-gateway.py

install -m 0644 deploy/flightradar-setupd.service /etc/systemd/system/
install -m 0644 deploy/flightradar-setup.service  /etc/systemd/system/
install -m 0644 deploy/98-flightradar-setup.conf  /etc/lighttpd/conf-available/
ln -sf /etc/lighttpd/conf-available/98-flightradar-setup.conf \
       /etc/lighttpd/conf-enabled/98-flightradar-setup.conf

echo "== verifying lighttpd config before touching the running server =="
lighttpd -tt -f /etc/lighttpd/lighttpd.conf

echo "== enabling =="
systemctl daemon-reload
systemctl enable --now flightradar-setupd.service
systemctl enable --now flightradar-setup.service
systemctl restart flightradar-funnel-gateway.service
systemctl reload lighttpd

echo "== verifying /setup is refused on the public tunnel =="
fail=0
for p in /setup /./setup /x/../setup /%73etup /wake /%77ake; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --path-as-is -X POST \
         -H 'Content-Length: 0' "http://127.0.0.1:8085$p")
  [ "$code" = "404" ] || { echo "  FAIL: $p returned $code via the public gateway"; fail=1; }
done
[ "$fail" = "0" ] && echo "  all privileged paths refused publicly"
[ "$fail" = "0" ] || { echo "REFUSING TO FINISH: the public filter is not working"; exit 1; }

echo
echo "Setup page:  http://$(hostname -I | awk '{print $1}')/setup"
echo "Claim code:  shown below (also in /run/flightradar/claim-code)"
cat /run/flightradar/claim-code 2>/dev/null || echo "  (not generated yet)"
