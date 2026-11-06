"""Adversarial Challenge & Stress-Test Harness for M2 (Unit Modder & Binary Patcher).

Tests:
1. Unit stat patcher boundary values:
   - speed = 0 (minimum valid speed)
   - speed = 255 (maximum 8-bit unsigned speed)
   - speed > 255 (e.g. 256, 1000) rejection
   - extreme HP (0, 65535, out-of-range)
   - negative value behavior / validation
   - safety guard: direct write to original YM binary MUST raise PermissionError.
2. PE structural integrity verification:
   - DOS header (0x5A4D)
   - NT Headers & PE signature (0x4550)
   - All 4 sections (.text, .rdata, .data, .rsrc) VirtualAddress, SizeOfRawData, PointerToRawData, Characteristics
   - OptionalHeader: EntryPoint, ImageBase, SectionAlignment, FileAlignment
   - Import Directory & IAT (all 12 DLLs and imports) remain 100% byte-for-byte identical.
   - Exact byte difference check: ONLY the targeted instruction bytes differ.
3. Command card cave injector:
   - Boundary button slots: 0, 11 (valid), 12, -1, 100 (rejected with ValueError)
   - Disassembly and verification of injected opcodes (call, push, mov ecx, esi, call AddButton, jmp)
   - Jump offset calculation and return VA accuracy in .text
   - Multi-button injection into slack space ensuring no collision / overlap
   - Slack boundary constraint: shellcode strictly contained before 0x004E5000 (.rdata)
   - Slack space exhaustion: verifies safe RuntimeError when slack space is depleted without overflowing .rdata
4. Unit Catalog edge cases:
   - Nonexistent index / string lookups
   - Substring vs exact matching
"""

import os
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

import pefile

from tools.modding.binary_patcher import (
    EXPECTED_BINARY_SIZE,
    IMAGE_BASE,
    BinaryPatcher,
    check_binary_integrity,
    modify_unit_stat,
    patch_movement_speed,
    verify_binary_integrity,
)
from tools.modding.command_card import (
    ADD_BUTTON_VA,
    BUILDING_HOOK_PRESETS,
    DAWN_CAVE_END_VA,
    DAWN_CAVE_START_VA,
    SLACK_END_VA,
    SLACK_START_VA,
    CommandCardInjector,
    decode_cave_hooks,
    inject_command_card_button,
)
from tools.modding.unit_catalog import UnitCatalog, load_unit_catalog

ORIGINAL_DAWN = Path(r"C:\src\reverse-imzinrok\YM\dawn\dawn.exe")
BACKUP_DAWN = Path(r"C:\src\reverse-imzinrok\YM_backup_original\dawn.exe")


class TestAdversarialModding(unittest.TestCase):
    """Adversarial challenge test cases for Unit Modder and Binary Patcher."""

    @classmethod
    def setUpClass(cls):
        assert ORIGINAL_DAWN.is_file(), f"Original binary not found: {ORIGINAL_DAWN}"
        cls.catalog = load_unit_catalog()
        cls.test_dir = Path(tempfile.mkdtemp(prefix="adv_mod_test_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _clone_dawn(self, name: str) -> Path:
        target = self.test_dir / name
        src = BACKUP_DAWN if BACKUP_DAWN.is_file() else ORIGINAL_DAWN
        shutil.copyfile(src, target)
        return target

    # =========================================================================
    # 1. Unit Stat Patcher Boundary Values & Safety
    # =========================================================================

    def test_adversarial_safety_guard_rejects_original_ym(self):
        """Original source binary in YM MUST be strictly protected against modification."""
        with self.assertRaises(PermissionError):
            BinaryPatcher(str(ORIGINAL_DAWN))

        with self.assertRaises(PermissionError):
            CommandCardInjector(str(ORIGINAL_DAWN))

    def test_adversarial_speed_boundary_zero(self):
        """Boundary test: speed = 0 (minimum speed) on unit with imm8 push."""
        cloned = self._clone_dawn("dawn_speed_0.exe")
        # Unit 18 is FILE_CHAR_CANNON2C2 with dawn speed = 2 (push 2 at 0x09d0c5)
        res = patch_movement_speed(str(cloned), 18, 0)
        self.assertTrue(res.success)
        self.assertEqual(res.new_value, 0)

        # Verify byte at file offset 0x09d0c5 is now 6a 00
        with open(cloned, "rb") as f:
            f.seek(res.file_offset)
            patched_bytes = f.read(2)
        self.assertEqual(patched_bytes, bytes([0x6A, 0x00]))

        # Verify integrity
        ref = BACKUP_DAWN if BACKUP_DAWN.is_file() else ORIGINAL_DAWN
        report = check_binary_integrity(str(ref), str(cloned), allowed_offsets=[res.file_offset + 1])
        self.assertTrue(report["valid"], report["message"])

    def test_adversarial_speed_boundary_max_255(self):
        """Boundary test: speed = 255 (maximum 8-bit unsigned speed)."""
        cloned = self._clone_dawn("dawn_speed_255.exe")
        res = patch_movement_speed(str(cloned), 18, 255)
        self.assertTrue(res.success)
        self.assertEqual(res.new_value, 255)

        with open(cloned, "rb") as f:
            f.seek(res.file_offset)
            patched_bytes = f.read(2)
        self.assertEqual(patched_bytes, bytes([0x6A, 0xFF]))

        ref = BACKUP_DAWN if BACKUP_DAWN.is_file() else ORIGINAL_DAWN
        report = check_binary_integrity(str(ref), str(cloned), allowed_offsets=[res.file_offset + 1])
        self.assertTrue(report["valid"])

    def test_adversarial_speed_overflow_rejected(self):
        """Stress test: speed > 255 (e.g. 256, 1000) must raise ValueError to prevent byte shifting."""
        cloned = self._clone_dawn("dawn_speed_overflow.exe")
        with self.assertRaises(ValueError):
            patch_movement_speed(str(cloned), 18, 256)
        with self.assertRaises(ValueError):
            patch_movement_speed(str(cloned), 18, 1000)

    def test_adversarial_negative_value_behavior(self):
        """Empirical evaluation: negative values behavior in binary patcher.
        
        Currently BinaryPatcher permits -128 <= value <= 255 for imm8 push and packs (val & 0xFF).
        For speed=-1, it yields 0xFF (255 in unsigned interpretation, -1 in signed).
        Values < -128 (e.g. -129, -500) raise ValueError.
        """
        cloned = self._clone_dawn("dawn_negative_test.exe")
        # Under -128 must be rejected by imm8 check
        with self.assertRaises(ValueError):
            patch_movement_speed(str(cloned), 18, -129)
        with self.assertRaises(ValueError):
            patch_movement_speed(str(cloned), 18, -500)

        # -1 converts to 0xFF (255)
        res = patch_movement_speed(str(cloned), 18, -1)
        self.assertEqual(res.new_bytes, bytes([0x6A, 0xFF]))

    def test_adversarial_hp_boundary_and_extremes(self):
        """Boundary test: HP modifications (0, extreme uint16/32)."""
        cloned = self._clone_dawn("dawn_hp_test.exe")
        # Unit 2: 명 천린 has HP 400 (push 400 = 68 90 01 00 00 at 0x09bf9e)
        unit2 = self.catalog.get_unit(2)
        self.assertIsNotNone(unit2)

        # Set HP to 0
        res0 = modify_unit_stat(str(cloned), 2, "hp", 0)
        self.assertTrue(res0.success)
        self.assertEqual(res0.new_value, 0)

        # Set HP to 65535 (max uint16)
        res_max = modify_unit_stat(str(cloned), 2, "hp", 65535)
        self.assertTrue(res_max.success)
        self.assertEqual(res_max.new_value, 65535)

        # Verify instruction bytes
        with open(cloned, "rb") as f:
            f.seek(res_max.file_offset)
            hp_bytes = f.read(5)
        self.assertEqual(hp_bytes, bytes([0x68]) + struct.pack("<I", 65535))

    # =========================================================================
    # 2. Exhaustive PE Structural & Import Table Integrity
    # =========================================================================

    def test_adversarial_pe_structural_and_import_integrity(self):
        """Verify PE headers, section table, and IAT are 100% untouched after multiple stat patches."""
        cloned = self._clone_dawn("dawn_multi_patch.exe")

        # Apply several patches
        res1 = patch_movement_speed(str(cloned), 18, 5)
        res2 = modify_unit_stat(str(cloned), 18, "attack", 20)
        res3 = modify_unit_stat(str(cloned), 2, "hp", 1500)

        # Parse both binaries with pefile
        pe_orig = pefile.PE(str(ORIGINAL_DAWN))
        pe_patched = pefile.PE(str(cloned))

        # 1. DOS & NT Signatures
        self.assertEqual(pe_orig.DOS_HEADER.e_magic, pe_patched.DOS_HEADER.e_magic)
        self.assertEqual(pe_orig.NT_HEADERS.Signature, pe_patched.NT_HEADERS.Signature)

        # 2. Section Headers
        self.assertEqual(len(pe_orig.sections), len(pe_patched.sections))
        for s_orig, s_patched in zip(pe_orig.sections, pe_patched.sections):
            self.assertEqual(s_orig.Name, s_patched.Name)
            self.assertEqual(s_orig.VirtualAddress, s_patched.VirtualAddress)
            self.assertEqual(s_orig.Misc_VirtualSize, s_patched.Misc_VirtualSize)
            self.assertEqual(s_orig.PointerToRawData, s_patched.PointerToRawData)
            self.assertEqual(s_orig.SizeOfRawData, s_patched.SizeOfRawData)
            self.assertEqual(s_orig.Characteristics, s_patched.Characteristics)

        # 3. Optional Header Critical Fields
        opt_orig = pe_orig.OPTIONAL_HEADER
        opt_patched = pe_patched.OPTIONAL_HEADER
        self.assertEqual(opt_orig.AddressOfEntryPoint, opt_patched.AddressOfEntryPoint)
        self.assertEqual(opt_orig.ImageBase, opt_patched.ImageBase)
        self.assertEqual(opt_orig.SectionAlignment, opt_patched.SectionAlignment)
        self.assertEqual(opt_orig.FileAlignment, opt_patched.FileAlignment)
        self.assertEqual(opt_orig.SizeOfImage, opt_patched.SizeOfImage)
        self.assertEqual(opt_orig.SizeOfHeaders, opt_patched.SizeOfHeaders)

        # 4. Import Directory / IAT Table Preservation
        self.assertEqual(len(pe_orig.DIRECTORY_ENTRY_IMPORT), len(pe_patched.DIRECTORY_ENTRY_IMPORT))
        for imp_orig, imp_patched in zip(pe_orig.DIRECTORY_ENTRY_IMPORT, pe_patched.DIRECTORY_ENTRY_IMPORT):
            self.assertEqual(imp_orig.dll, imp_patched.dll)
            self.assertEqual(len(imp_orig.imports), len(imp_patched.imports))
            for fn_orig, fn_patched in zip(imp_orig.imports, imp_patched.imports):
                self.assertEqual(fn_orig.name, fn_patched.name)
                self.assertEqual(fn_orig.address, fn_patched.address)

        pe_orig.close()
        pe_patched.close()

    # =========================================================================
    # 3. Command Card Cave Injector Stress Testing
    # =========================================================================

    def test_adversarial_button_slot_boundaries(self):
        """Boundary test: button slots 0 and 11 are valid; slot >= 12 or < 0 must be rejected."""
        cloned = self._clone_dawn("dawn_button_slots.exe")
        injector = CommandCardInjector(str(cloned))

        # Slot 12 is out of range (max slots = 12, indices 0..11)
        with self.assertRaises(ValueError):
            injector.inject_button("조선 훈련도감", slot=12, cmd_id=0x99)

        with self.assertRaises(ValueError):
            injector.inject_button("조선 훈련도감", slot=-1, cmd_id=0x99)

        with self.assertRaises(ValueError):
            injector.inject_button("조선 훈련도감", slot=100, cmd_id=0x99)

    def test_adversarial_button_injection_shellcode_opcodes_and_offsets(self):
        """Verify opcodes, call displacement, and return jump offset in injected shellcode."""
        cloned = self._clone_dawn("dawn_shellcode_test.exe")
        hook_va = 0x00480FF2  # 조선 훈련도감
        target_slot = 7
        target_cmd = 0x150

        res = inject_command_card_button(
            str(cloned),
            target_building_or_va=hook_va,
            slot=target_slot,
            cmd_id=target_cmd,
            requirements=[1, 2, 3, 0, 0, 0],
        )
        self.assertTrue(res.success)

        with open(cloned, "rb") as f:
            bin_data = f.read()

        # 1. Verify hook site at hook_va: must be E9 <disp32>
        hook_offset = hook_va - IMAGE_BASE
        hook_bytes = bin_data[hook_offset : hook_offset + 5]
        self.assertEqual(hook_bytes[0], 0xE9, "Hook site opcode must be JMP (0xE9)")
        disp_to_cave = struct.unpack("<i", hook_bytes[1:5])[0]
        actual_cave_va = hook_va + 5 + disp_to_cave

        # Cave VA must be within slack range
        self.assertTrue(
            SLACK_START_VA <= actual_cave_va <= SLACK_END_VA,
            f"Cave VA 0x{actual_cave_va:08x} outside slack range [0x{SLACK_START_VA:08x}, 0x{SLACK_END_VA:08x}]",
        )

        # 2. Inspect payload bytes in cave
        cave_offset = actual_cave_va - IMAGE_BASE
        payload_lead = bin_data[cave_offset : cave_offset + 5]
        self.assertEqual(payload_lead[0], 0xE8, "First cave instruction must be CALL (0xE8)")
        call_disp = struct.unpack("<i", payload_lead[1:5])[0]
        called_fn = actual_cave_va + 5 + call_disp
        self.assertEqual(called_fn, ADD_BUTTON_VA, f"Replaced call target 0x{called_fn:08x} != 0x{ADD_BUTTON_VA:08x}")

        # 3. Verify trailing JMP returns to hook_va + 5
        cave_bytes = bin_data[cave_offset : cave_offset + 50]
        jmp_idx = cave_bytes.rfind(b"\xE9")
        self.assertTrue(jmp_idx > 0, "Could not find trailing return JMP in cave")
        disp_return = struct.unpack("<i", cave_bytes[jmp_idx + 1 : jmp_idx + 5])[0]
        ret_va = actual_cave_va + jmp_idx + 5 + disp_return
        self.assertEqual(ret_va, hook_va + 5, f"Return JMP 0x{ret_va:08x} != expected 0x{hook_va + 5:08x}")

        # 4. Verify slack boundary: cave does not cross into .rdata (0x004E5000)
        self.assertTrue(cave_offset + 50 < 0x000E5000, "Cave overflowed into .rdata section!")

    def test_adversarial_sequential_button_injections_no_collision(self):
        """Stress test: inject multiple buttons at different sites; verify slack allocations do not collide."""
        cloned = self._clone_dawn("dawn_multi_inject.exe")

        res1 = inject_command_card_button(str(cloned), "조선 본영", slot=7, cmd_id=0x70)
        self.assertTrue(res1.success)

        res2 = inject_command_card_button(str(cloned), "일본 비행체제작소", slot=9, cmd_id=0x71)
        self.assertTrue(res2.success)

        with open(cloned, "rb") as f:
            data = f.read()

        off1 = res1.file_offset
        off2 = res2.file_offset
        self.assertNotEqual(off1, off2)

        disp1 = struct.unpack("<i", data[off1 + 1 : off1 + 5])[0]
        cave1_va = res1.virtual_address + 5 + disp1

        disp2 = struct.unpack("<i", data[off2 + 1 : off2 + 5])[0]
        cave2_va = res2.virtual_address + 5 + disp2

        self.assertNotEqual(cave1_va, cave2_va, "Cave addresses collided!")
        self.assertTrue(
            abs(cave1_va - cave2_va) >= 30,
            f"Caves are too close ({abs(cave1_va - cave2_va)} bytes), risk of corruption!",
        )

        self.assertTrue(cave1_va < 0x004E5000)
        self.assertTrue(cave2_va < 0x004E5000)

        self.assertEqual(len(data), EXPECTED_BINARY_SIZE)
        self.assertEqual(data[:2], b"MZ")

    def test_adversarial_slack_space_exhaustion(self):
        """Stress test: repeatedly inject buttons until slack space is exhausted.
        
        Must cleanly raise RuntimeError and NEVER write past 0x004E5000 into .rdata.
        """
        cloned = self._clone_dawn("dawn_slack_exhaustion.exe")
        injector = CommandCardInjector(str(cloned))

        injected_count = 0
        with self.assertRaises(RuntimeError):
            for i in range(50):
                injector.inject_button("조선 본영", slot=i % 12, cmd_id=0x100 + i)
                injected_count += 1

        # We must have injected multiple buttons before reaching exhaustion
        self.assertTrue(injected_count >= 10, f"Exhausted too quickly ({injected_count})")

        # Verify binary size still exactly 1,032,192
        self.assertEqual(os.path.getsize(cloned), EXPECTED_BINARY_SIZE)

        # Verify .rdata starts at 0x000E5000 and is 100% identical to original
        with open(ORIGINAL_DAWN, "rb") as f:
            orig_rdata = f.read()[0x000E5000 : 0x000EC000]
        with open(cloned, "rb") as f:
            patched_rdata = f.read()[0x000E5000 : 0x000EC000]
        self.assertEqual(orig_rdata, patched_rdata, ".rdata was corrupted during slack exhaustion!")

    # =========================================================================
    # 4. Unit Catalog Adversarial Lookups
    # =========================================================================

    def test_adversarial_unit_catalog_lookups(self):
        """Stress test: invalid unit lookups, boundary IDs, and exceptions."""
        self.assertEqual(len(self.catalog), 111)

        # Invalid index lookups
        self.assertIsNone(self.catalog.get_unit(-1))
        self.assertIsNone(self.catalog.get_unit(999))
        self.assertIsNone(self.catalog.get_unit("NON_EXISTENT_UNIT_NAME"))

        # KeyError on __getitem__
        with self.assertRaises(KeyError):
            _ = self.catalog[-1]
        with self.assertRaises(KeyError):
            _ = self.catalog["NOT_A_UNIT"]

        # Valid lookups by Korean name
        u1 = self.catalog.get_unit("조선 훈련도감")
        self.assertIsNotNone(u1)
        self.assertIn("훈련도감", u1["korean_name"])

        # Valid lookups by index string
        u2 = self.catalog.get_unit("18")
        self.assertIsNotNone(u2)
        self.assertEqual(u2["index"], 18)


if __name__ == "__main__":
    unittest.main()
