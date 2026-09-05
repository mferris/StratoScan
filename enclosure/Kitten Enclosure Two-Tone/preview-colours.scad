// Colour preview of the two-tone stand. Not a printable part -- this is the
// picture that says whether the split lands where a cat's markings would.
use <kitten-enclosure-twotone.scad>

black = "#1c1c1c";
white = "#f4f4f2";

color(black) part_stand_body();
color(white) part_stand_paws();
color(black) part_stand_toes();
color(black) part_stand_tail();
color(white) part_stand_tail_tip();
