// Colour preview of the two-tone stand. Not a printable part -- this is the
// picture that says whether the split lands where a cat's markings would.
use <kitten-enclosure-twotone.scad>
// `use <>` imports modules and functions but NOT special variables, so the
// design's own $fa/$fs do not come with them. Without these two lines this
// renders at OpenSCAD's defaults ($fa=12, $fs=2) and shows a faceting that
// the exported mesh does not have -- a preview that lies about the model.
$fs = 0.4;
$fa = 0.5;

black = "#1c1c1c";
white = "#f4f4f2";

color(black) part_stand_body();
color(white) part_stand_paws();
color(black) part_stand_toes();
color(black) part_stand_tail();
color(white) part_stand_tail_tip();
