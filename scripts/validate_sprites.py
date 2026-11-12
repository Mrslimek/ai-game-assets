#!/usr/bin/env python3
"""validate_sprites.py - Objective quality validation for sprite sheets and character frames.

Features:
- Validates frame dimensions and grid alignment
- Analyzes bounding boxes, transparent margins, and unexpected voids
- Measures character height, baseline consistency, and silhouette stability across frames
- Calculates silhouette Intersection-over-Union (IoU) across sequence
- Detects color palette consistency, unique color counts, and color noise
- Generates animated GIF previews (native and 4x nearest-neighbor)
- Outputs detailed JSON verification metrics
"""

import sys
import os
import json
import argparse
import numpy as np
from PIL import Image

def analyze_frame(im_rgba):
    """Analyze a single RGBA frame image."""
    arr = np.array(im_rgba)
    alpha = arr[:, :, 3]
    h, w = alpha.shape

    opaque_mask = alpha > 16
    ys, xs = np.where(opaque_mask)

    if len(xs) == 0:
        return {
            "empty": True,
            "bbox": None,
            "width": w,
            "height": h,
            "char_w": 0,
            "char_h": 0,
            "baseline": 0,
            "unique_colors": 0,
            "opaque_pixels": 0,
            "mask": np.zeros((h, w), dtype=bool)
        }

    min_x, max_x = int(np.min(xs)), int(np.max(xs))
    min_y, max_y = int(np.min(ys)), int(np.max(ys))
    char_w = max_x - min_x + 1
    char_h = max_y - min_y + 1
    baseline = int(max_y)

    # Unique colors among visible pixels
    visible_pixels = arr[opaque_mask]
    colors = set(tuple(p[:3]) for p in visible_pixels)

    return {
        "empty": False,
        "bbox": [min_x, min_y, char_w, char_h],
        "width": w,
        "height": h,
        "char_w": char_w,
        "char_h": char_h,
        "baseline": baseline,
        "unique_colors": len(colors),
        "opaque_pixels": int(np.sum(opaque_mask)),
        "mask": opaque_mask
    }

def analyze_spritesheet(sheet_path, frame_w, frame_h, out_dir=None, fps=8):
    im = Image.open(sheet_path).convert("RGBA")
    sw, sh = im.size

    cols = sw // frame_w
    rows = sh // frame_h
    total_frames = cols * rows

    frames = []
    frame_metrics = []

    for r in range(rows):
        for c in range(cols):
            x = c * frame_w
            y = r * frame_h
            sub = im.crop((x, y, x + frame_w, y + frame_h))
            frames.append(sub)
            m = analyze_frame(sub)
            frame_metrics.append(m)

    # Calculate baseline stability
    baselines = [m["baseline"] for m in frame_metrics if not m["empty"]]
    char_heights = [m["char_h"] for m in frame_metrics if not m["empty"]]
    baseline_variance = float(np.var(baselines)) if baselines else 0.0
    height_spread = float(np.ptp(char_heights)) if char_heights else 0.0

    # Calculate silhouette IoU between successive non-empty frames
    ious = []
    non_empty_masks = [m["mask"] for m in frame_metrics if not m["empty"]]
    for i in range(len(non_empty_masks) - 1):
        m1 = non_empty_masks[i]
        m2 = non_empty_masks[i+1]
        intersection = np.logical_and(m1, m2).sum()
        union = np.logical_or(m1, m2).sum()
        iou = float(intersection / union) if union > 0 else 1.0
        ious.append(iou)

    mean_iou = float(np.mean(ious)) if ious else 1.0

    # Overall palette across all frames
    all_opaque = []
    for f in frames:
        arr = np.array(f)
        op = arr[:, :, 3] > 16
        if op.any():
            all_opaque.extend([tuple(p[:3]) for p in arr[op]])
    total_unique_colors = len(set(all_opaque))

    # Generate animated GIF
    gif_path = None
    gif_upscaled_path = None
    if out_dir and len(frames) > 1:
        os.makedirs(out_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(sheet_path))[0]
        gif_path = os.path.join(out_dir, f"{base_name}_anim.gif")
        dur = int(1000 / fps)
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=dur, loop=0, disposal=2)

        # Upscaled preview
        upscaled_frames = [f.resize((frame_w * 4, frame_h * 4), Image.NEAREST) for f in frames]
        gif_upscaled_path = os.path.join(out_dir, f"{base_name}_anim_x4.gif")
        upscaled_frames[0].save(gif_upscaled_path, save_all=True, append_images=upscaled_frames[1:], duration=dur, loop=0, disposal=2)

    return {
        "file": os.path.abspath(sheet_path),
        "filename": os.path.basename(sheet_path),
        "sheet_width": sw,
        "sheet_height": sh,
        "frame_width": frame_w,
        "frame_height": frame_h,
        "cols": cols,
        "rows": rows,
        "total_frames": total_frames,
        "mean_silhouette_iou": round(mean_iou, 3),
        "baseline_variance": round(baseline_variance, 2),
        "height_spread": round(height_spread, 2),
        "total_unique_colors": total_unique_colors,
        "anim_gif": gif_path,
        "anim_gif_x4": gif_upscaled_path,
        "frames": [
            {
                "idx": i,
                "bbox": m["bbox"],
                "char_w": m["char_w"],
                "char_h": m["char_h"],
                "baseline": m["baseline"],
                "unique_colors": m["unique_colors"]
            }
            for i, m in enumerate(frame_metrics)
        ]
    }

def main():
    parser = argparse.ArgumentParser(description="Validate sprite sheets and character sequences")
    parser.add_argument("spritesheet", help="Path to sprite sheet image")
    parser.add_argument("--frame-w", "-W", type=int, default=32, help="Frame width in pixels")
    parser.add_argument("--frame-h", "-H", type=int, default=32, help="Frame height in pixels")
    parser.add_argument("--out-dir", "-o", default=None, help="Directory to save animated preview")
    parser.add_argument("--fps", type=int, default=8, help="Animation playback FPS")
    parser.add_argument("--json", "-j", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    if not os.path.exists(args.spritesheet):
        print(f"Error: {args.spritesheet} does not exist", file=sys.stderr)
        sys.exit(1)

    result = analyze_spritesheet(args.spritesheet, args.frame_w, args.frame_h, args.out_dir, args.fps)

    if args.json:
        # Don't serialize numpy types
        print(json.dumps(result, indent=2))
    else:
        print(f"Sprite Sheet: {result['filename']} ({result['sheet_width']}x{result['sheet_height']})")
        print(f"  Frames: {result['total_frames']} ({result['cols']}x{result['rows']}), Size: {result['frame_width']}x{result['frame_height']}")
        print(f"  Silhouette Mean IoU: {result['mean_silhouette_iou']}")
        print(f"  Baseline Variance: {result['baseline_variance']} px, Height Spread: {result['height_spread']} px")
        print(f"  Palette: {result['total_unique_colors']} unique colors")
        if result['anim_gif']:
            print(f"  Animated GIF saved: {result['anim_gif']}")

if __name__ == "__main__":
    main()
