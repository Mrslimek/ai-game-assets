# game-asset-pack-v1

Phase-2 QA production pack. Assembled 2026-11-12. Pixel sizes are nominal; the pack
assumes the game displays tiles/sprites at any 2x/4x scale it chooses — **no scaling
is baked into any asset**.

## Contents

| Folder | Contents |
|---|---|
| `tiles/` | 6 tier-1 seamless 16-color terrain tiles (grass/dirt/water, 32+64px) + 4 tier-2 tiles (sand/stone) |
| `autotiles/` | 3 blob47 atlases (grass-dirt, grass-water, dirt-stone), 1 wang16 atlas (grass-water), 20x20 demo islands (+x4) per pair |
| `icons/` | 16 final 32x32 icons + `atlas_4x4.png` (4x4 grid, row-major) |
| `characters/` | knight front/side/back/three_quarter (64px), turntable GIFs (600ms/frame), contact sheet, 39-color palette |
| `animations/` | knight idle/walk/attack registered 64x64 sheets + 64px and 256px GIFs at 10fps |
| `hd/` | 6 high-res rekeyed renders (chest, crystal, mana potion; 256/512) |
| `metadata/` | `palettes.json`, `atlas_icons.json`, `animations.json`, `autotiles/*.json`, before/after icon board |

`manifest.json` lists every asset with status (READY / NEEDS_WORK), QA metrics
(exact values from `reports/qa_*.json` and `reports/qa_v2_campaign.json`), and the
processing log.

## Tier explanation

- **tier-1 (READY)**: passed seam, palette, and connectivity QA. Safe to ship.
- **tier-2 (NEEDS_WORK)**: included but flawed — measurable edge seams and visible
  wallpapering on large repetition. Usable for prototypes or sparse placement.
- Icons marked NEEDS_WORK have concrete structural defects (see manifest notes).

## Honest limitations

- **sand/stone tiles**: measurable seams (e.g. sand_32 avg_row_seam 20.70) and
  wallpapering (autoperiod_strength up to 0.60 on sand_64). Do not use for large areas.
- **7 icons NEEDS_WORK**: dagger (hilt/blade disconnected), bow, staff, potion_gold,
  helmet, scroll, gem (detached sparkle fragments).
- **Animation motion subtle**: knight idle/walk/attack have small inter-frame deltas
  (post centroid spread 0.04–0.76px); OpenPose adherence was partial.
- **crystal 512**: minor purple/pink border shards remain on the boundary — crop 2px
  or accept; recommend crop.
- **HD assets**: binary alpha edges are 1px-jagged after rekeying; either apply a
  slight game-side smoothing or accept as-is.

## Licensing

See `../../research/licenses.md` for generation-model licensing terms.

## Regeneration

Autotile atlases/demos were rebuilt at pack time with the fixed 47-tile blob builder:
`python3 scripts/build_autotile_map.py --overlay <tile> --base <tile> --type blob47`.
The full pack assembly (copying, icon processing, GIFs, manifest) is reproducible with
`python3 scripts/build_asset_pack.py`.
