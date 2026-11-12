#!/usr/bin/env python3
"""qa_terrain.py - Phase-2 terrain & autotiling QA suite.

Computes per-tile metrics for the 10 seamless terrain tiles in assets/generated,
renders repetition / transition / mixed / atlas / sanity maps into
assets/qa/terrain, runs connectivity validators on every rendered map, and
writes reports/qa_terrain.json.

Metric definitions (as implemented):
- avg_row_seam / avg_col_seam: mean |top-row - bottom-row| / |left-col - right-col|
  over all pixels and channels (0 for a perfectly seamless tile).
- autoperiod_x / autoperiod_y: lag (>=2) of the best normalized autocorrelation
  peak of the grayscale image shifted along that axis, lags 2..N//2;
  autoperiod_strength: that peak's correlation value.
- edge_density_mean / edge_density_cv: Sobel magnitude mean and std/mean.
- luminance_drift: least-squares slope of column-means vs x and row-means vs y
  per channel, scaled by (dim-1) so the unit is gray levels across the tile;
  magnitude sqrt(sx^2+sy^2) averaged over channels.
- palette_size: number of distinct RGB colors.

A verdict flag means "no algorithmic defect found", not "production ready".
"""

import os
import sys
import json
import argparse
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_autotile_map as bam

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_DIR = os.path.join(ROOT, "assets", "generated")
QA_DIR = os.path.join(ROOT, "assets", "qa", "terrain")
REPORTS_DIR = os.path.join(ROOT, "reports")

TERRAINS = ["grass", "dirt", "sand", "stone", "water"]
SIZES = [32, 64]


# ---------------------------------------------------------------- metrics

def seam_diffs(arr):
    row_seam = float(np.abs(arr[0] - arr[-1]).mean())
    col_seam = float(np.abs(arr[:, 0] - arr[:, -1]).mean())
    return row_seam, col_seam


def autocorrelation_peak(gray, axis):
    """Best normalized autocorr peak over lags 2..N//2 along `axis`."""
    g = gray - gray.mean()
    n = gray.shape[axis]
    var = float((g * g).mean())
    if var < 1e-9:
        return 0, 0.0
    best_lag, best = 0, -1.0
    for lag in range(2, n // 2 + 1):
        if axis == 0:
            a, b = g[:-lag, :], g[lag:, :]
        else:
            a, b = g[:, :-lag], g[:, lag:]
        c = float((a * b).mean()) / var
        if c > best:
            best, best_lag = c, lag
    return best_lag, best


def sobel_magnitude(gray):
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=float)
    ky = kx.T
    pad = np.pad(gray, 1, mode="edge")
    gx = sum(kx[i, j] * pad[i:i + gray.shape[0], j:j + gray.shape[1]]
             for i in range(3) for j in range(3))
    gy = sum(ky[i, j] * pad[i:i + gray.shape[0], j:j + gray.shape[1]]
             for i in range(3) for j in range(3))
    return np.hypot(gx, gy)


def linear_drift(arr):
    """Per-channel slope of column-means (x) and row-means (y), scaled to
    gray levels across the tile; combined magnitude averaged over channels."""
    h, w = arr.shape[:2]
    xs = np.arange(w) / (w - 1)
    ys = np.arange(h) / (h - 1)
    drifts = []
    for c in range(arr.shape[2]):
        col_mean = arr[:, :, c].mean(axis=0)
        row_mean = arr[:, :, c].mean(axis=1)
        sx = float(np.polyfit(xs, col_mean, 1)[0])
        sy = float(np.polyfit(ys, row_mean, 1)[0])
        drifts.append(np.hypot(sx, sy))
    return float(np.mean(drifts))


def verdict_flags(m):
    flags = []
    if max(m["avg_row_seam"], m["avg_col_seam"]) > 12:
        flags.append("seam_suspect")
    if m["autoperiod_strength"] > 0.8 and min(m["autoperiod_x"], m["autoperiod_y"]) <= 8:
        flags.append("pattern_suspect")
    if m["edge_density_cv"] > 0.5:
        flags.append("density_uneven")
    if m["luminance_drift"] > 8:
        flags.append("drift")
    return flags


def measure_tile(path):
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im, dtype=float)
    gray = arr.mean(axis=2)
    lag_x, str_x = autocorrelation_peak(gray, axis=1)
    lag_y, str_y = autocorrelation_peak(gray, axis=0)
    row_seam, col_seam = seam_diffs(arr)
    mag = sobel_magnitude(gray)
    colors = {tuple(p) for p in np.asarray(im).reshape(-1, 3)}
    m = {
        "file": os.path.basename(path),
        "size": im.width,
        "avg_row_seam": round(row_seam, 4),
        "avg_col_seam": round(col_seam, 4),
        "autoperiod_x": int(lag_x),
        "autoperiod_y": int(lag_y),
        "autoperiod_strength": round(max(str_x, str_y), 4),
        "edge_density_mean": round(float(mag.mean()), 4),
        "edge_density_cv": round(float(mag.std() / max(mag.mean(), 1e-9)), 4),
        "luminance_drift": round(linear_drift(arr), 4),
        "palette_size": len(colors),
    }
    m["verdict_flags"] = verdict_flags(m)
    return m


# ------------------------------------------------------------- rendering

def pixel_edge_diffs(map_img, tile_size, grid_w, grid_h):
    """Mean |diff| across internal tile boundaries of a rendered map."""
    arr = np.asarray(map_img.convert("RGB"), dtype=float)
    diffs = []
    for x in range(1, grid_w):
        diffs.append(np.abs(arr[:, x * tile_size - 1] - arr[:, x * tile_size]).mean())
    for y in range(1, grid_h):
        diffs.append(np.abs(arr[y * tile_size - 1, :] - arr[y * tile_size, :]).mean())
    return round(float(np.mean(diffs)), 4) if diffs else 0.0


def save_pair(img, name, with_x4):
    img.save(os.path.join(QA_DIR, name))
    if with_x4:
        bam.save_x4(img, os.path.join(QA_DIR, name.replace(".png", "_x4.png")))


def load_tile(terrain, size):
    return Image.open(os.path.join(GEN_DIR, f"{terrain}_{size}.png")).convert("RGBA")


def main():
    ap = argparse.ArgumentParser(description="Phase-2 terrain & autotiling QA")
    ap.parse_args()

    os.makedirs(QA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {"tiles": [], "connectivity": {}, "meta": {}}

    # ---- per-tile metrics for the 10 source tiles
    for t in TERRAINS:
        for s in SIZES:
            report["tiles"].append(measure_tile(os.path.join(GEN_DIR, f"{t}_{s}.png")))

    # ---- repetition maps
    for t in TERRAINS:
        for s in SIZES:
            tile = load_tile(t, s)
            for g in (10, 30):
                rep = Image.new("RGBA", (g * s, g * s))
                for y in range(g):
                    for x in range(g):
                        rep.paste(tile, (x * s, y * s))
                name = f"repetition_{g}x{g}_{t}_{s}.png"
                with_x4 = (g, s) in ((10, 64), (30, 32))
                save_pair(rep, name, with_x4)
                report["connectivity"][name] = {
                    "type": "repetition",
                    "shared_edge_pixel_diff": pixel_edge_diffs(rep, s, g, g),
                    "mismatch_count": 0, "edges_checked": 0,
                    "note": "identical tiles; pixel diff across internal boundaries equals tile seam",
                }

    # ---- transition maps (Wang16 island, overlay=first, base=second)
    for pair in (("grass", "dirt"), ("grass", "water"), ("dirt", "stone")):
        o_im = load_tile(pair[0], 64)
        b_im = load_tile(pair[1], 64)
        w_tiles, _ = bam.build_wang16_tileset(o_im, b_im)
        grid = bam.generate_sample_island_map(13, 13, np.random.default_rng(7))
        map_img = bam.render_wang_map(grid, w_tiles, 64)
        name = f"transition_{pair[0]}-{pair[1]}_12x12.png"
        save_pair(map_img, name, True)
        report["connectivity"][name] = {
            "type": "wang16_island",
            "mismatch_count": bam.check_wang_connectivity(grid),
            "edges_checked": 2 * 12 * 11,
            "shared_edge_pixel_diff": pixel_edge_diffs(map_img, 64, 12, 12),
        }

    # ---- mixed elevation-band maps
    for g in (30, 64):
        tier = bam.elevation_tiers(g, g, np.random.default_rng(7))
        mixed, conn = bam.render_mixed_map(tier, 64, GEN_DIR)
        name = f"mixed_{g}x{g}_seed7.png"
        save_pair(mixed, name, True)
        report["connectivity"][name] = {
            "type": "mixed_wang_layers",
            "mismatch_count": sum(conn.values()),
            "edges_checked": "per boundary, 2*(g-1)*(g-1)",
            "per_boundary": conn,
            "shared_edge_pixel_diff": pixel_edge_diffs(mixed, 64, g, g),
        }

    # ---- labeled atlases (grass over dirt, 64px)
    g64 = load_tile("grass", 64)
    d64 = load_tile("dirt", 64)
    _, w_atlas = bam.build_wang16_tileset(g64, d64)
    bam.label_atlas(w_atlas, 4, 64, 64, os.path.join(QA_DIR, "atlas_wang16_labeled_x4.png"))
    b_tiles, b_atlas, m2i, _, b_meta = bam.build_blob47_tileset(g64, d64, return_debug=True)
    bam.label_atlas(b_atlas, 8, 64, 64, os.path.join(QA_DIR, "atlas_blob47_labeled_x4.png"))
    report["meta"]["blob47_r_out"] = b_meta["params"]["r_out"]

    # ---- seeded sanity maps + connectivity validation
    def sanity(kind, mode, g, seed, tile_pair=("grass", "dirt"), size=64, with_x4=False):
        o_im = load_tile(tile_pair[0], size)
        b_im = load_tile(tile_pair[1], size)
        rng = np.random.default_rng(seed)
        grid = (bam.generate_sample_island_map(g, g, rng) if mode == "island"
                else bam.generate_noise_grid(g, g, rng))
        if kind == "wang16":
            w_tiles, _ = bam.build_wang16_tileset(o_im, b_im)
            map_img = bam.render_wang_map(grid, w_tiles, size)
            mism = bam.check_wang_connectivity(grid)
            edges = 2 * (g - 1) * (g - 2)
            rw, rh = g - 1, g - 1
        else:
            b_tiles, _, m2i, _, meta = bam.build_blob47_tileset(o_im, b_im, return_debug=True)
            map_img = bam.render_blob_map(grid, b_tiles, m2i, size)
            mism, edges = bam.check_blob_connectivity(meta, grid)
            rw, rh = g, g
        name = f"sanity_{kind}_{mode}_{g}x{g}_seed{seed}.png"
        save_pair(map_img, name, with_x4)
        report["connectivity"][name] = {
            "type": f"{kind}_{mode}",
            "mismatch_count": mism,
            "edges_checked": edges,
            "shared_edge_pixel_diff": pixel_edge_diffs(map_img, size, rw, rh),
        }

    for seed in range(1, 6):
        sanity("wang16", "island", 16, seed)
        sanity("blob47", "island", 16, seed)
    sanity("wang16", "island", 30, 3)
    sanity("blob47", "island", 30, 3)
    sanity("blob47", "noise", 64, 42, with_x4=True)

    out = os.path.join(REPORTS_DIR, "qa_terrain.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {out}")
    for m in report["tiles"]:
        print(m["file"], m["verdict_flags"], "seam", m["avg_row_seam"], m["avg_col_seam"])
    bad = {k: v["mismatch_count"] for k, v in report["connectivity"].items()
           if v["mismatch_count"]}
    print("connectivity mismatches:", bad if bad else "none")


if __name__ == "__main__":
    main()
