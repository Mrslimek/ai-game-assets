# Pipeline Architecture & Technical Design

## 1. Modular Pipeline Flow

The local game asset pipeline is designed as a multi-stage modular system:

```
[Text Prompt / Preset]
        │
        ▼
[SDXL Juggernaut + Lightning 8-step + Pixel Art XL]
        │
        ├── Seamless Mode: [SK_SeamlessTiling Latent Roll]
        │
        ▼
   [KSampler (8 steps, Euler / SGM Uniform)]
        │
        ├── Seamless Mode: [SK_SeamlessVAEDecode Latent Wrap-Pad]
        └── Standard Mode: [Standard VAEDecode]
        │
        ▼
[Background Removal: SK_BackgroundRemove (key_refine / BiRefNet)]
        │
        ▼
[Pixel-Perfect Downscale: SK_PixelPerfect (Dominant Color Cluster Snapping)]
        │
        ▼
[Palette Quantization: SK_Palette (PICO-8 / 16-Color OKLab Lock)]
        │
        ▼
[Assembly & Export: Wang 16 / Blob 47 Autotiler OR SpriteSheet Exporter]
        │
        ▼
[Game-Ready Assets: PNG with Alpha + Aseprite/Godot Metadata + HTML Report]
```

---

## 2. Technical Implementations

### 2.1. Circular Latent Rolling (`SK_SeamlessTiling`)
Unlike naïve tileable post-processing (which blurs edges or stamps offsets), circular latent rolling hooks directly into the diffusion UNet wrapper:
- On every timestep, the latent tensor is circularly rolled by a golden-ratio pseudo-random offset:
  $$\Delta x = \lfloor W \cdot ((0.5 + k \cdot 0.618034) \pmod 1) \rfloor$$
- Because the seam is rolled into the center of the latent space during diffusion, the model naturally paints continuous texture across the boundary.
- Prior to decoding, the latent is padded with periodic wrap-around padding (`SK_SeamlessVAEDecode`) to avoid VAE convolution edge ringing.

### 2.2. Dual-Grid Wang 16 and 8-Neighbor Blob 47 Autotiling
- **Wang 16**: Uses a 2-corner / dual-grid formulation where each tile is composed of 4 quadrant corners. Given Overlay $A$ and Base $B$, tile index is:
  $$\text{Index} = \text{NW} + 2\cdot\text{NE} + 4\cdot\text{SW} + 8\cdot\text{SE}$$
  Producing all 16 transition combinations with seamless corner continuity.
- **Blob 47**: Uses an 8-neighbor bitmask:
  $$\text{Mask} = \sum_{i=0}^7 2^i \cdot N_i \quad (\text{N, NE, E, SE, S, SW, W, NW})$$
  Normalized using `_blob_reduce` so diagonal corners require adjacent orthogonal neighbors, mapping all 256 configurations to 47 canonical tiles.

### 2.3. True Pixel-Art Quantization vs Naïve Downscaling
- Standard bilinear/bicubic downscaling produces blurry, semi-transparent border pixels and hundreds of intermediate color artifacts.
- `SK_PixelPerfect` uses a two-stage dominant cluster vote:
  1. Finds the true pixel grid scale factor.
  2. In every $N\times N$ block of the diffusion canvas, counts pixel frequency across 48 initial color clusters in OKLab color space.
  3. Assigns the winning centroid color to that exact art pixel.
  4. Locks the palette to standard 16-color indie palettes (PICO-8 / Sweetie-16).
