"""
Builds YM/dawn/dplayx.dll — a lightweight, dependency-free 32-bit DirectPlay (DPLAYX.dll)
portable shim for Imjinrok 2+ Chosun's Counterattack (dawn.exe), and bundles 32-bit
vcruntime140.dll into YM/dawn/ if available on the host.

Why this is needed:
  - On fresh Windows 11 installations, the legacy "DirectPlay" Windows Optional Feature
    is disabled by default. Because dawn.exe statically imports DPLAYX.dll (Ordinal 1:
    DirectPlayCreate), Windows 11 blocks execution with a Fondue.exe popup ("An app on
    your PC needs the following Windows feature: DirectPlay").
  - Placing this 32-bit dplayx.dll directly in YM/dawn/ satisfies the PE loader and
    allows Single-Player Campaign ('시나리오') and Single-Player Skirmish ('임의게임 -> 혼자하기')
    to launch immediately on any Windows 11 or macOS (Wine/CrossOver/Parallels) system
    with zero OS feature installation.
"""

from __future__ import annotations

import shutil
import struct
from pathlib import Path

IMAGE_BASE = 0x65500000
TEXT_RVA = 0x1000
DATA_RVA = 0x2000


def build_dplayx_pe() -> bytes:
    text_sec = bytearray(0x1000)

    # 0x00: DllMain(hinst, reason, reserved) -> mov eax, 1; ret 0x0C
    off_dllmain = 0x00
    text_sec[off_dllmain : off_dllmain + 8] = b"\xB8\x01\x00\x00\x00\xC2\x0C\x00"

    # 0x10: DirectPlayCreate(lpGUID, lplpDP, pUnk) -> stdcall, ret 0x0C
    # Zeroes *lplpDP if non-null and returns DPERR_GENERIC (0x80004005)
    off_dp_create = 0x10
    dp_create_code = (
        b"\x8B\x44\x24\x08"              # mov eax, [esp+8] (lplpDP)
        b"\x85\xC0"                      # test eax, eax
        b"\x74\x06"                      # jz +6
        b"\xC7\x00\x00\x00\x00\x00"      # mov dword ptr [eax], 0
        b"\xB8\x05\x40\x00\x80"          # mov eax, 0x80004005 (E_FAIL / DPERR_GENERIC)
        b"\xC2\x0C\x00"                  # ret 0x0C
    )
    text_sec[off_dp_create : off_dp_create + len(dp_create_code)] = dp_create_code

    # 0x30: DirectPlayEnumerate / A / W (lpCallback, lpContext) -> xor eax, eax; ret 8
    off_dp_enum = 0x30
    text_sec[off_dp_enum : off_dp_enum + 5] = b"\x31\xC0\xC2\x08\x00"

    # 0x40: DirectPlayLobbyCreate A / W (5 args) -> mov eax, 0x80004005; ret 0x14
    off_dpl_create = 0x40
    dpl_code = (
        b"\x8B\x44\x24\x08"              # mov eax, [esp+8] (lplpDPL)
        b"\x85\xC0"
        b"\x74\x06"
        b"\xC7\x00\x00\x00\x00\x00"
        b"\xB8\x05\x40\x00\x80"
        b"\xC2\x14\x00"
    )
    text_sec[off_dpl_create : off_dpl_create + len(dpl_code)] = dpl_code

    # 0x60: DllCanUnloadNow / DllRegisterServer / DllUnregisterServer (0 args) -> xor eax, eax; ret
    off_dll_0 = 0x60
    text_sec[off_dll_0 : off_dll_0 + 3] = b"\x31\xC0\xC3"

    # 0x70: DllGetClassObject(rclsid, riid, ppv) -> CLASS_E_CLASSNOTAVAILABLE (0x80040111); ret 0x0C
    off_dll_gco = 0x70
    gco_code = (
        b"\x8B\x44\x24\x0C"              # mov eax, [esp+0x0C] (ppv)
        b"\x85\xC0"
        b"\x74\x06"
        b"\xC7\x00\x00\x00\x00\x00"
        b"\xB8\x11\x01\x04\x80"          # mov eax, 0x80040111
        b"\xC2\x0C\x00"
    )
    text_sec[off_dll_gco : off_dll_gco + len(gco_code)] = gco_code

    # Export Directory at offset 0x200 in .text (RVA 0x1200)
    exp_off = 0x200
    exp_rva = TEXT_RVA + exp_off
    eat_off = 0x240
    eat_rva = TEXT_RVA + eat_off
    name_ptr_off = 0x280
    name_ptr_rva = TEXT_RVA + name_ptr_off
    ord_off = 0x2C0
    ord_rva = TEXT_RVA + ord_off
    dll_name_off = 0x300
    dll_name_rva = TEXT_RVA + dll_name_off

    # Ordinals 1..11 (Base = 1)
    eat_entries = [
        TEXT_RVA + off_dp_create,   # 1: DirectPlayCreate
        TEXT_RVA + off_dp_enum,     # 2: DirectPlayEnumerateA
        TEXT_RVA + off_dp_enum,     # 3: DirectPlayEnumerateW
        TEXT_RVA + off_dpl_create,  # 4: DirectPlayLobbyCreateA
        TEXT_RVA + off_dpl_create,  # 5: DirectPlayLobbyCreateW
        TEXT_RVA + off_dll_0,       # 6: DllCanUnloadNow
        TEXT_RVA + off_dll_gco,     # 7: DllGetClassObject
        TEXT_RVA + off_dll_0,       # 8: DllRegisterServer
        TEXT_RVA + off_dp_enum,     # 9: DirectPlayEnumerate
        TEXT_RVA + off_dll_0,       # 10: DllUnregisterServer
        DATA_RVA + 0x00,            # 11: gdwDPlaySPRefCount
    ]
    for i, rva in enumerate(eat_entries):
        struct.pack_into("<I", text_sec, eat_off + i * 4, rva)

    # Named exports sorted lexicographically for binary search
    named_exports = [
        ("DirectPlayCreate", 0),
        ("DirectPlayEnumerate", 8),
        ("DirectPlayEnumerateA", 1),
        ("DirectPlayEnumerateW", 2),
        ("DirectPlayLobbyCreateA", 3),
        ("DirectPlayLobbyCreateW", 4),
        ("DllCanUnloadNow", 5),
        ("DllGetClassObject", 6),
        ("DllRegisterServer", 7),
        ("DllUnregisterServer", 9),
        ("gdwDPlaySPRefCount", 10),
    ]

    text_sec[dll_name_off : dll_name_off + 11] = b"dplayx.dll\x00"
    str_cursor = 0x320
    for idx, (sym_name, ord_idx) in enumerate(named_exports):
        sym_bytes = sym_name.encode("ascii") + b"\x00"
        text_sec[str_cursor : str_cursor + len(sym_bytes)] = sym_bytes
        struct.pack_into("<I", text_sec, name_ptr_off + idx * 4, TEXT_RVA + str_cursor)
        struct.pack_into("<H", text_sec, ord_off + idx * 2, ord_idx)
        str_cursor += len(sym_bytes)

    exp_dir = struct.pack(
        "<IIHHIIIIIII",
        0,
        0,
        0,
        0,
        dll_name_rva,
        1,                      # Base = 1
        len(eat_entries),       # NumberOfFunctions = 11
        len(named_exports),     # NumberOfNames = 11
        eat_rva,
        name_ptr_rva,
        ord_rva,
    )
    text_sec[exp_off : exp_off + 40] = exp_dir

    data_sec = bytearray(0x1000)

    # PE Headers (0x400 bytes)
    headers = bytearray(0x400)
    headers[0:2] = b"MZ"
    struct.pack_into("<I", headers, 0x3C, 0x80)
    pe_off = 0x80
    headers[pe_off : pe_off + 4] = b"PE\x00\x00"
    struct.pack_into(
        "<HHIIIHH",
        headers,
        pe_off + 4,
        0x014C,         # IMAGE_FILE_MACHINE_I386
        2,              # NumberOfSections = 2
        0, 0, 0,
        0xE0,           # SizeOfOptionalHeader
        0x210E,         # Characteristics (DLL | 32BIT | EXECUTABLE)
    )
    opt_off = pe_off + 24
    struct.pack_into(
        "<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII",
        headers,
        opt_off,
        0x010B,         # PE32
        14, 0,
        0x1000,         # SizeOfCode
        0x1000,         # SizeOfInitializedData
        0,
        TEXT_RVA + off_dllmain,
        TEXT_RVA,
        DATA_RVA,
        IMAGE_BASE,
        0x1000,         # SectionAlignment
        0x0200,         # FileAlignment
        4, 0, 0, 0, 4, 0, 0,
        0x3000,         # SizeOfImage
        0x0400,         # SizeOfHeaders
        0,
        2,              # Subsystem = WINDOWS_GUI
        0,
        0x100000, 0x1000, 0x100000, 0x1000, 0,
        16,
    )
    struct.pack_into("<II", headers, opt_off + 96, exp_rva, 0x200)

    sec_off = opt_off + 0xE0
    struct.pack_into(
        "<8sIIIIIIHHI",
        headers,
        sec_off,
        b".text\x00\x00\x00",
        0x1000, TEXT_RVA, 0x1000, 0x0400, 0, 0, 0, 0, 0x60000020,
    )
    struct.pack_into(
        "<8sIIIIIIHHI",
        headers,
        sec_off + 40,
        b".data\x00\x00\x00",
        0x1000, DATA_RVA, 0x1000, 0x1400, 0, 0, 0, 0, 0xC0000040,
    )
    return bytes(headers + text_sec + data_sec)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dawn_dir = repo_root / "YM" / "dawn"
    dplayx_out = dawn_dir / "dplayx.dll"
    pe_bytes = build_dplayx_pe()
    dplayx_out.write_bytes(pe_bytes)
    print(f"Built {dplayx_out} ({len(pe_bytes)} bytes)")

    # Also bundle 32-bit vcruntime140.dll from SysWOW64 if present so syw2x.dll works out-of-the-box
    sys_vcruntime = Path(r"C:\Windows\SysWOW64\vcruntime140.dll")
    dst_vcruntime = dawn_dir / "vcruntime140.dll"
    if sys_vcruntime.exists() and not dst_vcruntime.exists():
        shutil.copy2(sys_vcruntime, dst_vcruntime)
        print(f"Bundled {dst_vcruntime} ({dst_vcruntime.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
