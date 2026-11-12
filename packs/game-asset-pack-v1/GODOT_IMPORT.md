# Godot 4.3+ import guide (beginner-friendly)

How to bring this pack into a Godot 4.3+ project so pixel art stays crisp.

## 1. Global settings (do this first)

1. Open **Project Settings > Rendering > Textures > Canvas Textures** and set
   **Default Texture Filter** to **Nearest**. Without this, Godot blurs every
   sprite when it is scaled.
2. Also enable pixel snapping: **Project Settings > Rendering > 2D > Snap** and turn
   on **Snap 2D Transforms to Pixel** (the setting is internally named
   `rendering/2d/snap/snap_2d_transforms_to_pixel`). This stops sprites from landing
   on half-pixels and shimmering while moving.

## 2. Import defaults for the pack's PNGs

1. Select any PNG in the FileSystem dock, then look at the **Import** dock (next to
   Scene in the top-left tabs).
2. Set **Filter** to **Nearest** and **Mipmaps > Generate** to **Off**.
3. Click **Set as Default for "Texture2D"** (or repeat per texture). Then
   **Project > Tools > Reimport all** once so everything picks it up.

## 3. Tiles and autotiling (blob47 atlases)

The three blob47 atlases (`autotiles/atlas_grass_dirt_blob47.png`,
`atlas_grass_water_blob47.png`, `atlas_dirt_stone_blob47.png`) are **256x192 px**:
an **8x6 grid of 32px tiles** holding 47 real tiles (slot 47–48 of the last row are
empty). Each slot index corresponds to a reduced 8-neighbor bitmask — the mapping is
in `metadata/autotiles/<pair>.json` (`"mapping"`: bitmask -> slot index).

Steps:

1. Create a **TileMapLayer** node. In its TileSet resource, add an
   **Atlas Source** pointing at the atlas PNG; confirm 32x32 tiles.
2. In the TileSet editor, open the **Terrain Sets** tab and create a terrain set of
   type **Match Corners and Sides (3x3 bitmask)** — this is Godot's 8-neighbor mode.
   Add one terrain per side of the pair, e.g. terrain "Grass" (overlay) and "Dirt"
   (base).
3. Assign every atlas cell of the overlay terrain: for each slot, Godot asks for its
   3x3 peering-bit configuration. Decode it from the slot index: look up the bitmask
   `m` for that slot in `metadata/autotiles/<pair>.json`, then set bit N/NE/E/SE/S/SW/W/NW
   wherever the mask has it (bit order: N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64, NW=128).
4. Paint with the terrain tool; the boundary arcs are baked into the tiles, so
   transitions come out curved automatically.

**Why 3x3 and not 2x2?** A 2x2 (corner) bitmask only knows about the 4 diagonal
corners, so it can't distinguish an inner corner from a straight edge and produces
stair-stepped borders. This pack's blob47 geometry uses quarter-disc arcs per
16px quadrant driven by full 8-neighbor information — the 3x3 bitmask carries
exactly that information, so edges stay continuous (verified exhaustively at
build time).

The `grass-water` pair also ships a simpler **wang16** atlas
(`atlas_grass_water_wang16.png`, 4x4 grid): each tile is chosen from the four
surrounding dual-grid cells (index = NW + 2*NE + 4*SW + 8*SE). It is a lighter
alternative if you don't want terrain sets.

## 4. Sprites and icons

- Single images (`icons/*.png`, `characters/knight_*.png`): create a **Sprite2D**
  node, drag the texture in. Filter is already Nearest from the global default; if
  you overrode it, set **CanvasItem > Texture > Filter = Nearest** on the node.
- Icon atlas `icons/atlas_4x4.png`: 4x4 grid of 32px cells, row-major; the cell
  order is in `metadata/atlas_icons.json`. Use **Sprite2D > Region Enabled** and set
  the region rectangle, or an AtlasTexture.
- `hd/*.png` are 256/512px renders — they can keep the default (linear/bilinear)
  filter because smoothing hides the high-res pixel edges instead of blurring detail.
  Nearest on them would make the rekeyed 1px alpha edges look jagged.

## 5. Animations

1. Create an **AnimatedSprite2D** node. In SpriteFrames, click **Add Frames from
   Sheet** (Godot 4.3+), pick `animations/knight_idle.png`, and slice the 64x64 grid
   (idle: 2 frames, walk: 4, attack: 3 — frames run left-to-right).
2. Set the animation **fps to 10** (matches `metadata/animations.json`).
3. Do the same for walk and attack.
4. The GIFs (`*_64.gif`, `*_256.gif`) are previews only — Godot does not play GIFs;
   use the sliced sheets.

## 6. Characters turntable

`characters/knight_turntable.gif` is a preview of the four views (600ms per view).
In-game, swap `knight_front/side/back/three_quarter.png` on a Sprite2D based on
movement direction; all four share the 39-color palette in
`characters/knight_palette.hex`.
