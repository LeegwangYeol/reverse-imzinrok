"""
Procedural 3D Isometric Sprite Generator for '조선 왕벌' (Joseon Giant Hornet).

Generates an authentic Imjinrok 2+ Version 9 .spr file (74x74, 88 frames) with
row-aligned 0xFE RLE encoding and imjin2.pal color indices:
  - Frames 0..39  : Attack (5 directions [S, SW, W, NW, N] x 8 frames, hit at inst=5)
  - Frames 40..59 : Idle   (5 directions [S, SW, W, NW, N] x 4 frames)
  - Frames 60..79 : Move   (5 directions [S, SW, W, NW, N] x 4 frames)
  - Frames 80..87 : Die & Corpse (8 frames; Die=80..84, inst=4 -> frame 84 corpse on ground)
"""

from __future__ import annotations

import math
import shutil
import struct
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw

SPR_HEADER_SIZE = 3060
WIDTH = 74
HEIGHT = 74
FRAME_COUNT = 88

# Exact imjin2.pal indices verified from golddragon_online.spr, Tiger.Spr, fox.spr, bat_online.spr
IDX_TRANSPARENT = 0
IDX_OUTLINE = 228       # Dark translucent outline used by bat_online.spr & fox.spr (0xE4)

# Jet black / charcoal ramp (stripes, compound eyes, legs, stinger base)
IDX_BLACK_1 = 241       # RGB(16, 16, 16)
IDX_BLACK_2 = 242       # RGB(32, 32, 32)
IDX_BLACK_3 = 243       # RGB(48, 48, 48)
IDX_BLACK_4 = 244       # RGB(68, 68, 68)

# Golden-yellow ramp (hornet abdomen yellow bands)
IDX_GOLD_BRIGHT = 35    # RGB(228, 168, 36)
IDX_GOLD_HIGH = 41      # RGB(224, 160, 28)
IDX_GOLD_MID = 36       # RGB(212, 140, 24)
IDX_GOLD_WARM = 40      # RGB(212, 128, 20)
IDX_GOLD_SHADE = 215    # RGB(160, 104, 0)
IDX_GOLD_DARK = 214     # RGB(120, 84, 0)
IDX_GOLD_DEEP = 213     # RGB(76, 48, 0)

# Orange-amber ramp (hornet head & mandibles)
IDX_AMBER_BRIGHT = 35   # RGB(228, 168, 36)
IDX_AMBER_HIGH = 40     # RGB(212, 128, 20)
IDX_AMBER_MID = 44      # RGB(204, 112, 12)
IDX_AMBER_SHADE = 192   # RGB(108, 48, 4)
IDX_AMBER_DARK = 188    # RGB(60, 28, 0)

# Dark reddish-brown chitin ramp (hornet thorax)
IDX_THORAX_SPEC = 103   # RGB(128, 96, 52)
IDX_THORAX_HIGH = 192   # RGB(108, 48, 4)
IDX_THORAX_MID = 207    # RGB(96, 44, 4)
IDX_THORAX_LOW = 187    # RGB(72, 32, 0)
IDX_THORAX_DARK = 188   # RGB(60, 28, 0)
IDX_THORAX_DEEP = 191   # RGB(32, 12, 0)

# Translucent wing & stinger flash ramp
IDX_WING_BRIGHT = 255   # RGB(252, 252, 252)
IDX_WING_GLINT = 144    # RGB(208, 224, 240)
IDX_WING_LIGHT = 252    # RGB(204, 204, 204)
IDX_WING_MID = 250      # RGB(168, 168, 168)
IDX_WING_DARK = 248     # RGB(136, 136, 136)
IDX_WING_VEIN = 214     # RGB(120, 84, 0)
IDX_STING_FLASH = 70    # RGB(200, 200, 0) bright venom-yellow flash


def project_iso(x: float, y: float, z: float, cx: float, cy: float) -> Tuple[float, float, float]:
    """
    Project 3D world coordinates (x=right, y=forward-south, z=up) to 2D isometric screen (sx, sy, depth).
    Camera looks from South-Front at 35-degree elevation.
    """
    elev = math.radians(35.0)
    cos_e = math.cos(elev)
    sin_e = math.sin(elev)
    sx = cx + x
    sy = cy + y * cos_e - z * sin_e
    depth = y * sin_e + z * cos_e  # larger depth = closer to camera
    return sx, sy, depth


def rotate_z(x: float, y: float, z: float, yaw: float) -> Tuple[float, float, float]:
    c, s = math.cos(yaw), math.sin(yaw)
    return x * c - y * s, x * s + y * c, z


def rotate_local(
    lx: float, ly: float, lz: float, pitch: float, roll: float, yaw: float
) -> Tuple[float, float, float]:
    """
    Local coordinates:
      ly = forward (+ is head direction, - is abdomen direction)
      lx = right (+ is right side, - is left side)
      lz = dorsal up (+ is top, - is belly)
     pitch: positive tilts nose down (around X axis)
     roll : positive rolls right side down (around Y axis)
     yaw  : heading angle in world XY plane (0 = South/+Y, pi/2 = West/-X, pi = North/-Y)
    """
    # 1. Pitch around X
    cp, sp = math.cos(pitch), math.sin(pitch)
    y1 = ly * cp - lz * sp
    z1 = ly * sp + lz * cp
    x1 = lx

    # 2. Roll around Y
    cr, sr = math.cos(roll), math.sin(roll)
    x2 = x1 * cr + z1 * sr
    z2 = -x1 * sr + z1 * cr
    y2 = y1

    # 3. Yaw in world XY: yaw=0 -> facing South (world +Y, right=+X)
    # Wait: if facing South (+Y), local +ly maps to world +Y, and local +lx (hornet's right) maps to world -X (screen left)!
    # Let's verify: when a creature faces South (toward viewer), its right side is on viewer's left (-X).
    # When yaw = pi/2 (facing West / screen left -X):
    #   forward (+ly) -> world -X
    #   hornet's right (+lx) -> world -Y (North, away from camera)
    wx = -x2 * math.cos(yaw) - y2 * math.sin(yaw)
    wy = -x2 * math.sin(yaw) + y2 * math.cos(yaw)
    wz = z2
    return wx, wy, wz


def draw_ellipsoid(
    zbuf: np.ndarray,
    cbuf: np.ndarray,
    center_local: Tuple[float, float, float],
    radii: Tuple[float, float, float],
    pitch: float,
    roll: float,
    yaw: float,
    cx: float,
    cy: float,
    cz_offset: float,
    color_fn,
    body_bend_pitch: float = 0.0,
) -> None:
    """Render a 3D shaded ellipsoid in hornet local space onto (zbuf, cbuf)."""
    lx0, ly0, lz0 = center_local
    rx, ry, rz = radii

    # Sample dense 3D surface grid or bounding box in screen space
    # Since ellipsoids are small (radii 2..14 px), sampling spherical/volume points or inverse-mapping is fast.
    # Inverse mapping from 3D bounding box at 0.45px step guarantees zero holes!
    step = 0.45
    nx = max(3, int(math.ceil(2 * rx / step)))
    ny = max(3, int(math.ceil(2 * ry / step)))
    nz = max(3, int(math.ceil(2 * rz / step)))

    xs = np.linspace(-rx, rx, nx)
    ys = np.linspace(-ry, ry, ny)
    zs = np.linspace(-rz, rz, nz)

    # Light direction in world space (from top-left-front)
    lx_dir, ly_dir, lz_dir = -0.45, 0.35, 0.82
    l_norm = math.sqrt(lx_dir**2 + ly_dir**2 + lz_dir**2)
    lx_dir, ly_dir, lz_dir = lx_dir / l_norm, ly_dir / l_norm, lz_dir / l_norm

    cp_b, sp_b = math.cos(body_bend_pitch), math.sin(body_bend_pitch)

    for dy in ys:
        for dx in xs:
            r2_xy = (dx / rx) ** 2 + (dy / ry) ** 2
            if r2_xy > 1.0:
                continue
            # Only need top and bottom surface hemispheres (and a middle layer for watertightness)
            max_dz = rz * math.sqrt(max(0.0, 1.0 - r2_xy))
            for dz in (-max_dz, -0.5 * max_dz, 0.0, 0.5 * max_dz, max_dz):
                # Local normal on ellipsoid
                nx_l = dx / (rx * rx)
                ny_l = dy / (ry * ry)
                nz_l = dz / (rz * rz)
                n_len = math.sqrt(nx_l * nx_l + ny_l * ny_l + nz_l * nz_l) + 1e-8
                nx_l, ny_l, nz_l = nx_l / n_len, ny_l / n_len, nz_l / n_len

                # Apply local bend (for abdomen curl) around local X
                by = dy * cp_b - dz * sp_b
                bz = dy * sp_b + dz * cp_b
                bny = ny_l * cp_b - nz_l * sp_b
                bnz = ny_l * sp_b + nz_l * cp_b

                px_l = lx0 + dx
                py_l = ly0 + by
                pz_l = lz0 + bz

                wx, wy, wz = rotate_local(px_l, py_l, pz_l, pitch, roll, yaw)
                wnx, wny, wnz = rotate_local(nx_l, bny, bnz, pitch, roll, yaw)

                sx, sy, depth = project_iso(wx, wy, wz + cz_offset, cx, cy)
                ix, iy = int(round(sx)), int(round(sy))
                if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                    if depth >= zbuf[iy, ix]:
                        shade = max(0.0, min(1.0, wnx * lx_dir + wny * ly_dir + wnz * lz_dir))
                        col = color_fn(dx, dy, dz, shade)
                        if col != 0:
                            zbuf[iy, ix] = depth
                            cbuf[iy, ix] = col


def draw_segment_3d(
    zbuf: np.ndarray,
    cbuf: np.ndarray,
    p0: Tuple[float, float, float],
    p1: Tuple[float, float, float],
    radius: float,
    pitch: float,
    roll: float,
    yaw: float,
    cx: float,
    cy: float,
    cz_offset: float,
    col_high: int,
    col_dark: int,
) -> None:
    """Draw a 3D cylindrical limb/antenna/stinger segment in hornet local space."""
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
    steps = max(4, int(dist * 3.0))
    for i in range(steps + 1):
        t = i / steps
        lx = x0 + (x1 - x0) * t
        ly = y0 + (y1 - y0) * t
        lz = z0 + (z1 - z0) * t
        wx, wy, wz = rotate_local(lx, ly, lz, pitch, roll, yaw)
        sx, sy, depth = project_iso(wx, wy, wz + cz_offset, cx, cy)
        r_cur = radius * (1.0 - 0.25 * t)
        ir = max(1, int(math.ceil(r_cur)))
        for oy in range(-ir, ir + 1):
            for ox in range(-ir, ir + 1):
                if ox * ox + oy * oy <= r_cur * r_cur + 0.35:
                    ix, iy = int(round(sx)) + ox, int(round(sy)) + oy
                    if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                        d_adj = depth - 0.1 * (ox * ox + oy * oy)
                        if d_adj >= zbuf[iy, ix]:
                            zbuf[iy, ix] = d_adj
                            cbuf[iy, ix] = col_high if (oy <= 0 and ox <= 0) else col_dark


def draw_wing_3d(
    zbuf: np.ndarray,
    cbuf: np.ndarray,
    side: int,  # +1 for hornet's right wing, -1 for hornet's left wing
    wing_pair: int,  # 0 = forewing (large), 1 = hindwing (smaller)
    flap_angle: float,  # radians: +up, -down
    sweep_back: float,  # radians: swept toward abdomen
    pitch: float,
    roll: float,
    yaw: float,
    cx: float,
    cy: float,
    cz_offset: float,
) -> None:
    """Render translucent insect wing with dark leading vein and iridescent membrane."""
    length = 18.5 if wing_pair == 0 else 13.0
    chord = 5.4 if wing_pair == 0 else 4.0
    root_x = side * 3.2
    root_y = 1.5 if wing_pair == 0 else -1.2
    root_z = 3.6 if wing_pair == 0 else 3.0

    nu = 42
    nv = 16
    for iu in range(nu + 1):
        u = iu / nu  # 0 at root -> 1 at wingtip
        # Wing profile curve (tapers at root and tip)
        w_u = chord * math.sin(math.pi * (u ** 0.7))
        for iv in range(nv + 1):
            v = iv / nv  # 0 = leading edge -> 1 = trailing edge
            # Local wing plane before flap
            span_dist = u * length
            chord_dist = -v * w_u

            # Apply sweep and dihedral flap
            ca, sa = math.cos(flap_angle), math.sin(flap_angle)
            cs, ss = math.cos(sweep_back), math.sin(sweep_back)

            # Outward & backward sweep in XY
            wx_flat = side * (span_dist * cs + chord_dist * 0.25)
            wy_flat = -span_dist * ss + chord_dist * cs
            # Flap elevates wing along Z
            lx = root_x + wx_flat * ca
            ly = root_y + wy_flat
            lz = root_z + span_dist * sa - abs(chord_dist) * 0.15

            wx, wy, wz = rotate_local(lx, ly, lz, pitch, roll, yaw)
            sx, sy, depth = project_iso(wx, wy, wz + cz_offset, cx, cy)
            ix, iy = int(round(sx)), int(round(sy))
            if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                if depth >= zbuf[iy, ix]:
                    # Leading edge is a solid chitin vein
                    if v < 0.16:
                        zbuf[iy, ix] = depth
                        cbuf[iy, ix] = IDX_WING_VEIN if u < 0.8 else IDX_GOLD_HIGH
                    elif abs(v - 0.5) < 0.08 and u < 0.75:
                        # Median vein
                        zbuf[iy, ix] = depth
                        cbuf[iy, ix] = IDX_WING_DARK
                    else:
                        # Translucent membrane: stipple/shimmer pattern so it looks airy & translucent
                        if (ix + iy + int(flap_angle * 10)) % 2 == 0 or u > 0.85:
                            zbuf[iy, ix] = depth
                            if u > 0.7 and v < 0.45:
                                cbuf[iy, ix] = IDX_WING_BRIGHT
                            elif v < 0.45:
                                cbuf[iy, ix] = IDX_WING_GLINT
                            elif v < 0.75:
                                cbuf[iy, ix] = IDX_WING_LIGHT
                            else:
                                cbuf[iy, ix] = IDX_WING_MID


def render_hornet_frame(
    yaw: float,
    pitch: float,
    roll: float,
    flap_phase: float,
    abdomen_curl: float,
    lunge_forward: float,
    z_height: float,
    is_sting_flash: bool = False,
    is_dying_stage: int = 0,
) -> np.ndarray:
    """
    Render a single 74x74 8-bit indexed frame of '조선 왕벌' (Joseon Giant Hornet).
    """
    zbuf = np.full((HEIGHT, WIDTH), -1e9, dtype=np.float32)
    cbuf = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)

    # Center of canvas leaving Y=0..5 clear for the health bar (Head Y>=6)
    cx = 37.0
    cy = 31.0

    # Shift along facing direction for attack lunge
    wx_lunge, wy_lunge, wz_lunge = rotate_local(0.0, lunge_forward, 0.0, pitch, roll, yaw)
    cx_eff = cx + wx_lunge
    cy_eff = cy + wy_lunge * math.cos(math.radians(35.0))
    cz_eff = z_height + wz_lunge

    # 1. Abdomen color function: alternating vivid golden-yellow & jet-black bands!
    def abdomen_color(dx: float, dy: float, dz: float, shade: float) -> int:
        # dy goes from -10.5 (rear tip) to +10.5 (petiole/waist)
        # Create 4 bold yellow & black stripes along dy
        band_pos = (dy + 10.5) / 21.0  # 0.0 at stinger tip -> 1.0 at waist
        # Tip (0..0.12) dark, (0.12..0.30) GOLD, (0.30..0.44) BLACK, (0.44..0.64) GOLD, (0.64..0.78) BLACK, (0.78..0.94) GOLD, (0.94..1.0) BLACK
        is_gold = (0.11 <= band_pos < 0.31) or (0.43 <= band_pos < 0.65) or (0.77 <= band_pos < 0.94)
        if is_gold:
            if shade > 0.78:
                return IDX_GOLD_BRIGHT
            elif shade > 0.60:
                return IDX_GOLD_HIGH
            elif shade > 0.42:
                return IDX_GOLD_MID
            elif shade > 0.26:
                return IDX_GOLD_SHADE
            else:
                return IDX_GOLD_DARK
        else:
            if shade > 0.75:
                return IDX_BLACK_4
            elif shade > 0.50:
                return IDX_BLACK_3
            elif shade > 0.25:
                return IDX_BLACK_2
            else:
                return IDX_BLACK_1

    # 2. Thorax color function: armored dark reddish-brown/bronze chitin
    def thorax_color(dx: float, dy: float, dz: float, shade: float) -> int:
        # Golden collar stripe at front of pronotum (dy > 3.2)
        if dy > 3.2 and dz > 0.5:
            return IDX_GOLD_HIGH if shade > 0.5 else IDX_GOLD_SHADE
        if shade > 0.80:
            return IDX_THORAX_SPEC
        elif shade > 0.60:
            return IDX_THORAX_HIGH
        elif shade > 0.40:
            return IDX_THORAX_MID
        elif shade > 0.22:
            return IDX_THORAX_LOW
        else:
            return IDX_THORAX_DARK

    # 3. Head color function: fierce orange-amber head with glossy black compound eyes
    def head_color(dx: float, dy: float, dz: float, shade: float) -> int:
        # Compound eyes on left/right sides of head
        if abs(dx) > 2.1 and dy > -0.8 and dz > -1.2:
            return IDX_BLACK_4 if shade > 0.7 else (IDX_BLACK_2 if shade > 0.35 else IDX_BLACK_1)
        if shade > 0.75:
            return IDX_AMBER_BRIGHT
        elif shade > 0.52:
            return IDX_AMBER_HIGH
        elif shade > 0.30:
            return IDX_AMBER_MID
        else:
            return IDX_AMBER_SHADE

    # Abdomen center shifts forward/down when curled for stinging attack
    abd_y = -9.5 + 3.0 * math.sin(abdomen_curl)
    abd_z = -1.2 - 3.5 * math.sin(abdomen_curl)

    # Draw Abdomen (large, banded ovoid)
    draw_ellipsoid(
        zbuf,
        cbuf,
        center_local=(0.0, abd_y, abd_z),
        radii=(5.6, 9.8, 5.2),
        pitch=pitch,
        roll=roll,
        yaw=yaw,
        cx=cx_eff,
        cy=cy_eff,
        cz_offset=cz_eff,
        color_fn=abdomen_color,
        body_bend_pitch=abdomen_curl,
    )

    # Draw Venomous Stinger at the tip of the abdomen
    cp_b, sp_b = math.cos(abdomen_curl), math.sin(abdomen_curl)
    tip_base_y = abd_y - 9.2 * cp_b
    tip_base_z = abd_z - 9.2 * sp_b
    sting_len = 6.5 if is_sting_flash else 4.2
    tip_end_y = tip_base_y - sting_len * cp_b
    tip_end_z = tip_base_z - sting_len * sp_b
    draw_segment_3d(
        zbuf,
        cbuf,
        (0.0, tip_base_y, tip_base_z),
        (0.0, tip_end_y, tip_end_z),
        radius=1.3,
        pitch=pitch,
        roll=roll,
        yaw=yaw,
        cx=cx_eff,
        cy=cy_eff,
        cz_offset=cz_eff,
        col_high=IDX_WING_BRIGHT if is_sting_flash else IDX_GOLD_HIGH,
        col_dark=IDX_STING_FLASH if is_sting_flash else IDX_BLACK_1,
    )

    # Draw Thorax
    draw_ellipsoid(
        zbuf,
        cbuf,
        center_local=(0.0, 2.0, 0.8),
        radii=(4.6, 5.2, 4.4),
        pitch=pitch,
        roll=roll,
        yaw=yaw,
        cx=cx_eff,
        cy=cy_eff,
        cz_offset=cz_eff,
        color_fn=thorax_color,
    )

    # Draw Head
    draw_ellipsoid(
        zbuf,
        cbuf,
        center_local=(0.0, 7.6, 0.2),
        radii=(4.0, 3.3, 3.6),
        pitch=pitch,
        roll=roll,
        yaw=yaw,
        cx=cx_eff,
        cy=cy_eff,
        cz_offset=cz_eff,
        color_fn=head_color,
    )

    # Draw Mandibles (curved pincers under head) & Antennae
    for side in (-1, 1):
        # Mandible
        draw_segment_3d(
            zbuf,
            cbuf,
            (side * 1.8, 9.5, -1.8),
            (side * 0.6, 11.2, -2.8),
            radius=1.0,
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            cx=cx_eff,
            cy=cy_eff,
            cz_offset=cz_eff,
            col_high=IDX_AMBER_MID,
            col_dark=IDX_BLACK_1,
        )
        # Antenna (2 segments: scape + flagellum)
        ant_knee = (side * 2.6, 10.8, 2.6)
        ant_tip = (side * 5.2, 13.0, 1.4 + 0.6 * math.sin(flap_phase))
        draw_segment_3d(
            zbuf,
            cbuf,
            (side * 1.4, 9.2, 1.8),
            ant_knee,
            radius=0.8,
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            cx=cx_eff,
            cy=cy_eff,
            cz_offset=cz_eff,
            col_high=IDX_AMBER_HIGH,
            col_dark=IDX_BLACK_1,
        )
        draw_segment_3d(
            zbuf,
            cbuf,
            ant_knee,
            ant_tip,
            radius=0.75,
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            cx=cx_eff,
            cy=cy_eff,
            cz_offset=cz_eff,
            col_high=IDX_BLACK_3,
            col_dark=IDX_BLACK_1,
        )

    # Draw 6 Jointed Legs (3 pairs: front, mid, hind)
    leg_roots = [
        (3.2, 4.5, -2.0, 4.8, 6.2, -5.2, 4.0, 7.5, -8.5),    # Front leg
        (3.6, 1.5, -2.2, 6.2, 1.0, -5.5, 5.5, -0.5, -9.0),   # Mid leg
        (3.4, -1.8, -2.0, 6.0, -5.0, -5.8, 5.2, -8.8, -9.5), # Hind leg
    ]
    for side in (-1, 1):
        for li, (rx, ry, rz, kx, ky, kz, fx, fy, fz) in enumerate(leg_roots):
            if is_dying_stage >= 3:
                # Curled legs when lying dead on back
                kz_mod = kz * 0.4
                fz_mod = fz * 0.3
                kx_mod = kx * 0.75
                fx_mod = fx * 0.55
            else:
                leg_swing = 0.8 * math.sin(flap_phase + li)
                kz_mod, fz_mod = kz, fz + leg_swing
                kx_mod, fx_mod = kx, fx
            p_root = (side * rx, ry, rz)
            p_knee = (side * kx_mod, ky, kz_mod)
            p_foot = (side * fx_mod, fy, fz_mod)
            draw_segment_3d(
                zbuf,
                cbuf,
                p_root,
                p_knee,
                radius=1.05,
                pitch=pitch,
                roll=roll,
                yaw=yaw,
                cx=cx_eff,
                cy=cy_eff,
                cz_offset=cz_eff,
                col_high=IDX_THORAX_HIGH,
                col_dark=IDX_BLACK_1,
            )
            draw_segment_3d(
                zbuf,
                cbuf,
                p_knee,
                p_foot,
                radius=0.9,
                pitch=pitch,
                roll=roll,
                yaw=yaw,
                cx=cx_eff,
                cy=cy_eff,
                cz_offset=cz_eff,
                col_high=IDX_GOLD_MID,
                col_dark=IDX_BLACK_1,
            )

    # Draw 4 Translucent Wings (Forewings + Hindwings)
    for side in (-1, 1):
        if is_dying_stage >= 2:
            # Crumpled wings splayed on ground
            flap_fore = -0.35
            flap_hind = -0.45
            sweep_fore = 0.55
            sweep_hind = 0.75
        else:
            flap_fore = 0.62 * math.sin(flap_phase)
            flap_hind = 0.52 * math.sin(flap_phase - 0.6)
            sweep_fore = 0.28 + 0.12 * math.cos(flap_phase)
            sweep_hind = 0.52 + 0.10 * math.cos(flap_phase)

        draw_wing_3d(
            zbuf,
            cbuf,
            side=side,
            wing_pair=0,
            flap_angle=flap_fore,
            sweep_back=sweep_fore,
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            cx=cx_eff,
            cy=cy_eff,
            cz_offset=cz_eff,
        )
        draw_wing_3d(
            zbuf,
            cbuf,
            side=side,
            wing_pair=1,
            flap_angle=flap_hind,
            sweep_back=sweep_hind,
            pitch=pitch,
            roll=roll,
            yaw=yaw,
            cx=cx_eff,
            cy=cy_eff,
            cz_offset=cz_eff,
        )

    # Attack hit frame (inst=5): add venomous stinger strike burst in front of the hornet!
    if is_sting_flash:
        burst_local = (0.0, tip_end_y - 2.5 * cp_b, tip_end_z - 2.5 * sp_b)
        bwx, bwy, bwz = rotate_local(*burst_local, pitch, roll, yaw)
        bsx, bsy, bdepth = project_iso(bwx, bwy, bwz + cz_eff, cx_eff, cy_eff)
        ix0, iy0 = int(round(bsx)), int(round(bsy))
        for ray_angle in range(0, 360, 45):
            rad = math.radians(ray_angle)
            for r_step in range(1, 6):
                rx_p = ix0 + int(round(r_step * math.cos(rad)))
                ry_p = iy0 + int(round(r_step * math.sin(rad)))
                if 0 <= rx_p < WIDTH and 0 <= ry_p < HEIGHT:
                    cbuf[ry_p, rx_p] = IDX_WING_BRIGHT if r_step <= 2 else IDX_STING_FLASH

    # Add 1-pixel dark translucent outline (IDX_OUTLINE = 228) around non-zero pixels, matching bat_online.spr & fox.spr
    outlined = cbuf.copy()
    mask = cbuf != 0
    for dy_o, dx_o in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = np.zeros_like(mask)
        sy_src = slice(max(0, -dy_o), HEIGHT - max(0, dy_o))
        sx_src = slice(max(0, -dx_o), WIDTH - max(0, dx_o))
        sy_dst = slice(max(0, dy_o), HEIGHT - max(0, -dy_o))
        sx_dst = slice(max(0, dx_o), WIDTH - max(0, -dx_o))
        shifted[sy_dst, sx_dst] = mask[sy_src, sx_src]
        border = shifted & (~mask)
        outlined[border] = IDX_OUTLINE

    return outlined


def encode_frame_rle_row_aligned(canvas: np.ndarray) -> bytes:
    """
    Encode a (HEIGHT, WIDTH) uint8 array into Joymax Version 9 row-aligned 0xFE skip RLE.
    Every scanline ends exactly at x == WIDTH without crossing row boundaries.
    """
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
                    val = IDX_BLACK_4
                out.append(val)
                x += 1
    return bytes(out)


def build_hornet_spr_bytes() -> Tuple[bytes, List[np.ndarray]]:
    """
    Generate all 88 frames for Joseon Giant Hornet ('조선 왕벌') and pack into a Version 9 .spr container.
    Direction order for 5-direction sprites in Imjinrok 2+:
      dir 0: SOUTH       (yaw = 0.0)
      dir 1: SOUTH-WEST  (yaw = pi / 4)
      dir 2: WEST        (yaw = pi / 2)
      dir 3: NORTH-WEST  (yaw = 3 * pi / 4)
      dir 4: NORTH       (yaw = pi)
    """
    dir_yaws = [
        0.0,
        math.pi * 0.25,
        math.pi * 0.50,
        math.pi * 0.75,
        math.pi * 1.00,
    ]

    frames: List[np.ndarray] = []

    # 1. Frames 0..39: Attack (5 dirs x 8 frames, inst=5)
    # Hornets curl their striped abdomen underneath/forward and thrust their venomous stinger!
    atk_wing_phases = [0.2, 1.4, -1.1, 1.5, -1.2, 1.55, 0.0, -0.9]
    atk_pitches = [0.05, -0.15, -0.28, -0.35, -0.10, 0.22, 0.10, 0.02]
    atk_curls = [0.10, 0.35, 0.75, 1.15, 1.45, 1.65, 0.90, 0.30]
    atk_lunges = [0.0, -1.5, -2.5, -1.0, 2.5, 5.5, 2.5, 0.8]

    for yaw in dir_yaws:
        for f in range(8):
            canvas = render_hornet_frame(
                yaw=yaw,
                pitch=atk_pitches[f],
                roll=0.0,
                flap_phase=atk_wing_phases[f],
                abdomen_curl=atk_curls[f],
                lunge_forward=atk_lunges[f],
                z_height=2.0,
                is_sting_flash=(f == 5),
                is_dying_stage=0,
            )
            frames.append(canvas)

    # 2. Frames 40..59: Idle (5 dirs x 4 frames)
    idle_wing_phases = [1.35, 0.15, -1.25, 0.25]
    idle_z = [2.5, 1.5, 0.8, 1.8]
    for yaw in dir_yaws:
        for f in range(4):
            canvas = render_hornet_frame(
                yaw=yaw,
                pitch=-0.08,
                roll=0.0,
                flap_phase=idle_wing_phases[f],
                abdomen_curl=0.18,
                lunge_forward=0.0,
                z_height=idle_z[f],
                is_sting_flash=False,
                is_dying_stage=0,
            )
            frames.append(canvas)

    # 3. Frames 60..79: Move (5 dirs x 4 frames)
    move_wing_phases = [1.50, -0.10, -1.35, 0.30]
    move_z = [3.0, 2.0, 1.2, 2.2]
    for yaw in dir_yaws:
        for f in range(4):
            canvas = render_hornet_frame(
                yaw=yaw,
                pitch=0.26,  # tilted forward for fast flight
                roll=0.0,
                flap_phase=move_wing_phases[f],
                abdomen_curl=-0.10,  # abdomen streamlined behind
                lunge_forward=1.8,
                z_height=move_z[f],
                is_sting_flash=False,
                is_dying_stage=0,
            )
            frames.append(canvas)

    # 4. Frames 80..87: Die & Grounded Corpse (8 frames; Die uses 80..84 with inst=4 -> frame 84 corpse)
    die_specs = [
        # (yaw, pitch, roll, flap_phase, curl, z_height, stage)
        (math.pi * 0.25, -0.45, 0.45, 1.4, 0.5, 0.0, 1),     # 80: hit in air, jerks back
        (math.pi * 0.35, 0.55, 1.35, -0.6, 0.8, -8.0, 1),    # 81: tumbling down
        (math.pi * 0.42, 0.20, 2.35, -0.3, 1.0, -16.0, 2),   # 82: hits ground, rolling onto back
        (math.pi * 0.45, 0.05, 2.95, -0.4, 1.15, -20.0, 3),  # 83: upside-down on ground, legs twitch
        (math.pi * 0.45, 0.00, 3.10, -0.45, 1.25, -21.0, 4), # 84: CORPSE HOLD (inst=4) dead hornet on ground
        (math.pi * 0.45, 0.00, 3.10, -0.45, 1.25, -21.0, 4), # 85: corpse
        (math.pi * 0.45, 0.00, 3.10, -0.45, 1.25, -21.0, 4), # 86: corpse
        (math.pi * 0.45, 0.00, 3.10, -0.45, 1.25, -21.0, 4), # 87: corpse
    ]
    for yaw, pitch, roll, flap, curl, zh, stg in die_specs:
        canvas = render_hornet_frame(
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            flap_phase=flap,
            abdomen_curl=curl,
            lunge_forward=0.0,
            z_height=zh,
            is_sting_flash=False,
            is_dying_stage=stg,
        )
        frames.append(canvas)

    assert len(frames) == FRAME_COUNT

    # Pack into Version 9 .spr format (3060-byte header + RLE stream)
    encoded_streams: List[bytes] = []
    offsets: List[int] = []
    sizes_low16: List[int] = []
    cur_off = 0
    for f_canvas in frames:
        rle = encode_frame_rle_row_aligned(f_canvas)
        offsets.append(cur_off)
        sizes_low16.append(len(rle) & 0xFFFF)
        encoded_streams.append(rle)
        cur_off += len(rle)

    data_size = cur_off
    header = bytearray(SPR_HEADER_SIZE)
    struct.pack_into("<IIII", header, 0x000, 9, WIDTH, HEIGHT, FRAME_COUNT)
    struct.pack_into(f"<{FRAME_COUNT}I", header, 0x4C0, *offsets)
    struct.pack_into(f"<{FRAME_COUNT}H", header, 0x970, *sizes_low16)
    atlas_w = WIDTH * 8
    atlas_h = HEIGHT * ((FRAME_COUNT + 7) // 8)
    struct.pack_into("<III", header, 0xBC8, data_size, atlas_w, atlas_h)

    spr_bytes = bytes(header) + b"".join(encoded_streams)
    return spr_bytes, frames


def save_preview_sheet(frames: List[np.ndarray], pal_path: Path, out_png: Path) -> None:
    pal_raw = pal_path.read_bytes()
    scale = 4 if max(pal_raw[:768]) <= 63 else 1
    pal = [(pal_raw[i * 3] * scale, pal_raw[i * 3 + 1] * scale, pal_raw[i * 3 + 2] * scale) for i in range(256)]

    cols = 8
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (WIDTH * cols, HEIGHT * rows), (38, 42, 38))
    draw = ImageDraw.Draw(sheet)

    labels = {
        0: "ATK S",
        8: "ATK SW",
        16: "ATK W",
        24: "ATK NW",
        32: "ATK N",
        40: "IDLE S",
        44: "IDLE SW",
        48: "IDLE W",
        52: "IDLE NW",
        56: "IDLE N",
        60: "MOVE S",
        64: "MOVE SW",
        68: "MOVE W",
        72: "MOVE NW",
        76: "MOVE N",
        80: "DIE",
        84: "CORPSE",
    }

    for idx, arr in enumerate(frames):
        im = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        px = im.load()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                c = int(arr[y, x])
                if c != 0:
                    if c == IDX_OUTLINE:
                        px[x, y] = (18, 22, 18, 255)
                    else:
                        r, g, b = pal[c]
                        px[x, y] = (r, g, b, 255)
        gx, gy = (idx % cols) * WIDTH, (idx // cols) * HEIGHT
        sheet.paste(im, (gx, gy), im)
        lbl = f"{idx}" + (f" {labels[idx]}" if idx in labels else "")
        draw.text((gx + 2, gy + 2), lbl, fill=(255, 255, 120))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)


def install_hornet_spr(root_dir: Path) -> Path:
    spr_path = root_dir / "YM" / "dawn" / "char" / "joseon_wangbeol.spr"
    spr_bytes, _ = build_hornet_spr_bytes()
    spr_path.write_bytes(spr_bytes)
    return spr_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    spr_bytes, frames = build_hornet_spr_bytes()
    spr_out = install_hornet_spr(root)
    preview_out = Path(
        r"C:\Users\bpsco_93p6pse\.gemini\antigravity\brain\012fe533-910e-484f-9444-ed8db88cb5d7\joseon_wangbeol_88_frames_preview.png"
    )
    save_preview_sheet(frames, root / "YM" / "dawn" / "pal" / "imjin2.pal", preview_out)
    print(f"[OK] Wrote Joseon Giant Hornet SPR ({len(spr_bytes):,} bytes, 88 frames) -> {spr_out}")
    print(f"[OK] Saved 88-frame preview sheet -> {preview_out}")
