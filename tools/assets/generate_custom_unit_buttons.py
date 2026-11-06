#!/usr/bin/env python3
"""
generate_custom_unit_buttons.py - Custom Joseon 10 Units (0x70~0x79) Button Generator

Extracts authentic in-game sprites for all 10 custom Joseon units:
  0x70: 유생 (Scholar with white robe & horsehair hat)
  0x71: 검술 낭인 (Ronin Swordsman with blade)
  0x72: 조총 낭인 (Ronin Musketeer with matchlock gun)
  0x73: 구미호 (Nine-Tailed Fox with tails)
  0x74: 조선왕벌 (Joseon Hornet giant bee with wings)
  0x75: 조선 호랑이 (Joseon Tiger with stripes)
  0x76: 털가면 (FurHead Demon with white fur mask)
  0x77: 설녀 (Snow Woman in winter kimono)
  0x78: 조선 도깨비 (Joseon Dokkaebi horned demon with club)
  0x79: 불가살이 (Bulgasari iron monster)

Decodes sprites with authentic palette (imjin2.pal), removes ground shadows
and selection rings, applies RTS 34x34 button frame and charcoal texture,
and produces buttons_manifest.json with full metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.assets.palette import Palette
from tools.assets.sprite_rle import SpriteDecoder

# ---------------------------------------------------------------------------
# Unit Definitions & Extraction Configurations
# ---------------------------------------------------------------------------
CUSTOM_JOSEON_UNITS: List[Dict[str, Any]] = [
    {
        "kind_id": 0x70,
        "kind_hex": "0x70",
        "id": "yusaeng",
        "name": "유생",
        "english_name": "Scholar",
        "description": "Scholar with white robe & horsehair hat",
        "spr_file": "YM/dawn/char/keon_1hs.Spr",
        "frame": 72,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "Y",
        "slot": 9,
        "building_id": "chosun_hq",
        "building_name": "조선 본영",
        "cost_rice": 250,
        "cost_potato": 0,
        "build_time": 6,
        "speed": 18,
        "attack_min": 15,
        "attack_max": 20,
        "hp": 450,
        "native_button_id": 0x44,
    },
    {
        "kind_id": 0x71,
        "kind_hex": "0x71",
        "id": "geomsul_nangin",
        "name": "검술 낭인",
        "english_name": "Ronin Swordsman",
        "description": "Ronin Swordsman with blade",
        "spr_file": "YM/dawn/char/SwordPirate_online.spr",
        "frame": 40,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "K",
        "slot": 8,
        "building_id": "chosun_barracks",
        "building_name": "조선 훈련소",
        "cost_rice": 180,
        "cost_potato": 0,
        "build_time": 5,
        "speed": 21,
        "attack_min": 22,
        "attack_max": 28,
        "hp": 600,
        "native_button_id": 0x45,
    },
    {
        "kind_id": 0x72,
        "kind_hex": "0x72",
        "id": "jochong_nangin",
        "name": "조총 낭인",
        "english_name": "Ronin Musketeer",
        "description": "Ronin Musketeer with matchlock gun",
        "spr_file": "YM/dawn/char/GunPirate_online.spr",
        "frame": 40,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "N",
        "slot": 9,
        "building_id": "chosun_barracks",
        "building_name": "조선 훈련소",
        "cost_rice": 240,
        "cost_potato": 0,
        "build_time": 6,
        "speed": 18,
        "attack_min": 12,
        "attack_max": 16,
        "hp": 480,
        "native_button_id": 0x46,
    },
    {
        "kind_id": 0x73,
        "kind_hex": "0x73",
        "id": "gumiho",
        "name": "구미호",
        "english_name": "Nine-Tailed Fox",
        "description": "Nine-Tailed Fox with tails",
        "spr_file": "YM/dawn/char/fox.spr",
        "frame": 50,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "F",
        "slot": 11,
        "building_id": "chosun_hq",
        "building_name": "조선 본영",
        "cost_rice": 280,
        "cost_potato": 50,
        "build_time": 7,
        "speed": 22,
        "attack_min": 28,
        "attack_max": 34,
        "hp": 750,
        "native_button_id": 0x47,
    },
    {
        "kind_id": 0x74,
        "kind_hex": "0x74",
        "id": "wangbeol",
        "name": "조선왕벌",
        "english_name": "Joseon Hornet",
        "description": "Joseon Hornet giant bee with wings",
        "spr_file": "YM/dawn/char/bat_online.spr",
        "frame": 0,
        "slice": slice(37, 63),  # Aerial hornet excluding ground shadow
        "upper_crop_h": None,
        "hotkey": "B",
        "slot": 7,
        "building_id": "chosun_stables",
        "building_name": "조선 목장/마구간",
        "cost_rice": 200,
        "cost_potato": 50,
        "build_time": 6,
        "speed": 25,
        "attack_min": 24,
        "attack_max": 28,
        "hp": 500,
        "native_button_id": 0x48,
    },
    {
        "kind_id": 0x75,
        "kind_hex": "0x75",
        "id": "horangi",
        "name": "조선 호랑이",
        "english_name": "Joseon Tiger",
        "description": "Joseon Tiger with stripes",
        "spr_file": "YM/dawn/char/Tiger.Spr",
        "frame": 40,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "T",
        "slot": 8,
        "building_id": "chosun_stables",
        "building_name": "조선 목장/마구간",
        "cost_rice": 300,
        "cost_potato": 0,
        "build_time": 7,
        "speed": 24,
        "attack_min": 38,
        "attack_max": 46,
        "hp": 950,
        "native_button_id": 0x49,
    },
    {
        "kind_id": 0x76,
        "kind_hex": "0x76",
        "id": "teolgamyeon",
        "name": "털가면",
        "english_name": "FurHead Demon",
        "description": "FurHead Demon with white fur mask",
        "spr_file": "YM/dawn/char/furheaddemon_online.spr",
        "frame": 0,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "M",
        "slot": 10,
        "building_id": "chosun_barracks",
        "building_name": "조선 훈련소",
        "cost_rice": 220,
        "cost_potato": 40,
        "build_time": 6,
        "speed": 19,
        "attack_min": 25,
        "attack_max": 32,
        "hp": 700,
        "native_button_id": 0x4A,
    },
    {
        "kind_id": 0x77,
        "kind_hex": "0x77",
        "id": "seolnyeo",
        "name": "설녀",
        "english_name": "Snow Woman",
        "description": "Snow Woman in winter kimono",
        "spr_file": "YM/dawn/char/snowwoman_online.spr",
        "frame": 84,
        "slice": slice(0, 115),  # Isolate kimono & ice crystals without ground ring
        "upper_crop_h": None,
        "hotkey": "S",
        "slot": 9,
        "building_id": "chosun_stables",
        "building_name": "조선 목장/마구간",
        "cost_rice": 280,
        "cost_potato": 60,
        "build_time": 7,
        "speed": 20,
        "attack_min": 32,
        "attack_max": 40,
        "hp": 850,
        "native_button_id": 0x4B,
    },
    {
        "kind_id": 0x78,
        "kind_hex": "0x78",
        "id": "dokkaebi",
        "name": "조선 도깨비",
        "english_name": "Joseon Dokkaebi",
        "description": "Joseon Dokkaebi horned demon with club",
        "spr_file": "YM/dawn/char/oni_online.spr",
        "frame": 60,
        "slice": None,
        "upper_crop_h": 76,  # Upper body to showcase horn, red torso & spiked club
        "hotkey": "D",
        "slot": 10,
        "building_id": "chosun_stables",
        "building_name": "조선 목장/마구간",
        "cost_rice": 320,
        "cost_potato": 0,
        "build_time": 7,
        "speed": 17,
        "attack_min": 36,
        "attack_max": 45,
        "hp": 1100,
        "native_button_id": 0x4C,
    },
    {
        "kind_id": 0x79,
        "kind_hex": "0x79",
        "id": "bulgasari",
        "name": "불가살이",
        "english_name": "Bulgasari",
        "description": "Bulgasari iron monster",
        "spr_file": "YM/dawn/char/starfish.spr",
        "frame": 0,
        "slice": None,
        "upper_crop_h": None,
        "hotkey": "U",
        "slot": 10,
        "building_id": "chosun_hq",
        "building_name": "조선 본영",
        "cost_rice": 380,
        "cost_potato": 100,
        "build_time": 8,
        "speed": 15,
        "attack_min": 40,
        "attack_max": 52,
        "hp": 1400,
        "native_button_id": 0x4D,
    },
]


# ---------------------------------------------------------------------------
# Sprite Cleaning and Button Creation Helpers
# ---------------------------------------------------------------------------
def clean_unit_sprite(
    spr_path: Path,
    frame: int,
    lut: np.ndarray,
    row_slice: Optional[slice] = None,
    upper_crop_h: Optional[int] = None,
) -> Image.Image:
    """Decodes a sprite frame, cleans selection dots and ground shadow, and crops tightly."""
    dec = SpriteDecoder.from_file(spr_path)
    raw = dec.decode_frame_raw(frame)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((dec.height, dec.width)).copy()

    # Mask selection ellipse green dots (palette indices 228..231)
    for c in [228, 229, 230, 231]:
        arr[arr == c] = 0

    # Apply row slice if specified
    if row_slice is not None:
        sliced = np.zeros_like(arr)
        sliced[row_slice, :] = arr[row_slice, :]
        arr = sliced

    # Mask ground shadow pixels (indices 241..251) in the bottom 15 rows
    non_zero_rows = np.where((arr != 0).any(axis=1))[0]
    if len(non_zero_rows) > 15:
        bottom_start = non_zero_rows[-12]
        for c in range(241, 252):
            arr[bottom_start:, :][arr[bottom_start:, :] == c] = 0

    rgba = lut[arr]
    im = Image.fromarray(rgba, "RGBA")
    bbox = im.getbbox()
    if not bbox:
        return im

    cropped = im.crop(bbox)
    if upper_crop_h is not None and cropped.height > upper_crop_h:
        cropped = cropped.crop((0, 0, cropped.width, upper_crop_h))

    return cropped


def render_34x34_button(
    subject_img: Image.Image,
    bg_color: Tuple[int, int, int, int] = (24, 22, 20, 255),
    border_highlight: Tuple[int, int, int, int] = (75, 70, 60, 255),
    border_shadow: Tuple[int, int, int, int] = (14, 12, 10, 255),
) -> Image.Image:
    """Renders a standard 34x34 RTS button matching button_plus_atlas aesthetics."""
    btn = Image.new("RGBA", (34, 34), bg_color)

    # 1. Textured charcoal inner background (32x32)
    for y in range(1, 33):
        for x in range(1, 33):
            noise = ((x * 7 + y * 13) % 5) - 2
            r = min(255, max(0, bg_color[0] + noise))
            g = min(255, max(0, bg_color[1] + noise))
            b = min(255, max(0, bg_color[2] + noise))
            btn.putpixel((x, y), (r, g, b, 255))

    # 2. Outer 1px beveled border
    for x in range(34):
        btn.putpixel((x, 0), border_highlight)
        btn.putpixel((x, 33), border_shadow)
    for y in range(34):
        btn.putpixel((0, y), border_highlight)
        btn.putpixel((33, y), border_shadow)

    # 3. Scale subject to fit 30x30 bounding box while preserving aspect ratio
    w, h = subject_img.size
    scale = min(30.0 / w, 30.0 / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    scaled = subject_img.resize((nw, nh), Image.LANCZOS)

    # Center inside 32x32 inner area (offset 1, 1)
    px = 1 + (32 - nw) // 2
    py = 1 + (32 - nh) // 2
    btn.paste(scaled, (px, py), scaled)

    return btn


# ---------------------------------------------------------------------------
# Core Generation Routine
# ---------------------------------------------------------------------------
def generate_custom_buttons(
    output_dir: Path,
    palette_path: Optional[Path] = None,
    generate_named_aliases: bool = True,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Generates all 10 custom Joseon unit buttons and buttons_manifest.json."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Palette (default: YM/dawn/pal/imjin2.pal)
    if palette_path is None:
        palette_path = PROJECT_ROOT / "YM" / "dawn" / "pal" / "imjin2.pal"
    if not palette_path.exists():
        fallback = PROJECT_ROOT / "YM" / "dawn" / "pal" / "00.pal"
        palette_path = fallback

    pal = Palette.from_file(palette_path)
    lut = np.array(pal.colors, dtype=np.uint8)

    manifest_units = []
    by_kind_hex = {}
    by_id = {}
    by_building: Dict[str, List[Dict[str, Any]]] = {
        "chosun_hq": [],
        "chosun_barracks": [],
        "chosun_stables": [],
    }

    if verbose:
        print(f"[+] Using palette: {palette_path}")
        print(f"[+] Output directory: {output_dir}")

    for u in CUSTOM_JOSEON_UNITS:
        spr_path = PROJECT_ROOT / u["spr_file"]
        if not spr_path.exists():
            raise FileNotFoundError(f"Missing required sprite file: {spr_path}")

        cleaned_spr = clean_unit_sprite(
            spr_path=spr_path,
            frame=u["frame"],
            lut=lut,
            row_slice=u["slice"],
            upper_crop_h=u["upper_crop_h"],
        )

        btn_img = render_34x34_button(cleaned_spr)

        # Primary canonical button file: btn_unit_0x70.png
        filename_hex = f"btn_unit_{u['kind_hex'].lower()}.png"
        path_hex = output_dir / filename_hex
        btn_img.save(path_hex, "PNG")

        # Named alias file: btn_unit_yusaeng.png
        filename_named = f"btn_unit_{u['id']}.png"
        if generate_named_aliases:
            path_named = output_dir / filename_named
            btn_img.save(path_named, "PNG")

        unit_meta = {
            "kind_id": u["kind_id"],
            "kind_hex": u["kind_hex"],
            "id": u["id"],
            "name": u["name"],
            "english_name": u["english_name"],
            "description": u["description"],
            "hotkey": u["hotkey"],
            "slot": u["slot"],
            "building_id": u["building_id"],
            "building_name": u["building_name"],
            "cost_rice": u["cost_rice"],
            "cost_potato": u["cost_potato"],
            "build_time": u["build_time"],
            "speed": u["speed"],
            "attack_min": u["attack_min"],
            "attack_max": u["attack_max"],
            "hp": u["hp"],
            "native_button_id": u["native_button_id"],
            "button_file": filename_hex,
            "button_alias": filename_named,
            "icon_url": f"assets/ui/buttons/{filename_hex}",
            "icon_alias_url": f"assets/ui/buttons/{filename_named}",
            "tooltip": f"{u['name']} [{u['hotkey']}] - 쌀: {u['cost_rice']}, 감자: {u['cost_potato']}",
        }

        manifest_units.append(unit_meta)
        by_kind_hex[u["kind_hex"]] = unit_meta
        by_id[u["id"]] = unit_meta
        by_building[u["building_id"]].append(unit_meta)

        if verbose:
            print(f"  [GEN] {u['kind_hex']} {u['name']} ({u['english_name']}) -> {filename_hex}")

    manifest_data = {
        "generator": "generate_custom_unit_buttons.py",
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "palette_used": str(palette_path),
        "total_units": len(manifest_units),
        "button_width": 34,
        "button_height": 34,
        "units": manifest_units,
        "by_kind_hex": by_kind_hex,
        "by_id": by_id,
        "by_building": by_building,
    }

    manifest_path = output_dir / "buttons_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"[+] Wrote manifest: {manifest_path}")

    return manifest_data


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate 34x34 RTS button PNGs and manifest for 10 custom Joseon units."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "web_prototype" / "assets" / "ui" / "buttons",
        help="Directory to save generated PNG buttons and buttons_manifest.json",
    )
    parser.add_argument(
        "--palette",
        "-p",
        type=Path,
        default=None,
        help="Path to palette file (.pal). Defaults to YM/dawn/pal/imjin2.pal",
    )
    parser.add_argument(
        "--no-aliases",
        action="store_true",
        help="Do not generate named alias PNG files (e.g. btn_unit_yusaeng.png)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress verbose log messages",
    )

    args = parser.parse_args()
    generate_custom_buttons(
        output_dir=args.output_dir,
        palette_path=args.palette,
        generate_named_aliases=not args.no_aliases,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
