"""
tests/test_custom_unit_buttons.py - Automated Unit & Integration Tests for Custom Unit Buttons

Verifies:
1. tools/assets/generate_custom_unit_buttons.py functionality
2. web_prototype/assets/ui/buttons/ asset integrity:
   - 10 canonical PNG buttons (btn_unit_0x70.png .. btn_unit_0x79.png)
   - 10 named alias PNG buttons (btn_unit_yusaeng.png .. btn_unit_bulgasari.png)
   - Exact 34x34 resolution and valid RGBA channels
   - Beveled RTS button border (highlight top/left, shadow bottom/right)
3. buttons_manifest.json schema and metadata completeness
4. web_prototype/js/ui/command_card.js JavaScript HUD integration via Node.js
"""

import json
import subprocess
import sys
from pathlib import Path
from PIL import Image
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUTTONS_DIR = PROJECT_ROOT / "web_prototype" / "assets" / "ui" / "buttons"
MANIFEST_FILE = BUTTONS_DIR / "buttons_manifest.json"

EXPECTED_UNITS = [
    {"kind_id": 0x70, "kind_hex": "0x70", "id": "yusaeng", "name": "유생", "hotkey": "Y", "slot": 9, "bldg": "chosun_hq", "rice": 250, "potato": 0},
    {"kind_id": 0x71, "kind_hex": "0x71", "id": "geomsul_nangin", "name": "검술 낭인", "hotkey": "K", "slot": 8, "bldg": "chosun_barracks", "rice": 180, "potato": 0},
    {"kind_id": 0x72, "kind_hex": "0x72", "id": "jochong_nangin", "name": "조총 낭인", "hotkey": "N", "slot": 9, "bldg": "chosun_barracks", "rice": 240, "potato": 0},
    {"kind_id": 0x73, "kind_hex": "0x73", "id": "gumiho", "name": "구미호", "hotkey": "F", "slot": 11, "bldg": "chosun_hq", "rice": 280, "potato": 50},
    {"kind_id": 0x74, "kind_hex": "0x74", "id": "wangbeol", "name": "조선왕벌", "hotkey": "B", "slot": 7, "bldg": "chosun_stables", "rice": 200, "potato": 50},
    {"kind_id": 0x75, "kind_hex": "0x75", "id": "horangi", "name": "조선 호랑이", "hotkey": "T", "slot": 8, "bldg": "chosun_stables", "rice": 300, "potato": 0},
    {"kind_id": 0x76, "kind_hex": "0x76", "id": "teolgamyeon", "name": "털가면", "hotkey": "M", "slot": 10, "bldg": "chosun_barracks", "rice": 220, "potato": 40},
    {"kind_id": 0x77, "kind_hex": "0x77", "id": "seolnyeo", "name": "설녀", "hotkey": "S", "slot": 9, "bldg": "chosun_stables", "rice": 280, "potato": 60},
    {"kind_id": 0x78, "kind_hex": "0x78", "id": "dokkaebi", "name": "조선 도깨비", "hotkey": "D", "slot": 10, "bldg": "chosun_stables", "rice": 320, "potato": 0},
    {"kind_id": 0x79, "kind_hex": "0x79", "id": "bulgasari", "name": "불가살이", "hotkey": "U", "slot": 10, "bldg": "chosun_hq", "rice": 380, "potato": 100},
]


def test_generator_script_execution(tmp_path):
    """Test tools/assets/generate_custom_unit_buttons.py generates assets in custom directory."""
    from tools.assets.generate_custom_unit_buttons import generate_custom_buttons

    manifest = generate_custom_buttons(tmp_path, verbose=False)
    assert manifest["total_units"] == 10
    assert (tmp_path / "buttons_manifest.json").exists()

    for u in EXPECTED_UNITS:
        hex_file = tmp_path / f"btn_unit_{u['kind_hex'].lower()}.png"
        named_file = tmp_path / f"btn_unit_{u['id']}.png"
        assert hex_file.exists(), f"Missing {hex_file}"
        assert named_file.exists(), f"Missing {named_file}"


def test_button_png_dimensions_and_channels():
    """Verify all 10 canonical button PNGs are 34x34 RGBA images with valid bevel borders."""
    assert BUTTONS_DIR.exists(), f"Buttons directory not found: {BUTTONS_DIR}"

    for u in EXPECTED_UNITS:
        btn_file = BUTTONS_DIR / f"btn_unit_{u['kind_hex'].lower()}.png"
        assert btn_file.exists(), f"Missing canonical button file: {btn_file}"

        with Image.open(btn_file) as im:
            assert im.size == (34, 34), f"{btn_file.name} size is {im.size}, expected (34, 34)"
            assert im.mode == "RGBA", f"{btn_file.name} mode is {im.mode}, expected RGBA"

            # Check that button is not empty / transparent
            bbox = im.getbbox()
            assert bbox == (0, 0, 34, 34), f"{btn_file.name} bbox is {bbox}"

            # Verify RTS border bevel:
            # Top-left (0, 0) should be highlight (lighter)
            tl_pixel = im.getpixel((0, 0))
            # Bottom-right (33, 33) should be shadow (darker)
            br_pixel = im.getpixel((33, 33))
            assert tl_pixel[0] > br_pixel[0], f"Bevel highlight failed in {btn_file.name}: TL={tl_pixel}, BR={br_pixel}"


def test_button_named_aliases():
    """Verify that named aliases exist and match canonical files."""
    for u in EXPECTED_UNITS:
        hex_file = BUTTONS_DIR / f"btn_unit_{u['kind_hex'].lower()}.png"
        named_file = BUTTONS_DIR / f"btn_unit_{u['id']}.png"
        assert named_file.exists(), f"Missing alias button file: {named_file}"
        assert hex_file.read_bytes() == named_file.read_bytes(), f"Mismatch between {hex_file.name} and {named_file.name}"


def test_buttons_manifest_schema_and_contents():
    """Verify buttons_manifest.json conforms to required schema and data mappings."""
    assert MANIFEST_FILE.exists(), f"Missing buttons_manifest.json at {MANIFEST_FILE}"

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_units"] == 10
    assert data["button_width"] == 34
    assert data["button_height"] == 34
    assert len(data["units"]) == 10

    # Check units list
    for expected in EXPECTED_UNITS:
        match = next((u for u in data["units"] if u["kind_id"] == expected["kind_id"]), None)
        assert match is not None, f"Unit {expected['kind_hex']} not found in manifest units list"

        assert match["kind_hex"] == expected["kind_hex"]
        assert match["id"] == expected["id"]
        assert match["name"] == expected["name"]
        assert match["hotkey"] == expected["hotkey"]
        assert match["slot"] == expected["slot"]
        assert match["building_id"] == expected["bldg"]
        assert match["cost_rice"] == expected["rice"]
        assert match["cost_potato"] == expected["potato"]
        assert "icon_url" in match and match["icon_url"].endswith(".png")

    # Check by_kind_hex and by_id indexing
    assert len(data["by_kind_hex"]) == 10
    assert len(data["by_id"]) == 10
    for expected in EXPECTED_UNITS:
        assert expected["kind_hex"] in data["by_kind_hex"]
        assert expected["id"] in data["by_id"]

    # Check building groupings
    assert len(data["by_building"]["chosun_hq"]) == 3  # 유생, 불가살이, 구미호
    assert len(data["by_building"]["chosun_barracks"]) == 3  # 검술 낭인, 조총 낭인, 털가면
    assert len(data["by_building"]["chosun_stables"]) == 4  # 조선왕벌, 호랑이, 설녀, 도깨비


def test_command_card_js_integration():
    """Execute Node.js test script to verify command_card.js HUD integration."""
    node_test_code = """
    import { CommandCardHUD, COMMAND_HOTKEYS, CUSTOM_JOSEON_UNITS } from './web_prototype/js/ui/command_card.js';
    import assert from 'node:assert';

    console.log('Testing CommandCardHUD Custom Unit Integration...');

    // 1. Verify CUSTOM_JOSEON_UNITS array
    assert.strictEqual(CUSTOM_JOSEON_UNITS.length, 10, 'Must have 10 custom Joseon units');
    const yusaeng = CUSTOM_JOSEON_UNITS.find(u => u.kindId === 0x70);
    assert.ok(yusaeng, 'Yusaeng must exist');
    assert.strictEqual(yusaeng.hotkey, 'Y');
    assert.strictEqual(yusaeng.costRice, 250);

    // 2. Headless CommandCardHUD instance
    let triggeredCmd = null;
    const hud = new CommandCardHUD(null, (cmd) => {
        triggeredCmd = cmd;
    });

    // 3. getCustomUnitButtonDef
    const btn70 = hud.getCustomUnitButtonDef(0x70);
    assert.ok(btn70, 'Button def for 0x70 must be returned');
    assert.strictEqual(btn70.hotkey, 'Y');
    assert.strictEqual(btn70.isCustomUnit, true);
    assert.ok(btn70.iconUrl.includes('btn_unit_0x70.png'));

    const btnHorangi = hud.getCustomUnitButtonDef('horangi');
    assert.ok(btnHorangi, 'Button def for horangi must be returned');
    assert.strictEqual(btnHorangi.kindId, 0x75);
    assert.strictEqual(btnHorangi.hotkey, 'T');

    // 4. setBuildingCustomUnitCommands for Chosun HQ
    hud.setBuildingCustomUnitCommands('조선 본영');
    assert.ok(hud.slots[9], 'Slot 9 must have 유생');
    assert.strictEqual(hud.slots[9].unitId, 'yusaeng');
    assert.ok(hud.slots[10], 'Slot 10 must have 불가살이');
    assert.strictEqual(hud.slots[10].unitId, 'bulgasari');
    assert.ok(hud.slots[11], 'Slot 11 must have 구미호');
    assert.strictEqual(hud.slots[11].unitId, 'gumiho');

    // Trigger slot 9 (유생)
    hud.triggerSlot(9);
    assert.ok(triggeredCmd, 'Triggering slot 9 must invoke callback');
    assert.strictEqual(triggeredCmd.unitId, 'yusaeng');

    // 5. setBuildingCustomUnitCommands for Chosun Barracks
    hud.setBuildingCustomUnitCommands('조선 훈련소');
    assert.strictEqual(hud.slots[8].unitId, 'geomsul_nangin');
    assert.strictEqual(hud.slots[9].unitId, 'jochong_nangin');
    assert.strictEqual(hud.slots[10].unitId, 'teolgamyeon');

    // 6. setBuildingCustomUnitCommands for Chosun Stables
    hud.setBuildingCustomUnitCommands('조선 목장/마구간');
    assert.strictEqual(hud.slots[7].unitId, 'wangbeol');
    assert.strictEqual(hud.slots[8].unitId, 'horangi');
    assert.strictEqual(hud.slots[9].unitId, 'seolnyeo');
    assert.strictEqual(hud.slots[10].unitId, 'dokkaebi');

    // 7. Full custom unit command layout
    hud.setCustomJoseonUnitButtons();
    let customCount = hud.slots.filter(s => s && s.isCustomUnit).length;
    assert.ok(customCount >= 9, 'Custom layout must have at least 9 custom units placed');

    console.log('[PASS] All CommandCardHUD custom unit checks passed!');
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", node_test_code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Node.js integration test failed:\n{res.stderr}\n{res.stdout}"
    assert "[PASS]" in res.stdout
