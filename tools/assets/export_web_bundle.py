"""
export_web_bundle.py - Automated Game Asset Web Exporter for Imjinrok 2+ Dawn Web Prototype.

Converts proprietary Imjinrok 2+ assets (.spr, .ytl, .ypr, .pal, .YAV, .map)
into standard web-ready formats (PNG spritesheets, WAV audio, JSON metadata)
stored in web_prototype/assets/ with a unified manifest.json.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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

from tools.assets.audio import YAVAudio
from tools.assets.palette import Palette
from tools.assets.sprite_rle import SpriteDecoder
from tools.assets.tile_rle import TileDecoder
from tools.map.parser import MapData, parse_map
from tools.map.renderer import render_minimap_image


# ---------------------------------------------------------------------------
# Unit Definitions & Mappings (20 iconic units across 3 factions)
# ---------------------------------------------------------------------------
ICONIC_UNITS = [
    # Chosun Units, Heroes, and Buildings
    {
        "id": "chosun_farmer",
        "name": "조선 농부",
        "faction": "chosun",
        "cat": "unit",
        "file": "farmerk.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 1500,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 15,
            "cost_crop": 50,
            "cost_tree": 0,
        },
    },
    {
        "id": "chosun_spearman",
        "name": "조선 창병",
        "faction": "chosun",
        "cat": "unit",
        "file": "swordk.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 700,
            "attack_power": 12,
            "attack_range": 1,
            "attack_delay": 15,
            "cost_crop": 70,
            "cost_tree": 10,
        },
    },
    {
        "id": "chosun_archer",
        "name": "조선 궁수",
        "faction": "chosun",
        "cat": "unit",
        "file": "archerk.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 500,
            "attack_power": 10,
            "attack_range": 7,
            "attack_delay": 15,
            "cost_crop": 80,
            "cost_tree": 20,
        },
    },
    {
        "id": "chosun_turtleship",
        "name": "조선 거북선",
        "faction": "chosun",
        "cat": "naval",
        "file": "ashipk.spr",
        "base_stats": {
            "move_speed": 2,
            "hp": 3500,
            "attack_power": 15,
            "attack_range": 9,
            "attack_delay": 20,
            "cost_crop": 400,
            "cost_tree": 120,
        },
    },
    {
        "id": "chosun_yisunsin",
        "name": "조선 이순신",
        "faction": "chosun",
        "cat": "hero",
        "file": "generalk12.spr",
        "base_stats": {
            "move_speed": 7,
            "hp": 800,
            "attack_power": 35,
            "attack_range": 7,
            "attack_delay": 18,
            "cost_crop": 340,
            "cost_tree": 0,
        },
    },
    {
        "id": "chosun_gwakjaeu",
        "name": "조선 곽재우",
        "faction": "chosun",
        "cat": "hero",
        "file": "generalk31.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 2000,
            "attack_power": 25,
            "attack_range": 1,
            "attack_delay": 12,
            "cost_crop": 240,
            "cost_tree": 0,
        },
    },
    {
        "id": "chosun_hq",
        "name": "조선 본영",
        "faction": "chosun",
        "cat": "building",
        "file": "hqk.spr",
        "base_stats": {
            "move_speed": 0,
            "hp": 6000,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 0,
            "cost_crop": 400,
            "cost_tree": 200,
        },
    },
    {
        "id": "chosun_barracks",
        "name": "조선 훈련소",
        "faction": "chosun",
        "cat": "building",
        "file": "barrackk.spr",
        "base_stats": {
            "move_speed": 0,
            "hp": 3000,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 0,
            "cost_crop": 150,
            "cost_tree": 50,
        },
    },
    # Japan Units, Weapons, and Buildings
    {
        "id": "japan_farmer",
        "name": "일본 농부",
        "faction": "japan",
        "cat": "unit",
        "file": "farmerj.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 2500,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 15,
            "cost_crop": 50,
            "cost_tree": 0,
        },
    },
    {
        "id": "japan_samurai",
        "name": "일본 사무라이",
        "faction": "japan",
        "cat": "unit",
        "file": "swordj.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 800,
            "attack_power": 14,
            "attack_range": 1,
            "attack_delay": 14,
            "cost_crop": 80,
            "cost_tree": 10,
        },
    },
    {
        "id": "japan_ashigaru",
        "name": "일본 뎃뽀 아시가루",
        "faction": "japan",
        "cat": "unit",
        "file": "gunj1.spr",
        "base_stats": {
            "move_speed": 3,
            "hp": 450,
            "attack_power": 16,
            "attack_range": 8,
            "attack_delay": 20,
            "cost_crop": 90,
            "cost_tree": 30,
        },
    },
    {
        "id": "japan_flametank",
        "name": "일본 귀갑차",
        "faction": "japan",
        "cat": "siege",
        "file": "flametankj.spr",
        "base_stats": {
            "move_speed": 2,
            "hp": 1800,
            "attack_power": 18,
            "attack_range": 4,
            "attack_delay": 10,
            "cost_crop": 250,
            "cost_tree": 80,
        },
    },
    {
        "id": "japan_hq",
        "name": "일본 본영",
        "faction": "japan",
        "cat": "building",
        "file": "jhq.spr",
        "base_stats": {
            "move_speed": 0,
            "hp": 6000,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 0,
            "cost_crop": 400,
            "cost_tree": 200,
        },
    },
    {
        "id": "japan_barracks",
        "name": "일본 훈련소",
        "faction": "japan",
        "cat": "building",
        "file": "barrackj.spr",
        "base_stats": {
            "move_speed": 0,
            "hp": 3000,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 0,
            "cost_crop": 150,
            "cost_tree": 50,
        },
    },
    # Ming Units, Cavalry, and Buildings
    {
        "id": "ming_farmer",
        "name": "명 농부",
        "faction": "ming",
        "cat": "unit",
        "file": "farmerc.spr",
        "base_stats": {
            "move_speed": 4,
            "hp": 1500,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 15,
            "cost_crop": 50,
            "cost_tree": 0,
        },
    },
    {
        "id": "ming_spearman",
        "name": "명 창기병",
        "faction": "ming",
        "cat": "unit",
        "file": "swordc1.spr",
        "base_stats": {
            "move_speed": 5,
            "hp": 1000,
            "attack_power": 15,
            "attack_range": 2,
            "attack_delay": 16,
            "cost_crop": 100,
            "cost_tree": 30,
        },
    },
    {
        "id": "ming_gunner",
        "name": "명 화승총병",
        "faction": "ming",
        "cat": "unit",
        "file": "gunc.spr",
        "base_stats": {
            "move_speed": 3,
            "hp": 500,
            "attack_power": 18,
            "attack_range": 8,
            "attack_delay": 22,
            "cost_crop": 95,
            "cost_tree": 30,
        },
    },
    {
        "id": "ming_elephant",
        "name": "명 코끼리",
        "faction": "ming",
        "cat": "siege",
        "file": "elephantc1.spr",
        "base_stats": {
            "move_speed": 3,
            "hp": 2800,
            "attack_power": 22,
            "attack_range": 2,
            "attack_delay": 25,
            "cost_crop": 350,
            "cost_tree": 100,
        },
    },
    {
        "id": "ming_hq",
        "name": "명 본영",
        "faction": "ming",
        "cat": "building",
        "file": "hqc.spr",
        "base_stats": {
            "move_speed": 0,
            "hp": 6000,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 0,
            "cost_crop": 400,
            "cost_tree": 200,
        },
    },
    {
        "id": "ming_barracks",
        "name": "명 병부성",
        "faction": "ming",
        "cat": "building",
        "file": "barrackc.spr",
        "base_stats": {
            "move_speed": 0,
            "hp": 5000,
            "attack_power": 0,
            "attack_range": 0,
            "attack_delay": 0,
            "cost_crop": 150,
            "cost_tree": 50,
        },
    },
]

# ---------------------------------------------------------------------------
# Terrain, Resources, Maps, Audio, UI
# ---------------------------------------------------------------------------
TERRAIN_TILES = [
    {"name": "grss1", "type": "ytl", "file": "tile/normal/grss1.ytl"},
    {"name": "diff1", "type": "ytl", "file": "tile/normal/diff1.ytl"},
    {"name": "castle0", "type": "ytl", "file": "tile/normal/castle0.ytl"},
    {"name": "hill0", "type": "ypr", "file": "tile/normal/hill0.ypr"},
]

RESOURCES = [
    {"id": "crop0", "name": "potato", "korean": "감자", "file": "fnt/crop0.spr"},
    {"id": "crop1", "name": "rice", "korean": "벼/논", "file": "fnt/crop1.spr"},
    {"id": "tree0", "name": "tree", "korean": "나무", "file": "fnt/tree0.spr"},
]

REPRESENTATIVE_MAPS = [
    {"slug": "sea_of_cries", "file": "cusmap/(2인,70X70)함성이그치지않는바다.map"},
    {"slug": "taegeuk", "file": "cusmap/(2인,100x100)태극.map"},
    {"slug": "gyeongju_bibimbap", "file": "cusmap/(4인,120X120)경주비빔밥.map"},
    {"slug": "mugeuk", "file": "cusmap/(4인,140x140)무극.map"},
]

AUDIO_FILES = [
    # SFX
    {"key": "click", "cat": "sfx", "file": "eft/click.YAV"},
    {"key": "decidebuild", "cat": "sfx", "file": "eft/decidebuild.YAV"},
    {"key": "arrow1", "cat": "sfx", "file": "eft/arrow1.YAV"},
    {"key": "cannon1", "cat": "sfx", "file": "eft/cannon1.YAV"},
    {"key": "gun1", "cat": "sfx", "file": "eft/gun1.YAV"},
    {"key": "bigsword1", "cat": "sfx", "file": "eft/bigsword1.YAV"},
    {"key": "fire1", "cat": "sfx", "file": "eft/fire1.YAV"},
    {"key": "heal", "cat": "sfx", "file": "eft/heal.YAV"},
    {"key": "horsedie1", "cat": "sfx", "file": "eft/horsedie1.YAV"},
    {"key": "farmerjwork1", "cat": "sfx", "file": "eft/farmerjwork1.YAV"},
    # Voices
    {"key": "select_swordk0", "cat": "voice", "file": "tempeft/select_swordk0.yav"},
    {"key": "move_swordk0", "cat": "voice", "file": "tempeft/move_swordk0.yav"},
    {"key": "attack_swordk0", "cat": "voice", "file": "tempeft/attack_swordk0.yav"},
    {"key": "die_swordk0", "cat": "voice", "file": "tempeft/die_swordk0.yav"},
    # Music
    {"key": "startgame", "cat": "music", "file": "music/startgame.YAV"},
    {"key": "win", "cat": "music", "file": "music/win.YAV"},
    {"key": "lose", "cat": "music", "file": "music/lose.YAV"},
]

UI_SPRITES = [
    {"id": "mouse", "file": "fnt/mouse.spr"},
    {"id": "selectbox", "file": "fnt/selectbox.spr"},
    {"id": "movemark", "file": "fnt/movemark.spr"},
    {"id": "button_plus", "file": "fnt/button_plus.Spr"},
    {"id": "Back", "file": "BattleSpr/Back.Spr"},
    {"id": "BattleButton", "file": "BattleSpr/BattleButton.spr"},
]


# ---------------------------------------------------------------------------
# Sprite Decoder with Dynamic Grid Atlas
# ---------------------------------------------------------------------------
def decode_sprite_with_atlas(
    spr_path: Path,
    palette: Palette,
    out_dir: Path,
    base_name: str,
    export_frames: bool = False,
) -> Dict[str, Any]:
    """Decodes a Version 9 sprite and guarantees a valid atlas PNG even when atlas_w == 0."""
    out_dir.mkdir(parents=True, exist_ok=True)
    decoder = SpriteDecoder.from_file(spr_path)
    lut = palette.to_lut_array()

    decoded_images: List[Image.Image] = []
    frames_meta: List[Dict[str, Any]] = []

    for f_idx in range(decoder.frame_count):
        raw = decoder.decode_frame_raw(f_idx)
        rgba_buffer = lut[np.frombuffer(raw, dtype=np.uint8)].tobytes()
        img = Image.frombytes("RGBA", (decoder.width, decoder.height), rgba_buffer)
        decoded_images.append(img)

        frame_file: Optional[str] = None
        if export_frames:
            frame_file = f"{base_name}_frame_{f_idx:03d}.png"
            img.save(out_dir / frame_file, "PNG")

        hs_val = decoder.hotspot_raw[f_idx] if f_idx < len(decoder.hotspot_raw) else 0
        hs_x = hs_val if 0 < hs_val < decoder.width else decoder.width // 2
        hs_y = decoder.height // 2

        frames_meta.append({
            "index": f_idx,
            "width": decoder.width,
            "height": decoder.height,
            "hotspot_x": hs_x,
            "hotspot_y": hs_y,
            "file": frame_file,
        })

    # Determine Atlas Grid:
    # If header defines valid atlas_width and atlas_height, respect it.
    # If 0x0 (e.g., swordk, jhq, hqc, button_plus), dynamically calculate grid:
    # 8 columns for 8-directional sprites, otherwise min(frame_count, 16) cols.
    if decoder.atlas_width > 0 and decoder.atlas_height > 0:
        cols = decoder.atlas_width // decoder.width
        rows = decoder.atlas_height // decoder.height
        if cols <= 0 or rows <= 0 or cols * rows < decoder.frame_count:
            cols = 8 if decoder.frame_count % 8 == 0 else 10
            rows = math.ceil(decoder.frame_count / cols)
    else:
        cols = 8 if decoder.frame_count % 8 == 0 else min(decoder.frame_count, 16)
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
    atlas_img.save(out_dir / atlas_filename, "PNG")

    meta_doc = {
        "name": base_name,
        "version": decoder.version,
        "width": decoder.width,
        "height": decoder.height,
        "frame_count": decoder.frame_count,
        "atlas_file": atlas_filename,
        "atlas_width": atlas_w,
        "atlas_height": atlas_h,
        "cols": cols,
        "rows": rows,
        "frames": frames_meta,
    }

    meta_filename = f"{base_name}_meta.json"
    with open(out_dir / meta_filename, "w", encoding="utf-8") as f:
        json.dump(meta_doc, f, indent=2, ensure_ascii=False)

    return meta_doc


# ---------------------------------------------------------------------------
# Tile Decoder Helper
# ---------------------------------------------------------------------------
def decode_tile_asset(
    tile_path: Path,
    palette: Palette,
    out_dir: Path,
    base_name: str,
    tile_type: str = "ytl",
) -> Dict[str, Any]:
    """Decodes a terrain tile (.ytl or .ypr) to atlas and metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(tile_path, "rb") as f:
        data = f.read()

    decoder = TileDecoder(data, name=base_name, tile_type=tile_type)
    meta = decoder.export(out_dir, palette=palette, export_atlas=True, export_frames=False)
    return meta.to_dict()


# ---------------------------------------------------------------------------
# Map Exporter Helper
# ---------------------------------------------------------------------------
def export_map_asset(map_path: Path, out_dir: Path, slug: str) -> Dict[str, Any]:
    """Parses .map binary to structured JSON and 2D radar minimap PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    map_data = parse_map(map_path)

    # Pre-render 2D radar minimap image (400x400)
    minimap_img = render_minimap_image(map_data, width=400, height=400)
    minimap_file = f"{slug}_minimap.png"
    minimap_img.save(out_dir / minimap_file, "PNG")

    # Extract 1D arrays for web canvas rendering
    w, h = map_data.width, map_data.height
    tile_layer_1 = [map_data.get_tile(1, x, y) for y in range(h) for x in range(w)]
    tile_layer_2 = [map_data.get_tile(2, x, y) for y in range(h) for x in range(w)]
    tile_layer_3 = [map_data.get_tile(3, x, y) for y in range(h) for x in range(w)]
    walkability = [map_data.get_walkability(x, y) for y in range(h) for x in range(w)]
    elevation = [map_data.get_elevation(x, y) for y in range(h) for x in range(w)]
    terrain_type = [map_data.get_terrain_type(x, y) for y in range(h) for x in range(w)]

    resources = [r.to_dict() for r in map_data.get_all_resources()]
    buildings = [b.to_dict() for b in map_data.get_all_buildings()]
    starts = [ps.to_dict() for ps in map_data.get_active_player_starts()]

    map_doc = {
        "slug": slug,
        "name": map_path.stem,
        "version": map_data.version,
        "width": w,
        "height": h,
        "num_players": map_data.num_players,
        "theme_id": map_data.theme_id,
        "theme_name": map_data.theme_name,
        "minimap_image": f"maps/{minimap_file}",
        "player_starts": starts,
        "resources": resources,
        "buildings": buildings,
        "layers": {
            "tile1": tile_layer_1,
            "tile2": tile_layer_2,
            "tile3": tile_layer_3,
            "walkability": walkability,
            "elevation": elevation,
            "terrain_type": terrain_type,
        },
    }

    json_file = f"{slug}.json"
    with open(out_dir / json_file, "w", encoding="utf-8") as f:
        json.dump(map_doc, f, indent=2, ensure_ascii=False)

    return {
        "slug": slug,
        "name": map_path.stem,
        "file": f"maps/{json_file}",
        "minimap": f"maps/{minimap_file}",
        "width": w,
        "height": h,
        "players": map_data.num_players,
        "theme": map_data.theme_name,
        "total_resources": len(resources),
        "total_buildings": len(buildings),
    }


# ---------------------------------------------------------------------------
# Audio Exporter Helper
# ---------------------------------------------------------------------------
def export_audio_asset(yav_path: Path, out_dir: Path, key: str) -> Dict[str, Any]:
    """Converts a .YAV file to standard playable RIFF .wav."""
    out_dir.mkdir(parents=True, exist_ok=True)
    audio = YAVAudio.from_file(yav_path)
    if not audio.verify_with_wave():
        raise ValueError(f"WAV verification failed for {yav_path}")

    wav_filename = f"{key}.wav"
    audio.save_wav(out_dir / wav_filename)

    return {
        "key": key,
        "file": f"audio/{wav_filename}",
        "channels": audio.channels,
        "sample_rate": audio.sample_rate,
        "bits_per_sample": audio.bits_per_sample,
        "duration_seconds": round(audio.duration_seconds, 2),
        "data_size": audio.data_size,
    }


# ---------------------------------------------------------------------------
# Bundle Integrity Verifier
# ---------------------------------------------------------------------------
def verify_web_bundle(out_dir: Path, verbose: bool = True) -> bool:
    """Performs deep verification of all files in web_prototype/assets/."""
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        if verbose:
            print("[-] Manifest not found:", manifest_path)
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    errors: List[str] = []
    file_count = 0
    total_bytes = 0

    def check_file(rel_path: str, kind: str) -> bool:
        nonlocal file_count, total_bytes
        full_p = out_dir / rel_path
        if not full_p.exists():
            errors.append(f"Missing file: {rel_path}")
            return False
        sz = full_p.stat().st_size
        if sz == 0:
            errors.append(f"Empty file: {rel_path}")
            return False
        file_count += 1
        total_bytes += sz

        # Verify internal integrity
        if kind == "image":
            try:
                with Image.open(full_p) as im:
                    im.verify()
            except Exception as e:
                errors.append(f"Corrupt PNG {rel_path}: {e}")
                return False
        elif kind == "json":
            try:
                with open(full_p, "r", encoding="utf-8") as jf:
                    json.load(jf)
            except Exception as e:
                errors.append(f"Corrupt JSON {rel_path}: {e}")
                return False
        elif kind == "audio":
            try:
                with wave.open(str(full_p), "rb") as wf:
                    if wf.getnframes() == 0 or wf.getframerate() == 0:
                        errors.append(f"Invalid WAV frames in {rel_path}")
                        return False
            except Exception as e:
                errors.append(f"Corrupt WAV {rel_path}: {e}")
                return False

        return True

    # Check Palette
    check_file(manifest["palette"]["json"], "json")
    check_file(manifest["palette"]["swatch"], "image")

    # Check Units
    for uid, uinfo in manifest["units"].items():
        check_file(uinfo["atlas"], "image")
        check_file(uinfo["meta"], "json")

    # Check Tiles
    for t_theme, t_data in manifest["tilesets"].items():
        for t_info in t_data.get("tiles", []):
            check_file(t_info["atlas"], "image")
            check_file(t_info["meta"], "json")

    # Check Resources
    for rid, rinfo in manifest["resources"].items():
        check_file(rinfo["atlas"], "image")
        check_file(rinfo["meta"], "json")

    # Check Maps
    for mslug, minfo in manifest["maps"].items():
        check_file(minfo["file"], "json")
        check_file(minfo["minimap"], "image")

    # Check Audio
    for cat, aitems in manifest["audio"].items():
        for akey, ainfo in aitems.items():
            check_file(ainfo["file"], "audio")

    # Check UI
    for ui_id, ui_info in manifest["ui"].items():
        if "file" in ui_info:
            check_file(ui_info["file"], "image")
        if "atlas" in ui_info:
            check_file(ui_info["atlas"], "image")
        if "meta" in ui_info:
            check_file(ui_info["meta"], "json")

    if errors:
        if verbose:
            print(f"[-] Verification failed with {len(errors)} errors:")
            for err in errors[:10]:
                print("   *", err)
        return False

    if verbose:
        print(f"[PASS] All {file_count} bundle files verified valid (Total: {total_bytes / 1024 / 1024:.2f} MB).")
    return True


# ---------------------------------------------------------------------------
# Main Bundle Builder
# ---------------------------------------------------------------------------
def build_web_bundle(
    ym_dir: Path,
    out_dir: Path,
    dataset_path: Optional[Path] = None,
    verbose: bool = True,
    verify: bool = True,
) -> Path:
    """Builds the complete web asset bundle and manifest.json."""
    t_start = time.time()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Palette
    pal_path = ym_dir / "pal" / "imjin2.pal"
    palette = Palette.from_file(pal_path)
    pal_dir = out_dir / "palette"
    pal_dir.mkdir(parents=True, exist_ok=True)
    palette.save_json(pal_dir / "palette.json")
    palette.save_swatch_image(pal_dir / "palette_swatch.png")
    if verbose:
        print(f"[+] Loaded palette: {pal_path} (256 colors)")

    # 2. Load Dataset for Stats
    dataset_stats: Dict[str, Dict[str, Any]] = {}
    if dataset_path and dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as f:
            d_raw = json.load(f)
            for item in d_raw:
                p = item.get("sprite_path", "").replace("\\\\", "/").replace("\\", "/").split("/")[-1].lower()
                dataset_stats[p] = item
        if verbose:
            print(f"[+] Loaded dataset stats for {len(dataset_stats)} units")

    manifest: Dict[str, Any] = {
        "version": "1.0.0",
        "name": "Imjinrok 2+ Dawn Web RTS Asset Bundle",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "palette": {
            "json": "palette/palette.json",
            "swatch": "palette/palette_swatch.png",
        },
        "units": {},
        "tilesets": {},
        "resources": {},
        "maps": {},
        "audio": {"sfx": {}, "voice": {}, "music": {}},
        "ui": {},
    }

    # 3. Export Iconic Units & Buildings (20 total across Chosun, Japan, Ming)
    units_dir = out_dir / "units"
    for u in ICONIC_UNITS:
        spr_path = ym_dir / "char" / u["file"]
        if not spr_path.exists():
            print(f"[-] Warning: Sprite not found: {spr_path}")
            continue

        base = spr_path.stem
        meta = decode_sprite_with_atlas(spr_path, palette, units_dir, base)

        # Cross-reference stats with dataset.json fallback to authentic base stats
        stat_item = dataset_stats.get(u["file"].lower(), {})
        base_s = u.get("base_stats", {})

        spd = stat_item.get("speed_field", {}).get("dawn_val")
        if not isinstance(spd, int):
            spd = base_s.get("move_speed", 4)

        hp = stat_item.get("hp_field", {}).get("dawn_val")
        if not isinstance(hp, int):
            hp = base_s.get("hp", 1000)

        atk = stat_item.get("attack_field", {}).get("dawn_val")
        if not isinstance(atk, int):
            atk = base_s.get("attack_power", 10)

        rng = stat_item.get("attack_range", {}).get("dawn_val")
        if not isinstance(rng, int):
            rng = base_s.get("attack_range", 1)

        delay = stat_item.get("attack_delay", {}).get("dawn_val")
        if not isinstance(delay, int):
            delay = base_s.get("attack_delay", 15)

        cost_r = stat_item.get("cost", {}).get("rice", {}).get("dawn")
        if not isinstance(cost_r, int):
            cost_r = base_s.get("cost_crop", 50)

        cost_p = stat_item.get("cost", {}).get("potato", {}).get("dawn")
        if not isinstance(cost_p, int):
            cost_p = base_s.get("cost_tree", 0)

        manifest["units"][u["id"]] = {
            "id": u["id"],
            "name": u["name"],
            "faction": u["faction"],
            "category": u["cat"],
            "sprite_file": u["file"],
            "atlas": f"units/{meta['atlas_file']}",
            "meta": f"units/{base}_meta.json",
            "frame_width": meta["width"],
            "frame_height": meta["height"],
            "frame_count": meta["frame_count"],
            "directions": 8 if meta["frame_count"] % 8 == 0 else 4,
            "stats": {
                "move_speed": spd,
                "hp": hp,
                "mp": 0,
                "attack_power": atk,
                "attack_range": rng,
                "attack_delay": delay,
                "cost_crop": cost_r,
                "cost_tree": cost_p,
            },
        }
        if verbose:
            print(f"  [Unit] Decoded {u['name']} ({meta['width']}x{meta['height']}, {meta['frame_count']} frames)")

    # 4. Export Terrain Tilesets
    tiles_dir = out_dir / "tiles"
    manifest["tilesets"]["normal"] = {"theme": "normal", "tiles": []}
    for t in TERRAIN_TILES:
        t_path = ym_dir / t["file"]
        if not t_path.exists():
            continue
        base = f"normal_{t['name']}"
        t_meta = decode_tile_asset(t_path, palette, tiles_dir, base, tile_type=t["type"])
        manifest["tilesets"]["normal"]["tiles"].append({
            "name": t["name"],
            "type": t["type"],
            "atlas": f"tiles/{base}_atlas.png",
            "meta": f"tiles/{base}_meta.json",
            "width": t_meta["width"],
            "height": t_meta["height"],
            "frame_count": t_meta["frame_count"],
        })
        if verbose:
            print(f"  [Tile] Decoded {t['name']} ({t_meta['width']}x{t_meta['height']}, {t_meta['frame_count']} frames)")

    # 5. Export Resources
    res_dir = out_dir / "resources"
    for r in RESOURCES:
        r_path = ym_dir / r["file"]
        if not r_path.exists():
            continue
        r_meta = decode_sprite_with_atlas(r_path, palette, res_dir, r["id"])
        manifest["resources"][r["id"]] = {
            "id": r["id"],
            "name": r["name"],
            "korean": r["korean"],
            "atlas": f"resources/{r_meta['atlas_file']}",
            "meta": f"resources/{r['id']}_meta.json",
            "width": r_meta["width"],
            "height": r_meta["height"],
            "frame_count": r_meta["frame_count"],
        }
        if verbose:
            print(f"  [Resource] Decoded {r['korean']} ({r_meta['width']}x{r_meta['height']})")

    # 6. Export Representative Maps
    maps_dir = out_dir / "maps"
    for m in REPRESENTATIVE_MAPS:
        m_path = ym_dir / m["file"]
        if not m_path.exists():
            continue
        m_info = export_map_asset(m_path, maps_dir, m["slug"])
        manifest["maps"][m["slug"]] = m_info
        if verbose:
            print(f"  [Map] Parsed {m_info['name']} ({m_info['width']}x{m_info['height']}, {m_info['players']}P)")

    # 7. Export Audio Files
    audio_dir = out_dir / "audio"
    for a in AUDIO_FILES:
        a_path = ym_dir / a["file"]
        if not a_path.exists():
            continue
        a_info = export_audio_asset(a_path, audio_dir, a["key"])
        manifest["audio"][a["cat"]][a["key"]] = a_info
        if verbose:
            print(f"  [Audio] Converted {a['key']} ({a_info['duration_seconds']}s, {a_info['sample_rate']}Hz)")

    # 8. Export UI Elements
    ui_dir = out_dir / "ui"
    for uis in UI_SPRITES:
        ui_path = ym_dir / uis["file"]
        if not ui_path.exists():
            continue
        if uis["id"] == "Back":
            # Direct 800x600 HUD frame export
            dec = SpriteDecoder.from_file(ui_path)
            f0 = dec.decode_frame_image(0, palette)
            f0.save(ui_dir / "Back.png", "PNG")
            manifest["ui"]["Back"] = {
                "file": "ui/Back.png",
                "width": 800,
                "height": 600,
            }
        else:
            ui_meta = decode_sprite_with_atlas(ui_path, palette, ui_dir, uis["id"])
            manifest["ui"][uis["id"]] = {
                "atlas": f"ui/{ui_meta['atlas_file']}",
                "meta": f"ui/{uis['id']}_meta.json",
                "width": ui_meta["width"],
                "height": ui_meta["height"],
                "frame_count": ui_meta["frame_count"],
            }
        if verbose:
            print(f"  [UI] Decoded {uis['id']}")

    # 9. Save Master Manifest
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t_start
    if verbose:
        print(f"\n[+] Asset bundle exported successfully to {out_dir} in {elapsed:.2f}s!")
        print(f"    - Manifest: {manifest_path}")

    # 10. Run Deep Verification if requested
    if verify:
        if verbose:
            print("\n[*] Running deep integrity audit on exported bundle...")
        passed = verify_web_bundle(out_dir, verbose=verbose)
        if not passed:
            raise RuntimeError("Exported web asset bundle failed integrity verification.")

    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Imjinrok 2+ Dawn assets into web bundle.")
    parser.add_argument(
        "--source-ym",
        type=Path,
        default=Path(r"C:\src\reverse-imzinrok\YM\dawn"),
        help="Path to YM/dawn directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"C:\src\reverse-imzinrok\web_prototype\assets"),
        help="Output assets directory",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(r"C:\src\reverse-imzinrok\tools\modding\dataset.json"),
        help="Path to dataset.json",
    )
    parser.add_argument("--no-verify", action="store_true", help="Skip deep integrity verification")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose logging")
    args = parser.parse_args()

    try:
        build_web_bundle(
            ym_dir=args.source_ym,
            out_dir=args.output_dir,
            dataset_path=args.dataset,
            verbose=not args.quiet,
            verify=not args.no_verify,
        )
        return 0
    except Exception as e:
        print(f"Fatal error building web bundle: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
