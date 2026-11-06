"""
Test Suite for R1: Unit Catalog, Unit Stat Modder, PE Binary Patcher, and Command Card Button Injector
Imjinrok 2+ Dawn Modding Toolkit
"""

import os
import unittest
from pathlib import Path

from tests.conftest import (
    DAWN_EXE,
    ORIGINAL_DAWN_EXE,
    USEMAP_EXE,
    ORIGINAL_DAWN_EXE_SIZE,
    get_temp_dir,
    clone_dawn_exe,
    sha256_file,
)
from tools.modding.unit_catalog import (
    UnitCatalog,
    load_unit_catalog,
)
from tools.modding.binary_patcher import (
    BinaryPatcher,
    PatchResult,
    check_binary_integrity,
    verify_binary_integrity,
    STAT_TO_ARG,
    EXPECTED_BINARY_SIZE,
)
from tools.modding.command_card import (
    CommandCardInjector,
    decode_cave_hooks,
    inject_command_card_button,
    DAWN_HOOKS_METADATA,
    BUILDING_HOOK_PRESETS,
)


class TestUnitCatalog(unittest.TestCase):
    """Tier 1: Unit Catalog and RE dataset verification."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_unit_catalog()
        cls.temp_dir = get_temp_dir("catalog_test_")

    def test_catalog_size_and_completeness(self):
        """Verify catalog contains >= 40 units (in fact 111 units) and indices."""
        self.assertGreaterEqual(len(self.catalog), 40)
        self.assertEqual(len(self.catalog), 111)

    def test_unit_fields_presence(self):
        """Verify that every unit has Korean name, call VA, file offset, stats, and sprite info."""
        for unit in self.catalog:
            self.assertIn("index", unit)
            self.assertIn("korean_name", unit)
            self.assertTrue(len(unit["korean_name"]) > 0)
            self.assertIn("call_va", unit)
            self.assertIn("call_file_offset", unit)
            self.assertIn("speed_field", unit)
            self.assertIn("hp_field", unit)
            self.assertIn("attack_field", unit)
            self.assertIn("cost", unit)

    def test_korean_name_query(self):
        """Verify queries by Korean name (e.g. 명 천린, 조선 신기전망루, 일본 농부)."""
        chenlin = self.catalog.get_unit("명 천린")
        self.assertIsNotNone(chenlin)
        self.assertEqual(chenlin["index"], 2)

        tower = self.catalog.get_unit("조선 신기전망루")
        self.assertIsNotNone(tower)
        self.assertEqual(tower["index"], 5)

        farmer = self.catalog.get_unit("일본 농부")
        self.assertIsNotNone(farmer)
        self.assertIn(farmer["index"], (50, 88))

    def test_diff_against_usemap(self):
        """Verify that catalog detects stat diffs between Dawn and UseMap."""
        diffs = self.catalog.get_diff_summary()
        self.assertGreater(len(diffs), 10, "Expected at least 10 stat diffs between Dawn and UseMap")

    def test_export_catalog_to_json_and_csv(self):
        """Verify exporting catalog to human-readable JSON and CSV files."""
        json_out = self.temp_dir / "units.json"
        csv_out = self.temp_dir / "units.csv"

        self.catalog.export_to_json(str(json_out))
        self.catalog.export_to_csv(str(csv_out))

        self.assertTrue(json_out.exists())
        self.assertGreater(json_out.stat().st_size, 50000)

        self.assertTrue(csv_out.exists())
        self.assertGreater(csv_out.stat().st_size, 5000)

        # Check CSV header
        lines = csv_out.read_text(encoding="utf-8-sig").splitlines()
        self.assertIn("korean_name", lines[0])
        self.assertIn("speed_dawn", lines[0])


class TestBinaryPatcher(unittest.TestCase):
    """Tier 1, Tier 2 & Tier 4: PE Binary Patcher and Safety Tests."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("patcher_test_")

    def test_safety_refusal_to_patch_original(self):
        """Tier 2: Refuse to patch original source binary in YM/dawn/dawn.exe."""
        with self.assertRaises(PermissionError):
            BinaryPatcher(str(DAWN_EXE))

    def test_patch_unit_speed(self):
        """Modify unit movement speed on cloned binary and verify operands."""
        test_exe = clone_dawn_exe(self.temp_dir)
        orig_sha = sha256_file(test_exe)

        patcher = BinaryPatcher(str(test_exe))
        # Patch 일본 농부 (index 50) speed from default 7 to 9
        res = patcher.patch_unit_stat(50, "speed", 9)
        self.assertTrue(res.success)
        self.assertEqual(res.new_value, 9)
        self.assertNotEqual(sha256_file(test_exe), orig_sha)

        # Re-read target byte in binary
        with open(test_exe, "rb") as f:
            f.seek(res.file_offset)
            patched_bytes = f.read(len(res.new_bytes))
        self.assertEqual(patched_bytes, res.new_bytes)

    def test_patch_multiple_stats(self):
        """Modify HP, MP, Attack, and Cost on cloned binary in sequence."""
        test_exe = clone_dawn_exe(self.temp_dir)
        patcher = BinaryPatcher(str(test_exe))

        # 1. Modify HP
        res_hp = patcher.patch_unit_stat(50, "hp", 1250)
        self.assertTrue(res_hp.success)
        self.assertEqual(res_hp.new_value, 1250)

        # 2. Modify Attack
        res_atk = patcher.patch_unit_stat(50, "attack", 25)
        self.assertTrue(res_atk.success)
        self.assertEqual(res_atk.new_value, 25)

        # 3. Modify Cost Rice
        res_cost = patcher.patch_unit_stat(50, "cost_rice", 3000)
        self.assertTrue(res_cost.success)
        self.assertEqual(res_cost.new_value, 3000)

    def test_pe_header_preservation_after_patches(self):
        """Verify that PE headers, alignments, and untouched sections remain 100% intact."""
        test_exe = clone_dawn_exe(self.temp_dir)
        patcher = BinaryPatcher(str(test_exe))

        # Apply patch
        res = patcher.patch_unit_stat(50, "speed", 8)
        self.assertTrue(res.success)

        # Check binary integrity
        base_orig = ORIGINAL_DAWN_EXE if ORIGINAL_DAWN_EXE.exists() else DAWN_EXE
        report = check_binary_integrity(
            orig_path=str(base_orig),
            patched_path=str(test_exe),
            allowed_offsets=[res.file_offset, res.file_offset + 1],
        )
        self.assertTrue(report["pe_headers_intact"])
        self.assertTrue(report["size_valid"])
        self.assertTrue(report["valid"], f"Integrity failed: {report['message']}")
        self.assertTrue(verify_binary_integrity(str(base_orig), str(test_exe)))

    def test_invalid_unit_or_stat_rejection(self):
        """Tier 2: Unknown unit or unsupported stat raises KeyError or ValueError."""
        test_exe = clone_dawn_exe(self.temp_dir)
        patcher = BinaryPatcher(str(test_exe))

        with self.assertRaises(KeyError):
            patcher.patch_unit_stat("존재하지않는유닛999", "speed", 10)

        with self.assertRaises(ValueError):
            patcher.patch_unit_stat(50, "invalid_stat_xyz", 10)


class TestCommandCardHooksAndInjection(unittest.TestCase):
    """Tier 1, Tier 2 & Tier 4: Command card code cave decoder and button injector."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("cmd_card_test_")

    def test_decode_dawn_cave_hooks(self):
        """Verify decoding of the 6 Dawn mod code cave hook sites."""
        hooks = decode_cave_hooks(str(DAWN_EXE))
        self.assertEqual(len(hooks), 6)

        # Verify all 6 hooks are hooked in dawn.exe
        for h in hooks:
            self.assertTrue(h["hooked"], f"Hook {h['hook_id']} at 0x{h['hook_va']:08x} not hooked!")
            self.assertIn("injected_buttons", h)
            self.assertGreater(len(h["injected_buttons"]), 0)

    def test_inject_new_button_into_slack_space(self):
        """Inject a custom command card button into available zero-slack space."""
        test_exe = clone_dawn_exe(self.temp_dir)
        orig_sha = sha256_file(test_exe)

        # Inject into "조선 훈련도감" (hook VA 0x00480FF2) slot 9 with custom cmd_id 0x99
        res = inject_command_card_button(
            binary_path=str(test_exe),
            target_building_or_va="조선 훈련도감",
            slot=9,
            cmd_id=0x99,
            requirements=[0, 0, 0, 0, 0, 0],
        )

        self.assertTrue(res.success)
        self.assertEqual(res.unit_index, 9)
        self.assertNotEqual(sha256_file(test_exe), orig_sha)

        # Verify binary size remains strictly identical
        self.assertEqual(test_exe.stat().st_size, EXPECTED_BINARY_SIZE)

        # Verify PE headers remain intact
        report = check_binary_integrity(str(DAWN_EXE), str(test_exe))
        self.assertTrue(report["pe_headers_intact"])
        self.assertTrue(report["size_valid"])

    def test_invalid_slot_rejection(self):
        """Tier 2: Slot index >= 12 or < 0 raises ValueError (command card is 4x3 = 12 buttons)."""
        test_exe = clone_dawn_exe(self.temp_dir)
        injector = CommandCardInjector(str(test_exe))

        with self.assertRaises(ValueError):
            injector.assemble_button_hook(
                cave_va=0x004E4C70,
                hook_site_va=0x00480FF2,
                slot=12,  # Invalid: max slot is 11
                cmd_id=0x25,
            )
        with self.assertRaises(ValueError):
            injector.assemble_button_hook(
                cave_va=0x004E4C70,
                hook_site_va=0x00480FF2,
                slot=-1,
                cmd_id=0x25,
            )


if __name__ == "__main__":
    unittest.main()
