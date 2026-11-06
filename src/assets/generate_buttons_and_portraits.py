"""
generate_buttons_and_portraits.py - High-Fidelity Portrait & Button Generator
for Joseon 5 New Infantry Units (0x7A~0x7E).

Implements:
1. Selection Portraits (68x68) injected into YM/dawn/fnt/portrait_plus.spr (and portrait.spr):
   - Preserves & restores frames 165..174 (10 Custom Units: 유생, 검술 낭인, 조총 낭인, etc.)
   - Injects frames 175..179 (Joseon 5 Units):
       175: 등패수 (0x7A) - Jeonrip + Red plume + Blue dujeonggap + Woven rattan shield (등패) + Hwando
       176: 쌍수도병 (0x7B) - Battle-hardened swordsman + Manggeon + Giant 2H Greatsword (쌍수도)
       177: 장창수 (0x7C) - Pointed Cheomju helmet + Crimson dujeonggap + 15ft Spear with Red Tassel (붉은 영자)
       178: 월도병 (0x7D) - Veteran warrior with beard + Heavy dujeonggap + Crescent Halberd (월도)
       179: 낭선병 (0x7E) - Agile vanguard soldier + Jeonrip + Multi-tier bamboo branch spear (낭선)
   - Composited at 96x96 on authentic Gersang dark-red patterned background disc
     (extract_authentic_gersang_bg_96) with genuine HQ Team face art, downscaled to 68x68,
     sharpened, and masked with authentic circular disc.

2. Production Buttons (34x34) injected into YM/dawn/fnt/button_plus.Spr (and button.spr):
   - Injects frames 289..293 (Joseon 5 Units) with 1px beveled charcoal frame:
       289: 등패수 (Dengpaesu)
       290: 쌍수도병 (Ssangsudo)
       291: 장창수 (Jangchangsu)
       292: 월도병 (Woldo)
       293: 낭선병 (Nangseon)
   - Preserves frames 294..298 (Remaining 5 custom units), maintaining exact total frame count 299.
"""

from __future__ import annotations

import math
import os
import shutil
import stat
import struct
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.assets.constants import (
    IDX_BAMBOO_DARK,
    IDX_BAMBOO_HIGH,
    IDX_BAMBOO_LIGHT,
    IDX_BAMBOO_MID,
    IDX_BLACK_DARK,
    IDX_BLACK_DEEP,
    IDX_BLACK_LIGHT,
    IDX_BLACK_MID,
    IDX_FLESH_BRIGHT,
    IDX_FLESH_DARK,
    IDX_FLESH_HIGH,
    IDX_FLESH_MID,
    IDX_GOLD_BRIGHT,
    IDX_GOLD_DARK,
    IDX_GOLD_HIGH,
    IDX_GOLD_MID,
    IDX_OUTLINE,
    IDX_RED_BRIGHT,
    IDX_RED_DARK,
    IDX_RED_HIGH,
    IDX_RED_MID,
    IDX_STEEL_GLEAM,
    IDX_STEEL_HIGH,
    IDX_STEEL_LOW,
    IDX_STEEL_MID,
    IDX_TEAM_BRIGHT,
    IDX_TEAM_DARK,
    IDX_TEAM_HIGH,
    IDX_TEAM_MID,
    IDX_TRANSPARENT,
    IDX_WHITE_PURE,
    IDX_WHITE_SHADE,
    IDX_WHITE_SOFT,
    IDX_WOOD_DARK,
    IDX_WOOD_DEEP,
    IDX_WOOD_LIGHT,
    IDX_WOOD_MID,
    UNIT_SPECS,
)
from src.assets.spr_encoder import (
    encode_frame_rle_row_aligned,
    inject_frames_into_spr_file,
)
from tools.assets.generate_custom_unit_portraits import (
    apply_circular_mask_68,
    decode_spr_frames,
    extract_authentic_gersang_bg_96,
    load_palette,
)


def quantize_canvas_to_palette(im: Image.Image, pal_colors: np.ndarray) -> np.ndarray:
    """Quantize an RGBA PIL image to 8-bit indexed array using imjin2.pal."""
    arr = np.array(im.convert("RGBA"))
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int32)
    alpha = arr[:, :, 3]
    indexed = np.zeros((h, w), dtype=np.uint8)
    non_zero_pal = pal_colors[1:]  # 1..255 (reserve 0 for transparent)
    for y in range(h):
        for x in range(w):
            if alpha[y, x] < 64:
                indexed[y, x] = 0
            else:
                c = rgb[y, x]
                dists = np.sum((non_zero_pal - c) ** 2, axis=1)
                idx = int(np.argmin(dists)) + 1
                if idx == 0xFE:
                    idx = 244  # Avoid conflicting with RLE escape marker
                indexed[y, x] = idx
    return indexed


def draw_deungpae_shield(im: Image.Image, cx: int, cy: int, r: int):
    """Draw circular woven rattan shield (등패) with concentric wicker rings and central iron boss."""
    draw = ImageDraw.Draw(im)
    for cr in range(r, 0, -1):
        if cr <= 5:
            color = (205, 215, 225, 255) if cr < 3 else (100, 110, 120, 255)
        elif cr in (6, 7):
            color = (215, 155, 30, 255)
        elif cr % 4 == 0:
            color = (75, 48, 22, 255)
        elif cr % 4 == 1:
            color = (165, 118, 55, 255)
        elif cr % 4 == 2:
            color = (195, 148, 80, 255)
        else:
            color = (125, 82, 38, 255)
        draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=color)

    for ang in [0, 45, 90, 135, 180, 225, 270, 315]:
        rad = math.radians(ang)
        x1 = cx + int(7 * math.cos(rad))
        y1 = cy + int(7 * math.sin(rad))
        x2 = cx + int((r - 2) * math.cos(rad))
        y2 = cy + int((r - 2) * math.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(95, 60, 25, 255), width=2)
        draw.line([(x1, y1), (x2, y2)], fill=(225, 170, 40, 255), width=1)

    im.putpixel((cx - 1, cy - 1), (255, 255, 255, 255))
    im.putpixel((cx, cy - 1), (230, 240, 250, 255))


def build_dengpaesu_portrait(bg96_tpl: Image.Image, po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """175: 등패수 - Jeonrip + Red plume + Blue Dujeonggap + Deungpae Shield + Hwando."""
    bg96 = bg96_tpl.copy()
    f43 = po_frames[43]
    f43_rgb = pal_u8[f43]
    rgba = np.array(bg96)

    for y in range(26, 96):
        for x in range(16, 80):
            if f43[y, x] > 0:
                r, g, b = f43_rgb[y, x]
                is_bg = (r >= 35) and (r <= 105) and (g <= 38) and (b <= 20) and ((r - g) >= 20)
                if is_bg and (x < 24 or x > 72 or y < 32):
                    continue
                if y >= 58:
                    lum = int(0.3 * r + 0.5 * g + 0.2 * b)
                    nr = max(5, int(lum * 0.12 + 5))
                    ng = max(15, int(lum * 0.25 + 10))
                    nb = min(160, int(lum * 0.75 + 35))
                    rgba[y, x, :3] = (nr, ng, nb)
                else:
                    rgba[y, x, :3] = (r, g, b)

    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)

    rivet_pts = [
        (32, 64), (44, 63), (56, 64), (68, 66),
        (26, 74), (38, 73), (50, 73), (62, 75), (74, 78),
        (22, 84), (34, 83), (46, 83), (58, 85), (70, 88),
    ]
    for rx, ry in rivet_pts:
        draw.ellipse([rx - 1, ry - 1, rx + 1, ry + 1], fill=(235, 175, 40, 255), outline=(120, 85, 20, 255))
        im96.putpixel((rx, ry), (255, 235, 140, 255))

    draw.line([(38, 56), (46, 68), (58, 58)], fill=(235, 240, 245, 255), width=3)
    draw.line([(39, 56), (46, 66), (57, 58)], fill=(160, 175, 190, 255), width=1)

    for y in range(8, 28):
        ty = (y - 8) / 20.0
        hw = int(14 + 7 * ty)
        for x in range(46 - hw, 46 + hw + 1):
            arch = 8 + int(3.0 * ((x - 46) / float(hw)) ** 2)
            if y < arch:
                continue
            hl = max(0.0, 1.0 - abs((x - (46 - hw * 0.4)) / float(hw)))
            val = int(20 + 24 * hl)
            im96.putpixel((x, y), (val, val + 2, val + 4, 255))

    for y in range(26, 33):
        for x in range(16, 78):
            if ((x - 46) / 30.0) ** 2 + ((y - 29) / 4.0) ** 2 <= 1.0:
                im96.putpixel((x, y), (16, 16, 20, 255))
                if y == 26:
                    im96.putpixel((x, y), (40, 42, 50, 255))

    draw.line([(32, 31), (60, 31)], fill=(225, 230, 238, 255), width=2)

    draw.ellipse([44, 4, 48, 8], fill=(235, 175, 35, 255), outline=(130, 90, 20, 255))
    im96.putpixel((45, 5), (255, 240, 150, 255))
    feather_pts = [(46, 5), (55, 3), (68, 6), (78, 14), (86, 26)]
    for i in range(len(feather_pts) - 1):
        draw.line([feather_pts[i], feather_pts[i + 1]], fill=(215, 30, 20, 255), width=4)
        draw.line([feather_pts[i], feather_pts[i + 1]], fill=(255, 75, 55, 255), width=2)

    draw_deungpae_shield(im96, cx=26, cy=74, r=22)

    draw.line([(64, 76), (82, 54)], fill=(110, 120, 130, 255), width=5)
    draw.line([(64, 76), (82, 54)], fill=(220, 230, 240, 255), width=3)
    draw.line([(65, 75), (82, 53)], fill=(255, 255, 255, 255), width=1)
    draw.ellipse([61, 74, 67, 78], fill=(220, 160, 35, 255))
    draw.line([(63, 78), (60, 88)], fill=(40, 30, 20, 255), width=4)
    draw.ellipse([58, 86, 62, 90], fill=(220, 160, 35, 255))

    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    return apply_circular_mask_68(im68)


def build_ssangsudo_portrait(bg96_tpl: Image.Image, po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """176: 쌍수도병 - Battle-hardened Swordsman + Manggeon + Giant 2H Greatsword."""
    bg96 = bg96_tpl.copy()
    f15 = po_frames[15]
    f15_rgb = pal_u8[f15]
    rgba = np.array(bg96)

    for y in range(16, 96):
        for x in range(14, 82):
            if f15[y, x] > 0:
                r, g, b = f15_rgb[y, x]
                is_bg = (r >= 35) and (r <= 105) and (g <= 38) and (b <= 20) and ((r - g) >= 20)
                if is_bg and (x < 22 or x > 74 or y < 24):
                    continue
                if y >= 64:
                    lum = int(0.3 * r + 0.5 * g + 0.2 * b)
                    nr = max(8, int(lum * 0.15 + 5))
                    ng = max(18, int(lum * 0.25 + 10))
                    nb = min(170, int(lum * 0.75 + 40))
                    rgba[y, x, :3] = (nr, ng, nb)
                else:
                    rgba[y, x, :3] = (r, g, b)

    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)

    draw.line([(28, 28), (66, 28)], fill=(18, 18, 22, 255), width=4)
    draw.ellipse([64, 27, 68, 31], fill=(235, 180, 50, 255))

    draw.line([(24, 62), (68, 86)], fill=(50, 35, 20, 255), width=4)
    for bx, by in [(32, 67), (44, 73), (56, 80)]:
        draw.ellipse([bx - 1, by - 1, bx + 1, by + 1], fill=(235, 175, 40, 255))

    p_start = (18, 96)
    p_end = (82, 6)
    draw.line([(p_start[0] + 1, p_start[1] + 1), (p_end[0] + 1, p_end[1] + 1)], fill=(20, 20, 25, 255), width=6)
    draw.line([p_start, p_end], fill=(100, 115, 128, 255), width=5)
    draw.line([p_start, p_end], fill=(205, 220, 235, 255), width=3)
    draw.line([p_start, p_end], fill=(150, 170, 190, 255), width=1)
    draw.line([(p_start[0] - 1, p_start[1] - 1), (p_end[0] - 1, p_end[1] - 1)], fill=(255, 255, 255, 255), width=1)

    draw.ellipse([17, 86, 27, 94], fill=(225, 165, 35, 255), outline=(130, 85, 20, 255))
    draw.line([(20, 92), (8, 106)], fill=(25, 20, 20, 255), width=4)
    draw.line([(20, 92), (8, 106)], fill=(185, 135, 45, 255), width=2)
    draw.ellipse([5, 102, 11, 108], fill=(225, 165, 35, 255), outline=(130, 85, 20, 255))

    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    return apply_circular_mask_68(im68)


def build_jangchangsu_portrait(bg96_tpl: Image.Image, po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """177: 장창수 - Pointed Cheomju Helmet + Crimson Dujeonggap + 15ft Long Spear with Red Tassel."""
    bg96 = bg96_tpl.copy()
    f11 = po_frames[11]
    f11_rgb = pal_u8[f11]
    rgba = np.array(bg96)

    for y in range(24, 96):
        for x in range(16, 80):
            if f11[y, x] > 0:
                r, g, b = f11_rgb[y, x]
                is_bg = (r >= 35) and (r <= 105) and (g <= 38) and (b <= 20) and ((r - g) >= 20)
                if is_bg and (x < 24 or x > 72 or y < 32):
                    continue
                if y >= 58:
                    lum = int(0.3 * r + 0.5 * g + 0.2 * b)
                    nr = min(210, int(lum * 0.95 + 40))
                    ng = max(5, int(lum * 0.2))
                    nb = max(5, int(lum * 0.15))
                    rgba[y, x, :3] = (nr, ng, nb)
                else:
                    rgba[y, x, :3] = (r, g, b)

    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)

    rivet_pts = [
        (30, 64), (42, 63), (54, 64), (66, 66),
        (24, 74), (36, 73), (48, 73), (60, 75), (72, 78),
        (20, 84), (32, 83), (44, 83), (56, 85), (68, 88),
    ]
    for rx, ry in rivet_pts:
        draw.ellipse([rx - 1, ry - 1, rx + 1, ry + 1], fill=(245, 195, 50, 255), outline=(135, 90, 20, 255))
        im96.putpixel((rx, ry), (255, 245, 175, 255))

    for y in range(7, 28):
        ty = (y - 7) / 21.0
        hw = int(12 + 10 * ty)
        for x in range(46 - hw, 46 + hw + 1):
            arch = 7 + int(2.5 * ((x - 46) / float(hw)) ** 2)
            if y < arch:
                continue
            hl = max(0.0, 1.0 - abs((x - (46 - hw * 0.35)) / float(hw)))
            val_r = int(24 + 28 * hl)
            val_g = int(24 + 28 * hl)
            val_b = int(32 + 36 * hl)
            im96.putpixel((x, y), (val_r, val_g, val_b, 255))

    draw.line([(24, 27), (68, 27)], fill=(225, 175, 45, 255), width=3)
    draw.polygon([(24, 28), (20, 52), (28, 50), (28, 28)], fill=(145, 22, 18, 255))
    draw.polygon([(68, 28), (72, 52), (64, 50), (64, 28)], fill=(145, 22, 18, 255))
    draw.ellipse([23, 38, 25, 40], fill=(235, 185, 45, 255))
    draw.ellipse([67, 38, 69, 40], fill=(235, 185, 45, 255))

    draw.line([(46, 2), (46, 8)], fill=(235, 185, 45, 255), width=2)
    draw.line([(43, 4), (49, 4)], fill=(235, 185, 45, 255), width=2)
    for off_x in range(48, 66, 3):
        draw.line([(46, 7), (off_x, 12 + (off_x - 48))], fill=(210, 25, 20, 255), width=2)

    draw.line([(88, 98), (14, 10)], fill=(95, 68, 35, 255), width=3)
    draw.line([(88, 98), (14, 10)], fill=(165, 118, 60, 255), width=2)
    draw.line([(87, 97), (13, 9)], fill=(215, 160, 90, 255), width=1)

    draw.circle((14, 10), 3, fill=(235, 180, 40, 255))
    draw.polygon([(4, 0), (12, 13), (17, 8)], fill=(220, 230, 245, 255), outline=(105, 120, 135, 255))
    draw.line([(4, 0), (14, 10)], fill=(255, 255, 255, 255), width=1)

    tassel_pts = [
        (14, 12), (18, 20), (22, 32), (28, 40),
        (16, 14), (22, 26), (26, 38),
        (12, 16), (16, 28), (20, 36),
    ]
    for i in range(0, len(tassel_pts) - 1, 2):
        draw.line([tassel_pts[i], tassel_pts[i + 1]], fill=(225, 22, 20, 255), width=2)
        draw.line([tassel_pts[i], tassel_pts[i + 1]], fill=(255, 80, 70, 255), width=1)

    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    return apply_circular_mask_68(im68)


def build_woldo_portrait(bg96_tpl: Image.Image, po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """178: 월도병 - Seasoned Veteran Warrior (Frame 14) + Heavy Dujeonggap + Crescent Halberd Woldo."""
    bg96 = bg96_tpl.copy()
    f14 = po_frames[14]
    f14_rgb = pal_u8[f14]
    rgba = np.array(bg96)

    for y in range(22, 96):
        for x in range(14, 82):
            if f14[y, x] > 0:
                r, g, b = f14_rgb[y, x]
                is_bg = (r >= 35) and (r <= 105) and (g <= 38) and (b <= 20) and ((r - g) >= 20)
                if is_bg and (x < 22 or x > 74 or y < 30):
                    continue
                if y >= 60:
                    lum = int(0.3 * r + 0.5 * g + 0.2 * b)
                    nr = max(6, int(lum * 0.12 + 5))
                    ng = max(16, int(lum * 0.24 + 8))
                    nb = min(165, int(lum * 0.72 + 35))
                    rgba[y, x, :3] = (nr, ng, nb)
                else:
                    rgba[y, x, :3] = (r, g, b)

    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)

    for y in range(8, 28):
        ty = (y - 8) / 20.0
        hw = int(14 + 8 * ty)
        for x in range(46 - hw, 46 + hw + 1):
            arch = 8 + int(3.0 * ((x - 46) / float(hw)) ** 2)
            if y < arch:
                continue
            hl = max(0.0, 1.0 - abs((x - (46 - hw * 0.3)) / float(hw)))
            val = int(22 + 28 * hl)
            im96.putpixel((x, y), (val, val + 2, val + 5, 255))
    draw.line([(24, 27), (68, 27)], fill=(225, 175, 40, 255), width=3)

    rivet_pts = [
        (30, 68), (42, 66), (54, 66), (66, 68),
        (26, 78), (38, 76), (50, 76), (62, 78),
        (22, 88), (34, 86), (46, 86), (58, 88),
    ]
    for rx, ry in rivet_pts:
        draw.ellipse([rx - 1, ry - 1, rx + 1, ry + 1], fill=(240, 185, 45, 255), outline=(125, 80, 20, 255))

    draw.line([(12, 96), (72, 32)], fill=(40, 28, 15, 255), width=4)
    draw.line([(12, 96), (72, 32)], fill=(120, 80, 40, 255), width=2)

    draw.ellipse([68, 26, 78, 38], fill=(225, 170, 35, 255), outline=(130, 85, 20, 255))
    draw.ellipse([70, 29, 75, 34], fill=(175, 40, 30, 255))

    crescent_outer = [(72, 32), (85, 20), (87, 10), (77, 2), (56, 2), (48, 6)]
    crescent_inner = [(48, 6), (62, 12), (68, 22), (72, 32)]
    blade_poly = crescent_outer + crescent_inner[::-1]
    draw.polygon(blade_poly, fill=(210, 222, 238, 255), outline=(90, 105, 120, 255))
    for i in range(len(crescent_outer) - 1):
        draw.line([crescent_outer[i], crescent_outer[i + 1]], fill=(255, 255, 255, 255), width=2)
    draw.polygon([(79, 26), (89, 28), (81, 34)], fill=(175, 190, 205, 255), outline=(90, 105, 120, 255))

    draw.line([(70, 36), (66, 50), (64, 60)], fill=(220, 25, 20, 255), width=2)
    draw.line([(71, 36), (69, 48), (68, 56)], fill=(255, 75, 65, 255), width=1)

    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    return apply_circular_mask_68(im68)


def build_nangseon_portrait(bg96_tpl: Image.Image, po_frames: list[np.ndarray], pal_u8: np.ndarray) -> Image.Image:
    """179: 낭선병 - Agile Vanguard Soldier (Frame 44) + Jeonrip + Multi-Tier Bamboo Branch Spear."""
    bg96 = bg96_tpl.copy()
    f44 = po_frames[44]
    f44_rgb = pal_u8[f44]
    rgba = np.array(bg96)

    for y in range(24, 96):
        for x in range(16, 80):
            if f44[y, x] > 0:
                r, g, b = f44_rgb[y, x]
                is_bg = (r >= 35) and (r <= 105) and (g <= 38) and (b <= 20) and ((r - g) >= 20)
                if is_bg and (x < 24 or x > 72 or y < 32):
                    continue
                if y >= 62:
                    lum = int(0.3 * r + 0.5 * g + 0.2 * b)
                    nr = min(220, int(lum * 0.95 + 25))
                    ng = min(210, int(lum * 0.9 + 20))
                    nb = max(18, int(lum * 0.65 + 10))
                    rgba[y, x, :3] = (nr, ng, nb)
                else:
                    rgba[y, x, :3] = (r, g, b)

    im96 = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(im96)

    for y in range(8, 26):
        ty = (y - 8) / 18.0
        hw = int(14 + 6 * ty)
        for x in range(46 - hw, 46 + hw + 1):
            arch = 8 + int(3.0 * ((x - 46) / float(hw)) ** 2)
            if y < arch:
                continue
            hl = max(0.0, 1.0 - abs((x - (46 - hw * 0.4)) / float(hw)))
            val = int(20 + 24 * hl)
            im96.putpixel((x, y), (val, val + 2, val + 4, 255))
    draw.line([(18, 25), (74, 25)], fill=(18, 18, 22, 255), width=3)
    draw.line([(24, 29), (68, 29)], fill=(240, 245, 250, 255), width=2)

    trunk_start = (14, 96)
    trunk_end = (80, 12)
    draw.line([trunk_start, trunk_end], fill=(22, 60, 28, 255), width=4)
    draw.line([trunk_start, trunk_end], fill=(70, 138, 55, 255), width=2)
    draw.line([(trunk_start[0] - 1, trunk_start[1] - 1), (trunk_end[0] - 1, trunk_end[1] - 1)], fill=(155, 205, 115, 255), width=1)

    nodes = [(24, 84), (36, 68), (48, 52), (60, 36), (72, 20)]
    for nx, ny in nodes:
        draw.line([(nx - 2, ny + 2), (nx + 2, ny - 2)], fill=(38, 90, 32, 255), width=2)
        draw.line([(nx - 1, ny + 1), (nx + 1, ny - 1)], fill=(200, 225, 150, 255), width=1)

    branches = [
        (24, 84, 10, 68, -3, -4),
        (24, 84, 34, 90, 4, 3),
        (36, 68, 20, 52, -4, -4),
        (36, 68, 48, 74, 4, 2),
        (48, 52, 34, 36, -3, -4),
        (48, 52, 62, 58, 4, 2),
        (60, 36, 48, 22, -3, -4),
        (60, 36, 74, 42, 4, 2),
        (72, 20, 60, 8, -3, -3),
        (72, 20, 84, 26, 3, 2),
    ]
    for rx, ry, tx, ty, bdx, bdy in branches:
        draw.line([(rx, ry), (tx, ty)], fill=(40, 108, 42, 255), width=2)
        draw.line([(rx, ry), (tx, ty)], fill=(125, 185, 90, 255), width=1)
        tip_x, tip_y = tx + bdx, ty + bdy
        draw.polygon([(tx, ty), (tip_x, tip_y), (tx - bdy // 2, ty + bdx // 2)], fill=(220, 230, 242, 255), outline=(95, 110, 125, 255))
        im96.putpixel((tip_x, tip_y), (255, 255, 255, 255))

    draw.polygon([(88, 4), (78, 10), (82, 16)], fill=(225, 235, 245, 255), outline=(95, 110, 125, 255))
    draw.line([(88, 4), (80, 12)], fill=(255, 255, 255, 255), width=1)

    im68 = im96.resize((68, 68), Image.Resampling.LANCZOS)
    im68 = ImageEnhance.Sharpness(im68).enhance(1.35)
    return apply_circular_mask_68(im68)


def create_button_34(portrait_68: Image.Image, pal_colors: np.ndarray) -> np.ndarray:
    """Create authentic 34x34 RTS button icon with 1px beveled charcoal frame."""
    im32 = portrait_68.convert("RGBA").resize((32, 32), Image.Resampling.LANCZOS)
    im32 = ImageEnhance.Sharpness(im32).enhance(1.4)
    im32 = ImageEnhance.Contrast(im32).enhance(1.15)

    btn = np.zeros((34, 34, 4), dtype=np.uint8)
    for y in range(34):
        for x in range(34):
            pat = (x * 3 + y * 7) % 4
            v = 24 + pat * 3
            btn[y, x] = (v, v, v, 255)

    for x in range(34):
        btn[0, x] = (75, 75, 80, 255)
        btn[33, x] = (10, 10, 12, 255)
    for y in range(34):
        btn[y, 0] = (75, 75, 80, 255)
        btn[y, 33] = (10, 10, 12, 255)

    btn_im = Image.fromarray(btn, "RGBA")
    btn_im.paste(im32, (1, 1), im32)

    draw = ImageDraw.Draw(btn_im)
    draw.line([(0, 0), (33, 0)], fill=(85, 85, 95, 255))
    draw.line([(0, 0), (0, 33)], fill=(85, 85, 95, 255))
    draw.line([(0, 33), (33, 33)], fill=(15, 15, 18, 255))
    draw.line([(33, 0), (33, 33)], fill=(15, 15, 18, 255))

    indexed = quantize_canvas_to_palette(btn_im, pal_colors)
    for y in range(34):
        for x in range(34):
            if indexed[y, x] == 0:
                indexed[y, x] = 241
    return indexed


def generate_and_inject_all() -> None:
    repo_root = PROJECT_ROOT
    fnt_dir = repo_root / "YM" / "dawn" / "fnt"
    pal_path = repo_root / "YM" / "dawn" / "pal" / "imjin2.pal"

    pal_colors = load_palette(pal_path)
    pal_u8 = pal_colors.astype(np.uint8)

    # 1. Decode portrait_online.spr to extract genuine Gersang background & face frames
    _, _, po_frames = decode_spr_frames(fnt_dir / "portrait_online.spr")
    bg96_tpl = extract_authentic_gersang_bg_96(po_frames, pal_u8)

    print("[*] Generating high-fidelity authentic portraits for 5 Joseon units (frames 175..179)...")
    portraits_68: Dict[int, Image.Image] = {
        175: build_dengpaesu_portrait(bg96_tpl, po_frames, pal_u8),
        176: build_ssangsudo_portrait(bg96_tpl, po_frames, pal_u8),
        177: build_jangchangsu_portrait(bg96_tpl, po_frames, pal_u8),
        178: build_woldo_portrait(bg96_tpl, po_frames, pal_u8),
        179: build_nangseon_portrait(bg96_tpl, po_frames, pal_u8),
    }

    # Encode new portrait frames
    new_portrait_rle: Dict[int, bytes] = {}
    for f_idx, im68 in portraits_68.items():
        indexed = quantize_canvas_to_palette(im68, pal_colors)
        new_portrait_rle[f_idx] = encode_frame_rle_row_aligned(indexed)

    # Inject into portrait_plus.spr and portrait.spr strictly at frames 175..179
    for target_name in ["portrait_plus.spr", "portrait.spr"]:
        spr_path = fnt_dir / target_name
        if spr_path.exists():
            fc = inject_frames_into_spr_file(spr_path, new_portrait_rle, 68, 68)
            print(f"  [OK] Injected frames 175..179 into {target_name} (total frames = {fc})")

    # 2. Restore frames 289..298 (10 Custom Units) and Inject 299..303 (5 Joseon Infantry)
    print("[*] Restoring frames 289..298 and injecting frames 299..303 into button sprites...")
    btn_dir = repo_root / "web_prototype" / "assets" / "ui" / "buttons"
    all_buttons_34: Dict[int, np.ndarray] = {}

    # Restore 10 custom unit buttons (289..298)
    for k_id in range(0x70, 0x7A):
        png_path = btn_dir / f"btn_unit_0x{k_id:02x}.png"
        if not png_path.exists():
            raise FileNotFoundError(f"Missing custom unit button PNG: {png_path}")
        im = Image.open(png_path).convert("RGBA")
        indexed = quantize_canvas_to_palette(im, pal_colors)
        for y in range(34):
            for x in range(34):
                if indexed[y, x] == 0:
                    indexed[y, x] = 241
        btn_f_idx = 289 + (k_id - 0x70)
        all_buttons_34[btn_f_idx] = indexed

    # Generate 5 new Joseon infantry buttons in unused slots [216, 218, 219, 220, 233]
    new_btn_map = {
        216: (175, "0x7a", "dengpaesu"),
        218: (176, "0x7b", "ssangsudo"),
        219: (177, "0x7c", "jangchangsu"),
        220: (178, "0x7d", "woldo"),
        233: (179, "0x7e", "nangseon"),
    }

    for b_idx, (p_idx, hex_id, name_alias) in new_btn_map.items():
        btn_arr = create_button_34(portraits_68[p_idx], pal_colors)
        all_buttons_34[b_idx] = btn_arr

        # Save canonical PNG to web_prototype/assets/ui/buttons/
        btn_rgba = pal_u8[btn_arr]
        # Keep non-transparent alpha 255
        btn_rgba_im = Image.fromarray(btn_rgba, "RGB").convert("RGBA")
        btn_png_path = btn_dir / f"btn_unit_{hex_id}.png"
        btn_rgba_im.save(btn_png_path, "PNG")
        alias_png_path = btn_dir / f"btn_unit_{name_alias}.png"
        btn_rgba_im.save(alias_png_path, "PNG")

    new_button_rle: Dict[int, bytes] = {}
    for f_idx, btn_arr in all_buttons_34.items():
        new_button_rle[f_idx] = encode_frame_rle_row_aligned(btn_arr)

    # Inject into button_plus.Spr and button.spr (frames 216, 218, 219, 220, 233 and 289..298, fixed fc = 299)
    for target_name in ["button_plus.Spr", "button.spr"]:
        spr_path = fnt_dir / target_name
        if spr_path.exists():
            fc = inject_frames_into_spr_file(spr_path, new_button_rle, 34, 34, target_frame_count=299)
            print(f"  [OK] Injected custom buttons into {target_name} (total frames = {fc})")


if __name__ == "__main__":
    generate_and_inject_all()
