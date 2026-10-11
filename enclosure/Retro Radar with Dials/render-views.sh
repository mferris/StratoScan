#!/bin/sh
# Renders the pictures in images/ from retro-dials.scad.
# Usage: sh render-views.sh
set -eu
O=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
DIR=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$DIR/images"
r() {  # name, part, camera, size, projection
    "$O" -o "$DIR/images/$1.png" --render --backend=manifold --colorscheme=Tomorrow \
        --autocenter --viewall -D "dpart=\"$2\"" --camera="$3" --imgsize="$4" --projection="$5" \
        "$DIR/retro-dials.scad" >/dev/null 2>&1 && echo "  images/$1.png"
}
r stand-left   in_stand  0,0,0,68,0,-28,0  1600,1300 p
r stand-right  in_stand  0,0,0,70,0,30,0   1600,1300 p
r front        in_stand  0,0,0,72,0,0,0    1500,1500 o
r arc-closeup  arc_closeup 0,0,0,58,0,-20,0 1400,1100 p
r exploded     exploded  0,0,0,62,0,35,0   1600,1300 p
r knob         knob      0,0,0,55,0,25,0   900,900   p
r jewel        jewel     0,0,0,60,0,25,0   900,900   p
