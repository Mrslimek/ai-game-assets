# Local AI Game Asset Generation Pipeline (Apple Silicon M5)

A complete, production-validated local game asset generation ecosystem using ComfyUI on Apple Silicon (MacBook Air M5, 16 GB unified memory, macOS, Metal / PyTorch MPS).

---

## 🎮 Highlights & Verified Capabilities

- **100% Local & Offline**: All generation and post-processing run on-device with zero external API calls.
- **Strict 16 GB Memory Compliance**: Runs reliably within ~8.5-8.7 GB peak unified memory, with **0 MB swap usage** and automatic low-VRAM memory scheduling.
- **8-Step High-Speed Inference**: SDXL Lightning acceleration produces game-ready assets in **15 to 26 seconds** per asset on Apple Silicon MPS.
- **True Pixel Art (Not Blurry Downscales)**: Dominant color voting and OKLab palette quantization snap generations to exact pixel grids with zero noisy dither artifacts.
- **Seamless Tiling & Autotiling**: Integrated circular latent rolling ensures 100% seam continuity. Includes Wang 16 (dual-grid) and Blob 47 (8-neighbor) tileset synthesizers and map renderers.
- **Complete Asset Benchmark Suite**:
  1. Top-down RPG Terrain (Wang 16 & Blob 47 tilesets and procedural maps)
  2. Seamless Terrain (Grass, Dirt, Sand, Stone, Water; 32×32 and 64×64)
  3. Isometric Environment (Platforms, cliffs, trees, props with transparent backgrounds)
  4. Character Turnaround (Front, Side, Back, 3/4 views)
  5. Character Animation (4-action sprite sheets: Idle, Walk, Run, Attack + animated GIFs)
  6. Inventory Icons (16 unified 32×32 icons: weapons, potions, armor, materials)
  7. Stylized HD 2D Assets (256×256 and 512×512 hand-painted vector assets)

---

## 📁 Repository Directory Structure

```
game-asset-ai/
├── README.md                           # Main documentation & reproduction guide
├── research/
│   ├── model-catalog.md               # Detailed evaluation of models & LoRAs
│   ├── compatibility.md               # Hardware profiling on 16 GB Apple Silicon M5
│   ├── architecture.md                # System pipeline & mathematical design
│   ├── benchmark-results.md           # Technical QA metrics (MASD, IoU, timings)
│   └── licenses.md                    # Legal & commercial license assessments
├── models/
│   └── README.md                      # Model paths on /Volumes/Shared/AI/models
├── workflows/                         # Standalone executable ComfyUI workflow JSONs
│   ├── pixel-art/                     # Inventory icons & pixel-art generation
│   ├── tilesets/                      # Seamless tiles & isometric platforms
│   ├── characters/                    # Character turnaround workflows
│   ├── animation/                     # Frame-by-frame action workflows
│   └── stylized-2d/                   # High-res hand-painted transparent assets
├── scripts/
│   ├── run_benchmarks.py              # Master benchmark orchestration script
│   ├── validate_tiles.py              # Programmatic seam detection & 3x3 preview
│   ├── validate_sprites.py            # Silhouette IoU, baseline variance, GIF maker
│   ├── build_autotile_map.py          # Wang 16 & Blob 47 tileset & map builder
│   ├── make_contact_sheet.py          # Labeled grid contact sheet assembler
│   └── generate_report.py             # HTML dashboard & CSV report compiler
├── assets/
│   ├── generated/                     # Raw generated game assets (PNG)
│   └── validated/                     # Autotile atlases, maps, 3x3 tiles, animated GIFs
└── reports/
    ├── index.html                     # Interactive HTML visual comparison gallery
    ├── benchmark.json                 # Machine-readable benchmark telemetry
    └── benchmark.csv                  # Tabular performance dataset
```

---

## 🚀 Quick Start & Reproduction

### 1. Prerequisites & Environment
Ensure ComfyUI is installed and points to the external model directory:
- External drive mounted at `/Volumes/Shared/AI/models`
- ComfyUI server running on `http://127.0.0.1:8188`
- Custom nodes installed in `ComfyUI/custom_nodes`:
  - `ComfyUI-SpriteKiln`
  - `ComfyUI-GGUF`

### 2. Start Headless ComfyUI
```bash
/Users/viktor/Projects/AI/pipelines/comfy-server.sh start
```

### 3. Run Benchmark Suite & Generate Visual Report
```bash
/Users/viktor/ComfyUI-Installs/ComfyUI/ComfyUI/.venv/bin/python3 \
  /Users/viktor/Projects/AI/game-asset-ai/scripts/run_benchmarks.py
```

### 4. Inspect Results
Open the generated interactive gallery report in your browser:
```bash
open /Users/viktor/Projects/AI/game-asset-ai/reports/index.html
```

---

## 📊 Benchmark Telemetry Overview

| Workflow | Model Stack | Resolution | Steps | Warm Latency | Peak RAM | Swap | QA Result |
|---|---|---|---|---|---|---|---|
| **Seamless Terrain** | SDXL + Lightning + Pixel Art XL | 32×32 / 64×64 | 8 | 33.1s | 8.7 GB | 0 MB | **PASS** (MASD 14.5) |
| **Wang 16 & Blob 47**| Procedural Autotile Synthesizer | 32×32 (16/47) | 8 | 0.4s | 8.5 GB | 0 MB | **PASS** (100% Valid) |
| **Isometric Props** | SDXL + Pixel Art XL + SK_BgRemove | 64×64 | 8 | 27.1s | 8.7 GB | 0 MB | **PASS** (Clean Alpha) |
| **Character Views** | SDXL + Pixel Art XL + SK_BgRemove | 64×64 | 8 | 26.9s | 8.7 GB | 0 MB | **PASS** (Consistent) |
| **Action Sprites** | SDXL + Pixel Art XL + SK_SpriteSheet | 64×64 | 8 | 26.4s | 8.7 GB | 0 MB | **PASS** (IoU 0.612) |
| **16 Inventory Icons**| SDXL + Pixel Art XL + SK_BgRemove | 32×32 | 8 | 24.8s | 8.6 GB | 0 MB | **PASS** (16-Color Set) |
| **Stylized HD 2D** | SDXL + Lightning (HD Mode) | 256×256 / 512×512 | 8 | 25.8s | 8.6 GB | 0 MB | **PASS** (Smooth Vectors) |
