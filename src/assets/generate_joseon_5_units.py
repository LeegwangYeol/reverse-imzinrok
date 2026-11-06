"""
generate_joseon_5_units.py - Authentic Motion-Based Sprite Generator
for Joseon 5 New Infantry Units (0x7A~0x7E) (Imjinrok 2+ Version 9 .spr Format).

Builds genuine 168-frame unit sprites for:
1. YM/dawn/char/dengpaesu.spr   (68x68, 168 frames) - Round rattan shield (등패) + hwando + dujeong-gap
2. YM/dawn/char/ssangsudo.spr   (80x74, 168 frames) - Large two-handed sword + cheollik coat
3. YM/dawn/char/jangchangsu.spr (88x78, 168 frames) - 15-foot spear + red tassel (붉은 영자) + pointed helmet
4. YM/dawn/char/woldo.spr       (78x74, 168 frames) - Crescent blade halberd (월도) + dragon collar
5. YM/dawn/char/nangseon.spr    (88x82, 168 frames) - Multi-tier bamboo branch spear (낭선) + barbs

Animation Frame Structure (168 frames per unit across 5 isometric directions: 0=SW, 1=W, 2=NW, 3=N, 4=S):
- 000..039: Walk / Move (5 directions x 8 frames)
- 040..047: Die / Death (8 frames ending in fallen corpse)
- 048..087: Attack / Strike (5 directions x 8 frames)
- 088..127: Secondary Idle / Stand (5 directions x 8 frames)
- 128..167: Primary Idle / Stand (5 directions x 8 frames)

Base Dot Motion Source:
- Authentic Imjinrok 2+ Joseon infantry motion (YM/dawn/char/swordk.spr, 178 active frames)
- Standing idle frames (128..177, 5 dirs x 10 frames) mapped cleanly to both 88..127 and 128..167
- Trident prongs, wooden shaft, blue tassel, and floating trident shadow systematically removed
- Proportionally upscaled (~1.15x) so soldier stature matches Joseon elite infantry (~40px tall)
- Historical weapons and shields composited with authentic Idle (upright), Move (diagonal carry), and Attack stances
"""

from __future__ import annotations

import math
import os
import stat
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.assets.constants import (
    IDX_BAMBOO_GOLD,
    IDX_BAMBOO_HIGH,
    IDX_BAMBOO_LIGHT,
    IDX_BAMBOO_MID,
    IDX_BAMBOO_VIVID,
    IDX_BLACK_DARK,
    IDX_BLACK_DEEP,
    IDX_BLACK_LIGHT,
    IDX_BLACK_MID,
    IDX_GOLD_BRIGHT,
    IDX_GOLD_DARK,
    IDX_GOLD_HIGH,
    IDX_GOLD_MID,
    IDX_OUTLINE,
    IDX_RED_BRIGHT,
    IDX_RED_DARK,
    IDX_RED_HIGH,
    IDX_RED_MID,
    IDX_STEEL_DARK,
    IDX_STEEL_GLEAM,
    IDX_STEEL_HIGH,
    IDX_STEEL_LOW,
    IDX_STEEL_MID,
    IDX_TEAM_BRIGHT,
    IDX_TEAM_DARK,
    IDX_TEAM_HIGH,
    IDX_TEAM_MID,
    IDX_WOOD_DARK,
    IDX_WOOD_LIGHT,
    IDX_WOOD_MID,
    UNIT_SPECS,
)
from src.assets.spr_encoder import build_spr_v9
from tools.assets.sprite_rle import SpriteDecoder

# Authentic Imjinrok 2+ 5 isometric direction vectors matching swordk.spr (0: SW, 1: W, 2: NW, 3: N, 4: S)
ATK_DIR_VECTORS: List[Tuple[float, float]] = [
    (-0.82, 0.57),   # 0: South-West (Bottom-Left)
    (-0.98, 0.18),   # 1: West (Left)
    (-0.82, -0.57),  # 2: North-West (Top-Left)
    (0.24, -0.97),   # 3: North (Top / Back)
    (-0.32, 0.95),   # 4: South (Bottom / Front)
]

# Diagonal forward-upward carry vectors across chest during Walk / Move (0..39)
MOVE_DIR_VECTORS: List[Tuple[float, float]] = [
    (-0.58, -0.81),  # 0: SW walk -> carried diagonally forward-up-left across chest
    (-0.62, -0.78),  # 1: W walk  -> carried diagonally forward-up-left across chest
    (-0.55, -0.83),  # 2: NW walk -> carried diagonally forward-up-left across chest
    (0.52, -0.85),   # 3: N walk  -> carried diagonally forward-up-right
    (-0.55, -0.83),  # 4: S walk  -> carried diagonally across chest
]

# Natural two-handed ready-guard vectors during Idle / Stand (88..167) so rear hand (waist) and lead hand (chest) are separated both horizontally & vertically
IDLE_DIR_VECTORS: List[Tuple[float, float]] = [
    (-0.38, -0.92),  # 0: SW stand -> two-handed diagonal-upright ready guard
    (-0.40, -0.92),  # 1: W stand  -> two-handed diagonal-upright ready guard
    (-0.36, -0.93),  # 2: NW stand -> two-handed diagonal-upright ready guard
    (0.36, -0.93),   # 3: N stand  -> two-handed diagonal-upright right guard
    (-0.38, -0.92),  # 4: S stand  -> two-handed diagonal-upright ready guard
]

# Hand grip center offsets (dx, dy) relative to canvas center (cx, cy) at true chest/waist level
IDLE_GRIP_OFFSETS: List[Tuple[int, int]] = [
    (-2, -3),  # 0: SW (r_hand at cx+0, cy+1; f_hand at cx-4, cy-7)
    (-3, -3),  # 1: W  (r_hand at cx-1, cy+1; f_hand at cx-5, cy-7)
    (-2, -3),  # 2: NW (r_hand at cx+0, cy+1; f_hand at cx-4, cy-7)
    (2, -3),   # 3: N  (r_hand at cx+0, cy+1; f_hand at cx+4, cy-7)
    (-2, -3),  # 4: S  (r_hand at cx+0, cy+1; f_hand at cx-4, cy-7)
]

MOVE_GRIP_OFFSETS: List[Tuple[int, int]] = [
    (-2, -3),  # 0: SW
    (-2, -3),  # 1: W
    (-2, -3),  # 2: NW
    (2, -3),   # 3: N
    (-2, -3),  # 4: S
]

ATK_GRIP_OFFSETS: List[Tuple[int, int]] = [
    (-1, -3),  # 0: SW (r_hand at cx+2, cy-5; f_hand at cx-5, cy+0)
    (-2, -3),  # 1: W  (r_hand at cx+2, cy-4; f_hand at cx-7, cy-2)
    (-1, -4),  # 2: NW (r_hand at cx+2, cy-2; f_hand at cx-5, cy-7)
    (3, -4),   # 3: N  (r_hand at cx+2, cy+0; f_hand at cx+4, cy-9)
    (-1, -2),  # 4: S  (r_hand at cx+1, cy-6; f_hand at cx-3, cy+3)
]

# Explicit 8-step overhead-to-downward slash trajectories per direction (0: SW, 1: W, 2: NW, 3: N, 4: S)
# Kept close to the front of the torso so the hands and forearms stay anatomically connected to the shoulders.
SWORD_SLASH_KEYFRAMES: List[List[Tuple[int, int, float]]] = [
    # 0: SW (facing down-left: raise high overhead -> cleave diagonally down-left)
    [
        (0, -7, -100.0),   # step 0: raise sword high overhead
        (1, -9, -115.0),   # step 1: peak overhead chamber above head
        (-2, -5, -155.0),  # step 2: begin downward-left slash
        (-3, -2, 160.0),   # step 3: mid cleave across target
        (-3, 1, 118.0),    # step 4: deep downward follow-through (hit!)
        (-2, 2, 105.0),    # step 5: low follow-through hold
        (-1, -1, 140.0),   # step 6: recovery toward guard
        (-2, -4, -125.0),  # step 7: ready stance
    ],
    # 1: W (facing left: raise high overhead -> cleave wide down-left)
    [
        (-1, -7, -95.0),   # step 0: raise sword high overhead
        (0, -9, -110.0),   # step 1: peak overhead chamber
        (-3, -5, -150.0),  # step 2: begin downward slash
        (-4, -2, 172.0),   # step 3: mid cleave through West axis
        (-4, 1, 130.0),    # step 4: deep downward-left follow-through (hit!)
        (-3, 2, 118.0),    # step 5: low follow-through hold
        (-2, -1, 160.0),   # step 6: recovery
        (-2, -4, -120.0),  # step 7: ready stance
    ],
    # 2: NW (facing up-left: raise overhead -> cleave across up-left to down-left)
    [
        (0, -7, -75.0),    # step 0: raise sword high overhead
        (1, -9, -60.0),    # step 1: peak overhead chamber
        (-2, -6, -115.0),  # step 2: sweep across top-left
        (-4, -4, -155.0),  # step 3: mid cleave through NW axis
        (-4, -1, 160.0),   # step 4: follow-through to West-SW (hit!)
        (-3, 0, 148.0),    # step 5: follow-through hold
        (-2, -2, -150.0),  # step 6: recovery
        (-2, -4, -105.0),  # step 7: ready stance
    ],
    # 3: N (facing up/back: cock back overhead-left -> wide horizontal-diagonal cleave across North to NE)
    [
        (-1, -7, -135.0),  # step 0: cock back left shoulder
        (-2, -9, -150.0),  # step 1: peak back-swing
        (0, -8, -105.0),   # step 2: sweep across North
        (3, -6, -55.0),    # step 3: mid cleave through N-NE
        (4, -3, -15.0),    # step 4: full follow-through to East (hit!)
        (4, -2, -5.0),     # step 5: follow-through hold
        (3, -4, -55.0),    # step 6: recovery
        (2, -5, -90.0),    # step 7: ready stance
    ],
    # 4: S (facing down/front: raise above right shoulder on screen-left -> cleave down-front)
    [
        (-2, -7, -110.0),  # step 0: raise high above right shoulder (screen-left)
        (-3, -9, -125.0),  # step 1: peak overhead chamber
        (-4, -4, -165.0),  # step 2: sweep down-left
        (-3, 0, 125.0),    # step 3: mid cleave through South-SW
        (-1, 2, 85.0),     # step 4: deep downward follow-through (hit!)
        (0, 2, 75.0),      # step 5: low follow-through hold
        (-2, 0, 110.0),    # step 6: recovery
        (-3, -3, -105.0),  # step 7: ready stance
    ],
]


def draw_slash_arc(
    canvas: np.ndarray,
    hx: int,
    hy: int,
    ang_start_deg: float,
    ang_end_deg: float,
    radius: int,
) -> None:
    """Draw a curved metallic sword-slash trail (검기/궤적) between ang_start_deg and ang_end_deg."""
    diff = (ang_end_deg - ang_start_deg + 180.0) % 360.0 - 180.0
    steps = max(8, int(abs(diff) // 4))
    for i in range(steps + 1):
        t = i / float(steps)
        a_rad = math.radians(ang_start_deg + diff * t)
        ca, sa = math.cos(a_rad), math.sin(a_rad)
        col_outer = IDX_STEEL_GLEAM if t >= 0.55 else IDX_STEEL_HIGH
        col_inner = IDX_STEEL_MID if t >= 0.45 else IDX_STEEL_LOW
        ox = int(round(hx + radius * ca))
        oy = int(round(hy + radius * sa))
        ix = int(round(hx + (radius - 2) * ca))
        iy = int(round(hy + (radius - 2) * sa))
        set_safe_pixel(canvas, ox, oy, col_outer)
        set_safe_pixel(canvas, ix, iy, col_inner)
        if t >= 0.65:
            mx = int(round(hx + (radius - 1) * ca))
            my = int(round(hy + (radius - 1) * sa))
            set_safe_pixel(canvas, mx, my, IDX_STEEL_GLEAM)


def draw_sword_arm(
    canvas: np.ndarray,
    cx: int,
    cy: int,
    d: int,
    hx: int,
    hy: int,
    sleeve_col: int = IDX_TEAM_HIGH,
    cuff_col: int = IDX_GOLD_MID,
) -> None:
    """Draw 3D-shaded forearm/gauntlet reaching to sword grip (hx, hy) without overwriting 3ds Max chest armor."""
    sh_offsets = [
        (2, -3),   # 0: SW
        (2, -3),   # 1: W
        (2, -4),   # 2: NW
        (3, -4),   # 3: N
        (-2, -3),  # 4: S
    ]
    sx, sy = cx + sh_offsets[d][0], cy + sh_offsets[d][1]
    h, w = canvas.shape
    dist = max(abs(hx - sx), abs(hy - sy))
    if dist > 0:
        for s in range(dist + 1):
            t = s / float(dist)
            px = int(round(sx + (hx - sx) * t))
            py = int(round(sy + (hy - sy) * t))
            if 0 <= py < h and 0 <= px < w and canvas[py, px] == 0:
                canvas[py, px] = sleeve_col if t < 0.75 else cuff_col
            if 0 <= py + 1 < h and 0 <= px < w and canvas[py + 1, px] == 0:
                canvas[py + 1, px] = IDX_STEEL_DARK if t < 0.75 else cuff_col
    set_safe_pixel(canvas, hx, hy, IDX_WOOD_LIGHT)


def get_slash_body_frame_idx(f_idx: int) -> Tuple[int, int, int]:
    """
    For sword/halberd slashing units (등패수, 쌍수도병, 월도병), replace the crouched spear-poke
    frames at Attack step 0, 1, 6, 7 with upright standing/stepping frames so the soldier
    stands tall during the overhead wind-up and cleaves downward with his upper body.
    Returns (source_frame_idx, body_dx, body_dy).
    """
    state, d, step = get_frame_state(f_idx)
    if state != "attack":
        return f_idx, 0, 0
    ux, uy = ATK_DIR_VECTORS[d]
    if step == 0:
        # Upright wind-up
        return 88 + d * 8 + 0, 0, -1
    elif step == 1:
        # High overhead chamber (slight arch back/up)
        return 88 + d * 8 + 1, int(round(-ux)), -1
    elif step == 2:
        # Step into downward slash
        return 0 + d * 8 + 2, int(round(ux)), 0
    elif step in (3, 4, 5):
        # Full forward lunge cleave
        return f_idx, int(round(ux)), 0
    elif step == 6:
        # Step back to guard
        return 0 + d * 8 + 6, 0, 0
    else:
        # Ready stance
        return 88 + d * 8 + 7, 0, 0


def draw_line_indices(canvas: np.ndarray, x0: int, y0: int, x1: int, y1: int, color_idx: int, width: int = 1):
    """Bresenham-style line rasterization using color index with configurable thickness."""
    h, w = canvas.shape
    dist = max(abs(x1 - x0), abs(y1 - y0))
    if dist == 0:
        if 0 <= y0 < h and 0 <= x0 < w:
            canvas[y0, x0] = color_idx
        return
    for s in range(dist + 1):
        t = s / float(dist)
        cx = int(round(x0 + (x1 - x0) * t))
        cy = int(round(y0 + (y1 - y0) * t))
        if width <= 1:
            if 0 <= cy < h and 0 <= cx < w:
                canvas[cy, cx] = color_idx
        else:
            for wy in range(-(width // 2), (width + 1) // 2):
                for wx in range(-(width // 2), (width + 1) // 2):
                    nx, ny = cx + wx, cy + wy
                    if 0 <= ny < h and 0 <= nx < w:
                        canvas[ny, nx] = color_idx


def set_safe_pixel(canvas: np.ndarray, x: int, y: int, color_idx: int):
    """Safely write a single pixel with boundary check."""
    h, w = canvas.shape
    if 0 <= y < h and 0 <= x < w:
        canvas[y, x] = color_idx


def get_frame_state(f_idx: int) -> Tuple[str, int, int]:
    """Return (anim_state, direction 0..4, step 0..7) for frame index 0..167."""
    if f_idx < 40:
        return "move", f_idx // 8, f_idx % 8
    elif f_idx < 48:
        return "die", 0, f_idx - 40
    elif f_idx < 88:
        rel = f_idx - 48
        return "attack", rel // 8, rel % 8
    elif f_idx < 128:
        rel = f_idx - 88
        return "idle", rel // 8, rel % 8
    else:
        rel = f_idx - 128
        return "idle", rel // 8, rel % 8


def clean_base_human(base: np.ndarray, f_idx: int = 0, scale_factor: float = 1.15) -> np.ndarray:
    """
    Extract clean human soldier body from swordk.spr 60x60 frame,
    stripping ONLY the exterior trident prongs, wooden shaft, blue tassel, and floating trident shadow
    while 100% preserving the soldier's white sleeves (소매), white/gray trousers (바지),
    leg wraps (행전), waist sash, hands, dark outlines, boots, and foot shadow.
    Also runs morphological interior hole filling before and after upscaling so 0 transparent holes remain.
    """
    cleaned = base.copy()
    is_die = 40 <= f_idx < 48

    if is_die:
        for y in range(60):
            for x in range(60):
                val = cleaned[y, x]
                if val == 0:
                    continue
                # Strip trident outside fallen corpse (corpse is in x=18..44, y=14..48)
                if y < 14 or x < 17 or x > 45 or y > 49:
                    cleaned[y, x] = 0
                elif val in (246, 247, 248, 249, 250, 251, 252, 253, 255) and (x < 21 or x > 42 or y < 22):
                    cleaned[y, x] = 0
                elif val in (88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 105, 106, 126, 188):
                    if x < 18 or x > 36 or y < 26:
                        cleaned[y, x] = 0
        # Fill any internal pinholes inside the fallen corpse
        for y in range(16, 48):
            for x in range(18, 44):
                if cleaned[y, x] == 0:
                    l, r = int(cleaned[y, x - 1]), int(cleaned[y, x + 1])
                    u, d_v = int(cleaned[y - 1, x]), int(cleaned[y + 1, x])
                    if (l > 0 and r > 0) and (u > 0 or d_v > 0):
                        cleaned[y, x] = l
        return cleaned

    x_min, x_max = 25, 35
    y_min, y_max = 12, 46
    if 48 <= f_idx < 88:
        d = (f_idx - 48) // 8
        step = (f_idx - 48) % 8
        if step in (2, 3, 4, 5) and d in (0, 1, 2):
            x_min = 23

    for y in range(60):
        for x in range(60):
            val = cleaned[y, x]
            if val == 0:
                continue
            # 1. Outside human body silhouette -> 100% old trident prongs, shaft, ribbon, or trident shadow
            if x < x_min or x > x_max or y < y_min or y > y_max:
                cleaned[y, x] = 0
                continue
            # 2. In the hat zone (y=12..19): the hat (전립) is black/dark charcoal with a red plume.
            #    Bright white/steel pixels (249..255) here are trident prongs crossing the hat (e.g. Move W 8..15, Move SW 0..7).
            if 12 <= y <= 19 and val in (249, 250, 251, 252, 253, 255):
                if 27 <= x <= 33 and 14 <= y <= 19:
                    cleaned[y, x] = 242  # Inpaint with black hat color
                else:
                    cleaned[y, x] = 0
                continue
            # 3. Top-left/right corners above shoulders (y=12..17, x<=x_min+1 or x>=x_max-1): strip blue ribbon / shaft tips
            if y <= 17 and (x <= x_min + 1 or x >= x_max - 1):
                if val in (236, 237, 238, 239, 88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105):
                    cleaned[y, x] = 0
                    continue
            # 4. In Attack S (f_idx 80..87), the trident thrusts straight down the center/left:
            #    Inpaint steel prongs on torso (y=23..32) with team blue (237) and on pants (y=33..41) with white/gray (250)
            if 80 <= f_idx < 88:
                if 23 <= y <= 32 and 26 <= x <= 33 and val in (248, 249, 250, 251, 252, 253, 255):
                    cleaned[y, x] = 237
                    continue
                if y >= 42 and x <= 28 and val in (241, 242, 243, 248, 249, 250, 251, 252, 253, 255, 88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105):
                    cleaned[y, x] = 0
                    continue
            # 5. In Move S (f_idx 32..39), inpaint diagonal wooden shaft crossing the trousers (y=33..43, x=27..31)
            if 32 <= f_idx < 40:
                if 33 <= y <= 42 and 27 <= x <= 31 and val in (88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105):
                    cleaned[y, x] = 250
                    continue
                if y >= 43 and x <= 29 and val in (88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105):
                    cleaned[y, x] = 0
                    continue
            # 6. Below the knees (y=42..46): strip any diagonal wooden spear butt or trident shadow sticking out at x<=26 or x>=34
            if y >= 42 and (x <= 26 or x >= 34):
                if val in (88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105, 241, 242, 243, 250, 251, 252, 253, 255):
                    cleaned[y, x] = 0
                    continue
            # 7. Outer 1px vertical boundary (x == x_min or x == x_max) at y=18..41:
            #    Strip detached trident shadow (241..243) or prong tips (252..255)
            if (x == x_min or x == x_max) and 18 <= y <= 41:
                if val in (241, 242, 243, 252, 253, 255):
                    inner_x = x + 1 if x == x_min else x - 1
                    if cleaned[y, inner_x] == 0:
                        cleaned[y, x] = 0
                        continue
            # 8. Where wooden shaft (88..105) crosses blue torso vest (y=22..31) or white trousers (y=34..41),
            #    inpaint with vest blue (237) or trouser white-gray (250) instead of erasing to 0!
            if val in (88, 89, 90, 91, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105):
                if 22 <= y <= 31 and 26 <= x <= 34:
                    cleaned[y, x] = 237
                elif 34 <= y <= 41 and 26 <= x <= 34:
                    cleaned[y, x] = 250

    # Morphological interior hole filling (2 passes) so torso, sleeves, waist, and pants have 0 internal holes
    for _ in range(2):
        fill = cleaned.copy()
        for y in range(14, 46):
            for x in range(x_min + 1, x_max):
                if cleaned[y, x] == 0:
                    l, r = int(cleaned[y, x - 1]), int(cleaned[y, x + 1])
                    u, d_v = int(cleaned[y - 1, x]), int(cleaned[y + 1, x])
                    neighbors = [v for v in (l, r, u, d_v) if v > 0]
                    if len(neighbors) >= 3 or ((l > 0 and r > 0) and (u > 0 or d_v > 0)):
                        if 21 <= y <= 31:
                            fill[y, x] = 237  # Team blue torso
                        elif 32 <= y <= 41:
                            fill[y, x] = 250  # White/gray trousers
                        else:
                            fill[y, x] = neighbors[0]
        cleaned = fill

    if scale_factor <= 1.01:
        return cleaned

    # Nearest-neighbor index-preserving upscale around soldier center (30, 31)
    out = np.zeros((60, 60), dtype=np.uint8)
    for y in range(60):
        sy = int(round((y - 31) / scale_factor + 31))
        if 0 <= sy < 60:
            for x in range(60):
                sx = int(round((x - 30) / scale_factor + 30))
                if 0 <= sx < 60:
                    out[y, x] = cleaned[sy, sx]

    # Post-upscale interior hole fill to guarantee 0 transparent holes inside the scaled body
    for _ in range(2):
        fill = out.copy()
        for y in range(10, 50):
            for x in range(20, 40):
                if out[y, x] == 0:
                    l, r = int(out[y, x - 1]), int(out[y, x + 1])
                    u, d_v = int(out[y - 1, x]), int(out[y + 1, x])
                    neighbors = [v for v in (l, r, u, d_v) if v > 0]
                    if len(neighbors) >= 3 or ((l > 0 and r > 0) and (u > 0 and d_v > 0)):
                        fill[y, x] = l if l > 0 else neighbors[0]
        out = fill
    return out


# Warm skin / face / hand indices in imjin2.pal to preserve on face & hands
FLESH_INDICES = {
    19, 20, 22, 24, 37, 50, 75, 77, 79, 83, 90, 95,
    101, 103, 122, 126, 175, 176, 177,
}
TEAM_INDICES = {IDX_TEAM_DARK, IDX_TEAM_MID, IDX_TEAM_HIGH, IDX_TEAM_BRIGHT}
IDX_VERMILION = 46  # RGB(172, 52, 4) - bright vermilion Dujeonggap highlight

# 12-Step 3ds Max Pre-Rendered Luminance Ramps in imjin2.pal (darkest ambient shadow -> brightest specular peak)
RAMP_CRIMSON = [191, 232, 232, 113, 113, 48, 46, 46, 47, 47, 165, 33]
RAMP_STEEL = [241, 242, 243, 243, 243, 156, 156, 211, 211, 250, 250, 253]
RAMP_DARK_IRON = [241, 242, 208, 243, 244, 65, 156, 246, 248, 211, 250, 253]
RAMP_BRASS = [191, 214, 214, 69, 69, 69, 41, 41, 35, 35, 33, 33]
RAMP_BLUE = [206, 236, 237, 204, 201, 238, 200, 239, 136, 193, 159, 250]

HELMET_SET_GK11 = {17, 22, 23, 24, 66, 98, 99, 107, 108, 109, 110, 111, 112, 170, 188, 191, 212, 224}
RED_SET_GK11 = {46, 47, 48, 113, 114, 115, 116, 117, 118, 119, 120, 163, 164, 165, 166, 232, 233, 234, 235}
BLUE_SET_GK11 = set(range(193, 208)) | set(range(236, 240)) | {136, 137, 138, 139, 159}
YELLOW_LEG_SET_GK11 = {36, 37, 66, 68, 69, 75, 107, 109, 153, 214, 224}

_GK11_3D_CACHE: dict = {}


def _get_gk11_3d_cache() -> Tuple[List[np.ndarray], np.ndarray]:
    """
    Lazy-load and cache the 152 native 3ds Max frames of Kwon Yul on foot
    (generalk11.spr + generalk12.spr + generalk13.spr, 130x110) and the imjin2.pal luminance LUT.
    """
    if "frames" in _GK11_3D_CACHE:
        return _GK11_3D_CACHE["frames"], _GK11_3D_CACHE["lum"]

    from tools.assets.palette import Palette

    pal_path = PROJECT_ROOT / "YM" / "pal" / "imjin2.pal"
    if not pal_path.exists():
        pal_path = next((PROJECT_ROOT / "YM").rglob("imjin2.pal"))
    pal = Palette.from_file(pal_path)
    lum = np.zeros(256, dtype=np.float32)
    for i in range(256):
        r, g, b = pal.colors[i][:3]
        lum[i] = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    gk_frames: List[np.ndarray] = []
    char_dir = PROJECT_ROOT / "YM" / "dawn" / "char"
    for p_name in ("generalk11.spr", "generalk12.spr", "generalk13.spr"):
        dec = SpriteDecoder.from_file(char_dir / p_name)
        for i in range(dec.frame_count):
            gk_frames.append(
                np.frombuffer(dec.decode_frame_raw(i), dtype=np.uint8).reshape((dec.height, dec.width))
            )

    _GK11_3D_CACHE["frames"] = gk_frames
    _GK11_3D_CACHE["lum"] = lum
    return gk_frames, lum


def _pick_ramp(ramp: List[int], l_val: float, boost: float = 0.0) -> int:
    t = max(0.0, min(1.0, (l_val - 0.06) / 0.78 + boost))
    return ramp[int(round(t * (len(ramp) - 1)))]


def _map_168_to_gk11_idx(f_idx: int) -> int:
    """Map standard 168-frame infantry index (0..167) to clean fire-free 3ds Max generalk11..13 frame (0..151)."""
    state, d, step = get_frame_state(f_idx)
    if state == "move":
        return d * 8 + step
    elif state == "die":
        return 40 + step
    elif state == "attack":
        s_step = (step % 2) if d == 4 else step
        if step == 0:
            return 104 + d * 8 + 0
        elif step == 1:
            return 104 + d * 8 + 1
        elif step in (2, 3, 4, 5, 6):
            return 0 + d * 8 + step
        else:
            return 104 + d * 8 + (s_step if d == 4 else 7)
    else:
        s_step = (step % 2) if d == 4 else step
        return 104 + d * 8 + s_step


def apply_joseon_armor(base: np.ndarray, f_idx: int, style: str) -> np.ndarray:
    """
    Build a 100% genuine 3ds Max pre-rendered Joseon armored soldier (60x60) by fusing:
      1. Upper 75% (Conical Cheomju Helmet 첨주 투구, Neck Guard 드림, Shoulder Pauldrons 견철,
         Lamellar/Brigandine Torso 두정갑/경번갑, Team-Blue Surcoat 전복, Waist Sash 전대,
         and Knee-Length Tassets 갑상) from native 3ds Max generalk11..13.spr with 100% of its
         original 1-hand sword stripped and 3ds Max luminance mapped into 5 distinct armor styles:
           - "dujeonggap_blue"     (등패수): Brass-rimmed Conical Helmet + Crimson Pauldrons/Tassets + Team-Blue Studded Dujeong-gap
           - "gyeongbeongap_steel" (쌍수도병): Polished Steel Conical Helmet + Steel Lamellar Scale Mail (철편 경번갑)
           - "dujeonggap_crimson"  (장창수): Conical Helmet with Red Plume + Full Crimson Dujeong-gap (적색 융복 두정갑) with Brass Rivets
           - "gyeongbeongap_heavy" (월도병): Heavy Brass-and-Steel Conical Helmet + Brass & Steel Lamellar Scale Armor (황동·철편 중장 경번갑)
           - "dujeonggap_vanguard" (낭선병): Dark-Iron Conical Helmet & Pauldrons + Crimson & Steel Vanguard Brigandine
      2. Lower 25% (Animated 3ds Max Lower Legs, Armored Shin Greaves 경갑, and War Boots 전투화)
         from swordk.spr (`base`), shaded with 3ds Max steel/dark-iron luminance ramps.
    """
    gk_frames, lum = _get_gk11_3d_cache()
    state, d, step = get_frame_state(f_idx)
    gk_idx = _map_168_to_gk11_idx(f_idx)
    arr = gk_frames[gk_idx].copy()
    gh, gw = arr.shape

    # --- DIE FRAMES (40..47): 3ds Max Fallen Armored Corpse ---
    if state == "die":
        # Strip fallen sword blade & isolated 1px sword wire above corpse
        for y in range(min(60, gh)):
            for x in range(gw):
                v = int(arr[y, x])
                if v != 0 and y < 58 and lum[v] > 0.60:
                    arr[y, x] = 0
        for _ in range(2):
            cl = arr.copy()
            for y in range(1, min(60, gh - 1)):
                for x in range(1, gw - 1):
                    if arr[y, x] != 0:
                        nb = int(np.sum(arr[y - 1 : y + 2, x - 1 : x + 2] > 0)) - 1
                        if nb <= 3:
                            cl[y, x] = 0
            arr = cl

        ys, xs = np.nonzero(arr)
        cx_c = int(round(float(xs.mean()))) if len(xs) else 65
        cy_c = int(round(float(ys.mean()))) if len(ys) else 60
        out_die = np.zeros((60, 60), dtype=np.uint8)

        # Base fallen lower legs/boots from swordk.spr (`base`)
        for ty in range(60):
            for tx in range(60):
                bv = int(base[ty, tx])
                if bv != 0:
                    out_die[ty, tx] = _pick_ramp(
                        RAMP_STEEL if "gyeongbeongap" in style else RAMP_DARK_IRON,
                        float(lum[bv]),
                    )

        # Overlay 3ds Max fallen armored body from generalk11..13.spr
        for ty in range(60):
            sy = cy_c - 30 + ty
            if not (0 <= sy < gh):
                continue
            for tx in range(60):
                sx = cx_c - 30 + tx
                if not (0 <= sx < gw):
                    continue
                v = int(arr[sy, sx])
                if v == 0:
                    continue
                if v == IDX_OUTLINE:
                    out_die[ty, tx] = IDX_OUTLINE
                    continue
                l_v = float(lum[v])
                if v in BLUE_SET_GK11 and style == "dujeonggap_blue":
                    out_die[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                elif style == "dujeonggap_crimson":
                    out_die[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)
                elif style == "dujeonggap_blue":
                    out_die[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.05)
                elif style == "dujeonggap_vanguard":
                    out_die[ty, tx] = _pick_ramp(RAMP_DARK_IRON if (tx % 3 == 0) else RAMP_CRIMSON, l_v, boost=0.06)
                elif style == "gyeongbeongap_steel":
                    out_die[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                elif style == "gyeongbeongap_heavy":
                    out_die[ty, tx] = _pick_ramp(RAMP_BRASS if (ty % 2 == 0) else RAMP_STEEL, l_v, boost=0.10)
        return out_die

    # --- STANDING / MOVING / ATTACKING FRAMES ---
    # 1. Locate 3ds Max Conical Helmet top & horizontal center in generalk11..13.spr
    h_ys, h_xs = [], []
    for y in range(28, min(52, gh)):
        for x in range(54, min(75, gw)):
            if int(arr[y, x]) in HELMET_SET_GK11:
                h_ys.append(y)
                h_xs.append(x)
    hx_c = int(round(float(np.mean(h_xs)))) if h_xs else 64
    hy_top = min(h_ys) if h_ys else 33

    # 2. Strip 100% of Kwon Yul's original 1-hand sword per direction relative to (hx_c, hy_top)
    if d == 0:  # SW
        arr[:, : hx_c - 8] = 0
        arr[hy_top + 19 : hy_top + 32, : hx_c - 7] = 0
    elif d == 1:  # W
        arr[:, : hx_c - 5] = 0
        arr[hy_top + 18 : hy_top + 29, : hx_c - 2] = 0
    elif d == 2:  # NW
        arr[:, : hx_c - 8] = 0
        arr[: hy_top + 22, : hx_c - 6] = 0
    elif d == 3:  # N
        arr[: hy_top + 6, : hx_c - 1] = 0
        arr[hy_top + 24 : hy_top + 35, : hx_c - 8] = 0
        arr[hy_top + 25 :, hx_c + 9 :] = 0
    elif d == 4:  # S
        arr[hy_top + 27 :, : hx_c - 5] = 0
        arr[hy_top + 23 : hy_top + 28, : hx_c - 6] = 0
        for y in range(hy_top + 16, min(hy_top + 33, gh)):
            dy = y - hy_top
            x_diag = hx_c + 2.5 - (dy - 15) * 0.65
            for x in range(max(0, hx_c - 8), min(gw, hx_c + 5)):
                if abs(x - x_diag) <= 1.8 and arr[y, x] != 0:
                    if 16 <= dy <= 21:
                        arr[y, x] = 239 if x <= hx_c else 238
                    elif 22 <= dy <= 26:
                        arr[y, x] = 113 if x <= hx_c else 233
                    else:
                        arr[y, x] = 245

    # Remove yellow leg-wire remnants at y >= hy_top + 31 and prune 1px detached sword splinters
    for y in range(min(hy_top + 31, gh), gh):
        for x in range(gw):
            if int(arr[y, x]) in YELLOW_LEG_SET_GK11:
                arr[y, x] = 0
    for _ in range(2):
        cl = arr.copy()
        for y in range(25, min(95, gh - 1)):
            for x in range(40, min(90, gw - 1)):
                if arr[y, x] != 0:
                    nb = int(np.sum(arr[y - 1 : y + 2, x - 1 : x + 2] > 0)) - 1
                    if nb <= 1:
                        cl[y, x] = 0
        arr = cl

    # 3. Map 3ds Max upper body (hy_top - 2 .. hy_top + 34 -> ty = 2 .. 38) with 3ds Max luminance preservation
    out = np.zeros((60, 60), dtype=np.uint8)
    for ty in range(2, 38):
        sy = hy_top - 4 + ty
        if not (0 <= sy < gh):
            continue
        dy = sy - hy_top
        for tx in range(60):
            sx = hx_c - 30 + tx
            if not (0 <= sx < gw):
                continue
            v = int(arr[sy, sx])
            if v == 0:
                continue
            if v == IDX_OUTLINE:
                out[ty, tx] = IDX_OUTLINE
                continue

            l_v = float(lum[v])
            is_blue = v in BLUE_SET_GK11
            is_red = v in RED_SET_GK11
            is_helmet = (dy <= 8) and (v in HELMET_SET_GK11 or v in RED_SET_GK11)

            # A. 3ds Max Conical War Helmet (첨주 투구: dy <= 8)
            if is_helmet:
                if dy <= 1 and is_red:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.15)
                elif dy in (7, 8):
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.15)
                elif style == "dujeonggap_crimson":
                    if (tx - 30) in (-3, 0, 3) and dy in (3, 5):
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)
                elif style == "dujeonggap_blue":
                    if (tx - 30) in (-3, 0, 3) and dy in (4, 6):
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_DARK_IRON, l_v, boost=0.05)
                elif style == "dujeonggap_vanguard":
                    out[ty, tx] = _pick_ramp(RAMP_DARK_IRON, l_v, boost=0.05)
                elif style == "gyeongbeongap_steel":
                    if tx == 30:
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.15)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.10)
                elif style == "gyeongbeongap_heavy":
                    out[ty, tx] = _pick_ramp(RAMP_BRASS if (tx % 2 == 0) else RAMP_STEEL, l_v, boost=0.12)
                continue

            # B. 3ds Max Face (dy = 8..13 near center) & Neck Flaps (드림)
            if 8 <= dy <= 13:
                if d != 3 and abs(tx - 29) <= 2 and v in FLESH_INDICES:
                    out[ty, tx] = v
                    continue
                if "gyeongbeongap" in style:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.05)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.05)
                continue

            # C. 3ds Max Torso, Pauldrons (견철), Sleeves, & Waist Sash (dy = 14..26)
            if 14 <= dy <= 26:
                if dy in (22, 23, 24) and is_red:
                    if abs(tx - 30) <= 2 and dy == 23:
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                    elif "gyeongbeongap" in style:
                        out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.10)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.10)
                    continue

                if style == "dujeonggap_blue":
                    if is_blue and abs(tx - 30) <= 5:
                        if (dy % 3 == 1) and (tx % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        if (dy % 3 == 0) and (tx % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.06)

                elif style == "dujeonggap_crimson":
                    if is_blue and abs(tx - 30) <= 2 and 16 <= dy <= 21:
                        if dy == 18 and abs(tx - 30) <= 1:
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.25)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        if (dy % 3 == 1) and ((tx + dy) % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)

                elif style == "dujeonggap_vanguard":
                    if is_blue and abs(tx - 30) <= 2 and 16 <= dy <= 21:
                        out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    elif abs(tx - 30) >= 4 or dy <= 16:
                        out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                    else:
                        if (dy % 3 == 0) and (tx % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.05)

                elif style == "gyeongbeongap_steel":
                    if is_blue and abs(tx - 30) <= 2 and 16 <= dy <= 21:
                        out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        plate_mod = -0.07 if (dy % 3 == 0) else (0.06 if ((tx + dy) % 2 == 0) else 0.0)
                        if (dy % 3 == 0) and (tx % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.10)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08 + plate_mod)

                elif style == "gyeongbeongap_heavy":
                    if is_blue and abs(tx - 30) <= 2 and 16 <= dy <= 21:
                        out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        if (dy // 2) % 2 == 0:
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.12)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                continue

            # D. 3ds Max Thigh Tassets / Armored Coat Skirt (갑상: dy >= 27)
            s_dy = dy - 27
            if style == "dujeonggap_crimson":
                if (s_dy % 3 == 1) and ((tx + s_dy) % 3 == 0):
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)
            elif style == "dujeonggap_blue":
                if abs(tx - 30) >= 5:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.06)
                elif (s_dy % 3 == 1) and (tx % 3 == 0):
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.04)
            elif style == "dujeonggap_vanguard":
                if abs(tx - 30) >= 5:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                elif (s_dy % 3 == 1) and (tx % 3 == 0):
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.06)
            elif style == "gyeongbeongap_steel":
                plate_mod = -0.06 if (s_dy % 2 == 1) else 0.06
                out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08 + plate_mod)
            elif style == "gyeongbeongap_heavy":
                if (s_dy // 2) % 2 == 0:
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.12)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)

    # 4. Composite 3ds Max Lower Legs, Armored Shin Greaves (경갑), and War Boots (전투화) from swordk.spr (`base`) at ty = 35..50
    for ty in range(35, 51):
        for tx in range(20, 40):
            if ty >= 37 and out[ty, tx] != 0:
                out[ty, tx] = 0
            bv = int(base[ty, tx])
            if bv == 0:
                continue
            if bv == IDX_OUTLINE:
                if out[ty, tx] == 0:
                    out[ty, tx] = IDX_OUTLINE
                continue
            l_b = float(lum[bv])
            if ty <= 37 and out[ty, tx] != 0:
                continue
            if ty <= 44:
                if ty == 38 and (tx % 2 == 0):
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_b, boost=0.10)
                elif "gyeongbeongap" in style:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_b, boost=-0.04)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_DARK_IRON, l_b, boost=-0.06)
            else:
                out[ty, tx] = _pick_ramp(RAMP_DARK_IRON, l_b * 0.65, boost=-0.10)

    # 4b. Strip Kwon Yul's detached passive side-arm/empty hand and any stray hem pixels outside the 3ds Max
    # Pauldrons (견철), Chest/Waist, Thigh Tassets (갑상), and Lower Legs across the entire 60x60 frame.
    for ty in range(60):
        if ty < 17:
            x_min, x_max = 21, 38
        elif ty <= 22:
            x_min, x_max = 23, 37  # Full broad 3ds Max Shoulder Pauldrons (견철)
        elif ty <= 26:
            x_min, x_max = 25, 35  # 3ds Max Chest & Waist Sash (전대)
        elif ty <= 36:
            x_min, x_max = 24, 36  # Flared 3ds Max Thigh Tassets (갑상)
        else:
            x_min, x_max = 22, 38  # Lower legs & boots (removes stray side pixels at tx > 38)
        for tx in range(60):
            if tx < x_min or tx > x_max:
                out[ty, tx] = 0
        if 17 <= ty <= 36:
            if out[ty, x_min] > 0:
                out[ty, x_min] = IDX_OUTLINE
            if out[ty, x_max] > 0:
                out[ty, x_max] = IDX_OUTLINE

    # 5. Morphological interior pinhole fill (2 passes) so 0 transparent pinholes exist inside the 3ds Max body
    for _ in range(2):
        fill = out.copy()
        for y in range(8, 49):
            for x in range(20, 40):
                if out[y, x] == 0:
                    l, r = int(out[y, x - 1]), int(out[y, x + 1])
                    u, d_v = int(out[y - 1, x]), int(out[y + 1, x])
                    nbs = [v for v in (l, r, u, d_v) if v > 0 and v != IDX_OUTLINE]
                    if (l > 0 and r > 0 and u > 0 and d_v > 0) or len(nbs) >= 3:
                        fill[y, x] = nbs[0] if nbs else l
        out = fill

    return out


def get_arm_ramps(style: str) -> Tuple[List[int], List[int]]:
    """Return (upper_arm_ramp, bracer_ramp) matching each unit's 3ds Max armor style."""
    if style == "dujeonggap_crimson":
        return RAMP_CRIMSON, RAMP_BRASS
    if style == "dujeonggap_blue":
        return RAMP_CRIMSON, RAMP_BRASS
    if style == "dujeonggap_vanguard":
        return RAMP_STEEL, RAMP_CRIMSON
    if style == "gyeongbeongap_steel":
        return RAMP_STEEL, RAMP_DARK_IRON
    if style == "gyeongbeongap_heavy":
        return RAMP_BRASS, RAMP_STEEL
    return RAMP_CRIMSON, RAMP_BRASS


def draw_3d_cyl_limb(
    canvas: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    ramp: List[int],
    radius: float = 1.35,
) -> None:
    """Render a 3D cylindrical shaded limb segment with top-left highlight and bottom-right shadow."""
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)
    if length < 0.5:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    if px + py > 0:
        px, py = -px, -py
    steps = int(math.ceil(length * 2.0)) + 1
    for i in range(steps + 1):
        t = i / max(1, steps)
        cx_p = x0 + dx * t
        cy_p = y0 + dy * t
        for off in (-1.1, -0.55, 0.0, 0.55, 1.1):
            if abs(off) > radius:
                continue
            ix = int(round(cx_p + off * px))
            iy = int(round(cy_p + off * py))
            if 0 <= iy < canvas.shape[0] and 0 <= ix < canvas.shape[1]:
                lit = 0.76 - 0.34 * (off / radius)
                canvas[iy, ix] = _pick_ramp(ramp, lit)


def draw_3d_arm_via_elbow(
    canvas: np.ndarray,
    sx: int,
    sy: int,
    ex: int,
    ey: int,
    hx: int,
    hy: int,
    upper_ramp: List[int],
    bracer_ramp: List[int],
) -> None:
    """Render an articulated 3D upper arm (pauldron -> elbow) and forearm bracer (elbow -> hand)."""
    draw_3d_cyl_limb(canvas, sx, sy, ex, ey, upper_ramp, radius=1.40)
    draw_3d_cyl_limb(canvas, ex, ey, hx, hy, bracer_ramp, radius=1.25)


def draw_two_handed_arms(
    canvas: np.ndarray,
    cx: int,
    cy: int,
    hand1_xy: Tuple[int, int],
    hand2_xy: Tuple[int, int],
    style: str,
    d: int = 0,
) -> None:
    """
    Direction-aware 3D articulated arms connecting the anatomical Left & Right Shoulders
    via natural elbows to the two weapon grip points (hand1_xy, hand2_xy).
    """
    upper_ramp, bracer_ramp = get_arm_ramps(style)
    # Direction-specific shoulder anchors so side profiles (d=1 W, d=2 NW) never protrude behind the back
    shoulder_pairs = [
        ((cx - 4, cy - 8), (cx + 3, cy - 8), -1, 1),   # 0: SW
        ((cx - 3, cy - 8), (cx + 1, cy - 8), -1, 0),   # 1: W (side profile facing left)
        ((cx - 4, cy - 8), (cx + 2, cy - 8), -1, 0),   # 2: NW (three-quarter back-left)
        ((cx - 4, cy - 8), (cx + 4, cy - 8), -1, 1),   # 3: N
        ((cx - 4, cy - 8), (cx + 4, cy - 8), -1, 1),   # 4: S
    ]
    sh_l, sh_r, bend_l, bend_r = shoulder_pairs[d]

    if hand1_xy[0] <= hand2_xy[0]:
        lh, rh = hand1_xy, hand2_xy
    else:
        lh, rh = hand2_xy, hand1_xy

    el_l = ((sh_l[0] + lh[0]) // 2 + bend_l, (sh_l[1] + lh[1]) // 2 + 1)
    el_r = ((sh_r[0] + rh[0]) // 2 + bend_r, (sh_r[1] + rh[1]) // 2 + 1)

    draw_3d_arm_via_elbow(canvas, sh_l[0], sh_l[1], el_l[0], el_l[1], lh[0], lh[1], upper_ramp, bracer_ramp)
    draw_3d_arm_via_elbow(canvas, sh_r[0], sh_r[1], el_r[0], el_r[1], rh[0], rh[1], upper_ramp, bracer_ramp)


def draw_hand_wrapping_weapon(
    canvas: np.ndarray,
    gx: int,
    gy: int,
    ux: float,
    uy: float,
    cuff_col: int = IDX_GOLD_MID,
) -> None:
    """
    Draw a crisp dark-outlined 3D fist/gauntlet directly ON TOP OF the spear shaft or sword hilt at (gx, gy)
    so the fingers visibly clasp and wrap around the weapon shaft against any armor background.
    """
    px, py = -uy, ux
    if px + py > 0:
        px, py = -px, -py  # Ensure (px, py) points toward top-left light source

    # 1. Subtle 1px dark contour on the outer sides of the fist so the hand never merges into chest armor
    set_safe_pixel(canvas, int(round(gx + 1.5 * px)), int(round(gy + 1.5 * py)), IDX_OUTLINE)
    set_safe_pixel(canvas, int(round(gx - 1.5 * px)), int(round(gy - 1.5 * py)), IDX_OUTLINE)

    # 2. Armored wrist cuff slightly behind the knuckle
    wx = int(round(gx - 1.3 * ux))
    wy = int(round(gy - 1.3 * uy))
    set_safe_pixel(canvas, wx, wy, cuff_col)

    # 3. 3D shaded knuckles & fingers wrapping directly across the shaft at (gx, gy)
    set_safe_pixel(canvas, gx, gy, 175)  # Warm lit flesh mid-tone directly ON TOP OF shaft
    set_safe_pixel(canvas, int(round(gx + 0.8 * ux)), int(round(gy + 0.8 * uy)), 176)  # Bright leading knuckle
    set_safe_pixel(canvas, int(round(gx + 0.9 * px)), int(round(gy + 0.9 * py)), 176)  # Lit thumb wrap (top-left)
    set_safe_pixel(canvas, int(round(gx - 0.9 * px)), int(round(gy - 0.9 * py)), 126)  # Shaded finger wrap (bottom-right)


def seal_canvas_pinholes(canvas: np.ndarray, ox: int, oy: int) -> None:
    """Seal any 4-connected interior transparent pinholes created where arms/weapons meet the torso."""
    for _ in range(2):
        for y in range(oy + 12, oy + 46):
            for x in range(ox + 22, ox + 38):
                if canvas[y, x] == 0:
                    l, r = int(canvas[y, x - 1]), int(canvas[y, x + 1])
                    u, d_v = int(canvas[y - 1, x]), int(canvas[y + 1, x])
                    if l > 0 and r > 0 and u > 0 and d_v > 0:
                        nbs = [v for v in (l, r, u, d_v) if v != IDX_OUTLINE]
                        canvas[y, x] = nbs[0] if nbs else l


def load_base_frames() -> List[bytes]:
    """
    Load and decode all 178 active frames from YM/dawn/char/swordk.spr,
    and return a 168-frame list where:
      - 0..39   (Move):   swordk.spr[0..39]
      - 40..47  (Die):    swordk.spr[40..47]
      - 48..87  (Attack): swordk.spr[48..87]
      - 88..127 (Idle1):  swordk.spr[128 + d*10 + step] (standing upright, 5 dirs x 8 frames)
      - 128..167 (Idle0): swordk.spr[128 + d*10 + step] (standing upright, 5 dirs x 8 frames)
    """
    base_spr_path = PROJECT_ROOT / "YM" / "dawn" / "char" / "swordk.spr"
    if not base_spr_path.exists():
        raise FileNotFoundError(f"Base soldier sprite not found: {base_spr_path}")
    dec = SpriteDecoder.from_file(base_spr_path)
    raw_all = [dec.decode_frame_raw(i) for i in range(min(dec.frame_count, 178))]

    mapped: List[bytes] = []
    for f_idx in range(168):
        if f_idx < 88:
            mapped.append(raw_all[f_idx])
        elif f_idx < 128:
            d = (f_idx - 88) // 8
            step = (f_idx - 88) % 8
            mapped.append(raw_all[128 + d * 10 + step])
        else:
            d = (f_idx - 128) // 8
            step = (f_idx - 128) % 8
            mapped.append(raw_all[128 + d * 10 + step])
    return mapped


def get_polearm_pose(
    state: str, d: int, step: int, cx: int, cy: int, rear_len: int, front_len: int
) -> Tuple[int, int, int, int, int, int, float, float]:
    """
    Compute (butt_x, butt_y, grip_x, grip_y, tip_x, tip_y, ux, uy) for a two-handed polearm
    so that it is held upright in Idle, diagonally across the chest in Move, and thrust/swung in Attack.
    """
    if state == "idle":
        gx_off, gy_off = IDLE_GRIP_OFFSETS[d]
        ux, uy = IDLE_DIR_VECTORS[d]
        breathe = 1 if step in (3, 4, 5) else 0
        gx, gy = cx + gx_off, cy + gy_off + breathe
    elif state == "move":
        gx_off, gy_off = MOVE_GRIP_OFFSETS[d]
        ux, uy = MOVE_DIR_VECTORS[d]
        bob = -1 if step in (1, 2, 5, 6) else 0
        gx, gy = cx + gx_off, cy + gy_off + bob
    else:
        gx_off, gy_off = ATK_GRIP_OFFSETS[d]
        ux, uy = ATK_DIR_VECTORS[d]
        gx, gy = cx + gx_off, cy + gy_off

    butt_x = int(round(gx - rear_len * ux))
    butt_y = int(round(gy - rear_len * uy))
    tip_x = int(round(gx + front_len * ux))
    tip_y = int(round(gy + front_len * uy))
    return butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy


# ---------------------------------------------------------------------------
# Unit Sprite Frame Builders
# ---------------------------------------------------------------------------

def build_dengpaesu_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    68x68, 168 frames for 등패수 (0x7A):
    - Blue dujeonggap with golden rivets
    - Angled isometric oval rattan shield (등패) on the shield arm with iron boss and dark rim
    - Crisp steel Hwando blade held in right-hand guard in Idle/Move and slashing forward in Attack,
      with articulated 3D sword arm and visible hand gripping the Hwando hilt.
    """
    spec = UNIT_SPECS["dengpaesu"]
    tw, th = spec["width"], spec["height"]  # 68x68
    bw, bh = 60, 60
    ox, oy = (tw - bw) // 2, (th - bh) // 2  # 4, 4
    cx, cy = tw // 2, th // 2 - 1
    frames = []
    upper_ramp, bracer_ramp = get_arm_ramps("dujeonggap_blue")

    for f_idx in range(168):
        c = np.zeros((th, tw), dtype=np.uint8)
        state, d, step = get_frame_state(f_idx)
        src_idx, b_dx, b_dy = get_slash_body_frame_idx(f_idx)
        base = clean_base_human(np.frombuffer(base_frames[src_idx], dtype=np.uint8).reshape((bh, bw)), src_idx)
        base = apply_joseon_armor(base, src_idx, style="dujeonggap_blue")

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy + b_dy, bx + ox + b_dx
                if not (0 <= ty < th and 0 <= tx < tw):
                    continue
                c[ty, tx] = val

        if state == "die":
            # Fallen rattan shield and hwando beside corpse
            sx, sy = cx - 8 - step, cy + 10 + step // 2
            rx, ry = 6.0, 4.5
            draw_line_indices(c, cx + 2, cy + 8, cx + 14, cy + 12, IDX_STEEL_GLEAM, width=1)
            set_safe_pixel(c, cx + 2, cy + 8, IDX_GOLD_BRIGHT)
        else:
            # Shield held on the shield forearm (screen-left for d=0..3, screen-right for d=4)
            shield_pos = [
                (cx - 6, cy - 1, 5.5, 6.8),  # 0: SW
                (cx - 6, cy - 2, 5.0, 6.8),  # 1: W
                (cx - 5, cy - 3, 5.0, 6.5),  # 2: NW
                (cx - 5, cy - 4, 4.5, 6.0),  # 3: N
                (cx + 6, cy - 1, 5.5, 6.8),  # 4: S
            ]
            sx, sy, rx, ry = shield_pos[d]
            if state == "move" and step in (1, 2, 5, 6):
                sy -= 1
            elif state == "attack":
                brace_dx = 2 if d == 4 else -2
                brace_dy = 1 if step in (2, 3, 4, 5) else 0
                sx += brace_dx
                sy += brace_dy

            # Connect shield shoulder to shield center via 3D arm
            sh_shield_x = cx + b_dx + (5 if d == 4 else -5)
            sh_shield_y = cy + b_dy - 9
            draw_3d_cyl_limb(c, sh_shield_x, sh_shield_y, int(sx), int(sy), upper_ramp, radius=1.45)

        # 1. Render 3D convex hemisphere normal-shaded woven rattan shield (등패) FIRST
        irx, iry = int(math.ceil(rx)), int(math.ceil(ry))
        for dy_s in range(-iry, iry + 1):
            for dx_s in range(-irx, irx + 1):
                nx_s, ny_s = dx_s / rx, dy_s / ry
                nd = math.sqrt(nx_s * nx_s + ny_s * ny_s)
                if nd <= 1.0:
                    px, py = int(sx + dx_s), int(sy + dy_s)
                    if 0 <= py < th and 0 <= px < tw:
                        nz_s = math.sqrt(max(0.0, 1.0 - nd * nd))
                        s_lit = max(0.0, min(1.0, (-0.58 * nx_s - 0.52 * ny_s + 0.63 * nz_s) * 0.90 + 0.12))
                        if nd >= 0.85:
                            c[py, px] = _pick_ramp(RAMP_BRASS, s_lit * 0.62, boost=-0.05) if s_lit > 0.45 else IDX_OUTLINE
                        elif nd <= 0.28:
                            c[py, px] = 255 if (dx_s <= 0 and dy_s <= 0 and nd <= 0.16) else _pick_ramp(RAMP_BRASS, s_lit, boost=0.25)
                        elif nd <= 0.38:
                            c[py, px] = _pick_ramp(RAMP_DARK_IRON, s_lit * 0.55)
                        else:
                            ring_wave = 0.08 if (int(round(nd * 7.5)) % 2 == 0) else -0.06
                            weave_mod = 0.04 if ((dx_s + dy_s) % 2 == 0) else -0.04
                            c[py, px] = _pick_ramp(RAMP_BRASS, s_lit, boost=ring_wave + weave_mod)

        # 2. Render Hwando sword (환도) in sword hand ON TOP, with articulated 3D sword arm and clasping hand
        if state != "die":
            sh_sword_x = cx + b_dx + (-4 if d == 4 else (2 if d in (1, 2) else 4))
            sh_sword_y = cy + b_dy - 8

            if state == "attack":
                h_dx, h_dy, ang_deg = SWORD_SLASH_KEYFRAMES[d][step]
                # Keep one-handed Hwando hilt on the sword-hand side so it never crosses over the shield
                if d in (0, 1, 2):
                    hx = cx + b_dx + max(0, h_dx + 3)
                else:
                    hx = cx + b_dx + h_dx
                hy = cy + b_dy + h_dy
                ang = math.radians(ang_deg)
                cos_a, sin_a = math.cos(ang), math.sin(ang)
                px_a, py_a = -sin_a, cos_a
                blen = 17  # Constant 17px Hwando blade
                tx = int(round(hx + blen * cos_a))
                ty = int(round(hy + blen * sin_a))
                butt_x = int(round(hx - 4 * cos_a))
                butt_y = int(round(hy - 4 * sin_a))

                if step in (2, 3, 4):
                    prev_ang = SWORD_SLASH_KEYFRAMES[d][step - 1][2]
                    draw_slash_arc(c, hx, hy, prev_ang, ang_deg, radius=blen - 1)

                el_x = (sh_sword_x + hx) // 2 + (-1 if d == 4 else (0 if d in (1, 2) else 1))
                el_y = (sh_sword_y + hy) // 2 + 1
                draw_3d_arm_via_elbow(c, sh_sword_x, sh_sword_y, el_x, el_y, hx, hy, upper_ramp, bracer_ramp)

                # Hwando hilt + brass pommel + disc guard (코등이)
                draw_line_indices(c, butt_x, butt_y, hx, hy, IDX_WOOD_DARK, width=1)
                set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
                mid_x = int(round(hx + (blen * 0.55) * cos_a + 1.0 * px_a))
                mid_y = int(round(hy + (blen * 0.55) * sin_a + 1.0 * py_a))
                draw_line_indices(c, hx, hy, tx, ty, IDX_STEEL_MID, width=2)
                draw_line_indices(c, hx, hy, mid_x, mid_y, IDX_STEEL_GLEAM, width=1)
                draw_line_indices(c, mid_x, mid_y, tx, ty, IDX_STEEL_GLEAM, width=1)
                # 3D Hand wrapping directly around the Hwando hilt + brass disc guard
                draw_hand_wrapping_weapon(c, int(round(hx - 1.5 * cos_a)), int(round(hy - 1.5 * sin_a)), cos_a, sin_a)
                set_safe_pixel(c, hx, hy, IDX_GOLD_BRIGHT)
                set_safe_pixel(c, tx, ty, IDX_STEEL_GLEAM)
            else:
                # Held cleanly in poised sword-hand guard on the sword side (screen-right for d=0..3, screen-left for d=4)
                bob = -1 if (state == "move" and step in (1, 2, 5, 6)) else 0
                sword_ready = [
                    (cx + 5, cy - 3 + bob, cx + 9, cy - 17 + bob),   # 0: SW
                    (cx + 4, cy - 4 + bob, cx + 7, cy - 18 + bob),   # 1: W
                    (cx + 5, cy - 4 + bob, cx + 8, cy - 18 + bob),   # 2: NW
                    (cx + 5, cy - 5 + bob, cx + 8, cy - 19 + bob),   # 3: N
                    (cx - 5, cy - 3 + bob, cx - 9, cy - 17 + bob),   # 4: S
                ]
                hx, hy, tx, ty = sword_ready[d]
                dx_s, dy_s = tx - hx, ty - hy
                slen = max(1.0, math.hypot(dx_s, dy_s))
                ux_s, uy_s = dx_s / slen, dy_s / slen
                butt_x = int(round(hx - 3 * ux_s))
                butt_y = int(round(hy - 3 * uy_s))

                el_x = (sh_sword_x + hx) // 2 + (-1 if d == 4 else (0 if d in (1, 2) else 1))
                el_y = (sh_sword_y + hy) // 2 + 1
                draw_3d_arm_via_elbow(c, sh_sword_x, sh_sword_y, el_x, el_y, hx, hy, upper_ramp, bracer_ramp)

                draw_line_indices(c, butt_x, butt_y, hx, hy, IDX_WOOD_DARK, width=1)
                set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
                draw_line_indices(c, hx, hy, tx, ty, IDX_STEEL_MID, width=2)
                draw_line_indices(c, (hx + tx) // 2, (hy + ty) // 2, tx, ty, IDX_STEEL_GLEAM, width=1)
                draw_hand_wrapping_weapon(c, int(round(hx - 1.0 * ux_s)), int(round(hy - 1.0 * uy_s)), ux_s, uy_s)
                set_safe_pixel(c, hx, hy, IDX_GOLD_BRIGHT)
                set_safe_pixel(c, tx, ty, IDX_STEEL_GLEAM)

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_ssangsudo_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    80x74, 168 frames for 쌍수도병 (0x7B):
    - Solid Team-Blue & Steel Gyeongbeongap lamellar armor
    - Two-Handed Greatsword (쌍수도) held with BOTH hands on the 9px long hilt in Idle/Move,
      and executing a massive overhead-to-ground two-handed cleave during Attack.
    """
    spec = UNIT_SPECS["ssangsudo"]
    tw, th = spec["width"], spec["height"]  # 80x74
    bw, bh = 60, 60
    ox, oy = (tw - bw) // 2, (th - bh) // 2  # 10, 7
    cx, cy = tw // 2, th // 2 - 1
    frames = []

    for f_idx in range(168):
        c = np.zeros((th, tw), dtype=np.uint8)
        state, d, step = get_frame_state(f_idx)
        src_idx, b_dx, b_dy = get_slash_body_frame_idx(f_idx)
        base = clean_base_human(np.frombuffer(base_frames[src_idx], dtype=np.uint8).reshape((bh, bw)), src_idx)
        base = apply_joseon_armor(base, src_idx, style="gyeongbeongap_steel")

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy + b_dy, bx + ox + b_dx
                if not (0 <= ty < th and 0 <= tx < tw):
                    continue
                c[ty, tx] = val

        if state == "die":
            draw_line_indices(c, cx - 17, cy + 12, cx - 6, cy + 12, IDX_WOOD_DARK, width=1)
            set_safe_pixel(c, cx - 17, cy + 12, IDX_GOLD_BRIGHT)
            set_safe_pixel(c, cx - 6, cy + 12, IDX_GOLD_BRIGHT)
            draw_line_indices(c, cx - 5, cy + 12, cx + 20, cy + 12, IDX_STEEL_GLEAM, width=2)
        elif state == "attack":
            # Full two-handed overhead-to-downward greatsword cleave (1.2x scaled 양손 대도 내려베기)
            h_dx, h_dy, ang_deg = SWORD_SLASH_KEYFRAMES[d][step]
            gx, gy = cx + b_dx + h_dx, cy + b_dy + (h_dy // 2 if step in (0, 1) else h_dy)
            ang = math.radians(ang_deg)
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            px_a, py_a = -sin_a, cos_a
            butt_x = int(round(gx - 9 * cos_a))
            butt_y = int(round(gy - 9 * sin_a))
            blen = 29  # 1.2x scaled greatsword blade (24 -> 29px, total 38px with 9px two-handed hilt)
            tip_x = int(round(gx + blen * cos_a))
            tip_y = int(round(gy + blen * sin_a))

            f_hand = ( int(round(gx - 2 * cos_a)), int(round(gy - 2 * sin_a)) )
            r_hand = ( int(round(gx - 6 * cos_a)), int(round(gy - 6 * sin_a)) )

            if step in (2, 3, 4):
                prev_ang = SWORD_SLASH_KEYFRAMES[d][step - 1][2]
                draw_slash_arc(c, gx, gy, prev_ang, ang_deg, radius=blen - 1)
                draw_slash_arc(c, gx, gy, prev_ang, ang_deg, radius=blen - 4)

            # Both 3D arms connecting shoulders to the two grip positions on the greatsword hilt
            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "gyeongbeongap_steel", d=d)

            # Long two-handed wrapped hilt + brass ring pommel
            draw_line_indices(c, butt_x, butt_y, gx, gy, IDX_WOOD_DARK, width=2)
            set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
            # Heavy steel spine + broad gleaming cutting belly
            belly_x = int(round(gx + (blen * 0.65) * cos_a + 1.8 * px_a))
            belly_y = int(round(gy + (blen * 0.65) * sin_a + 1.8 * py_a))
            draw_line_indices(c, gx, gy, tip_x, tip_y, IDX_STEEL_MID, width=2)
            draw_line_indices(c, int(round(gx + px_a)), int(round(gy + py_a)), belly_x, belly_y, IDX_STEEL_GLEAM, width=1)
            draw_line_indices(c, belly_x, belly_y, tip_x, tip_y, IDX_STEEL_GLEAM, width=1)
            # Prominent brass crossguard (코등이)
            draw_line_indices(
                c,
                int(round(gx - 3 * px_a)),
                int(round(gy - 3 * py_a)),
                int(round(gx + 3 * px_a)),
                int(round(gy + 3 * py_a)),
                IDX_GOLD_BRIGHT,
                width=1,
            )
            # Both hands visibly clasping the long two-handed hilt ON TOP OF the hilt
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], cos_a, sin_a, cuff_col=IDX_RED_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], cos_a, sin_a, cuff_col=IDX_RED_HIGH)
            set_safe_pixel(c, tip_x, tip_y, IDX_STEEL_GLEAM)
        else:
            # High two-handed shoulder/chest guard stance (1.2x scaled: rear_len=9, front_len=27 -> 36px total)
            butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy = get_polearm_pose(
                state, d, step, cx, cy, rear_len=9, front_len=27
            )
            px_a, py_a = -uy, ux
            f_hand = (int(round(gx - 1.5 * ux)), int(round(gy - 1.5 * uy)))
            r_hand = (int(round(gx - 6.0 * ux)), int(round(gy - 6.0 * uy)))

            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "gyeongbeongap_steel", d=d)
            draw_line_indices(c, butt_x, butt_y, gx, gy, IDX_WOOD_DARK, width=2)
            set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
            draw_line_indices(c, gx, gy, tip_x, tip_y, IDX_STEEL_MID, width=2)
            draw_line_indices(c, int(round(gx + px_a)), int(round(gy + py_a)), tip_x, tip_y, IDX_STEEL_GLEAM, width=1)
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_RED_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_RED_HIGH)
            set_safe_pixel(c, gx, gy, IDX_GOLD_BRIGHT)
            set_safe_pixel(c, tip_x, tip_y, IDX_STEEL_GLEAM)

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_jangchangsu_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    144x140, 168 frames for 장창수 (0x7C):
    - Crimson & Team-Blue Dujeonggap with golden rivets
    - Full 2x-length (70px~78px) 15-foot Joseon long spear (장창) held upright in Idle,
      diagonally across chest in Move, and thrusting deep on Attack,
      with two articulated 3D arms and two hands visibly clasping the spear shaft (창대).
    """
    spec = UNIT_SPECS["jangchangsu"]
    tw, th = spec["width"], spec["height"]  # 144x140
    bw, bh = 60, 60
    ox, oy = (tw - bw) // 2, (th - bh) // 2  # 42, 40
    cx, cy = tw // 2, th // 2 - 1
    frames = []

    for f_idx in range(168):
        c = np.zeros((th, tw), dtype=np.uint8)
        state, d, step = get_frame_state(f_idx)
        base = clean_base_human(np.frombuffer(base_frames[f_idx], dtype=np.uint8).reshape((bh, bw)), f_idx)
        base = apply_joseon_armor(base, f_idx, style="dujeonggap_crimson")

        # Subtle forward lunge shift during peak spear thrust (steps 2..5)
        b_dx, b_dy = 0, 0
        if state == "attack" and step in (2, 3, 4, 5):
            ux_a, uy_a = ATK_DIR_VECTORS[d]
            b_dx = int(round(1.8 * ux_a))
            b_dy = int(round(1.5 * uy_a))

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy + b_dy, bx + ox + b_dx
                if 0 <= ty < th and 0 <= tx < tw:
                    c[ty, tx] = val

        if state == "die":
            # Fallen 2x-length long spear (86px total: cx-42 to cx+44)
            draw_line_indices(c, cx - 42, cy + 13, cx + 34, cy + 13, IDX_WOOD_MID, width=2)
            draw_line_indices(c, cx - 42, cy + 13, cx + 34, cy + 13, IDX_WOOD_LIGHT, width=1)
            set_safe_pixel(c, cx - 42, cy + 13, IDX_STEEL_LOW)
            draw_line_indices(c, cx + 34, cy + 13, cx + 43, cy + 13, IDX_STEEL_MID, width=2)
            draw_line_indices(c, cx + 35, cy + 13, cx + 44, cy + 13, IDX_STEEL_GLEAM, width=1)
            draw_line_indices(c, cx + 32, cy + 13, cx + 37, cy + 17, IDX_RED_BRIGHT, width=1)
        else:
            # Exactly 2.0x the previous spear length (Idle/Move: 52+18=70px; Attack: 44..66+12..20)
            if state == "attack":
                thrust = (step / 4.0) if step <= 4 else (1.0 - (step - 4) / 3.0)
                front_len = int(44 + 22 * thrust)
                rear_len = (10 if d == 4 else max(8, int(20 - 8 * thrust)))
            else:
                front_len = 52
                rear_len = 18

            butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy = get_polearm_pose(
                state, d, step, cx + b_dx, cy + b_dy, rear_len=rear_len, front_len=front_len
            )
            perp_x, perp_y = -uy, ux

            # Two collinear hand grip points on the spear shaft (rear hand and front lead hand)
            r_hand = (int(round(gx - 3.5 * ux)), int(round(gy - 3.5 * uy)))
            f_hand = (int(round(gx + 5.0 * ux)), int(round(gy + 5.0 * uy)))

            # 1. Draw both 3D articulated arms from the 3ds Max pauldrons to r_hand and f_hand
            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "dujeonggap_crimson", d=d)

            # 2. Solid hardwood/red-lacquered long spear shaft from rear butt through both hands to neck
            neck_x = int(round(tip_x - 10 * ux))
            neck_y = int(round(tip_y - 10 * uy))
            mid_shaft_x = int(round(gx + (front_len * 0.55) * ux))
            mid_shaft_y = int(round(gy + (front_len * 0.55) * uy))
            draw_line_indices(c, butt_x, butt_y, mid_shaft_x, mid_shaft_y, IDX_WOOD_DARK, width=2)
            draw_line_indices(c, butt_x, butt_y, neck_x, neck_y, IDX_WOOD_MID, width=1)
            draw_line_indices(c, gx, gy, mid_shaft_x, mid_shaft_y, IDX_WOOD_LIGHT, width=1)
            set_safe_pixel(c, butt_x, butt_y, IDX_STEEL_LOW)

            # 3. Draw both 3D hands wrapping ON TOP OF the spear shaft so the soldier visibly grasps the pole!
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_GOLD_MID)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_GOLD_MID)

            # 4. Prominent crimson horsehair tassel (붉은 영자) at neck collar
            tassel_end_x = int(round(neck_x + 5 * perp_x - 3 * ux))
            tassel_end_y = int(round(neck_y + 5 * perp_y + 3))
            draw_line_indices(c, neck_x, neck_y, tassel_end_x, tassel_end_y, IDX_RED_BRIGHT, width=2)
            set_safe_pixel(c, int(round(neck_x + 3 * perp_x)), int(round(neck_y + 3 * perp_y + 1)), IDX_RED_HIGH)
            set_safe_pixel(c, neck_x, neck_y, IDX_GOLD_BRIGHT)

            # 5. 10px tapered steel spearhead (2px base -> 1px gleaming razor tip)
            mid_head_x = int(round(tip_x - 4 * ux))
            mid_head_y = int(round(tip_y - 4 * uy))
            draw_line_indices(c, neck_x, neck_y, mid_head_x, mid_head_y, IDX_STEEL_MID, width=2)
            draw_line_indices(c, neck_x, neck_y, tip_x, tip_y, IDX_STEEL_GLEAM, width=1)
            set_safe_pixel(c, tip_x, tip_y, IDX_STEEL_GLEAM)

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_woldo_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    78x74, 168 frames for 월도병 (0x7D):
    - Heavy Gyeongbeongap with gold & steel lamellar rows
    - Authentic Joseon Crescent Halberd (월도) gripped with both hands on the wooden pole
      in Idle, Move, and sweeping Attack.
    """
    spec = UNIT_SPECS["woldo"]
    tw, th = spec["width"], spec["height"]  # 78x74
    bw, bh = 60, 60
    ox, oy = (tw - bw) // 2, (th - bh) // 2  # 9, 7
    cx, cy = tw // 2, th // 2 - 1
    frames = []

    for f_idx in range(168):
        c = np.zeros((th, tw), dtype=np.uint8)
        state, d, step = get_frame_state(f_idx)
        src_idx, b_dx, b_dy = get_slash_body_frame_idx(f_idx)
        base = clean_base_human(np.frombuffer(base_frames[src_idx], dtype=np.uint8).reshape((bh, bw)), src_idx)
        base = apply_joseon_armor(base, src_idx, style="gyeongbeongap_heavy")

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy + b_dy, bx + ox + b_dx
                if not (0 <= ty < th and 0 <= tx < tw):
                    continue
                c[ty, tx] = val

        if state == "die":
            # Fallen 1.2x-scaled woldo beside corpse
            draw_line_indices(c, cx - 22, cy + 12, cx + 12, cy + 12, IDX_WOOD_MID, width=1)
            set_safe_pixel(c, cx - 22, cy + 12, IDX_GOLD_MID)
            draw_line_indices(c, cx + 11, cy + 12, cx + 13, cy + 12, IDX_GOLD_BRIGHT, width=2)
            draw_line_indices(c, cx + 13, cy + 12, cx + 22, cy + 8, IDX_STEEL_MID, width=2)
            draw_line_indices(c, cx + 14, cy + 11, cx + 25, cy + 6, IDX_STEEL_GLEAM, width=1)
            set_safe_pixel(c, cx + 12, cy + 14, IDX_RED_BRIGHT)
        else:
            if state == "attack":
                h_dx, h_dy, ang_deg = SWORD_SLASH_KEYFRAMES[d][step]
                ang = math.radians(ang_deg)
                ux, uy = math.cos(ang), math.sin(ang)
                gx, gy = cx + b_dx + h_dx, cy + b_dy + (h_dy // 2 if step in (0, 1) else h_dy)
                rear_len = 10   # 1.2x scaled rear shaft (8 -> 10px)
                shaft_len = 18  # 1.2x scaled front shaft (15 -> 18px)
                butt_x = int(round(gx - rear_len * ux))
                butt_y = int(round(gy - rear_len * uy))
                collar_x = int(round(gx + shaft_len * ux))
                collar_y = int(round(gy + shaft_len * uy))
                if step in (2, 3, 4):
                    prev_ang = SWORD_SLASH_KEYFRAMES[d][step - 1][2]
                    draw_slash_arc(c, gx, gy, prev_ang, ang_deg, radius=shaft_len + 15)
            else:
                # 1.2x scaled Idle/Move polearm pose (rear_len=10, front_len=18)
                butt_x, butt_y, gx, gy, collar_x, collar_y, ux, uy = get_polearm_pose(
                    state, d, step, cx + b_dx, cy + b_dy, rear_len=10, front_len=18
                )

            perp_x, perp_y = -uy, ux
            r_hand = (int(round(gx - 3.5 * ux)), int(round(gy - 3.5 * uy)))
            f_hand = (int(round(gx + 4.5 * ux)), int(round(gy + 4.5 * uy)))

            # 0. Draw both 3D articulated arms connecting shoulders to the two grip points on the Woldo pole
            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "gyeongbeongap_heavy", d=d)

            # 1. Wooden pole from rear butt through hands to dragon collar
            draw_line_indices(c, butt_x, butt_y, collar_x, collar_y, IDX_WOOD_DARK, width=2)
            draw_line_indices(c, butt_x, butt_y, collar_x, collar_y, IDX_WOOD_MID, width=1)
            set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_MID)

            # 1b. Draw both 3D hands wrapping ON TOP OF the Woldo wooden pole
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_RED_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_RED_HIGH)

            # 2. Golden dragon collar (용두) + crimson tassel streamer
            c2_x = int(round(collar_x + 2 * ux))
            c2_y = int(round(collar_y + 2 * uy))
            draw_line_indices(c, collar_x, collar_y, c2_x, c2_y, IDX_GOLD_BRIGHT, width=2)
            draw_line_indices(
                c,
                collar_x,
                collar_y,
                int(round(collar_x - 4 * perp_x)),
                int(round(collar_y - 4 * perp_y + 2)),
                IDX_RED_BRIGHT,
                width=1,
            )

            # 3. 1.2x scaled curved crescent blade (월도날: 12px -> 15px long, 3.2px wide belly tapering to razor tip)
            belly1_x = int(round(c2_x + 5 * ux + 3.2 * perp_x))
            belly1_y = int(round(c2_y + 5 * uy + 3.2 * perp_y))
            belly2_x = int(round(c2_x + 10 * ux + 2.7 * perp_x))
            belly2_y = int(round(c2_y + 10 * uy + 2.7 * perp_y))
            tip_b_x = int(round(c2_x + 15 * ux + 0.8 * perp_x))
            tip_b_y = int(round(c2_y + 15 * uy + 0.8 * perp_y))
            spine_x = int(round(c2_x + 9 * ux + 0.6 * perp_x))
            spine_y = int(round(c2_y + 9 * uy + 0.6 * perp_y))

            # Inner steel spine & blade body
            draw_line_indices(c, c2_x, c2_y, spine_x, spine_y, IDX_STEEL_MID, width=2)
            draw_line_indices(c, spine_x, spine_y, tip_b_x, tip_b_y, IDX_STEEL_HIGH, width=1)
            # Curved gleaming outer cutting edge
            draw_line_indices(c, int(round(c2_x + perp_x)), int(round(c2_y + perp_y)), belly1_x, belly1_y, IDX_STEEL_GLEAM, width=2)
            draw_line_indices(c, belly1_x, belly1_y, belly2_x, belly2_y, IDX_STEEL_GLEAM, width=2)
            draw_line_indices(c, belly2_x, belly2_y, tip_b_x, tip_b_y, IDX_STEEL_GLEAM, width=1)
            # Back dorsal spike (신)
            set_safe_pixel(c, int(round(c2_x + 4 * ux - 1.8 * perp_x)), int(round(c2_y + 4 * uy - 1.8 * perp_y)), IDX_STEEL_GLEAM)
            set_safe_pixel(c, tip_b_x, tip_b_y, IDX_STEEL_GLEAM)

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_nangseon_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    144x140, 168 frames for 낭선병 (0x7E):
    - Agile vanguard soldier in steel-shouldered Dujeonggap
    - Full 2x-length (66px~74px) multi-tier bamboo branch spear (낭선) held upright in Idle,
      diagonally across chest in Move, and thrusting deep on Attack,
      with two articulated 3D arms and two hands visibly clasping the bamboo main shaft.
    """
    spec = UNIT_SPECS["nangseon"]
    tw, th = spec["width"], spec["height"]  # 144x140
    bw, bh = 60, 60
    ox, oy = (tw - bw) // 2, (th - bh) // 2  # 42, 40
    cx, cy = tw // 2, th // 2 - 1
    frames = []

    for f_idx in range(168):
        c = np.zeros((th, tw), dtype=np.uint8)
        state, d, step = get_frame_state(f_idx)
        base = clean_base_human(np.frombuffer(base_frames[f_idx], dtype=np.uint8).reshape((bh, bw)), f_idx)
        base = apply_joseon_armor(base, f_idx, style="dujeonggap_vanguard")

        b_dx, b_dy = 0, 0
        if state == "attack" and step in (2, 3, 4, 5):
            ux_a, uy_a = ATK_DIR_VECTORS[d]
            b_dx = int(round(1.8 * ux_a))
            b_dy = int(round(1.5 * uy_a))

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy + b_dy, bx + ox + b_dx
                if 0 <= ty < th and 0 <= tx < tw:
                    c[ty, tx] = val

        if state == "die":
            # Fallen 2x-length multi-branched bamboo spear (cx-40 to cx+42)
            draw_line_indices(c, cx - 40, cy + 14, cx + 36, cy + 14, IDX_BAMBOO_HIGH, width=2)
            draw_line_indices(c, cx - 40, cy + 14, cx + 36, cy + 14, IDX_BAMBOO_GOLD, width=1)
            draw_line_indices(c, cx + 36, cy + 14, cx + 42, cy + 14, IDX_STEEL_GLEAM, width=1)
            for bx_n in (cx - 10, cx - 1, cx + 8, cx + 17, cx + 26):
                # Upper & lower primary branches + sub-twigs
                draw_line_indices(c, bx_n, cy + 14, bx_n + 7, cy + 8, IDX_BAMBOO_GOLD, width=1)
                draw_line_indices(c, bx_n + 3, cy + 11, bx_n + 6, cy + 6, IDX_BAMBOO_VIVID, width=1)
                set_safe_pixel(c, bx_n + 7, cy + 8, IDX_STEEL_GLEAM)
                set_safe_pixel(c, bx_n + 6, cy + 6, IDX_STEEL_GLEAM)
                draw_line_indices(c, bx_n, cy + 14, bx_n + 7, cy + 20, IDX_BAMBOO_LIGHT, width=1)
                draw_line_indices(c, bx_n + 3, cy + 17, bx_n + 6, cy + 22, IDX_BAMBOO_HIGH, width=1)
                set_safe_pixel(c, bx_n + 7, cy + 20, IDX_STEEL_GLEAM)
                set_safe_pixel(c, bx_n + 6, cy + 22, IDX_STEEL_GLEAM)
        else:
            if state == "attack":
                thrust = (step / 4.0) if step <= 4 else (1.0 - (step - 4) / 3.0)
                front_len = int(42 + 22 * thrust)
                rear_len = (10 if d == 4 else max(8, int(18 - 8 * thrust)))
                tier_specs = (
                    (0.24, 9, 5),
                    (0.37, 11, 6),
                    (0.50, 12, 6),
                    (0.63, 11, 5),
                    (0.76, 9, 5),
                    (0.87, 7, 4),
                )
            else:
                front_len = 50
                rear_len = 16
                tier_specs = (
                    (0.26, 9, 5),
                    (0.40, 11, 6),
                    (0.54, 11, 6),
                    (0.68, 10, 5),
                    (0.82, 8, 4),
                )

            butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy = get_polearm_pose(
                state, d, step, cx + b_dx, cy + b_dy, rear_len=rear_len, front_len=front_len
            )
            perp_x, perp_y = -uy, ux

            r_hand = (int(round(gx - 3.5 * ux)), int(round(gy - 3.5 * uy)))
            f_hand = (int(round(gx + 5.0 * ux)), int(round(gy + 5.0 * uy)))

            # 0. Draw both 3D articulated arms connecting shoulders to r_hand and f_hand
            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "dujeonggap_vanguard", d=d)

            # 1. Prominent 2px bamboo main shaft (dark bamboo green shadow + bright golden bamboo ridge)
            neck_x = int(round(tip_x - 6 * ux))
            neck_y = int(round(tip_y - 6 * uy))
            draw_line_indices(c, butt_x, butt_y, neck_x, neck_y, IDX_BAMBOO_HIGH, width=2)
            draw_line_indices(c, butt_x, butt_y, neck_x, neck_y, IDX_BAMBOO_GOLD, width=1)
            set_safe_pixel(c, butt_x, butt_y, IDX_STEEL_LOW)

            # 1b. Draw both 3D hands wrapping ON TOP OF the bamboo main shaft
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_GOLD_MID)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_GOLD_MID)

            # 2. Multi-tiered lateral branches (주 가지) + forked secondary sub-twigs (잔가지) + iron barbs
            for t_idx, (t_node, b_len, twig_len) in enumerate(tier_specs):
                nx = int(round(gx + front_len * ux * t_node))
                ny = int(round(gy + front_len * uy * t_node))

                # Left & Right Primary Branches (sweeping forward-outward at ~45 deg)
                l_dir_x = ux * 0.68 + perp_x * 0.73
                l_dir_y = uy * 0.68 + perp_y * 0.73
                r_dir_x = ux * 0.68 - perp_x * 0.73
                r_dir_y = uy * 0.68 - perp_y * 0.73

                lbx = int(round(nx + b_len * l_dir_x))
                lby = int(round(ny + b_len * l_dir_y))
                rbx = int(round(nx + b_len * r_dir_x))
                rby = int(round(ny + b_len * r_dir_y))

                # Thicker 2px base for lower/middle tiers so branches stand out against any terrain
                l_mid_x = int(round(nx + (b_len * 0.52) * l_dir_x))
                l_mid_y = int(round(ny + (b_len * 0.52) * l_dir_y))
                r_mid_x = int(round(nx + (b_len * 0.52) * r_dir_x))
                r_mid_y = int(round(ny + (b_len * 0.52) * r_dir_y))

                draw_line_indices(c, nx, ny, l_mid_x, l_mid_y, IDX_BAMBOO_HIGH, width=2)
                draw_line_indices(c, nx, ny, lbx, lby, IDX_BAMBOO_GOLD, width=1)
                draw_line_indices(c, nx, ny, r_mid_x, r_mid_y, IDX_BAMBOO_MID, width=2)
                draw_line_indices(c, nx, ny, rbx, rby, IDX_BAMBOO_LIGHT, width=1)

                # Secondary forked sub-twigs (잔가지) sprouting outward from the middle of each primary branch
                lt_dir_x = ux * 0.28 + perp_x * 0.96
                lt_dir_y = uy * 0.28 + perp_y * 0.96
                rt_dir_x = ux * 0.28 - perp_x * 0.96
                rt_dir_y = uy * 0.28 - perp_y * 0.96

                lt_x = int(round(l_mid_x + twig_len * lt_dir_x))
                lt_y = int(round(l_mid_y + twig_len * lt_dir_y))
                rt_x = int(round(r_mid_x + twig_len * rt_dir_x))
                rt_y = int(round(r_mid_y + twig_len * rt_dir_y))

                draw_line_indices(c, l_mid_x, l_mid_y, lt_x, lt_y, IDX_BAMBOO_VIVID, width=1)
                draw_line_indices(c, r_mid_x, r_mid_y, rt_x, rt_y, IDX_BAMBOO_GOLD, width=1)

                # Inner upward/forward fine twigs (속 잔가지) on main tiers for extra thorny density
                if t_idx < len(tier_specs) - 1:
                    in_l_x = int(round(l_mid_x + (twig_len - 1) * (ux * 0.92 + perp_x * 0.38)))
                    in_l_y = int(round(l_mid_y + (twig_len - 1) * (uy * 0.92 + perp_y * 0.38)))
                    in_r_x = int(round(r_mid_x + (twig_len - 1) * (ux * 0.92 - perp_x * 0.38)))
                    in_r_y = int(round(r_mid_y + (twig_len - 1) * (uy * 0.92 - perp_y * 0.38)))
                    draw_line_indices(c, l_mid_x, l_mid_y, in_l_x, in_l_y, IDX_BAMBOO_LIGHT, width=1)
                    draw_line_indices(c, r_mid_x, r_mid_y, in_r_x, in_r_y, IDX_BAMBOO_VIVID, width=1)
                    set_safe_pixel(c, in_l_x, in_l_y, IDX_STEEL_HIGH)
                    set_safe_pixel(c, in_r_x, in_r_y, IDX_STEEL_HIGH)

                # Gleaming 2px steel barbs (철가시) on all primary & secondary twig tips
                set_safe_pixel(c, int(round(lbx - l_dir_x)), int(round(lby - l_dir_y)), IDX_STEEL_HIGH)
                set_safe_pixel(c, lbx, lby, IDX_STEEL_GLEAM)
                set_safe_pixel(c, int(round(rbx - r_dir_x)), int(round(rby - r_dir_y)), IDX_STEEL_HIGH)
                set_safe_pixel(c, rbx, rby, IDX_STEEL_GLEAM)
                set_safe_pixel(c, lt_x, lt_y, IDX_STEEL_GLEAM)
                set_safe_pixel(c, rt_x, rt_y, IDX_STEEL_GLEAM)

                # Golden bamboo node ring (마디) on main shaft
                set_safe_pixel(c, nx, ny, IDX_GOLD_BRIGHT)

            # 3. 6px central steel spearhead at the apex of the bamboo spear
            draw_line_indices(c, neck_x, neck_y, tip_x, tip_y, IDX_STEEL_MID, width=2)
            draw_line_indices(c, neck_x, neck_y, tip_x, tip_y, IDX_STEEL_GLEAM, width=1)
            set_safe_pixel(c, tip_x, tip_y, IDX_STEEL_GLEAM)

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


# ---------------------------------------------------------------------------
# Main Generation Function
# ---------------------------------------------------------------------------

def generate_all_unit_sprites():
    """Build and write all 5 .spr files into YM/dawn/char/ and mirror to online sprite slots."""
    print("[*] Loading base soldier motion frames from YM/dawn/char/swordk.spr...")
    base_frames = load_base_frames()
    char_dir = PROJECT_ROOT / "YM" / "dawn" / "char"

    generators = {
        "dengpaesu.spr": (build_dengpaesu_frames(base_frames), 68, 68),
        "ssangsudo.spr": (build_ssangsudo_frames(base_frames), 80, 74),
        "jangchangsu.spr": (build_jangchangsu_frames(base_frames), 144, 140),
        "woldo.spr": (build_woldo_frames(base_frames), 78, 74),
        "nangseon.spr": (build_nangseon_frames(base_frames), 144, 140),
    }

    # 1:1 online character slot mapping for dawn.exe engine runtime extraction
    online_slots = {
        "dengpaesu.spr": "Gangsi1_online.spr",      # ID 318
        "ssangsudo.spr": "Gangsi2_online.spr",      # ID 319
        "jangchangsu.spr": "Gangsi3_online.spr",    # ID 320
        "woldo.spr": "RaccoonDog_online.spr",       # ID 322
        "nangseon.spr": "Deer_online.spr",          # ID 323
    }

    for fname, (frames, w, h) in generators.items():
        spr_bytes = build_spr_v9(w, h, frames)

        # Primary sprite file
        out_path = char_dir / fname
        try:
            os.chmod(out_path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        out_path.write_bytes(spr_bytes)
        print(f"  [OK] Wrote {out_path.name} ({w}x{h}, {len(frames)} frames, {len(spr_bytes):,} bytes)")

        # Mirror to online character slot
        if fname in online_slots:
            online_name = online_slots[fname]
            online_path = char_dir / online_name
            try:
                os.chmod(online_path, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
            online_path.write_bytes(spr_bytes)
            print(f"  [OK] Mirrored to online slot: {online_name}")


if __name__ == "__main__":
    generate_all_unit_sprites()
