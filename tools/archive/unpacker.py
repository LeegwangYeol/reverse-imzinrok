"""Lossless unpacker for Data.hq and Data archives.

Binary Specifications:
- Data.hq (5,408 bytes): CRLF-separated index with header `총라인수 : [109]`
  followed by 109 entries formatted as `<filename>\\t[<size>]\\t[<offset>]`.
  Lines are encoded with CP949 and XORed with 0x10.
- Data (230,202 bytes): 100% contiguous concatenation of all 109 internal files,
  XORed with 0x10 unconditionally across all bytes.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import List, Optional, Tuple, Union

from tools.archive.codec import decode_data_bytes, decode_hq_bytes


@dataclass
class ArchiveEntry:
    """Metadata for an entry recorded in Data.hq index."""
    index: int
    name: str
    size: int
    offset: int
    category: str
    detected_encoding: str


@dataclass
class FileInfo:
    """Information about an extracted file on disk."""
    index: int
    name: str
    local_path: str
    size: int
    offset: int
    sha256: str
    category: str
    detected_encoding: str

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "local_path": self.local_path,
            "size": self.size,
            "offset": self.offset,
            "sha256": self.sha256,
            "category": self.category,
            "detected_encoding": self.detected_encoding,
        }


KNOWN_ENCODINGS = {
    "FontInfo_chi.dat": "gb2312",
    "FontInfo_eng.dat": "ascii",
    "FontInfo_jpn.dat": "cp932",
    "FontInfo_kor.dat": "cp949",
    "FontInfo_tai.dat": "big5",
    "FontInfo_tha.dat": "cp874",
    "Text_eng.dat": "ascii",
    "Text_jpn.dat": "cp932",
    "Text_kor.dat": "cp949",
    "Text_tha.dat": "cp874",
}


def detect_encoding(filename: str) -> str:
    """Detect expected character encoding for a given table file."""
    base = os.path.basename(filename)
    return KNOWN_ENCODINGS.get(base, "cp949")


def categorize_file(filename: str) -> str:
    """Categorize internal file by its functional domain."""
    base = os.path.basename(filename).lower()
    norm = filename.replace("/", "\\")

    if base.startswith("fontinfo_"):
        return "font_info"
    elif base.startswith("text_"):
        return "string_table"
    elif base.endswith(".cof"):
        return "cof_script"
    elif base == "imgfile.dat":
        return "sprite_table"
    elif base == "effectsound.dat":
        return "sound_table"
    elif base == "expforlevelup.dat":
        return "exp_table"
    elif base.startswith("screenpt_"):
        return "ui_layout"
    elif base == "onlinebattlemap.dat":
        return "battle_map"
    elif base.endswith("type.txt"):
        return "terrain_type"
    elif base == "tilefile.txt":
        return "tile_table"
    elif base == "generalportraitfilename.txt":
        return "portrait_table"
    elif "johapchar\\text" in norm.lower():
        return "johap_text"
    return "misc_table"


def parse_hq_entries(hq_bytes: bytes) -> Tuple[int, List[ArchiveEntry]]:
    """Parse Data.hq byte buffer into header count and entry list."""
    lines = decode_hq_bytes(hq_bytes, encoding="cp949")
    if not lines:
        raise ValueError("Data.hq is empty or corrupted")

    header_line = lines[0].strip()
    match = re.match(r"^총라인수\s*:\s*\[(\d+)\]$", header_line)
    if not match:
        raise ValueError(f"Invalid Data.hq header: '{header_line}'")
    
    expected_count = int(match.group(1))
    entries: List[ArchiveEntry] = []
    current_expected_offset = 0

    for idx, line in enumerate(lines[1:], start=0):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"Line {idx + 1} has invalid column count: {repr(line)}")
        
        name = parts[0].strip()
        size_str = parts[1].strip().strip("[]")
        offset_str = parts[2].strip().strip("[]")
        
        size = int(size_str)
        offset = int(offset_str)

        if offset != current_expected_offset:
            raise ValueError(
                f"Offset gap/overlap at entry {idx} ('{name}'): "
                f"expected {current_expected_offset}, got {offset}"
            )
        
        category = categorize_file(name)
        enc = detect_encoding(name)

        entries.append(
            ArchiveEntry(
                index=idx,
                name=name,
                size=size,
                offset=offset,
                category=category,
                detected_encoding=enc,
            )
        )
        current_expected_offset += size

    if len(entries) != expected_count:
        raise ValueError(
            f"Entry count mismatch: header specified {expected_count}, but found {len(entries)}"
        )

    return expected_count, entries


def unpack_archive(
    archive_path: Union[str, Path],
    hq_path: Union[str, Path],
    output_dir: Union[str, Path],
    write_manifest: bool = True,
    export_utf8: bool = False,
) -> List[FileInfo]:
    """Unpack all files from Data using Data.hq index into output_dir.
    
    Args:
        archive_path: Path to Data file.
        hq_path: Path to Data.hq index file.
        output_dir: Target directory where files will be unpacked.
        write_manifest: If True, writes manifest.json with complete metadata.
        export_utf8: If True, also writes decoded UTF-8 copies into utf8/ folder.
        
    Returns:
        List of FileInfo records for all unpacked files.
    """
    archive_path = Path(archive_path)
    hq_path = Path(hq_path)
    output_dir = Path(output_dir)

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")
    if not hq_path.exists():
        raise FileNotFoundError(f"Index file not found: {hq_path}")

    raw_hq = hq_path.read_bytes()
    raw_data = archive_path.read_bytes()

    expected_count, entries = parse_hq_entries(raw_hq)

    # Verify total size matches archive size
    total_expected_size = sum(e.size for e in entries)
    if len(raw_data) != total_expected_size:
        raise ValueError(
            f"Archive size mismatch: header entries total {total_expected_size} bytes, "
            f"but Data file is {len(raw_data)} bytes"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    if export_utf8:
        (output_dir / "utf8").mkdir(parents=True, exist_ok=True)

    file_infos: List[FileInfo] = []

    for entry in entries:
        raw_slice = raw_data[entry.offset : entry.offset + entry.size]
        decrypted_bytes = decode_data_bytes(raw_slice)

        # Normalize relative path using system separator
        rel_parts = entry.name.replace("/", "\\").split("\\")
        target_path = output_dir.joinpath(*rel_parts)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        target_path.write_bytes(decrypted_bytes)

        file_sha256 = hashlib.sha256(decrypted_bytes).hexdigest()

        if export_utf8:
            utf8_path = output_dir / "utf8" / Path(*rel_parts)
            utf8_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                text_content = decrypted_bytes.decode(entry.detected_encoding, errors="replace")
                utf8_path.write_text(text_content, encoding="utf-8")
            except Exception:
                # If binary fallback
                utf8_path.write_bytes(decrypted_bytes)

        file_info = FileInfo(
            index=entry.index,
            name=entry.name,
            local_path=str(target_path.relative_to(output_dir)),
            size=entry.size,
            offset=entry.offset,
            sha256=file_sha256,
            category=entry.category,
            detected_encoding=entry.detected_encoding,
        )
        file_infos.append(file_info)

    if write_manifest:
        manifest_data = {
            "archive_source": str(archive_path.resolve()),
            "hq_source": str(hq_path.resolve()),
            "total_files": len(file_infos),
            "total_size": total_expected_size,
            "archive_sha256": hashlib.sha256(raw_data).hexdigest(),
            "hq_sha256": hashlib.sha256(raw_hq).hexdigest(),
            "files": [f.to_dict() for f in file_infos],
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    return file_infos
