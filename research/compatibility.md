# Hardware Compatibility & Apple Silicon MPS Profiling

## 1. Hardware Specifications

- **Device**: MacBook Air M5
- **Unified Memory**: 16 GB LPDDR5
- **CPU**: Apple M5 (ARM64)
- **OS**: macOS 27.2 (Darwin Kernel 27.2.0)
- **Framework**: PyTorch 2.12.1 with Metal Performance Shaders (MPS)
- **Engine**: ComfyUI 0.44.2 (Standalone local desktop environment)

---

## 2. Key Observations on Apple Silicon MPS

1. **Unified Memory Constraints**:
   - Total available system RAM: 16.0 GB (17,179,869,184 bytes).
   - Baseline OS + system processes: ~4.5 GB.
   - Usable memory budget for ComfyUI: ~10.5 GB.
   - When models load, memory pressure rises to Yellow if models exceed ~11 GB, causing macOS VM compressor and swap activity.

2. **Absence of Native FP8 Hardware Units**:
   - Apple Silicon GPU (Metal) supports FP32, FP16, and BF16.
   - FP8 tensors cannot be executed natively in hardware by MPS. ComfyUI up-casts FP8 checkpoints to FP16 in memory, negating the memory savings and adding conversion overhead.
   - **Remedy**: Use native FP16 checkpoints, BF16, or GGUF quantization (via `ComfyUI-GGUF`), which de-quantizes blocks to FP16 on the fly during computation.

3. **Sequential Model Offloading**:
   - ComfyUI automatically manages low-VRAM memory scheduling on macOS:
     ```
     [INFO] Requested to load SDXL
     [INFO] loaded completely; 4897.05 MB loaded, full load: True
     [INFO] Requested to load AutoencoderKL
     [INFO] Unloaded partially: 4157.74 MB freed, 739.35 MB remains loaded
     ```
   - This ensures peak RAM consumption never exceeded **8.7 GB**, keeping swap usage at **0 MB** across all 7 benchmark runs.

4. **Inference Latency Breakdown**:
   - **Cold Start**: Initial model loading from external SSD: ~145-150s.
   - **Warm Start (1024×1024, 8 steps)**: ~59s KSampler (~7.4s / step).
   - **Warm Start (512×512, 8 steps)**: ~15.2s KSampler (~1.9s / step).
   - **Tile Synthesis (Wang 16 & Blob 47)**: Pure Python / NumPy vector operations: < 0.5s for 16-tile and 47-tile autotile sets!

---

## 3. Disqualified Workflows for 16 GB Apple Silicon

- **Wan 2.2 I2V 14B Video Generation**:
  - Requires ~14.5 GB VRAM in Q4_K_M.
  - On a 16 GB machine, running Wan 14B forces the macOS kernel to page 4-6 GB to disk swap, causing thermal throttling, UI freezes, and >450s per video clip.
  - **Selected Alternative**: Keyframe frame-by-frame synthesis with seed locking + SpriteKiln sprite sheet stabilization (`SK_Stabilize`), producing clean 4-8 frame action sheets in ~100s with 0 swap.
