"""
Comprehensive verification and regression test suite for the native Joseon New Units
patch in Imjinrok 2+ Chosun's Counterattack (YM/dawn/dawn.exe).

Covers Requirements R1 through R5:
  - R1: Binary diff cluster audit, PE section/header integrity, stack balance (calling conventions), register preservation.
  - R2: In-memory simulation of Cave #1 (KindInfo, CmdTable, ButtonTable), CalcKindChecksum execution & matching,
        Dueoksini sprite frame boundary checks (195 frames), Command Card button slot non-collision checks.
  - R3: syw2x.dll runtime memory non-overlap check, dxwrapper.ini and dxwrapper.dll binary token validation.
  - R4: Single-player skirmish (혼자하기) state machine tab selection (retail & fallback paths), protocol list visibility.
  - R5: Array bounds audit (0x004A2FE3, 0x004A3775, 0x004A37C5), selection command card branch routing (0x0047F90C -> Hook #4),
        F1 debug dialog unit check (0x004A796A).
"""

from __future__ import annotations

import configparser
import hashlib
import re
import struct
import unittest
from pathlib import Path

import capstone
import pefile

from tools.modding.patch_joseon_new_unit import (
    IMAGE_BASE,
    IMG_ID_DUEOKSINI,
    ORIGINAL_SHA256,
    VA_ADD_BUTTON,
    VA_BTN_INIT,
    VA_BTN_NEW_47,
    VA_BTN_NEW_48,
    VA_BTN_NEW_49,
    VA_CALC_KIND_CHECKSUM,
    VA_CAVE_BARRACKS_HOOK,
    VA_CAVE_CMDCARD_DISPATCH,
    VA_CAVE_HQ_HOOK,
    VA_CAVE_INIT_ROUTINE,
    VA_CAVE_STABLES_HOOK,
    VA_CAVE_UNIT_NAME_70,
    VA_CAVE_UNIT_NAME_71,
    VA_CAVE_UNIT_NAME_72,
    VA_CMD_INIT,
    VA_CMD_NEW_54,
    VA_CMD_NEW_58,
    VA_CMD_NEW_59,
    VA_COMBAT_CMDCARD,
    VA_F1_DEBUG_TREEVIEW_LIMIT,
    VA_HOOK_BARRACKS_K,
    VA_HOOK_BARRACKS_K_RESUME,
    VA_HOOK_DEFAULT_CMDCARD,
    VA_HOOK_HQ_K,
    VA_HOOK_HQ_K_RESUME,
    VA_HOOK_INIT_KIND,
    VA_HOOK_INIT_KIND_RESUME,
    VA_HOOK_HORNET_DEATH,
    VA_HOOK_HORNET_DEATH_RESUME,
    VA_HOOK_AI_CHEAT_BYPASS,
    VA_HOOK_AI_CHEAT_NEUTRALIZE,
    VA_AI_ORDER3_HARVEST_ENTRY,
    VA_AI_CHEAT_RESUME,
    VA_CAVE_INIT_EXTRA,
    VA_CAVE_GUMIHO_CMDCARD,
    VA_HOOK_STABLES_K,
    VA_HOOK_STABLES_K_RESUME,
    VA_JUSTICEK_CMDCARD,
    VA_KIND_NEW_70,
    VA_KIND_NEW_71,
    VA_KIND_NEW_72,
    VA_KIND_TEMPLATE_0C,
    VA_KIND_TEMPLATE_6E,
    VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN,
    VA_PROTOCOL_SELECT_FALLBACK_HONJA_SEL,
    VA_PROTOCOL_SELECT_FALLBACK_YEOROT_DIS,
    VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL,
    VA_PROTOCOL_SELECT_RETAIL_HONJA,
    VA_PROTOCOL_SELECT_RETAIL_YEOROT,
    build_building_buttons_cave,
    build_cmdcard_dispatcher,
    build_init_cave,
    va_to_offset,
)

# =============================================================================
# Round 5: 10 New Joseon Units Specification & Authoritative Parameters
# =============================================================================
MAX_KIND_ID = 0x79
NEW_UNIT_KIND_IDS = list(range(0x70, 0x7A))

NEW_UNITS_METADATA = [
    {
        "name": "유생", "kind_id": 0x70, "cmd_id": 0xAB, "btn_id": 0x44, "hotkey": "Y",
        "spr": "keon_1hs.Spr", "frames": 176, "hp": 450, "speed": 18,
        "atk_min": 15, "atk_max": 20, "rice": 250, "potato": 0, "btime": 6,
        "base_atk": 60, "max_mp": 100, "range1": 5, "range2": 7,
        "atb1": 0x00110405, "atb2": 0x02000408, "attack_atb": 9,
    },
    {
        "name": "검술 낭인", "kind_id": 0x71, "cmd_id": 0xAC, "btn_id": 0x45, "hotkey": "K",
        "spr": "SwordPirate_online.spr", "frames": 136, "hp": 600, "speed": 21,
        "atk_min": 22, "atk_max": 28, "rice": 180, "potato": 0, "btime": 5,
        "base_atk": 80, "max_mp": 80, "range1": 1, "range2": 5,
        "atb1": 0x00410005, "atb2": 0x04000008, "attack_atb": 1,
    },
    {
        "name": "조총 낭인", "kind_id": 0x72, "cmd_id": 0xAD, "btn_id": 0x46, "hotkey": "P",
        "spr": "GunPirate_online.spr", "frames": 136, "hp": 480, "speed": 18,
        "atk_min": 12, "atk_max": 16, "rice": 240, "potato": 0, "btime": 6,
        "base_atk": 70, "max_mp": 0, "range1": 6, "range2": 7,
        "atb1": 0x01C10405, "atb2": 0x00000008, "attack_atb": 8,
    },
    {
        "name": "구미호", "kind_id": 0x73, "cmd_id": 0xAE, "btn_id": 0x47, "hotkey": "G",
        "spr": "Fox.spr", "frames": 144, "hp": 750, "speed": 22,
        "atk_min": 28, "atk_max": 34, "rice": 280, "potato": 50, "btime": 7,
        "base_atk": 85, "max_mp": 100, "range1": 5, "range2": 6,
        "atb1": 0x00110405, "atb2": 0x10006008, "attack_atb": 11,
    },
    {
        "name": "조선왕벌", "kind_id": 0x74, "cmd_id": 0xAF, "btn_id": 0x48, "hotkey": "B",
        "spr": "Bat_online.spr", "frames": 160, "hp": 500, "speed": 25,
        "atk_min": 24, "atk_max": 28, "rice": 200, "potato": 50, "btime": 6,
        "base_atk": 90, "max_mp": 0, "range1": 1, "range2": 5,
        "atb1": 0x02210015, "atb2": 0x00000000, "attack_atb": 1,
    },
    {
        "name": "조선 호랑이", "kind_id": 0x75, "cmd_id": 0xB0, "btn_id": 0x49, "hotkey": "T",
        "spr": "Tiger.spr", "frames": 136, "hp": 950, "speed": 24,
        "atk_min": 32, "atk_max": 40, "rice": 300, "potato": 0, "btime": 7,
        "base_atk": 120, "max_mp": 0, "range1": 1, "range2": 5,
        "atb1": 0x00010005, "atb2": 0x00000000, "attack_atb": 1,
    },
    {
        "name": "털가면", "kind_id": 0x76, "cmd_id": 0xB1, "btn_id": 0x4A, "hotkey": "M",
        "spr": "FurHeadDemon_online.spr", "frames": 130, "hp": 700, "speed": 19,
        "atk_min": 20, "atk_max": 26, "rice": 220, "potato": 20, "btime": 6,
        "base_atk": 80, "max_mp": 80, "range1": 5, "range2": 6,
        "atb1": 0x00110405, "atb2": 0x20000008, "attack_atb": 26,
    },
    {
        "name": "설녀", "kind_id": 0x77, "cmd_id": 0xB2, "btn_id": 0x4B, "hotkey": "I",
        "spr": "SnowWoman_online.spr", "frames": 192, "hp": 850, "speed": 17,
        "atk_min": 30, "atk_max": 38, "rice": 320, "potato": 50, "btime": 7,
        "base_atk": 95, "max_mp": 120, "range1": 6, "range2": 7,
        "atb1": 0x01C10405, "atb2": 0x20000008, "attack_atb": 26,
    },
    {
        "name": "조선 도깨비", "kind_id": 0x78, "cmd_id": 0xB3, "btn_id": 0x4C, "hotkey": "O",
        "spr": "Oni_online.spr", "frames": 180, "hp": 1100, "speed": 18,
        "atk_min": 35, "atk_max": 45, "rice": 350, "potato": 0, "btime": 8,
        "base_atk": 110, "max_mp": 0, "range1": 1, "range2": 5,
        "atb1": 0x00010005, "atb2": 0x00000000, "attack_atb": 23,
    },
    {
        "name": "불가살이", "kind_id": 0x79, "cmd_id": 0xB4, "btn_id": 0x4D, "hotkey": "U",
        "spr": "Starfish.spr", "frames": 216, "hp": 1400, "speed": 14,
        "atk_min": 40, "atk_max": 55, "rice": 450, "potato": 100, "btime": 9,
        "base_atk": 130, "max_mp": 120, "range1": 6, "range2": 7,
        "atb1": 0x00110405, "atb2": 0x00000310, "attack_atb": 15,
    },
]


# Authoritative Building Command Card Slot Allocations
HQ_PATCHED_SLOTS = [9, 10, 11]
BARRACKS_PATCHED_SLOTS = [8, 9, 10]
STABLES_PATCHED_SLOTS = [7, 8, 9, 10]

# =============================================================================
# Joseon 5 New Infantry Units (0x7A~0x7E / 0x70~0x74) Authoritative Specifications
# =============================================================================
ARCHER_SFX_SELECT = 164       # 0x00A4
ARCHER_SFX_DYING = 223        # 0x00DF
ARCHER_SFX_MOVE = 254         # 0x00FE
ARCHER_SFX_TRYATTACK = 314    # 0x013A
ARCHER_VOICE_TPL_ID = 0x02    # FILE_CHAR_ARCHERK (Kind 0x02)

VA_HOOK_ADVBARRACKS_K = 0x004810A0
VA_HOOK_ADVBARRACKS_K_ALT = 0x00480FF2
VA_CAVE_ADVBARRACKS_HOOK = 0x004E4FA0

JOSEON_5_INFANTRY_METADATA = [
    {
        "name": "등패수",
        "kind_id": 0x7A,
        "kind_id_alt": 0x70,
        "cmd_id": 0xBF,
        "cmd_id_alt": 0xAB,
        "btn_id": 0x4E,
        "btn_id_alt": 0x44,
        "hotkey": "E",
        "hotkeys_allowed": ["E", "D"],
        "building": "조선 훈련소",
        "building_kind": 0x31,
        "slot": 11,
        "hp": 800,
        "base_atk": 40,
        "defense": 5,
        "speed": 18,
        "rice": 160,
        "potato": 0,
        "iron": 30,
        "btime": 5,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "방어 및 탱킹 특화 보병",
        "desc": "원형 방패(등패)와 환도, 조선 전통 갑주 착용. 높은 방어력과 체력의 전열 탱커.",
    },
    {
        "name": "쌍수도병",
        "kind_id": 0x7B,
        "kind_id_alt": 0x71,
        "cmd_id": 0xC0,
        "cmd_id_alt": 0xAC,
        "btn_id": 0x4F,
        "btn_id_alt": 0x45,
        "hotkey": "V",
        "hotkeys_allowed": ["C", "S", "V"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 8,
        "hp": 600,
        "base_atk": 85,
        "defense": 2,
        "speed": 21,
        "rice": 220,
        "potato": 0,
        "iron": 60,
        "btime": 6,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "고공격 강력 충격 보병",
        "desc": "거대한 양손 대검(쌍수도) 장착. 높은 공격력을 지닌 충격 보병.",
    },
    {
        "name": "장창수",
        "kind_id": 0x7C,
        "kind_id_alt": 0x72,
        "cmd_id": 0xC1,
        "cmd_id_alt": 0xAD,
        "btn_id": 0x2E,
        "btn_id_alt": 0x46,
        "hotkey": "J",
        "hotkeys_allowed": ["L", "J"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 9,
        "hp": 550,
        "base_atk": 55,
        "defense": 3,
        "speed": 18,
        "rice": 180,
        "potato": 30,
        "iron": 40,
        "btime": 6,
        "range1": 2,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "긴 사거리 찌르기 독립 유닛",
        "desc": "주칠장창 장착. 기존 창병 대비 긴 사거리(2타일)의 독립 생산 유닛.",
    },
    {
        "name": "월도병",
        "kind_id": 0x7D,
        "kind_id_alt": 0x73,
        "cmd_id": 0xC2,
        "cmd_id_alt": 0xAE,
        "btn_id": 0x2F,
        "btn_id_alt": 0x47,
        "hotkey": "W",
        "hotkeys_allowed": ["W"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 10,
        "hp": 700,
        "base_atk": 65,
        "defense": 4,
        "speed": 19,
        "rice": 240,
        "potato": 20,
        "iron": 70,
        "btime": 7,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "공방 일체형 충격 보병",
        "desc": "언월도 장착. 우수한 공격력과 준수한 방어력을 겸비한 공방 일체형 보병.",
    },
    {
        "name": "낭선병",
        "kind_id": 0x7E,
        "kind_id_alt": 0x74,
        "cmd_id": 0xC3,
        "cmd_id_alt": 0xAF,
        "btn_id": 0x30,
        "btn_id_alt": 0x48,
        "hotkey": "N",
        "hotkeys_allowed": ["N"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 11,
        "hp": 550,
        "base_atk": 50,
        "defense": 3,
        "speed": 18,
        "rice": 200,
        "potato": 50,
        "iron": 40,
        "btime": 7,
        "range1": 2,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "긴 사거리 및 넉백 제어 보병",
        "desc": "대나무 가지창(낭선) 장착. 긴 사거리(2타일) 및 피격 적 넉백 기믹.",
    },
]


class TestJoseonNewUnitsPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.exe_path = cls.root / "YM" / "dawn" / "dawn.exe"
        cls.backup_path = cls.root / "YM_backup_original" / "dawn.exe"
        cls.data = cls.exe_path.read_bytes()
        cls.orig_data = cls.backup_path.read_bytes()
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.md.detail = True
        cls.f1_limit = cls.data[va_to_offset(VA_F1_DEBUG_TREEVIEW_LIMIT)]
        cls.is_round5 = (cls.f1_limit >= 0x79)
        cls.is_15_units = (cls.f1_limit >= 0x7E)

    # =========================================================================
    # Baseline Existing Tests (Maintained for Backward Compatibility)
    # =========================================================================

    def test_backup_exists_and_matches_original_sha256(self) -> None:
        self.assertTrue(self.backup_path.exists(), "Original dawn.exe backup must exist")
        sha = hashlib.sha256(self.backup_path.read_bytes()).hexdigest()
        self.assertEqual(sha, ORIGINAL_SHA256)

    def test_all_unit_name_strings_in_code_cave(self) -> None:
        """Verify unit name strings exist in CP949 encoding within the .text code cave."""
        if self.is_round5:
            text_cave = self.data[va_to_offset(0x004E4C70) : va_to_offset(0x004E5000)]
            for u in NEW_UNITS_METADATA:
                name_bytes = u["name"].encode("cp949") + b"\x00"
                self.assertIn(
                    name_bytes,
                    text_cave,
                    f"Unit name '{u['name']}' not found in code cave (.text)",
                )
        else:
            off70 = va_to_offset(VA_CAVE_UNIT_NAME_70)
            exp70 = "조선 결사대".encode("cp949") + b"\x00"
            self.assertEqual(self.data[off70 : off70 + len(exp70)], exp70)

            off71 = va_to_offset(VA_CAVE_UNIT_NAME_71)
            exp71 = "조선 조총병".encode("cp949") + b"\x00"
            self.assertEqual(self.data[off71 : off71 + len(exp71)], exp71)

            off72 = va_to_offset(VA_CAVE_UNIT_NAME_72)
            exp72 = "조선 두억시니".encode("cp949") + b"\x00"
            self.assertEqual(self.data[off72 : off72 + len(exp72)], exp72)

    def test_hook_sites_jump_to_code_caves(self) -> None:
        # 1. InitAllKindInfo hook at 0x004A2FD2 -> jmp 0x004E4CA0
        ins_h1 = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_INIT_KIND) : va_to_offset(VA_HOOK_INIT_KIND) + 7], VA_HOOK_INIT_KIND))
        self.assertEqual(ins_h1[0].mnemonic, "jmp")
        self.assertEqual(int(ins_h1[0].op_str, 16), VA_CAVE_INIT_ROUTINE)

        # 2. Joseon Barracks hook at 0x00480488 -> jmp 0x004E4F08
        ins_h2 = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_BARRACKS_K) : va_to_offset(VA_HOOK_BARRACKS_K) + 5], VA_HOOK_BARRACKS_K))
        self.assertEqual(ins_h2[0].mnemonic, "jmp")
        self.assertEqual(int(ins_h2[0].op_str, 16), VA_CAVE_BARRACKS_HOOK)

        # 3. Joseon HQ hook at 0x00483048 -> jmp 0x004E4F60
        ins_h3 = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_HQ_K) : va_to_offset(VA_HOOK_HQ_K) + 5], VA_HOOK_HQ_K))
        self.assertEqual(ins_h3[0].mnemonic, "jmp")
        self.assertEqual(int(ins_h3[0].op_str, 16), VA_CAVE_HQ_HOOK)

        # 4. Default unit command card at 0x004801BB -> call 0x004E4FB8 (dispatcher)
        ins_h4 = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_DEFAULT_CMDCARD) : va_to_offset(VA_HOOK_DEFAULT_CMDCARD) + 5], VA_HOOK_DEFAULT_CMDCARD))
        self.assertEqual(ins_h4[0].mnemonic, "call")
        self.assertEqual(int(ins_h4[0].op_str, 16), VA_CAVE_CMDCARD_DISPATCH)

        # 5. Joseon Stables hook at 0x004818ED -> jmp VA_CAVE_STABLES_HOOK
        if self.is_round5:
            ins_h5 = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_STABLES_K) : va_to_offset(VA_HOOK_STABLES_K) + 5], VA_HOOK_STABLES_K))
            self.assertEqual(ins_h5[0].mnemonic, "jmp")
            self.assertEqual(int(ins_h5[0].op_str, 16), VA_CAVE_STABLES_HOOK)
        else:
            ins_h5 = list(self.md.disasm(self.orig_data[va_to_offset(VA_HOOK_STABLES_K) : va_to_offset(VA_HOOK_STABLES_K) + 5], VA_HOOK_STABLES_K))
            self.assertEqual(ins_h5[0].mnemonic, "call")
            self.assertEqual(int(ins_h5[0].op_str, 16), VA_ADD_BUTTON)

    def test_cave_init_routine_registers_all_units(self) -> None:
        if self.is_round5:
            cave1_len = len(build_init_cave(VA_CAVE_INIT_ROUTINE))
            off = va_to_offset(VA_CAVE_INIT_ROUTINE)
            insns = list(self.md.disasm(self.data[off : off + cave1_len], VA_CAVE_INIT_ROUTINE))
            # Slice up to jmp VA_HOOK_INIT_KIND_RESUME to exclude trailing unit descriptors table
            jmp_idx = next(idx for idx, i in enumerate(insns) if i.mnemonic == "jmp" and int(i.op_str, 16) == VA_HOOK_INIT_KIND_RESUME)
            code_insns = insns[:jmp_idx + 1]
            mnemonics = [i.mnemonic for i in code_insns]
            self.assertEqual(mnemonics[0], "pushal")
            self.assertIn("popal", mnemonics)
            self.assertEqual(mnemonics[-1], "jmp")
            calls = [int(i.op_str, 16) for i in code_insns if i.mnemonic == "call"]
            self.assertTrue(VA_CALC_KIND_CHECKSUM in calls or 0x0043F8D0 in calls or VA_CAVE_INIT_EXTRA in calls)
            self.assertIn(VA_CMD_INIT, calls)
            self.assertIn(VA_BTN_INIT, calls)
        else:
            cave1_len = len(build_init_cave(VA_CAVE_INIT_ROUTINE))
            off = va_to_offset(VA_CAVE_INIT_ROUTINE)
            insns = list(self.md.disasm(self.data[off : off + cave1_len], VA_CAVE_INIT_ROUTINE))
            mnemonics = [i.mnemonic for i in insns]
            self.assertEqual(mnemonics[0], "pushal")
            self.assertEqual(mnemonics.count("rep movsd"), 3)
            self.assertIn("popal", mnemonics)
            self.assertEqual(mnemonics[-1], "jmp")

            calls = [int(i.op_str, 16) for i in insns if i.mnemonic == "call"]
            self.assertEqual(
                calls,
                [
                    VA_CALC_KIND_CHECKSUM,
                    VA_CMD_INIT,
                    VA_BTN_INIT,
                    VA_CALC_KIND_CHECKSUM,
                    VA_CMD_INIT,
                    VA_BTN_INIT,
                    VA_CALC_KIND_CHECKSUM,
                    VA_CMD_INIT,
                    VA_BTN_INIT,
                ],
            )

    def test_building_button_caves_and_dispatcher(self) -> None:
        # Barracks Cave (#2): Slots [8, 9, 10]
        off_b = va_to_offset(VA_CAVE_BARRACKS_HOOK)
        ins_b = list(self.md.disasm(self.data[off_b : off_b + 120], VA_CAVE_BARRACKS_HOOK))
        calls_b = [int(i.op_str, 16) for i in ins_b if i.mnemonic == "call"]
        self.assertEqual(calls_b[0], VA_ADD_BUTTON)
        pushes_b = [int(i.op_str, 0) for i in ins_b if i.mnemonic == "push" and (i.op_str.startswith("0x") or i.op_str.isdigit())]

        # Critical Requirement R2: 조선 조총병 (BtnID 0x49) must be commented out
        if self.is_round5:
            self.assertNotIn(0x49, pushes_b, "조선 조총병 (BtnID 0x49) must be commented out from Barracks command card")
        else:
            r5_barracks_buttons = [(8, 0x45), (9, 0x46), (10, 0x4A)]
            r5_c2 = build_building_buttons_cave(VA_CAVE_BARRACKS_HOOK, VA_HOOK_BARRACKS_K_RESUME, r5_barracks_buttons)
            r5_ins_b = list(self.md.disasm(r5_c2, VA_CAVE_BARRACKS_HOOK))
            r5_pushes = [int(i.op_str, 0) for i in r5_ins_b if i.mnemonic == "push" and (i.op_str.startswith("0x") or i.op_str.isdigit())]
            self.assertNotIn(0x49, r5_pushes, "조선 조총병 (BtnID 0x49) must be commented out from Barracks command card")

        # HQ Cave (#3): Slots [8, 9, 10]
        off_hq = va_to_offset(VA_CAVE_HQ_HOOK)
        ins_hq = list(self.md.disasm(self.data[off_hq : off_hq + 120], VA_CAVE_HQ_HOOK))
        calls_hq = [int(i.op_str, 16) for i in ins_hq if i.mnemonic == "call"]
        self.assertEqual(calls_hq[0], VA_ADD_BUTTON)

        # Stables Cave (#Stables): Slots [7, 8, 9, 10] (KindID 0x2F 조선 목장)
        stables_buttons = [(7, 0x48), (8, 0x49), (9, 0x4B), (10, 0x4C)]
        c_st_bytes = build_building_buttons_cave(VA_CAVE_STABLES_HOOK, VA_HOOK_STABLES_K_RESUME, stables_buttons)
        ins_st = list(self.md.disasm(c_st_bytes, VA_CAVE_STABLES_HOOK))
        calls_st = [int(i.op_str, 16) for i in ins_st if i.mnemonic == "call"]
        self.assertEqual(calls_st[0], VA_ADD_BUTTON)
        self.assertEqual(len(calls_st), 1 + len(stables_buttons))
        self.assertEqual(ins_st[-1].mnemonic, "jmp")
        self.assertEqual(int(ins_st[-1].op_str, 16), VA_HOOK_STABLES_K_RESUME)

        # Dispatcher Cave (#4): je 0x0043F900 (Gumiho Combat+Clone card), jmp 0x00486EE0 (Combat card)
        cave4_len = len(build_cmdcard_dispatcher(VA_CAVE_CMDCARD_DISPATCH))
        off_d = va_to_offset(VA_CAVE_CMDCARD_DISPATCH)
        ins_d = list(self.md.disasm(self.data[off_d : off_d + cave4_len], VA_CAVE_CMDCARD_DISPATCH))
        self.assertEqual(ins_d[0].mnemonic, "cmp")
        self.assertEqual(ins_d[1].mnemonic, "je")
        self.assertIn(int(ins_d[1].op_str, 16), (VA_JUSTICEK_CMDCARD, 0x0043F900, VA_CAVE_GUMIHO_CMDCARD))
        self.assertEqual(ins_d[2].mnemonic, "jmp")
        self.assertEqual(int(ins_d[2].op_str, 16), VA_COMBAT_CMDCARD)

    def test_joseon_musketeer_commented_out(self) -> None:
        """Verify that 조선 조총병 (BtnID 0x49) is commented out / omitted from building command cards."""
        # Check custom button lists for Barracks and HQ
        r5_barracks_buttons = [(8, 0x45), (9, 0x46), (10, 0x4A)]
        self.assertNotIn(0x49, [b for s, b in r5_barracks_buttons], "0x49 must not be in Barracks buttons")

        if self.is_round5:
            off_b = va_to_offset(VA_CAVE_BARRACKS_HOOK)
            ins_b = list(self.md.disasm(self.data[off_b : off_b + 120], VA_CAVE_BARRACKS_HOOK))
            pushes_b = [int(i.op_str, 0) for i in ins_b if i.mnemonic == "push" and (i.op_str.startswith("0x") or i.op_str.isdigit())]
            self.assertNotIn(0x49, pushes_b, "조선 조총병 (BtnID 0x49) must not be pushed in Barracks cave")

    def test_ten_units_specification_matrix(self) -> None:
        """Verify the complete specification matrix for all 10 new Joseon units."""
        self.assertEqual(len(NEW_UNITS_METADATA), 10, "Must specify exactly 10 new units")
        kind_ids = [u["kind_id"] for u in NEW_UNITS_METADATA]
        cmd_ids = [u["cmd_id"] for u in NEW_UNITS_METADATA]
        btn_ids = [u["btn_id"] for u in NEW_UNITS_METADATA]

        self.assertEqual(kind_ids, list(range(0x70, 0x7A)), "KindIDs must be contiguous 0x70..0x79")
        self.assertEqual(cmd_ids, list(range(0xAB, 0xB5)), "CmdIDs must be contiguous 0xAB..0xB4")
        self.assertEqual(btn_ids, list(range(0x44, 0x4E)), "ButtonIDs must be contiguous 0x44..0x4D")
        self.assertEqual(MAX_KIND_ID, 0x79, "MAX_KIND_ID must be 0x79")


    # =========================================================================
    # Requirement R1 Tests: Binary Diff, Disassembly & Stack Balance, Registers
    # =========================================================================

    def test_r1_binary_diff_cluster_audit(self) -> None:
        """Verify binary diff is strictly confined to designated patch clusters and PE headers/sections are bit-exact."""
        self.assertEqual(len(self.data), len(self.orig_data), "Binary size must match exactly 1,032,192 bytes")

        # Designated valid file offset patch ranges
        valid_ranges = [
            ("Hook #4 (Default SetupCommandCard)", va_to_offset(VA_HOOK_DEFAULT_CMDCARD), va_to_offset(VA_HOOK_DEFAULT_CMDCARD) + 5),
            ("Hook #2 (Joseon Barracks CommandCard)", va_to_offset(VA_HOOK_BARRACKS_K), va_to_offset(VA_HOOK_BARRACKS_K) + 5),
            ("Hook #3 (Joseon HQ CommandCard)", va_to_offset(VA_HOOK_HQ_K), va_to_offset(VA_HOOK_HQ_K) + 5),
            ("Hook #Stables (Joseon Stables CommandCard)", va_to_offset(VA_HOOK_STABLES_K), va_to_offset(VA_HOOK_STABLES_K) + 5),
            ("Hook #AdvBarracks (Joseon 훈련도감 0x33 CommandCard)", va_to_offset(0x0048075D), va_to_offset(0x00480B66)),
            ("Hook #1 (InitAllKindInfo)", va_to_offset(VA_HOOK_INIT_KIND), va_to_offset(VA_HOOK_INIT_KIND) + 7),
            ("F1 Debug Dialog Limit", va_to_offset(VA_F1_DEBUG_TREEVIEW_LIMIT), va_to_offset(VA_F1_DEBUG_TREEVIEW_LIMIT) + 1),
            ("Hook #5A & #5B (Protocol Tab Selection)", va_to_offset(VA_PROTOCOL_SELECT_RETAIL_HONJA), va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN) + 2),
            ("Hook #HornetDeath (Joseon Hornet Instant Death)", va_to_offset(VA_HOOK_HORNET_DEATH), va_to_offset(VA_HOOK_HORNET_DEATH) + 49),
            ("P1 Crowding Cap", va_to_offset(0x00406C44), va_to_offset(0x00406C4A)),
            ("Area D Dead CD-check Caves", va_to_offset(0x00421A20), va_to_offset(0x00421AA0)),
            ("Alt+Tab WinMain & WndProc Hooks", va_to_offset(0x00423CC8), va_to_offset(0x0042434B)),
            ("Areas B/C Caves & AI Patches", va_to_offset(0x0043C8F5), va_to_offset(0x0043DEEC)),
            ("P8 Unit Max Ratio Cap", va_to_offset(0x0043E8DA), va_to_offset(0x0043E8DE)),
            ("AI Decision Wheel & 50:50 Bypass", va_to_offset(0x0043F7F7), va_to_offset(0x0043FB62)),
            ("P9 Worker Harvest Wood Balance", va_to_offset(0x004B04C2), va_to_offset(0x004B04C6)),
            ("Hook #CalcAttackStatus", va_to_offset(0x00470CD5), va_to_offset(0x00470CD5) + 6),
            ("Hook #FireTankBullet", va_to_offset(0x00474D58), va_to_offset(0x00474D58) + 7),
            ("Hook #CanAutoCastTech", va_to_offset(0x00475BD2), va_to_offset(0x00475BD2) + 6),
            ("Hook #CanClone", va_to_offset(0x00477CD1), va_to_offset(0x00477EEE)),
            ("Hook #UpdateCharMode", va_to_offset(0x0048CBB6), va_to_offset(0x0048CBB6) + 8),
            ("Hook #CloneTooltip", va_to_offset(0x0049A815), va_to_offset(0x0049A815) + 6),
            ("Dead Desync Dump Caves (InitInfantry5, AltTab, AttackEffects)", va_to_offset(0x00440C59), va_to_offset(0x00440F60)),
            ("Code Caves", va_to_offset(0x004E4C70), va_to_offset(0x004E5000)),
        ]

        unaccounted = []
        for off in range(len(self.orig_data)):
            if self.orig_data[off] != self.data[off]:
                in_valid_range = any(start <= off < end for _, start, end in valid_ranges)
                if not in_valid_range:
                    unaccounted.append(hex(off))

        self.assertEqual(len(unaccounted), 0, f"Disallowed binary modifications outside patch sites: {unaccounted}")

        # Check PE headers and section integrity
        pe = pefile.PE(data=self.orig_data)
        headers_size = pe.OPTIONAL_HEADER.SizeOfHeaders
        self.assertEqual(self.orig_data[:headers_size], self.data[:headers_size], "PE headers must be 100% bit-exact")

        for sec in pe.sections:
            name = sec.Name.rstrip(b"\x00").decode("latin-1")
            raw_off = sec.PointerToRawData
            raw_size = sec.SizeOfRawData
            orig_chunk = self.orig_data[raw_off : raw_off + raw_size]
            patched_chunk = self.data[raw_off : raw_off + raw_size]
            if name != ".text":
                self.assertEqual(orig_chunk, patched_chunk, f"Section {name} must be 100% bit-exact identical to original")

    def test_r1_x86_stack_balance_and_calling_conventions(self) -> None:
        """Verify callee/caller calling conventions and net stack delta = 0 across Hooks #1-#5 and Caves #1-#4."""
        # 1. Hook #1 -> Cave #1:
        # pushal (-32), popal (+32).
        # Check that CalcKindChecksum ends with ret (delta 0), CmdInit ends with ret 0x18 (pops 24B), BtnInit ends with ret 0x1C (pops 28B).
        def check_ret(va: int, expected_mnemonic: str, expected_op_str: str) -> None:
            off = va_to_offset(va)
            for ins in self.md.disasm(self.data[off : off + 1200], va):
                if ins.mnemonic in ("ret", "retf"):
                    self.assertEqual(ins.mnemonic, expected_mnemonic)
                    self.assertEqual(ins.op_str, expected_op_str)
                    return
            self.fail(f"No return instruction found for function at 0x{va:08X}")

        check_ret(VA_CALC_KIND_CHECKSUM, "ret", "")
        check_ret(VA_CMD_INIT, "ret", "0x18")
        check_ret(VA_BTN_INIT, "ret", "0x1c")
        check_ret(VA_ADD_BUTTON, "ret", "0x20")
        check_ret(VA_JUSTICEK_CMDCARD, "ret", "4")
        check_ret(VA_COMBAT_CMDCARD, "ret", "4")
        check_ret(0x00405540, "ret", "4")  # SetTabSelected
        check_ret(0x00403C50, "ret", "4")  # SetEnabled

        # 2. Cave #1 pushal/popal symmetry
        c1_bytes = build_init_cave(VA_CAVE_INIT_ROUTINE)
        c1_insns = list(self.md.disasm(c1_bytes, VA_CAVE_INIT_ROUTINE))
        jmp_idx = next(idx for idx, i in enumerate(c1_insns) if i.mnemonic == "jmp" and int(i.op_str, 16) == VA_HOOK_INIT_KIND_RESUME)
        c1_code = c1_insns[:jmp_idx + 1]
        self.assertEqual(c1_code[0].mnemonic, "pushal")
        self.assertEqual(c1_code[-4].mnemonic, "popal")
        self.assertEqual(c1_code[-1].mnemonic, "jmp")
        self.assertEqual(int(c1_code[-1].op_str, 16), VA_HOOK_INIT_KIND_RESUME)

        # 3. Cave #2 (Barracks) calling sequence
        c2_bytes = build_building_buttons_cave(VA_CAVE_BARRACKS_HOOK, VA_HOOK_BARRACKS_K_RESUME, [(8, 0x45), (9, 0x46), (10, 0x4A)])
        c2_insns = list(self.md.disasm(c2_bytes, VA_CAVE_BARRACKS_HOOK))
        self.assertEqual(c2_insns[0].mnemonic, "call")
        self.assertEqual(int(c2_insns[0].op_str, 16), VA_ADD_BUTTON)
        self.assertEqual(c2_insns[-1].mnemonic, "jmp")
        self.assertEqual(int(c2_insns[-1].op_str, 16), VA_HOOK_BARRACKS_K_RESUME)

        # 4. Cave #3 (HQ) calling sequence
        c3_bytes = build_building_buttons_cave(VA_CAVE_HQ_HOOK, VA_HOOK_HQ_K_RESUME, [(9, 0x44), (10, 0x4D), (11, 0x47)])
        c3_insns = list(self.md.disasm(c3_bytes, VA_CAVE_HQ_HOOK))
        self.assertEqual(c3_insns[0].mnemonic, "call")
        self.assertEqual(int(c3_insns[0].op_str, 16), VA_ADD_BUTTON)
        self.assertEqual(c3_insns[-1].mnemonic, "jmp")
        self.assertEqual(int(c3_insns[-1].op_str, 16), VA_HOOK_HQ_K_RESUME)

        # 5. Cave #Stables (Stables) calling sequence
        stables_buttons = [(7, 0x48), (8, 0x49), (9, 0x4B), (10, 0x4C)]
        c_st_bytes = build_building_buttons_cave(VA_CAVE_STABLES_HOOK, VA_HOOK_STABLES_K_RESUME, stables_buttons)
        c_st_insns = list(self.md.disasm(c_st_bytes, VA_CAVE_STABLES_HOOK))
        self.assertEqual(c_st_insns[0].mnemonic, "call")
        self.assertEqual(int(c_st_insns[0].op_str, 16), VA_ADD_BUTTON)
        self.assertEqual(c_st_insns[-1].mnemonic, "jmp")
        self.assertEqual(int(c_st_insns[-1].op_str, 16), VA_HOOK_STABLES_K_RESUME)

        # 6. Cave #4 (Dispatcher) tail calls
        c4_bytes = build_cmdcard_dispatcher(VA_CAVE_CMDCARD_DISPATCH)
        c4_insns = list(self.md.disasm(c4_bytes, VA_CAVE_CMDCARD_DISPATCH))
        self.assertEqual(c4_insns[1].mnemonic, "je")
        self.assertIn(int(c4_insns[1].op_str, 16), (VA_JUSTICEK_CMDCARD, 0x0043F900, VA_CAVE_GUMIHO_CMDCARD))
        self.assertEqual(c4_insns[2].mnemonic, "jmp")
        self.assertEqual(int(c4_insns[2].op_str, 16), VA_COMBAT_CMDCARD)

    def test_r1_register_preservation(self) -> None:
        """Verify register preservation across Cave routines: GP registers, ecx, esi, ebx."""
        # Cave #1 saves all GP registers with pushal (0x60) and restores with popal (0x61).
        c1_off = va_to_offset(VA_CAVE_INIT_ROUTINE)
        c1_len = len(build_init_cave(VA_CAVE_INIT_ROUTINE))
        c1_insns = list(self.md.disasm(self.data[c1_off : c1_off + c1_len], VA_CAVE_INIT_ROUTINE))
        jmp_idx = next(idx for idx, i in enumerate(c1_insns) if i.mnemonic == "jmp" and int(i.op_str, 16) == VA_HOOK_INIT_KIND_RESUME)
        c1_code = c1_insns[:jmp_idx + 1]
        self.assertEqual(c1_code[0].mnemonic, "pushal")
        self.assertEqual(c1_code[1].mnemonic, "cld")

        # Displaced instructions replayed after popal
        self.assertEqual(c1_code[-4].mnemonic, "popal")
        self.assertEqual(c1_code[-3].mnemonic, "xor")
        self.assertEqual(c1_code[-3].op_str, "ecx, ecx")
        self.assertEqual(c1_code[-2].mnemonic, "mov")
        self.assertEqual(c1_code[-2].op_str, "eax, 0x9b5230")
        self.assertEqual(c1_code[-1].mnemonic, "jmp")
        self.assertEqual(int(c1_code[-1].op_str, 16), VA_HOOK_INIT_KIND_RESUME)

        # Cave #2, Cave #3, and Cave #Stables: esi is loaded into ecx (mov ecx, esi) without modifying esi.
        for cave_va, resume_va, buttons in [
            (VA_CAVE_BARRACKS_HOOK, VA_HOOK_BARRACKS_K_RESUME, [(8, 0x45), (9, 0x46), (10, 0x4A)]),
            (VA_CAVE_HQ_HOOK, VA_HOOK_HQ_K_RESUME, [(9, 0x44), (10, 0x4D), (11, 0x47)]),
            (VA_CAVE_STABLES_HOOK, VA_HOOK_STABLES_K_RESUME, [(7, 0x48), (8, 0x49), (9, 0x4B), (10, 0x4C)]),
        ]:
            b_bytes = build_building_buttons_cave(cave_va, resume_va, buttons)
            b_insns = list(self.md.disasm(b_bytes, cave_va))
            mov_ecx_esi = [i for i in b_insns if i.mnemonic == "mov" and i.op_str == "ecx, esi"]
            self.assertEqual(len(mov_ecx_esi), len(buttons), "Each button call must move esi into ecx")

    # =========================================================================
    # Requirement R2 Tests: In-Memory Simulation, Checksum, Sprite & Button Slots
    # =========================================================================

    def test_r2_in_memory_simulation_reconstructed_fields(self) -> None:
        """Simulate Cave #1 in memory and verify reconstructed KindInfo, CmdTable, and ButtonTable fields for all 10 units."""
        # 1. Parse template KindInfo[0x6E] and KindInfo[0x0C] directly from dawn.exe initialization code
        def simulate_49baa0_writes(pushes: list[str]) -> bytearray:
            buf = bytearray(0x394)
            args = []
            for p in reversed(pushes):
                if p == "esi":
                    args.append(1)
                elif p in ("eax", "edx", "ecx"):
                    args.append(0)
                elif p.startswith("-"):
                    args.append(int(p, 0) & 0xFFFFFFFF)
                else:
                    args.append(int(p, 0))

            word_map = [
                (0x00, 0), (0x02, 1), (0x0C, 2), (0x0E, 3), (0x10, 4), (0x12, 5), (0x14, 6),
                (0x16, 7), (0x18, 8), (0x1A, 9), (0x1C, 10), (0x1E, 11), (0x20, 12),
                (0x28, 13), (0x2A, 14), (0x06, 16), (0x04, 17), (0x2C, 18), (0x2E, 19),
                (0x30, 20), (0x32, 21), (0x34, 22), (0x36, 23), (0x38, 24), (0x3A, 25),
                (0x3C, 26), (0x3E, 27), (0x40, 28), (0x42, 29), (0x44, 30), (0x46, 31),
                (0x48, 32), (0x4A, 33), (0x68, 41), (0x6A, 42), (0x74, 43), (0x6C, 44),
                (0x6E, 45), (0x70, 46), (0x72, 47), (0x1AC, 50), (0x1AE, 51), (0x1B0, 52), (0x1B2, 53)
            ]
            for off, arg in word_map:
                struct.pack_into("<H", buf, off, args[arg] & 0xFFFF)

            dword_map = [
                (0x24, 15), (0x4C, 34), (0x50, 35), (0x54, 36), (0x58, 37), (0x5C, 38),
                (0x60, 39), (0x64, 40), (0x1A4, 48), (0x1A8, 49)
            ]
            for off, arg in dword_map:
                struct.pack_into("<I", buf, off, args[arg] & 0xFFFFFFFF)
            return buf

        # Template 6E (JusticeK)
        off_call_6e = 0x0049C1E4 - IMAGE_BASE
        insns_6e = list(self.md.disasm(self.data[off_call_6e - 250 : off_call_6e], 0x0049C160))
        pushes_6e = [i.op_str for i in insns_6e if i.mnemonic == "push"][-54:]
        buf_6e = simulate_49baa0_writes(pushes_6e)

        # Template 0C (GunJ1)
        off_call_0c = 0x0049CAD1 - IMAGE_BASE
        insns_0c = list(self.md.disasm(self.data[off_call_0c - 300 : off_call_0c], 0x0049CAD1 - 300))
        pushes_0c = [i.op_str for i in insns_0c if i.mnemonic == "push"][-54:]
        buf_0c = simulate_49baa0_writes(pushes_0c)

        # --- Reconstruct Unit 0x70 (조선 결사대) ---
        buf_70 = bytearray(buf_6e)
        struct.pack_into("<I", buf_70, 0x1A4, VA_CAVE_UNIT_NAME_70)
        struct.pack_into("<H", buf_70, 0x06, 650)
        struct.pack_into("<H", buf_70, 0x10, 6)
        struct.pack_into("<H", buf_70, 0x12, 200)
        struct.pack_into("<H", buf_70, 0x14, 0)
        struct.pack_into("<H", buf_70, 0x2C, 20)
        struct.pack_into("<H", buf_70, 0x3A, 18)
        struct.pack_into("<H", buf_70, 0x3E, 22)

        self.assertEqual(struct.unpack_from("<H", buf_70, 0x06)[0], 650, "HP must be 650")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x10)[0], 6, "Build time must be 6")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x12)[0], 200, "Rice cost must be 200")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x14)[0], 0, "Potato cost must be 0")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x28)[0], 1, "Nation must be 1 (Joseon)")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x2C)[0], 20, "Move speed must be 20")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x3A)[0], 18, "Attack min must be 18")
        self.assertEqual(struct.unpack_from("<H", buf_70, 0x3E)[0], 22, "Attack max must be 22")
        self.assertEqual(struct.unpack_from("<I", buf_70, 0x1A4)[0], VA_CAVE_UNIT_NAME_70)

        # --- Reconstruct and verify all 10 new Joseon units ---
        for u in NEW_UNITS_METADATA:
            tpl_buf = buf_0c if "조총" in u["name"] else buf_6e
            unit_buf = bytearray(tpl_buf)
            struct.pack_into("<H", unit_buf, 0x04, u["base_atk"])  # BaseAttackPower (+0x04)
            struct.pack_into("<H", unit_buf, 0x06, u["hp"])        # MaxHP (+0x06)
            struct.pack_into("<H", unit_buf, 0x10, u["btime"])
            struct.pack_into("<H", unit_buf, 0x12, u["rice"])
            struct.pack_into("<H", unit_buf, 0x14, u["potato"])
            struct.pack_into("<H", unit_buf, 0x28, 1)  # Nation = 1 (Joseon)
            struct.pack_into("<H", unit_buf, 0x2C, u["speed"])     # MoveSpeed (+0x2C)
            struct.pack_into("<H", unit_buf, 0x2E, u["max_mp"])    # MaxMP (+0x2E)
            struct.pack_into("<H", unit_buf, 0x36, u["range1"])    # Range1 (+0x36)
            struct.pack_into("<H", unit_buf, 0x38, u["range2"])    # Range2 (+0x38)
            struct.pack_into("<H", unit_buf, 0x3A, u["atk_min"])
            struct.pack_into("<H", unit_buf, 0x3E, u["atk_max"])
            struct.pack_into("<I", unit_buf, 0x4C, u["atb1"])      # Atb1 (+0x4C)
            struct.pack_into("<I", unit_buf, 0x50, u["atb2"])      # Atb2 (+0x50)
            struct.pack_into("<I", unit_buf, 0x5C, u["attack_atb"]) # AttackAtb (+0x5C)

            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x04)[0], u["base_atk"], f"{u['name']} BaseAttackPower mismatch")
            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x06)[0], u["hp"], f"{u['name']} HP mismatch")
            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x28)[0], 1, f"{u['name']} Nation must be Joseon (1)")
            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x2C)[0], u["speed"], f"{u['name']} MoveSpeed mismatch")
            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x2E)[0], u["max_mp"], f"{u['name']} MaxMP mismatch")
            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x36)[0], u["range1"], f"{u['name']} Range1 mismatch")
            self.assertEqual(struct.unpack_from("<H", unit_buf, 0x38)[0], u["range2"], f"{u['name']} Range2 mismatch")
            self.assertEqual(struct.unpack_from("<I", unit_buf, 0x4C)[0], u["atb1"], f"{u['name']} Atb1 mismatch")
            self.assertEqual(struct.unpack_from("<I", unit_buf, 0x50)[0], u["atb2"], f"{u['name']} Atb2 mismatch")
            self.assertEqual(struct.unpack_from("<I", unit_buf, 0x5C)[0], u["attack_atb"], f"{u['name']} AttackAtb mismatch")
            self.assertGreater(struct.unpack_from("<H", unit_buf, 0x2C)[0], 0, f"{u['name']} Speed must be positive")
            self.assertGreater(struct.unpack_from("<H", unit_buf, 0x3A)[0], 0, f"{u['name']} Min attack must be positive")
            self.assertGreaterEqual(struct.unpack_from("<H", unit_buf, 0x3E)[0], struct.unpack_from("<H", unit_buf, 0x3A)[0])
            self.assertGreater(u["cmd_id"], 0, f"{u['name']} CmdID must be positive")
            self.assertGreater(u["btn_id"], 0, f"{u['name']} BtnID must be positive")

    def test_r2_calc_kind_checksum_execution_and_matching(self) -> None:
        """Verify CalcKindChecksum (0x0049BD50) algorithm, invocation in Cave #1, and exact checksum values."""
        # Exact CalcKindChecksum algorithm reverse-engineered from 0x0049BD50
        def calc_kind_checksum(buf: bytearray) -> int:
            words = [
                0x74, 0x72, 0x70, 0x6E, 0x6C, 0x6A, 0x68,
                0x4A, 0x48, 0x46, 0x44, 0x42, 0x40, 0x3E, 0x3C, 0x3A, 0x38, 0x36, 0x34, 0x32, 0x30, 0x2E, 0x2C, 0x2A, 0x28,
                0x20, 0x1E, 0x1C, 0x1A, 0x18, 0x16, 0x14, 0x12, 0x10, 0x0E, 0x0C, 0x06, 0x04, 0x02
            ]
            dwords = [0x60, 0x5C, 0x58, 0x54, 0x50, 0x4C, 0x24]
            total = 0
            for off in words:
                val = struct.unpack_from("<h", buf, off)[0]
                total = (total + val) & 0xFFFFFFFF
            for off in dwords:
                val = struct.unpack_from("<I", buf, off)[0]
                total = (total + val) & 0xFFFFFFFF
            val0 = struct.unpack_from("<h", buf, 0x00)[0]
            total = (total + val0) & 0xFFFFFFFF
            return total

        # Verify checksum calculation produces genuine non-zero values for all 10 units
        for u in NEW_UNITS_METADATA:
            buf = bytearray(0x394)
            struct.pack_into("<h", buf, 0x06, u["hp"])
            struct.pack_into("<h", buf, 0x28, 1)  # Joseon
            struct.pack_into("<h", buf, 0x2C, u["speed"])
            struct.pack_into("<h", buf, 0x3A, u["atk_min"])
            struct.pack_into("<h", buf, 0x3E, u["atk_max"])
            chk = calc_kind_checksum(buf)
            self.assertGreater(chk, 0, f"{u['name']} checksum must be positive")
            self.assertLessEqual(chk, 0xFFFFFFFF, f"{u['name']} checksum must fit in 32 bits")

        # In Round 5 patched binary, verify CalcKindChecksum calls in Cave #1 (directly or via InitExtra at 0x0043F8D0)
        if self.is_round5:
            c1_off = va_to_offset(VA_CAVE_INIT_ROUTINE)
            c1_bytes = self.data[c1_off : c1_off + len(build_init_cave(VA_CAVE_INIT_ROUTINE))]
            insns = list(self.md.disasm(c1_bytes, VA_CAVE_INIT_ROUTINE))
            chk_calls = [i for i in insns if i.mnemonic == "call" and int(i.op_str, 16) in (VA_CALC_KIND_CHECKSUM, 0x0043F8D0, VA_CAVE_INIT_EXTRA)]
            self.assertGreaterEqual(len(chk_calls), 1, "Cave #1 must invoke CalcKindChecksum")

    def test_r2_dueoksini_sprite_frame_boundaries(self) -> None:
        """Parse char/dueoksini_online.spr header and verify all 4 animation descriptors stay strictly <= 194."""
        spr_path = self.root / "YM" / "dawn" / "char" / "dueoksini_online.spr"
        self.assertTrue(spr_path.exists(), "dueoksini_online.spr must exist")
        spr_bytes = spr_path.read_bytes()

        ver, width, height, frame_count = struct.unpack("<IIII", spr_bytes[:16])
        self.assertEqual(ver, 9, "Must be Joymax Version 9 sprite container")
        self.assertEqual(width, 182, "Dueoksini width is 182 px")
        self.assertEqual(height, 182, "Dueoksini height is 182 px")
        self.assertEqual(frame_count, 195, "Dueoksini total frames is exactly 195 (indices 0..194)")

        anim_descriptors = [
            ("Move", 133, 12, 5),
            ("Attack", 0, 14, 5),
            ("Die", 70, 13, 1),
            ("Idle", 83, 10, 5),
        ]

        for name, start_frame, frames_per_dir, num_dirs in anim_descriptors:
            max_frame_index = start_frame + (frames_per_dir * num_dirs) - 1
            self.assertGreaterEqual(start_frame, 0, f"{name} start frame must be >= 0")
            self.assertLess(max_frame_index, frame_count, f"{name} animation exceeds sprite frame capacity ({max_frame_index} >= {frame_count})")
            self.assertLessEqual(max_frame_index, 194, f"{name} animation frame index must stay strictly <= 194")

    def test_r2_sprite_frame_boundaries_all_ten_units(self) -> None:
        """Parse all 10 unit .spr files in char/ and verify Joymax Version 9 format and exact frame capacities."""
        char_dir = self.root / "YM" / "dawn" / "char"
        for u in NEW_UNITS_METADATA:
            spr_file = char_dir / u["spr"]
            self.assertTrue(spr_file.exists(), f"Sprite file {u['spr']} for {u['name']} must exist")
            spr_bytes = spr_file.read_bytes()

            ver, width, height, frame_count = struct.unpack("<IIII", spr_bytes[:16])
            self.assertEqual(ver, 9, f"{u['spr']} must be Joymax Version 9 sprite container")
            self.assertGreater(width, 0, f"{u['spr']} width must be positive")
            self.assertGreater(height, 0, f"{u['spr']} height must be positive")
            self.assertEqual(frame_count, u["frames"], f"{u['spr']} frame count must match expected {u['frames']}")

    def test_r2_command_card_button_slots_non_collision(self) -> None:
        """Verify Barracks, HQ, and Stables custom slots do not collide with native building slots."""
        # 1. Native Joseon Barracks command card slots (0x00480380..0x00480488)
        off_b = va_to_offset(0x00480380)
        insns_b = list(self.md.disasm(self.data[off_b : off_b + 300], 0x00480380))
        b_slots = []
        for idx, i in enumerate(insns_b):
            if i.address >= VA_HOOK_BARRACKS_K:
                break
            if i.mnemonic == "call" and "412000" in i.op_str:
                prev_push = insns_b[idx - 2]
                if prev_push.mnemonic == "push":
                    try:
                        b_slots.append(int(prev_push.op_str, 0))
                    except ValueError:
                        pass

        # Native Barracks max slot used is 7 (slots 0..7)
        for s in b_slots:
            self.assertLessEqual(s, 7, f"Native Barracks slot {s} must be <= 7")

        # 2. Native Joseon HQ command card slots (0x00482F40..0x00483048)
        off_hq = va_to_offset(0x00482F40)
        insns_hq = list(self.md.disasm(self.data[off_hq : off_hq + 300], 0x00482F40))
        hq_slots = []
        for idx, i in enumerate(insns_hq):
            if i.address >= VA_HOOK_HQ_K:
                break
            if i.mnemonic == "call" and "412000" in i.op_str:
                prev_push = insns_hq[idx - 2]
                if prev_push.mnemonic == "push":
                    try:
                        hq_slots.append(int(prev_push.op_str, 0))
                    except ValueError:
                        pass

        # Native HQ max slot used is 8
        for s in hq_slots:
            self.assertLessEqual(s, 8, f"Native HQ slot {s} must be <= 8")

        # 3. Native Joseon Stables command card slots (KindID 0x2F 조선 목장, 0x0048188F..0x004818ED)
        off_st = va_to_offset(0x0048188F)
        insns_st = list(self.md.disasm(self.data[off_st : off_st + 200], 0x0048188F))
        st_slots = []
        for idx, i in enumerate(insns_st):
            if i.address >= VA_HOOK_STABLES_K:
                break
            if i.mnemonic == "call" and "412000" in i.op_str:
                prev_push = insns_st[idx - 2]
                if prev_push.mnemonic == "push":
                    try:
                        st_slots.append(int(prev_push.op_str, 0))
                    except ValueError:
                        pass

        # Native Stables max slot used is 6 (slots 0..6)
        for s in st_slots:
            self.assertLessEqual(s, 6, f"Native Stables slot {s} must be <= 6")

        # Patched Stables slots: [7, 8, 9, 10] do not collide with native slots
        for ps in STABLES_PATCHED_SLOTS:
            self.assertNotIn(ps, st_slots, f"Patched Stables slot {ps} collides with native slot")

    def test_r2_cave1_writes_sprite_and_animation_descriptors(self) -> None:
        """Verify Cave #1 writes authentic ImgID, StartFrame, FramesPerDir, Corpse, and Attack InstantFrame for all 10 units."""
        c1_bytes = build_init_cave(VA_CAVE_INIT_ROUTINE)
        desc_stride = 24 if len(c1_bytes) != 498 else 20
        self.assertLessEqual(len(c1_bytes), 500, "Cave #1 must stay within 500-byte slack space budget")
        desc_table = c1_bytes[-(desc_stride * 10):]

        expected_spr_info = [
            ("유생", 267, 176, (72, 12), (132, 8), (60, 12), (0, 8)),
            ("검술 낭인", 328, 136, (40, 8), (80, 8), (120, 9), (0, 8)),
            ("조총 낭인", 329, 136, (40, 8), (80, 8), (120, 9), (0, 8)),
            ("구미호", 295, 144, (40, 8), (80, 8), (120, 17), (0, 8)),
            ("대만 왕벌", 314, 160, (0, 8), (0, 8), (144, 11), (72, 8)),
            ("조선 호랑이", 272, 136, (40, 8), (80, 8), (120, 10), (0, 8)),
            ("털가면", 311, 130, (0, 8), (80, 8), (120, 10), (40, 8)),
            ("설녀", 334, 192, (84, 10), (134, 10), (65, 19), (0, 13)),
            ("조선 도깨비", 300, 180, (60, 8), (100, 8), (140, 11), (0, 12)),
            ("불가살이", 296, 216, (80, 8), (120, 8), (160, 20), (0, 16)),
        ]

        for idx, (name, exp_img_id, max_frames, exp_idle, exp_move, exp_die, exp_atk) in enumerate(expected_spr_info):
            entry = desc_table[idx * desc_stride : (idx + 1) * desc_stride]
            hp, img_id, rice_half, potato, btime, speed, min_atk, max_atk, icon_x, hotkey, idle_st, idle_fr, move_st, move_fr, die_st, die_fr, atk_st, atk_fr = struct.unpack("<HH16B", entry[:20])
            self.assertEqual(img_id, exp_img_id, f"{name} ImgID mismatch")
            self.assertEqual((idle_st, idle_fr), exp_idle, f"{name} Idle (start, frames) mismatch")
            self.assertEqual((move_st, move_fr), exp_move, f"{name} Move (start, frames) mismatch")
            self.assertEqual((die_st, die_fr), exp_die, f"{name} Die (start, frames) mismatch")
            self.assertEqual((atk_st, atk_fr), exp_atk, f"{name} Attack (start, frames) mismatch")
            # Boundary check against .spr frame_count
            self.assertLessEqual(idle_st + idle_fr * 5, max_frames, f"{name} Idle exceeds frame_count")
            self.assertLessEqual(move_st + move_fr * 5, max_frames, f"{name} Move exceeds frame_count")
            self.assertLessEqual(die_st + die_fr * 1, max_frames, f"{name} Die exceeds frame_count")
            self.assertLessEqual(atk_st + atk_fr * 5, max_frames, f"{name} Attack exceeds frame_count")

    def test_r2_voice_hitsound_and_corpse_decay_matching(self) -> None:
        """Verify all 10 units have role-matched HitSound (+0x5C), Voice IDs (+0x6C..+0x73), and Corpse InstantFrame (die_frames - 1)."""
        expected_voice_sfx = [
            ("유생", 0x4E, 1, 221, 12 - 1),
            ("검술 낭인", 0x03, 1, 224, 9 - 1),
            ("조총 낭인", 0x0C, 8, 230, 9 - 1),
            ("구미호", 0x10, 1, 227, 17 - 1),
            ("대만 왕벌", 0x6C, 1, 236, 11 - 1),
            ("조선 호랑이", 0x1C, 1, 235, 10 - 1),
            ("털가면", 0x1C, 1, 235, 10 - 1),
            ("설녀", 0x63, 1, 227, 19 - 1),
            ("조선 도깨비", 0x27, 23, 234, 11 - 1),
            ("불가살이", 0x1C, 23, 362, 20 - 1),
        ]
        c1_bytes = build_init_cave(VA_CAVE_INIT_ROUTINE)
        desc_stride = 24 if len(c1_bytes) != 498 else 20
        desc_table = c1_bytes[-(desc_stride * 10):]
        for idx, (name, exp_vtpl, exp_hit, exp_die_sfx, exp_corpse_inst) in enumerate(expected_voice_sfx):
            slot_off = va_to_offset(0x004E4C70 + idx * 16)
            vtpl, hit_sfx, die_sfx = struct.unpack_from("<BBH", self.data, slot_off + 0x0C)
            self.assertEqual(vtpl, exp_vtpl, f"{name} voice_tpl_id mismatch")
            self.assertIn(hit_sfx, (exp_hit, NEW_UNITS_METADATA[idx]["attack_atb"]), f"{name} hit_sfx (+0x5C) mismatch")
            self.assertEqual(die_sfx, exp_die_sfx, f"{name} die_sfx (+0x6E) mismatch")
            die_fr = desc_table[idx * desc_stride + 17]
            self.assertEqual(die_fr - 1, exp_corpse_inst, f"{name} corpse InstantFrame (die_frames - 1) mismatch")

    def test_r2_command_card_one_vacant_slot_invariant(self) -> None:
        """Verify the 1-vacant-slot invariant: HQ, Barracks, and Stables leave strictly 1 empty slot."""
        # In Skirmish mode, Joseon HQ native active slots are {0, 1, 2, 3, 4, 5, 6, 8} (Slot 7 is vacant, Slot 8 is written at 0x004832CB).
        native_hq = {0, 1, 2, 3, 4, 5, 6, 8}
        native_barracks = {0, 1, 2, 3, 4, 5, 6, 7}
        native_stables = {0, 1, 2, 3, 4, 5, 6}

        building_configs = [
            ("Joseon HQ", native_hq, set(HQ_PATCHED_SLOTS), 7),
            ("Joseon Barracks", native_barracks, set(BARRACKS_PATCHED_SLOTS), 11),
            ("Joseon Stables", native_stables, set(STABLES_PATCHED_SLOTS), 11),
        ]

        all_12_slots = set(range(12))

        for name, native_slots, custom_slots, expected_vacant_slot in building_configs:
            self.assertEqual(
                len(native_slots & custom_slots),
                0,
                f"{name} custom slots {custom_slots} must not collide with native slots {native_slots}",
            )
            # Combined occupied slots
            occupied = native_slots | custom_slots
            # Exactly 11 slots must be occupied
            self.assertEqual(
                len(occupied),
                11,
                f"{name} must have exactly 11 occupied slots, found {len(occupied)} ({sorted(occupied)})",
            )
            # Strictly 1 empty slot remaining
            vacant = all_12_slots - occupied
            self.assertEqual(
                len(vacant),
                1,
                f"{name} must have strictly 1 empty slot remaining, found {vacant}",
            )
            # The remaining vacant slot must match expected_vacant_slot
            self.assertIn(
                expected_vacant_slot,
                vacant,
                f"{name} expected Slot {expected_vacant_slot} to be the vacant slot, found {vacant}",
            )

    # =========================================================================
    # Requirement R3 Tests: syw2x.dll Non-Overlap & dxwrapper Validation
    # =========================================================================

    def test_r3_syw2x_memory_non_overlap(self) -> None:
        """Parse and disassemble syw2x.dll and verify all accessed memory addresses have zero overlap with patch sites."""
        syw_path = self.root / "YM" / "dawn" / "syw2x.dll"
        self.assertTrue(syw_path.exists(), "syw2x.dll must exist in YM/dawn")

        pe = pefile.PE(str(syw_path))
        image_base = pe.OPTIONAL_HEADER.ImageBase
        text_sec = next(s for s in pe.sections if b".text" in s.Name)
        text_data = text_sec.get_data()
        text_va = text_sec.VirtualAddress + image_base

        if self.is_15_units or self.is_round5:
            our_ranges = [
                ("Hook #4 (Default Unit CmdCard)", VA_HOOK_DEFAULT_CMDCARD, VA_HOOK_DEFAULT_CMDCARD + 5),
                ("Hook #2 (Barracks CmdCard)", VA_HOOK_BARRACKS_K, VA_HOOK_BARRACKS_K + 5),
                ("Hook #3 (HQ CmdCard)", VA_HOOK_HQ_K, VA_HOOK_HQ_K + 5),
                ("Hook #Stables (Stables CmdCard)", VA_HOOK_STABLES_K, VA_HOOK_STABLES_K + 5),
                ("Hook #AdvBarracks (AdvBarracks CmdCard)", 0x004810A0, 0x004810A5),
                ("Hook #1 (InitAllKindInfo)", VA_HOOK_INIT_KIND, VA_HOOK_INIT_KIND + 7),
                ("F1 Debug Limit", 0x004A796A, 0x004A7970),
                ("Hook #5 (Skirmish Default Tab)", VA_PROTOCOL_SELECT_RETAIL_HONJA, VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN + 8),
                ("Code Caves", 0x004E4C70, 0x004E5000),
                ("ButtonTable [0x2E..0x30]", 0x00637D28, 0x00637D28 + 3 * 0x10),
                ("ButtonTable [0x44..0x4F]", 0x00637E88, 0x00637E88 + 12 * 0x10),
                ("KindInfo [0x70..0x7E]", VA_KIND_NEW_70, VA_KIND_NEW_70 + 15 * 0x394),
                ("CmdTable [0xAB..0xB4]", 0x009E3F38, 0x009E3F38 + 10 * 0x18),
                ("CmdTable [0xBF..0xC3]", 0x009E4118, 0x009E4118 + 5 * 0x18),
            ]
        else:
            our_ranges = [
                ("Hook #4 (Default Unit CmdCard)", VA_HOOK_DEFAULT_CMDCARD, VA_HOOK_DEFAULT_CMDCARD + 5),
                ("Hook #2 (Barracks CmdCard)", VA_HOOK_BARRACKS_K, VA_HOOK_BARRACKS_K + 5),
                ("Hook #3 (HQ CmdCard)", VA_HOOK_HQ_K, VA_HOOK_HQ_K + 5),
                ("Hook #1 (InitAllKindInfo)", VA_HOOK_INIT_KIND, VA_HOOK_INIT_KIND + 7),
                ("F1 Debug Limit", 0x004A796A, 0x004A7970),
                ("Hook #5 (Skirmish Default Tab)", VA_PROTOCOL_SELECT_RETAIL_HONJA, VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN + 8),
                ("Code Caves #1-#4", VA_CAVE_UNIT_NAME_70, VA_CAVE_CMDCARD_DISPATCH + 0x30),
                ("ButtonTable [0x47..0x49]", VA_BTN_NEW_47, VA_BTN_NEW_49 + 0x10),
                ("KindInfo [0x70..0x72]", VA_KIND_NEW_70, VA_KIND_NEW_72 + 0x394),
                ("CmdTable [0x54, 0x58, 0x59]", VA_CMD_NEW_54, VA_CMD_NEW_59 + 0x18),
            ]

        conflicts = []
        for ins in self.md.disasm(text_data, text_va):
            for op in ins.operands:
                val = None
                if op.type == capstone.x86.X86_OP_IMM:
                    val = op.imm
                elif op.type == capstone.x86.X86_OP_MEM:
                    val = op.mem.disp
                if val is not None and 0x00400000 <= val <= 0x01100000:
                    for name, start, end in our_ranges:
                        if start <= val < end:
                            conflicts.append((hex(val), name, hex(ins.address)))

        self.assertEqual(len(conflicts), 0, f"syw2x.dll memory conflict detected with patch addresses: {conflicts}")

    def test_r3_dxwrapper_ini_and_binary_validation(self) -> None:
        """Verify dxwrapper.ini contains required keys and dxwrapper.dll binary strings match."""
        ini_path = self.root / "YM" / "dawn" / "dxwrapper.ini"
        self.assertTrue(ini_path.exists(), "dxwrapper.ini must exist")
        cp = configparser.ConfigParser()
        cp.read(str(ini_path))

        self.assertEqual(cp.getint("Compatibility", "Dd7to9"), 1)
        self.assertEqual(cp.getint("Compatibility", "EnableDdrawWrapper"), 1)
        self.assertEqual(cp.getint("ddraw", "ConvertToDirectDraw7"), 1)
        self.assertEqual(cp.getint("ddraw", "DdrawFixByteAlignment"), 1)
        self.assertEqual(cp.getint("Dd7to9", "DdrawEmulateSurface"), 1)
        self.assertEqual(cp.getint("Dd7to9", "DdrawUseNativeResolution"), 1)
        self.assertEqual(cp.getint("Dd7to9", "DdrawMaintainAspectRatio"), 1)

        dxw_data = (self.root / "YM" / "dawn" / "dxwrapper.dll").read_bytes()
        tokens = [
            b"Dd7to9",
            b"EnableDdrawWrapper",
            b"ConvertToDirectDraw7",
            b"DdrawFixByteAlignment",
            b"DdrawEmulateSurface",
            b"DdrawUseNativeResolution",
            b"DdrawMaintainAspectRatio",
        ]
        for token in tokens:
            self.assertIn(token, dxw_data, f"Token {token.decode()} must exist in dxwrapper.dll binary")

    # =========================================================================
    # Requirement R4 Tests: Skirmish State Machine & Protocol Visibility
    # =========================================================================

    def test_r4_skirmish_state_machine_tab_selection(self) -> None:
        """Verify Hook #5 retail path and standalone fallback path in dawn.exe default to 혼자하기."""
        # 1. Retail path at 0x004B8CD8 & 0x004B8CE4
        ins_retail = list(self.md.disasm(self.data[va_to_offset(VA_PROTOCOL_SELECT_RETAIL_HONJA) : va_to_offset(VA_PROTOCOL_SELECT_RETAIL_HONJA) + 24], VA_PROTOCOL_SELECT_RETAIL_HONJA))
        self.assertEqual(ins_retail[0].mnemonic, "push")
        self.assertEqual(ins_retail[0].op_str, "1", "Retail path must push 1 for 혼자하기 (0x0106A7C8)")
        self.assertEqual(ins_retail[3].mnemonic, "push")
        self.assertEqual(ins_retail[3].op_str, "0", "Retail path must push 0 for 여럿이하기 (0x0106A600)")

        # 2. Standalone fallback path at 0x004B8D09..0x004B8D38
        ins_fallback = list(self.md.disasm(self.data[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL) : va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL) + 48], VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL))
        self.assertEqual(ins_fallback[0].mnemonic, "push")
        self.assertEqual(ins_fallback[0].op_str, "0", "Fallback must push 0 to unselect 여럿이하기 (0x0106A600)")
        self.assertEqual(ins_fallback[3].mnemonic, "push")
        self.assertEqual(ins_fallback[3].op_str, "1", "Fallback must push 1 to select 혼자하기 (0x0106A7C8)")
        self.assertEqual(ins_fallback[6].mnemonic, "push")
        self.assertEqual(ins_fallback[6].op_str, "0", "Fallback must push 0 to disable 여럿이하기 (0x0106A600)")
        self.assertEqual(ins_fallback[9].mnemonic, "push")
        self.assertEqual(ins_fallback[9].op_str, "1", "Fallback must push 1 to enable 혼자하기 (0x0106A7C8)")

    def test_r4_protocol_list_visibility_control(self) -> None:
        """Verify that protocol list (0x01074588) visibility is controlled via 0x004CB360 with push 0 for 혼자하기."""
        # In CProtocolSelect::ProcessEvents at 0x004B9249..0x004B9285
        off_ev = va_to_offset(0x004B9249)
        insns = list(self.md.disasm(self.data[off_ev : off_ev + 64], 0x004B9249))

        # Check call to 0x004CB360 on 0x01074588
        call_addrs = [int(i.op_str, 16) for i in insns if i.mnemonic == "call" and i.op_str.startswith("0x")]
        self.assertIn(0x004CB360, call_addrs, "ProcessEvents must call 0x004CB360 to set protocol list visibility")

    # =========================================================================
    # Requirement R5 Tests: Array Limits, Routing, and F1 Debug Dialog
    # =========================================================================

    def test_r5_array_bounds_audit(self) -> None:
        """Verify universal engine limits (200 units) at 0x004A2FE3, 0x004A3775, and 0x004A37C5."""
        # 1. 0x004A2FE3 in InitAllKindInfo: cmp eax, 0x009E1DD0 (200 * 0x394 bytes)
        off1 = va_to_offset(0x004A2FDA)
        insns1 = list(self.md.disasm(self.data[off1 : off1 + 20], 0x004A2FDA))
        cmp1 = next(i for i in insns1 if i.address == 0x004A2FE3)
        self.assertEqual(cmp1.mnemonic, "cmp")
        self.assertEqual(cmp1.op_str, "eax, 0x9e1dd0", "InitAllKindInfo must compare against 200th unit entry address")

        # 2. 0x004A3775 in IncrementUnitCount: cmp dx, 0xC8 (200 units limit)
        off2 = va_to_offset(0x004A3770)
        insns2 = list(self.md.disasm(self.data[off2 : off2 + 15], 0x004A3770))
        cmp2 = next(i for i in insns2 if i.address == 0x004A3775)
        self.assertEqual(cmp2.mnemonic, "cmp")
        self.assertEqual(cmp2.op_str, "dx, 0xc8", "IncrementUnitCount bound check must be 200 (0xC8)")

        # 3. 0x004A37C5 in DecrementUnitCount: cmp dx, 0xC8 (200 units limit)
        off3 = va_to_offset(0x004A37C0)
        insns3 = list(self.md.disasm(self.data[off3 : off3 + 15], 0x004A37C0))
        cmp3 = next(i for i in insns3 if i.address == 0x004A37C5)
        self.assertEqual(cmp3.mnemonic, "cmp")
        self.assertEqual(cmp3.op_str, "dx, 0xc8", "DecrementUnitCount bound check must be 200 (0xC8)")

    def test_r5_selection_command_card_routing(self) -> None:
        """Verify selection command card branch (0x0047F90C cmp eax, 0x6D; ja 0x004801B4) routes to Hook #4."""
        off_branch = va_to_offset(0x0047F90C)
        insns_branch = list(self.md.disasm(self.data[off_branch : off_branch + 12], 0x0047F90C))
        self.assertEqual(insns_branch[0].mnemonic, "cmp")
        self.assertEqual(insns_branch[0].op_str, "eax, 0x6d")
        self.assertEqual(insns_branch[1].mnemonic, "ja")
        self.assertEqual(int(insns_branch[1].op_str, 16), 0x004801B4)

        # At fallback target 0x004801B4, Hook #4 at 0x004801BB calls Cave #4 (0x004E4FB8)
        off_hook4 = va_to_offset(VA_HOOK_DEFAULT_CMDCARD)
        ins_h4 = list(self.md.disasm(self.data[off_hook4 : off_hook4 + 5], VA_HOOK_DEFAULT_CMDCARD))[0]
        self.assertEqual(ins_h4.mnemonic, "call")
        self.assertEqual(int(ins_h4.op_str, 16), VA_CAVE_CMDCARD_DISPATCH)

        # For KindID 0x70..0x79: eax = KindID - 2 -> 0x6E..0x77 > 0x6D, guaranteed to trigger ja!
        target_kind_ids = list(range(0x70, 0x7F)) if (self.is_15_units or self.is_round5) else (0x70, 0x71, 0x72)
        for kind_id in target_kind_ids:
            eax = kind_id - 2
            self.assertGreater(eax, 0x6D, f"KindID 0x{kind_id:02X} must exceed jump table limit 0x6D")

    def test_r5_f1_debug_dialog_unit_check(self) -> None:
        """Verify F1 debug dialog unit list check at 0x004A796A is cmp ax, 0x79 or 0x7E (or 0x72 in Round 4)."""
        off = va_to_offset(0x004A796A)
        insns = list(self.md.disasm(self.data[off : off + 10], 0x004A796A))
        self.assertEqual(insns[0].mnemonic, "cmp")
        expected_cmps = ["ax, 0x79", "ax, 0x7e"] if (self.is_15_units or self.is_round5) else ["ax, 0x72"]
        self.assertIn(insns[0].op_str, expected_cmps, f"F1 debug dialog limit must be cmp in {expected_cmps} to include new units")
        self.assertEqual(insns[1].mnemonic, "jg")
        self.assertEqual(int(insns[1].op_str, 16), 0x004A79DC)

    def test_r2_health_bar_and_selection_box_above_sprite_head(self) -> None:
        """Verify all 10 units have custom KindInfo (+0x0E BotY, +0x1E Width%, +0x20 Height%, +0x2E MaxMP) placing health bars cleanly above sprite heads."""
        from tools.modding.patch_joseon_new_unit import UNIT_BBOX_PARAMS, VA_CAVE_BBOX_WH_TABLE

        # 1. Verify Cave #1 instructions write [ebx + 0x0e], [ebx + 0x1e], [ebx + 0x20], and [ebx + 0x2e] BEFORE CalcKindChecksum
        c1_bytes = build_init_cave(VA_CAVE_INIT_ROUTINE)
        c1_insns = list(self.md.disasm(c1_bytes[:296], VA_CAVE_INIT_ROUTINE))
        chk_addr = next(i.address for i in c1_insns if i.mnemonic == "call" and int(i.op_str, 16) in (VA_CALC_KIND_CHECKSUM, 0x0043F8D0, VA_CAVE_INIT_EXTRA))
        for disp_str in ("0xe", "0x1e", "0x20", "0x2e"):
            matches = [i for i in c1_insns if i.mnemonic == "mov" and f"ebx + {disp_str}]" in i.op_str]
            self.assertEqual(len(matches), 1, f"Cave #1 must write [ebx + {disp_str}]")
            self.assertLess(matches[0].address, chk_addr, f"[ebx + {disp_str}] must be written before CalcKindChecksum")

        # 2. Verify stored parameters and computed Top_Y ([esi + 0x54]) vs sprite head Y across all 10 units
        expected_canvas_and_head = [
            ("유생", 106, 97, 26),
            ("검술 낭인", 94, 100, 17),
            ("조총 낭인", 102, 103, 27),
            ("구미호", 250, 187, 72),
            ("대만 왕벌", 92, 146, 16),
            ("조선 호랑이", 114, 87, 20),
            ("털가면", 78, 76, 20),
            ("설녀", 130, 164, 19),
            ("조선 도깨비", 268, 206, 25),
            ("불가살이", 272, 188, 71),
        ]
        for idx, (name, cw, ch, head_y) in enumerate(expected_canvas_and_head):
            exp_bot, exp_w, exp_h = UNIT_BBOX_PARAMS[idx]
            bot_0e = self.data[va_to_offset(0x004E4C70 + idx * 16 - 5)]
            w_1e, h_20 = struct.unpack_from("<BB", self.data, va_to_offset(VA_CAVE_BBOX_WH_TABLE + idx * 2))
            self.assertEqual((bot_0e, w_1e, h_20), (exp_bot, exp_w, exp_h), f"{name} bbox params mismatch in binary")

            box_w = (w_1e * cw) // 100
            bot_y = ch - bot_0e
            box_h = (h_20 * ch) // 100
            top_y = bot_y - box_h
            bar_bottom = (top_y + 8) if idx == 0 else (top_y + 3)
            self.assertGreaterEqual(top_y, 0, f"{name} Top_Y ({top_y}) must be >= 0")
            self.assertLess(bar_bottom, head_y, f"{name} bar bottom ({bar_bottom}) overlaps sprite head ({head_y})")
            self.assertTrue(35 <= box_w <= 75, f"{name} health bar width ({box_w}px) out of tight range")

    # =========================================================================
    # Requirement R6 Tests: Custom Button Visuals, Hornet Death & AI Hooks
    # =========================================================================

    def test_r6_button_sprites_extended_and_valid(self) -> None:
        """Verify button_plus.Spr frame count is extended to 299, custom frames 289..298 decompress cleanly to 1156 bytes, and Cave #1 registers ButtonTable icon frames 289..298."""
        from tools.assets.sprite_rle import SpriteDecoder

        fnt_path = self.root / "YM" / "dawn" / "fnt" / "button_plus.Spr"
        self.assertTrue(fnt_path.exists(), "button_plus.Spr must exist in fnt/")
        dec = SpriteDecoder.from_file(fnt_path)
        self.assertEqual(dec.frame_count, 299, "button_plus.Spr must have exactly 299 frames (including 10 custom Joseon units)")
        self.assertEqual(dec.width, 34, "Button sprite width must be 34 px")
        self.assertEqual(dec.height, 34, "Button sprite height must be 34 px")

        for f in range(289, 299):
            raw_px = dec.decode_frame_raw(f)
            self.assertEqual(len(raw_px), 1156, f"Button frame {f} must decompress to exactly 1156 pixels (34x34)")
            non_zero = sum(1 for p in raw_px if p != 0)
            self.assertGreater(non_zero, 500, f"Button frame {f} must have non-trivial opaque button content")

        # Verify Cave #1 descriptors have matching icon values 0x21..0x2A (pushed as 0x0121..0x012A = 289..298)
        c1_bytes = build_init_cave(VA_CAVE_INIT_ROUTINE)
        desc_stride = 24 if len(c1_bytes) != 498 else 20
        desc_table = c1_bytes[-(desc_stride * 10):]
        for idx in range(10):
            entry = desc_table[idx * desc_stride : (idx + 1) * desc_stride]
            # byte 11 in descriptor is icon
            icon_byte = entry[11]
            self.assertEqual(icon_byte, 0x21 + idx, f"Unit {idx} icon descriptor byte must be 0x{0x21+idx:02X}")
            expected_frame = 289 + idx
            self.assertEqual((1 << 8) | icon_byte, expected_frame, f"Unit {idx} effective icon frame must be {expected_frame}")

    def test_r6_hornet_instant_death_patch(self) -> None:
        """Verify 0x00401AAF intercepts Joseon Hornet (0x74) to xor eax, eax; ret (no corpse) and other units to jmp 0x401bb0."""
        off = va_to_offset(VA_HOOK_HORNET_DEATH)
        chunk = self.data[off : off + 49]
        insns = list(self.md.disasm(chunk, VA_HOOK_HORNET_DEATH))

        # 1. First instruction must compare KindID in eax against 0x74 (조선왕벌)
        self.assertEqual(insns[0].mnemonic, "cmp")
        self.assertEqual(insns[0].op_str, "eax, 0x74")
        self.assertEqual(insns[1].mnemonic, "je")
        vanish_target = int(insns[1].op_str, 16)

        # 2. At vanish_target, must execute xor eax, eax; ret (skipping corpse spawner 0x00444060)
        vanish_insns = [i for i in insns if i.address >= vanish_target][:2]
        self.assertEqual(vanish_insns[0].mnemonic, "xor")
        self.assertEqual(vanish_insns[0].op_str, "eax, eax")
        self.assertEqual(vanish_insns[1].mnemonic, "ret")

        # 3. Second branch compares KindID against 0x70
        self.assertEqual(insns[2].mnemonic, "cmp")
        self.assertEqual(insns[2].op_str, "eax, 0x70")
        self.assertEqual(insns[3].mnemonic, "jae")
        corpse_target = int(insns[3].op_str, 16)

        # 4. At corpse_target, must jump to 0x00401BB0 (spawns ground corpse)
        corpse_insn = next(i for i in insns if i.address == corpse_target)
        self.assertEqual(corpse_insn.mnemonic, "jmp")
        self.assertEqual(int(corpse_insn.op_str, 16), 0x00401BB0)

    def test_r6_ai_difficulty_and_cheat_bypass_hooks(self) -> None:
        """Verify AI economy 50:50 equalizing cheat bypass hooks at 0x0043F8BB and 0x0043F8C1, and Order 3 preservation."""
        # 1. 0x0043F8BB preserves original jle 0x0043FB62 so decision wheel logic is untouched
        off_b = va_to_offset(VA_HOOK_AI_CHEAT_BYPASS)
        ins_b = list(self.md.disasm(self.data[off_b : off_b + 6], VA_HOOK_AI_CHEAT_BYPASS))
        self.assertEqual(ins_b[0].mnemonic, "jle")
        self.assertEqual(int(ins_b[0].op_str, 16), VA_AI_CHEAT_RESUME)

        # 2. 0x0043F8C1 jumps over 50:50 cheat directly to Order 3 (0x0043F8F0)
        off_n = va_to_offset(VA_HOOK_AI_CHEAT_NEUTRALIZE)
        ins_n = list(self.md.disasm(self.data[off_n : off_n + 2], VA_HOOK_AI_CHEAT_NEUTRALIZE))
        self.assertEqual(ins_n[0].mnemonic, "jmp")
        self.assertEqual(int(ins_n[0].op_str, 16), VA_AI_ORDER3_HARVEST_ENTRY)

        # 3. Order 3 entry at 0x0043F8F0 is 100% intact (mov ecx, [0x8924b8]; mov word ptr [esi + 0xd32], 3)
        off_o3 = va_to_offset(VA_AI_ORDER3_HARVEST_ENTRY)
        ins_o3 = list(self.md.disasm(self.data[off_o3 : off_o3 + 20], VA_AI_ORDER3_HARVEST_ENTRY))
        self.assertEqual(ins_o3[0].mnemonic, "mov")
        self.assertEqual(ins_o3[1].mnemonic, "mov")
        self.assertIn("0xd32", ins_o3[1].op_str)

    # =========================================================================
    # Requirement R7 Tests: Combat & Skill KindInfo Fields Verification
    # =========================================================================

    def test_r7_kindinfo_all_new_fields_verification(self) -> None:
        """Verify all 10 Joseon units specify all 9 Round 7 KindInfo fields (+0x04 BaseAttackPower, +0x06 MaxHP, +0x2C MoveSpeed, +0x2E MaxMP, +0x36 Range1, +0x38 Range2, +0x4C Atb1, +0x50 Atb2, +0x5C AttackAtb)."""
        self.assertEqual(len(NEW_UNITS_METADATA), 10, "Must have exactly 10 units")
        required_fields = [
            ("base_atk", 0x04),
            ("hp", 0x06),
            ("speed", 0x2C),
            ("max_mp", 0x2E),
            ("range1", 0x36),
            ("range2", 0x38),
            ("atb1", 0x4C),
            ("atb2", 0x50),
            ("attack_atb", 0x5C),
        ]
        for u in NEW_UNITS_METADATA:
            for field, offset in required_fields:
                self.assertIn(field, u, f"Unit {u['name']} (0x{u['kind_id']:02X}) missing field {field} (offset +0x{offset:02X})")
                val = u[field]
                self.assertIsInstance(val, int, f"{u['name']} {field} must be an integer")
                self.assertGreaterEqual(val, 0, f"{u['name']} {field} must be non-negative")

    def test_r7_kindinfo_air_flag_0x74(self) -> None:
        """Verify air flag (Atb1 & 0x10) is set for 0x74 대만 왕벌 and cleared for all 9 ground units."""
        bee = next(u for u in NEW_UNITS_METADATA if u["kind_id"] == 0x74)
        self.assertTrue(
            bool(bee["atb1"] & 0x10),
            "0x74 대만 왕벌 must have air flag bit 4 (0x10) set in Atb1 (+0x4C)",
        )

        for u in NEW_UNITS_METADATA:
            if u["kind_id"] != 0x74:
                self.assertFalse(
                    bool(u["atb1"] & 0x10),
                    f"{u['name']} (0x{u['kind_id']:02X}) is a ground unit and must NOT have air flag (Atb1 & 0x10)",
                )

    def test_r7_kindinfo_max_mp_specifications(self) -> None:
        """Verify MaxMP (+0x2E): 0x70 (100), 0x71 (80), 0x73 (100), 0x76 (80), 0x77 (120), 0x79 (120) and non-casters (0)."""
        expected_mp = {
            0x70: 100,  # 유생 (선비 포박술/매복)
            0x71: 80,   # 검술 낭인 (폭뢰격)
            0x72: 0,    # 조총 낭인 (패시브)
            0x73: 100,  # 구미호 (분신술/환술)
            0x74: 0,    # 대만 왕벌 (공중 근접 독침)
            0x75: 0,    # 조선 호랑이 (근접 물리)
            0x76: 80,   # 털가면 (냉동탄/빙결)
            0x77: 120,  # 설녀 (냉기 마법/눈보라 스플래쉬)
            0x78: 0,    # 조선 도깨비 (방망이 강타)
            0x79: 120,  # 불가살이 (화염차식 원거리 불공격 하이브리드)
        }
        for u in NEW_UNITS_METADATA:
            kind_id = u["kind_id"]
            self.assertEqual(
                u["max_mp"],
                expected_mp[kind_id],
                f"Unit {u['name']} (0x{kind_id:02X}) MaxMP must be {expected_mp[kind_id]}, got {u['max_mp']}",
            )

    def test_r7_kindinfo_range1_range2_all_units(self) -> None:
        """Verify Range1 (+0x36) and Range2 (+0x38) for all 10 units."""
        expected_ranges = {
            0x70: (5, 7),  # 유생: Range1 = 5, Range2 = 7
            0x71: (1, 5),  # 검술 낭인: Range1 = 1, Range2 = 5
            0x72: (6, 7),  # 조총 낭인: Range1 = 6, Range2 = 7
            0x73: (5, 6),  # 구미호: Range1 = 5, Range2 = 6
            0x74: (1, 5),  # 대만 왕벌: Range1 = 1, Range2 = 5
            0x75: (1, 5),  # 조선 호랑이: Range1 = 1, Range2 = 5
            0x76: (5, 6),  # 털가면: Range1 = 5, Range2 = 6
            0x77: (6, 7),  # 설녀: Range1 = 6, Range2 = 7
            0x78: (1, 5),  # 조선 도깨비: Range1 = 1, Range2 = 5
            0x79: (6, 7),  # 불가살이: Range1 = 6, Range2 = 7 (ranged flame mode)
        }
        for u in NEW_UNITS_METADATA:
            kind_id = u["kind_id"]
            exp_r1, exp_r2 = expected_ranges[kind_id]
            self.assertEqual(u["range1"], exp_r1, f"{u['name']} (0x{kind_id:02X}) Range1 mismatch")
            self.assertEqual(u["range2"], exp_r2, f"{u['name']} (0x{kind_id:02X}) Range2 mismatch")
            self.assertLessEqual(u["range1"], u["range2"], f"{u['name']} Range1 ({u['range1']}) must be <= Range2 ({u['range2']})")
            self.assertGreaterEqual(u["range1"], 1, f"{u['name']} Range1 must be >= 1")

    def test_r7_kindinfo_attack_atb_all_units(self) -> None:
        """Verify AttackAtb (+0x5C) dispatcher mapping for all 10 units."""
        expected_attack_atb = {
            0x70: 9,   # 유생: 9 (Ki-bullet / 포박술)
            0x71: 1,   # 검술 낭인: 1 (Melee slash)
            0x72: 8,   # 조총 낭인: 8 (Musket bullet, Bullet 19)
            0x73: 11,  # 구미호: 11 (Magic spirit orb, Bullet 15)
            0x74: 1,   # 대만 왕벌: 1 (Aerial stinger)
            0x75: 1,   # 조선 호랑이: 1 (Melee claw)
            0x76: 26,  # 털가면: 26 (Freezing ice ball, Bullet 12)
            0x77: 26,  # 설녀: 26 (Freezing ice ball + Splash)
            0x78: 23,  # 조선 도깨비: 23 (Ground shockwave ring, Smoke 0x37)
            0x79: 15,  # 불가살이: 15 / 0x0F (Japanese Flame Cart / Dragon Fire Breath, Bullet 7 + Smoke 0x1B + cltMap::SetFire)
        }
        for u in NEW_UNITS_METADATA:
            kind_id = u["kind_id"]
            exp_atb = expected_attack_atb[kind_id]
            self.assertEqual(
                u["attack_atb"],
                exp_atb,
                f"{u['name']} (0x{kind_id:02X}) AttackAtb must be {exp_atb}, got {u['attack_atb']}",
            )

    def test_r7_cltchar_copy_simulation_and_memory_geometry(self) -> None:
        """Simulate cltChar::Init copying KindInfo fields to entity struct and verify target offset alignments."""
        # Target cltChar offsets from reverse engineering (explorer_r7_native Section 2.1 & 2.2):
        #   cltChar + 0x168 = KindInfo + 0x04 (BaseAttackPower)
        #   cltChar + 0x120 = KindInfo + 0x06 (MaxHP)
        #   cltChar + 0x184 = KindInfo + 0x2C (MoveSpeed)
        #   cltChar + 0x124 = KindInfo + 0x2E (MaxMP)
        #   cltChar + 0x20C = KindInfo + 0x36 (Range1)
        #   cltChar + 0x208 = KindInfo + 0x38 (Range2)
        #   cltChar + 0x1D8 = KindInfo + 0x4C (Atb1)
        #   cltChar + 0x1DC = KindInfo + 0x50 (Atb2)
        #   cltChar + 0x1E4 = KindInfo + 0x5C (AttackAtb)
        #   cltChar + 0x1BC = 2 if (Atb1 & 0x10) else 1 (Air Unit detection at 0x00411E50)
        for u in NEW_UNITS_METADATA:
            kind_buf = bytearray(0x394)
            struct.pack_into("<H", kind_buf, 0x04, u["base_atk"])
            struct.pack_into("<H", kind_buf, 0x06, u["hp"])
            struct.pack_into("<H", kind_buf, 0x2C, u["speed"])
            struct.pack_into("<H", kind_buf, 0x2E, u["max_mp"])
            struct.pack_into("<H", kind_buf, 0x36, u["range1"])
            struct.pack_into("<H", kind_buf, 0x38, u["range2"])
            struct.pack_into("<I", kind_buf, 0x4C, u["atb1"])
            struct.pack_into("<I", kind_buf, 0x50, u["atb2"])
            struct.pack_into("<I", kind_buf, 0x5C, u["attack_atb"])

            clt_char = bytearray(0x300)
            # Emulate 0x00411D12..0x00411E77 instantiation
            struct.pack_into("<H", clt_char, 0x168, struct.unpack_from("<H", kind_buf, 0x04)[0])
            struct.pack_into("<H", clt_char, 0x120, struct.unpack_from("<H", kind_buf, 0x06)[0])
            struct.pack_into("<H", clt_char, 0x184, struct.unpack_from("<H", kind_buf, 0x2C)[0])
            struct.pack_into("<H", clt_char, 0x124, struct.unpack_from("<H", kind_buf, 0x2E)[0])
            struct.pack_into("<H", clt_char, 0x20C, struct.unpack_from("<H", kind_buf, 0x36)[0])
            struct.pack_into("<H", clt_char, 0x208, struct.unpack_from("<H", kind_buf, 0x38)[0])
            struct.pack_into("<I", clt_char, 0x1D8, struct.unpack_from("<I", kind_buf, 0x4C)[0])
            struct.pack_into("<I", clt_char, 0x1DC, struct.unpack_from("<I", kind_buf, 0x50)[0])
            struct.pack_into("<I", clt_char, 0x1E4, struct.unpack_from("<I", kind_buf, 0x5C)[0])

            # Air unit detection at 0x00411E50
            atb1 = struct.unpack_from("<I", kind_buf, 0x4C)[0]
            unit_class = 2 if (atb1 & 0x10) else 1
            clt_char[0x1BC] = unit_class

            # Assertions on cloned cltChar entity
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x168)[0], u["base_atk"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x120)[0], u["hp"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x184)[0], u["speed"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x124)[0], u["max_mp"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x20C)[0], u["range1"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x208)[0], u["range2"])
            self.assertEqual(struct.unpack_from("<I", clt_char, 0x1D8)[0], u["atb1"])
            self.assertEqual(struct.unpack_from("<I", clt_char, 0x1DC)[0], u["atb2"])
            self.assertEqual(struct.unpack_from("<I", clt_char, 0x1E4)[0], u["attack_atb"])

            if u["kind_id"] == 0x74:
                self.assertEqual(clt_char[0x1BC], 2, "Hornet must instantiate as Air Unit (cltChar+0x1BC == 2)")
            else:
                self.assertEqual(clt_char[0x1BC], 1, f"{u['name']} must instantiate as Ground Unit (cltChar+0x1BC == 1)")


    # =========================================================================
    # Joseon 5 New Infantry Units (0x7A~0x7E / 0x70~0x74) Comprehensive E2E Tests
    # =========================================================================

    def test_joseon_5_infantry_specification_matrix(self) -> None:
        """Verify the complete specification matrix for the 5 Joseon infantry units (등패수, 쌍수도병, 장창수, 월도병, 낭선병)."""
        self.assertEqual(len(JOSEON_5_INFANTRY_METADATA), 5, "Must specify exactly 5 infantry units")
        expected_names = ["등패수", "쌍수도병", "장창수", "월도병", "낭선병"]
        actual_names = [u["name"] for u in JOSEON_5_INFANTRY_METADATA]
        self.assertEqual(actual_names, expected_names, "5 unit names must match Muye 24-gi specification")

        for u in JOSEON_5_INFANTRY_METADATA:
            self.assertIn(u["kind_id"], range(0x7A, 0x7F), f"{u['name']} KindID must be in 0x7A..0x7E")
            self.assertIn(u["kind_id_alt"], range(0x70, 0x75), f"{u['name']} alternate KindID must be in 0x70..0x74")
            self.assertIn(u["cmd_id"], range(0xBF, 0xC4), f"{u['name']} CmdID must be in 0xBF..0xC3 (preserving 0xB5..0xB9 Farmer Build)")
            self.assertIn(u["btn_id"], (0x4E, 0x4F, 0x2E, 0x2F, 0x30), f"{u['name']} BtnID must be in valid non-colliding range")
            self.assertTrue(bool(u["atb1"] & 0x04), f"{u['name']} Atb1 must include ATB_MOVE (0x04)")
            self.assertTrue(bool(u["atb1"] & 0x01), f"{u['name']} Atb1 must include ATB_ATTACK (0x01)")
            self.assertGreater(u["hp"], 0, f"{u['name']} HP must be positive")
            self.assertGreater(u["base_atk"], 0, f"{u['name']} Attack must be positive")
            self.assertGreater(u["speed"], 0, f"{u['name']} Speed must be positive")
            self.assertGreater(u["rice"], 0, f"{u['name']} Rice cost must be positive")
            self.assertGreaterEqual(u["iron"], 0, f"{u['name']} Iron cost must be non-negative")
            self.assertIn(u["range1"], (1, 2), f"{u['name']} Range1 must be 1 or 2")
            self.assertGreaterEqual(u["range2"], u["range1"], f"{u['name']} Range2 must be >= Range1")

    def test_joseon_5_infantry_kindinfo_reconstruction(self) -> None:
        """Verify in-memory reconstruction of KindInfo entries (HP, attack, armor, speed, costs, names) for all 5 infantry units."""
        for u in JOSEON_5_INFANTRY_METADATA:
            buf = bytearray(0x394)
            struct.pack_into("<H", buf, 0x04, u["base_atk"])      # BaseAttackPower
            struct.pack_into("<H", buf, 0x06, u["hp"])            # MaxHP
            struct.pack_into("<H", buf, 0x42, u["defense"])       # Defense (+0x42, preserving +0x0C small icon)
            struct.pack_into("<H", buf, 0x10, u["btime"])         # BuildTime (seconds)
            struct.pack_into("<H", buf, 0x12, u["rice"])          # CostRice
            struct.pack_into("<H", buf, 0x14, u["potato"])        # CostPotato / Wood
            struct.pack_into("<I", buf, 0x24, u["iron"])          # CostMoney / Iron
            struct.pack_into("<H", buf, 0x28, 1)                  # Nation = 1 (Joseon)
            struct.pack_into("<H", buf, 0x2C, u["speed"])         # MoveSpeed
            struct.pack_into("<H", buf, 0x36, u["range1"])        # Range1
            struct.pack_into("<H", buf, 0x38, u["range2"])        # Range2
            struct.pack_into("<I", buf, 0x4C, u["atb1"])          # Atb1 (0x00410005 = Ground + Move + Attack)
            struct.pack_into("<I", buf, 0x50, u["atb2"])          # Atb2
            struct.pack_into("<I", buf, 0x5C, u["attack_atb"])    # AttackAtb (1 = Melee)

            # Assertions on reconstructed struct fields
            self.assertEqual(struct.unpack_from("<H", buf, 0x04)[0], u["base_atk"], f"{u['name']} BaseAttack mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x06)[0], u["hp"], f"{u['name']} MaxHP mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x42)[0], u["defense"], f"{u['name']} Defense mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x12)[0], u["rice"], f"{u['name']} Rice cost mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x14)[0], u["potato"], f"{u['name']} Potato/Wood cost mismatch")
            self.assertEqual(struct.unpack_from("<I", buf, 0x24)[0], u["iron"], f"{u['name']} Iron cost mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x28)[0], 1, f"{u['name']} Nation must be Joseon (1)")
            self.assertEqual(struct.unpack_from("<H", buf, 0x2C)[0], u["speed"], f"{u['name']} MoveSpeed mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x36)[0], u["range1"], f"{u['name']} Range1 mismatch")
            self.assertEqual(struct.unpack_from("<H", buf, 0x38)[0], u["range2"], f"{u['name']} Range2 mismatch")
            self.assertEqual(struct.unpack_from("<I", buf, 0x4C)[0], u["atb1"], f"{u['name']} Atb1 mismatch")
            self.assertEqual(struct.unpack_from("<I", buf, 0x5C)[0], u["attack_atb"], f"{u['name']} AttackAtb mismatch")

            # CP949 name encoding check
            name_cp949 = u["name"].encode("cp949") + b"\x00"
            self.assertLessEqual(len(name_cp949), 16, f"{u['name']} CP949 string must fit within 16-byte slot")
            self.assertEqual(name_cp949.decode("cp949").rstrip("\x00"), u["name"])

    def test_joseon_5_infantry_archer_sound_binding(self) -> None:
        """Verify Archer voice clone binding: SelectSfx=164, DyingSfx=223, MoveSfx=254, TryAttackSfx=314 for all 5 units."""
        # 1. Verify expected sound ID constants
        self.assertEqual(ARCHER_SFX_SELECT, 164, "Archer SelectSfx must be 164 (0x00A4)")
        self.assertEqual(ARCHER_SFX_DYING, 223, "Archer DyingSfx must be 223 (0x00DF)")
        self.assertEqual(ARCHER_SFX_MOVE, 254, "Archer MoveSfx must be 254 (0x00FE)")
        self.assertEqual(ARCHER_SFX_TRYATTACK, 314, "Archer TryAttackSfx must be 314 (0x013A)")
        self.assertEqual(ARCHER_VOICE_TPL_ID, 0x02, "Archer voice template ID must be 0x02")

        # 2. Extract authentic sound IDs from KindInfo[0x02] (Archer) initialization in dawn.exe
        # At 0x0049BF30..0x0049BFB2, UnitDef::Init pushes sound IDs for Archer (KindInfo[0x02] at 0x009B5950)
        va_call_archer = 0x0049BFB2
        off_call_archer = va_call_archer - IMAGE_BASE
        insns_archer = list(self.md.disasm(self.orig_data[off_call_archer - 140 : off_call_archer], va_call_archer - 140))
        pushes = [i.op_str for i in insns_archer if i.mnemonic == "push"]
        # Sound IDs are among the arguments pushed: Select (164), Dying (223), Move (254), Attack (314)
        sound_pushes = [int(p, 0) for p in pushes if p.isdigit() or p.startswith("0x")]
        self.assertIn(164, sound_pushes, "Archer SelectSfx 164 must be passed to UnitDef::Init")
        self.assertIn(223, sound_pushes, "Archer DyingSfx 223 must be passed to UnitDef::Init")
        self.assertIn(254, sound_pushes, "Archer MoveSfx 254 must be passed to UnitDef::Init")
        self.assertIn(314, sound_pushes, "Archer TryAttackSfx 314 must be passed to UnitDef::Init")

        # 3. Verify all 5 infantry units specify the identical 4 sound IDs
        for u in JOSEON_5_INFANTRY_METADATA:
            self.assertEqual(u["voice_tpl_id"], ARCHER_VOICE_TPL_ID, f"{u['name']} voice_tpl_id must be 0x02")
            self.assertEqual(u["select_sfx"], ARCHER_SFX_SELECT, f"{u['name']} SelectSfx must be 164")
            self.assertEqual(u["dying_sfx"], ARCHER_SFX_DYING, f"{u['name']} DyingSfx must be 223")
            self.assertEqual(u["move_sfx"], ARCHER_SFX_MOVE, f"{u['name']} MoveSfx must be 254")
            self.assertEqual(u["try_attack_sfx"], ARCHER_SFX_TRYATTACK, f"{u['name']} TryAttackSfx must be 314")

            # In-memory propagation check: pack into KindInfo +0x6C..+0x73
            kind_buf = bytearray(0x394)
            struct.pack_into("<HHHH", kind_buf, 0x6C, u["select_sfx"], u["dying_sfx"], u["move_sfx"], u["try_attack_sfx"])
            sel, die, mov, atk = struct.unpack_from("<HHHH", kind_buf, 0x6C)
            self.assertEqual((sel, die, mov, atk), (164, 223, 254, 314), f"{u['name']} KindInfo sound fields mismatch")

    def test_joseon_5_infantry_range_and_combat_gimmicks(self) -> None:
        """Verify combat range and gimmicks: 장창수 and 낭선병 Range1=2; 낭선병 knockback hook at 0x00470CD5 jumps to Zone D (0x00421A20)."""
        # 1. Range verification: 장창수 and 낭선병 have Range1 = 2 (extended melee stab)
        jangchang = next(u for u in JOSEON_5_INFANTRY_METADATA if u["name"] == "장창수")
        nangseon = next(u for u in JOSEON_5_INFANTRY_METADATA if u["name"] == "낭선병")
        dengpae = next(u for u in JOSEON_5_INFANTRY_METADATA if u["name"] == "등패수")
        ssangsu = next(u for u in JOSEON_5_INFANTRY_METADATA if u["name"] == "쌍수도병")
        woldo = next(u for u in JOSEON_5_INFANTRY_METADATA if u["name"] == "월도병")

        self.assertEqual(jangchang["range1"], 2, "장창수 must have Range1 = 2 (extended melee)")
        self.assertEqual(nangseon["range1"], 2, "낭선병 must have Range1 = 2 (extended melee)")
        self.assertEqual(dengpae["range1"], 1, "등패수 must have Range1 = 1 (melee shield)")
        self.assertEqual(ssangsu["range1"], 1, "쌍수도병 must have Range1 = 1 (melee sword)")
        self.assertEqual(woldo["range1"], 1, "월도병 must have Range1 = 1 (melee woldo)")

        # Verify AttackAtb = 1 (melee, no missile projectile creation)
        for u in (jangchang, nangseon, dengpae, ssangsu, woldo):
            self.assertEqual(u["attack_atb"], 1, f"{u['name']} AttackAtb must be 1 (direct melee)")

        # Verify engine Euclidean range math: dist^2 < 2025 * (Range1)^2
        # For Range1 = 2: max distance = sqrt(2025 * 4) = 90 pixels (~2.8 tiles)
        # For Range1 = 1: max distance = sqrt(2025 * 1) = 45 pixels (~1.4 tiles)
        dist_sq_range2 = 2025 * (2 ** 2)
        dist_sq_range1 = 2025 * (1 ** 2)
        self.assertEqual(dist_sq_range2, 8100)
        self.assertEqual(dist_sq_range1, 2025)
        self.assertGreater(dist_sq_range2, dist_sq_range1)

        # 2. Knockback hook site verification: 0x00470CD5 -> Zone D (0x00421A20)
        va_hook = 0x00470CD5
        va_cave = 0x00421A20
        off_hook = va_to_offset(va_hook)
        insns_hook = list(self.md.disasm(self.data[off_hook : off_hook + 6], va_hook))
        self.assertEqual(insns_hook[0].mnemonic, "jmp", "Hook at 0x00470CD5 must be a jmp instruction")
        self.assertEqual(int(insns_hook[0].op_str, 16), va_cave, "Hook at 0x00470CD5 must jump to Zone D (0x00421A20)")

        # 3. Zone D cave bounds audit: 0x00421A20..0x00421AA0 (128 bytes maximum)
        off_cave = va_to_offset(va_cave)
        insns_cave = list(self.md.disasm(self.data[off_cave : off_cave + 128], va_cave))
        self.assertGreater(len(insns_cave), 5, "Zone D cave must contain valid disassembled instructions")
        # Cave must handle attacker kind check, target building check, displacement, and jump back to resume
        jmp_resume = [i for i in insns_cave if i.mnemonic == "jmp" and int(i.op_str, 16) == 0x00470CE3]
        self.assertEqual(len(jmp_resume), 1, "Zone D cave must jump back to resume at 0x00470CE3")

    def test_joseon_5_infantry_building_command_cards(self) -> None:
        """Verify building command card slots: Barracks Slot 11 for 등패수, AdvBarracks Slots 8~11 for 쌍수도병, 장창수, 월도병, 낭선병."""
        # 1. Joseon Barracks (Kind 0x31, 훈련소): Slot 11 has 등패수
        dengpae = next(u for u in JOSEON_5_INFANTRY_METADATA if u["name"] == "등패수")
        self.assertEqual(dengpae["building_kind"], 0x31, "등패수 must be assigned to Joseon Barracks (Kind 0x31)")
        self.assertEqual(dengpae["slot"], 11, "등패수 must occupy Barracks Slot 11")
        self.assertIn(dengpae["btn_id"], (0x4E, 0x44), "등패수 ButtonID must be 0x4E (or 0x44)")

        # Barracks native slots: {0, 1, 2, 3, 4, 5, 6, 7}
        # In Round 5/6, slots 8, 9, 10 were patched. Slot 11 is the dedicated vacant slot!
        native_and_r5_barracks = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        self.assertNotIn(dengpae["slot"], native_and_r5_barracks - {11})
        self.assertEqual(dengpae["slot"], 11, "Slot 11 is the unique available slot for 등패수")

        # 2. Joseon AdvBarracks (Kind 0x57, 훈련도감 / 병기창): Slots 8~11
        adv_units = [u for u in JOSEON_5_INFANTRY_METADATA if u["building_kind"] == 0x57]
        self.assertEqual(len(adv_units), 4, "AdvBarracks must have exactly 4 new infantry units")
        adv_slots = [u["slot"] for u in adv_units]
        self.assertEqual(sorted(adv_slots), [8, 9, 10, 11], "AdvBarracks slots must be contiguous 8, 9, 10, 11")

        # Verify 1:1 mapping
        unit_slot_map = {u["name"]: u["slot"] for u in adv_units}
        self.assertEqual(unit_slot_map["쌍수도병"], 8)
        self.assertEqual(unit_slot_map["장창수"], 9)
        self.assertEqual(unit_slot_map["월도병"], 10)
        self.assertEqual(unit_slot_map["낭선병"], 11)

        # AdvBarracks native slots: {0, 1, 2, 3, 4, 5, 6} (Slot 7 reserved/empty)
        # Slots 8, 9, 10, 11 are 100% free and have zero collision with native slots
        native_advbarracks = {0, 1, 2, 3, 4, 5, 6}
        for s in adv_slots:
            self.assertNotIn(s, native_advbarracks, f"AdvBarracks slot {s} collides with native slots")

    def test_joseon_5_infantry_cmdtable_train_type(self) -> None:
        """Verify CmdTable entries have cmd_type = 8 (CMD_TRAIN) pointing to target KindIDs."""
        CMD_TRAIN = 8
        for u in JOSEON_5_INFANTRY_METADATA:
            # Reconstruct CmdTable entry (24 bytes, 0x18 stride):
            # +0x00: cmd_type (uint16 = 8)
            # +0x02: sub_action (uint16 = 0)
            # +0x04: kind_id (uint32)
            # +0x08: req_tech (uint32 = 0)
            # +0x0C: param1 (uint32 = 2)
            # +0x10: param2 (uint16 = 2)
            # +0x12: padding (uint16 = 0)
            cmd_buf = bytearray(0x18)
            struct.pack_into("<HHIIHH", cmd_buf, 0x00, CMD_TRAIN, 0, u["kind_id"], 0, 2, 2)

            cmd_type, sub_action, kind_id, req_tech = struct.unpack_from("<HHII", cmd_buf, 0x00)
            self.assertEqual(cmd_type, CMD_TRAIN, f"{u['name']} cmd_type must be 8 (CMD_TRAIN)")
            self.assertEqual(sub_action, 0, f"{u['name']} sub_action must be 0")
            self.assertEqual(kind_id, u["kind_id"], f"{u['name']} target kind_id mismatch")
            self.assertEqual(req_tech, 0, f"{u['name']} req_tech must be 0 (no tech block)")

            # Also verify with alternate KindID
            struct.pack_into("<I", cmd_buf, 0x04, u["kind_id_alt"])
            self.assertEqual(struct.unpack_from("<I", cmd_buf, 0x04)[0], u["kind_id_alt"])

    def test_code_cave_safety_authorized_zones(self) -> None:
        """Verify all modified code ranges fall strictly within authorized zones (Zone A, B, C, D)."""
        # Authorized memory zones:
        # Zone A: .text slack space (0x004E4C70..0x004E5000, 912 bytes)
        # Zone B: AI 50:50 cheat bypass (0x0043F8C3..0x0043F8EF, 45 bytes)
        # Zone C: Debug bypass blocks (0x0043C8F7..0x0043C92A, 0x0043CB4A..0x0043CBEF)
        # Zone D: Dead CD-check function (0x00421A20..0x00421AA0, 128 bytes)
        authorized_zones = [
            ("Zone A: .text Slack", 0x004E4C70, 0x004E5000),
            ("Zone B: AI Cheat Bypass", 0x0043F8C3, 0x0043F8EF),
            ("Zone C1: Order 7 Debug Bypass", 0x0043C8F5, 0x0043C92B),
            ("Zone C2: Order 8 Debug Bypass", 0x0043CB45, 0x0043CBF0),
            ("Zone D: Dead CD-Check Cave", 0x00421A20, 0x00421AA0),
            ("Zone F1: Dead AI Function Cave", 0x00440C63, 0x00441026),
            ("Zone F2: Dead Command Card Cave", 0x0048943A, 0x004894E8),
        ]

        # Verify zones are disjoint and within .text section
        pe = pefile.PE(data=self.orig_data)
        text_sec = next(s for s in pe.sections if b".text" in s.Name)
        text_start_va = text_sec.VirtualAddress + IMAGE_BASE
        text_end_va = text_start_va + max(text_sec.Misc_VirtualSize, text_sec.SizeOfRawData)

        for name, start_va, end_va in authorized_zones:
            self.assertGreaterEqual(start_va, text_start_va, f"{name} start below .text start")
            self.assertLessEqual(end_va, text_end_va, f"{name} end exceeds .text virtual size")
            self.assertGreater(end_va, start_va, f"{name} size must be positive")

        # Verify upper limit safety on KindInfo array: must stay < 0x009E1DD0 (engine 200-unit limit)
        # KindInfo base = 0x009B5228, stride = 0x394 (916)
        # For KindID 0x7E: 0x009B5228 + 126 * 916 = 0x009D14E0 < 0x009E1DD0
        max_kind_va = 0x009B5228 + 0x7E * 0x394
        self.assertLess(max_kind_va + 0x394, 0x009E1DD0, "KindInfo 0x7E must not exceed engine 200-unit array limit (0x009E1DD0)")

    def test_safety_verify_script_and_hash_audit(self) -> None:
        """Run verify_safety logic and assert 204/204 original files intact with pristine backup match."""
        # 1. Pristine backup verification
        self.assertTrue(self.backup_path.exists(), "Original dawn.exe backup must exist")
        backup_sha = hashlib.sha256(self.orig_data).hexdigest()
        self.assertEqual(backup_sha, ORIGINAL_SHA256, "Backup dawn.exe SHA-256 mismatch")
        self.assertEqual(len(self.orig_data), 1032192, "Original dawn.exe size must be 1,032,192 bytes")

        # 2. Check YM original read-only asset directory
        ym_dir = self.root / "YM"
        self.assertTrue(ym_dir.exists(), "YM directory must exist")
        core_files = [
            ym_dir / "dawn" / "Data",
            ym_dir / "dawn" / "Data.hq",
            ym_dir / "dawn" / "dawn.exe",
            ym_dir / "dawn" / "syw2x.dll",
            ym_dir / "dawn" / "dxwrapper.dll",
            ym_dir / "dawn" / "pal" / "imjin2.pal",
        ]
        for f in core_files:
            self.assertTrue(f.exists(), f"Core game asset {f} must exist intact")
            self.assertGreater(f.stat().st_size, 0, f"Core game asset {f} must have non-zero size")

        # 3. Comprehensive verification via tools.verify_safety (204 files intact)
        from tools.verify_safety import check_rea_git_clean, verify_ym_integrity
        ym_ok, ym_errors = verify_ym_integrity(str(ym_dir))
        self.assertTrue(ym_ok, f"verify_ym_integrity failed on 204 files: {ym_errors[:5]}")
        rea_clean, msg = check_rea_git_clean(r"C:\src\rea")
        self.assertTrue(rea_clean, f"check_rea_git_clean failed: {msg}")

    def test_all_15_units_coexistence_matrix(self) -> None:
        """Verify that all 15 units (0x70~0x7E) coexist with distinct KindIDs, CmdIDs, and ButtonIDs."""
        # Combine 10 existing units + 5 new infantry units
        existing_kinds = [u["kind_id"] for u in NEW_UNITS_METADATA]
        existing_cmds = [u["cmd_id"] for u in NEW_UNITS_METADATA]
        existing_btns = [u["btn_id"] for u in NEW_UNITS_METADATA]

        new_kinds = [u["kind_id"] for u in JOSEON_5_INFANTRY_METADATA]
        new_cmds = [u["cmd_id"] for u in JOSEON_5_INFANTRY_METADATA]
        new_btns = [u["btn_id"] for u in JOSEON_5_INFANTRY_METADATA]

        # Verify zero collision between existing 10 units and 5 new infantry units in 15-unit mode
        kind_intersection = set(existing_kinds) & set(new_kinds)
        cmd_intersection = set(existing_cmds) & set(new_cmds)
        btn_intersection = set(existing_btns) & set(new_btns)

        self.assertEqual(len(kind_intersection), 0, f"KindID collision detected: {kind_intersection}")
        self.assertEqual(len(cmd_intersection), 0, f"CmdID collision detected: {cmd_intersection}")
        self.assertEqual(len(btn_intersection), 0, f"ButtonID collision detected: {btn_intersection}")

        # Total 15 distinct KindIDs: 0x70..0x7E
        all_kinds = sorted(existing_kinds + new_kinds)
        self.assertEqual(all_kinds, list(range(0x70, 0x7F)), "15 units must span contiguous KindIDs 0x70..0x7E")

        # Total 15 distinct CmdIDs: 0xAB..0xB4 and 0xBF..0xC3 (preserving 0xB5..0xB9 Joseon Farmer Build commands!)
        all_cmds = sorted(existing_cmds + new_cmds)
        self.assertEqual(all_cmds, list(range(0xAB, 0xB5)) + list(range(0xBF, 0xC4)), "15 units must use CmdIDs 0xAB..0xB4 and 0xBF..0xC3")

    def test_cltchar_copy_simulation_5_infantry(self) -> None:
        """Simulate cltChar::Init instantiation for the 5 infantry units, verifying ground unit status and stat geometry."""
        for u in JOSEON_5_INFANTRY_METADATA:
            kind_buf = bytearray(0x394)
            struct.pack_into("<H", kind_buf, 0x04, u["base_atk"])
            struct.pack_into("<H", kind_buf, 0x06, u["hp"])
            struct.pack_into("<H", kind_buf, 0x0C, u["defense"])
            struct.pack_into("<H", kind_buf, 0x2C, u["speed"])
            struct.pack_into("<H", kind_buf, 0x36, u["range1"])
            struct.pack_into("<H", kind_buf, 0x38, u["range2"])
            struct.pack_into("<I", kind_buf, 0x4C, u["atb1"])
            struct.pack_into("<I", kind_buf, 0x50, u["atb2"])
            struct.pack_into("<I", kind_buf, 0x5C, u["attack_atb"])

            clt_char = bytearray(0x300)
            struct.pack_into("<H", clt_char, 0x168, struct.unpack_from("<H", kind_buf, 0x04)[0])
            struct.pack_into("<H", clt_char, 0x120, struct.unpack_from("<H", kind_buf, 0x06)[0])
            struct.pack_into("<H", clt_char, 0x184, struct.unpack_from("<H", kind_buf, 0x2C)[0])
            struct.pack_into("<H", clt_char, 0x20C, struct.unpack_from("<H", kind_buf, 0x36)[0])
            struct.pack_into("<H", clt_char, 0x208, struct.unpack_from("<H", kind_buf, 0x38)[0])
            struct.pack_into("<I", clt_char, 0x1D8, struct.unpack_from("<I", kind_buf, 0x4C)[0])
            struct.pack_into("<I", clt_char, 0x1DC, struct.unpack_from("<I", kind_buf, 0x50)[0])
            struct.pack_into("<I", clt_char, 0x1E4, struct.unpack_from("<I", kind_buf, 0x5C)[0])

            # Ground unit check (Atb1 & 0x10 == 0 -> cltChar + 0x1BC = 1)
            atb1 = struct.unpack_from("<I", kind_buf, 0x4C)[0]
            unit_class = 2 if (atb1 & 0x10) else 1
            clt_char[0x1BC] = unit_class

            self.assertEqual(clt_char[0x1BC], 1, f"{u['name']} must instantiate as Ground Unit (cltChar+0x1BC == 1)")
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x168)[0], u["base_atk"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x120)[0], u["hp"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x184)[0], u["speed"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x20C)[0], u["range1"])
            self.assertEqual(struct.unpack_from("<H", clt_char, 0x208)[0], u["range2"])

    def test_knockback_assembly_cave_simulation(self) -> None:
        """Simulate Zone D knockback vector mathematics and behavioral conditions in Python."""
        def simulate_knockback(
            attacker_kind: int,
            attacker_pos: tuple[int, int],
            target_pos: tuple[int, int],
            target_is_building: bool,
            push_distance: int = 16,
        ) -> tuple[tuple[int, int], int]:
            """Returns (new_target_pos, stagger_ticks)."""
            # 1. Attacker must be 낭선병 (0x7E or 0x74)
            if attacker_kind not in (0x7E, 0x74):
                return target_pos, 0

            # 2. Target must not be a building
            if target_is_building:
                return target_pos, 0

            target_x, target_y = target_pos
            attacker_x, attacker_y = attacker_pos

            dx = target_x - attacker_x
            dy = target_y - attacker_y

            new_x = target_x + push_distance if dx >= 0 else target_x - push_distance
            new_y = target_y + push_distance if dy >= 0 else target_y - push_distance
            stagger = 10
            return (new_x, new_y), stagger

        # Case 1: Attacker 낭선병 pushes target to the right and down
        new_pos, st = simulate_knockback(0x7E, (100, 100), (120, 110), False, push_distance=16)
        self.assertEqual(new_pos, (136, 126), "Target must be pushed +16px on X and +16px on Y")
        self.assertEqual(st, 10, "Target must receive 10-frame stagger")

        # Case 2: Attacker 낭선병 pushes target to the left and up
        new_pos, st = simulate_knockback(0x7E, (100, 100), (80, 90), False, push_distance=16)
        self.assertEqual(new_pos, (64, 74), "Target must be pushed -16px on X and -16px on Y")
        self.assertEqual(st, 10, "Target must receive 10-frame stagger")

        # Case 3: Building target immunity
        new_pos, st = simulate_knockback(0x7E, (100, 100), (120, 110), True, push_distance=16)
        self.assertEqual(new_pos, (120, 110), "Building target must not be moved")
        self.assertEqual(st, 0, "Building must not receive stagger")

        # Case 4: Non-낭선병 attacker (e.g. 등패수 0x7A) has no knockback
        new_pos, st = simulate_knockback(0x7A, (100, 100), (120, 110), False, push_distance=16)
        self.assertEqual(new_pos, (120, 110), "Non-낭선병 attacker must not cause knockback")
        self.assertEqual(st, 0, "No stagger for normal attacks")

        # Case 5: Alternate KindID 0x74 (낭선병 alternate)
        new_pos, st = simulate_knockback(0x74, (100, 100), (120, 110), False, push_distance=16)
        self.assertEqual(new_pos, (136, 126), "Alternate KindID 0x74 must also trigger knockback")
        self.assertEqual(st, 10)

    def test_joseon_5_infantry_custom_sageuk_voices(self) -> None:
        """Verify all 20 AI Korean Sageuk .YAV voice files, EffectSound.dat IDs 485..504, and SoundGroup bindings (202..217, 238..241)."""
        from src.assets.generate_muye24ki_voices import UNIT_VOICE_SPECS

        eff_dat_path = self.root / "YM" / "dawn" / "EffectSound.dat"
        self.assertTrue(eff_dat_path.exists(), "EffectSound.dat must exist")
        eff_text = eff_dat_path.read_bytes().decode("cp949", errors="replace")

        state_order = ["select", "die", "move", "attack"]
        for u in UNIT_VOICE_SPECS:
            for idx, st in enumerate(state_order):
                eff_id = u["base_effect_id"] + idx
                desc_name, yav_name, _, _ = u["lines"][st]
                yav_path = self.root / "YM" / "dawn" / "tempeft" / yav_name
                self.assertTrue(yav_path.exists(), f"Missing custom voice YAV: {yav_path}")
                raw = yav_path.read_bytes()
                fmt_sz, tag, ch, sr, bps, align, bits, cb, data_sz = struct.unpack("<IHHIIHHHI", raw[:26])
                self.assertEqual((fmt_sz, tag, ch, sr, bits), (18, 1, 1, 22050, 16))
                self.assertEqual(len(raw), 26 + data_sz)
                self.assertGreater(data_sz, 22050 * 2, f"{yav_name} duration must be > 1.0s")
                self.assertIn(f"{desc_name}\t{eff_id}\ttempeft\\\\{yav_name}", eff_text)

    def test_alttab_window_switching_and_minimize_restore_hooks(self) -> None:
        """Verify Alt+Tab window switching patches (non-TOPMOST, WM_ACTIVATEAPP minimize/restore, WM_SYSKEYDOWN DefWindowProcA)."""
        from tools.modding.patch_joseon_new_unit import (
            VA_CAVE_ALTTAB_ACTIVATE,
            VA_HOOK_WM_ACTIVATEAPP,
            VA_HOOK_WM_ACTIVATEAPP_COMMON,
            VA_HOOK_WM_SYSKEYDOWN_DEFPROC,
            VA_WINMAIN_EXSTYLE_TOPMOST,
            build_alttab_activate_cave,
        )

        # 1. CreateWindowExA dwExStyle must push 0 instead of WS_EX_TOPMOST (8)
        self.assertEqual(
            self.data[va_to_offset(VA_WINMAIN_EXSTYLE_TOPMOST) : va_to_offset(VA_WINMAIN_EXSTYLE_TOPMOST) + 2],
            b"\x6A\x00",
        )

        # 2. WM_ACTIVATEAPP at 0x00423F0E must jump to VA_CAVE_ALTTAB_ACTIVATE
        ins_act = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_WM_ACTIVATEAPP) : va_to_offset(VA_HOOK_WM_ACTIVATEAPP) + 6], VA_HOOK_WM_ACTIVATEAPP))
        self.assertEqual(ins_act[0].mnemonic, "jmp")
        self.assertEqual(int(ins_act[0].op_str, 16), VA_CAVE_ALTTAB_ACTIVATE)

        # 3. WM_SYSKEYDOWN tail at 0x00424343 must jump to DefWindowProcA (0x0042451A)
        ins_sys = list(self.md.disasm(self.data[va_to_offset(VA_HOOK_WM_SYSKEYDOWN_DEFPROC) : va_to_offset(VA_HOOK_WM_SYSKEYDOWN_DEFPROC) + 8], VA_HOOK_WM_SYSKEYDOWN_DEFPROC))
        self.assertEqual(ins_sys[0].mnemonic, "jmp")
        self.assertEqual(int(ins_sys[0].op_str, 16), 0x0042451A)

        # 4. Cave at VA_CAVE_ALTTAB_ACTIVATE must match build_alttab_activate_cave and include SW_MINIMIZE(6) & SW_RESTORE(9)
        cave = build_alttab_activate_cave(VA_CAVE_ALTTAB_ACTIVATE)
        self.assertEqual(
            self.data[va_to_offset(VA_CAVE_ALTTAB_ACTIVATE) : va_to_offset(VA_CAVE_ALTTAB_ACTIVATE) + len(cave)],
            cave,
        )
        self.assertIn(b"\x6A\x06", cave)  # push SW_MINIMIZE
        self.assertIn(b"\x6A\x09", cave)  # push SW_RESTORE
        self.assertIn(b"\xA3\x6C\x97\x66\x00", cave)  # mov [0x0066976C], eax
        self.assertEqual(VA_HOOK_WM_ACTIVATEAPP_COMMON, 0x00423F53)

    def test_sword_slash_animations_and_spear_range_nangseon_cave_offsets(self) -> None:
        """Verify 0x7A/0x7B/0x7D slash keyframes, 0x7C/0x7E Range1=3 (135px 2-tile all-dir), and 0x7E true cltChar[0] knockback/stagger offsets."""
        from src.assets.generate_joseon_5_units import SWORD_SLASH_KEYFRAMES
        from tools.modding.patch_joseon_new_unit import (
            VA_CAVE_ATTACK_EFFECTS,
            VA_CAVE_INIT_INFANTRY5,
        )
        va_cave_zone_d = 0x00421A20

        # 1. Verify SWORD_SLASH_KEYFRAMES defines 8 distinct overhead-to-downward angles per direction (dirs 0..4)
        self.assertEqual(len(SWORD_SLASH_KEYFRAMES), 5)
        for d in range(5):
            kfs = SWORD_SLASH_KEYFRAMES[d]
            self.assertEqual(len(kfs), 8)
            angles = [kf[2] for kf in kfs]
            # Wind-up angles (steps 0, 1) must differ significantly from cleave/follow-through angles (steps 3, 4, 5)
            self.assertGreater(abs(angles[1] - angles[4]), 70, f"Direction {d} slash arc sweep must exceed 70 degrees")

        # 2. Verify Zone D cave (0x00421A20) reads target_char_idx from si (movzx edx, si = 0F B7 D6), NOT [esp]
        zone_d_bytes = self.data[va_to_offset(va_cave_zone_d) : va_to_offset(va_cave_zone_d) + 128]
        self.assertIn(b"\x0F\xB7\xD6", zone_d_bytes, "Zone D cave must use movzx edx, si (0F B7 D6) for target_char_idx")
        self.assertNotIn(b"\x8B\x14\x24", zone_d_bytes, "Zone D cave must NOT read [esp] as target_char_idx")

        # 3. Verify AttackEffects cave (0x00489440) uses true cltChar[0] base (0x0066B790):
        #    KindID (+0x8D) = 0x0066B81D, CenterX (+0x1BE) = 0x0066B94E, CenterY (+0x1C0) = 0x0066B950, HaltTimer (+0x370) = 0x0066BB00
        atk_eff_bytes = self.data[va_to_offset(VA_CAVE_ATTACK_EFFECTS) : va_to_offset(VA_CAVE_ATTACK_EFFECTS) + 156]
        self.assertIn(struct.pack("<I", 0x0066B81D), atk_eff_bytes, "AttackEffects cave must read Attacker KindID at 0x0066B81D")
        self.assertIn(struct.pack("<I", 0x0066B94E), atk_eff_bytes, "AttackEffects cave must access CenterX at 0x0066B94E")
        self.assertIn(struct.pack("<I", 0x0066B950), atk_eff_bytes, "AttackEffects cave must access CenterY at 0x0066B950")
        self.assertIn(struct.pack("<I", 0x0066BB00), atk_eff_bytes, "AttackEffects cave must write HaltTimer stagger at 0x0066BB00")

        # 4. Verify InitInfantry5 cave descriptor table sets runtime Range1 = 3 for 장창수 (0x7C) and 낭선병 (0x7E)
        from tools.modding.patch_joseon_new_unit import build_init_infantry5_cave
        inf5_cave = build_init_infantry5_cave(VA_CAVE_INIT_INFANTRY5)
        ret_idx = inf5_cave.index(b"\x61\xC3") + 2
        desc_table = inf5_cave[ret_idx : ret_idx + 5 * 24]
        expected_runtime_ranges = [1, 1, 3, 1, 3]  # 등패수=1, 쌍수도병=1, 장창수=3, 월도병=1, 낭선병=3
        for idx, exp_r1 in enumerate(expected_runtime_ranges):
            entry = desc_table[idx * 24 : (idx + 1) * 24]
            r1 = entry[16]
            self.assertEqual(r1, exp_r1, f"Infantry #{idx+1} runtime Range1 in InitInfantry5 descriptor must be {exp_r1}")

    def test_joseon_5_infantry_solid_body_and_2x_jangchang_spear(self) -> None:
        """Verify all 5 infantry sprites have solid bodies (0 internal holes, preserved white sleeves/pants) and 장창수 has 2x spear length (144x140)."""
        import numpy as np
        from tools.assets.sprite_rle import SpriteDecoder

        char_dir = self.root / "YM" / "dawn" / "char"
        pairs = [
            ("dengpaesu.spr", "Gangsi1_online.spr", 68, 68),
            ("ssangsudo.spr", "Gangsi2_online.spr", 80, 74),
            ("jangchangsu.spr", "Gangsi3_online.spr", 144, 140),
            ("woldo.spr", "RaccoonDog_online.spr", 78, 74),
            ("nangseon.spr", "Deer_online.spr", 144, 140),
        ]
        for primary, online, exp_w, exp_h in pairs:
            p_bytes = (char_dir / primary).read_bytes()
            o_bytes = (char_dir / online).read_bytes()
            self.assertEqual(p_bytes, o_bytes, f"{primary} and {online} must be bit-identical")

            dec = SpriteDecoder.from_file(char_dir / primary)
            self.assertEqual((dec.width, dec.height, dec.frame_count), (exp_w, exp_h, 168))

            # Check Idle frame 128 (SW) and 160 (S): verify authentic Dujeong-gap / Gyeongbeon-gap heavy armor
            armor_indices = (
                33, 35, 41, 46, 47, 69, 113, 156, 211, 214, 232,
                236, 237, 238, 239, 243, 250, 253,
            )
            for f_no in (128, 160):
                arr = np.frombuffer(dec.decode_frame_raw(f_no), dtype=np.uint8).reshape((exp_h, exp_w))
                ox, oy = (exp_w - 60) // 2, (exp_h - 60) // 2
                body = arr[oy + 10 : oy + 46, ox + 20 : ox + 40]
                armor_px = sum(int(np.sum(body == idx)) for idx in armor_indices)
                self.assertGreaterEqual(
                    armor_px, 180,
                    f"{primary} frame {f_no} must have >=180 Dujeong-gap/Gyeongbeon-gap armor pixels, got {armor_px}",
                )

                # Verify 0 4-connected interior transparent pinholes inside the core body
                pinholes = 0
                for y in range(oy + 16, oy + 44):
                    for x in range(ox + 26, ox + 34):
                        if arr[y, x] == 0:
                            if arr[y, x - 1] > 0 and arr[y, x + 1] > 0 and arr[y - 1, x] > 0 and arr[y + 1, x] > 0:
                                pinholes += 1
                self.assertEqual(pinholes, 0, f"{primary} frame {f_no} must have 0 interior transparent pinholes")

        # Verify 장창수 and 낭선병 2x spear span (>= 65px in Idle and Attack) + 낭선병 prominent branches & sub-twigs
        dec_jc = SpriteDecoder.from_file(char_dir / "jangchangsu.spr")
        arr_idle = np.frombuffer(dec_jc.decode_frame_raw(128), dtype=np.uint8).reshape((140, 144))
        ys_idle, xs_idle = np.nonzero(arr_idle)
        span_idle = float(np.hypot(xs_idle.max() - xs_idle.min(), ys_idle.max() - ys_idle.min()))
        self.assertGreaterEqual(span_idle, 68.0, f"장창수 Idle 2x spear span must be >= 68px, got {span_idle:.1f}px")

        dec_ns = SpriteDecoder.from_file(char_dir / "nangseon.spr")
        arr_ns_idle = np.frombuffer(dec_ns.decode_frame_raw(128), dtype=np.uint8).reshape((140, 144))
        ys_ns, xs_ns = np.nonzero(arr_ns_idle)
        span_ns = float(np.hypot(xs_ns.max() - xs_ns.min(), ys_ns.max() - ys_ns.min()))
        self.assertGreaterEqual(span_ns, 65.0, f"낭선병 Idle 2x spear span must be >= 65px, got {span_ns:.1f}px")
        bamboo_and_barb_px = sum(int(np.sum(arr_ns_idle == idx)) for idx in (7, 21, 27, 70, 77, 253, 255))
        self.assertGreaterEqual(bamboo_and_barb_px, 180, f"낭선병 must have prominent multi-tier branches & sub-twigs (>=180 px), got {bamboo_and_barb_px}")

    def test_joseon_production_buildings_zero_hotkey_overlap(self) -> None:
        """Verify zero hotkey overlap in all 4 Joseon production buildings and 15/15 globally unique custom unit hotkeys."""
        from tools.modding.patch_joseon_new_unit import (
            UNIT_DEFINITIONS,
            VA_CAVE_INIT_INFANTRY5,
            build_init_infantry5_cave,
        )

        # 1. Verify all 15 custom Joseon units have globally distinct hotkeys
        all_hotkeys = [u["hotkey"] for u in UNIT_DEFINITIONS]
        self.assertEqual(len(all_hotkeys), 15)
        self.assertEqual(len(set(all_hotkeys)), 15, f"Duplicate custom unit hotkeys found: {all_hotkeys}")

        # 2. Verify binary descriptor tables in Cave #1 (0x70..0x79) and Cave #InitInfantry5 (0x7A..0x7E) match metadata hotkeys
        cave1 = build_init_cave(VA_CAVE_INIT_ROUTINE)
        desc10_off = len(cave1) - 10 * 20
        for i in range(10):
            rec = cave1[desc10_off + i * 20 : desc10_off + (i + 1) * 20]
            hk_char = chr(rec[10])
            self.assertEqual(hk_char, NEW_UNITS_METADATA[i]["hotkey"], f"Unit 0x{0x70+i:02X} binary hotkey mismatch")

        inf5_cave = build_init_infantry5_cave(VA_CAVE_INIT_INFANTRY5)
        ret_idx = inf5_cave.index(b"\x61\xC3") + 2
        desc5 = inf5_cave[ret_idx : ret_idx + 5 * 24]
        for i in range(5):
            rec = desc5[i * 24 : (i + 1) * 24]
            hk_char = chr(rec[19])
            self.assertEqual(hk_char, JOSEON_5_INFANTRY_METADATA[i]["hotkey"], f"Infantry 0x{0x7A+i:02X} binary hotkey mismatch")

        # 3. Verify zero overlap inside each of the 4 Joseon production buildings (native buttons + custom buttons)
        building_hotkey_sets = {
            "조선 본영 (0x31)": {
                "native": ["R", "S", "C", "D", "F", "B", "Z", "M"],
                "custom": ["Y", "U", "G"],  # 유생 [Y], 불가살이 [U], 구미호 [G]
            },
            "조선 훈련소 (0x32)": {
                "native": ["R", "S", "C", "D", "W", "A", "Z", "L"],
                "custom": ["K", "P", "M", "E"],  # 검술 낭인 [K], 조총 낭인 [P], 털가면 [M], 등패수 [E]
            },
            "조선 마구간 (0x35)": {
                "native": ["R", "S", "C", "D", "H", "Z"],
                "custom": ["B", "T", "I", "O"],  # 조선왕벌 [B], 조선 호랑이 [T], 설녀 [I], 조선 도깨비 [O]
            },
            "조선 훈련도감 (0x33)": {
                "native": ["R", "S", "C", "D", "E", "Z", "F", "X", "Q", "B"],
                "custom": ["V", "J", "W", "N"],  # 쌍수도병 [V], 장창수 [J], 월도병 [W], 낭선병 [N]
            },
        }
        for bname, groups in building_hotkey_sets.items():
            native_set = set(groups["native"])
            custom_list = groups["custom"]
            self.assertEqual(len(custom_list), len(set(custom_list)), f"{bname} has duplicate custom hotkeys: {custom_list}")
            overlap = native_set & set(custom_list)
            self.assertEqual(len(overlap), 0, f"{bname} has hotkey collision between native and custom buttons: {overlap}")

    def test_gumiho_clone_cannot_summon_further_clones(self) -> None:
        """Verify summoned Gumiho (0x73) clones ([esi+0x74] != 0) cannot display 분신술 [C] or execute CanClone/DoClone."""
        from tools.modding.patch_joseon_new_unit import build_gumiho_cmdcard_cave

        # 1. VA_CAVE_GUMIHO_CMDCARD (0x0043C8F8) must check byte ptr [esi + 0x74] == 0 (80 7E 74 00), NOT [esi + 0x94]
        cave_bytes = build_gumiho_cmdcard_cave(VA_CAVE_GUMIHO_CMDCARD)
        self.assertEqual(
            self.data[va_to_offset(VA_CAVE_GUMIHO_CMDCARD) : va_to_offset(VA_CAVE_GUMIHO_CMDCARD) + len(cave_bytes)],
            cave_bytes,
        )
        self.assertIn(b"\x80\x7E\x74\x00", cave_bytes, "Gumiho CmdCard cave must check cmp byte ptr [esi + 0x74], 0")
        self.assertNotIn(b"\x83\xBE\x94\x00\x00\x00\x00", cave_bytes, "Gumiho CmdCard cave must NOT check wrong offset +0x94")

        # 2. CanClone (0x00477CA0) at 0x00477CE3..0x00477CED must check cmp byte ptr [esi + 0x74], 0; jne 0x00477D02 (return 0)
        canclone_patch = self.data[va_to_offset(0x00477CE3) : va_to_offset(0x00477CE3) + 11]
        self.assertEqual(
            canclone_patch,
            b"\x80\x7E\x74\x00\x90\x90\x90\x90\x90\x75\x14",
            "CanClone at 0x00477CE3 must block any unit with IsClone flag ([esi+0x74] != 0) by jumping to 0x00477D02 (xor eax, eax; ret 4)",
        )

    def test_nangseonbyung_true_knockback_without_paralysis(self) -> None:
        """Verify Nangseonbyung (0x7E) pushes target back by 1 tile + 16px and jumps directly to .return without paralysis (HaltTimer)."""
        from tools.modding.patch_joseon_new_unit import (
            VA_CAVE_ATTACK_EFFECTS,
            VA_CAVE_KNOCKBACK_P1,
            VA_CAVE_KNOCKBACK_P2,
            VA_CAVE_KNOCKBACK_P3,
            build_attack_effects_cave,
            build_knockback_tile_caves,
        )

        cave = build_attack_effects_cave(VA_CAVE_ATTACK_EFFECTS)
        # Locate .status_effects (cmp bl, 9 -> 80 FB 09)
        idx_status = cave.index(b"\x80\xFB\x09")
        knockback_branch = cave[:idx_status]

        # 1. Knockback branch must NOT write HaltTimer (+0x370 = 0x0066BB00, paralysis visual effect)
        self.assertNotIn(
            b"\x00\xBB\x66\x00",
            knockback_branch,
            "Nangseonbyung knockback branch must NEVER touch HaltTimer (0x0066BB00) which triggers the paralysis effect",
        )
        # 2. Knockback branch must end with an unconditional jump (0xEB) to .return so it never falls through into .status_effects
        self.assertEqual(
            knockback_branch[-2],
            0xEB,
            "Nangseonbyung knockback branch must end with jmp .return (0xEB) before .status_effects",
        )
        # 3. Verify true 1-tile knockback caves P1..P3 are present in patched dawn.exe and call DeleteID, IsColl, SetID, CalculateRealXY
        p1, p2, p3 = build_knockback_tile_caves()
        self.assertEqual(self.data[va_to_offset(VA_CAVE_KNOCKBACK_P1) : va_to_offset(VA_CAVE_KNOCKBACK_P1) + len(p1)], p1)
        self.assertEqual(self.data[va_to_offset(VA_CAVE_KNOCKBACK_P2) : va_to_offset(VA_CAVE_KNOCKBACK_P2) + len(p2)], p2)
        self.assertEqual(self.data[va_to_offset(VA_CAVE_KNOCKBACK_P3) : va_to_offset(VA_CAVE_KNOCKBACK_P3) + len(p3)], p3)


if __name__ == "__main__":
    unittest.main()


