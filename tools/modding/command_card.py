"""
tools.modding.command_card
~~~~~~~~~~~~~~~~~~~~~~~~~~
Command card button injector and code-cave hook decoder for Imjinrok 2+: Dawn.
Decodes the 6 Dawn code cave hooks and safely injects new unit production/skill
button hooks into the 917 bytes of available zero-slack space (0x004e4c6b–0x004e4fff).
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import capstone
except ImportError:
    capstone = None

from tools.modding.binary_patcher import (
    EXPECTED_BINARY_SIZE,
    IMAGE_BASE,
    PatchResult,
    _assert_safe_target_path,
)

# Known Dawn Mod Code Cave Range
DAWN_CAVE_START_VA = 0x004E4AE6
DAWN_CAVE_END_VA = 0x004E4C6A
DAWN_CAVE_SIZE = 389

# Available Slack Space in .text section
SLACK_START_VA = 0x004E4C70  # 16-byte aligned start in slack
SLACK_END_VA = 0x004E4FF0    # Safe margin before .rdata at 0x004E5000
TOTAL_SLACK_BYTES = 917       # 0x004E4C6B to 0x004E5000

# Address of CCommandCard::AddButton in engine
ADD_BUTTON_VA = 0x00412000

# Known Dawn Hook Sites
DAWN_HOOKS_METADATA = [
    {
        "hook_id": 1,
        "hook_va": 0x00480FF2,
        "cave_va": 0x004E4B09,
        "target_unit_id": 74,
        "target_unit_name": "조선 훈련도감 / 장수",
        "sprite": "char\\generalk13.spr",
        "injected_buttons": [{"slot": 6, "cmd_id": 0x6F, "description": "신규 공성 병기 (대장군포/파쇄차) 생산"}],
        "logic": "Unconditional: calls original AddButton(4, 0x6e), then adds slot 6, cmdId 0x6f.",
    },
    {
        "hook_id": 2,
        "hook_va": 0x00483F6F,
        "cave_va": 0x004E4AE6,
        "target_unit_id": 60,
        "target_unit_name": "조선 본영 / 이순신",
        "sprite": "char\\generalk12.spr",
        "injected_buttons": [{"slot": 8, "cmd_id": 0x69, "description": "신규 장수 등용 (김덕령/김시민) 버튼"}],
        "logic": "Unconditional: calls original AddButton(1, 0xc5), then adds slot 8, cmdId 0x69.",
    },
    {
        "hook_id": 3,
        "hook_va": 0x00484A1F,
        "cave_va": 0x004E4B4E,
        "target_unit_id": 55,
        "target_unit_name": "일본 비행체제작소",
        "sprite": "char\\tflyj.spr",
        "injected_buttons": [{"slot": 10, "cmd_id": 0x114, "description": "고급 무기 / 대공 화전 연구 업그레이드"}],
        "logic": "Faction check: calls sub_0047f7f0(4); if result == edi, adds slot 10, cmdId 0x114.",
    },
    {
        "hook_id": 4,
        "hook_va": 0x004879BF,
        "cave_va": 0x004E4BF2,
        "target_unit_id": 95,
        "target_unit_name": "조선 조선소",
        "sprite": "char\\tshipk.spr",
        "injected_buttons": [{"slot": 8, "cmd_id": 0x28, "description": "판옥선 (Panokseon) 특수 전함 건조"}],
        "logic": "Condition: [esi+0x6f8] == 0x19 and [esi+0x94] == 0 -> adds slot 8, cmdId 0x28.",
    },
    {
        "hook_id": 5,
        "hook_va": 0x004880BF,
        "cave_va": 0x004E4C2E,
        "target_unit_id": 86,
        "target_unit_name": "명나라 조선소",
        "sprite": "char\\ashipc.spr",
        "injected_buttons": [{"slot": 7, "cmd_id": 0x27, "description": "명나라 공격선 / 거북선 건조"}],
        "logic": "Condition: [esi+0x6f8] == 0x10 and [esi+0x94] == 0 -> adds slot 7, cmdId 0x27.",
    },
    {
        "hook_id": 6,
        "hook_va": 0x004881E8,
        "cave_va": 0x004E4B84,
        "target_unit_id": 99,
        "target_unit_name": "명나라 호선 / 판옥선",
        "sprite": "char\\pshipc.spr",
        "injected_buttons": [
            {"slot": 5, "cmd_id": 0x2D, "description": "명나라 사선 (Attack Ship) 건조"},
            {"slot": 6, "cmd_id": 0x36, "description": "명나라 호선 (Armored Battleship) 연구/건조"},
        ],
        "logic": "Adds slot 5, cmdId 0x2d. If player research table 0x009598d4[player*4] == 1, adds slot 6, cmdId 0x36.",
    },
]

# Convenient Building Preset Names to Hook Sites
BUILDING_HOOK_PRESETS: Dict[str, int] = {
    "조선 훈련도감": 0x00480FF2,
    "훈련도감": 0x00480FF2,
    "ADVBARRACKK": 0x00480FF2,
    "조선 본영": 0x00483F6F,
    "본영": 0x00483F6F,
    "HQK": 0x00483F6F,
    "일본 비행체제작소": 0x00484A1F,
    "비행체제작소": 0x00484A1F,
    "TFLYJ": 0x00484A1F,
    "조선 조선소": 0x004879BF,
    "조선소": 0x004879BF,
    "SHIPYARDK": 0x004879BF,
    "명나라 조선소": 0x004880BF,
    "명 조선소": 0x004880BF,
    "SHIPYARDC": 0x004880BF,
    "명나라 호선": 0x004881E8,
    "호선": 0x004881E8,
    "PSHIPC": 0x004881E8,
}


@dataclass
class CaveInjectionInfo:
    """Details of an injected command card button hook in slack space."""
    hook_site_va: int
    cave_va: int
    slot: int
    cmd_id: int
    requirements: List[int]
    shellcode_len: int
    file_offset: int


class CommandCardInjector:
    """Injects and manages command card button hooks in PE slack space."""

    def __init__(self, binary_path: str) -> None:
        self.binary_path = os.path.abspath(binary_path)
        _assert_safe_target_path(self.binary_path)

        if not os.path.isfile(self.binary_path):
            raise FileNotFoundError(f"Binary file not found: {self.binary_path}")

        file_size = os.path.getsize(self.binary_path)
        if file_size != EXPECTED_BINARY_SIZE:
            raise ValueError(
                f"Binary size {file_size} != expected {EXPECTED_BINARY_SIZE} bytes."
            )

    def find_available_slack(self, required_bytes: int = 36) -> Tuple[int, int]:
        """Scan .text slack space (0x000e4c6b–0x000e5000) for consecutive zero bytes.

        Returns (cave_va, file_offset).
        """
        with open(self.binary_path, "rb") as f:
            data = f.read()

        slack_start_off = SLACK_START_VA - IMAGE_BASE
        slack_end_off = SLACK_END_VA - IMAGE_BASE

        consecutive = 0
        match_start = -1
        for off in range(slack_start_off, slack_end_off):
            if data[off] == 0:
                if consecutive == 0:
                    match_start = off
                consecutive += 1
                if consecutive >= required_bytes:
                    cave_va = match_start + IMAGE_BASE
                    return cave_va, match_start
            else:
                consecutive = 0
                match_start = -1

        raise RuntimeError(
            f"Not enough contiguous slack space available ({required_bytes} bytes requested) in .text padding."
        )

    def assemble_button_hook(
        self,
        cave_va: int,
        hook_site_va: int,
        slot: int,
        cmd_id: int,
        requirements: Optional[List[int]] = None,
        replaced_call_va: int = ADD_BUTTON_VA,
    ) -> bytes:
        """Assemble x86 machine code for injecting a new command card button.

        Payload structure:
        1. call replaced_call_va (e.g. call 0x00412000)
        2. push req6..req1 (default 0)
        3. push cmd_id (imm8 or imm32)
        4. push slot (0..11)
        5. mov ecx, esi (this pointer = unit object)
        6. call 0x00412000 (CCommandCard::AddButton)
        7. jmp (hook_site_va + 5) (resume normal flow)
        """
        if not (0 <= slot <= 11):
            raise ValueError(f"Command card slot must be 0..11 (requested {slot}). Engine supports max 12 buttons.")

        if requirements is None:
            requirements = [0, 0, 0, 0, 0, 0]
        elif len(requirements) < 6:
            requirements = requirements + [0] * (6 - len(requirements))

        code = bytearray()

        # 1. Execute replaced original call: e8 <disp32>
        disp1 = replaced_call_va - (cave_va + len(code) + 5)
        code.append(0xE8)
        code.extend(struct.pack("<i", disp1))

        # 2. Push 6 requirement IDs (req6 down to req1)
        for r in reversed(requirements[:6]):
            if -128 <= r <= 127:
                code.extend([0x6A, r & 0xFF])
            else:
                code.append(0x68)
                code.extend(struct.pack("<I", r & 0xFFFFFFFF))

        # 3. Push command ID
        if 0 <= cmd_id <= 127:
            code.extend([0x6A, cmd_id & 0xFF])
        else:
            code.append(0x68)
            code.extend(struct.pack("<I", cmd_id & 0xFFFFFFFF))

        # 4. Push button slot index
        code.extend([0x6A, slot & 0xFF])

        # 5. mov ecx, esi
        code.extend([0x8B, 0xCE])

        # 6. call CCommandCard::AddButton (0x00412000)
        disp2 = ADD_BUTTON_VA - (cave_va + len(code) + 5)
        code.append(0xE8)
        code.extend(struct.pack("<i", disp2))

        # 7. jmp back to resume normal execution: jmp (hook_site_va + 5)
        return_va = hook_site_va + 5
        disp_return = return_va - (cave_va + len(code) + 5)
        code.append(0xE9)
        code.extend(struct.pack("<i", disp_return))

        return bytes(code)

    def inject_button(
        self,
        target_building_or_va: Union[int, str],
        slot: int,
        cmd_id: int,
        requirements: Optional[List[int]] = None,
        custom_cave_va: Optional[int] = None,
    ) -> PatchResult:
        """Inject a command button hook at target hook site using available slack space."""
        # Resolve target hook site VA
        if isinstance(target_building_or_va, int):
            hook_site_va = target_building_or_va
        elif str(target_building_or_va).startswith("0x") or str(target_building_or_va).startswith("0X"):
            hook_site_va = int(str(target_building_or_va), 16)
        elif str(target_building_or_va).isdigit():
            hook_site_va = int(str(target_building_or_va))
        else:
            # Check presets
            preset_key = str(target_building_or_va).strip()
            if preset_key in BUILDING_HOOK_PRESETS:
                hook_site_va = BUILDING_HOOK_PRESETS[preset_key]
            else:
                # Substring search in presets
                matched = None
                for k, va in BUILDING_HOOK_PRESETS.items():
                    if preset_key in k:
                        matched = va
                        break
                if matched is not None:
                    hook_site_va = matched
                else:
                    raise KeyError(
                        f"Unknown building preset '{preset_key}'. "
                        f"Available presets: {list(BUILDING_HOOK_PRESETS.keys())}"
                    )

        with open(self.binary_path, "rb") as f:
            bin_data = bytearray(f.read())

        hook_offset = hook_site_va - IMAGE_BASE
        old_hook_bytes = bytes(bin_data[hook_offset : hook_offset + 5])

        # Find slack location
        dummy_len = 36
        if custom_cave_va is not None:
            cave_va = custom_cave_va
            cave_offset = cave_va - IMAGE_BASE
        else:
            cave_va, cave_offset = self.find_available_slack(dummy_len)

        # Assemble payload
        payload = self.assemble_button_hook(
            cave_va=cave_va,
            hook_site_va=hook_site_va,
            slot=slot,
            cmd_id=cmd_id,
            requirements=requirements,
        )

        # Write payload to slack
        bin_data[cave_offset : cave_offset + len(payload)] = payload

        # Assemble jmp to cave at hook site: e9 <disp32>
        disp_to_cave = cave_va - (hook_site_va + 5)
        new_hook_bytes = bytes([0xE9]) + struct.pack("<i", disp_to_cave)
        bin_data[hook_offset : hook_offset + 5] = new_hook_bytes

        if len(bin_data) != EXPECTED_BINARY_SIZE:
            raise RuntimeError(
                f"Binary size integrity violated: {len(bin_data)} != {EXPECTED_BINARY_SIZE}"
            )

        with open(self.binary_path, "wb") as f:
            f.write(bin_data)

        return PatchResult(
            success=True,
            unit_name=str(target_building_or_va),
            unit_index=slot,
            stat_name="command_card_button",
            old_value=f"Hook at 0x{hook_site_va:08x}",
            new_value=f"cmd_id=0x{cmd_id:x}, slot={slot}, cave_va=0x{cave_va:08x}",
            virtual_address=hook_site_va,
            file_offset=hook_offset,
            old_bytes=old_hook_bytes,
            new_bytes=new_hook_bytes,
            message=(
                f"Successfully injected button slot {slot} (cmd_id 0x{cmd_id:x}) "
                f"at hook VA 0x{hook_site_va:08x} -> Cave VA 0x{cave_va:08x} ({len(payload)} bytes)"
            ),
        )


def decode_cave_hooks(binary_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Decode and inspect the 6 Dawn mod code cave hooks from binary or specifications."""
    results = []
    bin_data = None
    if binary_path and os.path.isfile(binary_path):
        with open(binary_path, "rb") as f:
            bin_data = f.read()

    for item in DAWN_HOOKS_METADATA:
        hook_info = dict(item)
        hook_va = item["hook_va"]
        hook_off = hook_va - IMAGE_BASE
        if bin_data is not None and hook_off + 5 <= len(bin_data):
            hook_bytes = bin_data[hook_off : hook_off + 5]
            hook_info["current_opcode"] = hook_bytes.hex()
            if hook_bytes[0] == 0xE9:
                disp = struct.unpack("<i", hook_bytes[1:5])[0]
                target = hook_va + 5 + disp
                hook_info["hooked"] = True
                hook_info["actual_cave_target"] = f"0x{target:08x}"
            else:
                hook_info["hooked"] = False
                hook_info["actual_cave_target"] = None
        results.append(hook_info)

    return results


def inject_command_card_button(
    binary_path: str,
    target_building_or_va: Union[int, str],
    slot: int,
    cmd_id: int,
    requirements: Optional[List[int]] = None,
) -> PatchResult:
    """Convenience top-level functional API for injecting a command card button."""
    injector = CommandCardInjector(binary_path)
    return injector.inject_button(target_building_or_va, slot, cmd_id, requirements)
