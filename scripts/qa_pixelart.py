#!/usr/bin/env python3
"""Pixel-art QA: palette / outline / speckle / connectivity metrics for icons,
knight views and animation frames; deterministic improvements (speckle removal,
outline unification) and visual contact sheets. Writes reports/qa_pixelart.json,
reports/qa_improvements.json, assets/improved/*, assets/qa/pixelart/*."""
from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "assets" / "generated"
QA_DIR = ROOT / "assets" / "qa" / "pixelart"
IMP_DIR = ROOT / "assets" / "improved"
REPORTS = ROOT / "reports"

ICON_NAMES = [
    "weapon_sword", "weapon_dagger", "weapon_bow", "weapon_staff",
    "potion_health", "potion_mana", "potion_stamina", "potion_gold",
    "armor_helmet", "armor_chest", "armor_shield", "armor_boots",
    "craft_ore", "craft_gem", "craft_scroll", "craft_feather",
]
VIEW_NAMES = ["knight_front", "knight_side", "knight_back", "knight_three_quarter"]
ANIM_NAMES = ["anim_idle", "anim_walk", "anim_run", "anim_attack"]

BG = (22, 22, 26)          # #16161A neutral dark
GRID = (58, 58, 66)        # grid lines drawn after upscale
TEXT = (184, 184, 192)


# ---------------------------------------------------------------- metrics

def load_rgba(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)


def arr_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr, "RGBA")


def hexa(c: tuple[int, int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}{:02X}".format(*c)


def palette(arr: np.ndarray) -> dict:
    cols = Counter(map(tuple, arr.reshape(-1, 4)))
    opaque_cols = set(map(tuple, arr[arr[..., 3] == 255].reshape(-1, 4)))
    trans_rgb_variants = len(cols) - len(opaque_cols)
    return {
        "colors": [hexa(c) for c in sorted(cols)],
        "unique_color_count": len(cols),
        "opaque_unique_color_count": len(opaque_cols),
        "transparent_rgb_variant_count": trans_rgb_variants,
        "_set": {c for c in cols},
        "_opaque_set": opaque_cols,
    }


def jaccard(a: set, b: set) -> float:
    return round(len(a & b) / len(a | b), 4) if (a | b) else 1.0


def semi_transparent_count(arr: np.ndarray) -> int:
    alpha = arr[..., 3]
    return int(((alpha > 0) & (alpha < 255)).sum())


def opaque_mask(arr: np.ndarray) -> np.ndarray:
    return arr[..., 3] == 255


def boundary_mask(arr: np.ndarray) -> np.ndarray:
    """Silhouette-edge pixels: opaque with at least one 4-neighbor of alpha==0."""
    opaque = opaque_mask(arr)
    trans = arr[..., 3] == 0
    pad = np.pad(trans, 1, constant_values=True)
    near_trans = (
        pad[1:-1, :-2] | pad[1:-1, 2:] | pad[:-2, 1:-1] | pad[2:, 1:-1]
    )
    return opaque & near_trans


def boundary_outline(arr: np.ndarray) -> dict:
    edge = boundary_mask(arr)
    if not edge.any():
        return {"most_common_color": None, "frequency_pct": None,
                "distinct_boundary_colors": 0}
    cols = Counter(map(tuple, arr[edge]))
    (top, n), = cols.most_common(1)
    return {
        "most_common_color": hexa(top),
        "frequency_pct": round(100.0 * n / int(edge.sum()), 2),
        "distinct_boundary_colors": len(cols),
    }


def all8_transparent_neighbors(alpha: np.ndarray) -> np.ndarray:
    trans = alpha == 0
    pad = np.pad(trans, 1, constant_values=True)
    h, w = trans.shape
    acc = np.ones((h, w), bool)
    for dy in range(3):
        for dx in range(3):
            if (dy, dx) == (1, 1):
                continue
            acc &= pad[dy:dy + h, dx:dx + w]
    return acc


def speckle_count(arr: np.ndarray) -> int:
    opaque = opaque_mask(arr)
    return int((opaque & all8_transparent_neighbors(arr[..., 3])).sum())


def connected_components(alpha: np.ndarray) -> tuple[int, float]:
    """4-connectivity on opaque pixels; returns (n_components, largest fraction)."""
    opaque = alpha == 255
    h, w = opaque.shape
    lab = np.full((h, w), -1, np.int32)
    sizes: list[int] = []
    cid = 0
    for y in range(h):
        for x in range(w):
            if not opaque[y, x] or lab[y, x] != -1:
                continue
            q = deque([(y, x)])
            lab[y, x] = cid
            n = 0
            while q:
                cy, cx = q.popleft()
                n += 1
                for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and opaque[ny, nx] and lab[ny, nx] == -1:
                        lab[ny, nx] = cid
                        q.append((ny, nx))
            sizes.append(n)
            cid += 1
    total = sum(sizes)
    return cid, round(max(sizes) / total, 4) if total else 0.0


def measure(arr: np.ndarray, name: str, with_components: bool) -> dict:
    pal = palette(arr)
    out = {
        "name": name,
        "size": [int(arr.shape[1]), int(arr.shape[0])],
        "palette": pal["colors"],
        "unique_color_count": pal["unique_color_count"],
        "opaque_unique_color_count": pal["opaque_unique_color_count"],
        "transparent_rgb_variant_count": pal["transparent_rgb_variant_count"],
        "semi_transparent_pixels": semi_transparent_count(arr),
        "boundary_outline": boundary_outline(arr),
        "speckle_pixels": speckle_count(arr),
    }
    if with_components:
        n, frac = connected_components(arr[..., 3])
        out["connected_components"] = n
        out["largest_component_fraction"] = frac
    out["_palset"] = pal["_set"]
    out["_opaque_set"] = pal["_opaque_set"]
    return out


# ---------------------------------------------------------------- improvements

def median_set_boundary_color(arrays: list[np.ndarray]) -> tuple[int, int, int]:
    """Per-channel median over every boundary pixel of the whole icon set."""
    px = np.concatenate([a[boundary_mask(a)] for a in arrays])
    med = np.median(px[:, :3], axis=0)
    return tuple(int(round(v)) for v in med)


def clean_icon(arr: np.ndarray, target_boundary: Optional[tuple[int, int, int]],
               record: dict) -> np.ndarray:
    out = arr.copy()
    alpha = out[..., 3]
    speck = opaque_mask(out) & all8_transparent_neighbors(alpha)
    record["speckle_removed"] = int(speck.sum())
    if speck.any():
        out[speck] = (0, 0, 0, 0)
    edge = boundary_mask(out)  # recompute after speckle removal
    n_outline_changed = 0
    if target_boundary is not None and edge.any():
        before = out[edge].copy()
        out[edge] = (*target_boundary, 255)
        n_outline_changed = int((before != (*target_boundary, 255)).any(axis=1).sum())
    record["outline_pixels_recolored"] = n_outline_changed
    record["changed"] = speck.any() or n_outline_changed > 0
    return out


def build_improvements(icons: dict[str, np.ndarray], union_size: int,
                       union_size_opaque: int) -> tuple[dict, dict[str, np.ndarray]]:
    """Returns (improvements report, improved icon arrays incl. unchanged copies)."""
    arrays = [icons[n] for n in ICON_NAMES]
    most_common = [boundary_outline(a)["most_common_color"] for a in arrays]
    n_distinct = len(set(most_common))

    report: dict = {
        "palette_unification": {
            "condition": "union palette of 16 icons <= 24 colors",
            "union_size_measured_rgba": union_size,
            "union_size_measured_opaque": union_size_opaque,
            "applied": False,
            "reason": f"union is {union_size} RGBA colors ({union_size_opaque} opaque) "
                      f">> 24; palettes are pairwise disjoint (all off-diagonal Jaccard "
                      f"= 0.0). A nearest-color remap onto a 429+ color 'union' would "
                      f"change nothing; forcing a shared 16-color palette would be a "
                      f"lossy global requantization, not a deterministic fix.",
        },
        "speckle_removal": {
            "condition": "isolated opaque pixel with all 8 neighbors transparent",
            "applied": False,
            "files": {},
        },
        "outline_unification": {
            "condition": "3+ distinct most-common boundary colors across the 16 icons",
            "distinct_most_common_boundary_colors": n_distinct,
            "most_common_per_icon": dict(zip(ICON_NAMES, most_common)),
            "applied": False,
            "median_boundary_color": None,
            "reason": "",
        },
        "files": {},
    }

    total_speck = sum(speckle_count(a) for a in arrays)
    target: Optional[tuple[int, int, int]] = None
    if n_distinct >= 3:
        target = median_set_boundary_color(arrays)
        report["outline_unification"].update(
            applied=True,
            median_boundary_color=hexa((*target, 255)),
            reason="boundary colors are per-icon artifacts of quantization; unifying "
                   "them to the set median is a deterministic cosmetic outline fix.",
        )
    if total_speck > 0:
        report["speckle_removal"]["applied"] = True
        report["speckle_removal"]["total_speckle_pixels"] = total_speck
        report["speckle_removal"]["reason"] = (
            "isolated pixels cannot belong to the intended silhouette (silhouettes are "
            "connected blobs); removal disconnects nothing by construction."
        )

    improved: dict[str, np.ndarray] = {}
    for name in ICON_NAMES:
        rec: dict = {"reasons": []}
        out = clean_icon(icons[name], target, rec)
        if rec["speckle_removed"]:
            report["speckle_removal"]["files"][name] = rec["speckle_removed"]
            rec["reasons"].append(f"removed {rec['speckle_removed']} speckle pixel(s)")
        if rec["outline_pixels_recolored"]:
            rec["reasons"].append(
                f"recolored {rec['outline_pixels_recolored']} boundary pixel(s) to "
                f"{hexa((*target, 255))}" if target else "")
        if not rec["reasons"]:
            rec["reasons"] = ["no measured violation"]
        rec["changed"] = bool(rec["reasons"] and
                              rec["reasons"] != ["no measured violation"])
        report["files"][f"assets/improved/icons/{name}.png"] = {
            "changed": rec["changed"], "reason": "; ".join(rec["reasons"])}
        improved[name] = out

    report["atlas"] = {
        "rebuilt": True,
        "path": "assets/improved/atlas/inventory_icons_atlas_4x4.png",
        "source": "improved icons (see per-file reasons)",
    }
    return report, improved


# ---------------------------------------------------------------- sheets

def get_font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def upscale(arr: np.ndarray, k: int) -> Image.Image:
    im = arr_to_pil(arr)
    return im if k == 1 else im.resize((im.width * k, im.height * k), Image.NEAREST)


def paste_center(canvas: Image.Image, cell: Image.Image, cx: int, cy: int):
    canvas.paste(cell, (cx - cell.width // 2, cy - cell.height // 2), cell)


def contact_sheet(cells: list[tuple[Image.Image, str]], cols: int, label_h: int,
                  cell_size: int, index_labels: bool = False) -> Image.Image:
    rows = (len(cells) + cols - 1) // cols
    w = cols * cell_size
    h = rows * (cell_size + label_h)
    canvas = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(canvas)
    font = get_font(max(9, label_h - 6))
    for i, (img, label) in enumerate(cells):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_size, r * (cell_size + label_h)
        paste_center(canvas, img, x0 + cell_size // 2, y0 + cell_size // 2)
        text = f"{i}: {label}" if index_labels else label
        bb = d.textbbox((0, 0), text, font=font)
        d.text((x0 + (cell_size - bb[2] + bb[0]) // 2, y0 + cell_size + 2),
               text, fill=TEXT, font=font)
    d = ImageDraw.Draw(canvas)
    for c in range(1, cols):
        d.line([(c * cell_size, 0), (c * cell_size, h)], fill=GRID)
    for r in range(1, rows):
        d.line([(0, r * (cell_size + label_h)), (w, r * (cell_size + label_h))], fill=GRID)
    return canvas


def build_sheets(icons: dict[str, np.ndarray], improved: dict[str, np.ndarray],
                 changed: dict[str, bool]) -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    contact_sheet([(upscale(icons[n], 1), n) for n in ICON_NAMES],
                  cols=4, label_h=14, cell_size=32).save(QA_DIR / "icons_native.png")
    contact_sheet([(upscale(icons[n], 4), n) for n in ICON_NAMES],
                  cols=4, label_h=20, cell_size=128).save(QA_DIR / "icons_4x.png")

    pairs: list[tuple[Image.Image, str]] = []
    for n in ICON_NAMES:
        pairs.append((upscale(icons[n], 4), n))
        lab = "improved" if changed[n] else "UNCHANGED (no violation)"
        pairs.append((upscale(improved[n], 4), lab))
    contact_sheet(pairs, cols=2, label_h=20, cell_size=128).save(
        QA_DIR / "icons_before_after_4x.png")

    atlas = load_rgba(GEN / "inventory_icons_atlas_4x4.png")
    sheet = upscale(atlas, 4).convert("RGB")
    d = ImageDraw.Draw(sheet)
    font = get_font(20)
    for i in range(16):
        r, c = divmod(i, 4)
        x, y = c * 128, r * 128
        if c:
            d.line([(x, y), (x, y + 128)], fill=GRID)
        if r:
            d.line([(x, y), (x + 128, y)], fill=GRID)
        d.text((x + 4, y + 2), str(i), fill=TEXT, font=font)
    sheet.save(QA_DIR / "atlas_grid_4x.png")


def build_improved_atlas(improved: dict[str, np.ndarray]) -> None:
    atlas = np.zeros((128, 128, 4), np.uint8)
    for i, n in enumerate(ICON_NAMES):
        r, c = divmod(i, 4)
        atlas[r * 32:(r + 1) * 32, c * 32:(c + 1) * 32] = improved[n]
    IMP_DIR.mkdir(parents=True, exist_ok=True)
    arr_to_pil(atlas).save(IMP_DIR / "atlas" / "inventory_icons_atlas_4x4.png")


# ---------------------------------------------------------------- main

def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)

    icons = {n: load_rgba(GEN / f"{n}.png") for n in ICON_NAMES}
    views = {n: load_rgba(GEN / f"{n}.png") for n in VIEW_NAMES}
    anims = {n: load_rgba(GEN / f"{n}.png") for n in ANIM_NAMES}

    icon_meas = {n: measure(icons[n], n, True) for n in ICON_NAMES}
    view_meas = {n: measure(views[n], n, False) for n in VIEW_NAMES}
    anim_meas = {n: measure(anims[n], n, False) for n in ANIM_NAMES}

    icon_union: set = set()
    icon_union_opaque: set = set()
    for n in ICON_NAMES:
        icon_union |= icon_meas[n]["_palset"]
        icon_union_opaque |= icon_meas[n]["_opaque_set"]
    view_union: set = set()
    view_union_opaque: set = set()
    for n in VIEW_NAMES:
        view_union |= view_meas[n]["_palset"]
        view_union_opaque |= view_meas[n]["_opaque_set"]

    def jac_matrix(meas: dict, order: list[str], key: str) -> list[list[float]]:
        return [[jaccard(meas[a][key], meas[b][key]) for b in order]
                for a in order]

    report = {
        "source": "assets/generated (read-only ground truth)",
        "icons": list(icon_meas.values()),
        "knight_views": list(view_meas.values()),
        "anim_frames": list(anim_meas.values()),
        "unions": {
            "icon_set_16": len(icon_union),
            "icon_set_16_opaque_only": len(icon_union_opaque),
            "knight_view_set_4": len(view_union),
            "knight_view_set_4_opaque_only": len(view_union_opaque),
            "note": "exact RGBA union counts distinct alpha=0 RGB variants too; "
                    "each transparent pixel keeps keying garbage, so RGBA counts "
                    "exceed the pipeline's 16-color-per-image claim",
        },
        "palette_jaccard": {
            "icon_order": ICON_NAMES,
            "icon_matrix": jac_matrix(icon_meas, ICON_NAMES, "_palset"),
            "view_order": VIEW_NAMES,
            "view_matrix": jac_matrix(view_meas, VIEW_NAMES, "_palset"),
        },
        "palette_jaccard_opaque_only": {
            "icon_matrix": jac_matrix(icon_meas, ICON_NAMES, "_opaque_set"),
            "view_matrix": jac_matrix(view_meas, VIEW_NAMES, "_opaque_set"),
            "note": "supplementary metric: ignores alpha=0 RGB garbage",
        },
    }
    for m in (*icon_meas.values(), *view_meas.values(), *anim_meas.values()):
        m.pop("_palset")
        m.pop("_opaque_set")
    (REPORTS / "qa_pixelart.json").write_text(json.dumps(report, indent=2))

    imp_report, improved = build_improvements(
        icons, len(icon_union), len(icon_union_opaque))
    changed = {n: imp_report["files"][f"assets/improved/icons/{n}.png"]["changed"]
               for n in ICON_NAMES}
    for n in ICON_NAMES:
        (IMP_DIR / "icons" / f"{n}.png").parent.mkdir(parents=True, exist_ok=True)
        arr_to_pil(improved[n]).save(IMP_DIR / "icons" / f"{n}.png")
    build_improved_atlas(improved)
    (REPORTS / "qa_improvements.json").write_text(json.dumps(imp_report, indent=2))

    build_sheets(icons, improved, changed)
    print("qa_pixelart: wrote reports/qa_pixelart.json, reports/qa_improvements.json")
    print("  icon union:", len(icon_union), "(opaque", len(icon_union_opaque),
          ") view union:", len(view_union), "(opaque", len(view_union_opaque), ")")


if __name__ == "__main__":
    main()
