"""Catalog generator for Imjinrok 2+ Dawn archive internal tables.

Parses all 109 internal configuration and data files into structured JSON metadata,
including parsed tables for:
- ImgFile.dat: Sprite ID, numeric index, file path, initial load flag
- Text_kor.dat: String IDs and Korean strings (units, buildings, skills, dialogs)
- ExpForLevelUp.dat: Levels 1-100 experience progression table
- TileFile.txt: Tile symbolic IDs to .ytl file mapping
- screenPt_plus.dat / screenPt_imjin.dat: UI grid coordinates and menu settings
- GeneralPortraitFileName.txt: Hero portrait bitmaps
- Cross-reference mapping between sprites and unit names
"""

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from tools.archive.unpacker import FileInfo, categorize_file, detect_encoding


def parse_img_file_table(content: str) -> List[Dict[str, Any]]:
    """Parse ImgFile.dat into structured records."""
    entries: List[Dict[str, Any]] = []
    lines = content.splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("파일 ID"):
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            sprite_id = parts[0].strip()
            try:
                num = int(parts[1].strip())
            except ValueError:
                continue
            file_path = parts[2].strip()
            try:
                init_load = int(parts[3].strip())
            except ValueError:
                init_load = 0

            entries.append({
                "sprite_id": sprite_id,
                "number": num,
                "file_path": file_path,
                "load_initially": init_load,
            })
    return entries


def parse_text_kor_table(content: str) -> List[Dict[str, Any]]:
    """Parse Text_kor.dat into string ID and text mappings."""
    entries: List[Dict[str, Any]] = []
    lines = content.splitlines()

    curr_id: Optional[int] = None
    curr_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Format: <id>, ""<text>""
        # Check if line starts a new record
        match = re.match(r"^(\d+)\s*,\s*\"\"(.*)", stripped)
        if match:
            # Save previous record if open
            if curr_id is not None:
                full_text = "\n".join(curr_lines)
                entries.append({
                    "id": curr_id,
                    "text": full_text,
                    "category": _categorize_string_id(curr_id),
                })
            curr_id = int(match.group(1))
            remainder = match.group(2)
            if remainder.endswith('""'):
                # Complete on single line
                text_content = remainder[:-2]
                entries.append({
                    "id": curr_id,
                    "text": text_content,
                    "category": _categorize_string_id(curr_id),
                })
                curr_id = None
                curr_lines = []
            else:
                curr_lines = [remainder]
        elif curr_id is not None:
            if stripped.endswith('""'):
                curr_lines.append(stripped[:-2])
                full_text = "\n".join(curr_lines)
                entries.append({
                    "id": curr_id,
                    "text": full_text,
                    "category": _categorize_string_id(curr_id),
                })
                curr_id = None
                curr_lines = []
            else:
                curr_lines.append(line)

    if curr_id is not None and curr_lines:
        entries.append({
            "id": curr_id,
            "text": "\n".join(curr_lines),
            "category": _categorize_string_id(curr_id),
        })

    return entries


def _categorize_string_id(str_id: int) -> str:
    """Classify string ID into functional category."""
    if 100 <= str_id < 1000:
        return "system_dialog"
    elif 1000 <= str_id < 2000:
        return "chosun_units_buildings"
    elif 2000 <= str_id < 3000:
        return "japan_ming_units_buildings"
    elif 3000 <= str_id < 5000:
        return "research_and_upgrades"
    elif 5000 <= str_id < 8000:
        return "hero_skills_and_items"
    elif 8000 <= str_id < 10000:
        return "campaign_and_online"
    return "general_strings"


def parse_exp_level_table(content: str) -> List[Dict[str, int]]:
    """Parse ExpForLevelUp.dat table (levels 1-100)."""
    records: List[Dict[str, int]] = []
    lines = content.splitlines()

    for line in lines:
        parts = line.strip().split("\t")
        if len(parts) >= 4:
            try:
                lvl = int(parts[0].strip())
                accu = int(parts[1].strip())
                need = int(parts[2].strip())
                calc = int(parts[3].strip())
                records.append({
                    "level": lvl,
                    "accumulated_exp": accu,
                    "needed_exp": need,
                    "calc_step": calc,
                })
            except ValueError:
                continue
    return records


def parse_key_value_table(content: str) -> Dict[str, str]:
    """Parse tab-separated key-value tables like screenPt_plus.dat."""
    data: Dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            key = parts[0].strip()
            val = parts[1].strip()
            data[key] = val
    return data


def parse_tile_file_table(content: str) -> List[Dict[str, str]]:
    """Parse TileFile.txt table."""
    records: List[Dict[str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) >= 2:
            records.append({
                "symbol": parts[0],
                "file": parts[1],
            })
    return records


def build_catalog(
    unpacked_dir: Union[str, Path],
    output_catalog_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Build a complete, structured JSON catalog of all 109 internal files.

    Args:
        unpacked_dir: Directory containing unpacked files (and optional manifest.json).
        output_catalog_path: Path to write catalog.json (optional).

    Returns:
        Dictionary containing catalog data.
    """
    unpacked_dir = Path(unpacked_dir)
    manifest_p = unpacked_dir / "manifest.json"

    file_entries: List[Dict[str, Any]] = []
    total_size = 0

    if manifest_p.exists():
        manifest_data = json.loads(manifest_p.read_text(encoding="utf-8"))
        for f in manifest_data["files"]:
            rel_parts = f["name"].replace("/", "\\").split("\\")
            local_p = unpacked_dir.joinpath(*rel_parts)
            line_count = 0
            if local_p.exists():
                try:
                    line_count = len(local_p.read_bytes().split(b"\n"))
                except Exception:
                    line_count = 0
            entry_info = dict(f)
            entry_info["line_count"] = line_count
            file_entries.append(entry_info)
            total_size += f["size"]
    else:
        # Scan on disk
        idx = 0
        running_offset = 0
        for root, _, files in os.walk(unpacked_dir):
            for file in sorted(files):
                if file in {"manifest.json", "catalog.json", "utf8"}:
                    continue
                p = Path(root) / file
                rel_p = str(p.relative_to(unpacked_dir)).replace("/", "\\")
                raw = p.read_bytes()
                sz = len(raw)
                sha = hashlib.sha256(raw).hexdigest()
                enc = detect_encoding(rel_p)
                cat = categorize_file(rel_p)
                line_count = len(raw.split(b"\n"))
                file_entries.append({
                    "index": idx,
                    "name": rel_p,
                    "local_path": str(p.relative_to(unpacked_dir)),
                    "size": sz,
                    "offset": running_offset,
                    "sha256": sha,
                    "category": cat,
                    "detected_encoding": enc,
                    "line_count": line_count,
                })
                idx += 1
                running_offset += sz
        total_size = running_offset

    # Category statistics
    category_counts: Dict[str, int] = {}
    for f in file_entries:
        c = f.get("category", "misc")
        category_counts[c] = category_counts.get(c, 0) + 1

    # Deep parse key game tables
    parsed_tables: Dict[str, Any] = {}

    # 1. ImgFile.dat
    img_path = unpacked_dir / "ImgFile.dat"
    if img_path.exists():
        img_content = img_path.read_text(encoding="cp949", errors="replace")
        parsed_tables["img_file_dat"] = parse_img_file_table(img_content)

    # 2. Text_kor.dat
    text_kor_path = unpacked_dir / "Text_kor.dat"
    if text_kor_path.exists():
        text_kor_content = text_kor_path.read_text(encoding="cp949", errors="replace")
        parsed_tables["text_kor_dat"] = parse_text_kor_table(text_kor_content)

    # 3. ExpForLevelUp.dat
    exp_path = unpacked_dir / "ExpForLevelUp.dat"
    if exp_path.exists():
        exp_content = exp_path.read_text(encoding="cp949", errors="replace")
        parsed_tables["exp_for_level_up"] = parse_exp_level_table(exp_content)

    # 4. screenPt_plus.dat
    screen_plus_p = unpacked_dir / "screenPt_plus.dat"
    if screen_plus_p.exists():
        screen_content = screen_plus_p.read_text(encoding="cp949", errors="replace")
        parsed_tables["screen_pt_plus"] = parse_key_value_table(screen_content)

    # 5. screenPt_imjin.dat
    screen_imjin_p = unpacked_dir / "screenPt_imjin.dat"
    if screen_imjin_p.exists():
        screen_imjin_content = screen_imjin_p.read_text(encoding="cp949", errors="replace")
        parsed_tables["screen_pt_imjin"] = parse_key_value_table(screen_imjin_content)

    # 6. TileFile.txt
    tile_file_p = unpacked_dir / "TileFile.txt"
    if tile_file_p.exists():
        tile_content = tile_file_p.read_text(encoding="cp949", errors="replace")
        parsed_tables["tile_file"] = parse_tile_file_table(tile_content)

    # 7. GeneralPortraitFileName.txt
    portrait_p = unpacked_dir / "GeneralPortraitFileName.txt"
    if portrait_p.exists():
        portrait_lines = [
            l.strip()
            for l in portrait_p.read_text(encoding="cp949", errors="replace").splitlines()
            if l.strip()
        ]
        parsed_tables["general_portraits"] = portrait_lines

    # Cross-reference: Unit/Building sprite inventory
    cross_ref = []
    if "img_file_dat" in parsed_tables:
        for img in parsed_tables["img_file_dat"]:
            sp_id = img["sprite_id"]
            fp = img["file_path"].lower()
            if sp_id.startswith("FILE_CHAR_") or "char\\" in fp or "char/" in fp:
                cross_ref.append({
                    "sprite_id": sp_id,
                    "number": img["number"],
                    "file_path": img["file_path"],
                    "load_initially": img["load_initially"],
                })

    catalog_data = {
        "title": "Imjinrok 2+ Dawn Archive Catalog",
        "total_files": len(file_entries),
        "total_size_bytes": total_size,
        "category_summary": category_counts,
        "files": file_entries,
        "parsed_tables_summary": {
            k: len(v) if isinstance(v, (list, dict)) else 1
            for k, v in parsed_tables.items()
        },
        "parsed_tables": parsed_tables,
        "unit_building_sprite_inventory": cross_ref,
    }

    if output_catalog_path:
        out_p = Path(output_catalog_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(
            json.dumps(catalog_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    return catalog_data
