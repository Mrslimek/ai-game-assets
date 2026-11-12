#!/usr/bin/env python3
"""make_contact_sheet.py - Assembles images into labeled, grid-aligned contact sheets.

Features:
- Configurable columns, tile scaling (e.g. 1x, 2x, 4x, 8x nearest-neighbor)
- Title banner and individual item captions
- Clean dark background for pixel art readability
"""

import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFont

def make_contact_sheet(image_items, out_path, cols=4, scale=4, title=None, padding=16):
    """
    image_items: list of (img_path_or_Image, label_str)
    """
    if not image_items:
        print("No images to assemble.", file=sys.stderr)
        return

    loaded = []
    max_w = 0
    max_h = 0
    for item, label in image_items:
        if isinstance(item, str):
            im = Image.open(item).convert("RGBA")
        else:
            im = item.convert("RGBA")
        if scale > 1:
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        max_w = max(max_w, im.width)
        max_h = max(max_h, im.height)
        loaded.append((im, label))

    rows = (len(loaded) + cols - 1) // cols
    label_h = 24
    cell_w = max_w + padding
    cell_h = max_h + label_h + padding

    header_h = 48 if title else padding
    total_w = padding + cols * cell_w
    total_h = header_h + rows * cell_h

    sheet = Image.new("RGBA", (total_w, total_h), (24, 24, 28, 255))
    draw = ImageDraw.Draw(sheet)

    if title:
        draw.text((padding, padding), title, fill=(240, 240, 245, 255))

    for idx, (im, label) in enumerate(loaded):
        c = idx % cols
        r = idx // cols
        x = padding + c * cell_w
        y = header_h + r * cell_h

        # draw thumbnail centered
        img_x = x + (max_w - im.width) // 2
        img_y = y + (max_h - im.height) // 2
        sheet.paste(im, (img_x, img_y), im)

        # draw label
        if label:
            draw.text((x, y + max_h + 4), label, fill=(180, 185, 195, 255))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    print(f"Contact sheet saved: {out_path} ({total_w}x{total_h})")

def main():
    parser = argparse.ArgumentParser(description="Create labeled contact sheet")
    parser.add_argument("images", nargs="+", help="Image paths")
    parser.add_argument("--out", "-o", required=True, help="Output image path")
    parser.add_argument("--cols", "-c", type=int, default=4, help="Number of columns")
    parser.add_argument("--scale", "-s", type=int, default=4, help="Nearest-neighbor upscale factor")
    parser.add_argument("--title", "-t", default=None, help="Contact sheet header title")
    args = parser.parse_args()

    items = [(p, os.path.basename(p)) for p in args.images if os.path.exists(p)]
    make_contact_sheet(items, args.out, cols=args.cols, scale=args.scale, title=args.title)

if __name__ == "__main__":
    main()
