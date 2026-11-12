#!/usr/bin/env python3
"""Character QA: knight view / animation-frame shape metrics, head-body split,
region palettes, animation-sheet registration (registered sheet + GIF previews)
and visual contact sheets. Writes reports/qa_characters.json and outputs under
assets/qa/characters/ and assets/improved/."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "assets" / "generated"
QA_DIR = ROOT / "assets" / "qa" / "characters"
IMP_DIR = ROOT / "assets" / "improved"
REPORTS = ROOT / "reports"

VIEW_NAMES = ["knight_front", "knight_side", "knight_back", "knight_three_quarter"]
ANIM_NAMES = ["anim_idle", "anim_walk", "anim_run", "anim_attack"]
SHEET_FRAMES = ["idle", "walk", "run", "attack"]

BG = (22, 22, 26)
GRID = (58, 58, 66)
TEXT = (184, 184, 192)
TINTS = {"knight_front": (255, 80, 80), "knight_side": (80, 230, 80),
         "knight_back": (90, 140, 255), "knight_three_quarter": (230, 80, 255)}


def load_rgba(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)


def hexa(c) -> str:
    return "#{:02X}{:02X}{:02X}{:02X}".format(int(c[0]), int(c[1]), int(c[2]), int(c[3]))


def jaccard(a: set, b: set) -> float:
    return round(len(a & b) / len(a | b), 4) if (a | b) else 1.0


def color_sets(arr: np.ndarray) -> tuple[set, set]:
    rgba = {tuple(c) for c in arr.reshape(-1, 4)}
    opaque = {tuple(c) for c in arr[arr[..., 3] == 255].reshape(-1, 4)}
    return rgba, opaque


# ---------------------------------------------------------------- shape metrics

def shape_metrics(arr: np.ndarray) -> dict:
    opaque = arr[..., 3] == 255
    ys, xs = np.nonzero(opaque)
    top, bottom = int(ys.min()), int(ys.max())
    left, right = int(xs.min()), int(xs.max())
    centroid_x = round(float(xs.mean()), 2)
    rows = [int(opaque[y, left:right + 1].sum()) for y in range(top, bottom + 1)]
    widths = []
    for y in range(top, bottom + 1):
        xs_y = np.nonzero(opaque[y, left:right + 1])[0]
        widths.append(int(xs_y.max() - xs_y.min() + 1) if len(xs_y) else 0)
    return {
        "char_width": right - left + 1,
        "char_height": bottom - top + 1,
        "baseline": bottom,
        "bbox_left": left,
        "bbox_top": top,
        "centroid_x": centroid_x,
        "silhouette_row_counts": rows,
        "_widths": widths,
        "_top": top,
    }


def head_body_split(m: dict) -> dict:
    """Neck = deepest strict width valley (w[y] < w[y-1] and w[y] < w[y+1]) within
    the upper 45% of the bbox, required to narrow <=80% of the bulge above it
    (a helmet/plume taper never qualifies because it is monotonically increasing)."""
    widths, top, h = m["_widths"], m["_top"], m["char_height"]
    zone = max(3, int(0.45 * h))
    valleys = [y for y in range(2, min(zone - 1, len(widths) - 1))
               if widths[y] < widths[y - 1] and widths[y] < widths[y + 1]]
    best = min(valleys, key=lambda y: (widths[y], y)) if valleys else None
    convincing = (best is not None
                  and 0.12 * h <= best
                  and widths[best] >= 4
                  and max(widths[:best + 1]) >= 8
                  and widths[best] <= 0.8 * max(widths[:best + 1]))
    res = {"neck_y": None, "head_h": None, "body_h": None,
           "head_body_ratio": None, "head_undetected": True,
           "width_valleys_in_upper_45pct":
               [[top + y, widths[y]] for y in valleys]}
    if convincing:
        head_h = best + 1
        body_h = len(widths) - head_h
        res.update(neck_y=top + best, head_h=head_h, body_h=body_h,
                   head_body_ratio=round(head_h / body_h, 3) if body_h else None,
                   head_undetected=False)
    return res


def region_palettes(arr: np.ndarray) -> dict:
    opaque = arr[arr[..., 3] == 255]
    if not len(opaque):
        return {}
    ys, _ = np.nonzero(arr[..., 3] == 255)
    top, bottom = ys.min(), ys.max()
    h3 = (bottom - top + 1) / 3.0
    out = {}
    for name, lo, hi in (("top", 0, 1), ("mid", 1, 2), ("bottom", 2, 3)):
        y0, y1 = top + int(lo * h3), top + int(hi * h3)
        seg = arr[y0:y1][arr[y0:y1, ..., 3] == 255]
        if not len(seg):
            out[name] = []
            continue
        cnt = Counter(map(tuple, seg.reshape(-1, 4)))
        out[name] = [{"color": hexa(c), "count": n} for c, n in cnt.most_common(3)]
    return out


def full_metrics(arr: np.ndarray, name: str, ref: tuple[set, set]) -> dict:
    m = shape_metrics(arr)
    rgba, opaque = color_sets(arr)
    head = head_body_split(m)
    out = {
        "name": name,
        "size": [int(arr.shape[1]), int(arr.shape[0])],
        **{k: v for k, v in m.items() if not k.startswith("_")},
        "head_body_split": head,
        "region_palettes": region_palettes(arr),
        "palette_vs_knight_front": {
            "jaccard_rgba": jaccard(rgba, ref[0]),
            "jaccard_opaque": jaccard(opaque, ref[1]),
        },
    }
    return out


# ---------------------------------------------------------------- sheet registration

def frame_metrics(arr: np.ndarray) -> dict:
    m = shape_metrics(arr)
    return {k: m[k] for k in ("char_width", "char_height", "baseline",
                              "bbox_left", "centroid_x")} | {"_m": m}


def translate(arr: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift content by (dx, dy), clipped at the frame edge, no wraparound."""
    out = np.zeros_like(arr)
    h, w = arr.shape[:2]
    x0, x1 = max(0, dx), min(w, w + dx)
    y0, y1 = max(0, dy), min(h, h + dy)
    if x1 <= x0 or y1 <= y0:
        return out
    out[y0:y1, x0:x1] = arr[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return out


def build_sheet_metrics() -> tuple[dict, np.ndarray]:
    sheet = load_rgba(GEN / "knight_animation_sheet.png")
    frames = [sheet[:, i * 64:(i + 1) * 64] for i in range(4)]
    ms = [frame_metrics(f) for f in frames]
    base = ms[0]
    per = []
    offsets = []
    for name, m, f in zip(SHEET_FRAMES, ms, frames):
        dx = round(base["centroid_x"] - m["centroid_x"], 2)
        dy = int(base["baseline"] - m["baseline"])
        offsets.append((dx, dy))
        per.append({"frame": name,
                    **{k: m[k] for k in m if k != "_m"},
                    "registration_dx": dx, "registration_dy": dy})
    registered = np.zeros_like(sheet)
    for i, (f, (dx, dy)) in enumerate(zip(frames, offsets)):
        registered[:, i * 64:(i + 1) * 64] = translate(f, int(round(dx)), dy)
    report = {"sheet": "knight_animation_sheet.png",
              "note": "sheet composes four independently generated frames of "
                      "DIFFERENT actions; not a coherent 4-frame animation",
              "frames": per,
              "registration": "dx aligns centroid_x to frame 1, dy aligns baseline to frame 1"}
    return report, registered


def save_registered_and_gifs(registered: np.ndarray) -> None:
    IMP_DIR.mkdir(parents=True, exist_ok=True)
    arr = load_rgba(GEN / "knight_animation_sheet.png")
    Image.fromarray(registered, "RGBA").save(
        IMP_DIR / "knight_animation_sheet_registered.png")
    QA_DIR.mkdir(parents=True, exist_ok=True)

    def frames_list(a: np.ndarray) -> list[Image.Image]:
        ims = []
        for i in range(4):
            f = a[:, i * 64:(i + 1) * 64]
            im = Image.fromarray(f, "RGBA").resize((256, 256), Image.NEAREST)
            bg = Image.new("RGB", (256, 256), BG)
            bg.paste(im, (0, 0), im)
            ims.append(bg)
        return ims

    for tag, a in (("unregistered", arr), ("registered", registered)):
        ims = frames_list(a)
        ims[0].save(QA_DIR / f"knight_sheet_{tag}_x4.gif", save_all=True,
                    append_images=ims[1:], duration=100, loop=0)


# ---------------------------------------------------------------- sheets

def get_font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def upscale(arr: np.ndarray, k: int) -> Image.Image:
    im = Image.fromarray(arr, "RGBA")
    return im if k == 1 else im.resize((im.width * k, im.height * k), Image.NEAREST)


def grid_sheet(images: list[tuple[Image.Image, str]], cols: int, label_h: int,
               cell: int) -> Image.Image:
    rows = (len(images) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell, rows * (cell + label_h)), BG)
    font = get_font(max(9, label_h - 6))
    for i, (img, label) in enumerate(images):
        r, c = divmod(i, cols)
        x0, y0 = c * cell, r * (cell + label_h)
        canvas.paste(img, (x0 + (cell - img.width) // 2, y0 + (cell - img.height) // 2), img)
        d = ImageDraw.Draw(canvas)
        bb = d.textbbox((0, 0), label, font=font)
        d.text((x0 + (cell - bb[2]) // 2, y0 + cell + 2), label, fill=TEXT, font=font)
    d = ImageDraw.Draw(canvas)
    for c in range(1, cols):
        d.line([(c * cell, 0), (c * cell, rows * (cell + label_h))], fill=GRID)
    for r in range(1, rows):
        d.line([(0, r * (cell + label_h)), (cols * cell, r * (cell + label_h))], fill=GRID)
    return canvas


def overlay_sheet(views: dict[str, np.ndarray], ms: dict[str, dict]) -> Image.Image:
    cell, legend_w = 256, 480
    acc = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    for i, (name, arr) in enumerate(views.items()):
        f = np.array(upscale(arr, 4), dtype=np.float32)
        f[..., :3] *= np.array(TINTS[name], np.float32) / 255.0
        f[..., 3] *= 0.5 if i < 2 else 0.25
        acc = Image.alpha_composite(
            acc, Image.fromarray(f.astype(np.uint8), "RGBA"))
    canvas = Image.new("RGB", (cell + legend_w, 348), BG)
    base = Image.new("RGB", (cell, cell), BG)
    base.paste(acc, (0, 0), acc)
    canvas.paste(base, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.text((10, cell + 6), "front+side @50%, back+3/4 @25%", fill=TEXT, font=get_font(13))
    font = get_font(13)
    front = ms["knight_front"]
    x, y = cell + 10, 8
    rows = [("front", "knight_front"), ("side", "knight_side"),
            ("back", "knight_back"), ("3/4", "knight_three_quarter")]
    for label, name in rows:
        d.rectangle([x, y, x + 12, y + 12], fill=TINTS[name])
        m = ms[name]
        d.text((x + 18, y - 1),
               f"{label}: h{m['char_height']} "
               f"({m['char_height'] - front['char_height']:+d}) base "
               f"{m['baseline']} ({m['baseline'] - front['baseline']:+d})",
               fill=TEXT, font=font)
        y += 16
    y += 4
    d.multiline_text((x, y),
                     "\n".join(
                         [f"{name}: left {ms[name]['bbox_left'] - front['bbox_left']:+d}, "
                          f"cx {ms[name]['centroid_x'] - front['centroid_x']:+.2f}"
                          for _, name in rows] + [""] +
                         [f"{name}: pal rgba "
                          f"{ms[name]['palette_vs_knight_front']['jaccard_rgba']} / "
                          f"opaque {ms[name]['palette_vs_knight_front']['jaccard_opaque']}"
                          for _, name in rows] + [""] +
                         [(f"{name}: neck {ms[name]['head_body_split']['neck_y']}, "
                           f"ratio {ms[name]['head_body_split']['head_body_ratio']}"
                           + (" [head_undetected]"
                              if ms[name]["head_body_split"]["head_undetected"] else ""))
                          for _, name in rows]),
                     fill=TEXT, font=font)
    return canvas


def annotated_sheet(sheet: np.ndarray, ms: list[dict]) -> Image.Image:
    """4x sheet: red line under each frame's baseline row, cyan centroid column."""
    big = upscale(sheet, 4)
    d = ImageDraw.Draw(big)
    for i, m in enumerate(ms):
        x0 = i * 256
        y = (m["baseline"] + 1) * 4 - 1
        d.line([(x0, y), (x0 + 255, y)], fill=(255, 40, 40))
        cx = int(round(m["centroid_x"])) * 4
        d.line([(cx, 0), (cx, 255)], fill=(40, 220, 255))
        d.text((x0 + 4, 2), SHEET_FRAMES[i], fill=TEXT, font=get_font(16))
    return big


def record_registered_sheet(sheet_report: dict) -> None:
    """Log the registration-only knight improvement in qa_improvements.json."""
    path = REPORTS / "qa_improvements.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    frames = sheet_report["frames"]
    data["knight_assets"] = {
        "policy": "no repainting; registration only (deliverable 4d)",
        "files": {
            "assets/improved/knight_animation_sheet_registered.png": {
                "changed": any(f["registration_dx"] or f["registration_dy"]
                               for f in frames),
                "reason": "per-frame translation aligning centroid_x and baseline "
                          "to frame 1: " + ", ".join(
                              f"{f['frame']} dx={f['registration_dx']:+.2f} "
                              f"dy={f['registration_dy']:+d}" for f in frames),
            },
            "assets/generated/knight_*.png": {"changed": False,
                                              "reason": "read-only ground truth"},
        },
    }
    path.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------- main

def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    views = {n: load_rgba(GEN / f"{n}.png") for n in VIEW_NAMES}
    anims = {n: load_rgba(GEN / f"{n}.png") for n in ANIM_NAMES}
    ref = color_sets(views["knight_front"])

    view_ms = {n: full_metrics(views[n], n, ref) for n in VIEW_NAMES}
    anim_ms = {n: full_metrics(anims[n], n, ref) for n in ANIM_NAMES}
    sheet_report, registered = build_sheet_metrics()

    report = {
        "knight_views": list(view_ms.values()),
        "anim_frames": list(anim_ms.values()),
        "animation_sheet": sheet_report,
    }
    (REPORTS / "qa_characters.json").write_text(json.dumps(report, indent=2))
    record_registered_sheet(sheet_report)

    save_registered_and_gifs(registered)

    QA_DIR.mkdir(parents=True, exist_ok=True)
    grid_sheet([(upscale(views[n], 1), n) for n in VIEW_NAMES], 4, 14, 64) \
        .save(QA_DIR / "knight_views_native.png")
    grid_sheet([(upscale(views[n], 4), n) for n in VIEW_NAMES], 4, 20, 256) \
        .save(QA_DIR / "knight_views_4x.png")
    grid_sheet([(upscale(anims[n], 4), n.replace("anim_", "")) for n in ANIM_NAMES],
               4, 20, 256).save(QA_DIR / "anim_frames_4x.png")

    turn = [upscale(views[n], 1) for n in
            ("knight_front", "knight_side", "knight_back", "knight_three_quarter")]
    turn4 = [upscale(views[n], 4) for n in
             ("knight_front", "knight_side", "knight_back", "knight_three_quarter")]
    for tag, ims, sz in (("knight_views_turntable", turn, 64),
                         ("knight_views_turntable_x4", turn4, 256)):
        composites = []
        for im in ims:
            bg = Image.new("RGB", (sz, sz), BG)
            bg.paste(im, (0, 0), im)
            composites.append(bg)
        composites[0].save(QA_DIR / f"{tag}.gif", save_all=True,
                           append_images=composites[1:], duration=600, loop=0)

    overlay_sheet(views, view_ms).save(QA_DIR / "knight_views_overlay_4x.png")

    sheet = load_rgba(GEN / "knight_animation_sheet.png")
    per = [frame_metrics(sheet[:, i * 64:(i + 1) * 64]) for i in range(4)]
    annotated_sheet(sheet, per).save(QA_DIR / "knight_sheet_annotated_4x.png")

    print("qa_characters: wrote reports/qa_characters.json + sheets")
    for n, m in {**view_ms, **anim_ms}.items():
        hb = m["head_body_split"]
        print(f"  {n:22s} h={m['char_height']} base={m['baseline']} "
              f"cx={m['centroid_x']} neck={hb['neck_y']} "
              f"jac_front(rgba)={m['palette_vs_knight_front']['jaccard_rgba']}")
    print("  sheet offsets:", [(f["frame"], f["registration_dx"], f["registration_dy"])
                              for f in sheet_report["frames"][1:]])


if __name__ == "__main__":
    main()
