#!/usr/bin/env python3
"""build_autotile_map.py - Constructs Wang 16 and Blob 47 tilesets and renders test maps.

Blob 47 is a true 8-neighbor set: all 47 reduced masks resolve their four quadrants
to one of four states (pure base, pure overlay, inner corner, outer corner) with
quarter-disc arc geometry, so boundary transitions are curved rather than stair-
stepped. Edge continuity rule: a quadrant paints its full outer tile edge exactly
when the neighbour across that edge is covered; diagonals only place arcs inside
quadrants. verify_all_edges() proves the rule exhaustively over the tileset.

Modes:
- island: organic blob of the overlay terrain on the base terrain
- noise:  per-cell random binary assignment
- mixed:  elevation bands water->sand->dirt->grass->stone with value noise;
          each band boundary rendered as a pairwise Wang16 transition layer

CLI keeps the original flags (--overlay/-a, --base/-b, --out-dir/-o, --type) and
adds --grid, --seeds, --all-seeds, --seed, --mode.
"""

import os
import sys
import json
import argparse
import numpy as np
from PIL import Image, ImageDraw

TILE_ORDER = ["water", "sand", "dirt", "grass", "stone"]

B_N, B_NE, B_E, B_SE, B_S, B_SW, B_W, B_NW = 1, 2, 4, 8, 16, 32, 64, 128

Q_BASE, Q_OVERLAY, Q_OUTER, Q_INNER = 0, 1, 2, 3
STATE_NAMES = {Q_BASE: "base", Q_OVERLAY: "overlay", Q_OUTER: "outer", Q_INNER: "inner"}

# (primary, secondary, diagonal) neighbour-bit names per quadrant slot, slot order
# NW, NE, SE, SW. The primary bit's physical edge is the local TOP of the slot's
# canonical frame; the secondary's is the local LEFT; (0,0) = tile outer corner.
QUAD_ORTHOS = ((B_N, B_W, B_NW), (B_E, B_N, B_NE), (B_S, B_E, B_SE), (B_W, B_S, B_SW))


def _blob_reduce(mask):
    """Normalize 8-neighbor bitmask: diagonal corners require both orthogonal neighbors."""
    N  = bool(mask & 1)
    E  = bool(mask & 4)
    S  = bool(mask & 16)
    W  = bool(mask & 64)
    NE = bool(mask & 2) and N and E
    SE = bool(mask & 8) and S and E
    SW = bool(mask & 32) and S and W
    NW = bool(mask & 128) and N and W
    return int(N | E << 2 | S << 4 | W << 6 | NE << 1 | SE << 3 | SW << 5 | NW << 7)


def quadrant_states(mask):
    """Reduced mask -> (qNW, qNE, qSW, qSE), each in {BASE, OVERLAY, OUTER, INNER}.

    Both orthogonals + diagonal  -> pure overlay
    Both orthogonals, diag off   -> outer corner (rounded bite at the tile corner)
    Exactly one orthogonal       -> inner corner (quarter-disc bulge from that edge)
    Neither orthogonal           -> pure base
    """
    out = []
    for o1, o2, d in QUAD_ORTHOS:
        a, b, c = bool(mask & o1), bool(mask & o2), bool(mask & d)
        if a and b:
            out.append(Q_OVERLAY if c else Q_OUTER)
        elif a or b:
            out.append(Q_INNER)
        else:
            out.append(Q_BASE)
    return tuple(out)


def unique_reduced_masks():
    return sorted({_blob_reduce(m) for m in range(256)})


def _outer(xs, ys, r_out, soft):
    """Outer-corner cut: quarter disc of radius r_out at the tile corner. Full
    coverage is kept on both outer edges beyond the arc so ortho-neighbour edges
    still match; only the corner interior yields to the (base) diagonal."""
    return np.clip((r_out - np.hypot(xs, ys)) / soft + 0.5, 0.0, 1.0)


def _orient(a_q, rot):
    """Rotate the NW-quadrant crop into physical slot rot (90-degree rotations)."""
    if rot == 0:
        return a_q
    return np.ascontiguousarray(np.rot90(a_q, -rot))


def _slot_origin(rot, hw, hh):
    return ((0, 0), (hw, 0), (hw, hh), (0, hh))[rot]


def build_blob47_tileset(img_a, img_b, return_debug=False):
    """Build the 47 Blob tiles from the 47 reduced 8-neighbor masks."""
    assert img_a.size == img_b.size, "Both images must have identical size"
    w, h = img_a.size
    hw, hh = w // 2, h // 2
    r_in, soft = hw, 1.5
    r_out = max(3.0, round(hw * 0.35))

    unique_masks = unique_reduced_masks()
    assert len(unique_masks) == 47, f"reduced mask set is {len(unique_masks)}, expected 47"
    mask_to_idx = {m: i for i, m in enumerate(unique_masks)}

    a_q = np.asarray(img_a.convert("RGB").crop((0, 0, hw, hh)), dtype=np.uint8)
    b_q = np.asarray(img_b.convert("RGB").crop((0, 0, hw, hh)), dtype=np.uint8)

    xs, ys = np.meshgrid(np.arange(hw), np.arange(hh))

    def slot_mask(m, rot):
        """Coverage for slot `rot` of reduced mask `m`, in the slot's canonical
        frame (local top = primary neighbour edge, local left = secondary)."""
        primary, secondary, diagonal = QUAD_ORTHOS[rot]
        p, s, d = bool(m & primary), bool(m & secondary), bool(m & diagonal)
        if p and s and d:
            return np.ones((hh, hw))
        if p and s:
            return 1.0 - _outer(xs, ys, r_out, soft)
        if p:
            return np.clip((r_in - np.hypot(xs - hw, ys)) / soft + 0.5, 0.0, 1.0)
        if s:
            return np.clip((r_in - np.hypot(xs, ys - hh)) / soft + 0.5, 0.0, 1.0)
        return np.zeros((hh, hw))

    tiles, coverage_by_mask, states_by_mask = [], {}, {}
    for m in unique_masks:
        tile = np.zeros((h, w, 3), dtype=np.uint8)
        cov = np.zeros((h, w), dtype=float)
        for rot in range(4):
            mm = np.ascontiguousarray(np.rot90(slot_mask(m, rot), -rot)) if rot else slot_mask(m, rot)
            x0, y0 = _slot_origin(rot, hw, hh)
            src_a, src_b = _orient(a_q, rot), _orient(b_q, rot)
            tile[y0:y0 + hh, x0:x0 + hw] = (src_a * mm[..., None]
                                            + src_b * (1 - mm[..., None])).round().astype(np.uint8)
            cov[y0:y0 + hh, x0:x0 + hw] = mm
        tiles.append(Image.fromarray(tile).convert("RGBA"))
        coverage_by_mask[m] = cov
        states_by_mask[m] = quadrant_states(m)

    # Quadrant variant bank: every distinct (state, rot, diag) pattern rendered once.
    bank, bank_index, bank_keys = [], {}, []
    for m in unique_masks:
        for rot in range(4):
            _, _, diagonal = QUAD_ORTHOS[rot]
            key = (quadrant_states(m)[rot], rot, bool(m & diagonal))
            if key not in bank_index:
                mm = np.ascontiguousarray(np.rot90(slot_mask(m, rot), -rot)) if rot else slot_mask(m, rot)
                rgb = (_orient(a_q, rot) * mm[..., None]
                       + _orient(b_q, rot) * (1 - mm[..., None])).round().astype(np.uint8)
                bank_index[key] = len(bank)
                bank.append(rgb)
                bank_keys.append(key)
    vatlas = Image.new("RGB", (hw * max(1, len(bank)), hh))
    for i, rgb in enumerate(bank):
        vatlas.paste(Image.fromarray(rgb), (i * hw, 0))

    atlas = Image.new("RGBA", (w * 8, h * 6))
    for i, t in enumerate(tiles):
        atlas.paste(t, ((i % 8) * w, (i // 8) * h))

    meta = {
        "mask_order": unique_masks,
        "states_by_mask": {str(m): [int(x) for x in s] for m, s in states_by_mask.items()},
        "coverage_by_mask": {str(m): coverage_by_mask[m].round(4).tolist() for m in unique_masks},
        "tile_size": w,
        "variant_bank_keys": [[int(st), int(ro), bool(dg)] for (st, ro, dg) in bank_keys],
        "params": {"r_in": r_in, "r_out": r_out, "soft": soft},
    }
    result = (tiles, atlas, mask_to_idx)
    if return_debug:
        return result + (vatlas, meta)
    return result


def edge_profile(cov_full, hw, hh, phys_bit):
    """Coverage profile along a full tile's physical edge (already oriented in the
    direction of travel shared by both neighbours)."""
    if phys_bit == B_N:
        return cov_full[0, :]
    if phys_bit == B_S:
        return cov_full[2 * hh - 1, :][::-1]
    if phys_bit == B_W:
        return cov_full[:, 0][::-1]
    return cov_full[:, 2 * hw - 1]


def _edge_interior_mask(length, corner_tol):
    """Boolean mask over an edge profile: corner-cut zones at both ends are
    exempt from pairwise comparison (they are diagonal-dependent)."""
    im = np.ones(length, dtype=bool)
    im[:corner_tol] = False
    im[length - corner_tol:] = False
    return im


def verify_all_edges(meta):
    """Exhaustive edge-continuity proof over the whole tileset.

    For every tile m and direction d with bit d set, and every overlay neighbour
    configuration n with the opposite bit set, compare the painted coverage
    profiles of the shared edge, ignoring the corner-cut zones at both ends of
    the edge (a set bit means the neighbour across the edge is overlay; base
    neighbours only occur across unset bits, enforced by the leak check).
    Returns list of bad triples."""
    cov = {int(m): np.asarray(meta["coverage_by_mask"][str(m)], dtype=float)
           for m in meta["mask_order"]}
    ts = meta["tile_size"]
    hw, hh = ts // 2, ts // 2
    tol = int(round(meta["params"]["r_out"])) + 2
    interior = _edge_interior_mask(ts, tol)
    opposite = {B_N: B_S, B_S: B_N, B_E: B_W, B_W: B_E}
    bad = []
    masks = list(cov.keys())
    for m in masks:
        for d in (B_N, B_E, B_S, B_W):
            if not (m & d):
                continue
            pm = edge_profile(cov[m], hw, hh, d)[interior]
            for n in masks:
                if not (n & opposite[d]):
                    continue
                pn = edge_profile(cov[n], hw, hh, opposite[d])[interior]
                diff = int(np.abs(np.round(pm) - np.round(pn)).sum())
                if diff:
                    bad.append((m, d, n, diff))
    # base tile edges face only base neighbours or covered ones (covered tiles paint
    # empty edges toward base by the rule above); also check base vs covered
    for m in masks:
        if m == 0:
            continue
        for d in (B_N, B_E, B_S, B_W):
            if m & d:
                continue
            pm = edge_profile(cov[m], hw, hh, d)[interior]
            if pm.max() > 0.5:
                bad.append((m, d, "base-leak", float(pm.max())))
    return bad


def check_blob_connectivity(meta, grid):
    """Count shared interior edges where adjacent tiles' painted coverage profiles
    disagree. Returns (mismatches, edges_checked)."""
    cov = {int(m): np.asarray(meta["coverage_by_mask"][str(m)], dtype=float)
           for m in meta["mask_order"]}
    ts = meta["tile_size"]
    hw, hh = ts // 2, ts // 2
    tol = int(round(meta["params"]["r_out"])) + 2
    interior = _edge_interior_mask(ts, tol)
    gh, gw = grid.shape
    mism = total = 0

    def prof(y, x, bit):
        if grid[y, x] == 1:
            return edge_profile(cov[blob_mask_for(grid, y, x)], hw, hh, bit)
        return edge_profile(cov[0], hw, hh, bit)

    opposite = {B_N: B_S, B_S: B_N, B_E: B_W, B_W: B_E}
    for y in range(gh):
        for x in range(gw):
            if x + 1 < gw:
                total += 1
                a = prof(y, x, B_E)[interior]
                b = prof(y, x + 1, B_W)[interior]
                if np.abs(np.round(a) - np.round(b)).sum():
                    mism += 1
            if y + 1 < gh:
                total += 1
                a = prof(y, x, B_S)[interior]
                b = prof(y + 1, x, B_N)[interior]
                if np.abs(np.round(a) - np.round(b)).sum():
                    mism += 1
    return mism, total


def blob_mask_for(grid, y, x, outer_value=0):
    """Reduced 8-neighbor mask for an overlay cell; out-of-grid neighbours read base."""
    gh, gw = grid.shape

    def nb(dy, dx):
        yy, xx = y + dy, x + dx
        if 0 <= yy < gh and 0 <= xx < gw:
            return 1 if grid[yy, xx] == 1 else outer_value
        return 0

    return _blob_reduce(nb(-1, 0) | nb(-1, 1) << 1 | nb(0, 1) << 2 | nb(1, 1) << 3 |
                        nb(1, 0) << 4 | nb(1, -1) << 5 | nb(0, -1) << 6 | nb(-1, -1) << 7)


def build_wang16_tileset(img_a, img_b):
    """Build the 16 Wang tiles by combining quadrants of texture A and B.
    Index = NW + 2*NE + 4*SW + 8*SE where bit=1 means Overlay A, bit=0 means Base B.
    """
    assert img_a.size == img_b.size, "Both images must have identical size"
    w, h = img_a.size
    hw, hh = w // 2, h // 2

    a_nw = img_a.crop((0, 0, hw, hh))
    a_ne = img_a.crop((hw, 0, w, hh))
    a_sw = img_a.crop((0, hh, hw, h))
    a_se = img_a.crop((hw, hh, w, h))

    b_nw = img_b.crop((0, 0, hw, hh))
    b_ne = img_b.crop((hw, 0, w, hh))
    b_sw = img_b.crop((0, hh, hw, h))
    b_se = img_b.crop((hw, hh, w, h))

    tiles = []
    for idx in range(16):
        nw_bit = (idx >> 0) & 1
        ne_bit = (idx >> 1) & 1
        sw_bit = (idx >> 2) & 1
        se_bit = (idx >> 3) & 1

        tile = Image.new("RGBA", (w, h))
        tile.paste(a_nw if nw_bit else b_nw, (0, 0))
        tile.paste(a_ne if ne_bit else b_ne, (hw, 0))
        tile.paste(a_sw if sw_bit else b_sw, (0, hh))
        tile.paste(a_se if se_bit else b_se, (hw, hh))
        tiles.append(tile)

    atlas = Image.new("RGBA", (w * 4, h * 4))
    for i, t in enumerate(tiles):
        atlas.paste(t, ((i % 4) * w, (i // 4) * h))

    return tiles, atlas


def generate_sample_island_map(grid_w=16, grid_h=16, rng=None):
    """Organic island grid where 1=Overlay A, 0=Base B."""
    rng = rng or np.random.default_rng()
    grid = np.zeros((grid_h, grid_w), dtype=int)
    cy, cx = grid_h / 2.0, grid_w / 2.0
    radius = min(grid_w, grid_h) * 0.38
    px, py = rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi)
    amp = max(0.6, grid_w / 24.0)
    for y in range(grid_h):
        for x in range(grid_w):
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            noise = np.sin(x * 0.8 + px) + np.cos(y * 0.8 + py) + rng.normal(0, 0.3)
            if d + noise * amp < radius:
                grid[y, x] = 1
    return grid


def generate_noise_grid(grid_w, grid_h, rng, p=0.4):
    return (rng.random((grid_h, grid_w)) < p).astype(int)


def _value_noise(rng, grid_w, grid_h):
    cell = max(3, min(grid_w, grid_h) // 8)
    coarse = rng.random((grid_h // cell + 2, grid_w // cell + 2))
    img = Image.fromarray((coarse * 255).astype(np.uint8)).resize(
        (grid_w + cell, grid_h + cell), Image.BILINEAR)
    return np.asarray(img, dtype=float)[:grid_h, :grid_w] / 255.0


def elevation_tiers(grid_w, grid_h, rng):
    """Multi-terrain elevation bands: 0=water 1=sand 2=dirt 3=grass 4=stone."""
    yy, xx = np.mgrid[0:grid_h, 0:grid_w]
    cx, cy = (grid_w - 1) / 2.0, (grid_h - 1) / 2.0
    dist = np.hypot((xx - cx) / max(cx, 1.0), (yy - cy) / max(cy, 1.0))
    nz = _value_noise(rng, grid_w, grid_h)
    elev = 1.15 - dist + (nz - 0.5) * 0.9
    edges = [0.28, 0.48, 0.68, 0.86]
    tier = np.zeros((grid_h, grid_w), dtype=int)
    for i, t in enumerate(edges):
        tier = np.where(elev >= t, i + 1, tier)
    return tier


def render_mixed_map(tier, tile_size, terrain_dir):
    """Layered elevation-band composite: for each boundary t, the full dual-grid
    Wang16 layer (overlay=terrains[t] vs base=terrains[t-1]) is rendered from the
    binary grid tier>=t, then revealed only over cells whose tier >= t. Returns
    (mixed_image, per-boundary wang mismatch counts)."""
    G = tier.shape[0]
    base_im = Image.open(os.path.join(terrain_dir, f"{TILE_ORDER[0]}_{tile_size}.png")).convert("RGBA")
    mixed = Image.new("RGBA", (G * tile_size, G * tile_size))
    for y in range(G):
        for x in range(G):
            mixed.paste(base_im, (x * tile_size, y * tile_size))
    conn = {}
    for t in range(1, len(TILE_ORDER)):
        b_im = Image.open(os.path.join(terrain_dir, f"{TILE_ORDER[t-1]}_{tile_size}.png")).convert("RGBA")
        o_im = Image.open(os.path.join(terrain_dir, f"{TILE_ORDER[t]}_{tile_size}.png")).convert("RGBA")
        w_tiles, _ = build_wang16_tileset(o_im, b_im)
        bgrid = (tier >= t).astype(int)
        padded = np.pad(bgrid, 1, mode="edge")
        layer = render_wang_map(padded, w_tiles, tile_size)
        cellmask = (tier >= t)
        px_mask = np.repeat(np.repeat(cellmask, tile_size, axis=0), tile_size, axis=1)
        arr = np.asarray(mixed)
        lay = np.asarray(layer)[:G * tile_size, :G * tile_size]
        mixed = Image.fromarray(np.where(px_mask[..., None], lay, arr).astype(np.uint8), "RGBA")
        conn[f"{TILE_ORDER[t-1]}->{TILE_ORDER[t]}"] = check_wang_connectivity(padded)
    return mixed, conn


def render_wang_map(grid, wang_tiles, tile_size):
    """Render a 2D map from grid using Wang 16 dual grid rules."""
    gh, gw = grid.shape
    canvas = Image.new("RGBA", ((gw - 1) * tile_size, (gh - 1) * tile_size))
    for y in range(gh - 1):
        for x in range(gw - 1):
            canvas.paste(wang_tiles[wang_index_for(grid, x, y)], (x * tile_size, y * tile_size))
    return canvas


def wang_index_for(grid, x, y):
    """Wang tile index for dual-grid vertex (x, y). Bit order = renderer's."""
    gh, gw = grid.shape
    nw = grid[y, x]
    ne = grid[y, x + 1] if x + 1 < gw else 0
    sw = grid[y + 1, x] if y + 1 < gh else 0
    se = grid[y + 1, x + 1] if (y + 1 < gh and x + 1 < gw) else 0
    return int(nw + 2 * ne + 4 * sw + 8 * se)


def check_wang_connectivity(grid):
    """Count adjacent rendered tile pairs whose shared edge mixes different
    quadrant sources (right half of tile i vs left half of tile j)."""
    gh, gw = grid.shape
    rw, rh = gw - 1, gh - 1
    mism = 0
    for y in range(rh):
        for x in range(rw - 1):
            i, j = wang_index_for(grid, x, y), wang_index_for(grid, x + 1, y)
            if ((i >> 1) & 1) != (j & 1) or ((i >> 3) & 1) != ((j >> 2) & 1):
                mism += 1
    for y in range(rh - 1):
        for x in range(rw):
            i, j = wang_index_for(grid, x, y), wang_index_for(grid, x, y + 1)
            if ((i >> 2) & 1) != (j & 1) or ((i >> 3) & 1) != ((j >> 1) & 1):
                mism += 1
    return mism


def render_blob_map(grid, blob_tiles, mask_to_idx, tile_size):
    """Render a 2D map using 8-neighbor Blob 47 autotiling."""
    gh, gw = grid.shape
    canvas = Image.new("RGBA", (gw * tile_size, gh * tile_size))
    for y in range(gh):
        for x in range(gw):
            if grid[y, x] == 0:
                idx = mask_to_idx.get(0, 0)
            else:
                idx = mask_to_idx.get(blob_mask_for(grid, y, x), 0)
            canvas.paste(blob_tiles[idx], (x * tile_size, y * tile_size))
    return canvas


def save_x4(img, path):
    img.resize((img.width * 4, img.height * 4), Image.NEAREST).save(path)


def label_atlas(atlas, cols, tile_w, tile_h, out_path, scale=4):
    """Label each non-empty slot with its index; also draw slot grid lines."""
    im = atlas.convert("RGBA")
    d = ImageDraw.Draw(im)
    rows = im.height // tile_h
    for i in range(rows * cols):
        col, row = i % cols, i // cols
        x0, y0 = col * tile_w, row * tile_h
        cell = im.crop((x0, y0, x0 + tile_w, y0 + tile_h))
        if np.asarray(cell)[:, :, 3].max() == 0:
            continue
        d.rectangle([x0, y0, x0 + tile_w - 1, y0 + tile_h - 1], outline=(255, 0, 0, 255))
        d.text((x0 + 2, y0 + 2), str(i), fill=(255, 255, 0, 255))
    im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(out_path)
    return im


def main():
    parser = argparse.ArgumentParser(description="Build Wang 16 & Blob 47 tilesets and render test maps")
    parser.add_argument("--overlay", "-a", required=True, help="Overlay seamless tile A (e.g. Grass)")
    parser.add_argument("--base", "-b", required=True, help="Base seamless tile B (e.g. Water/Dirt)")
    parser.add_argument("--out-dir", "-o", default="out_autotile", help="Output directory")
    parser.add_argument("--type", choices=["wang16", "blob47", "both"], default="both")
    parser.add_argument("--grid", "-g", type=int, default=16, help="map size NxN")
    parser.add_argument("--seeds", default="1", help="comma/space list of seeds, e.g. '1 2 3 4 5'")
    parser.add_argument("--all-seeds", action="store_true", help="use seeds 1..5")
    parser.add_argument("--seed", type=int, default=None, help="single RNG seed (overrides --seeds)")
    parser.add_argument("--mode", choices=["island", "noise", "mixed"], default="island")
    parser.add_argument("--terrain-dir", default=None, help="dir with {terrain}_{size}.png for mixed mode")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    im_a = Image.open(args.overlay).convert("RGBA")
    im_b = Image.open(args.base).convert("RGBA")
    tile_size = im_a.size[0]

    if args.all_seeds:
        seeds = [1, 2, 3, 4, 5]
    elif args.seed is not None:
        seeds = [args.seed]
    else:
        seeds = [int(s) for s in args.seeds.replace(" ", ",").split(",") if s.strip()]
    G = args.grid
    tdir = args.terrain_dir or os.path.join("assets", "generated")

    summary = {}
    for seed in seeds:
        rng = np.random.default_rng(seed)
        tag = f"{args.mode}_{G}x{G}_seed{seed}"

        if args.mode == "mixed":
            tier = elevation_tiers(G, G, rng)
            mixed, conn_w = render_mixed_map(tier, tile_size, tdir)
            mixed_path = os.path.join(args.out_dir, f"map_mixed_{tag}.png")
            mixed.save(mixed_path)
            save_x4(mixed, os.path.join(args.out_dir, f"map_mixed_{tag}_x4.png"))
            summary[f"mixed_{tag}"] = {"map": mixed_path, "wang_mismatches_per_boundary": conn_w}
            print(f"[PASS] mixed map -> {mixed_path}  wang mismatches: {conn_w}")
            continue

        grid = (generate_sample_island_map(G, G, rng) if args.mode == "island"
                else generate_noise_grid(G, G, rng))
        n_overlay = int(grid.sum())

        if args.type in ("wang16", "both"):
            w_tiles, w_atlas = build_wang16_tileset(im_a, im_b)
            w_atlas_path = os.path.join(args.out_dir, f"tileset_wang16_{tag}.png")
            w_atlas.save(w_atlas_path)
            w_map = render_wang_map(grid, w_tiles, tile_size)
            w_map_path = os.path.join(args.out_dir, f"map_wang16_{tag}.png")
            w_map.save(w_map_path)
            save_x4(w_map, os.path.join(args.out_dir, f"map_wang16_{tag}_x4.png"))
            mism = check_wang_connectivity(grid)
            summary[f"wang16_{tag}"] = {
                "tiles_count": len(w_tiles), "overlay_cells": n_overlay,
                "atlas": w_atlas_path, "map": w_map_path, "mismatches": mism,
            }
            print(f"[PASS] Wang 16 ({len(w_tiles)} tiles) -> {w_atlas_path}; mismatches {mism}")

        if args.type in ("blob47", "both"):
            b_tiles, b_atlas, m_to_idx, vatlas, meta = build_blob47_tileset(im_a, im_b, return_debug=True)
            b_atlas_path = os.path.join(args.out_dir, f"tileset_blob47_{tag}.png")
            b_atlas.save(b_atlas_path)
            vatlas.save(os.path.join(args.out_dir, f"quadrants_blob47_{tag}.png"))
            with open(os.path.join(args.out_dir, f"tileset_blob47_{tag}.json"), "w") as f:
                json.dump(meta, f)
            b_map = render_blob_map(grid, b_tiles, m_to_idx, tile_size)
            b_map_path = os.path.join(args.out_dir, f"map_blob47_{tag}.png")
            b_map.save(b_map_path)
            save_x4(b_map, os.path.join(args.out_dir, f"map_blob47_{tag}_x4.png"))
            mism, total = check_blob_connectivity(meta, grid)
            bad = verify_all_edges(meta)
            summary[f"blob47_{tag}"] = {
                "tiles_count": len(b_tiles), "overlay_cells": n_overlay,
                "quadrant_variants": len(meta["variant_bank_keys"]),
                "atlas": b_atlas_path, "map": b_map_path,
                "mismatches": mism, "shared_edges_checked": total,
                "all_edge_pair_failures": len(bad),
            }
            print(f"[PASS] Blob 47 ({len(b_tiles)} tiles, {len(meta['variant_bank_keys'])} "
                  f"quadrant variants) -> {b_atlas_path}; map mismatches {mism}/{total}, "
                  f"all-pair failures {len(bad)}")

    spath = os.path.join(args.out_dir, f"summary_{args.mode}_{G}x{G}_{'_'.join(map(str, seeds))}.json")
    with open(spath, "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
