# Software and Model Licenses & Commercial Usability

This document details the licensing terms of all software dependencies, base models, LoRAs, and preprocessors used in the pipeline.

---

## 1. Software & Code Dependencies

| Component | Repository | License | Commercial Game Development Usability |
|---|---|---|---|
| **ComfyUI** | [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI) | GNU GPL v3.0 | Output images are user-owned; ComfyUI engine code itself is GPLv3. Safe for game asset generation. |
| **SpriteKiln** | [brunocpf/spritekiln](https://github.com/brunocpf/spritekiln) | GNU GPL v3.0 | Custom node pack is GPLv3. Generated assets are free from code copyleft. |
| **ComfyUI-GGUF** | [city96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | Apache-2.0 | Permissive open source. Commercial use permitted. |
| **IP-Adapter Plus** | [cubiq/ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) | Apache-2.0 | Permissive open source. Commercial use permitted. |
| **BiRefNet** | [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | MIT License | Permissive open source. Commercial use permitted. |

---

## 2. Model Weights & Checkpoints

| Model / Weight | Creator | License | Commercial Terms |
|---|---|---|---|
| **Juggernaut-XL v9** | RunDiffusion | CreativeML OpenRAIL-M | Permitted for commercial output generation provided use cases comply with standard OpenRAIL-M ethical restrictions. |
| **Animagine XL 3.1** | CagliostroLab | Fair AI OpenRAIL-M | Permitted for commercial output generation under Fair AI terms. |
| **FLUX.2 Klein 4B** | Black Forest Labs | Apache-2.0 | Fully open weights, commercial use permitted. |
| **Z-Image Turbo** | Tongyi-MAI / Alibaba | Apache-2.0 | Fully open weights, commercial use permitted. |
| **FLUX.1-dev** | Black Forest Labs | FLUX.1-dev Non-Commercial | **Non-commercial only** without commercial license from Black Forest Labs. Do not use for commercial games without license. |
| **SDXL Lightning LoRA** | ByteDance | Apache-2.0 | Permissive open source. Commercial use permitted. |
| **Pixel Art XL LoRA** | Glabs / Nerijs | CreativeML OpenRAIL-M | Permitted for commercial game art generation. |
| **SpriteKiln Pixel LoRAs** | tarn59 / Limbicnation / svntax | Apache-2.0 | Fully open weights, commercial use permitted. |
| **BiRefNet Weights** | ZhengPeng7 / Comfy-Org | MIT License | Permissive open source. Commercial use permitted. |

---

## 3. Recommended Commercial Indie Stack

For complete peace of mind and unconditional commercial freedom:
1. **Base Model**: FLUX.2 Klein 4B (Apache-2.0) OR SDXL Juggernaut (OpenRAIL-M).
2. **Speed / Acceleration**: SDXL Lightning (Apache-2.0).
3. **Pixel Art Style**: SpriteKiln Klein / Z-Image LoRAs (Apache-2.0) or Pixel Art XL (OpenRAIL-M).
4. **Avoid**: FLUX.1-dev base weights unless operating under non-commercial or academic scope.
