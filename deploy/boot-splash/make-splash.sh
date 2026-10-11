#!/bin/sh
# Makes splash.png, the picture a unit shows from power-on until the radar
# paints: the brand's logo-on-dark, 62% of the width (as the page's own
# splash draws it), on the dark theme's background, at the round panel's
# 1080 x 1080. Rendered by Chrome, so it is the same artwork the page shows.
# Usage (on a Mac with Google Chrome): sh deploy/boot-splash/make-splash.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$HERE/../../assets/brand/logo-on-dark.svg" "$TMP/logo.svg"
cat > "$TMP/splash.html" <<'HTML'
<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;width:1080px;height:1080px;background:#0a0d0f;overflow:hidden}
body{display:flex;align-items:center;justify-content:center}
img{width:62%;height:auto;display:block}
</style></head><body><img src="logo.svg" alt=""></body></html>
HTML
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1080,1080 --default-background-color=0a0d0fff \
  --screenshot="$HERE/splash.png" "file://$TMP/splash.html" >/dev/null 2>&1
python3 -c "
import struct; d=open('$HERE/splash.png','rb').read(24); w,h=struct.unpack('>II',d[16:24]); print('splash.png', w, 'x', h); assert (w,h)==(1080,1080)"
