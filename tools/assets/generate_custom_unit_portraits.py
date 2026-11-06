#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate and inject 10 authentic Gersang / Imjinrok 2+ circular 68x68 unit portraits
for custom Joseon units 0x70..0x79 into YM/dawn/fnt/portrait_plus.spr (frames 165..174 / 0xA5..0xAE)
and YM/dawn/fnt/portrait.spr.
"""

from __future__ import annotations

import os
import shutil
import stat
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance


UNIT_SPECS = [
    (0x70, 165, "유생", "yusaeng"),
    (0x71, 166, "검술 낭인", "geomsul_nangin"),
    (0x72, 167, "조총 낭인", "jochong_nangin"),
    (0x73, 168, "구미호", "gumiho"),
    (0x74, 169, "조선왕벌", "joseon_wangbeol"),
    (0x75, 170, "조선 호랑이", "joseon_horangi"),
    (0x76, 171, "털가면", "teolgamyeon"),
    (0x77, 172, "설녀", "seolnyeo"),
    (0x78, 173, "조선 도깨비", "joseon_dokkaebi"),
    (0x79, 174, "불가살이", "bulgasari"),
]


def load_palette(pal_path: Path) -> np.ndarray:
    pal_raw = pal_path.read_bytes()
    scale = 4 if max(pal_raw[:768]) <= 63 else 1
    return np.array(
        [(pal_raw[i * 3] * scale, pal_raw[i * 3 + 1] * scale, pal_raw[i * 3 + 2] * scale) for i in range(256)],
        dtype=np.int32,
    )


def decode_spr_frames(spr_path: Path) -> tuple[int, int, list[np.ndarray]]:
    d = spr_path.read_bytes()
    ver, w, h, fc = struct.unpack("<IIII", d[:16])
    offs = struct.unpack(f"<{fc}I", d[0x4C0 : 0x4C0 + 4 * fc])
    frames: list[np.ndarray] = []
    for i in range(fc):
        pos = 0xBF4 + offs[i]
        canvas = np.zeros((h, w), dtype=np.uint8)
        for y in range(h):
            x = 0
            while x < w and pos < len(d):
                b = d[pos]
                pos += 1
                if b == 0xFE:
                    if pos < len(d):
                        run = d[pos]
                        pos += 1
                        x += run
                    else:
                        break
                else:
                    canvas[y, x] = b
                    x += 1
        frames.append(canvas)
    return w, h, frames


def encode_rle(canvas: np.ndarray) -> bytes:
    out = bytearray()
    h, w = canvas.shape
    for y in range(h):
        row = canvas[y]
        x = 0
        while x < w:
            if row[x] == 0:
                run = 0
                while x + run < w and row[x + run] == 0 and run < 255:
                    run += 1
                out.append(0xFE)
                out.append(run)
                x += run
            else:
                val = int(row[x])
                if val == 0xFE:
                    val = 244
                out.append(val)
                x += 1
    return bytes(out)


def apply_circular_mask_68(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA").resize((68, 68), Image.Resampling.LANCZOS)
    px = im.load()
    cx, cy = 33.5, 33.5
    for y in range(68):
        for x in range(68):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist > 33.2:
                px[x, y] = (0, 0, 0, 0)
            else:
                r, g, b, a = px[x, y]
                if a < 128:
                    px[x, y] = (0, 0, 0, 0)
                else:
                    px[x, y] = (r, g, b, 255)
    return im


def downscale_online_portrait(frame_96: np.ndarray, pal_u8: np.ndarray) -> Image.Image:
    rgba = np.zeros((96, 96, 4), dtype=np.uint8)
    mask = frame_96 > 0
    rgba[mask, :3] = pal_u8[frame_96[mask]]
    rgba[mask, 3] = 255
    im96 = Image.fromarray(rgba, "RGBA")
    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    im68 = ImageEnhance.Contrast(im68).enhance(1.08)
    return apply_circular_mask_68(im68)


def extract_authentic_gersang_bg_96(po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """
    Reconstruct a 100% genuine 96x96 Gersang dark-reddish patterned background disc
    by taking the median of background pixels across multiple portrait_online.spr frames.
    """
    candidates = []
    for idx in [1, 8, 10, 12, 18, 20, 24, 26, 46, 47]:
        f = po_frames[idx]
        rgb = pal_u8[f].astype(np.int32)
        candidates.append(rgb)
    stack = np.stack(candidates, axis=0)
    # In portrait_online.spr, the dark red background has R in 40..95, G in 8..32, B in 0..16
    bg_96 = np.zeros((96, 96, 4), dtype=np.uint8)
    cx, cy = 47.5, 47.5
    for y in range(96):
        for x in range(96):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist <= 47.2:
                # Find pixels from candidates that match the dark-red background color family
                px_list = stack[:, y, x, :]
                is_bg = (px_list[:, 0] >= 35) & (px_list[:, 0] <= 105) & (px_list[:, 1] <= 38) & (px_list[:, 2] <= 20)
                if np.any(is_bg):
                    med = np.median(px_list[is_bg], axis=0).astype(np.uint8)
                    bg_96[y, x, :3] = med
                else:
                    # Sample from symmetric/nearby background pixel in Frame 47 (monk has clean top/side background)
                    sy = min(35, y % 32 + 4)
                    sx = min(20, x % 18 + 6)
                    bg_96[y, x, :3] = pal_u8[po_frames[47][sy, sx]]
                bg_96[y, x, 3] = 255
    return Image.fromarray(bg_96, "RGBA")


def build_yusaeng_portrait(po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """
    Build 0x70 유생 (Joseon Confucian Scholar) at 96x96 and downscale to 68x68:
    - Uses HQ Team's hand-painted Joseon face & white headband from portrait_online Frame 46
    - Restores the genuine dark-red Gersang background where the straw brim was
    - Paints a shaded horsehair Confucian Yugeon (유건) cap, white/jade scholar Dopo (도포), and folding fan
    """
    bg96 = extract_authentic_gersang_bg_96(po_frames, pal_u8)
    f46 = po_frames[46]
    rgba = np.array(bg96).copy()
    f46_rgb = pal_u8[f46]

    # Copy the face, headband, neck, and shoulders (y >= 27, or x in 27..68) from Frame 46
    for y in range(26, 96):
        for x in range(0, 96):
            if f46[y, x] > 0:
                r, g, b = int(f46_rgb[y, x, 0]), int(f46_rgb[y, x, 1]), int(f46_rgb[y, x, 2])
                # Skip the straw brim on the upper left/right (y < 36 and outside head width)
                if y < 35 and (x < 24 or x > 69):
                    continue
                # Recolor the brownish-tan vest on the lower torso (y >= 68) into crisp scholar jade-white Dopo
                if y >= 68 and r > g > b and r > 80 and (r - b) > 35:
                    lum = int(0.35 * r + 0.50 * g + 0.15 * b)
                    nr = min(245, int(lum * 1.15 + 35))
                    ng = min(250, int(lum * 1.22 + 42))
                    nb = min(255, int(lum * 1.30 + 52))
                    rgba[y, x, :3] = (nr, ng, nb)
                else:
                    rgba[y, x, :3] = (r, g, b)

    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)

    # Paint a finely shaded tall black horsehair Yugeon (유건) scholar cap above the white headband (y=5..30, x=26..65)
    for y in range(6, 30):
        t_y = (y - 6) / 24.0
        left_x = int(28 - 2 * t_y)
        right_x = int(63 + 2 * t_y)
        for x in range(left_x, right_x + 1):
            if ((x - 47.5) ** 2 + (y - 47.5) ** 2) ** 0.5 > 46.5:
                continue
            # Top contour arch
            arch = 6 + int(2.5 * ((x - 45.5) / 18.0) ** 2)
            if y < arch:
                continue
            # Cylindrical horsehair shading + vertical weave texture
            rel_x = (x - left_x) / max(1, (right_x - left_x))
            highlight = max(0.0, 1.0 - abs(rel_x - 0.32) * 2.8)
            weave = ((x * 3 + y * 5) % 5) - 2
            base_v = int(20 + 28 * highlight + weave * 1.5)
            # Crown tier seam at y == 14 and headband rim at y >= 26
            if y in (14, 15):
                base_v += 14
            elif y >= 26:
                base_v = int(base_v * 0.75)
            if x in (left_x, right_x) or y == arch:
                base_v = 12
            im96.putpixel((x, y), (base_v, base_v + 2, min(255, base_v + 6), 255))

    # Navy scholar collar (깃) trim along the V-neck of the Dopo
    draw.line([(36, 68), (47, 86), (62, 69)], fill=(30, 52, 92, 255), width=4)
    draw.line([(39, 67), (47, 81), (59, 68)], fill=(238, 244, 250, 255), width=2)

    # Scholar's folding fan (부채) held at lower-left with bamboo ribs and Taegeuk emblem
    fan_cx, fan_cy = 26, 88
    for y in range(54, 92):
        for x in range(8, 46):
            if ((x - 47.5) ** 2 + (y - 47.5) ** 2) ** 0.5 > 46.2:
                continue
            dx, dy = x - fan_cx, y - fan_cy
            r_fan = (dx * dx + dy * dy) ** 0.5
            ang = np.degrees(np.arctan2(-dy, dx))
            if 8.0 <= r_fan <= 31.0 and 35.0 <= ang <= 145.0:
                # Paper shading + rib lines every 18 degrees
                rib_dist = abs(((ang - 35.0) % 18.0) - 9.0)
                if r_fan >= 29.5 or ang <= 37.5 or ang >= 142.5:
                    im96.putpixel((x, y), (75, 50, 25, 255))
                elif r_fan <= 13.0:
                    im96.putpixel((x, y), (155, 112, 58, 255))
                elif rib_dist > 7.8:
                    im96.putpixel((x, y), (175, 132, 74, 255))
                else:
                    # Taegeuk circle in the center of the fan
                    tc_dist = ((x - 26) ** 2 + (y - 68) ** 2) ** 0.5
                    if tc_dist <= 5.2:
                        if y < 68 + 1.5 * np.sin((x - 26) * 0.6):
                            im96.putpixel((x, y), (200, 48, 38, 255))
                        else:
                            im96.putpixel((x, y), (38, 85, 165, 255))
                    else:
                        shade = int(238 - (r_fan - 13.0) * 1.2 - abs(ang - 90.0) * 0.25)
                        im96.putpixel((x, y), (shade, shade - 8, shade - 28, 255))

    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.3)
    return apply_circular_mask_68(im68)


def build_wangbeol_portrait(
    po_frames: list[np.ndarray],
    pal_u8: np.ndarray,
    repo_root: Path,
) -> Image.Image:
    """
    Build 0x74 조선왕벌 (Giant Hornet) 68x68 portrait by compositing the official
    true-color 3D-rendered Gersang Hornet (extracted_gersang_assets/kinghornet_n_preview.png
    and hornet_preview.png) onto the authentic 96x96 Gersang dark-red circular background!
    """
    bg96 = extract_authentic_gersang_bg_96(po_frames, pal_u8)
    kh_png = repo_root / "extracted_gersang_assets" / "kinghornet_n_preview.png"
    if kh_png.exists():
        sheet = Image.open(kh_png).convert("RGBA")
        # Cell (col=4, row=1) -> frame 12 (549x412 per cell) is a dramatic 3/4 front-left pose
        cw_cell, ch_cell = 549, 412
        col, row = 1, 1
        cell = sheet.crop((col * cw_cell, row * ch_cell, (col + 1) * cw_cell, (row + 1) * ch_cell))
        arr = np.array(cell)
        r, g, b = arr[:, :, 0].astype(np.int32), arr[:, :, 1].astype(np.int32), arr[:, :, 2].astype(np.int32)
        # Exclude dark background (28,28,28) and neutral-grey ground shadow (r==g==b < 70)
        fg_mask = ((np.abs(r - 28) + np.abs(g - 28) + np.abs(b - 28)) > 18) & ~(
            (np.abs(r - g) <= 3) & (np.abs(g - b) <= 3) & (r < 72)
        )
        ys, xs = np.where(fg_mask)
        if len(ys) > 0:
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            crop = arr[y0:y1, x0:x1].copy()
            crop_fg = fg_mask[y0:y1, x0:x1]
            crop[~crop_fg, 3] = 0
            cr = crop[:, :, 0].astype(np.float32)
            cg = crop[:, :, 1].astype(np.float32)
            cb = crop[:, :, 2].astype(np.float32)
            new_r = np.clip(np.maximum(cr * 1.38, cg * 1.28), 0, 255).astype(np.uint8)
            new_g = np.clip(cg * 1.15, 0, 255).astype(np.uint8)
            new_b = np.clip(cb * 0.88, 0, 255).astype(np.uint8)
            crop[:, :, 0] = new_r
            crop[:, :, 1] = new_g
            crop[:, :, 2] = new_b

            hornet_im = Image.fromarray(crop, "RGBA")
            hornet_im = ImageEnhance.Contrast(hornet_im).enhance(1.30)
            hornet_im = ImageEnhance.Brightness(hornet_im).enhance(1.25)

            ch, cw = crop.shape[:2]
            scale = 88.0 / max(cw, ch)
            nw, nh = int(cw * scale), int(ch * scale)
            hornet_im = hornet_im.resize((nw, nh), Image.Resampling.LANCZOS)
            hornet_im = ImageEnhance.Sharpness(hornet_im).enhance(1.6)

            ox = (96 - nw) // 2
            oy = (96 - nh) // 2
            bg96.alpha_composite(hornet_im, dest=(max(0, ox), max(0, oy)))

    im68 = bg96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.3)
    return apply_circular_mask_68(im68)


def build_seolnyeo_portrait(po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """
    Build 0x77 설녀 (Snow Woman) 68x68 portrait using HQ Team's hand-painted female portrait
    (portrait_online.spr Frame 12) transformed into the Ice/Snow Spirit (설녀):
    - Preserves HQ Team's authentic hand-drawn shading, eyelashes, nose, lips, and robe folds
    - Transforms skin to luminous frost-porcelain, hair to deep icy-navy with glacial cyan highlights,
      eyes to glowing ice-blue, and adds crystalline ice spikes behind her shoulders matching snowwoman_online.spr.
    """
    bg96 = extract_authentic_gersang_bg_96(po_frames, pal_u8)
    f12 = po_frames[12]
    f12_rgb = pal_u8[f12]
    rgba = np.array(bg96).copy()

    # First draw crystalline ice crown spikes radiating behind her head on the 96x96 canvas
    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)
    spikes_96 = [
        [(22, 46), (8, 22), (34, 34)],
        [(30, 34), (20, 8), (42, 24)],
        [(44, 26), (48, 4), (56, 26)],
        [(54, 34), (76, 8), (66, 38)],
        [(62, 46), (88, 22), (72, 52)],
    ]
    for pts in spikes_96:
        draw.polygon(pts, fill=(115, 195, 245, 255), outline=(45, 105, 175, 255))
        draw.line([pts[0], pts[1]], fill=(225, 248, 255, 255), width=2)
    rgba = np.array(im96)

    # Transform Frame 12's character pixels (non-background pixels) into icy Snow Woman palette
    for y in range(96):
        for x in range(96):
            idx = f12[y, x]
            if idx == 0:
                continue
            r, g, b = int(f12_rgb[y, x, 0]), int(f12_rgb[y, x, 1]), int(f12_rgb[y, x, 2])
            # Detect dark-red background pixels of Frame 12: keep our bg96 (which now has the ice spikes!)
            is_bg = (r >= 38) and (r <= 102) and (g <= 36) and (b <= 18) and ((r - g) >= 24)
            if is_bg and (x < 24 or x > 72 or y < 14):
                continue
            if is_bg and y < 48 and (x < 29 or x > 67):
                continue

            lum = 0.299 * r + 0.587 * g + 0.114 * b
            # Skin tones (warm peach/ivory in Frame 12: high R, medium-high G, medium B, inside face/neck x in 28..68, y in 24..88)
            if 28 <= x <= 68 and 22 <= y <= 88 and r > 135 and g > 95 and (r - b) > 25:
                # Luminous icy porcelain skin
                nr = min(252, int(lum * 0.98 + 42))
                ng = min(254, int(lum * 1.03 + 48))
                nb = min(255, int(lum * 1.08 + 58))
                # Soft rose-frost tint on lips (y in 56..62, x in 43..54)
                if 55 <= y <= 63 and 42 <= x <= 54 and (r - g) > 35:
                    nr = min(235, int(lum * 0.95 + 45))
                    ng = max(90, int(lum * 0.65 + 15))
                    nb = min(220, int(lum * 0.95 + 55))
                rgba[y, x, :3] = (nr, ng, nb)
            # Eyes (dark iris at y in 38..46, x in 33..62): give glowing glacial cyan irises
            elif 38 <= y <= 46 and ((34 <= x <= 43) or (53 <= x <= 62)) and lum < 75:
                if lum < 30:
                    rgba[y, x, :3] = (20, 65, 135)
                else:
                    rgba[y, x, :3] = (75, 195, 250)
            # Hair & hair braids (brown/amber in Frame 12): transform to deep glacial navy-blue with ice highlights
            elif y < 78 and (lum < 145):
                nr = max(16, min(175, int(lum * 0.55 + 12)))
                ng = max(32, min(215, int(lum * 0.85 + 26)))
                nb = max(68, min(252, int(lum * 1.25 + 54)))
                rgba[y, x, :3] = (nr, ng, nb)
            # Lower robe / collar & hair ornament: icy white & cyan silk
            else:
                nr = min(250, int(lum * 0.90 + 40))
                ng = min(253, int(lum * 1.02 + 52))
                nb = min(255, int(lum * 1.15 + 68))
                rgba[y, x, :3] = (nr, ng, nb)

    im68 = Image.fromarray(rgba, "RGBA").resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    return apply_circular_mask_68(im68)


def quantize_to_palette(im: Image.Image, pal_colors: np.ndarray) -> np.ndarray:
    arr = np.array(im.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.int32)
    alpha = arr[:, :, 3]
    indexed = np.zeros((68, 68), dtype=np.uint8)
    non_zero_pal = pal_colors[1:]  # indices 1..255 (avoid 0=transparent and 254=0xFE RLE marker)
    for y in range(68):
        for x in range(68):
            if alpha[y, x] < 128:
                indexed[y, x] = 0
            else:
                c = rgb[y, x]
                dists = np.sum((non_zero_pal - c) ** 2, axis=1)
                idx = int(np.argmin(dists)) + 1
                if idx == 0xFE:
                    idx = 244
                indexed[y, x] = idx
    return indexed


def inject_portraits_into_spr(
    spr_path: Path,
    backup_path: Path,
    new_frames: dict[int, bytes],
) -> None:
    if not backup_path.exists():
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(spr_path, backup_path)

    raw = bytearray(backup_path.read_bytes())
    ver, w, h, fc = struct.unpack("<IIII", raw[:16])
    data_size, aw, ah = struct.unpack("<III", raw[0xBC8:0xBD4])
    offs = list(struct.unpack(f"<{fc}I", raw[0x4C0 : 0x4C0 + 4 * fc]))
    szs = list(struct.unpack(f"<{fc}H", raw[0x970 : 0x970 + 2 * fc]))

    target_max_frame = max(new_frames.keys())
    total_frames = max(fc, target_max_frame + 1)

    frame_chunks: list[bytes] = []
    for i in range(fc):
        start = 0xBF4 + offs[i]
        end = (0xBF4 + offs[i + 1]) if (i + 1 < fc) else (0xBF4 + data_size)
        frame_chunks.append(bytes(raw[start:end]))

    blank_rle = b"\xFE\x44" * 68
    while len(frame_chunks) < total_frames:
        frame_chunks.append(blank_rle)

    for f_idx, rle_bytes in new_frames.items():
        frame_chunks[f_idx] = rle_bytes

    new_offs: list[int] = []
    new_szs: list[int] = []
    new_body = bytearray()
    for chunk in frame_chunks:
        new_offs.append(len(new_body))
        new_szs.append(len(chunk))
        new_body.extend(chunk)

    header = bytearray(raw[:0xBF4])
    struct.pack_into("<I", header, 0x00C, total_frames)
    struct.pack_into(f"<{total_frames}I", header, 0x4C0, *new_offs)
    struct.pack_into(f"<{total_frames}H", header, 0x970, *new_szs)
    struct.pack_into("<III", header, 0xBC8, len(new_body), aw, ah)

    out_bytes = bytes(header) + bytes(new_body)
    try:
        os.chmod(spr_path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    spr_path.write_bytes(out_bytes)
    print(f"[OK] Updated {spr_path} (frames={total_frames}, size={len(out_bytes):,} bytes)")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    fnt_dir = repo_root / "YM" / "dawn" / "fnt"
    pal_path = repo_root / "YM" / "dawn" / "pal" / "imjin2.pal"
    backup_dir = repo_root / "YM_backup_original"

    pal_colors = load_palette(pal_path)
    pal_u8 = pal_colors.astype(np.uint8)
    _, _, po_frames = decode_spr_frames(fnt_dir / "portrait_online.spr")

    portraits_rgba: dict[int, Image.Image] = {
        0x70: build_yusaeng_portrait(po_frames, pal_u8),               # 유생
        0x71: downscale_online_portrait(po_frames[4], pal_u8),         # 검술 낭인
        0x72: downscale_online_portrait(po_frames[45], pal_u8),        # 조총 낭인
        0x73: downscale_online_portrait(po_frames[17], pal_u8),        # 구미호
        0x74: build_wangbeol_portrait(po_frames, pal_u8, repo_root),   # 조선왕벌
        0x75: downscale_online_portrait(po_frames[9], pal_u8),         # 조선 호랑이
        0x76: downscale_online_portrait(po_frames[42], pal_u8),        # 털가면
        0x77: build_seolnyeo_portrait(po_frames, pal_u8),              # 설녀
        0x78: downscale_online_portrait(po_frames[3], pal_u8),         # 조선 도깨비
        0x79: downscale_online_portrait(po_frames[5], pal_u8),         # 불가살이
    }

    new_rle_frames: dict[int, bytes] = {}
    quantized_frames: dict[int, np.ndarray] = {}
    out_ui_dir = repo_root / "web_prototype" / "assets" / "ui" / "portraits"
    out_ui_dir.mkdir(parents=True, exist_ok=True)

    for kind_id, frame_idx, kor_name, slug in UNIT_SPECS:
        im = portraits_rgba[kind_id]
        indexed = quantize_to_palette(im, pal_colors)
        quantized_frames[kind_id] = indexed
        new_rle_frames[frame_idx] = encode_rle(indexed)

        q_rgba = np.zeros((68, 68, 4), dtype=np.uint8)
        mask = indexed > 0
        q_rgba[mask, :3] = pal_u8[indexed[mask]]
        q_rgba[mask, 3] = 255
        Image.fromarray(q_rgba, "RGBA").save(out_ui_dir / f"portrait_0x{kind_id:02x}_{slug}.png")

    inject_portraits_into_spr(
        fnt_dir / "portrait_plus.spr",
        backup_dir / "portrait_plus.spr",
        new_rle_frames,
    )
    inject_portraits_into_spr(
        fnt_dir / "portrait.spr",
        backup_dir / "portrait.spr",
        new_rle_frames,
    )

    sheet = Image.new("RGB", (5 * 160, 2 * 140), (24, 22, 20))
    draw = ImageDraw.Draw(sheet)
    for idx, (kind_id, frame_idx, kor_name, slug) in enumerate(UNIT_SPECS):
        indexed = quantized_frames[kind_id]
        q_rgb = np.zeros((68, 68, 3), dtype=np.uint8)
        q_rgb[:, :] = (24, 22, 20)
        mask = indexed > 0
        q_rgb[mask] = pal_u8[indexed[mask]]
        im_scaled = Image.fromarray(q_rgb, "RGB").resize((96, 96), Image.Resampling.NEAREST)
        gx = (idx % 5) * 160 + 32
        gy = (idx // 5) * 140 + 12
        sheet.paste(im_scaled, (gx, gy))
        draw.text((gx - 10, gy + 102), f"0x{kind_id:02X} (Frame {frame_idx}) {slug}", fill=(255, 230, 120))

    artifact_sheet = Path(
        r"C:\Users\bpsco_93p6pse\.gemini\antigravity\brain\012fe533-910e-484f-9444-ed8db88cb5d7\custom_portraits_10_units.png"
    )
    if artifact_sheet.parent.exists():
        sheet.save(artifact_sheet)
        print(f"[OK] Saved contact sheet to {artifact_sheet}")


if __name__ == "__main__":
    main()
