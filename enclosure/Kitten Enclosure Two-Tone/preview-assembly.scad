// Whole-unit preview: head seated in the stand. Must live beside the
// design -- `use <>` resolves relative to THIS file, so a copy elsewhere
// silently renders nothing at all.
use <kitten-enclosure-twotone.scad>
// `use <>` imports modules and functions but NOT special variables, so the
// design's own $fa/$fs do not come with them. Without these two lines this
// renders at OpenSCAD's defaults ($fa=12, $fs=2) and shows a faceting that
// the exported mesh does not have -- a preview that lies about the model.
$fs = 0.4;
$fa = 0.5;
outer_dia=223.34; shell_depth=56; base_h=16; stand_angle=18;
cradle_id=outer_dia+2; cradle_od=cradle_id+26;
arm_lift = base_h + cradle_od/2 - 3;
color("DimGray") stand();
translate([0,0,arm_lift]) rotate([90-stand_angle,0,0]) translate([0,0,-shell_depth/2]) {
    color("Gainsboro") shell();
    color("LightPink") translate([0,0,shell_depth+1.62]) front_trim();
}
