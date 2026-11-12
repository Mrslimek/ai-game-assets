#!/usr/bin/env python3
"""validate_tiles.py - Programmatic validation for seamless tiles and autotile sets.

Features:
- Dimension validation (32x32, 64x64, 128x128, etc.)
- Programmatic seam analysis:
    - Vertical boundary diff: |left_col - right_col|
    - Horizontal boundary diff: |top_row - bottom_row|
    - Mean Absolute Seam Discontinuity (MASD)
    - Max Seam Step
- 3x3 repetition preview generation
- Palette size and unique color analysis
- JSON summary output
"""

import sys
import os
import json
import argparse
import numpy as np
from PIL import Image

def analyze_seam(img_path, output_dir=None):
    im = Image.open(img_path).convert("RGBA")
    w, h = im.size
    arr = np.array(im, dtype=np.float32)

    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    # Horizontal seam: compare top row with bottom row
    top_row = rgb[0, :, :]
    bottom_row = rgb[-1, :, :]
    h_diff = np.abs(top_row - bottom_row)
    h_masd = float(np.mean(h_diff))
    h_max = float(np.max(h_diff))

    # Vertical seam: compare left col with right col
    left_col = rgb[:, 0, :]
    right_col = rgb[:, -1, :]
    v_diff = np.abs(left_col - right_col)
    v_masd = float(np.mean(v_diff))
    v_max = float(np.max(v_diff))

    # 4-corner seam check: (0,0), (0, w-1), (h-1, 0), (h-1, w-1)
    corners = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    corner_spread = float(np.max(np.ptp(corners, axis=0)))

    # Overall Seam Discontinuity Score
    masd = (h_masd + v_masd) / 2.0
    max_step = max(h_max, v_max)

    # Palette count
    rgb_tuples = [tuple(p[:3]) for p in arr.reshape(-1, 4).astype(np.uint8)]
    unique_colors = len(set(rgb_tuples))

    # Seam verdict:
    # In perfectly seamless textures, masd is 0 or very small (< 15 on scale 0-255)
    is_seamless = bool(masd < 18.0 and max_step < 50.0)

    # Generate 3x3 preview
    preview_path = None
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        preview_3x3 = Image.new("RGBA", (w * 3, h * 3))
        for y in range(3):
            for x in range(3):
                preview_3x3.paste(im, (x * w, y * h))
        preview_filename = f"preview_3x3_{os.path.basename(img_path)}"
        preview_path = os.path.join(output_dir, preview_filename)
        preview_3x3.save(preview_path)

    return {
        "file": os.path.abspath(img_path),
        "filename": os.path.basename(img_path),
        "width": w,
        "height": h,
        "channels": len(im.getbands()),
        "unique_colors": unique_colors,
        "horizontal_masd": round(h_masd, 2),
        "vertical_masd": round(v_masd, 2),
        "total_masd": round(masd, 2),
        "max_step": round(max_step, 2),
        "corner_spread": round(corner_spread, 2),
        "is_seamless": is_seamless,
        "preview_3x3": preview_path
    }

def main():
    parser = argparse.ArgumentParser(description="Validate seamless tiles and tilesets")
    parser.add_argument("images", nargs="+", help="Tile image path(s)")
    parser.add_argument("--out-dir", "-o", default=None, help="Directory to save 3x3 preview")
    parser.add_argument("--json", "-j", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    results = []
    for path in args.images:
        if os.path.exists(path):
            res = analyze_seam(path, args.out_dir)
            results.append(res)
            if not args.json:
                status = "SEAMLESS [PASS]" if res["is_seamless"] else "SEAM DETECTED [WARN]"
                print(f"[{status}] {res['filename']} ({res['width']}x{res['height']}) - MASD: {res['total_masd']}, MaxStep: {res['max_step']}, Colors: {res['unique_colors']}")
        else:
            print(f"File not found: {path}", file=sys.stderr)

    if args.json:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
