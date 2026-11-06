"""
tools.modding.binary_patcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Safe PE binary patcher for Imjinrok 2+: Dawn executables.
Modifies movement speed, HP, MP, attack power, attack delay, range, defense,
and resource costs in-place without corrupting PE headers, sections, or alignments.
Strictly safeguards original source binaries from modification.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import struct
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

try:
    import capstone
except ImportError:
    capstone = None

from tools.modding.unit_catalog import UnitCatalog, load_unit_catalog

EXPECTED_BINARY_SIZE = 1_032_192  # Exactly 0xFC000 bytes
IMAGE_BASE = 0x00400000

# Mapping of stat aliases to argument index in UnitDef::Init(54 args)
# 0 is pushed last, 53 is pushed first
STAT_TO_ARG: Dict[str, int] = {
    "speed": 29,
    "move_speed": 29,
    "move_speed_base": 29,
    "base_speed": 29,
    "speed_fast": 30,
    "move_speed_fast": 30,
    "running_speed": 30,
    "hp": 5,
    "max_hp": 5,
    "health": 5,
    "mp": 6,
    "max_mp": 6,
    "mana": 6,
    "build_delay": 11,
    "build_time": 11,
    "delay": 12,
    "attack_delay": 12,
    "attack_speed": 12,
    "cost_rice": 16,
    "rice": 16,
    "cost_potato": 17,
    "potato": 17,
    "cost_money": 18,
    "money": 18,
    "gold": 18,
    "defense": 20,
    "armor": 20,
    "sight": 24,
    "sight_range": 24,
    "range": 25,
    "attack_range": 25,
    "attack": 26,
    "attack_power": 26,
    "damage": 26,
    "tech": 34,
    "tech_requirements": 34,
}


@dataclass
class PatchResult:
    """Detailed result of a binary patch operation."""
    success: bool
    unit_name: str
    unit_index: int
    stat_name: str
    old_value: Any
    new_value: Any
    virtual_address: int
    file_offset: int
    old_bytes: bytes
    new_bytes: bytes
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "unit_name": self.unit_name,
            "unit_index": self.unit_index,
            "stat_name": self.stat_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "virtual_address": f"0x{self.virtual_address:08x}",
            "file_offset": f"0x{self.file_offset:06x}",
            "old_bytes": self.old_bytes.hex(),
            "new_bytes": self.new_bytes.hex(),
            "message": self.message,
        }


def _assert_safe_target_path(binary_path: str) -> None:
    """Ensure we never write to the original YM source directory."""
    abs_path = os.path.abspath(binary_path)
    # Check normalized segments
    parts = os.path.normpath(abs_path).lower().split(os.sep)
    if "ym" in parts and ("dawn.exe" in parts or "usemap.exe" in parts or "map editor.exe" in parts):
        raise PermissionError(
            f"REFUSING TO MODIFY ORIGINAL SOURCE BINARY: {abs_path}\n"
            "All game files in YM are strictly read-only.\n"
            "Please create a working copy (e.g. at a temporary path) and patch the copy."
        )


class BinaryPatcher:
    """Safe in-place PE binary patcher for Dawn binaries."""

    def __init__(self, binary_path: str, catalog: Optional[UnitCatalog] = None) -> None:
        self.binary_path = os.path.abspath(binary_path)
        _assert_safe_target_path(self.binary_path)

        if not os.path.isfile(self.binary_path):
            raise FileNotFoundError(f"Binary file not found: {self.binary_path}")

        file_size = os.path.getsize(self.binary_path)
        if file_size != EXPECTED_BINARY_SIZE:
            raise ValueError(
                f"Binary size {file_size} bytes does not match expected {EXPECTED_BINARY_SIZE} bytes."
            )

        self.catalog = catalog or load_unit_catalog()
        if capstone is not None:
            self._cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        else:
            self._cs = None

    def _get_call_pushes(self, bin_bytes: bytes, call_offset: int) -> List[Tuple[int, bytes, str, Any]]:
        """Extract the 54 pushes immediately preceding call 0x0049baa0."""
        if self._cs is None:
            # Fallback naive scan if capstone not present
            return self._fallback_get_pushes(bin_bytes, call_offset)

        start_offset = max(0x1000, call_offset - 400)
        start_va = IMAGE_BASE + start_offset
        chunk = bin_bytes[start_offset:call_offset]
        insns = list(self._cs.disasm(chunk, start_va))

        pushes = []
        for ins in reversed(insns):
            if ins.mnemonic == "push":
                # Calculate int val if possible
                val_raw = ins.op_str.strip()
                try:
                    val = int(val_raw, 16) if val_raw.startswith("0x") else int(val_raw)
                except ValueError:
                    val = val_raw
                pushes.append((ins.address, bytes(ins.bytes), ins.op_str, val))
                if len(pushes) == 54:
                    break
            elif ins.mnemonic in ("ret",) and len(pushes) >= 40:
                break

        pushes.reverse()
        return pushes

    def _fallback_get_pushes(self, bin_bytes: bytes, call_offset: int) -> List[Tuple[int, bytes, str, Any]]:
        """Fallback push extractor using raw opcode inspection."""
        pushes = []
        off = call_offset - 1
        while off >= max(0x1000, call_offset - 350) and len(pushes) < 54:
            # Check 6a <imm8>
            if off - 1 >= 0 and bin_bytes[off - 1] == 0x6A:
                imm8 = struct.unpack("b", bin_bytes[off : off + 1])[0]
                ins_va = IMAGE_BASE + (off - 1)
                pushes.append((ins_va, bin_bytes[off - 1 : off + 1], str(imm8), imm8))
                off -= 2
                continue
            # Check 68 <imm32>
            if off - 4 >= 0 and bin_bytes[off - 4] == 0x68:
                imm32 = struct.unpack("<I", bin_bytes[off - 3 : off + 1])[0]
                ins_va = IMAGE_BASE + (off - 4)
                pushes.append((ins_va, bin_bytes[off - 4 : off + 1], hex(imm32), imm32))
                off -= 5
                continue
            # Check 50..57 (push reg, e.g. 56 = push esi)
            if 0x50 <= bin_bytes[off] <= 0x57:
                reg_names = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"]
                reg = reg_names[bin_bytes[off] - 0x50]
                ins_va = IMAGE_BASE + off
                pushes.append((ins_va, bin_bytes[off : off + 1], reg, reg))
                off -= 1
                continue
            off -= 1

        pushes.reverse()
        return pushes

    def patch_unit_stat(
        self,
        unit_identifier: Union[int, str],
        stat_name: str,
        new_value: int,
    ) -> PatchResult:
        """Patch a unit's stat directly in the binary without modifying PE headers."""
        unit = self.catalog.get_unit(unit_identifier)
        if unit is None:
            raise KeyError(f"Unit not found in catalog: {unit_identifier}")

        stat_key = stat_name.lower().strip()
        if stat_key not in STAT_TO_ARG:
            raise ValueError(
                f"Unsupported stat '{stat_name}'. Supported stats: {sorted(list(STAT_TO_ARG.keys()))}"
            )

        target_arg = STAT_TO_ARG[stat_key]
        call_off_str = unit.get("call_file_offset")
        if not call_off_str:
            raise ValueError(f"Unit {unit['korean_name']} missing call_file_offset in catalog.")
        call_offset = int(call_off_str, 16)

        with open(self.binary_path, "rb") as f:
            bin_data = bytearray(f.read())

        pushes = self._get_call_pushes(bin_data, call_offset)
        if len(pushes) != 54:
            raise RuntimeError(
                f"Failed to find all 54 pushes for unit {unit['korean_name']} (found {len(pushes)})."
            )

        # In 54 pushes: arg[53] is pushes[0], arg[0] is pushes[53]
        push_index = 53 - target_arg
        ins_va, ins_bytes, op_str, old_val = pushes[push_index]
        ins_offset = ins_va - IMAGE_BASE

        opcode = ins_bytes[0]

        if opcode == 0x6A:  # push imm8 (2 bytes)
            if not (-128 <= new_value <= 255):
                raise ValueError(
                    f"Stat '{stat_name}' for unit {unit['korean_name']} is an imm8 push (max 127/255). "
                    f"Value {new_value} cannot fit in a 1-byte immediate without resizing instruction."
                )
            new_bytes = bytes([0x6A, new_value & 0xFF])
            bin_data[ins_offset : ins_offset + 2] = new_bytes

        elif opcode == 0x68:  # push imm32 (5 bytes)
            new_bytes = bytes([0x68]) + struct.pack("<I", new_value & 0xFFFFFFFF)
            bin_data[ins_offset : ins_offset + 5] = new_bytes

        else:
            raise ValueError(
                f"Instruction at 0x{ins_va:08x} for '{stat_name}' is '{op_str}' (opcode 0x{opcode:02x}), "
                "which is not an immediate push (e.g. dynamic register). Cannot patch in-place."
            )

        if len(bin_data) != EXPECTED_BINARY_SIZE:
            raise RuntimeError(
                f"Integrity check failed: patched binary size {len(bin_data)} != {EXPECTED_BINARY_SIZE}."
            )

        # Write safely back to target binary copy
        with open(self.binary_path, "wb") as f:
            f.write(bin_data)

        return PatchResult(
            success=True,
            unit_name=unit.get("korean_name", "UNKNOWN"),
            unit_index=unit.get("index", 0),
            stat_name=stat_key,
            old_value=old_val,
            new_value=new_value,
            virtual_address=ins_va,
            file_offset=ins_offset,
            old_bytes=ins_bytes,
            new_bytes=new_bytes,
            message=f"Successfully patched {unit.get('korean_name')} {stat_key} from {old_val} to {new_value}",
        )


def modify_unit_stat(
    binary_path: str,
    unit_id_or_name: Union[int, str],
    stat_field: str,
    new_value: int,
) -> PatchResult:
    """Top-level functional API for patching a unit stat in a Dawn executable copy."""
    patcher = BinaryPatcher(binary_path)
    return patcher.patch_unit_stat(unit_id_or_name, stat_field, new_value)


def patch_movement_speed(
    binary_path: str,
    unit_id_or_name: Union[int, str],
    new_speed: int,
) -> PatchResult:
    """Specialized helper for patching movement speed of a unit in a Dawn binary copy."""
    return modify_unit_stat(binary_path, unit_id_or_name, "speed", new_speed)


def check_binary_integrity(
    orig_path: str,
    patched_path: str,
    allowed_offsets: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """Exhaustive PE integrity verification between original Dawn binary and patched copy.

    Checks:
    1. Both files exist and are exactly 1,032,192 bytes.
    2. DOS header, PE signature, COFF header, OptionalHeader, and Section Headers are 100% intact.
    3. If allowed_offsets is provided, ensures NO OTHER byte in the entire 1MB binary differs.
    """
    if not os.path.isfile(orig_path):
        return {"valid": False, "message": f"Original file not found: {orig_path}"}
    if not os.path.isfile(patched_path):
        return {"valid": False, "message": f"Patched file not found: {patched_path}"}

    orig_size = os.path.getsize(orig_path)
    patched_size = os.path.getsize(patched_path)

    if orig_size != EXPECTED_BINARY_SIZE or patched_size != EXPECTED_BINARY_SIZE:
        return {
            "valid": False,
            "size_valid": False,
            "orig_size": orig_size,
            "patched_size": patched_size,
            "message": f"File size mismatch: orig={orig_size}, patched={patched_size}, expected={EXPECTED_BINARY_SIZE}",
        }

    with open(orig_path, "rb") as f:
        orig = f.read()
    with open(patched_path, "rb") as f:
        patched = f.read()

    # Verify PE Header region (offset 0 to 0x1000 is section alignment boundary)
    pe_headers_intact = orig[:0x1000] == patched[:0x1000]

    # Find all byte diffs across entire file
    diff_offsets: List[int] = []
    for i in range(EXPECTED_BINARY_SIZE):
        if orig[i] != patched[i]:
            diff_offsets.append(i)

    disallowed_diffs: List[int] = []
    if allowed_offsets is not None:
        allowed_set: Set[int] = set(allowed_offsets)
        disallowed_diffs = [off for off in diff_offsets if off not in allowed_set]

    valid = pe_headers_intact and (len(disallowed_diffs) == 0)

    # Group contiguous diff ranges
    diff_ranges: List[Tuple[int, int]] = []
    if diff_offsets:
        start = diff_offsets[0]
        prev = start
        for off in diff_offsets[1:]:
            if off == prev + 1:
                prev = off
            else:
                diff_ranges.append((start, prev - start + 1))
                start = off
                prev = off
        diff_ranges.append((start, prev - start + 1))

    return {
        "valid": valid,
        "size_valid": True,
        "pe_headers_intact": pe_headers_intact,
        "diff_count": len(diff_offsets),
        "diff_offsets": diff_offsets,
        "diff_ranges": diff_ranges,
        "disallowed_diffs": disallowed_diffs,
        "message": (
            "PE binary integrity verified: headers intact and only target bytes differ."
            if valid
            else f"Integrity check failed: headers_intact={pe_headers_intact}, disallowed_diffs={len(disallowed_diffs)}"
        ),
    }


def verify_binary_integrity(
    orig_path: str,
    patched_path: str,
    allowed_offsets: Optional[Iterable[int]] = None,
) -> bool:
    """Simple boolean verification wrapper for automated test suites."""
    report = check_binary_integrity(orig_path, patched_path, allowed_offsets)
    return report.get("valid", False)
