#!/bin/sh
# This radar's own TLS certificate, for the app's setup flow (security review
# 2026-10-04, item 9). Made once, on the unit itself, so no two radars share
# one. The setup link on the first-run screen carries its SHA-256, and the
# app accepts only that certificate (RadarSetup.swift), so the admin and
# WiFi passwords the app sends cross the setup network encrypted, not just
# by WPA. Browsers keep plain http for the page on the LAN; https (lighttpd,
# 85-stratoscan-tls.conf) is there for the app.
# Run by stratoscan-tls-cert.service before lighttpd, and by the installer.
set -eu
DIR=/etc/stratoscan/tls
[ -s "$DIR/unit.pem" ] && exit 0
install -d -m 0750 -o root -g www-data "$DIR"
TMP=$(mktemp -d)
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 7300 \
  -subj "/CN=StratoScan radar" -addext "subjectAltName=DNS:stratoscan.local,IP:10.42.0.1" \
  -keyout "$TMP/key.pem" -out "$TMP/crt.pem" 2>/dev/null
cat "$TMP/key.pem" "$TMP/crt.pem" > "$TMP/unit.pem"
install -m 0640 -o root -g www-data "$TMP/unit.pem" "$DIR/unit.pem"
install -m 0644 "$TMP/crt.pem" "$DIR/unit.crt"
rm -rf "$TMP"
echo "tls: made this radar's certificate, $(openssl x509 -in "$DIR/unit.crt" -noout -fingerprint -sha256 | cut -d= -f2)"
