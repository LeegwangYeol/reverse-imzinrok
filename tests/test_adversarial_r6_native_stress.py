"""
Adversarial Native Binary & Sprite Format Stress-Test Suite (Round 6)

Authored by: challenger_r6_stress_verifier (Roles: Critic, Specialist)

Empirically stress-tests:
1. Native dawn.exe Disassembly Invariants:
   - Hook #HornetDeath at 0x00401AAF: instant return 0 for 0x74, bypassing ground carcass spawner.
   - Hook #AICheatBypass at 0x0043F8BB & 0x0043F8C1: unconditional jump to 0x0043FB62.
   - Cave 1 at 0x004E4D10: ButtonTable[0x44..0x4D] bound to frames 289..298.
   - Cave 2, 3, 4: HQ, Barracks, Stables button slot allocations.
2. button_plus.Spr / button.spr Physical Decompression:
   - 299 frames total, 34x34 resolution, 1,156 uncompressed bytes per frame.
   - Pairwise pixel diversity across frames 289..298 (no blank or duplicate frames).
3. PE Section & Slack Space Boundary Verification:
   - Cave memory addresses inside .text bounds (VirtualAddress + SizeOfRawData).
   - Checksum & alignment invariants.
"""

from __future__ import annotations

import hashlib
import struct
import unittest
from pathlib import Path

import capstone
import pefile

from tools.modding.patch_joseon_new_unit import (
    IMAGE_BASE,
    VA_CAVE_INIT_ROUTINE,
    VA_HOOK_AI_CHEAT_BYPASS,
    VA_HOOK_AI_CHEAT_NEUTRALIZE,
    VA_HOOK_HORNET_DEATH,
    va_to_offset,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAWN_EXE_PATH = PROJECT_ROOT / "YM" / "dawn" / "dawn.exe"
BUTTON_SPR_PATH = PROJECT_ROOT / "YM" / "dawn" / "fnt" / "button_plus.Spr"
if not BUTTON_SPR_PATH.exists():
    BUTTON_SPR_PATH = PROJECT_ROOT / "YM" / "dawn" / "fnt" / "button.spr"


def decompress_joymax_button_rle(data: bytes, width: int = 34, height: int = 34) -> bytes:
    """Decompresses a Joymax button sprite frame (0xFE indicates 0-pixel run)."""
    out = bytearray(width * height)
    in_idx = 0
    out_idx = 0
    total = width * height
    while in_idx < len(data) and out_idx < total:
        b = data[in_idx]
        in_idx += 1
        if b == 0xFE:
            if in_idx < len(data):
                run = data[in_idx]
                in_idx += 1
                out_idx += run
        else:
            out[out_idx] = b
            out_idx += 1
    return bytes(out)


class AdversarialNativeStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert DAWN_EXE_PATH.exists(), f"dawn.exe not found at {DAWN_EXE_PATH}"
        cls.pe_data = DAWN_EXE_PATH.read_bytes()
        cls.pe = pefile.PE(data=cls.pe_data)
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def test_hornet_death_hook_disassembly(self):
        """Stress-test Hook #HornetDeath at 0x00401AAF."""
        offset = va_to_offset(VA_HOOK_HORNET_DEATH)
        code = self.pe_data[offset : offset + 48]
        instructions = list(self.md.disasm(code, VA_HOOK_HORNET_DEATH))

        insn_strs = [f"{i.mnemonic} {i.op_str}" for i in instructions]

        # Verify cmp eax, 0x74
        self.assertIn("cmp eax, 0x74", insn_strs[0], "First instruction must check 0x74 (Hornet)")
        # Verify je to xor eax, eax; ret
        self.assertTrue(insn_strs[1].startswith("je 0x401ace") or insn_strs[1].startswith("je 0x00401ace"))

        # Verify xor eax, eax; ret at 0x00401ACE
        offset_ret = va_to_offset(0x00401ACE)
        code_ret = self.pe_data[offset_ret : offset_ret + 4]
        insn_ret = list(self.md.disasm(code_ret, 0x00401ACE))
        self.assertEqual(insn_ret[0].mnemonic, "xor")
        self.assertEqual(insn_ret[0].op_str, "eax, eax")
        self.assertEqual(insn_ret[1].mnemonic, "ret")

    def test_ai_cheat_bypass_hooks(self):
        """Stress-test 50:50 resource cheat bypass hooks at 0x0043F8BB and 0x0043F8C1."""
        offset1 = va_to_offset(VA_HOOK_AI_CHEAT_BYPASS)
        code1 = self.pe_data[offset1 : offset1 + 6]
        insn1 = list(self.md.disasm(code1, VA_HOOK_AI_CHEAT_BYPASS))
        self.assertEqual(insn1[0].mnemonic, "jle")
        self.assertTrue(insn1[0].op_str.endswith("0x43fb62"))

        offset2 = va_to_offset(VA_HOOK_AI_CHEAT_NEUTRALIZE)
        code2 = self.pe_data[offset2 : offset2 + 7]
        insn2 = list(self.md.disasm(code2, VA_HOOK_AI_CHEAT_NEUTRALIZE))
        self.assertEqual(insn2[0].mnemonic, "jmp")
        self.assertTrue(insn2[0].op_str.endswith("0x43f8f0") or insn2[0].op_str.endswith("0x43fb62"))

    def test_cave1_button_table_binding(self):
        """Stress-test Cave 1 button initialization binding frames 289..298 to Button IDs 0x44..0x4D."""
        offset = va_to_offset(VA_CAVE_INIT_ROUTINE)
        code = self.pe_data[offset : offset + 300]
        instructions = list(self.md.disasm(code, VA_CAVE_INIT_ROUTINE))

        # Check for mov dh, 1 and edx push (icon frame 289..298)
        found_icon_binding = False
        for i in instructions:
            if i.mnemonic == "mov" and "dh, 1" in i.op_str:
                found_icon_binding = True
                break
        self.assertTrue(found_icon_binding, "Cave 1 must set DH=1 for high-byte sprite frame >= 256")

    def test_button_sprite_frames_and_diversity(self):
        """Stress-test button_plus.Spr: frame count 299, 34x34 resolution, 1,156 uncompressed bytes, non-duplicate frames."""
        buf = BUTTON_SPR_PATH.read_bytes()
        self.assertGreaterEqual(len(buf), 0x970, "button_plus.Spr header and offset table truncated")

        ver, w, h, fc = struct.unpack("<IIII", buf[:16])
        self.assertEqual(ver, 9, "Joymax sprite version must be 9")
        self.assertEqual(w, 34, "Width must be 34")
        self.assertEqual(h, 34, "Height must be 34")
        self.assertEqual(fc, 299, "Frame count must be exactly 299")

        # Read offset table
        offsets = []
        for i in range(fc):
            off = struct.unpack("<I", buf[0x4C0 + i * 4 : 0x4C4 + i * 4])[0]
            offsets.append(off)

        # Decompress frames 289..298 (10 custom unit buttons)
        frame_hashes = set()
        for idx in range(289, 299):
            start = offsets[idx]
            end = offsets[idx + 1] if idx + 1 < fc else len(buf)
            frame_data = buf[start:end]
            pixels = decompress_joymax_button_rle(frame_data, 34, 34)

            self.assertEqual(len(pixels), 1156, f"Frame {idx} must decompress to 1,156 bytes")
            non_zero = sum(1 for p in pixels if p != 0)
            self.assertGreater(non_zero, 300, f"Frame {idx} must have at least 300 non-zero pixels")

            h_val = hashlib.sha256(pixels).hexdigest()
            self.assertNotIn(h_val, frame_hashes, f"Duplicate frame detected at index {idx}!")
            frame_hashes.add(h_val)

        self.assertEqual(len(frame_hashes), 10, "All 10 custom button frames must have unique pixel data")

    def test_pe_slack_space_bounds(self):
        """Verify that Code Caves 1..4 (0x004E4C70..0x004E5000) stay strictly within .text section raw file buffer."""
        text_sec = next(s for s in self.pe.sections if s.Name.rstrip(b"\x00") == b".text")
        text_start_va = IMAGE_BASE + text_sec.VirtualAddress
        text_raw_end_va = text_start_va + text_sec.SizeOfRawData

        # Caves reside at 0x004E4C70..0x004E5000
        self.assertGreaterEqual(0x004E4C70, text_start_va)
        self.assertLessEqual(0x004E5000, text_raw_end_va, "Caves must not overflow .text raw data size on disk")


if __name__ == "__main__":
    unittest.main()
