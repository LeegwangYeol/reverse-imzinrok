"""
E2E Test Infrastructure Configuration and Fixtures
Imjinrok 2+ Dawn Modding Toolkit
"""

import os
import shutil
import tempfile
import hashlib
from pathlib import Path

# Base Paths
BASE_DIR = Path("C:/src/reverse-imzinrok")
YM_DIR = BASE_DIR / "YM"
DAWN_DIR = YM_DIR / "dawn"
MAP_EDITOR_DIR = YM_DIR / "맵에디터"

# Executables
DAWN_EXE = DAWN_DIR / "dawn.exe"
ORIGINAL_DAWN_EXE = BASE_DIR / "YM_backup_original" / "dawn.exe"
USEMAP_EXE = MAP_EDITOR_DIR / "UseMap.exe"
MAP_EDITOR_EXE = MAP_EDITOR_DIR / "Map Editor.exe"

# Archive Files
DATA_FILE = DAWN_DIR / "Data"
DATA_HQ_FILE = DAWN_DIR / "Data.hq"

# Asset Paths
PAL_DIR = DAWN_DIR / "pal"
DEFAULT_PAL = PAL_DIR / "00.pal"
IMJIN2_PAL = DAWN_DIR / "Imjin2.pal"
CUSMAP_DIR = DAWN_DIR / "cusmap"
EFT_DIR = DAWN_DIR / "eft"
MUSIC_DIR = DAWN_DIR / "music"
CHAR_DIR = DAWN_DIR / "char"
TILE_DIR = DAWN_DIR / "tile"
FNT_DIR = DAWN_DIR / "fnt"
BATTLE_SPR = DAWN_DIR / "BattleSpr" / "Back.Spr"

# Subsystems
TOOLS_DIR = BASE_DIR / "tools"
TESTS_DIR = BASE_DIR / "tests"

# Known Checksums / Baseline Sizes for Non-destructive Safety
ORIGINAL_DATA_SIZE = 230202
ORIGINAL_DATA_HQ_SIZE = 5408
ORIGINAL_MAP_SIZE = 1132876
ORIGINAL_DAWN_EXE_SIZE = 1032192

# Snapshot of original SHA-256 hashes to guarantee YM remains strictly untouched
_ORIGINAL_HASHES = {}


def sha256_file(path: str | Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_ym_hashes():
    """Record initial hashes of critical source files."""
    critical_files = [
        DAWN_EXE,
        USEMAP_EXE,
        DATA_FILE,
        DATA_HQ_FILE,
        IMJIN2_PAL,
        DEFAULT_PAL,
        BATTLE_SPR,
    ]
    for p in critical_files:
        if p.exists():
            _ORIGINAL_HASHES[str(p)] = (p.stat().st_size, sha256_file(p))


# Initialize snapshot on import
if not _ORIGINAL_HASHES:
    snapshot_ym_hashes()


def verify_ym_integrity() -> bool:
    """Verify that none of the source game files in YM have been modified or corrupted."""
    for path_str, (expected_size, expected_hash) in _ORIGINAL_HASHES.items():
        p = Path(path_str)
        if not p.exists():
            return False
        if p.stat().st_size != expected_size:
            return False
        if sha256_file(p) != expected_hash:
            return False
    return True


def get_temp_dir(prefix: str = "test_imzinrok_") -> Path:
    """Create a temporary directory for test outputs."""
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    return temp_dir


def clone_dawn_exe(target_dir: Path | None = None) -> Path:
    r"""
    Safely clone dawn.exe into a temporary directory for patching tests.
    Ensures the original YM\dawn\dawn.exe is NEVER touched.
    Clones from YM_backup_original\dawn.exe to ensure contiguous zero slack space.
    """
    if target_dir is None:
        target_dir = get_temp_dir("dawn_patch_")
    target_exe = target_dir / "dawn_test.exe"
    src_exe = ORIGINAL_DAWN_EXE if ORIGINAL_DAWN_EXE.exists() else DAWN_EXE
    shutil.copy2(src_exe, target_exe)
    return target_exe


def clone_map_file(map_name_or_path: str | Path, target_dir: Path | None = None) -> Path:
    """
    Safely clone a .map file into a temporary directory for modding tests.
    """
    src_map = Path(map_name_or_path)
    if not src_map.is_absolute():
        src_map = CUSMAP_DIR / src_map
    if target_dir is None:
        target_dir = get_temp_dir("map_test_")
    target_map = target_dir / src_map.name
    shutil.copy2(src_map, target_map)
    return target_map
