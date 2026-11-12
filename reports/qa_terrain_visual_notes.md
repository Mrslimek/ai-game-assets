# qa_terrain visual self-check notes

Viewed with the Read tool (images rendered successfully). Files are in
`assets/qa/terrain/`. These are grounded observations, not pass/fail judgments.

## atlas_blob47_labeled_x4.png
All 47 slots are filled with distinct tiles (slot 47 empty as expected in the 8x6
grid). Tile 0 is pure dirt and tile 46 pure grass; the corner tiles (e.g. 1, 5, 8,
16, 33) show grass quarter-blobs with visibly rounded arcs at the dirt boundary —
no hard 90-degree corners remain. Inner-corner tiles (e.g. 4, 7, 24) show the
concave quarter-disc bulges meeting the tile edges cleanly, and the red slot
borders confirm each quadrant's arc terminates exactly at the tile edge.

## atlas_wang16_labeled_x4.png
Bit ordering matches the renderer: tile 1 shows grass only in its top-left (NW)
quadrant, tile 3 grass across the top half (NW+NE), tile 4 grass only bottom-left
(SW), tile 15 fully grass — consistent with index = NW + 2*NE + 4*SW + 8*SE.
Borders between quadrants are hard straight edges (inherent to the Wang16
quadrant-paste design), so this set gives blocky staircase borders rather than
smooth corners.

## transition_grass-water_12x12_x4.png
The island reads clearly (grass mass on water), but the shoreline is a blocky
staircase of half-tile quadrant steps with no smoothing — consistent with Wang16
dual-grid rendering, not a defect of the seamlessness of the underlying tiles.
No visible lattice lines or brightness drift across the water region; texture
continuity inside each terrain region looks uniform.

## mixed_30x30_seed7_x4.png
Elevation bands read correctly: water (deep blue) -> sand ring -> dirt -> grass ->
stone core, with value-noise-perturbed boundaries. The band borders are again hard
Wang16 quadrant steps; notable artifacts are small isolated sand fragments
(e.g. top-left sliver) and the diagonal sand/dirt staircase banding on the east
side, which read as noise rather than seams. After the water-fill fix there are no
black/transparent holes left in the composite.

## repetition_30x30_grass_32_x4.png
Uniform grass field with no visible tile grid lines, no repeated-feature
"wallpaper" pattern detectable at this scale, and no banding or brightness drift
across the 960x960 map. The measured shared-edge pixel diff for this map
(8.92 gray levels) is invisible at viewing scale but is the honest reason the
tiles are not mathematically pixel-identical at their rolled edges.

## sanity_blob47_island_16x16_seed1.png (additional)
The grass island edge is scalloped with smooth round inner/outer corner arcs —
this is the true 47-tile blob look; no grid lines, no corner notches, no visible
state mismatches anywhere along the boundary.
