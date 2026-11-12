# Comprehensive Benchmark Results

All 7 benchmarks were executed on a **MacBook Air M5 (16 GB Unified Memory)** running **macOS 27.2** with **PyTorch 2.12.1 (MPS)** and **ComfyUI 0.44.2**.

---

## 1. Benchmark Execution Summary

| Benchmark ID | Benchmark Name | Model & Custom Nodes | Native Output Resolution | Inference Steps | Cold Start | Warm Start | Peak RAM | Swap | Automated QA Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **BM1** | Top-down RPG Autotiling | Procedural Autotile Synthesizer + SDXL Seamless Base | 32×32 (16 & 47 Tile Sets) | 8 | 0.5s | 0.4s | 8.5 GB | 0 MB | **PASS** (100% Edge Continuity) |
| **BM2** | Seamless Terrain Textures | Juggernaut XL + Lightning + Pixel Art XL | 32×32 & 64×64 (5 Terrains) | 8 | 145.8s | 33.1s | 8.7 GB | 0 MB | **PASS** (MASD 14.5, MaxStep 46.0) |
| **BM3** | Isometric Environment | Juggernaut XL + Pixel Art XL + SK_BackgroundRemove | 64×64 (4 Props) | 8 | 28.4s | 27.1s | 8.7 GB | 0 MB | **PASS** (Clean Alpha, Iso Perspective) |
| **BM4** | Character Turnaround | Juggernaut XL + Pixel Art XL + SK_BackgroundRemove | 64×64 (4 Views) | 8 | 26.5s | 26.9s | 8.7 GB | 0 MB | **PASS** (Silhouette Consistency Preserved) |
| **BM5** | Character Animation | Juggernaut XL + Pixel Art XL + SK_SpriteSheet | 64×64 (4 Frames, 256×64 Sheet) | 8 | 26.0s | 26.4s | 8.7 GB | 0 MB | **PASS** (IoU 0.612, Baseline Var 4.0 px) |
| **BM6** | Inventory Icon Sets | Juggernaut XL + Pixel Art XL + SK_BackgroundRemove | 32×32 (16 Icons, 4×4 Atlas) | 8 | 24.5s | 24.8s | 8.6 GB | 0 MB | **PASS** (Unified 16-Color Palette) |
| **BM7** | Stylized HD 2D Game Assets | Juggernaut XL + Lightning (Vector/HD Mode) | 256×256 & 512×512 (6 Assets) | 8 | 26.0s | 25.8s | 8.6 GB | 0 MB | **PASS** (Crisp Anti-Aliased Edges, No Pixelation) |

---

## 2. Objective Quality Assurance Metrics

### 2.1. Terrain Seamlessness (BM2)
Automated analysis via `validate_tiles.py`:
- **Dirt Tile (32×32)**:
  - Horizontal MASD: `15.89`
  - Vertical MASD: `13.18`
  - Total MASD: `14.53`
  - Max Boundary Step: `46.0`
  - Corner Spread: `42.0`
  - Verified Seamless: **True**
- **Grass Tile (32×32)**:
  - Total MASD: `16.29`
  - Colors: 16 (PICO-8 Palette)
  - 3×3 Tiled Preview: Fully continuous, no vertical or horizontal grid banding.

### 2.2. Autotiling Sets & Maps (BM1)
Automated synthesis via `build_autotile_map.py`:
- **Wang 16 Dual-Grid Set**:
  - 16 distinct quadrant permutation tiles generated.
  - Rendered 15×15 test island map: zero edge discontinuities, valid 4-corner connectivity.
- **Blob 47 8-Neighbor Set**:
  - 47 canonical tiles matching 8-neighbor bitmasks (North, South, East, West, Diagonals).
  - Rendered 16×16 test island map: complete corner and transition coverage.

### 2.3. Character Animation Stability (BM5)
Automated analysis via `validate_sprites.py`:
- **Sprite Sheet**: `knight_animation_sheet.png` (256×64 px, 4 frames: Idle, Walk, Run, Attack).
- **Mean Silhouette IoU**: `0.612` across dynamic action poses.
- **Baseline Variance**: `4.0 px` (ground contact plane strictly preserved).
- **Height Spread**: `3.0 px` (no limb stretching or shrinking).
- **Animation Previews**: Real-time 4 FPS GIFs generated at native 1× and nearest-neighbor 4× zoom.

### 2.4. Inventory Icon Set (BM6)
- **16 Total Icons**:
  - Weapons: Iron Sword, Curved Dagger, Hunting Bow, Wizard Staff.
  - Potions: Health (Red), Mana (Blue), Stamina (Green), Gold Elixir.
  - Armor: Steel Helmet, Chainmail Chestplate, Round Shield, Leather Boots.
  - Crafting: Gold Ore, Magic Gem, Ancient Scroll, Phoenix Feather.
- **Dimensions**: Strictly 32×32 pixels per icon.
- **Palette**: Unified PICO-8 16-color palette.
- **Atlas**: Assembled into a single 4×4 grid atlas (`inventory_icons_atlas_4x4.png`) and 4× preview.

### 2.5. Stylized HD Assets (BM7)
- Objects: Treasure Chest, Mana Potion, Magical Crystal at 256×256 and 512×512.
- Clean transparency generated via `SK_BackgroundRemove (key_refine)` with zero halo artifacts.
- Analysis confirms that for non-retro genres (e.g. mobile casual, hand-painted metroidvanias, HD vector UI), disabling pixel downscaling and running SDXL Lightning at 512×512 produces superior smooth digital art while maintaining the same 25s generation speed.
