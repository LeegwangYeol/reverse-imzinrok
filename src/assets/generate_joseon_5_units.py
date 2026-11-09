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
    (-2, -3),  # 0: SW (front/three-quarter view)
    (-4, -5),  # 1: W  (side-back profile: held in front of chest, occluded by torso)
    (-3, -5),  # 2: NW (back view: held in front of upper chest, occluded by torso)
    (3, -5),   # 3: N  (back view: held in front of upper-right chest, occluded by torso)
    (-2, -3),  # 4: S  (front view)
]

MOVE_GRIP_OFFSETS: List[Tuple[int, int]] = [
    (-2, -3),  # 0: SW
    (-4, -5),  # 1: W  (held in front of chest, occluded by back/side armor)
    (-3, -5),  # 2: NW (held in front of chest, occluded by back armor)
    (3, -5),   # 3: N  (held in front of chest, occluded by back armor)
    (-2, -3),  # 4: S
]

ATK_GRIP_OFFSETS: List[Tuple[int, int]] = [
    (-1, -3),  # 0: SW
    (-4, -4),  # 1: W  (thrusting forward in front of chest, occluded by torso)
    (-3, -5),  # 2: NW (thrusting forward in front of chest, occluded by back armor)
    (3, -5),   # 3: N  (thrusting forward in front of chest, occluded by back armor)
    (-1, -2),  # 4: S
]

# 8-step Idle forearm/hand-tip poise trajectory & wrist pitch oscillation:
# Across the 8 Idle frames (step = 0..7), the forearms move the hands (팔끝/손끝) along a smooth
# 8-step poise arc and the wrists pitch the blade angle so the sword/halberd visibly sways back and forth
# following the moving tip of the arm (팔끝을 따라서 검이 왔다갔다 함).
IDLE_ARM_DX: Tuple[float, ...] = (-2.0, -1.0, 0.5, 2.0, 3.0, 2.0, 0.0, -1.0)
IDLE_ARM_DY: Tuple[float, ...] = (1.0, 0.0, -1.0, -2.0, -1.0, 0.0, 1.0, 2.0)
IDLE_WRIST_DEG: Tuple[float, ...] = (-11.0, -5.5, 2.5, 10.0, 15.0, 9.0, 0.0, -6.5)

# Explicit 8-step 3D elliptical Arm-Lead -> Forearm-Whip -> Wrist-Snap -> Cross-Body Follow-Through
# slash trajectories per direction (0: SW, 1: W, 2: NW, 3: N, 4: S).
# Here (h_dx, h_dy) is the TRUE 3D HAND GRIP CENTER (손끝/팔끝) relative to (cx + b_dx, cy + b_dy):
# - Step 0 (Lift): Hands lift up-right in front of rear shoulder, blade angled up;
# - Step 1 (Coil): Hands pull high behind rear shoulder/helmet, elbow bent wide, blade cocked back;
# - Step 2 (Arm-Lead Pull): Shoulders & elbows pull the hands forward across the upper chest FIRST
#   while the heavy blade lags upright-back behind the hands;
# - Step 3 (Forearm Whip): Elbows unbend, whipping the forearms & hands wide outward-forward;
# - Step 4 (Full Extension & Wrist Snap): Arms reach maximum forward extension while the wrist snaps the blade across;
# - Step 5 (Downward Cut): Outstretched arms sweep down-forward through the target;
# - Step 6 (Cross-Body Follow-Through): Hands continue the circular arc across the lower front waist/hip;
# - Step 7 (Guard Recovery): Elbows flex to lift the hands and blade smoothly back to chest guard.
SWORD_SLASH_KEYFRAMES: List[List[Tuple[int, int, float]]] = [
    # 0: SW (facing down-left)
    [
        (4, -8, -55.0),    # step 0: hands lift up-right to rear shoulder, blade tilted back-right
        (6, -10, -32.0),   # step 1: hands coil deep behind right shoulder, blade cocked far back
        (-3, -9, -118.0),  # step 2: arms drive hilt high forward-left past shoulder, blade whips overhead
        (-7, -5, -155.0),  # step 3: forearms whip wide forward-left, blade accelerates out
        (-9, -1, 165.0),   # step 4: full forward arm extension + wrist snap across SW
        (-7, 3, 132.0),    # step 5: deep downward-SW arc cleave (hit!)
        (-2, 4, 108.0),    # step 6: cross-body low follow-through across front waist
        (-2, -3, -128.0),  # step 7: elbows flex back to chest ready guard
    ],
    # 1: W (facing left)
    [
        (4, -8, -52.0),    # step 0: hands lift up-right behind shoulder
        (6, -10, -30.0),   # step 1: deep overhead-back coil behind shoulder
        (-3, -9, -115.0),  # step 2: arms drive forward-left past top of shoulder
        (-7, -5, -150.0),  # step 3: forearms whip wide forward-up-left
        (-9, -2, 174.0),   # step 4: full horizontal-left arm extension + wrist snap
        (-7, 2, 144.0),    # step 5: deep West-SW cleave follow-through (hit!)
        (-3, 3, 120.0),    # step 6: cross-body low follow-through
        (-3, -3, -125.0),  # step 7: return to guard
    ],
    # 2: NW (facing up-left)
    [
        (4, -8, -48.0),    # step 0: hands lift up-right behind shoulder
        (6, -10, -28.0),   # step 1: coil back-right behind helmet
        (-3, -9, -112.0),  # step 2: arms pull forward-left past shoulder
        (-7, -6, -145.0),  # step 3: forearms whip out past left shoulder
        (-8, -3, -172.0),  # step 4: full forward-NW arm extension + wrist snap
        (-7, 0, 160.0),    # step 5: follow-through cleave to West (hit!)
        (-3, 1, 140.0),    # step 6: cross-body follow-through in front of chest
        (-3, -4, -120.0),  # step 7: ready stance
    ],
    # 3: N (facing up/back)
    [
        (-4, -8, -125.0),  # step 0: hands lift up-left behind left shoulder
        (-6, -10, -148.0), # step 1: coil back-left behind helmet
        (3, -9, -65.0),    # step 2: arms drive forward-right past right shoulder
        (7, -6, -35.0),    # step 3: forearms whip out past right shoulder
        (8, -3, -8.0),     # step 4: full forward-NE arm extension + wrist snap
        (7, 0, 20.0),      # step 5: full follow-through to East (hit!)
        (3, 1, 40.0),      # step 6: cross-body follow-through
        (3, -4, -60.0),    # step 7: ready stance
    ],
    # 4: S (facing down/front)
    [
        (4, -8, -58.0),    # step 0: hands lift high-right above shoulder
        (6, -10, -35.0),   # step 1: peak overhead-back coil
        (-3, -8, -122.0),  # step 2: arms drive hilt forward-left above shoulder
        (-7, -4, -158.0),  # step 3: forearms whip wide out-left
        (-7, 1, 145.0),    # step 4: full downward-front-left arm extension + wrist snap
        (-2, 5, 102.0),    # step 5: deep downward cleave straight across South (hit!)
        (2, 4, 78.0),      # step 6: cross-body follow-through to lower-right hip
        (-1, -2, -122.0),  # step 7: return to front chest guard
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
    """Draw a sleek, tight metallic sword-slash trail (검기) right behind the cutting edge (clamped to <= 26 deg)."""
    diff = (ang_end_deg - ang_start_deg + 180.0) % 360.0 - 180.0
    if abs(diff) > 26.0:
        ang_start_deg = ang_end_deg - (26.0 if diff > 0 else -26.0)
        diff = 26.0 if diff > 0 else -26.0
    steps = max(8, int(abs(diff) * 1.5))
    for i in range(steps + 1):
        t = i / float(steps)
        a_rad = math.radians(ang_start_deg + diff * t)
        ca, sa = math.cos(a_rad), math.sin(a_rad)
        col_outer = IDX_STEEL_GLEAM if t >= 0.50 else IDX_STEEL_HIGH
        col_inner = IDX_STEEL_MID if t >= 0.40 else IDX_STEEL_LOW
        ox = int(round(hx + radius * ca))
        oy = int(round(hy + radius * sa))
        ix = int(round(hx + (radius - 1) * ca))
        iy = int(round(hy + (radius - 1) * sa))
        set_safe_pixel(canvas, ox, oy, col_outer)
        set_safe_pixel(canvas, ix, iy, col_inner)


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


def get_upper_body_offset(state: str, d: int, step: int) -> Tuple[int, int]:
    """
    Compute (ub_dx, ub_dy) for the upper torso & shoulders so that:
      - In Move (0..39), the soldier's upper body has a natural 2-beat running bounce (뜀박질 바운스)
        and forward athletic sprint lean.
      - In Attack (48..87), the lower body & feet stay 100% planted on the ground (0px foot twitch)
        while the upper torso coils back slightly (step 1) and lunges forward into the strike (steps 3..5).
      - In Idle (88..167), the torso stays grounded while the forearms/hands sway the weapon.
    """
    if state == "move":
        ub_dy = (1, 0, -1, 0, 1, 0, -1, 0)[step]
        ub_dx = -1 if d in (0, 1, 2) else (1 if d == 3 else 0)
        return ub_dx, ub_dy
    if state == "attack":
        ux, uy = ATK_DIR_VECTORS[d]
        lunge = (0.0, -0.8, 0.4, 1.3, 2.0, 1.3, 0.4, 0.0)[step]
        ub_dx = int(round(lunge * ux))
        ub_dy = int(round(max(0.0, lunge) * 0.5 * uy))
        return ub_dx, ub_dy
    return 0, 0


def get_slash_body_frame_idx(f_idx: int) -> Tuple[int, int, int]:
    """
    Keep the frame index consistent (no splicing between Idle, Move, and Attack leg frames)
    and return (f_idx, ub_dx, ub_dy) where (ub_dx, ub_dy) is the upper-body shoulder lunge offset.
    """
    state, d, step = get_frame_state(f_idx)
    ub_dx, ub_dy = get_upper_body_offset(state, d, step)
    return f_idx, ub_dx, ub_dy


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
RAMP_BAJI = [242, 95, 90, 83, 52, 53, 54, 54, 55, 55, 240, 240]

HELMET_SET_GK11 = {17, 22, 23, 24, 66, 98, 99, 107, 108, 109, 110, 111, 112, 170, 188, 191, 212, 224}
RED_SET_GK11 = {46, 47, 48, 113, 114, 115, 116, 117, 118, 119, 120, 163, 164, 165, 166, 232, 233, 234, 235}
BLUE_SET_GK11 = set(range(193, 208)) | set(range(236, 240)) | {136, 137, 138, 139, 159}
YELLOW_LEG_SET_GK11 = {36, 37, 66, 68, 69, 75, 107, 109, 153, 214, 224}

# 3ds Max human leg palette sets in SwordPirate_online.spr (excludes katana steel 49..58, 247..255 and ground shadow 228..229)
SP_LEG_VALID = {
    9, 14, 18, 19, 20, 21, 22, 23, 24, 37, 43, 64, 65, 66, 67, 71, 72, 74, 75, 76,
    77, 78, 79, 80, 81, 82, 83, 84, 85, 87, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98,
    99, 100, 101, 102, 103, 105, 106, 126, 147, 148, 149, 150, 172, 174, 175, 176,
    177, 178, 182, 183, 190, 191, 208, 209, 212, 224, 241, 242, 243, 244, 245, 246,
}
SP_LEG_OUTLINE = {14, 66, 190, 191, 208, 212, 224, 241, 242}
SP_LEG_DARK_WRAP = {65, 72, 89, 90, 91, 94, 95, 96, 148, 149, 150, 209, 243, 244, 245, 246}
SP_ATK_STEP_MAP = (0, 1, 2, 3, 4, 3, 2, 0)

_GK11_3D_CACHE: dict = {}


def _get_gk11_3d_cache() -> Tuple[List[np.ndarray], np.ndarray]:
    """
    Lazy-load and cache the 152 native 3ds Max frames of Kwon Yul on foot
    (generalk11.spr + generalk12.spr + generalk13.spr, 128x108), SwordPirate_online.spr
    (for 3ds Max running & grounded martial-arts lower body), and the imjin2.pal luminance LUT.
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

    dec_sp = SpriteDecoder.from_file(char_dir / "SwordPirate_online.spr")
    sp_frames: List[np.ndarray] = [
        np.frombuffer(dec_sp.decode_frame_raw(i), dtype=np.uint8).reshape((dec_sp.height, dec_sp.width))
        for i in range(min(120, dec_sp.frame_count))
    ]

    _GK11_3D_CACHE["frames"] = gk_frames
    _GK11_3D_CACHE["sp_frames"] = sp_frames
    _GK11_3D_CACHE["lum"] = lum
    return gk_frames, lum


def _extract_sp_3d_legs(state: str, d: int, step: int) -> Tuple[np.ndarray, float]:
    """
    Extract clean 3ds Max human lower body (thighs, knees, shin wraps, boots) from SwordPirate_online.spr:
      - Move (0..39):   SwordPirate_online.spr[80 + d*8 + step] (dynamic 3ds Max running stride 뜀박질)
      - Attack (48..87): SwordPirate_online.spr[0 + d*8 + SP_ATK_STEP_MAP[step]] (wide planted martial stance, 0px foot twitch)
      - Idle (88..167): SwordPirate_online.spr[40 + d*8 + 0] (balanced wide ready stance)
    """
    _get_gk11_3d_cache()
    sp_frames = _GK11_3D_CACHE["sp_frames"]
    if state == "move":
        f_i = 80 + d * 8 + step
        cx_ref = (21.5, 20.5, 21.5, 19.5, 21.5)[d]
    elif state == "attack":
        f_i = 0 + d * 8 + SP_ATK_STEP_MAP[step]
        cx_ref = (19.0, 17.5, 19.0, 19.0, 21.0)[d]
    else:
        f_i = 40 + d * 8 + (step % 2 if d == 4 else 0)
        cx_ref = (19.0, 17.5, 19.0, 19.0, 21.0)[d]

    cache_key = ("sp_leg", state, d, step)
    if cache_key in _GK11_3D_CACHE:
        return _GK11_3D_CACHE[cache_key], cx_ref

    from collections import deque

    f = sp_frames[f_i]
    sub = f[53:83, 26:70].copy()
    if state == "move" and d == 4:
        # In South Move (112..119), the katana crosses horizontally over the left thigh (sy=0..9, sx=16..25)
        for y_k in range(10):
            for x_k in range(16, 26):
                if sub[y_k, x_k] > 0 and sub[y_k, x_k] not in (228, 229) and sub[y_k, x_k] not in SP_LEG_VALID:
                    sub[y_k, x_k] = 75
    sub[~np.isin(sub, list(SP_LEG_VALID))] = 0

    # Strip any side hand/scabbard/hilt outside the anatomical leg corridor
    c_i = int(round(cx_ref))
    sub[:6, : max(0, c_i - 9)] = 0
    sub[:6, min(sub.shape[1], c_i + 9) :] = 0
    if state == "move":
        if d in (0, 1, 2):
            sub[:, :9] = 0
            sub[:, 37:] = 0
        elif d == 3:
            sub[:, :12] = 0
            sub[:, 28:] = 0
        else:  # d == 4: strip swinging left-of-screen fist (sx_l < 15)
            sub[:, :15] = 0
            sub[:, 29:] = 0
    else:
        sub[:, : max(0, c_i - 14)] = 0
        sub[:, min(sub.shape[1], c_i + 18) :] = 0

    # Remove detached specks/islands (< 20px)
    vis = np.zeros_like(sub, dtype=bool)
    sh, sw = sub.shape
    for y in range(sh):
        for x in range(sw):
            if sub[y, x] > 0 and not vis[y, x]:
                comp = []
                q = deque([(y, x)])
                vis[y, x] = True
                while q:
                    cy_p, cx_p = q.popleft()
                    comp.append((cy_p, cx_p))
                    for ny in range(max(0, cy_p - 1), min(sh, cy_p + 2)):
                        for nx in range(max(0, cx_p - 1), min(sw, cx_p + 2)):
                            if sub[ny, nx] > 0 and not vis[ny, nx]:
                                vis[ny, nx] = True
                                q.append((ny, nx))
                if len(comp) < 20:
                    for cy_p, cx_p in comp:
                        sub[cy_p, cx_p] = 0

    _GK11_3D_CACHE[cache_key] = sub
    return sub, cx_ref


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
      1. Lower 40% (ty = 27..50): Dynamic 3ds Max Running & Martial-Stance Lower Body from SwordPirate_online.spr,
         shaded as traditional Joseon Baji (바지), Knee Ties (행전끈), Shin Wraps/Greaves (행전/경갑), and War Boots (전투화).
         - In Move (0..39), executes a full athletic running stride (자연스러운 뜀박질).
         - In Attack (48..87), maintains a wide, grounded martial stance (기마립/궁보) where both feet stay planted
           on the ground across all 8 steps (공격할때 다리가 방정거리지 않게) while the front knee flexes into the lunge.
      2. Upper 60% (ty = 2..32): Conical Cheomju Helmet (첨주 투구), Neck Guard (드림), Shoulder Pauldrons (견철),
         Lamellar/Brigandine Torso (두정갑/경번갑), Waist Sash (전대), and Hip-Length Tassets (갑상) from native 3ds Max
         generalk11..13.spr with natural 2-beat running bounce (뜀박질 바운스) and forward athletic lean.
    """
    gk_frames, lum = _get_gk11_3d_cache()
    state, d, step = get_frame_state(f_idx)
    gk_idx = _map_168_to_gk11_idx(f_idx)
    arr = gk_frames[gk_idx].copy()
    gh, gw = arr.shape

    # --- DIE FRAMES (40..47): 3ds Max Fallen Armored Corpse ---
    if state == "die":
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

        for ty in range(60):
            for tx in range(60):
                bv = int(base[ty, tx])
                if bv != 0:
                    out_die[ty, tx] = _pick_ramp(
                        RAMP_STEEL if "gyeongbeongap" in style else RAMP_DARK_IRON,
                        float(lum[bv]),
                    )

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

    out = np.zeros((60, 60), dtype=np.uint8)
    ub_dx, ub_dy = get_upper_body_offset(state, d, step)

    # 3. Build Knee-Length Heavy Armored Lower Body (무릎까지 내려온 중장갑 갑상/슬갑 ty=27..40 + 철제 정강이 경갑/전투화 ty=41..51)
    sub_leg, cx_ref = _extract_sp_3d_legs(state, d, step)
    sh_l, sw_l = sub_leg.shape
    leg_buf = np.zeros((60, 60), dtype=np.uint8)
    for ty in range(27, 52):
        sy_l = int(round((ty - 27) * 1.05))
        if not (0 <= sy_l < sh_l):
            continue
        for tx in range(10, 50):
            sx_l = int(round(cx_ref + (tx - 30)))
            if 0 <= sx_l < sw_l and int(sub_leg[sy_l, sx_l]) > 0:
                leg_buf[ty, tx] = int(sub_leg[sy_l, sx_l])

    # 3a. Horizontally dilate thigh & shin segments by +1px so heavy-infantry cuisses & greaves have full 3D bulk
    dilated = leg_buf.copy()
    for ty in range(27, 51):
        for tx in range(12, 48):
            if leg_buf[ty, tx] == 0:
                if leg_buf[ty, tx - 1] > 0 and leg_buf[ty, tx - 1] not in SP_LEG_OUTLINE:
                    dilated[ty, tx] = leg_buf[ty, tx - 1]
                elif leg_buf[ty, tx + 1] > 0 and leg_buf[ty, tx + 1] not in SP_LEG_OUTLINE:
                    dilated[ty, tx] = leg_buf[ty, tx + 1]
    leg_buf = dilated

    # 3b. Ensure solid Knee-Length Heavy Armored Tasset Flaps (좌우 중장갑 갑상/슬갑, ty=28..40) with zero hollow hip/thigh gaps
    if state == "move":
        l_knee_y = 40 + (-1, -1, 0, 1, 1, 0, -1, -1)[step]
        r_knee_y = 40 + (1, 0, -1, -1, -1, 0, 1, 1)[step]
        l_sway = (-1, -1, 0, 1, 1, 0, 0, -1)[step] if d in (0, 1, 2) else 0
        r_sway = (1, 1, 0, -1, -1, 0, 0, 1)[step] if d in (0, 1, 2) else 0
    elif state == "attack":
        l_knee_y, r_knee_y = 40, 40
        l_sway, r_sway = -1, 1
    else:
        l_knee_y, r_knee_y = 40, 40
        l_sway, r_sway = 0, 0

    for ty in range(28, 41):
        # Upper-to-mid thigh (ty <= 35): continuous wide heavy tasset skirt; Lower knee flaps (ty = 36..40): split left/right cuisses
        if ty <= 35:
            for tx in range(23 + ub_dx, 38 + ub_dx):
                if leg_buf[ty, tx] == 0:
                    leg_buf[ty, tx] = 75
        else:
            if ty <= l_knee_y:
                l_x0 = (22 if state == "attack" else 23) + ub_dx + l_sway
                l_x1 = 29 + ub_dx + max(0, l_sway)
                for tx in range(l_x0, l_x1 + 1):
                    if leg_buf[ty, tx] == 0:
                        leg_buf[ty, tx] = 75
            if ty <= r_knee_y:
                r_x0 = 31 + ub_dx + min(0, r_sway)
                r_x1 = (38 if state == "attack" else 37) + ub_dx + r_sway
                for tx in range(r_x0, r_x1 + 1):
                    if leg_buf[ty, tx] == 0:
                        leg_buf[ty, tx] = 75

    # 3c. In Move (0..39), ensure both left & right armored shin greaves (ty=41..47) are always visible below the knee skirt
    #     (when one leg lifts in N/S or crossover steps, render the raised second shin/boot down to ty=45..46)
    if state == "move":
        has_left_shin = np.any(leg_buf[42:48, 15:30] > 0)
        has_right_shin = np.any(leg_buf[42:48, 31:46] > 0)
        lift_max_y = 45 + (step % 2)
        if not has_left_shin:
            for ty in range(40, lift_max_y + 1):
                for tx in range(24 + ub_dx, 29 + ub_dx):
                    if leg_buf[ty, tx] == 0:
                        leg_buf[ty, tx] = 75
        if not has_right_shin:
            for ty in range(40, lift_max_y + 1):
                for tx in range(32 + ub_dx, 37 + ub_dx):
                    if leg_buf[ty, tx] == 0:
                        leg_buf[ty, tx] = 75

    # 3d. Shade Knee-Length Heavy Armor (ty=27..40) and Iron/Steel Shin Greaves & War Boots (ty=41..51)
    for ty in range(27, 52):
        sy_l = int(round((ty - 27) * 1.05))
        row_lv: List[Tuple[int, int]] = [(tx, int(leg_buf[ty, tx])) for tx in range(10, 50) if leg_buf[ty, tx] > 0]
        if not row_lv:
            continue
        segs: List[List[Tuple[int, int]]] = [[row_lv[0]]]
        for item in row_lv[1:]:
            if item[0] == segs[-1][-1][0] + 1:
                segs[-1].append(item)
            else:
                segs.append([item])
        for seg in segs:
            w_seg = len(seg)
            x_s, x_e = seg[0][0], seg[-1][0]
            mid_x = 0.5 * (x_s + x_e)
            half_w = max(1.0, 0.5 * w_seg)
            for tx, lv in seg:
                is_edge = (w_seg >= 3 and (tx == x_s or tx == x_e)) or (w_seg == 2 and tx == x_e)
                if is_edge:
                    out[ty, tx] = IDX_OUTLINE
                    continue
                nx_leg = (tx - mid_x) / half_w
                cyl_lit = math.sqrt(max(0.0, 1.0 - nx_leg * nx_leg)) * 0.75 + max(0.0, -nx_leg) * 0.25
                l_b = float(lum[lv])
                eff_l = max(l_b * 0.85, 0.34 + 0.54 * cyl_lit)
                tx_rel = tx - ub_dx

                # Check if this pixel is on the bottom knee hem of the heavy armored tasset (ty in 39..40)
                is_knee_hem = (ty == 40) or (ty in (38, 39) and leg_buf[ty + 1, tx] == 0)
                if is_knee_hem:
                    # Gleaming Brass / Crimson Knee-Guard Border (슬갑 하단 황동/주홍 테두리)
                    out[ty, tx] = _pick_ramp(
                        RAMP_CRIMSON if style == "gyeongbeongap_heavy" else RAMP_BRASS,
                        max(0.50, eff_l),
                        boost=0.18,
                    )
                elif ty <= 39:
                    # Knee-Length Heavy Armored Thigh Tassets (무릎까지 내려온 중장갑 갑상/하갑) matching upper body armor!
                    s_dy = ty - 27
                    if style == "dujeonggap_crimson":
                        if (tx_rel + s_dy) % 3 == 0 and (s_dy % 2 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, max(0.55, eff_l), boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, eff_l, boost=0.08)
                    elif style == "dujeonggap_blue":
                        if abs(tx_rel - 30) >= 5:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, eff_l, boost=0.08)
                        elif (tx_rel + s_dy) % 3 == 0 and (s_dy % 2 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, max(0.55, eff_l), boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_BLUE, eff_l, boost=0.06)
                    elif style == "dujeonggap_vanguard":
                        if abs(tx_rel - 30) >= 5:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, eff_l, boost=0.10)
                        elif (tx_rel + s_dy) % 3 == 0 and (s_dy % 2 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, max(0.55, eff_l), boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, eff_l, boost=0.08)
                    elif style == "gyeongbeongap_steel":
                        plate_mod = -0.06 if (s_dy % 2 == 1) else 0.08
                        if (s_dy % 3 == 0) and (tx_rel % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, eff_l, boost=0.12)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, eff_l, boost=0.08 + plate_mod)
                    elif style == "gyeongbeongap_heavy":
                        if (s_dy // 2) % 2 == 0:
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, eff_l, boost=0.14)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, eff_l, boost=0.10)
                elif ty == 41:
                    # Crimson/Brass Under-Knee Tie Band (행전끈 / 경갑 상단 끈)
                    out[ty, tx] = _pick_ramp(
                        RAMP_CRIMSON if "dujeonggap" in style else RAMP_BRASS,
                        max(0.48, eff_l),
                        boost=0.14,
                    )
                elif ty <= 46:
                    # Heavy Iron/Steel Shin Greaves (중장갑 철제 정강이 경갑)
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, max(0.46, eff_l), boost=0.12)
                else:
                    # Heavy Armored War Boots (중장갑 전투화 / 철제 목화)
                    out[ty, tx] = _pick_ramp(
                        RAMP_STEEL if eff_l > 0.64 else RAMP_DARK_IRON,
                        max(0.40, eff_l),
                        boost=0.08,
                    )

    # 5. Overlay 3ds Max Upper Body (Conical Helmet, Face, Pauldrons, Chest Armor, Waist Sash, and Upper-to-Mid Tassets dy <= 31)
    for ty in range(2, 36):
        sy = hy_top - 4 + (ty - ub_dy)
        if not (0 <= sy < gh):
            continue
        dy = sy - hy_top
        if dy > 31:
            continue

        row_lean = ub_dx
        if state == "move" and dy <= 15 and d in (0, 1, 2):
            row_lean -= 1

        if dy < 13:
            x_min, x_max = 21 + row_lean, 38 + row_lean
        elif dy <= 18:
            x_min, x_max = 23 + row_lean, 37 + row_lean  # Broad 3ds Max Shoulder Pauldrons (견철)
        elif dy <= 23:
            x_min, x_max = 25 + row_lean, 35 + row_lean  # Chest & Waist Sash (전대)
        else:
            x_min, x_max = 23 + row_lean, 37 + row_lean  # Heavy Armored Hip & Thigh Tassets (갑상: dy = 24..31)

        for tx in range(max(0, x_min), min(60, x_max + 1)):
            sx = hx_c - 30 + (tx - row_lean)
            if not (0 <= sx < gw):
                continue
            v = int(arr[sy, sx])
            if v == 0:
                continue
            if v == IDX_OUTLINE or tx == x_min or tx == x_max:
                out[ty, tx] = IDX_OUTLINE
                continue

            l_v = float(lum[v])
            is_blue = v in BLUE_SET_GK11
            is_red = v in RED_SET_GK11
            is_helmet = (dy <= 8) and (v in HELMET_SET_GK11 or v in RED_SET_GK11)
            tx_rel = tx - row_lean

            # A. 3ds Max Conical War Helmet (첨주 투구: dy <= 8)
            if is_helmet:
                if dy <= 1 and is_red:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.15)
                elif dy in (7, 8):
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.15)
                elif style == "dujeonggap_crimson":
                    if (tx_rel - 30) in (-3, 0, 3) and dy in (3, 5):
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)
                elif style == "dujeonggap_blue":
                    if (tx_rel - 30) in (-3, 0, 3) and dy in (4, 6):
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_DARK_IRON, l_v, boost=0.05)
                elif style == "dujeonggap_vanguard":
                    out[ty, tx] = _pick_ramp(RAMP_DARK_IRON, l_v, boost=0.05)
                elif style == "gyeongbeongap_steel":
                    if tx_rel == 30:
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.15)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.10)
                elif style == "gyeongbeongap_heavy":
                    out[ty, tx] = _pick_ramp(RAMP_BRASS if (tx_rel % 2 == 0) else RAMP_STEEL, l_v, boost=0.12)
                continue

            # B. 3ds Max Face (dy = 8..13 near center) & Neck Flaps (드림)
            if 8 <= dy <= 13:
                if d != 3 and abs(tx_rel - 29) <= 2 and v in FLESH_INDICES:
                    out[ty, tx] = v
                    continue
                if "gyeongbeongap" in style:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.05)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.05)
                continue

            # C. 3ds Max Torso, Pauldrons (견철), Sleeves, & Waist Sash (dy = 14..24)
            if 14 <= dy <= 24:
                if dy in (22, 23, 24) and is_red:
                    if abs(tx_rel - 30) <= 2 and dy == 23:
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                    elif "gyeongbeongap" in style:
                        out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.10)
                    else:
                        out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.10)
                    continue

                if style == "dujeonggap_blue":
                    if is_blue and abs(tx_rel - 30) <= 5:
                        if (dy % 3 == 1) and (tx_rel % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        if (dy % 3 == 0) and (tx_rel % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.20)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.06)

                elif style == "dujeonggap_crimson":
                    if is_blue and abs(tx_rel - 30) <= 2 and 16 <= dy <= 21:
                        if dy == 18 and abs(tx_rel - 30) <= 1:
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.25)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        if (dy % 3 == 1) and ((tx_rel + dy) % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)

                elif style == "dujeonggap_vanguard":
                    if is_blue and abs(tx_rel - 30) <= 2 and 16 <= dy <= 21:
                        out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    elif abs(tx_rel - 30) >= 4 or dy <= 16:
                        out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                    else:
                        if (dy % 3 == 0) and (tx_rel % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.05)

                elif style == "gyeongbeongap_steel":
                    if is_blue and abs(tx_rel - 30) <= 2 and 16 <= dy <= 21:
                        out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        plate_mod = -0.07 if (dy % 3 == 0) else (0.06 if ((tx_rel + dy) % 2 == 0) else 0.0)
                        if (dy % 3 == 0) and (tx_rel % 3 == 0):
                            out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.10)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08 + plate_mod)

                elif style == "gyeongbeongap_heavy":
                    if is_blue and abs(tx_rel - 30) <= 2 and 16 <= dy <= 21:
                        out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.05)
                    else:
                        if (dy // 2) % 2 == 0:
                            out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.12)
                        else:
                            out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                continue

            # D. Short Hip Tassets (갑상: dy = 25..26, leaving thighs & knees exposed for running/stance)
            s_dy = dy - 25
            if style == "dujeonggap_crimson":
                if (tx_rel + s_dy) % 3 == 0:
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.08)
            elif style == "dujeonggap_blue":
                if abs(tx_rel - 30) >= 5:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.06)
                elif tx_rel % 3 == 0:
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_BLUE, l_v, boost=0.04)
            elif style == "dujeonggap_vanguard":
                if abs(tx_rel - 30) >= 5:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)
                elif tx_rel % 3 == 0:
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.22)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_CRIMSON, l_v, boost=0.06)
            elif style == "gyeongbeongap_steel":
                plate_mod = -0.06 if (s_dy % 2 == 1) else 0.06
                out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08 + plate_mod)
            elif style == "gyeongbeongap_heavy":
                if s_dy % 2 == 0:
                    out[ty, tx] = _pick_ramp(RAMP_BRASS, l_v, boost=0.12)
                else:
                    out[ty, tx] = _pick_ramp(RAMP_STEEL, l_v, boost=0.08)

    # 6. Morphological interior pinhole fill STRICTLY on the upper torso (y = 6..30)
    #    so the transparent separation between the left and right legs (y >= 31) is NEVER filled!
    for _ in range(2):
        fill = out.copy()
        for y in range(6, 31):
            for x in range(18, 42):
                if out[y, x] == 0:
                    l, r = int(out[y, x - 1]), int(out[y, x + 1])
                    u, d_v = int(out[y - 1, x]), int(out[y + 1, x])
                    nbs = [v for v in (l, r, u, d_v) if v > 0 and v != IDX_OUTLINE]
                    if (l > 0 and r > 0 and u > 0 and d_v > 0) or len(nbs) >= 3:
                        fill[y, x] = nbs[0] if nbs else l
        out = fill

    return out


def get_arm_ramps(style: str) -> Tuple[List[int], List[int]]:
    """
    Return (upper_arm_ramp, bracer_ramp) where the upper sleeve (동달이 소매) contrasts with the
    chest armor and the forearm vambrace (팔뚝 완갑/토시) uses dark iron or steel so the warm flesh
    human hand (손) at the end of the arm stands out clearly instead of blending into yellow brass.
    """
    if style == "dujeonggap_crimson":
        return RAMP_BLUE, RAMP_DARK_IRON
    if style == "dujeonggap_blue":
        return RAMP_CRIMSON, RAMP_DARK_IRON
    if style == "dujeonggap_vanguard":
        return RAMP_BLUE, RAMP_STEEL
    if style == "gyeongbeongap_steel":
        return RAMP_CRIMSON, RAMP_DARK_IRON
    if style == "gyeongbeongap_heavy":
        return RAMP_BLUE, RAMP_STEEL
    return RAMP_CRIMSON, RAMP_DARK_IRON


def draw_3d_cyl_limb(
    canvas: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    ramp: List[int],
    radius: float = 1.0,
    outline: bool = True,
) -> None:
    """Render a natural human-proportioned 3D cylindrical limb segment with top-left lighting."""
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
    if outline:
        out_off = radius + 0.45
        for i in range(steps + 1):
            t = i / max(1, steps)
            cx_p = x0 + dx * t
            cy_p = y0 + dy * t
            # Subtle 1px dark contour on the shaded underside so arms stay slender and natural
            ix = int(round(cx_p - out_off * px))
            iy = int(round(cy_p - out_off * py))
            if 0 <= iy < canvas.shape[0] and 0 <= ix < canvas.shape[1] and canvas[iy, ix] == 0:
                canvas[iy, ix] = IDX_OUTLINE
    for i in range(steps + 1):
        t = i / max(1, steps)
        cx_p = x0 + dx * t
        cy_p = y0 + dy * t
        for off in (-0.85, -0.40, 0.0, 0.40, 0.85):
            if abs(off) > radius:
                continue
            ix = int(round(cx_p + off * px))
            iy = int(round(cy_p + off * py))
            if 0 <= iy < canvas.shape[0] and 0 <= ix < canvas.shape[1]:
                lit = 0.82 - 0.36 * (off / max(0.5, radius))
                canvas[iy, ix] = _pick_ramp(ramp, lit)


def solve_arm_elbow_ik(
    sx: int,
    sy: int,
    hx: int,
    hy: int,
    bend_side: int,
    bone_len: float = 4.4,
) -> Tuple[int, int]:
    """
    2-Bone Inverse Kinematics solver for the soldier's elbow (팔꿈치):
    Given shoulder (sx, sy) and hand grip (hx, hy), maintains natural upper-arm and forearm
    bone lengths (~4.4px each) so the elbow bends smoothly when coiled and extends on the strike.
    """
    dx = float(hx - sx)
    dy = float(hy - sy)
    dist = math.hypot(dx, dy)
    mx = 0.5 * (sx + hx)
    my = 0.5 * (sy + hy)
    if dist < 0.5:
        return int(round(mx + bend_side * 2.5)), int(round(my + 2.0))
    half_d = min(bone_len - 0.25, 0.5 * dist)
    bend_mag = math.sqrt(max(1.0, bone_len * bone_len - half_d * half_d))
    ux, uy = dx / dist, dy / dist
    n1x, n1y = -uy, ux
    n2x, n2y = uy, -ux
    pref_x = float(bend_side) * 0.85 if bend_side != 0 else -0.65
    pref_y = -0.45 if hy < sy - 2 else 0.65
    if (n1x * pref_x + n1y * pref_y) >= (n2x * pref_x + n2y * pref_y):
        nx, ny = n1x, n1y
    else:
        nx, ny = n2x, n2y
    ex = int(round(mx + bend_mag * nx))
    ey = int(round(my + bend_mag * ny))
    return ex, ey


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
    """
    Render an anatomical, tapered 3D human arm:
      - Upper arm sleeve (소매: shoulder -> elbow, radius=1.0)
      - Forearm bracer (토시/완갑: elbow -> wrist just behind hand, radius=0.80)
      - No artificial yellow hinge dot at the elbow!
    """
    draw_3d_cyl_limb(canvas, sx, sy, ex, ey, upper_ramp, radius=1.0, outline=True)
    # Taper forearm to wrist (stopping 0.8px short of hand center so the fist stays crisp)
    dx_f = hx - ex
    dy_f = hy - ey
    f_len = math.hypot(dx_f, dy_f)
    if f_len > 1.2:
        wx = int(round(hx - 0.8 * (dx_f / f_len)))
        wy = int(round(hy - 0.8 * (dy_f / f_len)))
    else:
        wx, wy = hx, hy
    draw_3d_cyl_limb(canvas, ex, ey, wx, wy, bracer_ramp, radius=0.80, outline=True)


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
    Direction-aware 3D 2-bone IK articulated arms connecting the anatomical Left & Right Shoulders
    via natural flexing elbows to the two weapon grip points (hand1_xy, hand2_xy).
    """
    upper_ramp, bracer_ramp = get_arm_ramps(style)
    shoulder_pairs = [
        ((cx - 4, cy - 8), (cx + 3, cy - 8), -1, 1),   # 0: SW
        ((cx - 3, cy - 8), (cx + 1, cy - 8), -1, 1),   # 1: W (side profile facing left)
        ((cx - 4, cy - 8), (cx + 2, cy - 8), -1, 1),   # 2: NW (three-quarter back-left)
        ((cx - 4, cy - 8), (cx + 4, cy - 8), -1, 1),   # 3: N
        ((cx - 4, cy - 8), (cx + 4, cy - 8), -1, 1),   # 4: S
    ]
    sh_l, sh_r, bend_l, bend_r = shoulder_pairs[d]

    d_direct = (
        (hand1_xy[0] - sh_l[0]) ** 2 + (hand1_xy[1] - sh_l[1]) ** 2
        + (hand2_xy[0] - sh_r[0]) ** 2 + (hand2_xy[1] - sh_r[1]) ** 2
    )
    d_swapped = (
        (hand2_xy[0] - sh_l[0]) ** 2 + (hand2_xy[1] - sh_l[1]) ** 2
        + (hand1_xy[0] - sh_r[0]) ** 2 + (hand1_xy[1] - sh_r[1]) ** 2
    )
    if d_direct <= d_swapped:
        lh, rh = hand1_xy, hand2_xy
    else:
        lh, rh = hand2_xy, hand1_xy

    el_l = solve_arm_elbow_ik(sh_l[0], sh_l[1], lh[0], lh[1], bend_l)
    el_r = solve_arm_elbow_ik(sh_r[0], sh_r[1], rh[0], rh[1], bend_r)

    if d in (0, 1, 2):
        draw_3d_arm_via_elbow(canvas, sh_l[0], sh_l[1], el_l[0], el_l[1], lh[0], lh[1], upper_ramp, bracer_ramp)
        draw_3d_arm_via_elbow(canvas, sh_r[0], sh_r[1], el_r[0], el_r[1], rh[0], rh[1], upper_ramp, bracer_ramp)
    else:
        draw_3d_arm_via_elbow(canvas, sh_r[0], sh_r[1], el_r[0], el_r[1], rh[0], rh[1], upper_ramp, bracer_ramp)
        draw_3d_arm_via_elbow(canvas, sh_l[0], sh_l[1], el_l[0], el_l[1], lh[0], lh[1], upper_ramp, bracer_ramp)


def apply_back_view_body_occlusion(
    canvas: np.ndarray,
    base: np.ndarray,
    ox: int,
    oy: int,
    b_dx: int,
    b_dy: int,
    cx: int,
    cy: int,
    d: int,
    style: str,
    is_overhead: bool = False,
    one_handed_sword: bool = False,
) -> None:
    """
    When viewing a soldier from behind (d=2 NW / engine-mirrored NE, and d=3 N),
    the weapon shaft, sword hilt, and hands are held IN FRONT OF the soldier's chest
    (further from the camera than the soldier's back armor, helmet, and legs).
    """
    if d not in (1, 2, 3):
        return
    th, tw = canvas.shape
    bh, bw = base.shape

    # 1. Remove any stray lower shaft butt or hilt tail in the waist/hip zone behind the soldier
    #    (keep y_clear_end <= cy + 2 so the wide running legs below cy + 2 are NEVER erased!)
    if not is_overhead:
        y_clear_start = max(0, cy + b_dy - 4)
        y_clear_end = min(th, cy + b_dy + 2)
        x_clear_start = max(0, cx + b_dx - 5)
        x_clear_end = min(tw, cx + b_dx + 6)
        canvas[y_clear_start:y_clear_end, x_clear_start:x_clear_end] = 0

    # 2. Composite the 3ds Max soldier body (helmet, back armor, waist, and running/planted legs) ON TOP OF the chest-front weapon
    by_start = 19 if is_overhead else 0
    for by in range(by_start, bh):
        for bx in range(bw):
            val = base[by, bx]
            if val == 0:
                continue
            ty, tx = by + oy, bx + ox
            if 0 <= ty < th and 0 <= tx < tw:
                canvas[ty, tx] = val

    # 3. Draw the outer 3D shoulder pauldrons / rear upper arms wrapping forward around the torso edges
    upper_ramp, _ = get_arm_ramps(style)
    if d == 1:
        sh_l = (cx + b_dx - 3, cy + b_dy - 8)
        el_l = (cx + b_dx - 5, cy + b_dy - 5)
        sh_r = (cx + b_dx + 2, cy + b_dy - 8)
        el_r = (cx + b_dx + 3, cy + b_dy - 5)
    elif d == 2:
        sh_l = (cx + b_dx - 4, cy + b_dy - 8)
        el_l = (cx + b_dx - 5, cy + b_dy - 6)
        sh_r = (cx + b_dx + 3, cy + b_dy - 8)
        el_r = (cx + b_dx + 4, cy + b_dy - 5)
    else:
        sh_l = (cx + b_dx - 4, cy + b_dy - 8)
        el_l = (cx + b_dx - 5, cy + b_dy - 5)
        sh_r = (cx + b_dx + 4, cy + b_dy - 8)
        el_r = (cx + b_dx + 5, cy + b_dy - 6)

    draw_3d_cyl_limb(canvas, sh_l[0], sh_l[1], el_l[0], el_l[1], upper_ramp, radius=0.95)
    if not one_handed_sword or d in (1, 2, 3):
        draw_3d_cyl_limb(canvas, sh_r[0], sh_r[1], el_r[0], el_r[1], upper_ramp, radius=0.95)

    # Restore central spine pixels of base so upper-arm cylinders only wrap the outer shoulder edges
    for by in range(max(18, by_start), bh):
        for bx in range(27, 34):
            val = base[by, bx]
            if val != 0:
                ty, tx = by + oy, bx + ox
                if 0 <= ty < th and 0 <= tx < tw:
                    canvas[ty, tx] = val


def draw_hand_wrapping_weapon(
    canvas: np.ndarray,
    gx: int,
    gy: int,
    ux: float,
    uy: float,
    cuff_col: int = IDX_GOLD_MID,
) -> None:
    """
    Draw a compact, natural 3D human fist (주먹 쥔 손) directly ON TOP OF the spear shaft or sword hilt at (gx, gy)
    with a 1px wrist cuff behind the knuckles and warm flesh fingers clasping around the weapon.
    """
    px, py = -uy, ux
    if px + py > 0:
        px, py = -px, -py  # Ensure (px, py) points toward top-left light source

    # 1. Subtle 1px dark contour on the shaded bottom-right side of the fist
    set_safe_pixel(canvas, int(round(gx - 1.3 * px)), int(round(gy - 1.3 * py)), IDX_OUTLINE)

    # 2. 1px wrist cuff slightly behind the knuckle
    wx = int(round(gx - 1.2 * ux))
    wy = int(round(gy - 1.2 * uy))
    set_safe_pixel(canvas, wx, wy, cuff_col)

    # 3. Compact 3D human knuckles & thumb/finger wrap across the shaft at (gx, gy)
    set_safe_pixel(canvas, gx, gy, 175)  # Warm lit flesh center knuckle
    set_safe_pixel(canvas, int(round(gx + 0.8 * ux)), int(round(gy + 0.8 * uy)), 176)  # Leading index knuckle
    set_safe_pixel(canvas, int(round(gx + 0.8 * px)), int(round(gy + 0.8 * py)), 176)  # Lit thumb wrap (top-left)
    set_safe_pixel(canvas, int(round(gx - 0.8 * px)), int(round(gy - 0.8 * py)), 20)   # Shaded finger wrap (bottom-right)


def seal_canvas_pinholes(canvas: np.ndarray, ox: int, oy: int) -> None:
    """Seal any 1x1 4-connected interior transparent pinholes inside (oy + 10 .. oy + 45)."""
    for _ in range(2):
        for y in range(oy + 10, oy + 45):
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
    state: str,
    d: int,
    step: int,
    cx: int,
    cy: int,
    rear_len: int,
    front_len: int,
    sway_scale: float = 1.0,
) -> Tuple[int, int, int, int, int, int, float, float]:
    """
    Compute (butt_x, butt_y, grip_x, grip_y, tip_x, tip_y, ux, uy) for a two-handed weapon
    so that in Idle the forearms move the hands (팔끝/손끝) along a living 8-step poise wave while
    the wrists pitch the blade/pole back and forth following the arm tip (팔끝을 따라서 검이 왔다갔다 함),
    in Move it sways rhythmically with the walk stride, and in Attack it thrusts/cleaves with the arms.
    """
    if state == "idle":
        gx_off, gy_off = IDLE_GRIP_OFFSETS[d]
        ux_b, uy_b = IDLE_DIR_VECTORS[d]
        dir_sign = 1.0 if d == 3 else -1.0
        wrist_rad = math.radians(dir_sign * IDLE_WRIST_DEG[step] * sway_scale)
        cw, sw = math.cos(wrist_rad), math.sin(wrist_rad)
        ux = ux_b * cw - uy_b * sw
        uy = ux_b * sw + uy_b * cw
        arm_dx = int(round(dir_sign * IDLE_ARM_DX[step] * sway_scale))
        arm_dy = int(round(IDLE_ARM_DY[step] * sway_scale))
        gx = cx + gx_off + arm_dx
        gy = cy + gy_off + arm_dy
    elif state == "move":
        gx_off, gy_off = MOVE_GRIP_OFFSETS[d]
        ux_b, uy_b = MOVE_DIR_VECTORS[d]
        # Dynamic 8-step athletic running (자연스러운 뜀박질) arm-tip pump & wrist pitch
        sway_rad = math.radians((-11.0, -5.0, 2.0, 9.0, 13.0, 6.0, -2.0, -7.0)[step] * sway_scale)
        cs, ss = math.cos(sway_rad), math.sin(sway_rad)
        ux = ux_b * cs - uy_b * ss
        uy = ux_b * ss + uy_b * cs
        stride = (-2.6, -1.3, 0.4, 2.0, 2.8, 1.3, -0.4, -1.8)[step] * sway_scale
        gx = int(round(cx + gx_off + stride * ux))
        gy = int(round(cy + gy_off + stride * uy))
    else:
        gx_off, gy_off = ATK_GRIP_OFFSETS[d]
        ux_b, uy_b = ATK_DIR_VECTORS[d]
        # Angular coil on wind-up (steps 0..1) and downward-forward drive on lunge (steps 3..5)
        coil_sign = -1.0 if d == 3 else 1.0
        coil_rad = math.radians(coil_sign * (5.0, 7.0, 0.0, -2.0, -3.0, -2.0, 0.0, 2.0)[step])
        cc, sc = math.cos(coil_rad), math.sin(coil_rad)
        ux = ux_b * cc - uy_b * sc
        uy = ux_b * sc + uy_b * cc
        # Physical two-handed pull-back (steps 0..1) and deep forward arm thrust (steps 2..5)
        thrust_shift = (-4.5, -6.0, 1.5, 6.5, 9.0, 6.5, 2.0, -1.5)[step]
        gx = int(round(cx + gx_off + thrust_shift * ux))
        gy = int(round(cy + gy_off + thrust_shift * uy))

    eff_rear_len = min(rear_len, 4) if d in (1, 2, 3) else rear_len
    eff_front_len = (front_len + 2) if d in (1, 2, 3) else front_len

    butt_x = int(round(gx - eff_rear_len * ux))
    butt_y = int(round(gy - eff_rear_len * uy))
    tip_x = int(round(gx + eff_front_len * ux))
    tip_y = int(round(gy + eff_front_len * uy))
    return butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy


# ---------------------------------------------------------------------------
# Unit Sprite Frame Builders
# ---------------------------------------------------------------------------

def build_dengpaesu_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    68x68, 168 frames for 등패수 (0x7A):
    - Blue dujeonggap with golden rivets
    - Angled isometric oval rattan shield (등패) on the shield arm with iron boss and dark rim
    - Crisp steel Hwando blade swaying with the moving sword hand/forearm in Idle/Move and slashing
      in a wide 2-bone IK arm-led 3D circular arc in Attack, with back-view torso occlusion in d=1,2,3.
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
                ty, tx = by + oy, bx + ox
                if not (0 <= ty < th and 0 <= tx < tw):
                    continue
                c[ty, tx] = val

        if state == "die":
            # Fallen 1.5x-scaled rattan shield (80~90cm diameter) and hwando beside corpse
            sx, sy = cx - 8 - step, cy + 10 + step // 2
            rx, ry = 9.0, 6.75
            draw_line_indices(c, cx + 2, cy + 8, cx + 14, cy + 12, IDX_STEEL_GLEAM, width=1)
            set_safe_pixel(c, cx + 2, cy + 8, IDX_GOLD_BRIGHT)
        else:
            # 1.5x-scaled 80~90cm Large Rattan Shield (대형 등패) held on the shield forearm
            shield_pos = [
                (cx - 7, cy + 1, 8.25, 10.2),  # 0: SW (1.5x of 5.5 x 6.8)
                (cx - 7, cy + 0, 7.50, 10.2),  # 1: W  (1.5x of 5.0 x 6.8)
                (cx - 7, cy - 3, 7.20, 9.3),   # 2: NW (1.5x of 4.8 x 6.2)
                (cx - 7, cy - 3, 6.75, 8.7),   # 3: N  (1.5x of 4.5 x 5.8)
                (cx + 7, cy + 1, 8.25, 10.2),  # 4: S  (1.5x of 5.5 x 6.8)
            ]
            sx, sy, rx, ry = shield_pos[d]
            sx += b_dx
            sy += b_dy
            if state == "idle":
                sx += (-1, 0, 0, 1, 1, 0, 0, -1)[step]
                sy += (0, 0, -1, -1, 0, 1, 1, 0)[step]
            elif state == "move":
                sx += (-1 if d == 4 else 1) * (-1, -1, 0, 1, 1, 1, 0, -1)[step]
            elif state == "attack":
                brace_dx = 1 if d == 4 else -1
                brace_dy = 1 if step in (2, 3, 4, 5) else 0
                sx += brace_dx
                sy += brace_dy

            # Connect shield shoulder to shield center via 3D arm
            sh_shield_x = cx + b_dx + (5 if d == 4 else -5)
            sh_shield_y = cy + b_dy - 9
            draw_3d_cyl_limb(c, sh_shield_x, sh_shield_y, int(sx), int(sy), upper_ramp, radius=1.05)

        # 1. Render 1.5x-scaled 3D convex hemisphere normal-shaded woven rattan shield (80~90cm 등패) FIRST
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
                        if nd >= 0.88:
                            c[py, px] = _pick_ramp(RAMP_BRASS, s_lit * 0.62, boost=-0.05) if s_lit > 0.45 else IDX_OUTLINE
                        elif nd <= 0.24:
                            c[py, px] = 255 if (dx_s <= 0 and dy_s <= 0 and nd <= 0.12) else _pick_ramp(RAMP_BRASS, s_lit, boost=0.25)
                        elif nd <= 0.33:
                            c[py, px] = _pick_ramp(RAMP_DARK_IRON, s_lit * 0.55)
                        elif 0.60 <= nd <= 0.72 and (abs(dx_s) <= 1 or abs(dy_s) <= 1):
                            # 4 radial brass reinforcing studs (사방 방패 두정) on the large 80~90cm shield
                            c[py, px] = _pick_ramp(RAMP_BRASS, max(0.65, s_lit), boost=0.22)
                        else:
                            ring_wave = 0.09 if (int(round(nd * 9.5)) % 2 == 0) else -0.07
                            weave_mod = 0.04 if ((dx_s + dy_s) % 2 == 0) else -0.04
                            c[py, px] = _pick_ramp(RAMP_BRASS, s_lit, boost=ring_wave + weave_mod)

        # 2. Render Hwando sword (환도) in sword hand ON TOP, with 2-bone IK articulated 3D sword arm and clasping hand
        if state != "die":
            sh_sword_x = cx + b_dx + (-4 if d == 4 else (2 if d in (1, 2) else 4))
            sh_sword_y = cy + b_dy - 8
            bend_side = -1 if d == 4 else 1

            if state == "attack":
                h_dx, h_dy, ang_deg = SWORD_SLASH_KEYFRAMES[d][step]
                # True 3D hand center for the Hwando sword arm
                hand_cx = cx + b_dx + (h_dx + 1 if d in (0, 1, 2) else h_dx)
                hand_cy = cy + b_dy + h_dy
                ang = math.radians(ang_deg)
                cos_a, sin_a = math.cos(ang), math.sin(ang)
                px_a, py_a = -sin_a, cos_a
                # Crossguard (hx, hy) sits 1.5px ahead of the fist center; pommel (butt) sits 2.5px behind
                hx = int(round(hand_cx + 1.5 * cos_a))
                hy = int(round(hand_cy + 1.5 * sin_a))
                blen = 17  # Constant 17px Hwando blade
                tx = int(round(hx + blen * cos_a))
                ty = int(round(hy + blen * sin_a))
                butt_len = 2.0 if (d in (2, 3) and step >= 2) else 2.5
                butt_x = int(round(hand_cx - butt_len * cos_a))
                butt_y = int(round(hand_cy - butt_len * sin_a))

                el_x, el_y = solve_arm_elbow_ik(sh_sword_x, sh_sword_y, hand_cx, hand_cy, bend_side)
                draw_3d_arm_via_elbow(c, sh_sword_x, sh_sword_y, el_x, el_y, hand_cx, hand_cy, upper_ramp, bracer_ramp)

                # Hwando hilt + brass pommel + disc guard (코등이)
                draw_line_indices(c, butt_x, butt_y, hx, hy, IDX_WOOD_DARK, width=1)
                set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
                mid_x = int(round(hx + (blen * 0.55) * cos_a + 1.1 * px_a))
                mid_y = int(round(hy + (blen * 0.55) * sin_a + 1.1 * py_a))
                draw_line_indices(c, hx, hy, tx, ty, IDX_STEEL_MID, width=2)
                draw_line_indices(c, hx, hy, mid_x, mid_y, IDX_STEEL_GLEAM, width=1)
                draw_line_indices(c, mid_x, mid_y, tx, ty, IDX_STEEL_GLEAM, width=1)
                # 3D Hand wrapping directly around the Hwando hilt + brass disc guard
                draw_hand_wrapping_weapon(c, hand_cx, hand_cy, cos_a, sin_a)
                set_safe_pixel(c, hx, hy, IDX_GOLD_BRIGHT)
                set_safe_pixel(c, tx, ty, IDX_STEEL_GLEAM)
            else:
                # In Idle and Move, the sword forearm moves the hand tip (팔끝/손끝) back and forth
                # and the wrist pitches the 17px Hwando blade along with the moving arm tip!
                s_sign = -1.0 if d == 4 else 1.0
                base_hand = [
                    (cx + 5, cy - 3, -72.0),   # 0: SW
                    (cx + 4, cy - 4, -75.0),   # 1: W
                    (cx + 3, cy - 5, -72.0),   # 2: NW (in front of chest)
                    (cx + 4, cy - 5, -70.0),   # 3: N  (in front of chest)
                    (cx - 5, cy - 3, -108.0),  # 4: S
                ]
                bhx, bhy, base_ang_deg = base_hand[d]
                if state == "idle":
                    arm_dx = int(round(s_sign * IDLE_ARM_DX[step]))
                    arm_dy = int(round(IDLE_ARM_DY[step]))
                    wrist_deg = s_sign * IDLE_WRIST_DEG[step] * 1.15
                else:
                    arm_dx = int(round(s_sign * (-2.5, -1.2, 0.5, 2.0, 2.5, 1.2, -0.5, -1.8)[step]))
                    arm_dy = (-1, -1, 0, 1, 1, 1, 0, -1)[step]
                    wrist_deg = s_sign * (-12.0, -6.0, 2.0, 9.0, 13.0, 6.0, -2.0, -8.0)[step]

                hand_cx = bhx + b_dx + arm_dx
                hand_cy = bhy + b_dy + arm_dy
                ang = math.radians(base_ang_deg + wrist_deg)
                ux_s, uy_s = math.cos(ang), math.sin(ang)
                px_a, py_a = -uy_s, ux_s
                hx = int(round(hand_cx + 1.5 * ux_s))
                hy = int(round(hand_cy + 1.5 * uy_s))
                blen = 17
                tx = int(round(hx + blen * ux_s))
                ty = int(round(hy + blen * uy_s))
                butt_x = int(round(hand_cx - 2.5 * ux_s))
                butt_y = int(round(hand_cy - 2.5 * uy_s))

                el_x, el_y = solve_arm_elbow_ik(sh_sword_x, sh_sword_y, hand_cx, hand_cy, bend_side)
                draw_3d_arm_via_elbow(c, sh_sword_x, sh_sword_y, el_x, el_y, hand_cx, hand_cy, upper_ramp, bracer_ramp)

                draw_line_indices(c, butt_x, butt_y, hx, hy, IDX_WOOD_DARK, width=1)
                set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
                mid_x = int(round(hx + (blen * 0.55) * ux_s + 1.0 * px_a))
                mid_y = int(round(hy + (blen * 0.55) * uy_s + 1.0 * py_a))
                draw_line_indices(c, hx, hy, tx, ty, IDX_STEEL_MID, width=2)
                draw_line_indices(c, hx, hy, mid_x, mid_y, IDX_STEEL_GLEAM, width=1)
                draw_line_indices(c, mid_x, mid_y, tx, ty, IDX_STEEL_GLEAM, width=1)
                draw_hand_wrapping_weapon(c, hand_cx, hand_cy, ux_s, uy_s)
                set_safe_pixel(c, hx, hy, IDX_GOLD_BRIGHT)
                set_safe_pixel(c, tx, ty, IDX_STEEL_GLEAM)

            if d in (2, 3):
                apply_back_view_body_occlusion(
                    c, base, ox, oy, b_dx, b_dy, cx, cy, d,
                    style="dujeonggap_blue",
                    is_overhead=(state == "attack" and step in (0, 1)),
                    one_handed_sword=True,
                )

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_ssangsudo_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    80x74, 168 frames for 쌍수도병 (0x7B):
    - Solid Team-Blue & Steel Gyeongbeongap lamellar armor
    - Two-Handed Greatsword (쌍수도) swaying with both moving arm tips in Idle/Move,
      and executing a wide 2-bone IK arm-led 3D elliptical cleave during Attack,
      with full back-view torso occlusion in d=1,2,3.
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
                ty, tx = by + oy, bx + ox
                if not (0 <= ty < th and 0 <= tx < tw):
                    continue
                c[ty, tx] = val

        if state == "die":
            draw_line_indices(c, cx - 17, cy + 12, cx - 6, cy + 12, IDX_WOOD_DARK, width=1)
            set_safe_pixel(c, cx - 17, cy + 12, IDX_GOLD_BRIGHT)
            set_safe_pixel(c, cx - 6, cy + 12, IDX_GOLD_BRIGHT)
            draw_line_indices(c, cx - 5, cy + 12, cx + 20, cy + 12, IDX_STEEL_GLEAM, width=2)
        elif state == "attack":
            # Full two-handed 3D elliptical arm-led greatsword cleave (1.2x scaled 양손 대도 회전 베기)
            # (hand_cx, hand_cy) is the true midpoint between the warrior's two hands at the tips of his arms!
            h_dx, h_dy, ang_deg = SWORD_SLASH_KEYFRAMES[d][step]
            hand_cx, hand_cy = cx + b_dx + h_dx, cy + b_dy + h_dy
            ang = math.radians(ang_deg)
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            px_a, py_a = -sin_a, cos_a

            # Two hands spaced cleanly along the greatsword handle so both hands & arms are distinct
            r_off = 1.8 if (d in (2, 3) and step >= 2) else 2.2
            f_off = 2.4
            r_hand = (int(round(hand_cx - r_off * cos_a)), int(round(hand_cy - r_off * sin_a)))
            f_hand = (int(round(hand_cx + f_off * cos_a)), int(round(hand_cy + f_off * sin_a)))
            butt_off = 2.8 if (d in (2, 3) and step >= 2) else 4.5
            butt_x = int(round(hand_cx - butt_off * cos_a))
            butt_y = int(round(hand_cy - butt_off * sin_a))
            gx = int(round(hand_cx + 3.8 * cos_a))
            gy = int(round(hand_cy + 3.8 * sin_a))
            blen = 27  # 1.2x scaled greatsword blade
            tip_x = int(round(gx + blen * cos_a))
            tip_y = int(round(gy + blen * sin_a))

            # Both 3D 2-bone IK arms connecting shoulders to the two grip positions on the greatsword hilt
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
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], cos_a, sin_a, cuff_col=IDX_STEEL_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], cos_a, sin_a, cuff_col=IDX_STEEL_HIGH)
            set_safe_pixel(c, tip_x, tip_y, IDX_STEEL_GLEAM)

            if d in (1, 2, 3):
                apply_back_view_body_occlusion(
                    c, base, ox, oy, b_dx, b_dy, cx, cy, d,
                    style="gyeongbeongap_steel",
                    is_overhead=(step in (0, 1)),
                )
        else:
            # Living two-handed shoulder/chest guard stance (1.2x scaled: rear_len=9, front_len=27 -> 36px total)
            butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy = get_polearm_pose(
                state, d, step, cx + b_dx, cy + b_dy, rear_len=9, front_len=27, sway_scale=1.0
            )
            px_a, py_a = -uy, ux
            f_hand = (int(round(gx - 1.5 * ux)), int(round(gy - 1.5 * uy)))
            r_hand = (int(round(gx - (3.8 if d in (1, 2, 3) else 5.5) * ux)), int(round(gy - (3.8 if d in (1, 2, 3) else 5.5) * uy)))

            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "gyeongbeongap_steel", d=d)
            draw_line_indices(c, butt_x, butt_y, gx, gy, IDX_WOOD_DARK, width=2)
            set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_BRIGHT)
            draw_line_indices(c, gx, gy, tip_x, tip_y, IDX_STEEL_MID, width=2)
            draw_line_indices(c, int(round(gx + px_a)), int(round(gy + py_a)), tip_x, tip_y, IDX_STEEL_GLEAM, width=1)
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_STEEL_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_STEEL_HIGH)
            set_safe_pixel(c, gx, gy, IDX_GOLD_BRIGHT)
            set_safe_pixel(c, tip_x, tip_y, IDX_STEEL_GLEAM)

            if d in (1, 2, 3):
                apply_back_view_body_occlusion(
                    c, base, ox, oy, b_dx, b_dy, cx, cy, d,
                    style="gyeongbeongap_steel",
                    is_overhead=False,
                )

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_jangchangsu_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    144x140, 168 frames for 장창수 (0x7C):
    - Crimson & Team-Blue Dujeonggap with golden rivets
    - Full 2x-length (70px~78px) 15-foot Joseon long spear (장창) held upright in Idle,
      diagonally across chest in Move, and physically pulled back & thrust deep by the hands/arms in Attack,
      with full back-view torso occlusion in d=1,2,3.
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
        b_dx, b_dy = get_upper_body_offset(state, d, step)
        base = clean_base_human(np.frombuffer(base_frames[f_idx], dtype=np.uint8).reshape((bh, bw)), f_idx)
        base = apply_joseon_armor(base, f_idx, style="dujeonggap_crimson")

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy, bx + ox
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
            # Rigid 70px spear length (52px front + 18px rear) while get_polearm_pose physically thrusts the hands/arms!
            if state == "attack":
                thrust = (step / 4.0) if step <= 4 else (1.0 - (step - 4) / 3.0)
                front_len = int(52 + 4 * thrust)
                rear_len = (10 if d == 4 else max(10, int(18 - 4 * thrust)))
            else:
                front_len = 52
                rear_len = 18

            butt_x, butt_y, gx, gy, tip_x, tip_y, ux, uy = get_polearm_pose(
                state, d, step, cx + b_dx, cy + b_dy, rear_len=rear_len, front_len=front_len, sway_scale=0.55
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
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_STEEL_MID)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_STEEL_MID)

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

            if d in (1, 2, 3):
                apply_back_view_body_occlusion(
                    c, base, ox, oy, b_dx, b_dy, cx, cy, d,
                    style="dujeonggap_crimson",
                    is_overhead=False,
                )

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_woldo_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    78x74, 168 frames for 월도병 (0x7D):
    - Heavy Gyeongbeongap with gold & steel lamellar rows
    - Authentic Joseon Crescent Halberd (월도) swaying with both moving arm tips in Idle/Move,
      and executing a wide 2-bone IK arm-led 3D elliptical sweep in Attack,
      with full back-view torso occlusion in d=1,2,3.
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
                ty, tx = by + oy, bx + ox
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
                gx, gy = cx + b_dx + h_dx, cy + b_dy + h_dy
                rear_len = 4 if (d in (2, 3) and step >= 2) else 9   # 1.2x scaled rear shaft
                shaft_len = 16  # 1.2x scaled front shaft
                butt_x = int(round(gx - rear_len * ux))
                butt_y = int(round(gy - rear_len * uy))
                collar_x = int(round(gx + shaft_len * ux))
                collar_y = int(round(gy + shaft_len * uy))
                r_hand = (int(round(gx - 2.4 * ux)), int(round(gy - 2.4 * uy)))
                f_hand = (int(round(gx + 3.4 * ux)), int(round(gy + 3.4 * uy)))
            else:
                # 1.2x scaled Idle/Move polearm pose (rear_len=10, front_len=18) with full arm-tip sway
                butt_x, butt_y, gx, gy, collar_x, collar_y, ux, uy = get_polearm_pose(
                    state, d, step, cx + b_dx, cy + b_dy, rear_len=10, front_len=18, sway_scale=1.0
                )
                r_hand = (int(round(gx - 3.2 * ux)), int(round(gy - 3.2 * uy)))
                f_hand = (int(round(gx + 4.2 * ux)), int(round(gy + 4.2 * uy)))

            perp_x, perp_y = -uy, ux

            # 0. Draw both 3D 2-bone IK articulated arms connecting shoulders to the two grip points on the Woldo pole
            draw_two_handed_arms(c, cx + b_dx, cy + b_dy, f_hand, r_hand, "gyeongbeongap_heavy", d=d)

            # 1. Wooden pole from rear butt through hands to dragon collar
            draw_line_indices(c, butt_x, butt_y, collar_x, collar_y, IDX_WOOD_DARK, width=2)
            draw_line_indices(c, butt_x, butt_y, collar_x, collar_y, IDX_WOOD_MID, width=1)
            set_safe_pixel(c, butt_x, butt_y, IDX_GOLD_MID)

            # 1b. Draw both 3D hands wrapping ON TOP OF the Woldo wooden pole
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_STEEL_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_STEEL_HIGH)

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

            if d in (1, 2, 3):
                apply_back_view_body_occlusion(
                    c, base, ox, oy, b_dx, b_dy, cx, cy, d,
                    style="gyeongbeongap_heavy",
                    is_overhead=(state == "attack" and step in (0, 1)),
                )

        seal_canvas_pinholes(c, ox, oy)
        frames.append(c)

    return frames


def build_nangseon_frames(base_frames: List[bytes]) -> List[np.ndarray]:
    """
    144x140, 168 frames for 낭선병 (0x7E):
    - Agile vanguard soldier in steel-shouldered Dujeonggap
    - Full 2x-length (66px~74px) multi-tier bamboo branch spear (낭선) held upright in Idle,
      diagonally across chest in Move, and physically pulled back & thrust deep by the hands/arms in Attack,
      with full back-view torso occlusion in d=1,2,3.
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
        b_dx, b_dy = get_upper_body_offset(state, d, step)
        base = clean_base_human(np.frombuffer(base_frames[f_idx], dtype=np.uint8).reshape((bh, bw)), f_idx)
        base = apply_joseon_armor(base, f_idx, style="dujeonggap_vanguard")

        for by in range(bh):
            for bx in range(bw):
                val = base[by, bx]
                if val == 0:
                    continue
                ty, tx = by + oy, bx + ox
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
                front_len = int(50 + 4 * thrust)
                rear_len = (10 if d == 4 else max(10, int(16 - 4 * thrust)))
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
                state, d, step, cx + b_dx, cy + b_dy, rear_len=rear_len, front_len=front_len, sway_scale=0.55
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
            draw_hand_wrapping_weapon(c, r_hand[0], r_hand[1], ux, uy, cuff_col=IDX_STEEL_HIGH)
            draw_hand_wrapping_weapon(c, f_hand[0], f_hand[1], ux, uy, cuff_col=IDX_STEEL_HIGH)

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

            if d in (1, 2, 3):
                apply_back_view_body_occlusion(
                    c, base, ox, oy, b_dx, b_dy, cx, cy, d,
                    style="dujeonggap_vanguard",
                    is_overhead=False,
                )

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
