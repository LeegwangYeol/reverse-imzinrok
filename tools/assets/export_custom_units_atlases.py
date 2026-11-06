"""
export_custom_units_atlases.py - Exporter for 10 Custom Joseon Units (0x70~0x79)

Extracts and generates web atlas PNGs and meta JSONs for the 10 custom Joseon units
from YM/dawn/char/*.spr into web_prototype/assets/units/ and registers them in
web_prototype/assets/manifest.json.

Units:
- 0x70: 유생 (keon_1hs.Spr)
- 0x71: 검술 낭인 (SwordPirate_online.spr)
- 0x72: 조총 낭인 (GunPirate_online.spr)
- 0x73: 구미호 (fox.spr)
- 0x74: 조선왕벌 (bat_online.spr) - Air unit, 0 corpse decay
- 0x75: 조선 호랑이 (Tiger.Spr)
- 0x76: 털가면 (furheaddemon_online.spr)
- 0x77: 설녀 (snowwoman_online.spr)
- 0x78: 조선 도깨비 (oni_online.spr)
- 0x79: 불가살이 (starfish.spr)
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

# Ensure UTF-8 output on Windows consoles
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.assets.palette import Palette
from tools.assets.sprite_rle import SpriteDecoder

CUSTOM_JOSEON_UNITS = [
    {
        "id": "chosun_yusaeng",
        "alias_id": "keon_1hs",
        "name": "조선 유생",
        "kind_id": 0x70,
        "faction": "chosun",
        "cat": "unit",
        "file": "keon_1hs.Spr",
        "base_name": "keon_1hs",
        "is_air": False,
        "stats": {
            "move_speed": 18,
            "hp": 450,
            "mp": 100,
            "attack_power": 18,
            "attack_range": 4.5,
            "attack_delay": 26,
            "cost_crop": 250,
            "cost_tree": 0,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "die": {"start": 60, "total": 12, "corpse": 71},
            "idle": {"start": 72, "fDir": 12, "dirs": 5, "total": 60},
            "move": {"start": 132, "fDir": 8, "dirs": 5, "total": 40},
        },
    },
    {
        "id": "chosun_geomsul_nangin",
        "alias_id": "SwordPirate_online",
        "name": "검술 낭인",
        "kind_id": 0x71,
        "faction": "chosun",
        "cat": "unit",
        "file": "SwordPirate_online.spr",
        "base_name": "SwordPirate_online",
        "is_air": False,
        "stats": {
            "move_speed": 21,
            "hp": 600,
            "mp": 0,
            "attack_power": 25,
            "attack_range": 1.5,
            "attack_delay": 22,
            "cost_crop": 180,
            "cost_tree": 0,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "idle": {"start": 40, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 80, "fDir": 8, "dirs": 5, "total": 40},
            "die": {"start": 120, "total": 9, "corpse": 128},
        },
    },
    {
        "id": "chosun_jochong_nangin",
        "alias_id": "GunPirate_online",
        "name": "조총 낭인",
        "kind_id": 0x72,
        "faction": "chosun",
        "cat": "unit",
        "file": "GunPirate_online.spr",
        "base_name": "GunPirate_online",
        "is_air": False,
        "stats": {
            "move_speed": 18,
            "hp": 480,
            "mp": 0,
            "attack_power": 14,
            "attack_range": 6.5,
            "attack_delay": 32,
            "cost_crop": 240,
            "cost_tree": 0,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "idle": {"start": 40, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 80, "fDir": 8, "dirs": 5, "total": 40},
            "die": {"start": 120, "total": 9, "corpse": 128},
        },
    },
    {
        "id": "chosun_gumiho",
        "alias_id": "fox",
        "name": "구미호",
        "kind_id": 0x73,
        "faction": "chosun",
        "cat": "unit",
        "file": "fox.spr",
        "base_name": "fox",
        "is_air": False,
        "stats": {
            "move_speed": 22,
            "hp": 750,
            "mp": 150,
            "attack_power": 31,
            "attack_range": 1.8,
            "attack_delay": 24,
            "cost_crop": 280,
            "cost_tree": 50,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "idle": {"start": 40, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 80, "fDir": 8, "dirs": 5, "total": 40},
            "die": {"start": 120, "total": 17, "corpse": 136},
        },
    },
    {
        "id": "chosun_wangbeol",
        "alias_id": "bat_online",
        "name": "조선왕벌",
        "kind_id": 0x74,
        "faction": "chosun",
        "cat": "air",
        "file": "bat_online.spr",
        "base_name": "bat_online",
        "is_air": True,
        "stats": {
            "move_speed": 25,
            "hp": 500,
            "mp": 0,
            "attack_power": 26,
            "attack_range": 1.5,
            "attack_delay": 25,
            "cost_crop": 200,
            "cost_tree": 50,
        },
        "anim_spec": {
            "idle": {"start": 0, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 0, "fDir": 8, "dirs": 5, "total": 40},
            "atk": {"start": 72, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "die": {"start": 144, "total": 11, "corpse": None},
        },
    },
    {
        "id": "chosun_horangi",
        "alias_id": "Tiger",
        "name": "조선 호랑이",
        "kind_id": 0x75,
        "faction": "chosun",
        "cat": "unit",
        "file": "Tiger.Spr",
        "base_name": "Tiger",
        "is_air": False,
        "stats": {
            "move_speed": 24,
            "hp": 950,
            "mp": 0,
            "attack_power": 42,
            "attack_range": 1.6,
            "attack_delay": 24,
            "cost_crop": 300,
            "cost_tree": 0,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "idle": {"start": 40, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 80, "fDir": 8, "dirs": 5, "total": 40},
            "die": {"start": 120, "total": 10, "corpse": 129},
        },
    },
    {
        "id": "chosun_teolgamyeon",
        "alias_id": "furheaddemon_online",
        "name": "털가면",
        "kind_id": 0x76,
        "faction": "chosun",
        "cat": "unit",
        "file": "furheaddemon_online.spr",
        "base_name": "furheaddemon_online",
        "is_air": False,
        "stats": {
            "move_speed": 19,
            "hp": 700,
            "mp": 80,
            "attack_power": 28,
            "attack_range": 1.5,
            "attack_delay": 26,
            "cost_crop": 220,
            "cost_tree": 40,
        },
        "anim_spec": {
            "idle": {"start": 0, "fDir": 8, "dirs": 5, "total": 40},
            "atk": {"start": 40, "fDir": 8, "dirs": 5, "total": 40, "instant": 4},
            "move": {"start": 80, "fDir": 8, "dirs": 5, "total": 40},
            "die": {"start": 120, "total": 10, "corpse": 129},
        },
    },
    {
        "id": "chosun_seolnyeo",
        "alias_id": "snowwoman_online",
        "name": "설녀",
        "kind_id": 0x77,
        "faction": "chosun",
        "cat": "unit",
        "file": "snowwoman_online.spr",
        "base_name": "snowwoman_online",
        "is_air": False,
        "stats": {
            "move_speed": 20,
            "hp": 850,
            "mp": 200,
            "attack_power": 36,
            "attack_range": 5.5,
            "attack_delay": 28,
            "cost_crop": 280,
            "cost_tree": 60,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 13, "dirs": 5, "total": 65, "instant": 6},
            "die": {"start": 65, "total": 19, "corpse": 83},
            "idle": {"start": 84, "fDir": 10, "dirs": 5, "total": 50},
            "move": {"start": 134, "fDir": 10, "dirs": 5, "total": 50},
        },
    },
    {
        "id": "chosun_dokkaebi",
        "alias_id": "oni_online",
        "name": "조선 도깨비",
        "kind_id": 0x78,
        "faction": "chosun",
        "cat": "unit",
        "file": "oni_online.spr",
        "base_name": "oni_online",
        "is_air": False,
        "stats": {
            "move_speed": 17,
            "hp": 1100,
            "mp": 120,
            "attack_power": 40,
            "attack_range": 1.8,
            "attack_delay": 28,
            "cost_crop": 320,
            "cost_tree": 0,
        },
        "anim_spec": {
            "atk": {"start": 0, "fDir": 12, "dirs": 5, "total": 60, "instant": 6},
            "idle": {"start": 60, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 100, "fDir": 8, "dirs": 5, "total": 40},
            "die": {"start": 140, "total": 11, "corpse": 150},
        },
    },
    {
        "id": "chosun_bulgasari",
        "alias_id": "starfish",
        "name": "불가살이",
        "kind_id": 0x79,
        "faction": "chosun",
        "cat": "siege",
        "file": "starfish.spr",
        "base_name": "starfish",
        "is_air": False,
        "stats": {
            "move_speed": 15,
            "hp": 1400,
            "mp": 0,
            "attack_power": 46,
            "attack_range": 2.2,
            "attack_delay": 34,
            "cost_crop": 380,
            "cost_tree": 100,
        },
        "anim_spec": {
            "idle": {"start": 0, "fDir": 8, "dirs": 5, "total": 40},
            "move": {"start": 40, "fDir": 8, "dirs": 5, "total": 40},
            "atk": {"start": 80, "fDir": 16, "dirs": 5, "total": 80, "instant": 8},
            "die": {"start": 160, "total": 20, "corpse": 179},
        },
    },
]


def decode_and_export_unit(
    spr_path: Path,
    palette: Palette,
    units_dir: Path,
    base_name: str,
    unit_def: Dict[str, Any],
) -> Dict[str, Any]:
    """Decodes a sprite and generates an atlas PNG and meta JSON with exact animation boundaries."""
    units_dir.mkdir(parents=True, exist_ok=True)
    decoder = SpriteDecoder.from_file(spr_path)
    lut = palette.to_lut_array()

    decoded_images: List[Image.Image] = []
    frames_meta: List[Dict[str, Any]] = []

    for f_idx in range(decoder.frame_count):
        raw = decoder.decode_frame_raw(f_idx)
        rgba_buffer = lut[np.frombuffer(raw, dtype=np.uint8)].tobytes()
        img = Image.frombytes("RGBA", (decoder.width, decoder.height), rgba_buffer)
        decoded_images.append(img)

        hs_val = decoder.hotspot_raw[f_idx] if f_idx < len(decoder.hotspot_raw) else 0
        hs_x = hs_val if 0 < hs_val < decoder.width else decoder.width // 2
        hs_y = int(decoder.height * 0.78)

        frames_meta.append({
            "index": f_idx,
            "width": decoder.width,
            "height": decoder.height,
            "hotspot_x": hs_x,
            "hotspot_y": hs_y,
        })

    # Grid packing: 8 columns for standard 8/16 multiples, else 10 or 12
    if decoder.frame_count % 8 == 0:
        cols = 8
    elif decoder.frame_count % 10 == 0:
        cols = 10
    elif decoder.frame_count % 12 == 0:
        cols = 12
    else:
        cols = min(decoder.frame_count, 16)
    rows = math.ceil(decoder.frame_count / cols)

    atlas_w = cols * decoder.width
    atlas_h = rows * decoder.height
    atlas_img = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))

    for idx, f_img in enumerate(decoded_images):
        c = idx % cols
        r = idx // cols
        u = c * decoder.width
        v = r * decoder.height
        atlas_img.paste(f_img, (u, v))
        frames_meta[idx]["u"] = u
        frames_meta[idx]["v"] = v

    atlas_filename = f"{base_name}_atlas.png"
    atlas_img.save(units_dir / atlas_filename, "PNG")

    meta_doc = {
        "name": base_name,
        "kind_id": unit_def["kind_id"],
        "unit_id": unit_def["id"],
        "korean_name": unit_def["name"],
        "version": decoder.version,
        "width": decoder.width,
        "height": decoder.height,
        "frame_count": decoder.frame_count,
        "atlas_file": atlas_filename,
        "atlas_width": atlas_w,
        "atlas_height": atlas_h,
        "cols": cols,
        "rows": rows,
        "is_air": unit_def["is_air"],
        "anim_spec": unit_def["anim_spec"],
        "frames": frames_meta,
    }

    meta_filename = f"{base_name}_meta.json"
    with open(units_dir / meta_filename, "w", encoding="utf-8") as f:
        json.dump(meta_doc, f, indent=2, ensure_ascii=False)

    # Also generate lowercase alias files if base_name contains uppercase letters
    lower_name = base_name.lower()
    if lower_name != base_name:
        lower_atlas = f"{lower_name}_atlas.png"
        lower_meta = f"{lower_name}_meta.json"
        if not (units_dir / lower_atlas).exists():
            shutil.copy2(units_dir / atlas_filename, units_dir / lower_atlas)
        if not (units_dir / lower_meta).exists():
            shutil.copy2(units_dir / meta_filename, units_dir / lower_meta)

    return meta_doc


def export_custom_units():
    """Main routine to extract the 10 custom units and register in manifest.json."""
    ym_dir = PROJECT_ROOT / "YM" / "dawn"
    web_dir = PROJECT_ROOT / "web_prototype"
    units_dir = web_dir / "assets" / "units"
    manifest_path = web_dir / "assets" / "manifest.json"

    pal_path = ym_dir / "pal" / "imjin2.pal"
    if not pal_path.exists():
        pal_path = PROJECT_ROOT / "web_prototype" / "assets" / "palette" / "palette.json"
        palette = Palette.from_json(pal_path)
    else:
        palette = Palette.from_file(pal_path)

    print(f"[+] Loaded palette: {pal_path}")

    # Read existing manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if "units" not in manifest:
        manifest["units"] = {}

    exported_count = 0
    for u in CUSTOM_JOSEON_UNITS:
        spr_path = ym_dir / "char" / u["file"]
        if not spr_path.exists():
            # Try case-insensitive matching
            found = False
            for p in (ym_dir / "char").glob("*"):
                if p.name.lower() == u["file"].lower():
                    spr_path = p
                    found = True
                    break
            if not found:
                print(f"[-] Error: SPR file not found: {u['file']}")
                continue

        print(f"[+] Exporting {u['name']} (0x{u['kind_id']:02X}) from {spr_path.name}...")
        meta = decode_and_export_unit(spr_path, palette, units_dir, u["base_name"], u)

        unit_entry = {
            "id": u["id"],
            "name": u["name"],
            "faction": u["faction"],
            "category": u["cat"],
            "kind_id": u["kind_id"],
            "sprite_file": u["file"],
            "atlas": f"units/{meta['atlas_file']}",
            "meta": f"units/{u['base_name']}_meta.json",
            "frame_width": meta["width"],
            "frame_height": meta["height"],
            "frame_count": meta["frame_count"],
            "directions": 8,
            "is_air": u["is_air"],
            "isAirUnit": u["is_air"],
            "flightAltitude": 36 if u["is_air"] else 0,
            "hasGroundCorpse": not u["is_air"],
            "corpseDuration": 0.0 if u["is_air"] else 4.0,
            "stats": u["stats"],
            "anim_spec": u["anim_spec"],
        }

        # Register primary ID and alias
        manifest["units"][u["id"]] = unit_entry
        manifest["units"][u["alias_id"]] = unit_entry
        exported_count += 1

    # Save manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Successfully exported {exported_count} custom units and updated {manifest_path}")


if __name__ == "__main__":
    export_custom_units()
