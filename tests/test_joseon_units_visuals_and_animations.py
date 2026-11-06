"""
tests/test_joseon_units_visuals_and_animations.py - Visual Assets, Sprites & Safety Verification Suite

Comprehensive test suite verifying:
1. 34x34 RGBA Button Graphics for 10 custom Joseon units (0x70~0x79):
   - Canonical files (btn_unit_0x70.png .. btn_unit_0x79.png) & named aliases
   - Strict 34x34 resolution, RGBA channels, non-zero alpha, RTS beveled borders
   - Distinct imagery across all 10 units (no duplicate placeholder clones)
2. Atlas Sprite PNGs and Metadata in web_prototype/assets/units/ & manifest.json:
   - Complete atlas PNG validation (valid dimensions, non-corrupted images)
   - Metadata JSON schema validation (frame_count, frame boundaries, atlas bounds)
   - Air unit Joseon Hornet (0x74) isAirUnit: true registration
3. 100% Safety & Integrity Verification via tools/verify_safety.py:
   - 204 protected files in YM_KEY_MANIFEST bit-exact and untouched
   - Clean git working tree in rea repository
"""

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from PIL import Image
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "web_prototype" / "assets"
BUTTONS_DIR = ASSETS_DIR / "ui" / "buttons"
UNITS_DIR = ASSETS_DIR / "units"
MANIFEST_FILE = ASSETS_DIR / "manifest.json"
BUTTONS_MANIFEST_FILE = BUTTONS_DIR / "buttons_manifest.json"
SAFETY_SCRIPT = PROJECT_ROOT / "tools" / "verify_safety.py"

CUSTOM_JOSEON_UNITS = [
    {
        "kind_id": 0x70,
        "kind_hex": "0x70",
        "id": "chosun_yusaeng",
        "alias_id": "yusaeng",
        "name": "유생",
        "hotkey": "Y",
        "slot": 9,
        "bldg": "chosun_hq",
        "rice": 250,
        "potato": 0,
        "atlas_base": "keon_1hs",
        "expected_frames": 176,
        "is_air": False,
        "corpse_frame": 71
    },
    {
        "kind_id": 0x71,
        "kind_hex": "0x71",
        "id": "chosun_geomsul_nangin",
        "alias_id": "geomsul_nangin",
        "name": "검술 낭인",
        "hotkey": "K",
        "slot": 8,
        "bldg": "chosun_barracks",
        "rice": 180,
        "potato": 0,
        "atlas_base": "SwordPirate_online",
        "expected_frames": 136,
        "is_air": False,
        "corpse_frame": 128
    },
    {
        "kind_id": 0x72,
        "kind_hex": "0x72",
        "id": "chosun_jochong_nangin",
        "alias_id": "jochong_nangin",
        "name": "조총 낭인",
        "hotkey": "N",
        "slot": 9,
        "bldg": "chosun_barracks",
        "rice": 240,
        "potato": 0,
        "atlas_base": "GunPirate_online",
        "expected_frames": 136,
        "is_air": False,
        "corpse_frame": 128
    },
    {
        "kind_id": 0x73,
        "kind_hex": "0x73",
        "id": "chosun_gumiho",
        "alias_id": "gumiho",
        "name": "구미호",
        "hotkey": "F",
        "slot": 11,
        "bldg": "chosun_hq",
        "rice": 280,
        "potato": 50,
        "atlas_base": "fox",
        "expected_frames": 144,
        "is_air": False,
        "corpse_frame": 136
    },
    {
        "kind_id": 0x74,
        "kind_hex": "0x74",
        "id": "chosun_wangbeol",
        "alias_id": "wangbeol",
        "name": "조선왕벌",
        "hotkey": "B",
        "slot": 7,
        "bldg": "chosun_stables",
        "rice": 200,
        "potato": 50,
        "atlas_base": "bat_online",
        "expected_frames": 160,
        "is_air": True,
        "corpse_frame": None
    },
    {
        "kind_id": 0x75,
        "kind_hex": "0x75",
        "id": "chosun_horangi",
        "alias_id": "horangi",
        "name": "조선 호랑이",
        "hotkey": "T",
        "slot": 8,
        "bldg": "chosun_stables",
        "rice": 300,
        "potato": 0,
        "atlas_base": "Tiger",
        "expected_frames": 136,
        "is_air": False,
        "corpse_frame": 129
    },
    {
        "kind_id": 0x76,
        "kind_hex": "0x76",
        "id": "chosun_teolgamyeon",
        "alias_id": "teolgamyeon",
        "name": "털가면",
        "hotkey": "M",
        "slot": 10,
        "bldg": "chosun_barracks",
        "rice": 220,
        "potato": 40,
        "atlas_base": "furheaddemon_online",
        "expected_frames": 130,
        "is_air": False,
        "corpse_frame": 129
    },
    {
        "kind_id": 0x77,
        "kind_hex": "0x77",
        "id": "chosun_seolnyeo",
        "alias_id": "seolnyeo",
        "name": "설녀",
        "hotkey": "S",
        "slot": 9,
        "bldg": "chosun_stables",
        "rice": 280,
        "potato": 60,
        "atlas_base": "snowwoman_online",
        "expected_frames": 192,
        "is_air": False,
        "corpse_frame": 83
    },
    {
        "kind_id": 0x78,
        "kind_hex": "0x78",
        "id": "chosun_dokkaebi",
        "alias_id": "dokkaebi",
        "name": "조선 도깨비",
        "hotkey": "D",
        "slot": 10,
        "bldg": "chosun_stables",
        "rice": 320,
        "potato": 0,
        "atlas_base": "oni_online",
        "expected_frames": 180,
        "is_air": False,
        "corpse_frame": 150
    },
    {
        "kind_id": 0x79,
        "kind_hex": "0x79",
        "id": "chosun_bulgasari",
        "alias_id": "bulgasari",
        "name": "불가살이",
        "hotkey": "U",
        "slot": 10,
        "bldg": "chosun_hq",
        "rice": 380,
        "potato": 100,
        "atlas_base": "starfish",
        "expected_frames": 216,
        "is_air": False,
        "corpse_frame": 179
    }
]


# ===========================================================================
# 1. BUTTON VISUALS, DIMENSIONS, CHANNELS, AND DIVERSITY
# ===========================================================================

def test_buttons_directory_and_manifest_exist():
    """Verify that buttons directory and buttons_manifest.json exist."""
    assert BUTTONS_DIR.exists(), f"Buttons directory missing: {BUTTONS_DIR}"
    assert BUTTONS_MANIFEST_FILE.exists(), f"Buttons manifest missing: {BUTTONS_MANIFEST_FILE}"


def test_canonical_button_dimensions_channels_and_nonzero_alpha():
    """Verify each canonical button PNG is exactly 34x34, mode RGBA, with non-zero alpha and bevel."""
    for unit in CUSTOM_JOSEON_UNITS:
        btn_path = BUTTONS_DIR / f"btn_unit_{unit['kind_hex'].lower()}.png"
        assert btn_path.exists(), f"Missing canonical button: {btn_path}"

        with Image.open(btn_path) as im:
            # 1. Dimensions
            assert im.size == (34, 34), f"{btn_path.name} dimension is {im.size}, expected (34, 34)"

            # 2. Mode
            assert im.mode == "RGBA", f"{btn_path.name} mode is {im.mode}, expected RGBA"

            # 3. Non-zero alpha: bounding box covers the full 34x34 area
            bbox = im.getbbox()
            assert bbox == (0, 0, 34, 34), f"{btn_path.name} bbox is {bbox}, expected full (0, 0, 34, 34)"

            # Verify alpha channel values are not zero
            alpha_channel = im.split()[3]
            min_alpha, max_alpha = alpha_channel.getextrema()
            assert max_alpha > 200, f"{btn_path.name} max alpha {max_alpha} is too low"

            # 4. RTS Beveled border: top-left highlight pixel should be brighter than bottom-right shadow pixel
            tl_pixel = im.getpixel((0, 0))
            br_pixel = im.getpixel((33, 33))
            # Compare luminance or red channel
            tl_lum = 0.299 * tl_pixel[0] + 0.587 * tl_pixel[1] + 0.114 * tl_pixel[2]
            br_lum = 0.299 * br_pixel[0] + 0.587 * br_pixel[1] + 0.114 * br_pixel[2]
            assert tl_lum > br_lum, f"{btn_path.name} bevel lighting failure: TL={tl_lum} <= BR={br_lum}"


def test_distinct_button_imagery_across_units():
    """Verify all 10 custom unit buttons have distinct imagery and are not identical clones."""
    hashes = {}
    for unit in CUSTOM_JOSEON_UNITS:
        btn_path = BUTTONS_DIR / f"btn_unit_{unit['kind_hex'].lower()}.png"
        with Image.open(btn_path) as im:
            data = im.tobytes()
            img_hash = sha256(data).hexdigest()
            assert img_hash not in hashes.values(), (
                f"Duplicate button imagery detected: {btn_path.name} is identical to {list(hashes.keys())[list(hashes.values()).index(img_hash)]}"
            )
            hashes[unit["kind_hex"]] = img_hash

    assert len(hashes) == 10, f"Expected 10 distinct button hashes, got {len(hashes)}"


def test_named_button_aliases_match_canonical():
    """Verify alias button files match their corresponding canonical hex files exactly."""
    for unit in CUSTOM_JOSEON_UNITS:
        hex_file = BUTTONS_DIR / f"btn_unit_{unit['kind_hex'].lower()}.png"
        alias_file = BUTTONS_DIR / f"btn_unit_{unit['alias_id']}.png"
        assert alias_file.exists(), f"Missing alias button file: {alias_file}"
        assert hex_file.read_bytes() == alias_file.read_bytes(), (
            f"Byte mismatch between canonical {hex_file.name} and alias {alias_file.name}"
        )


def test_buttons_manifest_schema_and_building_slots():
    """Verify buttons_manifest.json contains complete metadata, hotkeys, and building assignments."""
    with open(BUTTONS_MANIFEST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("total_units") == 10
    assert data.get("button_width") == 34
    assert data.get("button_height") == 34
    assert len(data.get("units", [])) == 10

    # Building distribution checks
    hq_units = [u for u in data["units"] if u["building_id"] == "chosun_hq"]
    barracks_units = [u for u in data["units"] if u["building_id"] == "chosun_barracks"]
    stables_units = [u for u in data["units"] if u["building_id"] == "chosun_stables"]

    assert len(hq_units) == 3, f"Expected 3 HQ units, found {len(hq_units)}"
    assert len(barracks_units) == 3, f"Expected 3 Barracks units, found {len(barracks_units)}"
    assert len(stables_units) == 4, f"Expected 4 Stables units, found {len(stables_units)}"

    # Specific slot mapping checks
    hq_slots = {u["slot"]: u["kind_id"] for u in hq_units}
    assert hq_slots.get(9) == 0x70, "HQ slot 9 must be 0x70 (유생)"
    assert hq_slots.get(10) == 0x79, "HQ slot 10 must be 0x79 (불가살이)"
    assert hq_slots.get(11) == 0x73, "HQ slot 11 must be 0x73 (구미호)"

    barracks_slots = {u["slot"]: u["kind_id"] for u in barracks_units}
    assert barracks_slots.get(8) == 0x71, "Barracks slot 8 must be 0x71 (검술 낭인)"
    assert barracks_slots.get(9) == 0x72, "Barracks slot 9 must be 0x72 (조총 낭인)"
    assert barracks_slots.get(10) == 0x76, "Barracks slot 10 must be 0x76 (털가면)"

    stables_slots = {u["slot"]: u["kind_id"] for u in stables_units}
    assert stables_slots.get(7) == 0x74, "Stables slot 7 must be 0x74 (조선왕벌)"
    assert stables_slots.get(8) == 0x75, "Stables slot 8 must be 0x75 (조선 호랑이)"
    assert stables_slots.get(9) == 0x77, "Stables slot 9 must be 0x77 (설녀)"
    assert stables_slots.get(10) == 0x78, "Stables slot 10 must be 0x78 (조선 도깨비)"


# ===========================================================================
# 2. ATLAS SPRITE PNG AND METADATA VALIDITY
# ===========================================================================

def test_unit_atlas_pngs_and_metadata_json():
    """Verify all 10 custom Joseon unit atlas PNGs and meta JSONs exist with valid dimensions."""
    assert UNITS_DIR.exists(), f"Units directory missing: {UNITS_DIR}"

    for unit in CUSTOM_JOSEON_UNITS:
        atlas_png = UNITS_DIR / f"{unit['atlas_base']}_atlas.png"
        meta_json = UNITS_DIR / f"{unit['atlas_base']}_meta.json"

        assert atlas_png.exists(), f"Missing atlas PNG: {atlas_png}"
        assert meta_json.exists(), f"Missing meta JSON: {meta_json}"

        # 1. Verify Atlas Image
        with Image.open(atlas_png) as im:
            atlas_w, atlas_h = im.size
            assert atlas_w > 0 and atlas_h > 0, f"Invalid dimensions for {atlas_png.name}"
            assert im.mode in ("RGB", "RGBA"), f"Unexpected mode {im.mode} for {atlas_png.name}"

        # 2. Verify Meta JSON
        with open(meta_json, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert meta.get("frame_count") == unit["expected_frames"], (
            f"Frame count mismatch for {unit['name']}: got {meta.get('frame_count')}, expected {unit['expected_frames']}"
        )
        assert len(meta.get("frames", [])) == unit["expected_frames"], (
            f"Frames array length mismatch for {unit['name']}"
        )

        # 3. Verify frame coordinates fit inside atlas
        for idx, frame in enumerate(meta["frames"]):
            fx = frame.get("u", frame.get("x", 0))
            fy = frame.get("v", frame.get("y", 0))
            fw = frame.get("width", frame.get("w", 0))
            fh = frame.get("height", frame.get("h", 0))

            assert fx >= 0 and fy >= 0, f"Frame {idx} in {meta_json.name} has negative offset: ({fx}, {fy})"
            assert fw > 0 and fh > 0, f"Frame {idx} in {meta_json.name} has non-positive size: ({fw}, {fh})"
            assert fx + fw <= atlas_w, f"Frame {idx} in {meta_json.name} overflows atlas width ({fx + fw} > {atlas_w})"
            assert fy + fh <= atlas_h, f"Frame {idx} in {meta_json.name} overflows atlas height ({fy + fh} > {atlas_h})"


def test_manifest_registration_and_air_unit_spec():
    """Verify all 10 units are registered in web_prototype/assets/manifest.json and air flags are correct."""
    assert MANIFEST_FILE.exists(), f"Missing manifest.json at {MANIFEST_FILE}"

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    units_dict = manifest.get("units", {})

    for unit in CUSTOM_JOSEON_UNITS:
        u_key = unit["id"]
        assert u_key in units_dict, f"Unit key {u_key} missing from manifest.json"
        entry = units_dict[u_key]

        assert entry.get("kind_id") == unit["kind_id"]
        assert entry.get("isAirUnit") == unit["is_air"], (
            f"Mismatched isAirUnit for {unit['name']}: expected {unit['is_air']}, got {entry.get('isAirUnit')}"
        )

        # Confirm atlas paths in manifest point to existing files
        atlas_rel = entry.get("atlas")
        meta_rel = entry.get("meta")
        assert atlas_rel and (ASSETS_DIR / atlas_rel).exists(), f"Atlas file {atlas_rel} not found"
        assert meta_rel and (ASSETS_DIR / meta_rel).exists(), f"Meta file {meta_rel} not found"


# ===========================================================================
# 3. 100% SAFETY & KEY MANIFEST INTEGRITY VERIFICATION
# ===========================================================================

def test_workspace_safety_and_key_manifest_integrity():
    """Execute python tools/verify_safety.py to ensure 204 protected files remain 100% bit-exact."""
    assert SAFETY_SCRIPT.exists(), f"Safety verification script missing: {SAFETY_SCRIPT}"

    res = subprocess.run(
        [sys.executable, str(SAFETY_SCRIPT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )

    stdout = res.stdout
    assert res.returncode == 0, f"Safety verification failed (code {res.returncode}):\n{res.stderr}\n{stdout}"
    assert "AUDIT RESULT: PASSED (100% Clean & Untouched)" in stdout, f"Audit did not pass:\n{stdout}"
    assert "All 204 key files verified bit-exact" in stdout, f"Missing 204 bit-exact check in output:\n{stdout}"
    assert "Working tree is 100% clean" in stdout, f"Working tree not clean in output:\n{stdout}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
