# Game Asset AI Model Registry & Paths

This document catalogs all models used by the local game asset generation pipeline on Apple Silicon (MacBook Air M5, 16 GB unified memory).

Models are stored on the external SSD volume at `/Volumes/Shared/AI/models` to conserve internal SSD space while maintaining high read throughput over USB-C.

---

## Model Inventory & Storage Layout

| Category | Model Filename | Architecture | Size | Precision / Format | Location / Path | License |
|---|---|---|---|---|---|---|
| **Base Checkpoint** | `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors` | SDXL (Stability AI / RunDiffusion) | 6.77 GB | FP16 Checkpoint | `/Volumes/Shared/AI/models/checkpoints/` | CreativeML OpenRAIL-M |
| **Anime Checkpoint** | `animagine-xl-3.1.safetensors` | SDXL (CagliostroLab) | 6.62 GB | FP16 Checkpoint | `/Volumes/Shared/AI/models/checkpoints/` | Fair AI OpenRAIL-M |
| **SD 1.5 Checkpoint** | `Realistic_Vision_V6.0_NV_B1_verified_20260704.safetensors` | SD 1.5 | 4.07 GB | FP16 Checkpoint | `/Volumes/Shared/AI/models/checkpoints/` | CreativeML OpenRAIL-M |
| **Diffusion (GGUF)** | `flux-2-klein-4b-Q4_K_M.gguf` | FLUX.2 Klein 4B | 2.48 GB | GGUF Q4_K_M | `/Volumes/Shared/AI/models/diffusion_models/` | Apache-2.0 |
| **Diffusion (GGUF)** | `z_image_nsfw_v2-Q8_0.gguf` | Z-Image Turbo | 6.89 GB | GGUF Q8_0 | `/Volumes/Shared/AI/models/diffusion_models/` | Apache-2.0 |
| **Diffusion (GGUF)** | `flux1-dev-Q4_K_S.gguf` | FLUX.1-dev | 6.49 GB | GGUF Q4_K_S | `/Volumes/Shared/AI/models/diffusion_models/` | Non-commercial FLUX.1-dev |
| **Step Accelerator** | `sdxl_lightning_8step_lora.safetensors` | SDXL Lightning (ByteDance) | 375.6 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | Apache-2.0 |
| **Step Accelerator** | `sdxl_lightning_4step_lora.safetensors` | SDXL Lightning (ByteDance) | 375.6 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | Apache-2.0 |
| **Pixel Art LoRA** | `pixel-art-xl.safetensors` | SDXL Pixel Art (Glabs/Nerijs) | 170.5 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | CreativeML OpenRAIL-M |
| **Pixel Art LoRA** | `spritekiln_zimage_pixel_art.safetensors` | Z-Image Turbo Pixel LoRA (tarn59) | 170.1 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | Apache-2.0 |
| **Pixel Art LoRA** | `spritekiln_klein_pixel_art.safetensors` | FLUX.2 Klein Pixel LoRA (Limbicnation)| 325.3 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | Apache-2.0 |
| **Sprite Sheet LoRA**| `spritekiln_klein_base_4walk_sheet.safetensors` | FLUX.2 Klein Walk Sheet (svntax) | 92.4 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | Apache-2.0 |
| **Multiview LoRA** | `spritekiln_klein_2x2_multiview.safetensors` | FLUX.2 Klein 2x2 Sheet (fal) | 76.0 MB | FP16 LoRA | `/Volumes/Shared/AI/models/loras/` | Apache-2.0 |
| **Background Removal**| `birefnet.safetensors` | BiRefNet (Zheng et al.) | 444.5 MB | FP16 Tensor | `/Volumes/Shared/AI/models/background_removal/` | MIT |
| **ControlNet** | `OpenPoseXL2.safetensors` | ControlNet OpenPose SDXL (thibaud) | 4.77 GB | FP16 Tensor | `/Volumes/Shared/AI/models/controlnet/` | Apache-2.0 |
| **IP-Adapter** | `ip-adapter-plus_sdxl_vit-h.safetensors` | IPAdapter Plus SDXL (cubiq) | 808.3 MB | FP16 Tensor | `/Volumes/Shared/AI/models/ipadapter/` | Apache-2.0 |
| **CLIP Vision** | `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | OpenCLIP ViT-H/14 | 2.41 GB | FP16 Tensor | `/Volumes/Shared/AI/models/clip_vision/` | MIT |

---

## ComfyUI Path Configuration

ComfyUI loads all models via `/Users/viktor/ComfyUI-Shared/instance-model-paths.yaml`:

```yaml
comfy.desktop_0:
  base_path: '/Users/viktor/ComfyUI-Shared/models'
  is_default: true
  ...

ssd:
  base_path: '/Volumes/Shared/AI/models'
  'checkpoints': 'checkpoints/'
  'diffusion_models': 'diffusion_models/'
  'loras': 'loras/'
  'controlnet': 'controlnet/'
  'ipadapter': 'ipadapter/'
  'clip_vision': 'clip_vision/'
  'background_removal': 'background_removal/'
  'text_encoders': 'text_encoders/'
  'vae': 'vae/'
```

---

## Hardware Operating Rules on 16 GB Apple Silicon

1. **Never load multiple large diffusion models simultaneously**: ComfyUI unloads the diffusion UNet partially (~4.1 GB freed) before loading VAE or CLIP models.
2. **Precision on MPS**: MPS does not have native FP8 arithmetic. Checkpoints in FP16 or GGUF dequantized on-the-fly to FP16 provide the best memory/speed ratio without CPU fallback.
3. **Step Budget**: SDXL Lightning 8-step reduces inference latency from ~180s (at 30 steps) down to ~15-25s on 512×512 latents.
