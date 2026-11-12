#!/usr/bin/env python3
"""Phase-2 regeneration campaign v2 (regeneration-stage defect fixes).

Stages (run individually): master | views | anim | icons | terrain
All outputs go to assets/generated_v2/, never touching assets/generated or
assets/validated. Reports to reports/qa_terrain_v2.json etc.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request
from collections import Counter

import numpy as np
import psutil
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from qa_terrain import measure_tile  # noqa: E402

COMFY_URL = "http://127.0.0.1:8188"
COMFY_IN = "/Users/viktor/ComfyUI-Shared/input"
COMFY_OUT = "/Users/viktor/ComfyUI-Shared/output"
GEN_V2 = os.path.join(ROOT, "assets", "generated_v2")
REPORTS = os.path.join(ROOT, "reports")
LOG = os.path.join(ROOT, "logs", "v2tmp")
os.makedirs(GEN_V2, exist_ok=True)
os.makedirs(LOG, exist_ok=True)

CKPT = "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
LORa_LIGHT = "sdxl_lightning_8step_lora.safetensors"
LORA_PIXEL = "pixel-art-xl.safetensors"
IPADAPTER_FILE = "ip-adapter-plus_sdxl_vit-h.safetensors"
CLIP_VISION_FILE = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
CN_OPENPOSE = "OpenPoseXL2.safetensors"

CHAR_BASE = "brave medieval knight in gleaming steel plate armor, red cape, holding a sword"
NEG_STD = "blurry, photographic, realistic, messy, noisy, gradient, complex background, shadow"

TIMING = {"gens": 0, "total_s": 0.0, "peak_ram_gb": 0.0, "peak_swap_mb": 0.0}
SWAP_POSITIVE_SINCE = None


def log(msg):
    print(msg, flush=True)


def ram_guard():
    global SWAP_POSITIVE_SINCE
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    free_gb = vm.available / 1024**3
    swap_mb = sw.used / 1024**2
    TIMING["peak_ram_gb"] = max(TIMING["peak_ram_gb"], vm.used / 1024**3)
    TIMING["peak_swap_mb"] = max(TIMING["peak_swap_mb"], swap_mb)
    if swap_mb > 0:
        now = time.time()
        if SWAP_POSITIVE_SINCE is None:
            SWAP_POSITIVE_SINCE = now
        elif now - SWAP_POSITIVE_SINCE > 60:
            log(f"[ram] swap {swap_mb:.0f}MB for >60s, waiting 30s")
            time.sleep(30)
    else:
        SWAP_POSITIVE_SINCE = None
    while free_gb < 2.0:
        log(f"[ram] ram_free {free_gb:.2f}GB < 2GB, waiting 20s")
        time.sleep(20)
        free_gb = psutil.virtual_memory().available / 1024**3


def submit_and_wait(workflow, client_id="v2", timeout=300):
    ram_guard()
    t0 = time.time()
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=json.dumps({"prompt": workflow, "client_id": client_id}).encode(),
        headers={"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=300))
    pid = res["prompt_id"]
    while True:
        if time.time() - t0 > timeout:
            raise TimeoutError(f"workflow {pid} exceeded {timeout}s")
        time.sleep(1)
        h = json.load(urllib.request.urlopen(f"{COMFY_URL}/history/{pid}", timeout=10))
        if not h:
            continue
        entry = h[pid]
        status = entry["status"]["status_str"]
        if status == "error":
            raise RuntimeError(f"workflow failed: {json.dumps(entry['status'])[:500]}")
        if status == "success":
            TIMING["gens"] += 1
            TIMING["total_s"] += time.time() - t0
            imgs = []
            for out in (entry.get("outputs") or {}).values():
                for im in out.get("images", []):
                    imgs.append(im)
            return imgs, round(time.time() - t0, 1)


def fetch_image(imginfo) -> Image.Image:
    q = f"{COMFY_URL}/view?filename={urllib.parse.quote(imginfo['filename'])}" \
        f"&subfolder={urllib.parse.quote(imginfo.get('subfolder',''))}" \
        f"&type={imginfo.get('type','output')}"
    data = urllib.request.urlopen(q, timeout=60).read()
    return Image.open(io.BytesIO(data))


import urllib.parse  # noqa: E402


def save_png(im: Image.Image, name: str):
    path = os.path.join(GEN_V2, name)
    im.save(path)
    return path


# ------------------------------------------------------------------ workflows

def base_chain():
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "lightning": {"class_type": "LoraLoader", "inputs": {
            "lora_name": LORa_LIGHT, "strength_model": 1.0, "strength_clip": 1.0,
            "model": ["ckpt", 0], "clip": ["ckpt", 1]}},
    }


def pixel_lora_node(model_ref, clip_ref, strength=1.1):
    return {"class_type": "LoraLoader", "inputs": {
        "lora_name": LORA_PIXEL, "strength_model": strength, "strength_clip": 1.0,
        "model": model_ref, "clip": clip_ref}}


def sk_pipeline(decode_ref, art_size, prefix, colors=16, bg_remove=True, tol=0.08):
    nodes = {}
    src = decode_ref
    if bg_remove:
        nodes["bg_remove"] = {"class_type": "SK_BackgroundRemove", "inputs": {
            "image": decode_ref, "mode": "key_refine", "remove_shadow": True,
            "tolerance": tol, "mask_threshold": 0.5, "enabled": True}}
        src = ["bg_remove", 0]
    nodes["pp"] = {"class_type": "SK_PixelPerfect", "inputs": {
        "image": src, "mode": "fixed_size", "width": art_size, "height": art_size,
        "scale": 16, "method": "dominant", "pre_colors": 48}}
    nodes["pal"] = {"class_type": "SK_Palette", "inputs": {
        "image": ["pp", 0], "source": "auto", "colors": colors, "preset": "PICO-8",
        "dither": "none", "dither_strength": 0.5, "shared_palette": True}}
    nodes["save"] = {"class_type": "SaveImage", "inputs": {
        "filename_prefix": prefix, "images": ["pal", 0]}}
    return nodes


def wf_master(prompt, prefix, seed):
    """512x512 full-body knight on green, no pixel lora, no downscale."""
    wf = base_chain()
    wf["latent"] = {"class_type": "EmptyLatentImage",
                    "inputs": {"width": 512, "height": 512, "batch_size": 1}}
    wf["pos"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": f"{prompt}, on a solid pure green background, isolated, centered",
        "clip": ["lightning", 1]}}
    wf["neg"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": "pixel art, 3d render, photo, complex background, shadow, blurry, multiple characters",
        "clip": ["lightning", 1]}}
    wf["sampler"] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": 8, "cfg": 1.5, "sampler_name": "euler",
        "scheduler": "sgm_uniform", "denoise": 1.0, "model": ["lightning", 0],
        "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    wf["decode"] = {"class_type": "VAEDecode",
                    "inputs": {"samples": ["sampler", 0], "vae": ["ckpt", 2]}}
    wf["bg_remove"] = {"class_type": "SK_BackgroundRemove", "inputs": {
        "image": ["decode", 0], "mode": "key_refine", "remove_shadow": True,
        "tolerance": 0.10, "mask_threshold": 0.5, "enabled": True}}
    wf["save"] = {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": prefix, "images": ["bg_remove", 0]}}
    return wf


def wf_ipadapter_knight(prompt, prefix, seed, art_size=64, pose_file=None,
                        cn_strength=0.8, cn_end=0.85, ipa_weight=0.9,
                        latent=512, ipa_image="knight_master_reference.png",
                        use_ipadapter=True):
    wf = base_chain()
    wf["pixel_lora"] = pixel_lora_node(["lightning", 0], ["lightning", 1], 1.1)
    model_ref = ["pixel_lora", 0]
    clip_ref = ["pixel_lora", 1]
    if use_ipadapter:
        wf["ipa_model"] = {"class_type": "IPAdapterModelLoader",
                           "inputs": {"ipadapter_file": IPADAPTER_FILE}}
        wf["clip_vision"] = {"class_type": "CLIPVisionLoader",
                             "inputs": {"clip_name": CLIP_VISION_FILE}}
        wf["ipa_img"] = {"class_type": "LoadImage",
                         "inputs": {"image": ipa_image}}
        wf["ipa"] = {"class_type": "IPAdapterAdvanced", "inputs": {
            "model": model_ref, "ipadapter": ["ipa_model", 0],
            "image": ["ipa_img", 0], "clip_vision": ["clip_vision", 0],
            "weight": ipa_weight, "weight_type": "linear", "combine_embeds": "concat",
            "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "K+V"}}
        model_ref = ["ipa", 0]
    pos_text = prompt
    if pose_file:
        wf["cn"] = {"class_type": "ControlNetLoader",
                    "inputs": {"control_net_name": CN_OPENPOSE}}
        wf["cn_img"] = {"class_type": "LoadImage", "inputs": {"image": pose_file}}
        wf["cn_apply"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
            "positive": ["pos", 0], "negative": ["neg", 0],
            "control_net": ["cn", 0], "image": ["cn_img", 0],
            "strength": cn_strength, "start_percent": 0.0, "end_percent": cn_end}}
    wf["latent"] = {"class_type": "EmptyLatentImage",
                    "inputs": {"width": latent, "height": latent, "batch_size": 1}}
    wf["pos"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": f"pixel art, {pos_text}, 16-bit sprite, clean pixel contours",
        "clip": clip_ref}}
    wf["neg"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": NEG_STD, "clip": clip_ref}}
    pos_ref = ["cn_apply", 0] if pose_file else ["pos", 0]
    neg_ref = ["cn_apply", 1] if pose_file else ["neg", 0]
    wf["sampler"] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": 8, "cfg": 1.5, "sampler_name": "euler",
        "scheduler": "sgm_uniform", "denoise": 1.0, "model": model_ref,
        "positive": pos_ref, "negative": neg_ref, "latent_image": ["latent", 0]}}
    wf["decode"] = {"class_type": "VAEDecode",
                    "inputs": {"samples": ["sampler", 0], "vae": ["ckpt", 2]}}
    wf.update(sk_pipeline(["decode", 0], art_size, prefix))
    return wf


def wf_terrain(prompt, prefix, seed, art_size):
    wf = base_chain()
    wf["pixel_lora"] = pixel_lora_node(["lightning", 0], ["lightning", 1], 1.1)
    wf["seamless"] = {"class_type": "SK_SeamlessTiling", "inputs": {
        "model": ["pixel_lora", 0], "axes": "both", "align": 1}}
    wf["latent"] = {"class_type": "EmptyLatentImage",
                    "inputs": {"width": 512, "height": 512, "batch_size": 1}}
    wf["pos"] = {"class_type": "CLIPTextEncode",
                 "inputs": {"text": prompt, "clip": ["pixel_lora", 1]}}
    wf["neg"] = {"class_type": "CLIPTextEncode", "inputs": {
        "text": "blurry, photographic, 3d, realistic, watermark, text, objects, "
                "characters, border, frame, vignette",
        "clip": ["pixel_lora", 1]}}
    wf["sampler"] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": 8, "cfg": 1.5, "sampler_name": "euler",
        "scheduler": "sgm_uniform", "denoise": 1.0, "model": ["seamless", 0],
        "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    wf["vae_decode"] = {"class_type": "SK_SeamlessVAEDecode", "inputs": {
        "samples": ["sampler", 0], "vae": ["ckpt", 2], "axes": "both", "pad_latent": 8}}
    wf.update(sk_pipeline(["vae_decode", 0], art_size, prefix, bg_remove=False))
    return wf


# ------------------------------------------------------------------ metrics

def load_rgba(path):
    return np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)


def opaque_colors(arr):
    return {tuple(int(v) for v in c) for c in arr[arr[..., 3] == 255].reshape(-1, 4)}


def largest_component_fraction(arr):
    op = arr[..., 3] == 255
    h, w = op.shape
    lab = np.zeros((h, w), dtype=int)
    cur = 0
    sizes = {}
    for y in range(h):
        for x in range(w):
            if op[y, x] and lab[y, x] == 0:
                cur += 1
                stack = [(y, x)]
                lab[y, x] = cur
                n = 0
                while stack:
                    cy, cx = stack.pop()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and op[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            stack.append((ny, nx))
                sizes[cur] = n
    total = int(op.sum())
    return (max(sizes.values()) / total) if total else 0.0, len(sizes)


def boundary_consistency(arr):
    """Fraction of silhouette-boundary opaque pixels in the most common color."""
    op = arr[..., 3] == 255
    h, w = op.shape
    px = []
    for y in range(h):
        for x in range(w):
            if op[y, x]:
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if not (0 <= ny < h and 0 <= nx < w) or not op[ny, nx]:
                        px.append(tuple(arr[y, x][:3]))
                        break
    if not px:
        return 0.0
    return Counter(px).most_common(1)[0][1] / len(px)


def silhouette_stats(arr):
    op = arr[..., 3] == 255
    ys, xs = np.nonzero(op)
    if not len(ys):
        return {"height": 0, "width": 0, "baseline": -1, "centroid_x": -1,
                "components": 0, "lcc": 0.0}
    lcc, comps = largest_component_fraction(arr)
    return {"height": int(ys.max() - ys.min() + 1),
            "width": int(xs.max() - xs.min() + 1),
            "baseline": int(ys.max()), "centroid_x": round(float(xs.mean()), 2),
            "components": comps, "lcc": round(lcc, 4)}


def jaccard(a, b):
    u = a | b
    return round(len(a & b) / len(u), 4) if u else 1.0


def bucket_colors(arr, bits=4):
    """Colors quantized to `bits` per channel so photo-master vs pixel-art
    palettes can be compared meaningfully."""
    sh = 8 - bits
    px = arr[arr[..., 3] == 255][:, :3] >> sh
    return {tuple(int(v) for v in c) for c in px}


def bucketed_jaccard(a_arr, b_arr, bits=4):
    return jaccard(bucket_colors(a_arr, bits), bucket_colors(b_arr, bits))


def contact_sheet(paths, out_name, cell=256, labels=None):
    ims = []
    for p in paths:
        im = Image.open(p).convert("RGBA")
        im = im.resize((cell, cell), Image.NEAREST)
        bg = Image.new("RGBA", (cell, cell), (240, 240, 240, 255))
        bg.paste(im, (0, 0), im)
        ims.append(bg)
    sheet = Image.new("RGB", (cell * len(ims), cell + 20), (30, 30, 34))
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        sheet.paste(im.convert("RGB"), (i * cell, 0))
        if labels:
            d.text((i * cell + 4, cell + 3), labels[i], fill=(200, 200, 205))
    out = os.path.join(GEN_V2, out_name)
    sheet.save(out)
    return out


def crop_master(im: Image.Image, target=512) -> Image.Image:
    """Key stray green, crop to visible bbox with margin, square pad, resize."""
    arr = np.array(im.convert("RGBA"), dtype=np.uint8)
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    stray = (arr[..., 3] > 0) & (g > 90) & (g > np.maximum(r, b) + 12)
    arr[..., 3][stray] = 0
    arr[arr[..., 3] == 0] = (128, 128, 128, 0)  # neutral RGB under transparency
    op = arr[..., 3] > 0
    ys, xs = np.nonzero(op)
    top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    h, w = bot - top + 1, right - left + 1
    side = int(max(h, w) * 1.08)
    sq = Image.fromarray(arr).crop((left, top, right + 1, bot + 1))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(sq, ((side - w) // 2, (side - h) // 2), sq)
    out = canvas.resize((target, target), Image.LANCZOS)
    a2 = np.array(out)
    r2, g2, b2 = a2[..., 0].astype(int), a2[..., 1].astype(int), a2[..., 2].astype(int)
    stray2 = (a2[..., 3] > 0) & (g2 > 90) & (g2 > np.maximum(r2, b2) + 12)
    a2[..., 3][stray2] = 0
    keep_only_main_component(a2)
    return Image.fromarray(a2)


def keep_only_main_component(arr):
    """Zero alpha of everything except the largest connected opaque component."""
    op = arr[..., 3] > 0
    h, w = op.shape
    seen = np.zeros((h, w), dtype=bool)
    best, best_n = None, 0
    for y in range(h):
        for x in range(w):
            if op[y, x] and not seen[y, x]:
                stack = [(y, x)]
                seen[y, x] = True
                comp = []
                while stack:
                    cy, cx = stack.pop()
                    comp.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and op[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if len(comp) > best_n:
                    best_n, best = len(comp), comp
    mask = np.zeros((h, w), dtype=bool)
    for y, x in best:
        mask[y, x] = True
    arr[..., 3][~mask] = 0


# ------------------------------------------------------------------ stage 1

STAGE = sys.argv[1] if len(sys.argv) > 1 else "all"


def stage_master():
    prompt = f"{CHAR_BASE}, full body, facing forward, neutral stance"
    wf = wf_master(prompt, "v2_master", seed=9001)
    with open(os.path.join(LOG, "wf_master.json"), "w") as f:
        json.dump(wf, f)
    imgs, dt = submit_and_wait(wf)
    im = fetch_image(imgs[0])
    master = crop_master(im, 512)
    mpath = save_png(master, "knight_master_reference.png")
    log(f"master saved {mpath} ({dt}s)")
    # copy flattened reference into ComfyUI input for LoadImage
    ref = Image.new("RGB", master.size, (255, 255, 255))
    ref.paste(master, (0, 0), master)
    ref.save(os.path.join(COMFY_IN, "knight_master_reference.png"))
    opaque = np.array(master)[..., 3] == 255
    flat = Image.new("RGB", master.size, (255, 255, 255))
    flat.paste(master, (0, 0), master)
    pal = flat.quantize(colors=16, method=Image.MEDIANCUT)
    counts = Counter(np.array(pal)[opaque].ravel().tolist())
    keep = {i for i, _ in counts.most_common(16)}
    hexes = sorted({"#{:02X}{:02X}{:02X}".format(*pal.getpalette()[i*3:i*3+3]) for i in keep})
    json.dump({"master_palette_hex": hexes}, open(os.path.join(GEN_V2, "master_palette_tmp.json"), "w"), indent=2)
    return mpath, hexes


# ------------------------------------------------------------------ stage 2

VIEW_PROMPTS = {
    "front": "front view of a knight, facing directly forward, standing neutral pose",
    "side": "side profile view of a knight, facing to the right, standing neutral pose",
    "back": "back view of a knight, seen from behind, showing cape and armor back",
    "three_quarter": "three-quarter view of a knight, 45-degree angle, standing pose",
}


def gen_candidates(prompt, pose_file, prefix, base_seed, n, art_size=64, **kw):
    out = []
    for i in range(n):
        wf = wf_ipadapter_knight(prompt, f"{prefix}_c{i}", base_seed + i * 7,
                                 art_size=art_size, pose_file=pose_file, **kw)
        imgs, dt = submit_and_wait(wf)
        im = fetch_image(imgs[0]).convert("RGBA")
        p = save_png(im, os.path.basename(prefix) + f"_c{i}.png")
        log(f"  {prefix}_c{i} ({dt}s)")
        out.append(p)
    return out


def stage_views():
    mpath = os.path.join(GEN_V2, "knight_master_reference.png")
    master_arr = load_rgba(mpath)
    master_pal = opaque_colors(master_arr)
    results = {"candidates": {}, "master_palette_hex": sorted(
        "#{:02X}{:02X}{:02X}".format(*c[:3]) for c in master_pal)}
    chosen = {}
    for view, vp in VIEW_PROMPTS.items():
        prompt = f"{CHAR_BASE}, {vp}"
        cands = gen_candidates(prompt, None, f"v2_view_{view}", 10000 + hash(view) % 1000, 2)
        scored = []
        for p in cands:
            arr = load_rgba(p)
            sil = silhouette_stats(arr)
            jac = jaccard(opaque_colors(arr), master_pal)
            bjac = bucketed_jaccard(arr, master_arr)
            scored.append({"path": p, "jaccard_vs_master": jac,
                           "bucketed_jaccard_vs_master": bjac, **sil,
                           "score": bjac + sil["lcc"]})
        scored.sort(key=lambda d: -d["score"])
        results["candidates"][view] = scored
        chosen[view] = scored[0]["path"]
        log(f"{view}: " + ", ".join(f"{os.path.basename(s['path'])} jac={s['jaccard_vs_master']} lcc={s['lcc']} h={s['height']}" for s in scored))
    sheet = contact_sheet([chosen[v] for v in VIEW_PROMPTS], "knights_v2_4x.png",
                          labels=list(VIEW_PROMPTS))
    log(f"contact sheet: {sheet}")
    results["chosen"] = {v: os.path.basename(p) for v, p in chosen.items()}
    for v in VIEW_PROMPTS:
        arr = load_rgba(chosen[v])
        save_png(Image.fromarray(arr), f"knight_{v}_v2.png")
    return chosen, results


def build_common_palette(chosen, cap=40):
    union = set()
    for p in chosen.values():
        union |= opaque_colors(load_rgba(p))
    if len(union) > cap:
        cols = np.array(sorted(union), dtype=np.float32)
        pal_im = Image.new("RGB", (len(cols), 1))
        pal_im.putdata([tuple(int(v) for v in c) for c in cols])
        q = pal_im.convert("P", palette=Image.ADAPTIVE, colors=cap)
        rgb = q.convert("RGB")
        union = {rgb.getpixel((x, 0)) for x in range(len(cols))}
    return sorted(union)


def remap_to_palette(arr, palette):
    out = arr.copy()
    op = arr[..., 3] == 255
    pal = np.array(palette, dtype=np.int32)
    px = arr[op][:, :3].astype(np.int32)
    d = ((px[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
    out[op, :3] = pal[d.argmin(axis=1)]
    return out


def finish_views(chosen, results):
    palette = build_common_palette(chosen)
    hexes = ["#{:02X}{:02X}{:02X}".format(*c) for c in palette]
    pal_jac = {}
    for v, p in chosen.items():
        arr = remap_to_palette(load_rgba(p), palette)
        save_png(Image.fromarray(arr), f"knight_{v}_v2_pal.png")
        pal_arr = load_rgba(os.path.join(GEN_V2, f"knight_{v}_v2_pal.png"))
        pal_jac[v] = jaccard({tuple(c[:3]) for c in pal_arr[pal_arr[..., 3] == 255].reshape(-1, 4)},
                             {tuple(int(x) for x in c) for c in palette})
    results["common_palette_hex"] = hexes
    results["post_remap_jaccard_vs_common"] = pal_jac
    json.dump({"palette_hex": hexes,
               "post_remap_jaccard_vs_common": pal_jac,
               "candidate_scores": results["candidates"]},
              open(os.path.join(GEN_V2, "knight_v2_palette.json"), "w"), indent=2)
    log(f"common palette: {len(hexes)} colors")


# ------------------------------------------------------------------ stage 3

def draw_pose(joints, lines, fname, size=64):
    """joints: {name:(x,y,color)} in 64-space; lines: [(nameA,nameB)]."""
    k = size * 8
    im = Image.new("RGB", (k, k), (255, 255, 255))
    d = ImageDraw.Draw(im)
    P = {n: (x * k / size, y * k / size) for n, (x, y, *_ ) in joints.items()}
    for a, b in lines:
        d.line([P[a], P[b]], fill=(20, 20, 20), width=int(k / 40))
    for n, (x, y, *rest) in joints.items():
        col = rest[0] if rest else (200, 30, 30)
        r = k / 42
        d.ellipse([x * k / size - r, y * k / size - r, x * k / size + r, y * k / size + r], fill=col)
    path = os.path.join(COMFY_IN, fname)
    im.save(path)
    return fname


def limb(head, neck, sh_l, el_l, wr_l, sh_r, el_r, wr_r, hip, kn_l, an_l, kn_r, an_r):
    joints = {"head": (head[0], head[1], (0, 0, 255)), "neck": (neck[0], neck[1]),
              "sh_l": (sh_l[0], sh_l[1], (0, 0, 255)), "el_l": (el_l[0], el_l[1], (0, 0, 255)),
              "wr_l": (wr_l[0], wr_l[1], (0, 0, 255)),
              "sh_r": (sh_r[0], sh_r[1], (255, 0, 0)), "el_r": (el_r[0], el_r[1], (255, 0, 0)),
              "wr_r": (wr_r[0], wr_r[1], (255, 0, 0)),
              "hip": (hip[0], hip[1]),
              "kn_l": (kn_l[0], kn_l[1], (0, 0, 255)), "an_l": (an_l[0], an_l[1], (0, 0, 255)),
              "kn_r": (kn_r[0], kn_r[1], (255, 0, 0)), "an_r": (an_r[0], an_r[1], (255, 0, 0))}
    lines = [("head", "neck"), ("neck", "sh_l"), ("sh_l", "el_l"), ("el_l", "wr_l"),
             ("neck", "sh_r"), ("sh_r", "el_r"), ("el_r", "wr_r"),
             ("neck", "hip"), ("hip", "kn_l"), ("kn_l", "an_l"),
             ("hip", "kn_r"), ("kn_r", "an_r")]
    return joints, lines


POSES = {
    "idle_0": lambda: limb((32, 10), (32, 15), (27, 16), (26, 21), (26, 26),
                           (37, 16), (38, 21), (38, 26), (32, 27),
                           (29, 35), (29, 43), (35, 35), (35, 43)),
    "idle_1": lambda: limb((32, 9), (32, 14), (27, 15), (26, 20), (26, 25),
                           (37, 15), (38, 20), (38, 25), (32, 26),
                           (29, 34), (29, 42), (35, 34), (35, 42)),
    "walk_0": lambda: limb((32, 10), (32, 15), (27, 16), (25, 21), (24, 26),
                           (37, 16), (39, 21), (40, 25), (32, 27),
                           (27, 34), (26, 42), (37, 34), (38, 42)),
    "walk_1": lambda: limb((32, 10), (32, 15), (27, 16), (26, 21), (25, 25),
                           (37, 16), (38, 21), (39, 26), (32, 27),
                           (29, 34), (28, 42), (35, 34), (36, 42)),
    "walk_2": lambda: limb((32, 10), (32, 15), (27, 16), (29, 21), (30, 26),
                           (37, 16), (35, 21), (34, 26), (32, 27),
                           (37, 34), (38, 42), (27, 34), (26, 42)),
    "walk_3": lambda: limb((32, 10), (32, 15), (27, 16), (28, 21), (29, 25),
                           (37, 16), (36, 21), (35, 26), (32, 27),
                           (35, 34), (36, 42), (29, 34), (28, 42)),
    "attack_0": lambda: limb((32, 10), (32, 15), (27, 16), (24, 18), (21, 16),
                             (37, 16), (41, 13), (45, 9), (32, 27),
                             (29, 35), (29, 43), (35, 35), (35, 43)),
    "attack_1": lambda: limb((32, 11), (32, 16), (27, 17), (24, 22), (20, 26),
                             (37, 17), (42, 20), (47, 24), (32, 28),
                             (29, 36), (28, 44), (36, 36), (37, 44)),
    "attack_2": lambda: limb((32, 11), (32, 16), (27, 17), (26, 23), (24, 29),
                             (37, 17), (40, 22), (44, 28), (32, 28),
                             (29, 36), (28, 44), (36, 36), (37, 44)),
}

ANIM_PROMPTS = {
    "idle": "standing idle breathing pose, sword held at rest",
    "walk": "walking pose stepping forward",
    "attack": "sword attack slashing downward",
}


def translate(arr, dx, dy):
    out = np.zeros_like(arr)
    h, w = arr.shape[:2]
    x0, x1 = max(0, dx), min(w, w + dx)
    y0, y1 = max(0, dy), min(h, h + dy)
    if x1 <= x0 or y1 <= y0:
        return out
    out[y0:y1, x0:x1] = arr[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return out


def stage_anim():
    results = {"actions": {}}
    for action, n in (("idle", 2), ("walk", 4), ("attack", 3)):
        paths = []
        for i in range(n):
            pname = f"v2_pose_{action}_{i}.png"
            joints, lines = POSES[f"{action}_{i}"]()
            draw_pose(joints, lines, pname)
            prompt = f"{CHAR_BASE}, {ANIM_PROMPTS[action]}, full body, same character design as reference"
            cands = gen_candidates(prompt, pname, f"v2_anim_{action}_{i}", 20000 + i * 13, 1)
            paths.append(cands[0])
        # sheet
        frames = [Image.open(p).convert("RGBA") for p in paths]
        sheet = Image.new("RGBA", (64 * n, 64))
        for i, f in enumerate(frames):
            sheet.paste(f, (i * 64, 0))
        sheet_path = save_png(sheet, f"knight_{action}_v2_sheet.png")
        # metrics before registration
        arrs = [load_rgba(p) for p in paths]
        pre = [silhouette_stats(a) for a in arrs]
        pre_jac = [jaccard(opaque_colors(a), opaque_colors(arrs[0])) for a in arrs]
        # register to frame 1
        base = pre[0]
        reg = np.zeros_like(sheet and np.array(sheet, dtype=np.uint8))
        offsets = []
        for i, a in enumerate(arrs):
            dx = int(round(base["centroid_x"] - pre[i]["centroid_x"]))
            dy = base["baseline"] - pre[i]["baseline"]
            offsets.append((dx, dy))
            reg[:, i * 64:(i + 1) * 64] = translate(a, dx, dy)
        Image.fromarray(reg, "RGBA").save(os.path.join(
            ROOT, "assets", "improved", f"knight_{action}_v2_registered.png"))
        post = [silhouette_stats(reg[:, i * 64:(i + 1) * 64]) for i in range(n)]
        # GIFs 10fps at 64 and 256
        for size in (64, 256):
            ims = []
            for i in range(n):
                f = Image.fromarray(reg[:, i * 64:(i + 1) * 64], "RGBA")
                bg = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                bg.alpha_composite(f)
                ims.append(bg.resize((size, size), Image.NEAREST).convert("P", palette=Image.ADAPTIVE))
            ims[0].save(os.path.join(GEN_V2, f"knight_{action}_v2_{size}.gif"),
                        save_all=True, append_images=ims[1:], duration=100, loop=0)
        results["actions"][action] = {
            "files": [os.path.basename(p) for p in paths],
            "pre_registration": pre, "pre_palette_jaccard_vs_frame1": pre_jac,
            "offsets": offsets, "post_registration": post,
            "post_baseline_spread": max(p["baseline"] for p in post) - min(p["baseline"] for p in post),
            "post_centroid_spread": round(max(p["centroid_x"] for p in post) - min(p["centroid_x"] for p in post), 2),
            "sheet": os.path.basename(sheet_path)}
        log(f"{action}: pre baseline spread {max(p['baseline'] for p in pre)-min(p['baseline'] for p in pre)}, "
            f"post {results['actions'][action]['post_baseline_spread']}, jac {pre_jac}")
    json.dump(results, open(os.path.join(GEN_V2, "anim_v2_metrics.json"), "w"), indent=2)
    return results


# ------------------------------------------------------------------ stage 4

ICON_PROMPTS = {
    "potion_health": "single round glass flask filled with glowing red liquid, red potion bottle",
    "armor_shield": "round wooden shield with steel rim, big bold round shield shape",
    "craft_feather": "single large purple feather, bold simple feather shape",
    "craft_gem": "single large faceted cyan gemstone, bold crystal shape",
    "armor_chest": "steel chestplate armor, big bold symmetric torso plate",
}
ICON_SUFFIX = ("simple bold silhouette, large readable shapes, minimal detail, "
               "clean pixel clusters, no dithering, no tiny fragments, centered, "
               "RPG inventory icon")


def stage_icons():
    old = {n: os.path.join(ROOT, "assets", "generated", f"{n}.png")
           for n in ICON_PROMPTS}
    results = {"icons": {}}
    chosen = {}
    for name, ip in ICON_PROMPTS.items():
        prompt = f"{ip}, {ICON_SUFFIX}"
        cands = gen_candidates(prompt, None, f"v2_icon_{name}", 30000 + hash(name) % 997, 2,
                               art_size=32, use_ipadapter=False)
        scored = []
        for p in cands + [old[name]]:
            tag = "phase1" if p == old[name] else os.path.basename(p)
            arr = load_rgba(p)
            lcc, comps = largest_component_fraction(arr)
            bc = boundary_consistency(arr)
            scored.append({"path": p, "tag": tag, "lcc": round(lcc, 4),
                           "components": comps, "boundary_consistency": round(bc, 4),
                           "score": round(lcc + bc, 4)})
        scored.sort(key=lambda d: -d["score"])
        results["icons"][name] = scored
        best = scored[0]
        if best["tag"] == "phase1":
            log(f"{name}: phase-1 kept (v2 worse)")
            chosen[name] = old[name]
        else:
            chosen[name] = best["path"]
        log(f"{name}: " + ", ".join(f"{s['tag']} lcc={s['lcc']} bc={s['boundary_consistency']}" for s in scored))
    contact_sheet([chosen[n] for n in ICON_PROMPTS], "icons_v2_4x.png",
                  labels=list(ICON_PROMPTS))
    for n in ICON_PROMPTS:
        if chosen[n] != old[n]:
            Image.open(chosen[n]).convert("RGBA").save(
                os.path.join(GEN_V2, f"{n}_v2.png"))
    results["chosen"] = {n: os.path.basename(chosen[n]) for n in ICON_PROMPTS}
    json.dump(results, open(os.path.join(GEN_V2, "icons_v2_metrics.json"), "w"), indent=2)
    return results


# ------------------------------------------------------------------ stage 5

TERRAIN_PROMPT = ("pixel art, top-down seamless tile, even fine-grained texture, "
                  "uniform density across the whole square, no large stones, "
                  "no vignette, flat lighting, ")


def stage_terrain():
    results = {"tiles": {}}
    for name, flavor, base_seed in (
            ("sand", "golden desert sand with fine grain", 40001),
            ("stone", "grey cobblestone rock pathway", 40003)):
        for size in (32, 64):
            cands = []
            for i in range(2):
                wf = wf_terrain(TERRAIN_PROMPT + flavor + ", 16-bit pixel art",
                                f"v2_terrain_{name}_{size}_c{i}", base_seed + i * 11, size)
                imgs, dt = submit_and_wait(wf)
                p = save_png(fetch_image(imgs[0]).convert("RGBA"),
                             f"{name}_{size}_c{i}.png")
                cands.append(p)
                log(f"  {name}_{size}_c{i} ({dt}s)")
            scored = []
            for p in cands:
                m = measure_tile(p)
                m["file"] = os.path.basename(p)
                scored.append(m)
            old_path = os.path.join(ROOT, "assets", "generated", f"{name}_{size}.png")
            old_m = measure_tile(old_path)
            best = min(scored, key=lambda m: (m["avg_row_seam"] + m["avg_col_seam"],
                                              m["edge_density_cv"]))
            better = (best["avg_row_seam"] + best["avg_col_seam"]) < \
                     (old_m["avg_row_seam"] + old_m["avg_col_seam"])
            keep = best["file"] if better else "phase1"
            if better:
                Image.open(os.path.join(GEN_V2, best["file"])).convert("RGBA").save(
                    os.path.join(GEN_V2, f"{name}_{size}_v2.png"))
            results["tiles"][f"{name}_{size}"] = {
                "candidates": scored, "phase1": old_m, "kept": keep,
                "seam_before": round(old_m["avg_row_seam"] + old_m["avg_col_seam"], 4),
                "seam_after": round(best["avg_row_seam"] + best["avg_col_seam"], 4) if better else round(old_m["avg_row_seam"] + old_m["avg_col_seam"], 4)}
            log(f"{name}_{size}: phase1 seam {results['tiles'][f'{name}_{size}']['seam_before']}, "
                f"best v2 {results['tiles'][f'{name}_{size}']['seam_after']}, kept {keep}")
    json.dump(results, open(os.path.join(REPORTS, "qa_terrain_v2.json"), "w"), indent=2)
    return results


# ------------------------------------------------------------------ main

def main():
    t0 = time.time()
    summary = {}
    stages = {"master": stage_master, "views": stage_views, "anim": stage_anim,
              "icons": stage_icons, "terrain": stage_terrain}
    order = ["master", "views", "anim", "icons", "terrain"] \
        if STAGE == "all" else [STAGE]
    for s in order:
        log(f"=== stage {s} ===")
        summary[s] = stages[s]()
    summary["_timing"] = {"wall_s": round(time.time() - t0, 1),
                          "gens": TIMING["gens"], "gen_time_s": TIMING["total_s"],
                          "peak_ram_gb": round(TIMING["peak_ram_gb"], 2),
                          "peak_swap_mb": round(TIMING["peak_swap_mb"], 1)}
    json.dump({k: v for k, v in summary.items() if not isinstance(v, tuple)},
              open(os.path.join(GEN_V2, "campaign_summary.json"), "w"),
              indent=2, default=str)
    log(f"done in {time.time()-t0:.0f}s, gens={TIMING['gens']}, "
        f"peak_ram={TIMING['peak_ram_gb']:.2f}GB")


if __name__ == "__main__":
    main()
