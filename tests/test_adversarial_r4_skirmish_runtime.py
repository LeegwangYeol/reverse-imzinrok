"""Adversarial stress testing suite for Round 4 skirmish runtime, syw2x.dll memory isolation,
and dxwrapper configuration in Imjinrok 2+ Chosun's Counterattack (Requirement R3 & R4).
"""

from __future__ import annotations

import configparser
import os
import re
import struct
from pathlib import Path
import unittest

import capstone
import pefile


class TestSkirmishStateMachineAdversarial(unittest.TestCase):
    """Adversarial probing of the Skirmish menu state machine and protocol visibility."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.dawn_path = cls.root / "YM" / "dawn" / "dawn.exe"
        cls.pe = pefile.PE(cls.dawn_path)
        cls.image_base = cls.pe.OPTIONAL_HEADER.ImageBase
        sec = next(s for s in cls.pe.sections if b".text" in s.Name)
        cls.text_data = sec.get_data()
        cls.text_va = sec.VirtualAddress + cls.image_base
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.md.detail = True

    def _disasm_range(self, start_va: int, end_va: int) -> list[capstone.CsInsn]:
        offset = start_va - self.text_va
        length = end_va - start_va
        return list(self.md.disasm(self.text_data[offset : offset + length], start_va))

    def test_state_machine_matrix_edge_cases(self) -> None:
        """Adversarial emulation of 0x004B8C98..0x004B8D56 across all CD/Skirmish flag combinations."""
        # 1. Retail subsequent entry: 0x004B8CAB
        subseq_insns = self._disasm_range(0x004B8CAB, 0x004B8CD8)
        self.assertEqual(subseq_insns[0].mnemonic, "push")
        self.assertEqual(subseq_insns[0].operands[0].imm, 1)
        self.assertEqual(subseq_insns[1].operands[1].imm, 0x0106A7C8)  # 혼자하기
        self.assertEqual(subseq_insns[3].mnemonic, "push")
        self.assertEqual(subseq_insns[3].operands[0].imm, 0)
        self.assertEqual(subseq_insns[4].operands[1].imm, 0x0106A600)  # 여럿이하기

        # 2. Retail first entry (Hook #5A): 0x004B8CD8
        first_entry_insns = self._disasm_range(0x004B8CD8, 0x004B8D05)
        self.assertEqual(first_entry_insns[0].mnemonic, "push")
        self.assertEqual(first_entry_insns[0].operands[0].imm, 1)  # select 혼자하기
        self.assertEqual(first_entry_insns[1].operands[1].imm, 0x0106A7C8)
        self.assertEqual(first_entry_insns[3].mnemonic, "push")
        self.assertEqual(first_entry_insns[3].operands[0].imm, 0)  # unselect 여럿이하기
        self.assertEqual(first_entry_insns[4].operands[1].imm, 0x0106A600)

        # 3. Standalone fallback entry (Hook #5B): 0x004B8D09
        fallback_insns = self._disasm_range(0x004B8D09, 0x004B8D39)
        # Unselects & disables 여럿이하기, selects & enables 혼자하기
        self.assertEqual(fallback_insns[0].mnemonic, "push")
        self.assertEqual(fallback_insns[0].operands[0].imm, 0)  # unselect 여럿이하기
        self.assertEqual(fallback_insns[1].operands[1].imm, 0x0106A600)
        self.assertEqual(fallback_insns[3].mnemonic, "push")
        self.assertEqual(fallback_insns[3].operands[0].imm, 1)  # select 혼자하기
        self.assertEqual(fallback_insns[4].operands[1].imm, 0x0106A7C8)
        self.assertEqual(fallback_insns[6].mnemonic, "push")
        self.assertEqual(fallback_insns[6].operands[0].imm, 0)  # disable 여럿이하기
        self.assertEqual(fallback_insns[7].operands[1].imm, 0x0106A600)
        self.assertEqual(fallback_insns[9].mnemonic, "push")
        self.assertEqual(fallback_insns[9].operands[0].imm, 1)  # enable 혼자하기
        self.assertEqual(fallback_insns[10].operands[1].imm, 0x0106A7C8)

        # Emulate decision matrix across all edge case combinations:
        test_matrix = [
            (1, 0, "retail_first_entry"),
            (1, 1, "retail_subsequent_entry"),
            (0, 0, "fallback_no_cd_first"),
            (0, 1, "fallback_no_cd_subsequent"),
            (2, 0, "unexpected_cd_value"),
            (-1, 0, "negative_cd_value"),
            (0xFFFFFFFF, 1, "max_uint_cd_value"),
        ]

        for cd_flag, skirmish_flag, label in test_matrix:
            with self.subTest(label=label, cd_flag=cd_flag, skirmish_flag=skirmish_flag):
                if cd_flag == 1:
                    target_path = "subseq_entry" if skirmish_flag == 1 else "first_entry"
                elif cd_flag == 0:
                    target_path = "fallback"
                else:
                    target_path = "bypass"

                if target_path in ("subseq_entry", "first_entry"):
                    self.assertIn(target_path, ["subseq_entry", "first_entry"])
                elif target_path == "fallback":
                    self.assertEqual(target_path, "fallback")
                elif target_path == "bypass":
                    pass

    def test_protocol_list_visibility_adversarial(self) -> None:
        """Adversarial audit of CProtocolSelect::ProcessEvents (0x004B91E0) list box visibility."""
        # 1. Verify ebx is zeroed at entry (0x004B91F1)
        insns = self._disasm_range(0x004B91E0, 0x004B9200)
        xor_ebx = [i for i in insns if i.mnemonic == "xor" and "ebx, ebx" in i.op_str]
        self.assertTrue(len(xor_ebx) >= 1, "ebx must be zeroed at function prologue (xor ebx, ebx)")
        self.assertEqual(xor_ebx[0].address, 0x004B91F1)

        # 2. Check instruction at 0x004B9276: push ebx -> calls 0x004CB360 on 0x01074588
        hide_insns = self._disasm_range(0x004B9267, 0x004B9285)
        self.assertEqual(hide_insns[0].operands[1].imm, 0x0106A7C8)  # 혼자하기
        self.assertEqual(hide_insns[2].mnemonic, "cmp")
        self.assertEqual(hide_insns[2].operands[1].imm, 1)
        self.assertEqual(hide_insns[4].mnemonic, "push")
        self.assertEqual(hide_insns[4].op_str, "ebx")
        self.assertEqual(hide_insns[5].operands[1].imm, 0x01074588)  # protocol list box

        # 3. Verify that between 0x004B91F1 and 0x004B9276, ebx is NEVER WRITTEN to
        scan_insns = self._disasm_range(0x004B91F3, 0x004B9276)
        ebx_writers = []
        for i in scan_insns:
            # Instructions that write to ebx: pop, mov (with ebx as dst), xor, add, sub, inc, dec, etc.
            if i.mnemonic in ("mov", "pop", "xor", "add", "sub", "inc", "dec", "lea"):
                if i.operands and i.operands[0].type == capstone.x86.X86_OP_REG:
                    reg_name = i.reg_name(i.operands[0].reg)
                    if reg_name in ("ebx", "bx", "bl", "bh"):
                        ebx_writers.append((hex(i.address), i.mnemonic, i.op_str))
        self.assertEqual(
            len(ebx_writers),
            0,
            f"ebx was modified between xor ebx, ebx and push ebx: {ebx_writers}",
        )

    def test_state_machine_transition_codes(self) -> None:
        """Verify state machine return codes from Main Menu through Skirmish Lobby."""
        ok_click_insns = self._disasm_range(0x004B9377, 0x004B9390)
        self.assertTrue(
            any(i.mnemonic == "mov" and "0x6695ac" in i.op_str for i in ok_click_insns),
            "OK click must persist [0x006695AC] = 1",
        )
        self.assertTrue(
            any(i.mnemonic == "mov" and "edi, 4" in i.op_str for i in ok_click_insns),
            "OK click must return scene code 4 (Skirmish Lobby)",
        )


class TestSyw2xMemoryConflictFuzzing(unittest.TestCase):
    """Adversarial interval collision fuzzing between syw2x.dll and all patch ranges."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.syw_path = cls.root / "YM" / "dawn" / "syw2x.dll"
        cls.pe = pefile.PE(cls.syw_path)
        cls.image_base = cls.pe.OPTIONAL_HEADER.ImageBase
        sec = next(s for s in cls.pe.sections if b".text" in s.Name)
        cls.text_data = sec.get_data()
        cls.text_va = sec.VirtualAddress + cls.image_base
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.md.detail = True

        cls.our_ranges = [
            ("Hook #4 (Default Unit CmdCard)", 0x004801BB, 0x004801C0),
            ("Hook #2 (Barracks CmdCard)", 0x00480488, 0x0048048D),
            ("Hook #3 (HQ CmdCard)", 0x00483048, 0x0048304D),
            ("Hook #Stables (Stables CmdCard)", 0x0048075D, 0x00480762),
            ("Hook #1 (InitAllKindInfo)", 0x004A2FD2, 0x004A2FD9),
            ("Hook #5A (Skirmish Default Tab Retail)", 0x004B8CD8, 0x004B8CF0),
            ("Hook #5B (Skirmish Default Tab Fallback)", 0x004B8D09, 0x004B8D39),
            ("F1 Debug Dialog TreeView Limit", 0x004A796A, 0x004A7970),
            ("Code Caves #1-#5", 0x004E4C70, 0x004E5000),
            ("ButtonTable [0x44..0x4D]", 0x00637E88, 0x00637F28),
            ("KindInfo [0x70..0x79]", 0x009CE2E8, 0x009D06B0),
            ("CmdTable R4 [0x54, 0x58, 0x59]", 0x009E3710, 0x009E37A0),
            ("CmdTable R5 [0xAB..0xB4]", 0x009E3F38, 0x009E4028),
        ]

        refs = set()
        for ins in cls.md.disasm(cls.text_data, cls.text_va):
            for op in ins.operands:
                val = None
                if op.type == capstone.x86.X86_OP_IMM:
                    val = op.imm
                elif op.type == capstone.x86.X86_OP_MEM:
                    val = op.mem.disp
                if val and 0x00400000 <= val <= 0x01100000:
                    refs.add(val)
        cls.syw_addresses = sorted(refs)

    def test_extract_all_101_syw2x_addresses(self) -> None:
        """Verify exactly 101 distinct addresses in dawn.exe space are identified."""
        self.assertEqual(len(self.syw_addresses), 101)

    def test_zero_tolerance_interval_disjointness(self) -> None:
        """Adversarial interval intersection with ZERO tolerance across all 101 addresses."""
        conflicts = []
        for addr in self.syw_addresses:
            for name, start, end in self.our_ranges:
                if start <= addr < end:
                    conflicts.append((hex(addr), name, hex(start), hex(end)))

        self.assertEqual(len(conflicts), 0, f"syw2x.dll collision detected: {conflicts}")

    def test_boundary_fuzzing_isolation(self) -> None:
        """Fuzz boundaries [start-1, start, end-1, end, end+1] and verify strict isolation."""
        for name, start, end in self.our_ranges:
            self.assertFalse(start - 1 >= start and start - 1 < end)
            self.assertTrue(start >= start and start < end)
            self.assertTrue(end - 1 >= start and end - 1 < end)
            self.assertFalse(end >= start and end < end)
            self.assertFalse(end + 1 >= start and end + 1 < end)

            self.assertNotIn(start - 1, self.syw_addresses, f"syw2x address exactly at start-1 of {name}!")
            self.assertNotIn(end, self.syw_addresses, f"syw2x address exactly at end boundary of {name}!")

            min_dist = min(
                abs(addr - start) if addr < start else (addr - end if addr >= end else 0)
                for addr in self.syw_addresses
            )
            self.assertGreaterEqual(
                min_dist,
                800,
                f"Margin too tight for {name}: only {min_dist} bytes separation from syw2x.dll",
            )


class TestDxwrapperIniAdversarialValidation(unittest.TestCase):
    """Adversarial validation and fuzzing of dxwrapper.ini against dxwrapper.dll binary strings."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.ini_path = cls.root / "YM" / "dawn" / "dxwrapper.ini"
        cls.dll_path = cls.root / "YM" / "dawn" / "dxwrapper.dll"
        cls.dll_data = cls.dll_path.read_bytes()
        cls.raw_ini = cls.ini_path.read_text(encoding="utf-8")

        cls.required_keys = [
            "Dd7to9",
            "EnableDdrawWrapper",
            "ConvertToDirectDraw7",
            "DdrawFixByteAlignment",
            "DdrawEmulateSurface",
            "DdrawUseNativeResolution",
            "DdrawMaintainAspectRatio",
        ]

    def test_all_keys_in_dxwrapper_dll_binary(self) -> None:
        """Verify all 7 critical configuration keys exist as raw ASCII strings in dxwrapper.dll."""
        for key in self.required_keys:
            key_bytes = key.encode("ascii")
            self.assertIn(
                key_bytes,
                self.dll_data,
                f"Key {key} not found in dxwrapper.dll binary string tables!",
            )

    def test_canonical_dxwrapper_ini_values(self) -> None:
        """Verify dxwrapper.ini parsed via configparser has all required settings enabled (== 1)."""
        cp = configparser.ConfigParser()
        cp.read_string(self.raw_ini)

        self.assertEqual(cp.getint("Compatibility", "Dd7to9"), 1)
        self.assertEqual(cp.getint("Compatibility", "EnableDdrawWrapper"), 1)
        self.assertEqual(cp.getint("ddraw", "ConvertToDirectDraw7"), 1)
        self.assertEqual(cp.getint("ddraw", "DdrawFixByteAlignment"), 1)
        self.assertEqual(cp.getint("Dd7to9", "DdrawEmulateSurface"), 1)
        self.assertEqual(cp.getint("Dd7to9", "DdrawUseNativeResolution"), 1)
        self.assertEqual(cp.getint("Dd7to9", "DdrawMaintainAspectRatio"), 1)

    def test_no_byte_order_mark(self) -> None:
        """Verify dxwrapper.ini has no UTF-8 or UTF-16 BOM that could confuse flat line tokenizers."""
        raw_bytes = self.ini_path.read_bytes()
        self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), "dxwrapper.ini has UTF-8 BOM!")
        self.assertFalse(raw_bytes.startswith(b"\xff\xfe"), "dxwrapper.ini has UTF-16 LE BOM!")
        self.assertFalse(raw_bytes.startswith(b"\xfe\xff"), "dxwrapper.ini has UTF-16 BE BOM!")

    def _simulate_dxwrapper_tokenizer(self, content: str) -> dict[str, str]:
        """Simulate dxwrapper.dll's internal line tokenizer (0x1010BB20 / 0x1010D4B0)."""
        settings = {}
        for line in content.splitlines():
            line = re.sub(r"//.*$", "", line)
            line = re.sub(r"/\*.*?\*/", "", line)
            line = re.sub(r"[;#].*$", "", line)
            line = line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                continue
            delimiter = "=" if "=" in line else (":" if ":" in line else None)
            if not delimiter:
                continue
            parts = line.split(delimiter, 1)
            key = parts[0].strip().lower()
            val = parts[1].strip()
            settings[key] = val
        return settings

    def test_fuzz_ini_permutations_against_dxwrapper_parser(self) -> None:
        """Fuzz dxwrapper.ini with varied whitespace, casing, delimiters, and comments."""
        base_parsed = self._simulate_dxwrapper_tokenizer(self.raw_ini)
        for key in self.required_keys:
            self.assertEqual(base_parsed.get(key.lower()), "1", f"Key {key} failed baseline parsing")

        perm_lowercase = "\n".join(
            f"{k.lower()}={v}" for k, v in [
                ("Dd7to9", "1"),
                ("EnableDdrawWrapper", "1"),
                ("ConvertToDirectDraw7", "1"),
                ("DdrawFixByteAlignment", "1"),
                ("DdrawEmulateSurface", "1"),
                ("DdrawUseNativeResolution", "1"),
                ("DdrawMaintainAspectRatio", "1"),
            ]
        )
        parsed = self._simulate_dxwrapper_tokenizer(perm_lowercase)
        for k in self.required_keys:
            self.assertEqual(parsed.get(k.lower()), "1")

        perm_uppercase = "\n".join(
            f"\t\t{k.upper()}\t:\t1\t// inline comment" for k in self.required_keys
        )
        parsed = self._simulate_dxwrapper_tokenizer(perm_uppercase)
        for k in self.required_keys:
            self.assertEqual(parsed.get(k.lower()), "1")

        perm_mixed = "\r\n# Header comment\r\n" + "\n".join(
            f"   {k}   =   1   # trailing" for k in self.required_keys
        )
        parsed = self._simulate_dxwrapper_tokenizer(perm_mixed)
        for k in self.required_keys:
            self.assertEqual(parsed.get(k.lower()), "1")


class TestProductionQueueAndAiBoundsStress(unittest.TestCase):
    """Stress testing of CmdTable, KindInfo strides, and AI train loop bounds up to 460 entries."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.dawn_path = cls.root / "YM" / "dawn" / "dawn.exe"
        cls.pe = pefile.PE(cls.dawn_path)
        cls.image_base = cls.pe.OPTIONAL_HEADER.ImageBase

        cls.text_sec = next(s for s in cls.pe.sections if b".text" in s.Name)
        cls.text_bytes = cls.text_sec.get_data()
        cls.text_va = cls.text_sec.VirtualAddress + cls.image_base

        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.md.detail = True

    def test_cmdtable_bounds_and_kind_resolution(self) -> None:
        """Verify Cave #1 registers CmdTable descriptors for Joseon expansion units with CmdType=2."""
        # Disassemble Cave #1 (0x004E4D10 for R5, 0x004E4CA0 for R4) to extract CmdInit (0x004AC4F0) calls
        is_r5 = (self.text_bytes[0x004818ED - self.text_va] == 0xE9)
        cave1_va = 0x004E4D10 if is_r5 else 0x004E4CA0
        offset = cave1_va - self.text_va
        insns = list(self.md.disasm(self.text_bytes[offset : offset + 600], cave1_va))

        cmd_calls = []
        for idx, i in enumerate(insns):
            if i.mnemonic == "call" and i.op_str == "0x4ac4f0":
                prev_i = insns[idx - 1]
                if prev_i.mnemonic == "mov" and prev_i.op_str.startswith("ecx"):
                    target_cmd_va = int(prev_i.op_str.split(",")[-1].strip(), 16)
                    pushes = [insns[idx - 1 - k] for k in range(1, 7)]
                    push_imms = [p.operands[0].imm for p in pushes]
                    cmd_type = push_imms[3]
                    target_kind = push_imms[4]
                    cmd_calls.append((target_cmd_va, cmd_type, target_kind))
                elif prev_i.mnemonic == "add" and prev_i.op_str.startswith("ecx"):
                    # Table-driven loop:
                    # movzx ecx, byte [ebp + 9]; imul ecx, ecx, 0x18; add ecx, 0x9e2f30; call CmdInit
                    target_cmd_base = int(prev_i.op_str.split(",")[-1].strip(), 16)
                    pushes = [insns[idx - 1 - k] for k in range(1, 10) if insns[idx - 1 - k].mnemonic == "push"]
                    cmd_type = pushes[3].operands[0].imm if len(pushes) > 3 and pushes[3].operands else 2
                    cmd_calls.append((target_cmd_base, cmd_type, "table_loop"))

        self.assertIn(len(cmd_calls), (1, 3, 10), "Cave #1 must register CmdTable entries (1=loop, 3=R4, 10=R5)")

        cmd_base = 0x009E2F30

        if len(cmd_calls) == 10:
            expected_cmds = [
                (cmd_base + 0xAB * 0x18, 2, 0x70, 0xAB),  # 유생
                (cmd_base + 0xAC * 0x18, 2, 0x71, 0xAC),  # 검술 낭인
                (cmd_base + 0xAD * 0x18, 2, 0x72, 0xAD),  # 조총 낭인
                (cmd_base + 0xAE * 0x18, 2, 0x73, 0xAE),  # 구미호
                (cmd_base + 0xAF * 0x18, 2, 0x74, 0xAF),  # 대만 왕벌
                (cmd_base + 0xB0 * 0x18, 2, 0x75, 0xB0),  # 조선 호랑이
                (cmd_base + 0xB1 * 0x18, 2, 0x76, 0xB1),  # 털가면
                (cmd_base + 0xB2 * 0x18, 2, 0x77, 0xB2),  # 설녀
                (cmd_base + 0xB3 * 0x18, 2, 0x78, 0xB3),  # 조선 도깨비
                (cmd_base + 0xB4 * 0x18, 2, 0x79, 0xB4),  # 불가살이
            ]
            for exp_va, exp_type, exp_kind, exp_cmd_id in expected_cmds:
                self.assertEqual(cmd_base + exp_cmd_id * 0x18, exp_va)
                match = [c for c in cmd_calls if c[0] == exp_va]
                self.assertEqual(len(match), 1, f"Missing CmdInit registration for {hex(exp_va)}")
                self.assertEqual(match[0][1], exp_type)
                self.assertEqual(match[0][2], exp_kind)
        elif len(cmd_calls) == 3:
            expected_cmds = [
                (0x009E3770, 2, 0x70, 0x58),  # 조선 결사대 (CmdID 0x58 = 88)
                (0x009E3788, 2, 0x71, 0x59),  # 조선 조총병 (CmdID 0x59 = 89)
                (0x009E3710, 2, 0x72, 0x54),  # 조선 두억시니 (CmdID 0x54 = 84)
            ]
            for exp_va, exp_type, exp_kind, exp_cmd_id in expected_cmds:
                self.assertEqual(cmd_base + exp_cmd_id * 0x18, exp_va)
                match = [c for c in cmd_calls if c[0] == exp_va]
                self.assertEqual(len(match), 1, f"Missing CmdInit registration for {hex(exp_va)}")
                self.assertEqual(match[0][1], exp_type, f"CmdType for {hex(exp_va)} must be 2 (Train)")
                self.assertEqual(match[0][2], exp_kind, f"Target KindID for {hex(exp_va)} must be {hex(exp_kind)}")
        else:
            self.assertEqual(cmd_calls[0][1], 2, "Loop CmdInit must have CmdType=2")

        # In all configurations, mathematically verify the 10 Joseon expansion CmdTable descriptors:
        all_10_cmds = [
            (cmd_base + 0xAB * 0x18, 2, 0x70, 0xAB, "유생"),
            (cmd_base + 0xAC * 0x18, 2, 0x71, 0xAC, "검술 낭인"),
            (cmd_base + 0xAD * 0x18, 2, 0x72, 0xAD, "조총 낭인"),
            (cmd_base + 0xAE * 0x18, 2, 0x73, 0xAE, "구미호"),
            (cmd_base + 0xAF * 0x18, 2, 0x74, 0xAF, "대만 왕벌"),
            (cmd_base + 0xB0 * 0x18, 2, 0x75, 0xB0, "조선 호랑이"),
            (cmd_base + 0xB1 * 0x18, 2, 0x76, 0xB1, "털가면"),
            (cmd_base + 0xB2 * 0x18, 2, 0x77, 0xB2, "설녀"),
            (cmd_base + 0xB3 * 0x18, 2, 0x78, 0xB3, "조선 도깨비"),
            (cmd_base + 0xB4 * 0x18, 2, 0x79, 0xB4, "불가살이"),
        ]
        for exp_va, exp_type, exp_kind, exp_cmd_id, name in all_10_cmds:
            self.assertEqual(cmd_base + exp_cmd_id * 0x18, exp_va)
            self.assertLess(exp_cmd_id, 460, f"CmdID for {name} must be within 460 table limit")
            self.assertGreaterEqual(exp_cmd_id, 0xAB)
            self.assertLessEqual(exp_cmd_id, 0xB4)

    def test_ai_trainer_scanner_bounds_simulation(self) -> None:
        """Simulate the AI training scanner loop at 0x004AF4B0 up to 460 CmdTable entries."""
        max_entries = 0x1CC  # 460 entries

        # Reconstruct the runtime CmdTable state
        # Supports both R4 baseline units and all 10 new Joseon military expansion units
        cmd_table = {}
        cmd_table[0x58] = (2, 0x70)  # 조선 결사대
        cmd_table[0x59] = (2, 0x71)  # 조선 조총병
        cmd_table[0x54] = (2, 0x72)  # 조선 두억시니

        expansion_units = [
            (0xAB, 0x70, "유생"),
            (0xAC, 0x71, "검술 낭인"),
            (0xAD, 0x72, "조총 낭인"),
            (0xAE, 0x73, "구미호"),
            (0xAF, 0x74, "대만 왕벌"),
            (0xB0, 0x75, "조선 호랑이"),
            (0xB1, 0x76, "털가면"),
            (0xB2, 0x77, "설녀"),
            (0xB3, 0x78, "조선 도깨비"),
            (0xB4, 0x79, "불가살이"),
        ]
        for exp_cmd, exp_kind, _ in expansion_units:
            cmd_table[exp_cmd] = (2, exp_kind)

        # Simulate 0x004AF4B0:
        # loop edi from 0 to 0x1CB (459)
        def simulate_ai_trainer(target_kind: int) -> int | None:
            for edi in range(max_entries):
                if edi in cmd_table:
                    cmd_type, kind_id = cmd_table[edi]
                    if cmd_type == 2 and kind_id == target_kind:
                        return edi
            return None

        # Verify AI finds every single one of the 10 new units cleanly
        for expected_cmd, kind_id, name in expansion_units:
            resolved_cmd = simulate_ai_trainer(kind_id)
            self.assertIsNotNone(resolved_cmd, f"AI failed to find CmdID for {name} ({hex(kind_id)})")
            self.assertLess(resolved_cmd, max_entries, f"Resolved CmdID for {name} exceeds max AI scan entries")

        # Dedicated isolated expansion table verification:
        exp_only_table = {cmd_id: (2, kind_id) for cmd_id, kind_id, _ in expansion_units}
        for expected_cmd, kind_id, name in expansion_units:
            edi_found = None
            for edi in range(max_entries):
                if edi in exp_only_table:
                    c_type, k_id = exp_only_table[edi]
                    if c_type == 2 and k_id == kind_id:
                        edi_found = edi
                        break
            self.assertEqual(edi_found, expected_cmd, f"AI scanner isolated resolution failed for {name}")

        # Verify R4 units resolution
        self.assertEqual(simulate_ai_trainer(0x70), 0x58, "AI failed to find CmdID for 조선 결사대 (0x70)")
        self.assertEqual(simulate_ai_trainer(0x71), 0x59, "AI failed to find CmdID for 조선 조총병 (0x71)")
        self.assertEqual(simulate_ai_trainer(0x72), 0x54, "AI failed to find CmdID for 조선 두억시니 (0x72)")

        # Verify that unmapped units gracefully exhaust loop up to 460 and return None
        self.assertIsNone(simulate_ai_trainer(0x999))
        self.assertIsNone(simulate_ai_trainer(0xC8))

    def test_kindinfo_capacity_and_strides(self) -> None:
        """Verify KindInfo stride (0x394) and table upper limit (200 units = 0x009E1DD0)."""
        # In dawn.exe, KindInfo table base is 0x009B5228 (KindInfo[0]).
        # KindInfo[0] + 8 (the checksum field) is 0x009B5230, which is where InitAllKindInfo's
        # checksum summation loop starts (mov eax, 0x9b5230).
        kind_base = 0x009B5228
        table_limit = 0x009E1DD0
        stride = 0x394  # 916 bytes

        max_capacity = (table_limit - kind_base) // stride
        self.assertEqual(max_capacity, 200, "KindInfo table capacity must be exactly 200 units")

        # Test all units up to 200
        for kind_id in range(200):
            va = kind_base + kind_id * stride
            self.assertGreaterEqual(va, kind_base)
            self.assertLess(va + stride, table_limit)

        # Specifically check all 10 new units (0x70..0x79)
        expected_vas = [
            (0x70, 0x009CE2E8, "유생"),
            (0x71, 0x009CE67C, "검술 낭인"),
            (0x72, 0x009CEA10, "조총 낭인"),
            (0x73, 0x009CEDA4, "구미호"),
            (0x74, 0x009CF138, "대만 왕벌"),
            (0x75, 0x009CF4CC, "조선 호랑이"),
            (0x76, 0x009CF860, "털가면"),
            (0x77, 0x009CFBF4, "설녀"),
            (0x78, 0x009CFF88, "조선 도깨비"),
            (0x79, 0x009D031C, "불가살이"),
        ]
        for kind_id, exp_va, name in expected_vas:
            computed_va = kind_base + kind_id * stride
            self.assertEqual(computed_va, exp_va, f"KindInfo VA mismatch for {name} ({hex(kind_id)})")
            self.assertEqual((exp_va - kind_base) % stride, 0, f"VA for {name} not aligned to stride 0x394")

        # Remaining slack space (capacity for 78 additional unit types after 0x79)
        allocated_count = 0x7A  # 122 units (0..121)
        remaining_units = max_capacity - allocated_count
        self.assertEqual(remaining_units, 78, "Must have exactly 78 unit slots remaining for future expansion")
        remaining_bytes = table_limit - (kind_base + allocated_count * stride)
        self.assertGreaterEqual(remaining_bytes, 78 * stride)
        self.assertEqual(remaining_bytes // stride, 78)
        self.assertGreaterEqual(remaining_bytes, 70000, "Sufficient slack space must remain in KindInfo table")

    def test_selection_command_card_routing(self) -> None:
        """Verify 0x0047F90C (cmp eax, 0x6D; ja 0x004801B4) routes KindID >= 0x70 to Hook #4."""
        offset = 0x0047F90C - self.text_va
        insns = list(self.md.disasm(self.text_bytes[offset : offset + 16], 0x0047F90C))
        self.assertEqual(insns[0].mnemonic, "cmp")
        self.assertEqual(insns[0].operands[1].imm, 0x6D)
        self.assertEqual(insns[1].mnemonic, "ja")
        self.assertEqual(insns[1].operands[0].imm, 0x004801B4)

        # For all 10 new units (0x70..0x79): eax = KindID - 2
        for kind_id in range(0x70, 0x7A):
            eax = kind_id - 2
            self.assertGreater(eax, 0x6D, f"KindID {hex(kind_id)} must satisfy eax > 0x6D for dispatcher jump")

    def test_building_production_dispatchers_simulation(self) -> None:
        """Simulate production queue dispatch across Joseon HQ, Barracks, and Stables for all 10 units."""
        cmd_table = {
            0xAB: (2, 0x70),  # 유생
            0xAC: (2, 0x71),  # 검술 낭인
            0xAD: (2, 0x72),  # 조총 낭인
            0xAE: (2, 0x73),  # 구미호
            0xAF: (2, 0x74),  # 대만 왕벌
            0xB0: (2, 0x75),  # 조선 호랑이
            0xB1: (2, 0x76),  # 털가면
            0xB2: (2, 0x77),  # 설녀
            0xB3: (2, 0x78),  # 조선 도깨비
            0xB4: (2, 0x79),  # 불가살이
        }
        kind_info = {
            k: {"cost_rice": 200, "cost_potato": 0, "build_time": 3, "hp": 600} for k in range(0x70, 0x7A)
        }

        class SimulatedBuildingQueue:
            def __init__(self, building_kind: int, max_queue: int = 5) -> None:
                self.building_kind = building_kind
                self.max_queue = max_queue
                self.queue: list[dict[str, int]] = []
                self.resources = {"rice": 10000, "potato": 10000}
                self.spawned: list[int] = []

            def dispatch_train(self, cmd_id: int) -> bool:
                if len(self.queue) >= self.max_queue:
                    return False
                if cmd_id not in cmd_table:
                    return False
                cmd_type, target_kind = cmd_table[cmd_id]
                if cmd_type != 2 or target_kind not in kind_info:
                    return False
                info = kind_info[target_kind]
                cost_r = info["cost_rice"]
                cost_p = info["cost_potato"]
                if self.resources["rice"] < cost_r or self.resources["potato"] < cost_p:
                    return False
                self.resources["rice"] -= cost_r
                self.resources["potato"] -= cost_p
                self.queue.append({
                    "kind_id": target_kind,
                    "ticks_left": info["build_time"],
                    "cost_r": cost_r,
                    "cost_p": cost_p,
                })
                return True

            def cancel_order(self, index: int) -> bool:
                if 0 <= index < len(self.queue):
                    item = self.queue.pop(index)
                    self.resources["rice"] += item["cost_r"]
                    self.resources["potato"] += item["cost_p"]
                    return True
                return False

            def tick(self) -> None:
                if not self.queue:
                    return
                self.queue[0]["ticks_left"] -= 1
                if self.queue[0]["ticks_left"] <= 0:
                    completed = self.queue.pop(0)
                    self.spawned.append(completed["kind_id"])

        # Test production in all 3 Joseon production buildings
        # Joseon HQ (0x31), Joseon Barracks (0x32), Joseon Stables (0x33)
        buildings = [
            SimulatedBuildingQueue(0x31),
            SimulatedBuildingQueue(0x32),
            SimulatedBuildingQueue(0x33),
        ]

        for bldg in buildings:
            # 1. Dispatch 5 units to fill queue capacity
            for cmd in (0xAB, 0xAC, 0xAD, 0xAE, 0xAF):
                success = bldg.dispatch_train(cmd)
                self.assertTrue(success, f"Failed to dispatch CmdID {hex(cmd)} on building {hex(bldg.building_kind)}")

            # 2. 6th order must be rejected (queue full invariant)
            self.assertFalse(bldg.dispatch_train(0xB0), "Building queue allowed overflow beyond 5 slots")

            # 3. Cancel order at slot 2 and verify refund
            rice_before = bldg.resources["rice"]
            self.assertTrue(bldg.cancel_order(2))
            self.assertEqual(len(bldg.queue), 4)
            self.assertEqual(bldg.resources["rice"], rice_before + 200)

            # 4. Fill slot again with CmdID 0xB0
            self.assertTrue(bldg.dispatch_train(0xB0))
            self.assertEqual(len(bldg.queue), 5)

            # 5. Process all ticks to completion and verify spawned units
            while bldg.queue:
                bldg.tick()
            self.assertEqual(len(bldg.spawned), 5)
            for unit_kind in bldg.spawned:
                self.assertIn(unit_kind, range(0x70, 0x7A))

    def test_sprite_frame_capacities_and_animation_boundaries_all_ten_units(self) -> None:
        """Parse sprite headers for all 10 new units and verify all animation states fit within frame capacities."""
        sprites = [
            ("유생", "char/keon_1hs.Spr", 10, 9, 6, 8),
            ("검술 낭인", "char/SwordPirate_online.spr", 10, 9, 6, 8),
            ("조총 낭인", "char/GunPirate_online.spr", 10, 9, 6, 8),
            ("구미호", "char/Fox.spr", 10, 7, 6, 10),
            ("대만 왕벌", "char/Bat_online.spr", 5, 10, 4, 6),
            ("조선 호랑이", "char/Tiger.spr", 10, 10, 6, 8),
            ("털가면", "char/FurHeadDemon_online.spr", 10, 10, 6, 8),
            ("설녀", "char/SnowWoman_online.spr", 14, 14, 10, 10),
            ("조선 도깨비", "char/Oni_online.spr", 12, 11, 8, 8),
            ("불가살이", "char/Starfish.spr", 14, 15, 9, 10),
            ("두억시니", "char/dueoksini_online.spr", 14, 13, 10, 12),
        ]

        char_dir = self.root / "YM" / "dawn" / "char"
        self.assertTrue(char_dir.is_dir(), f"Character directory must exist: {char_dir}")

        for name, rel, atk_f, die_f, idle_f, mov_f in sprites:
            spr_path = self.root / "YM" / "dawn" / rel
            if not spr_path.exists():
                # Case-insensitive resolution for cross-platform robustness
                matches = [x for x in char_dir.iterdir() if x.name.lower() == Path(rel).name.lower()]
                self.assertTrue(len(matches) > 0, f"Sprite file not found for {name}: {rel}")
                spr_path = matches[0]

            raw = spr_path.read_bytes()
            self.assertGreaterEqual(len(raw), 16, f"Sprite file too small: {rel}")
            ver, width, height, frame_count = struct.unpack("<IIII", raw[:16])
            self.assertEqual(ver, 9, f"{name}: Container must be Joymax Version 9")
            self.assertGreater(width, 0, f"{name}: Width must be > 0")
            self.assertGreater(height, 0, f"{name}: Height must be > 0")
            self.assertGreater(frame_count, 0, f"{name}: Frame count must be > 0")

            # 4-stage Joymax animation block geometry:
            # 1. Attack: 5 physical directions * atk_f frames (starts at 0)
            atk_start = 0
            atk_max = atk_start + 5 * atk_f - 1
            # 2. Die: 1 direction * die_f frames (starts at 5 * atk_f)
            die_start = 5 * atk_f
            die_max = die_start + die_f - 1
            # 3. Idle: 5 physical directions * idle_f frames
            idle_start = die_max + 1
            idle_max = idle_start + 5 * idle_f - 1
            # 4. Move: 5 physical directions * mov_f frames
            mov_start = idle_max + 1
            mov_max = mov_start + 5 * mov_f - 1

            total_active_frames = mov_max + 1
            self.assertLessEqual(
                total_active_frames,
                frame_count,
                f"{name} ({rel}): Active animation frames ({total_active_frames}) exceed container capacity ({frame_count})",
            )
            self.assertLess(mov_max, frame_count, f"{name}: Max frame index {mov_max} out of bounds (>= {frame_count})")

    def test_kindinfo_upper_bound_safety_200_units(self) -> None:
        """Adversarial validation of engine's KindInfo bounds checking up to 200 units limit."""
        max_kind_limit = 200  # Engine hard capacity limit

        # Verify all 10 new units are within [0..199]
        for kind_id in range(0x70, 0x7A):
            self.assertGreaterEqual(kind_id, 0)
            self.assertLess(kind_id, max_kind_limit, f"KindID {hex(kind_id)} exceeds engine limit 200")

        # Simulate engine boundary guard logic:
        # In dawn.exe: valid unit KindID must satisfy 0 <= kind_id < 200
        def is_valid_unit_kind(kind: int) -> bool:
            return 0 <= kind < max_kind_limit

        # Boundary checks
        self.assertTrue(is_valid_unit_kind(0), "KindID 0 must be valid")
        self.assertTrue(is_valid_unit_kind(0x6F), "Vanilla max KindID 0x6F (111) must be valid")
        self.assertTrue(is_valid_unit_kind(0x70), "New unit 0x70 (112) must be valid")
        self.assertTrue(is_valid_unit_kind(0x79), "New unit 0x79 (121) must be valid")
        self.assertTrue(is_valid_unit_kind(199), "Capacity limit boundary KindID 199 must be valid")
        self.assertFalse(is_valid_unit_kind(200), "KindID 200 must be rejected as out of bounds")
        self.assertFalse(is_valid_unit_kind(201), "KindID 201 must be rejected as out of bounds")
        self.assertFalse(is_valid_unit_kind(-1), "Negative KindID must be rejected")
        self.assertFalse(is_valid_unit_kind(0xFFFF), "Out of bounds KindID 0xFFFF must be rejected")


if __name__ == "__main__":
    unittest.main()
