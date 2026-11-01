#!/bin/sh
# Renders the pictures in images/ from kitten-dials.scad.
# Usage: sh render-views.sh
set -eu
O=/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD
DIR=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$DIR/images"
r() {  # name, part, camera, size, projection, [viewall]
    "$O" -o "$DIR/images/$1.png" --render --backend=manifold --colorscheme=Tomorrow \
        ${6:+--autocenter --viewall} -D "dpart=\"$2\"" --camera="$3" --imgsize="$4" --projection="$5" \
        "$DIR/kitten-dials.scad" >/dev/null 2>&1 && echo "  images/$1.png"
}
r front          in_stand        0,0,0,72,0,0,0      1500,1500 o 1
r three-quarter  in_stand        0,0,0,68,0,-28,0    1600,1300 p 1
r side           in_stand        0,0,0,90,0,-90,0    1500,1300 o 1
r closeup        closeup         0,0,0,40,0,-22,0    1500,1100 p 1
r exploded       exploded        0,0,0,62,0,35,0     1600,1300 p 1
# the sections, each on the plane through the case's axis and one control,
# seen from the side with the face up (the camera centred on the control)
s() {  # name, part, angle
    c=$(python3 -c "import math; a=math.radians($3); print(f'{126*math.cos(a):.1f},{126*math.sin(a):.1f},72')")
    r "$1" "$2" "$c,90,0,$(( $3 - 180 )),190" 1200,1100 o
}
s section-screen section_screen 228
s section-status section_status 270
s section-range  section_range  312
