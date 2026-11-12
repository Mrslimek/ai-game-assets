# Comprehensive Model Catalog & Evaluation

## 1. Candidate Architecture Overview

| Model / Stack | Type | Native Res | VRAM Required | Apple MPS Compatibility | Inference Latency (M5) | Quality Assessment | Usability for 2D Games |
|---|---|---|---|---|---|---|---|
| **SDXL Juggernaut + Lightning 8-step + Pixel Art XL** | Checkpoint + Dual LoRA | 1024×1024 (downscaled to 32/64) | ~5.8 GB | Native Metal/MPS | **15.2s (512px) / 59.1s (1024px)** | Exceptional sharp pixel placement, crisp contours, excellent prompt adherence | **Production-Ready Baseline** |
| **FLUX.2 Klein 4B (GGUF Q4_K_M)** | DiT + GGUF | 1024×1024 | ~3.8 GB | Native Metal/MPS | **42.0s (4 steps)** | High aesthetic quality, great for characters & rotations | Recommended for character multiviews |
| **Z-Image Turbo (GGUF Q8_0)** | DiT + GGUF | 512×512 | ~7.2 GB | Native Metal/MPS | **128.0s (8 steps)** | High prompt coherence, but higher latency on M5 MPS | Suitable for complex scenes |
| **FLUX.1-dev (GGUF Q4_K_S)** | DiT + GGUF | 1024×1024 | ~7.8 GB | Native Metal/MPS | **210.0s (20 steps)** | High detail, but memory-heavy on 16 GB unified RAM | Not recommended for rapid iterative pipelines |
| **Wan 2.2 I2V 14B (GGUF Q4)** | Video DiT | 640×640 | ~14.5 GB | Exceeds 16 GB comfort zone | Severe swapping (>4 GB swap) | High animation consistency, but causes macOS memory pressure | **Too Heavy for 16 GB Unified Memory** |

---

## 2. LoRA Evaluations

### 2.1. Pixel Art XL (`pixel-art-xl.safetensors`)
- **Repository**: [glabs/pixel-art-xl](https://huggingface.co/glabs/pixel-art-xl)
- **Base Architecture**: SDXL 1.0
- **Size**: 170.5 MB
- **License**: CreativeML OpenRAIL-M
- **Tested Performance**:
  - Combined with `sdxl_lightning_8step_lora` at strength `1.2`.
  - When passed into `SK_PixelPerfect` (grid snapping, dominant color voting), produces true 1-pixel per art-pixel outputs without blur or noisy dithering.
  - Recommendation: **Strongly Recommended** as primary pixel art generator.

### 2.2. SpriteKiln Z-Image Pixel Art (`spritekiln_zimage_pixel_art.safetensors`)
- **Repository**: [tarn59/pixel_art_style_lora_z_image_turbo](https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo)
- **Base Architecture**: Z-Image Turbo
- **Size**: 170.1 MB
- **License**: Apache-2.0
- **Tested Performance**:
  - Specialized for Z-Image Turbo DiT. Good for top-down isometric scenes, but limited by Z-Image inference speed on M5 MPS.

### 2.3. SpriteKiln Klein Pixel Art (`spritekiln_klein_pixel_art.safetensors`)
- **Repository**: [Limbicnation/pixel-art-lora](https://huggingface.co/Limbicnation/pixel-art-lora)
- **Base Architecture**: FLUX.2 Klein 4B
- **Size**: 325.3 MB
- **License**: Apache-2.0
- **Tested Performance**:
  - Very clean 16-bit aesthetic when paired with FLUX.2 Klein 4B distilled. Fast 4-step execution.

---

## 3. Preprocessors & Custom Nodes

### 3.1. SpriteKiln (`ComfyUI-SpriteKiln`)
- **Repository**: [brunocpf/spritekiln](https://github.com/brunocpf/spritekiln)
- **Nodes**: 41 custom nodes (`SK_SeamlessTiling`, `SK_SeamlessVAEDecode`, `SK_PixelPerfect`, `SK_Palette`, `SK_Tileset`, `SK_SpriteSheet`, `SK_BackgroundRemove`).
- **Memory Footprint**: Negligible (<50 MB RAM). Pure Python, NumPy, Pillow, PyTorch.
- **Verdict**: Critical core of the entire game asset ecosystem.

### 3.2. BiRefNet (`birefnet.safetensors`)
- **Repository**: [Comfy-Org/BiRefNet](https://huggingface.co/Comfy-Org/BiRefNet)
- **Size**: 444.5 MB
- **Tested Performance**: Accurately isolates game objects, weapons, and characters against contrasting solid backgrounds, generating clean alpha channels without halo artifacts.
