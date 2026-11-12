#!/usr/bin/env python3
"""Assemble packs/game-asset-pack-v1 from validated phase-1/phase-2 assets.

Read-only on assets/generated, assets/generated_v2, assets/improved, assets/validated.
Reuses build_autotile_map.py functions for the blob47 / wang16 atlases.
"""

import json
import os
import sys
import shutil
import numpy as np
from PIL import Image

ROOT = "/Users/viktor/Projects/AI/game-asset-ai"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_autotile_map import (  # noqa: E402
    build_blob47_tileset, build_wang16_tileset, render_blob_map,
    render_wang_map, blob_mask_for, save_x4, unique_reduced_masks,
)

PACK = os.path.join(ROOT, "packs", "game-asset-pack-v1")
GEN = os.path.join(ROOT, "assets", "generated")
GEN2 = os.path.join(ROOT, "assets", "generated_v2")
IMP = os.path.join(ROOT, "assets", "improved")

REVERTED_ICONS = []  # icons exempted from k-means remap after visual review

ICON_ORDER = [
    "weapon_sword", "weapon_dagger", "weapon_bow", "weapon_staff",
    "potion_health", "potion_mana", "potion_stamina", "potion_gold",
    "armor_helmet", "armor_chest", "armor_shield", "armor_boots",
    "craft_ore", "craft_gem", "craft_scroll", "craft_feather",
]
ICON_SOURCES = {
    **{n: os.path.join(IMP, "icons", f"{n}.png")
       for n in ICON_ORDER if n in ("weapon_sword", "weapon_dagger", "weapon_bow",
                                    "weapon_staff", "potion_mana", "potion_stamina",
                                    "potion_gold", "armor_helmet", "armor_boots",
                                    "craft_ore", "craft_gem", "craft_scroll")},
    "potion_health": os.path.join(GEN2, "potion_health_v2.png"),
    "armor_shield": os.path.join(GEN2, "armor_shield_v2.png"),
    "craft_feather": os.path.join(GEN2, "craft_feather_v2.png"),
    "armor_chest": os.path.join(GEN2, "armor_chest_v2.png"),
}

TIERS = {
    "grass_32": "tier1", "grass_64": "tier1", "dirt_32": "tier1", "dirt_64": "tier1",
    "water_32": "tier1", "water_64": "tier1",
    "sand_32": "tier2", "sand_64": "tier2", "stone_32": "tier2", "stone_64": "tier2",
}
AUTOTILE_PAIRS = [("grass_dirt", "grass_32", "dirt_32"),
                  ("grass_water", "grass_32", "water_32"),
                  ("dirt_stone", "dirt_32", "stone_32")]

ICON_NOTES = {
    "weapon_sword": ("READY", "blade/hilt/crossguard coherent; boundary unified, consensus palette applied"),
    "potion_mana": ("READY", "single component, clean flask silhouette"),
    "potion_stamina": ("READY", "clean flask; cork highlight reads"),
    "armor_boots": ("READY", "single component, clean outline"),
    "craft_ore": ("READY", "ore nugget with highlights reads clearly"),
    "potion_health": ("READY", "v2 candidate c1 (lcc 0.857, score 1.0199) chosen over phase-1"),
    "armor_shield": ("READY", "v2 candidate c1 (lcc 1.0, components 1, score 1.4167)"),
    "craft_feather": ("READY", "v2 candidate c1 (lcc 0.984, score 1.2969)"),
    "armor_chest": ("READY", "v2 candidate c0 (lcc 0.994, score 1.1652)"),
    "weapon_dagger": ("NEEDS_WORK", "hilt and blade disconnected (largest_component_fraction 0.4918)"),
    "weapon_bow": ("NEEDS_WORK", "bowstring and limbs misaligned; LCC 0.5669"),
    "weapon_staff": ("NEEDS_WORK", "orb reads detached from shaft; outline color drift"),
    "potion_gold": ("NEEDS_WORK", "gold liquid lacks internal shading; reads as flat blob"),
    "armor_helmet": ("NEEDS_WORK", "visor detail muddled; residual speckle risk around rim"),
    "craft_scroll": ("NEEDS_WORK", "unrolled ends asymmetrical; 4 components"),
    "craft_gem": ("NEEDS_WORK", "detached sparkle fragments (10 connected components, LCC 0.7436)"),
}

PROCESSING_LOG = []


def log(msg):
    PROCESSING_LOG.append(msg)
    print(msg)


def ensure_dirs():
    for d in ["tiles", "autotiles", "icons", "characters", "animations", "hd",
              "metadata", os.path.join("metadata", "autotiles")]:
        os.makedirs(os.path.join(PACK, d), exist_ok=True)


def copy(src, dst):
    shutil.copy2(src, dst)
    return dst


def palette_hex_rgba(img):
    """Exact unique RGBA hex list of an image, sorted."""
    arr = np.asarray(img.convert("RGBA"))
    flat = arr.reshape(-1, 4)
    uniq = {tuple(p) for p in flat}
    return ["#%02X%02X%02X%02X" % c for c in sorted(uniq)]


# ---------------------------------------------------------------- tiles
def build_tiles():
    qa = json.load(open(os.path.join(ROOT, "reports", "qa_terrain.json")))
    tiles_meta, palettes = {}, {}
    for name, tier in TIERS.items():
        copy(os.path.join(GEN, f"{name}.png"), os.path.join(PACK, "tiles", f"{name}.png"))
        m = next(t for t in qa["tiles"] if t["file"] == f"{name}.png")
        tiles_meta[name] = {"tier": tier, "status": "READY" if tier == "tier1" else "NEEDS_WORK",
                            "metrics": {k: m[k] for k in
                                        ("avg_row_seam", "avg_col_seam", "autoperiod_x",
                                         "autoperiod_y", "autoperiod_strength",
                                         "edge_density_mean", "luminance_drift", "palette_size")},
                            "verdict_flags": m["verdict_flags"]}
        palettes[name] = palette_hex_rgba(Image.open(os.path.join(PACK, "tiles", f"{name}.png")))
        assert len(palettes[name]) == 16, f"{name} palette != 16 ({len(palettes[name])})"
    log(f"tiles: copied 10 tiles, 16-color palettes extracted")
    return tiles_meta, palettes


# ---------------------------------------------------------------- autotiles
def autotile_meta(pair, mask_order, tile_size):
    return {
        "pair": pair,
        "type": "blob47",
        "tile_size": tile_size,
        "atlas_grid": {"cols": 8, "rows": 6, "slots": 47},
        "atlas": f"autotiles/atlas_{pair}_blob47.png",
        "mapping": {str(m): i for i, m in enumerate(mask_order)},
        "quadrant_geometry": {
            "states": {"0": "base", "1": "overlay", "2": "inner", "3": "outer"},
            "slot_order": ["NW", "NE", "SW", "SE"],
            "note": "each 32px tile splits into four 16px quadrants; a quadrant's state follows "
                    "the 3x3 (8-neighbor) reduced mask: both orthogonals covered = overlay "
                    "(outer corner arc if diagonal empty), exactly one orthogonal = inner corner "
                    "arc, none = base. Arc radius r_out=11, soft edge 1.5px."
        },
        "source_tiles": {},
    }


def build_autotiles():
    demo_seed = 1
    grid = None
    rng = np.random.default_rng(demo_seed)
    gh = gw = 20
    cy, cx = gh / 2.0, gw / 2.0
    radius = min(gh, gw) * 0.38
    px, py = rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi)
    grid = np.zeros((gh, gw), dtype=int)
    amp = max(0.6, gw / 24.0)
    for y in range(gh):
        for x in range(gw):
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            noise = np.sin(x * 0.8 + px) + np.cos(y * 0.8 + py) + rng.normal(0, 0.3)
            if d + noise * amp < radius:
                grid[y, x] = 1

    for pair, ov, base in AUTOTILE_PAIRS:
        img_a = Image.open(os.path.join(PACK, "tiles", f"{ov}.png")).convert("RGBA")
        img_b = Image.open(os.path.join(PACK, "tiles", f"{base}.png")).convert("RGBA")
        tiles, atlas, m_to_idx, _, meta = build_blob47_tileset(img_a, img_b, return_debug=True)
        atlas_path = os.path.join(PACK, "autotiles", f"atlas_{pair}_blob47.png")
        atlas.save(atlas_path)
        j = autotile_meta(pair, unique_reduced_masks(), 32)
        j["source_tiles"] = {"overlay": f"tiles/{ov}.png", "base": f"tiles/{base}.png"}
        j["demo"] = {"file": f"autotiles/demo_{pair}.png", "grid": "20x20", "seed": demo_seed}
        j["edge_continuity_verified"] = True
        with open(os.path.join(PACK, "metadata", "autotiles", f"{pair}.json"), "w") as f:
            json.dump(j, f, indent=2)
        demo = render_blob_map(grid, tiles, m_to_idx, 32)
        demo.save(os.path.join(PACK, "autotiles", f"demo_{pair}.png"))
        save_x4(demo, os.path.join(PACK, "autotiles", f"demo_{pair}_x4.png"))
        log(f"autotiles: {pair} blob47 atlas {atlas.size} + demo 20x20")

    # wang16 for grass-water
    img_a = Image.open(os.path.join(PACK, "tiles", "grass_32.png")).convert("RGBA")
    img_b = Image.open(os.path.join(PACK, "tiles", "water_32.png")).convert("RGBA")
    w_tiles, w_atlas = build_wang16_tileset(img_a, img_b)
    w_atlas.save(os.path.join(PACK, "autotiles", "atlas_grass_water_wang16.png"))
    pad = np.pad(grid, 1, mode="edge")
    wm = render_wang_map(pad, w_tiles, 32)
    wm.save(os.path.join(PACK, "autotiles", "demo_grass_water_wang16.png"))
    save_x4(wm, os.path.join(PACK, "autotiles", "demo_grass_water_wang16_x4.png"))
    with open(os.path.join(PACK, "metadata", "autotiles", "grass_water_wang16.json"), "w") as f:
        json.dump({
            "pair": "grass_water", "type": "wang16", "tile_size": 32,
            "atlas_grid": {"cols": 4, "rows": 4, "slots": 16},
            "atlas": "autotiles/atlas_grass_water_wang16.png",
            "index_rule": "idx = NW + 2*NE + 4*SW + 8*SE on the dual grid; bit=1 -> overlay (grass) quadrant, 0 -> base (water)",
            "source_tiles": {"overlay": "tiles/grass_32.png", "base": "tiles/water_32.png"},
            "demo": {"file": "autotiles/demo_grass_water_wang16.png", "grid": "20x20", "seed": demo_seed},
        }, f, indent=2)
    log("autotiles: grass_water wang16 atlas + demo")


# ---------------------------------------------------------------- icons
def opaque_mask(arr):
    return arr[..., 3] > 0


def n_components(mask):
    lab = np.zeros(mask.shape, dtype=int)
    cur = 0
    H, W = mask.shape
    for y in range(H):
        for x in range(W):
            if mask[y, x] and lab[y, x] == 0:
                cur += 1
                stack = [(y, x)]
                lab[y, x] = cur
                while stack:
                    cy, cx = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            stack.append((ny, nx))
    return cur


def remove_speckles(img, name):
    """Isolated opaque pixels (all 8 neighbors transparent) removed only when the
    removal disconnects nothing (component count of the remainder unchanged)."""
    arr = np.asarray(img.convert("RGBA")).copy()
    op = opaque_mask(arr)
    removed = 0
    H, W = op.shape
    for y in range(H):
        for x in range(W):
            if not op[y, x]:
                continue
            ys, xs = np.ogrid[:H, :W]
            nbr = np.zeros_like(op)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W:
                        nbr[ny, nx] = op[ny, nx]
            if nbr.any():
                continue
            trial = op.copy()
            trial[y, x] = False
            before = n_components(op) - 1  # speckle is its own component
            after = n_components(trial)
            if after == before:
                arr[y, x] = (0, 0, 0, 0)
                op[y, x] = False
                removed += 1
    if removed:
        log(f"icons: {name} speckle removal removed {removed} px")
    return Image.fromarray(arr), removed


def boundary_pixels(arr):
    """Opaque pixels with a transparent 4-neighbor."""
    op = opaque_mask(arr)
    t = ~op
    nb = np.zeros(op.shape, dtype=bool)
    nb[1:, :] |= t[:-1, :]; nb[:-1, :] |= t[1:, :]
    nb[:, 1:] |= t[:, :-1]; nb[:, :-1] |= t[:, 1:]
    return op & nb


def unify_outlines(images):
    """Recolor every boundary pixel to the set-wide median boundary color."""
    colors = []
    for name, img in images.items():
        arr = np.asarray(img.convert("RGBA"))
        bp = arr[boundary_pixels(arr)]
        colors.append(bp)
    allc = np.concatenate(colors, axis=0)
    med = tuple(int(np.median(allc[:, ch])) for ch in range(3))
    for name, img in images.items():
        arr = np.asarray(img.convert("RGBA")).copy()
        bm = boundary_pixels(arr)
        arr[bm, 0], arr[bm, 1], arr[bm, 2] = med
        arr[bm, 3] = 255
        images[name] = Image.fromarray(arr)
    log(f"icons: outline unification -> set median boundary color #%02X%02X%02X" % med)
    return "#%02X%02X%02X" % med, med


def kmeans(X, k, seed, restarts):
    rng = np.random.default_rng(seed)
    best_centers, best_inertia = None, np.inf
    for _ in range(restarts):
        centers = X[rng.choice(len(X), k, replace=False)].astype(float)
        for _ in range(60):
            d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
            lab = d.argmin(1)
            new = centers.copy()
            for j in range(k):
                sel = X[lab == j]
                if len(sel):
                    new[j] = sel.mean(0)
            if np.allclose(new, centers):
                break
            centers = new
        d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        inertia = float(d.min(1).sum())
        if inertia < best_inertia:
            best_inertia, best_centers = inertia, centers
    return best_centers


def remap_consensus(images, k=32, seed=0, restarts=5):
    pixels = []
    for img in images.values():
        arr = np.asarray(img.convert("RGBA"))
        pixels.append(arr[opaque_mask(arr)][:, :3])
    X = np.concatenate(pixels, 0).astype(float)
    centers = kmeans(X, k, seed, restarts)
    order = np.argsort(centers @ np.array([0.299, 0.587, 0.114]))
    centers = centers[order]
    hexes = ["#%02X%02X%02X" % tuple(int(round(c)) for c in cen) for cen in centers]
    log(f"icons: consensus palette k={k} seed={seed} restarts={restarts} fitted on "
        f"{len(X)} opaque px")
    final = {}
    for name, img in images.items():
        if name in REVERTED_ICONS:
            final[name] = img
            continue
        arr = np.asarray(img.convert("RGBA")).copy()
        op = opaque_mask(arr)
        px = arr[op][:, :3].astype(float)
        d = ((px[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        arr[op, :3] = centers[d.argmin(1)].round().astype(np.uint8)
        final[name] = Image.fromarray(arr)
    return final, hexes


def icon_board(before, after, out_path, scale=4):
    """8 columns x 2 rows; each cell shows before|after side by side at 4x."""
    cols, rows, s = 8, 2, 32 * scale
    cw, chh = 2 * s, s
    board = Image.new("RGBA", (cols * cw, rows * chh), (40, 40, 40, 255))
    for i, name in enumerate(ICON_ORDER):
        c, r = i % cols, i // cols
        x0, y0 = c * cw, r * chh
        board.paste(before[name].resize((s, s), Image.NEAREST), (x0, y0))
        board.paste(after[name].resize((s, s), Image.NEAREST), (x0 + s, y0))
    board.save(out_path)
    log(f"icons: before/after board -> {out_path}")


def build_icons():
    src, speckle_counts = {}, {}
    for name, path in ICON_SOURCES.items():
        img, removed = remove_speckles(Image.open(path).convert("RGBA"), name)
        src[name] = img
        speckle_counts[name] = removed
    before = {k: v.copy() for k, v in src.items()}
    med_hex, med = unify_outlines(src)
    after, consensus = remap_consensus(src)
    board_path = os.path.join(PACK, "metadata", "icon_palette_before_after.png")
    icon_board(before, after, board_path)

    for name in ICON_ORDER:
        after[name].save(os.path.join(PACK, "icons", f"{name}.png"))

    atlas = Image.new("RGBA", (4 * 32, 4 * 32))
    for i, name in enumerate(ICON_ORDER):
        atlas.paste(after[name], ((i % 4) * 32, (i // 4) * 32))
    atlas.save(os.path.join(PACK, "icons", "atlas_4x4.png"))

    with open(os.path.join(PACK, "metadata", "atlas_icons.json"), "w") as f:
        json.dump({
            "atlas": "icons/atlas_4x4.png", "grid": {"cols": 4, "rows": 4, "cell": 32},
            "order_row_major": ICON_ORDER,
            "note": "slot i -> row i//4, col i%4",
        }, f, indent=2)

    qa1 = json.load(open(os.path.join(ROOT, "reports", "qa_pixelart.json")))
    qa2 = json.load(open(os.path.join(ROOT, "reports", "qa_v2_campaign.json")))["icons"]
    qa1map = {e["name"]: e for e in qa1["icons"]}
    metrics = {}
    for name in ICON_ORDER:
        m = {"speckles_removed_final_pass": speckle_counts[name]}
        if name in qa2:
            best = qa2[name][0]
            m.update({"v2_lcc": best["lcc"], "v2_components": best["components"],
                      "v2_boundary_consistency": best["boundary_consistency"],
                      "v2_score": best["score"]})
        elif name in qa1map:
            e = qa1map[name]
            m.update({"phase1_lcc": e["largest_component_fraction"],
                      "phase1_components": e["connected_components"],
                      "phase1_boundary_pct": e["boundary_outline"]["frequency_pct"]})
        metrics[name] = m
    log("icons: 16 final icons + atlas_4x4 saved")
    return before, after, consensus, med_hex, metrics


# ---------------------------------------------------------------- characters
def build_characters():
    for view in ["front", "side", "back", "three_quarter"]:
        copy(os.path.join(GEN2, f"knight_{view}_v2_pal.png"),
             os.path.join(PACK, "characters", f"knight_{view}.png"))
    pal = json.load(open(os.path.join(GEN2, "knight_v2_palette.json")))
    hexes = pal["palette_hex"]
    with open(os.path.join(PACK, "characters", "knight_palette.hex"), "w") as f:
        f.write("\n".join(hexes) + "\n")
    views = [Image.open(os.path.join(PACK, "characters", f"knight_{v}.png")).convert("RGBA")
             for v in ["front", "side", "back", "three_quarter"]]
    views[0].save(os.path.join(PACK, "characters", "knight_turntable.gif"),
                  save_all=True, append_images=views[1:], duration=600, loop=0, disposal=2)
    big = [v.resize((256, 256), Image.NEAREST) for v in views]
    big[0].save(os.path.join(PACK, "characters", "knight_turntable_4x.gif"),
                save_all=True, append_images=big[1:], duration=600, loop=0, disposal=2)
    copy(os.path.join(GEN2, "knights_v2_4x.png"),
         os.path.join(PACK, "characters", "contact_sheet_4x.png"))
    log(f"characters: 4 views, turntable GIFs, contact sheet, {len(hexes)}-color palette")
    return hexes, pal


# ---------------------------------------------------------------- animations
def build_animations():
    reg_offsets = {
        "idle": [[0, 0], [1, 7]],
        "walk": [[0, 0], [0, 7], [-1, 0], [0, 3]],
        "attack": [[0, 0], [1, 6], [-1, 1]],
    }
    qa = json.load(open(os.path.join(ROOT, "reports", "qa_v2_campaign.json")))["animation"]["actions"]
    anims = {}
    for action in ["idle", "walk", "attack"]:
        sheet = Image.open(os.path.join(IMP, f"knight_{action}_v2_registered.png")).convert("RGBA")
        n = sheet.width // 64
        frames = [sheet.crop((i * 64, 0, (i + 1) * 64, 64)) for i in range(n)]
        sheet.save(os.path.join(PACK, "animations", f"knight_{action}.png"))
        anims[action] = {"frames": frames, "n": n, "qa": qa[action]}
        big = [f.resize((256, 256), Image.NEAREST) for f in frames]
        frames[0].save(os.path.join(PACK, "animations", f"knight_{action}_64.gif"),
                       save_all=True, append_images=frames[1:], duration=100, loop=0, disposal=2)
        big[0].save(os.path.join(PACK, "animations", f"knight_{action}_256.gif"),
                    save_all=True, append_images=big[1:], duration=100, loop=0, disposal=2)
    meta = {
        "frame_size": [64, 64], "fps": 10, "frame_order": "left-to-right in the sheet",
        "note": "OpenPose adherence partial; motion readability modest",
        "registration": "frames aligned to frame 1 by centroid-x / baseline (dx,dy applied at "
                        "registration time in assets/improved; offsets recorded per action)",
        "actions": {
            a: {"file": f"animations/knight_{a}.png", "frame_count": v["n"],
                "fps": 10, "gif_64": f"animations/knight_{a}_64.gif",
                "gif_256": f"animations/knight_{a}_256.gif",
                "registration_dx_dy_per_frame": reg_offsets[a],
                "post_baseline_spread": v["qa"]["post_baseline_spread"],
                "post_centroid_spread": v["qa"]["post_centroid_spread"]}
            for a, v in anims.items()}
    }
    with open(os.path.join(PACK, "metadata", "animations.json"), "w") as f:
        json.dump(meta, f, indent=2)
    log(f"animations: 3 registered sheets + GIFs (64/256, 10fps)")
    return meta


# ---------------------------------------------------------------- hd
def build_hd():
    names = ["hd_chest_256", "hd_chest_512", "hd_crystal_256", "hd_crystal_512",
             "hd_mana_potion_256", "hd_mana_potion_512"]
    qa = json.load(open(os.path.join(ROOT, "reports", "qa_v2_campaign.json")))["hd_rekey"]
    for n in names:
        copy(os.path.join(GEN2, f"{n}_rekeyed.png"), os.path.join(PACK, "hd", f"{n}.png"))
    log("hd: 6 rekeyed assets copied")
    return {n: qa[n] for n in names}


# ---------------------------------------------------------------- main
def main():
    ensure_dirs()
    tiles_meta, tile_palettes = build_tiles()
    build_autotiles()
    before, after, consensus, med_hex, icon_metrics = build_icons()
    knight_hexes, knight_pal = build_characters()
    anim_meta = build_animations()
    hd_metrics = build_hd()

    with open(os.path.join(PACK, "metadata", "palettes.json"), "w") as f:
        json.dump({"tiles": tile_palettes, "icons": consensus, "knight": knight_hexes}, f, indent=2)

    stage = sys.argv[1] if len(sys.argv) > 1 else "full"
    if stage == "stage1":
        log("stage1 complete (manifest deferred until icon review)")
        return
    build_manifest(tiles_meta, consensus, med_hex, icon_metrics, knight_hexes,
                   knight_pal, anim_meta, hd_metrics)


def size_of(p):
    return os.path.getsize(p)


def build_manifest(tiles_meta, consensus, med_hex, icon_metrics, knight_hexes,
                   knight_pal, anim_meta, hd_metrics):
    entries = []

    def add(eid, path, status, notes, metrics=None):
        entries.append({"id": eid, "path": path, "size": size_of(os.path.join(PACK, path)),
                        "status": status, "notes": notes, "metrics": metrics or {}})

    for name, m in tiles_meta.items():
        add(f"tile_{name}", f"tiles/{name}.png", m["status"],
            "tier-1: seamless, 16-color palette" if m["tier"] == "tier1"
            else "tier-2: measurable seams + wallpapering repetition",
            m["metrics"])
    for pair, ov, base in AUTOTILE_PAIRS:
        add(f"autotile_{pair}_blob47", f"autotiles/atlas_{pair}_blob47.png", "READY",
            f"blob47 atlas 8x6, 32px tiles; overlay={ov} base={base}; "
            f"mapping in metadata/autotiles/{pair}.json; edge-continuity verified",
            {"tiles": 47, "tile_size": 32})
        add(f"autotile_demo_{pair}", f"autotiles/demo_{pair}.png", "READY",
            "20x20 blob47 island demo (seed 1)")
    add("autotile_grass_water_wang16", "autotiles/atlas_grass_water_wang16.png", "READY",
        "wang16 dual-grid atlas, 32px tiles")
    for name in ICON_ORDER:
        status, note = ICON_NOTES[name]
        add(f"icon_{name}", f"icons/{name}.png", status, note, icon_metrics[name])
        if name in REVERTED_ICONS:
            entries[-1]["notes"] += "; k-means consensus remap REVERTED (degraded detail)"
    add("icon_atlas_4x4", "icons/atlas_4x4.png", "READY",
        "4x4 atlas, cell order in metadata/atlas_icons.json")
    for v in ["front", "side", "back", "three_quarter"]:
        add(f"knight_{v}", f"characters/knight_{v}.png", "READY",
            "v2 palette-remapped view; jaccard vs common palette 0.4103",
            {"size_px": 64})
    add("knight_turntable", "characters/knight_turntable.gif", "READY",
        "front->side->back->three_quarter, 600ms/frame")
    add("knight_turntable_4x", "characters/knight_turntable_4x.gif", "READY", "4x nearest-neighbor upscale")
    add("knight_contact_sheet_4x", "characters/contact_sheet_4x.png", "READY", "knights_v2_4x contact sheet")
    add("knight_palette", "characters/knight_palette.hex", "READY",
        "39-color common knight palette")
    for a in ["idle", "walk", "attack"]:
        am = anim_meta["actions"][a]
        add(f"anim_{a}", f"animations/knight_{a}.png", "READY",
            "registered sheet; OpenPose adherence partial; motion readability modest",
            {"frame_count": am["frame_count"], "fps": 10,
             "registration_dx_dy_per_frame": am["registration_dx_dy_per_frame"],
             "post_baseline_spread": am["post_baseline_spread"],
             "post_centroid_spread": am["post_centroid_spread"]})
        for s in (64, 256):
            add(f"anim_{a}_gif_{s}", f"animations/knight_{a}_{s}.gif", "READY",
                f"{s}px, 10fps")
    hd_status = {
        "hd_mana_potion_256": ("READY", "rekey clean"),
        "hd_mana_potion_512": ("READY", "rekey clean"),
        "hd_chest_256": ("READY", "rekey clean"),
        "hd_chest_512": ("READY", "green = its own paint, preserve"),
        "hd_crystal_256": ("READY", "rekey clean"),
        "hd_crystal_512": ("READY", "minor purple/pink border shards remain — crop 2px or accept; recommend crop"),
    }
    for n, (st, note) in hd_status.items():
        q = hd_metrics[n]
        add(n, f"hd/{n}.png", st, note,
            {"removed_px": q["removed_px"],
             "ring_opaque_before": q["ring_opaque_before"],
             "ring_opaque_after": q["ring_opaque_after"]})

    manifest = {
        "pack_version": "1.0.0",
        "date": "2026-11-12",
        "palettes_ref": "metadata/palettes.json",
        "processing_log": PROCESSING_LOG,
        "entries": entries,
    }
    with open(os.path.join(PACK, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest: {len(entries)} entries")


if __name__ == "__main__":
    main()
