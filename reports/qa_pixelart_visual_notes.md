# Pixel-art visual notes

Inspected with the Read tool on `assets/qa/pixelart/icons_4x.png` and
`icons_before_after_4x.png` and `icons_native.png` and `atlas_grid_4x.png`.
Cell references are row/col of the 4x4 grid (row 1 = top).
Every numeric claim was cross-checked against `reports/qa_pixelart.json`.
All observations below were made by directly viewing the rendered sheets.

## Per-icon silhouette readability at 32x32

- r1c1 weapon_sword — READABLE. Clean diagonal blade plus crossguard plus pommel. One dominant component (89.68% of opaque pixels).
- r1c2 weapon_dagger — FRAGMENTED. Hilt and pommel sit in the upper half and the pale blade is a separate diagonal sliver below. Largest component only 49.18%. Reads as a broken dagger at 32x32.
- r1c3 weapon_bow — FRAGMENTED but recognizable. Two brown arcs with no string. Largest component 56.69%. It reads only because the two arcs share a curve.
- r1c4 weapon_staff — READABLE with ambiguity. Brown shaft plus blue orb. The green leaf cluster around the orb makes it read as a small tree at first glance.
- r2c1 potion_health — NOISE-LIKE. Smallest silhouette in the set. A 38 px flask plus a detached 13 px dot plus two 1 px speckles (4 components). Reads as a smear at 32x32. Worst icon.
- r2c2 potion_mana — READABLE. Blue round flask with cork. Single component (100%).
- r2c3 potion_stamina — READABLE. Green flask with dark label band and red cap.
- r2c4 potion_gold — CONFUSING. The dominant feature is a yellow star shape on a green bottle. The gold-coin association is weak.
- r3c1 armor_helmet — WEAK. Greenish rounded dome with a dark horizontal band. The visor slit is unclear.
- r3c2 armor_chest — NOISY. Dark mass with white highlight pixels on both shoulders and a pale center. 12 connected components (largest 87.68%). The interior reads as dithered noise.
- r3c3 armor_shield — READS AS A SPIRAL. Brown concentric arc fragments. 13 components and largest only 54.81%. Looks like a coil at 32x32 — not a shield.
- r3c4 armor_boots — READABLE. Single brown boot. 1 component (100%).
- r4c1 craft_ore — READABLE. Brown rock mass with gold flecks.
- r4c2 craft_gem — MIXED. Clean cyan egg center plus detached cyan comma fragments floating around it (10 components; largest 74.36%). The fragments read as sparkles or noise.
- r4c3 craft_scroll — READABLE. Tan scroll with rolled ends. The four red corner marks look like keying artifacts rather than design.
- r4c4 craft_feather — MISREADS AS A FLOWER. Purple bud on a green stem with leaves. Nothing about it reads "feather" at 32x32.

Icons that read as noise or are unrecognizable: potion_health (worst) and
armor_shield (spiral) and craft_feather (flower) and craft_gem (floating
fragments) and armor_chest (interior dither).

## Stray pixels (speckle)

- 10 isolated opaque pixels (all 8 neighbors transparent) across 6 icons: potion_health 1 and armor_helmet 1 and armor_chest 3 and armor_shield 2 and craft_gem 2 and craft_feather 1.
- Verified example: the potion_health speckle sits at x=17 y=13.
- All 10 were removed in `assets/improved/icons/`. Removal cannot disconnect anything by construction.
- Larger detached fragments (the 13 px health dot and the gem commas) are NOT speckle and were deliberately kept.

## AA remnants

- semi_transparent_pixels = 0 for every icon and every knight view and every anim frame. No alpha-based anti-aliasing survives the keying.
- Keying garbage remains as opaque-adjacent RGB variants: each icon keeps 6–15 distinct RGB colors under alpha=0 (visible only with alpha inspection — invisible in render).
- Blended-color remnants were quantized INTO the opaque palettes instead: visible as the muddy white/grey shoulder highlights on armor_chest and the pale center blotch on armor_helmet.

## Outline consistency

- No consistent outline anywhere in the original set. Each icon has 11–16 distinct colors on its silhouette boundary and the most common boundary color covers only 16–30% of the boundary.
- The 16 icons have 16 DIFFERENT most-common boundary colors:

| icon | most common boundary color | share |
|---|---|---|
| weapon_sword | #585D4EFF | 21.35% |
| weapon_dagger | #B2BDCEFF | 21.82% |
| weapon_bow | #45604CFF | 20.00% |
| weapon_staff | #611E23FF | 16.07% |
| potion_health | #63212FFF | 27.78% |
| potion_mana | #1E4E6EFF | 19.23% |
| potion_stamina | #273F32FF | 28.17% |
| potion_gold | #4D5648FF | 24.14% |
| armor_helmet | #475C4DFF | 24.32% |
| armor_chest | #2B2A22FF | 21.94% |
| armor_shield | #7A472AFF | 18.60% |
| armor_boots | #62281CFF | 24.59% |
| craft_ore | #5F4023FF | 16.00% |
| craft_gem | #2E4943FF | 30.00% |
| craft_scroll | #885D3EFF | 18.35% |
| craft_feather | #56447DFF | 20.34% |

- Visible in `icons_4x.png`: the dagger rims bright silver; the scroll has red corner pixels; the mana and stamina bottles have no dark rim at all.
- Knight views are equally inconsistent: front #672520FF / side #4D4140FF / back #4C4547FF / three_quarter #611E1AFF.

## Unintended gradients and dithering

- armor_chest interior is dithered noise (quantization remnant of smooth SDXL shading).
- armor_helmet shows a soft shaded band across the dome that quantized into a muddy stripe.
- craft_ore and potion_gold carry speckled highlight clusters that read as quantized gradient remnants (possibly intended as ore sparkle and label shine — ambiguous).
- No smooth gradients survive quantization anywhere else; shading elsewhere is flat and clean.

## Before/after (outline unification to the set median #4E4E3EFF)

- Left column = original. Right column = improved. Sheet: `icons_before_after_4x.png`.
- The improved set gains a uniform dark-olive rim on every silhouette. Internal colors are untouched.
- craft_scroll's red corner specks are replaced by olive.
- The potion_health detached dot SURVIVES (a 13 px component is not a 1 px speckle).
- The armor_chest and armor_helmet white highlights survive (they are interior pixels not boundary pixels).
- No icon is visibly damaged; silhouettes are bit-identical apart from rim recolors and the 10 speckle removals.
- Verdict: the applied fixes are safe and visibly beneficial but purely cosmetic.

## Atlas grid

- `atlas_grid_4x.png` shows the generated 128x128 atlas upscaled 4x with cell indices 0–15.
- Cell order matches the icon list row-major (sword / dagger / bow / staff // health / mana / stamina / gold // helmet / chest / shield / boots // ore / gem / scroll / feather).
- No bleed between cells; every icon keeps transparent padding inside its 32x32 cell.
- Rebuilt improved atlas `assets/improved/atlas/inventory_icons_atlas_4x4.png` verified as 128x128 RGBA holding the 16 improved icons.

## Palette numbers (exact)

- Every icon has exactly 16 opaque colors (pipeline-enforced) plus 6–15 transparent RGB variants. Total unique colors per icon range 22–31.
- Union of the 16 icons: 429 RGBA colors (256 opaque). All pairwise palette Jaccard = 0.0 in both RGBA and opaque-only matrices — every icon owns a fully disjoint palette.
- Union of the 4 knight views: 119 RGBA (64 opaque = 4x16 with zero sharing). All pairwise Jaccard = 0.0.
- semi_transparent_pixels = 0 on all 24 measured assets.

## Honesty caveat

- "No algorithmic defect remaining" is NOT "production ready".
- 5 of 16 icons read poorly at 32x32 because of fragmentation or subject ambiguity — that requires regeneration rather than post-processing.
- The 16-color-per-image claim is technically true for opaque pixels only and says nothing about quality.
