"""
Builds YM/dawn/parsec_gdi.asi — a 32-bit DirectDraw7-to-GDI DIBSection renderer ASI plugin
for Imjinrok 2+ Chosun's Counterattack (dawn.exe).

Enhanced with borderless windowed fullscreen scaling:
  1. Queries display resolution via GetSystemMetrics(SM_CXSCREEN / SM_CYSCREEN).
  2. Resizes game window to cover full screen via MoveWindow(hWnd, 0, 0, screen_w, screen_h, 1).
  3. Maintains strict 4:3 aspect ratio pillarbox/letterbox destination viewport.
  4. Fills pillarbox / letterbox margins with solid black via PatBlt(BLACKNESS).
  5. Scales top-down DIBSection into destination rectangle via StretchBlt.
  6. Maps mouse coordinates accurately from scaled screen space back to game coordinates
     via GetCursorPos and WM_MOUSEMOVE hooks.
"""

from __future__ import annotations

import struct
from pathlib import Path
import capstone


IMAGE_BASE = 0x65400000
TEXT_RVA = 0x1000
DATA_RVA = 0x3000
TEXT_VA = IMAGE_BASE + TEXT_RVA
DATA_VA = IMAGE_BASE + DATA_RVA

# dawn.exe IAT function pointers (dawn.exe has fixed ImageBase 0x00400000, no ASLR)
IAT_VirtualFree = 0x004E5108
IAT_VirtualAlloc = 0x004E510C
IAT_GetModuleHandleA = 0x004E5160
IAT_GetProcAddress = 0x004E516C
IAT_GetCursorPos = 0x004E51D8
IAT_MoveWindow = 0x004E523C
IAT_GetDC = 0x004E524C
IAT_ReleaseDC = 0x004E5250
IAT_GetSystemMetrics = 0x004E5268
IAT_SelectObject = 0x004E5040
IAT_DeleteObject = 0x004E5044
IAT_DeleteDC = 0x004E504C
IAT_StretchBlt = 0x004E5050
IAT_CreateCompatibleDC = 0x004E5054
IAT_CreateFontA = 0x004E5028
IAT_TextOutA = 0x004E502C
IAT_GetTextExtentPoint32A = 0x004E5034
IAT_MultiByteToWideChar = 0x004E50B8

# .data layout (0x65403000)
VA_DD_OBJ = DATA_VA + 0x0000          # ddObj: [ddVtable]
VA_PAL_OBJ = DATA_VA + 0x0004         # palObj: [palVtable]
VA_CLIP_OBJ = DATA_VA + 0x0008        # clipObj: [clipVtable]
VA_G_HWND = DATA_VA + 0x0010          # HWND
VA_G_WIDTH = DATA_VA + 0x0014         # DWORD (default 640)
VA_G_HEIGHT = DATA_VA + 0x0018        # DWORD (default 480)
VA_G_BPP = DATA_VA + 0x001C           # DWORD (default 8)
VA_G_PRIMARY = DATA_VA + 0x0020       # Surface*
VA_G_BACK = DATA_VA + 0x0024          # Surface*
VA_PFN_VIRTUALPROTECT = DATA_VA + 0x0028
VA_PFN_CREATEDIBSECTION = DATA_VA + 0x002C
VA_PFN_SETDIBCOLORTABLE = DATA_VA + 0x0030
VA_PFN_GDIFLUSH = DATA_VA + 0x0034
VA_OLD_PROTECT = DATA_VA + 0x0038
VA_G_INIT_DONE = DATA_VA + 0x003C
VA_PFN_PATBLT = DATA_VA + 0x0040
VA_ORIG_GETCURSORPOS = DATA_VA + 0x0044
VA_SCREEN_W = DATA_VA + 0x0048
VA_SCREEN_H = DATA_VA + 0x004C
VA_DST_X = DATA_VA + 0x0050
VA_DST_Y = DATA_VA + 0x0054
VA_DST_W = DATA_VA + 0x0058
VA_DST_H = DATA_VA + 0x005C
VA_LAST_RAW_X = DATA_VA + 0x0060
VA_LAST_RAW_Y = DATA_VA + 0x0064
VA_PFN_CREATEFONTW = DATA_VA + 0x0068
VA_PFN_TEXTOUTW = DATA_VA + 0x006C
VA_PFN_GETTEXTEXTENTPOINT32W = DATA_VA + 0x0070
VA_WIDE_BUF = DATA_VA + 0x1400        # 1024 WCHARs (2048 bytes) for CP949->UTF16LE conversion

VA_DD_VTABLE = DATA_VA + 0x0100       # 32 dwords
VA_SURF_VTABLE = DATA_VA + 0x0180     # 40 dwords
VA_PAL_VTABLE = DATA_VA + 0x0220      # 16 dwords
VA_CLIP_VTABLE = DATA_VA + 0x0260     # 16 dwords
VA_MODE_TABLE = DATA_VA + 0x0300      # 8 modes * 12 bytes (w, h, bpp)
VA_RGBQUADS = DATA_VA + 0x0400        # 256 * 4 bytes (B, G, R, 0)
VA_PALENTRIES = DATA_VA + 0x0800      # 256 * 4 bytes (R, G, B, flags)
VA_BMI_BUF = DATA_VA + 0x0C00         # 40 + 1024 bytes
VA_ENUM_DDSD = DATA_VA + 0x1100       # 128 bytes


class CodeBuffer:
    def __init__(self, base_va: int) -> None:
        self.base_va = base_va
        self.buf = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups_rel32: list[tuple[int, str]] = []
        self.fixups_rel8: list[tuple[int, str]] = []

    @property
    def va(self) -> int:
        return self.base_va + len(self.buf)

    def label(self, name: str) -> int:
        while len(self.buf) % 4 != 0:
            self.buf.append(0x90)
        self.labels[name] = self.va
        return self.va

    def mark(self, name: str) -> int:
        self.labels[name] = self.va
        return self.va

    def emit(self, raw: bytes) -> None:
        self.buf.extend(raw)

    def call_rel(self, target_label: str) -> None:
        self.buf.append(0xE8)
        self.fixups_rel32.append((len(self.buf), target_label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def jmp_rel(self, target_label: str) -> None:
        self.buf.append(0xE9)
        self.fixups_rel32.append((len(self.buf), target_label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def jcc_rel(self, opcode2: int, target_label: str) -> None:
        self.buf.extend(bytes([0x0F, opcode2]))
        self.fixups_rel32.append((len(self.buf), target_label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def resolve(self) -> bytes:
        for off, name in self.fixups_rel32:
            target_va = self.labels[name]
            next_va = self.base_va + off + 4
            rel = target_va - next_va
            struct.pack_into("<i", self.buf, off, rel)
        for off, name in self.fixups_rel8:
            target_va = self.labels[name]
            next_va = self.base_va + off + 1
            rel = target_va - next_va
            struct.pack_into("<b", self.buf, off, rel)
        return bytes(self.buf)


def build_code() -> tuple[bytes, dict[str, int]]:
    c = CodeBuffer(TEXT_VA)

    # Strings in .data at DATA_VA + 0x1200
    VA_STR_KERNEL32 = DATA_VA + 0x1200
    VA_STR_VIRTUALPROTECT = DATA_VA + 0x1210
    VA_STR_GDI32 = DATA_VA + 0x1224
    VA_STR_CREATEDIBSECTION = DATA_VA + 0x1230
    VA_STR_SETDIBCOLORTABLE = DATA_VA + 0x1244
    VA_STR_GDIFLUSH = DATA_VA + 0x1258
    VA_STR_PATBLT = DATA_VA + 0x1268
    VA_STR_CREATEFONTW = DATA_VA + 0x1278
    VA_STR_TEXTOUTW = DATA_VA + 0x1288
    VA_STR_GETTEXTEXTENTPOINT32W = DATA_VA + 0x1298

    # =========================================================================
    # 1. DllMain(hinstDLL, fdwReason, lpvReserved) -> stdcall, ret 0x0C
    # =========================================================================
    c.label("DllMain")
    c.emit(b"\x83\x7C\x24\x08\x01")              # cmp dword ptr [esp+8], 1 (DLL_PROCESS_ATTACH)
    c.jcc_rel(0x85, "dllmain_done")              # jne dllmain_done
    c.call_rel("InitializeASI")
    c.mark("dllmain_done")
    c.emit(b"\xB8\x01\x00\x00\x00")              # mov eax, 1
    c.emit(b"\xC2\x0C\x00")                      # ret 0x0C

    # =========================================================================
    # Helper: UpdateScreenMetrics() -> cdecl (0 args), preserves ebx, esi, edi
    # =========================================================================
    c.label("UpdateScreenMetrics")
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi

    # GetSystemMetrics(0 = SM_CXSCREEN)
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetSystemMetrics))
    c.emit(b"\x89\xC3")                                                 # mov ebx, eax (screen_w)
    c.emit(b"\x89\x05" + struct.pack("<I", VA_SCREEN_W))

    # GetSystemMetrics(1 = SM_CYSCREEN)
    c.emit(b"\x6A\x01")                                                 # push 1
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetSystemMetrics))
    c.emit(b"\x89\xC6")                                                 # mov esi, eax (screen_h)
    c.emit(b"\x89\x05" + struct.pack("<I", VA_SCREEN_H))

    # Compare screen_w * 3 vs screen_h * 4:
    # eax = screen_w * 3
    c.emit(b"\x8D\x04\x5B")                                             # lea eax, [ebx + ebx*2] (screen_w * 3)
    # ecx = screen_h * 4
    c.emit(b"\x89\xF1")                                                 # mov ecx, esi
    c.emit(b"\xC1\xE1\x02")                                             # shl ecx, 2 (screen_h * 4)
    c.emit(b"\x39\xC8")                                                 # cmp eax, ecx
    c.jcc_rel(0x8C, "usm_letterbox")                                    # jl usm_letterbox

    # Pillarbox (widescreen 16:9 / 16:10 / 21:9):
    # dst_h = screen_h
    c.emit(b"\x89\x35" + struct.pack("<I", VA_DST_H))
    # dst_w = (screen_h * 4) / 3
    c.emit(b"\x89\xF0")                                                 # mov eax, esi (screen_h)
    c.emit(b"\xC1\xE0\x02")                                             # shl eax, 2 (screen_h * 4)
    c.emit(b"\x31\xD2")                                                 # xor edx, edx
    c.emit(b"\xB9\x03\x00\x00\x00")                                     # mov ecx, 3
    c.emit(b"\xF7\xF1")                                                 # div ecx (eax = dst_w)
    c.emit(b"\xA3" + struct.pack("<I", VA_DST_W))
    # dst_x = (screen_w - dst_w) / 2
    c.emit(b"\x89\xDA")                                                 # mov edx, ebx (screen_w)
    c.emit(b"\x29\xC2")                                                 # sub edx, eax (screen_w - dst_w)
    c.emit(b"\xD1\xFA")                                                 # sar edx, 1
    c.emit(b"\x89\x15" + struct.pack("<I", VA_DST_X))
    # dst_y = 0
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_DST_Y, 0))
    c.jmp_rel("usm_done")

    c.mark("usm_letterbox")
    # Letterbox:
    # dst_w = screen_w
    c.emit(b"\x89\x1D" + struct.pack("<I", VA_DST_W))                  # dst_w = screen_w
    # dst_h = (screen_w * 3) / 4
    c.emit(b"\x8D\x04\x5B")                                             # lea eax, [ebx + ebx*2] (screen_w * 3)
    c.emit(b"\xC1\xE8\x02")                                             # shr eax, 2
    c.emit(b"\xA3" + struct.pack("<I", VA_DST_H))
    # dst_y = (screen_h - dst_h) / 2
    c.emit(b"\x89\xF2")                                                 # mov edx, esi (screen_h)
    c.emit(b"\x29\xC2")                                                 # sub edx, eax
    c.emit(b"\xD1\xFA")                                                 # sar edx, 1
    c.emit(b"\x89\x15" + struct.pack("<I", VA_DST_Y))
    # dst_x = 0
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_DST_X, 0))

    c.mark("usm_done")
    c.emit(b"\x5F\x5E\x5B")                                             # pop edi; pop esi; pop ebx
    c.emit(b"\xC3")                                                     # ret

    # =========================================================================
    # 2. InitializeASI() -> cdecl/stdcall (0 args), ret
    # =========================================================================
    c.label("InitializeASI")
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_G_INIT_DONE) + b"\x01")  # cmp dword ptr [VA_G_INIT_DONE], 1
    c.jcc_rel(0x84, "init_ret")
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_G_INIT_DONE, 1))        # mov dword ptr [VA_G_INIT_DONE], 1
    c.emit(b"\x56")                                                     # push esi

    # Resolve VirtualProtect from KERNEL32.dll
    c.emit(b"\x68" + struct.pack("<I", VA_STR_KERNEL32))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetModuleHandleA))
    c.emit(b"\x68" + struct.pack("<I", VA_STR_VIRTUALPROTECT))
    c.emit(b"\x50")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_VIRTUALPROTECT))

    # Resolve CreateDIBSection, SetDIBColorTable, GdiFlush, PatBlt from GDI32.dll
    c.emit(b"\x68" + struct.pack("<I", VA_STR_GDI32))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetModuleHandleA))
    c.emit(b"\x89\xC6")                                                 # mov esi, eax

    c.emit(b"\x68" + struct.pack("<I", VA_STR_CREATEDIBSECTION))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_CREATEDIBSECTION))

    c.emit(b"\x68" + struct.pack("<I", VA_STR_SETDIBCOLORTABLE))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_SETDIBCOLORTABLE))

    c.emit(b"\x68" + struct.pack("<I", VA_STR_GDIFLUSH))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_GDIFLUSH))

    c.emit(b"\x68" + struct.pack("<I", VA_STR_PATBLT))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_PATBLT))

    c.emit(b"\x68" + struct.pack("<I", VA_STR_CREATEFONTW))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_CREATEFONTW))

    c.emit(b"\x68" + struct.pack("<I", VA_STR_TEXTOUTW))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_TEXTOUTW))

    c.emit(b"\x68" + struct.pack("<I", VA_STR_GETTEXTEXTENTPOINT32W))
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
    c.emit(b"\xA3" + struct.pack("<I", VA_PFN_GETTEXTEXTENTPOINT32W))

    # Hook GDI32 CreateFontA (0x004E5028), TextOutA (0x004E502C), GetTextExtentPoint32A (0x004E5034)
    # VirtualProtect(0x004E5028, 16, PAGE_READWRITE (0x04), &oldProtect)
    c.emit(b"\x68" + struct.pack("<I", VA_OLD_PROTECT))
    c.emit(b"\x6A\x04")
    c.emit(b"\x6A\x10")
    c.emit(b"\x68" + struct.pack("<I", IAT_CreateFontA))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_VIRTUALPROTECT))

    c.emit(b"\xC7\x05" + struct.pack("<I", IAT_CreateFontA))
    patch_cf_pos = len(c.buf)
    c.emit(b"\x00\x00\x00\x00")

    c.emit(b"\xC7\x05" + struct.pack("<I", IAT_TextOutA))
    patch_toa_pos = len(c.buf)
    c.emit(b"\x00\x00\x00\x00")

    c.emit(b"\xC7\x05" + struct.pack("<I", IAT_GetTextExtentPoint32A))
    patch_gtep_pos = len(c.buf)
    c.emit(b"\x00\x00\x00\x00")

    # Initialize screen metrics and dst rect
    c.call_rel("UpdateScreenMetrics")

    # VirtualProtect(0x004D7938, 8, PAGE_EXECUTE_READWRITE (0x40), &oldProtect)
    c.emit(b"\x68" + struct.pack("<I", VA_OLD_PROTECT))
    c.emit(b"\x6A\x40")
    c.emit(b"\x6A\x08")
    c.emit(b"\x68" + struct.pack("<I", 0x004D7938))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_VIRTUALPROTECT))

    # Patch 0x004D7938: jmp MyDirectDrawCreateEx
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x004D7938) + b"\xE9")
    patch_disp_pos = len(c.buf) + 6
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x004D7939, 0))

    # Save original GetCursorPos from IAT (0x004E51D8)
    c.emit(b"\xA1" + struct.pack("<I", IAT_GetCursorPos))
    c.emit(b"\xA3" + struct.pack("<I", VA_ORIG_GETCURSORPOS))

    # VirtualProtect(0x004E51D8, 4, PAGE_READWRITE (0x04), &oldProtect)
    c.emit(b"\x68" + struct.pack("<I", VA_OLD_PROTECT))
    c.emit(b"\x6A\x04")
    c.emit(b"\x6A\x04")
    c.emit(b"\x68" + struct.pack("<I", IAT_GetCursorPos))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_VIRTUALPROTECT))

    # Overwrite IAT_GetCursorPos (0x004E51D8) with MyGetCursorPos
    c.emit(b"\xC7\x05" + struct.pack("<I", IAT_GetCursorPos))
    patch_gcp_pos = len(c.buf)
    c.emit(b"\x00\x00\x00\x00")

    # Hook WM_MOUSEMOVE (0x0042434B), WM_SYSKEYDOWN (0x00424300), and patch exit/focus logic
    # VirtualProtect(0x00423000, 0x2700, PAGE_EXECUTE_READWRITE (0x40), &oldProtect)
    c.emit(b"\x68" + struct.pack("<I", VA_OLD_PROTECT))
    c.emit(b"\x6A\x40")
    c.emit(b"\x68\x00\x27\x00\x00")
    c.emit(b"\x68" + struct.pack("<I", 0x00423000))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_VIRTUALPROTECT))

    # VirtualProtect(0x00493F00, 0x20, PAGE_EXECUTE_READWRITE (0x40), &oldProtect)
    c.emit(b"\x68" + struct.pack("<I", VA_OLD_PROTECT))
    c.emit(b"\x6A\x40")
    c.emit(b"\x6A\x20")
    c.emit(b"\x68" + struct.pack("<I", 0x00493F00))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_VIRTUALPROTECT))

    # Patch 0x0042434B: jmp MyMouseMove (5 bytes) + 3 NOPs
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x0042434B) + b"\xE9")
    patch_mouse_disp_pos = len(c.buf) + 6
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x0042434C, 0))
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x00424350) + b"\x90")
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x00424351) + b"\x90")
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x00424352) + b"\x90")

    # Patch 0x00424300 (WM_SYSKEYDOWN): jmp MySysKeyDown (5 bytes) + 2 NOPs
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x00424300) + b"\xE9")
    patch_syskey_disp_pos = len(c.buf) + 6
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00424301, 0))
    c.emit(b"\x66\xC7\x05" + struct.pack("<IH", 0x00424305, 0x9090))

    # Fix 1: Prevent WinMain (0x004232BE) from resetting [0x00B643C8] to 0
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x004232C4, 1))

    # Fix 2: NOP out synchronous SetSysColors(25, ...) call in WM_DESTROY cleanup (0x0042300D..0x00423016)
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x0042300D, 0x90909090))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00423011, 0x90909090))
    c.emit(b"\x66\xC7\x05" + struct.pack("<IH", 0x00423015, 0x9090))

    # Fix 3: Skip redundant second 21-frame fade-out in State 10 (0x0042473E -> State 11 DestroyWindow)
    c.emit(b"\x66\xC7\x05" + struct.pack("<IH", 0x00424745, 0x000B))

    # Fix 4: Make In-Game '설정 -> 게임종료 -> 예' in Single-Player Skirmish exit directly to Windows
    # (0x004255F8: jne 0x0042562D instead of 0x0042560E Score Screen; 0x00493F15: 1 tick instead of 20)
    c.emit(b"\xC6\x05" + struct.pack("<I", 0x004255F9) + b"\x33")
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00493F15, 1))

    # Keep dawn.exe active in background ([0x00B643C8] = 1, [0x0066976C] = 1, [0x00B64FE8] = 0)
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00B643C8, 1))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x0066976C, 1))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00B64FE8, 0))

    c.emit(b"\x5E")                                                     # pop esi
    c.mark("init_ret")
    c.emit(b"\xC3")                                                     # ret

    # =========================================================================
    # 3. MyDirectDrawCreateEx(lpGUID, lplpDD, iid, pUnkOuter) -> stdcall, ret 0x10
    # =========================================================================
    va_my_ddcreate = c.label("MyDirectDrawCreateEx")
    struct.pack_into("<i", c.buf, patch_disp_pos, va_my_ddcreate - (0x004D7938 + 5))

    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00B643C8, 1))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x0066976C, 1))
    c.emit(b"\x8B\x44\x24\x08")                                         # mov eax, [esp+8] (lplpDD)
    c.emit(b"\xC7\x00" + struct.pack("<I", VA_DD_OBJ))                  # mov dword ptr [eax], VA_DD_OBJ
    c.emit(b"\x31\xC0")                                                 # xor eax, eax (DD_OK)
    c.emit(b"\xC2\x10\x00")                                             # ret 0x10

    # =========================================================================
    # Helper: CP949-to-Unicode GDI Hooks (for non-Korean Windows 11 & macOS Wine)
    # =========================================================================
    va_my_createfont = c.label("MyCreateFontA")
    struct.pack_into("<I", c.buf, patch_cf_pos, va_my_createfont)
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x66\xC7\x05" + struct.pack("<IH", VA_WIDE_BUF, 0))        # mov word ptr [VA_WIDE_BUF], 0
    c.emit(b"\x8B\x55\x3C")                                             # mov edx, [ebp+0x3C] (pszFaceName)
    c.emit(b"\x85\xD2")                                                 # test edx, edx
    c.jcc_rel(0x84, "cf_call_w")
    c.emit(b"\x6A\x40")                                                 # push 64
    c.emit(b"\x68" + struct.pack("<I", VA_WIDE_BUF))                    # push VA_WIDE_BUF
    c.emit(b"\x6A\xFF")                                                 # push -1
    c.emit(b"\x52")                                                     # push edx (pszFaceName)
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\x68\xB5\x03\x00\x00")                                     # push 949 (CP949 Korean)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_MultiByteToWideChar))
    c.mark("cf_call_w")
    c.emit(b"\x68" + struct.pack("<I", VA_WIDE_BUF))                    # arg14: pszFaceName
    c.emit(b"\xFF\x75\x38")                                             # arg13: iPitchAndFamily
    c.emit(b"\xFF\x75\x34")                                             # arg12: iQuality
    c.emit(b"\xFF\x75\x30")                                             # arg11: iClipPrecision
    c.emit(b"\xFF\x75\x2C")                                             # arg10: iOutPrecision
    c.emit(b"\x68\x81\x00\x00\x00")                                     # arg9:  iCharSet = HANGEUL_CHARSET (0x81)
    c.emit(b"\xFF\x75\x24")                                             # arg8:  bStrikeOut
    c.emit(b"\xFF\x75\x20")                                             # arg7:  bUnderline
    c.emit(b"\xFF\x75\x1C")                                             # arg6:  bItalic
    c.emit(b"\xFF\x75\x18")                                             # arg5:  cWeight
    c.emit(b"\xFF\x75\x14")                                             # arg4:  cOrientation
    c.emit(b"\xFF\x75\x10")                                             # arg3:  cEscapement
    c.emit(b"\xFF\x75\x0C")                                             # arg2:  cWidth
    c.emit(b"\xFF\x75\x08")                                             # arg1:  cHeight
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_CREATEFONTW))
    c.emit(b"\x5D\xC2\x38\x00")                                         # pop ebp; ret 0x38

    va_my_textout = c.label("MyTextOutA")
    struct.pack_into("<I", c.buf, patch_toa_pos, va_my_textout)
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x8B\x4D\x18")                                             # mov ecx, [ebp+0x18] (c)
    c.emit(b"\x85\xC9")                                                 # test ecx, ecx
    c.jcc_rel(0x8E, "toa_empty")
    c.emit(b"\x8B\x55\x14")                                             # mov edx, [ebp+0x14] (lpString)
    c.emit(b"\x85\xD2")                                                 # test edx, edx
    c.jcc_rel(0x84, "toa_empty")
    c.emit(b"\x68\xFC\x03\x00\x00")                                     # push 1020
    c.emit(b"\x68" + struct.pack("<I", VA_WIDE_BUF))                    # push VA_WIDE_BUF
    c.emit(b"\x51")                                                     # push ecx (cbMultiByte)
    c.emit(b"\x52")                                                     # push edx (lpMultiByteStr)
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\x68\xB5\x03\x00\x00")                                     # push 949 (CP949 Korean)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_MultiByteToWideChar))
    c.emit(b"\x50")                                                     # push eax (wideLen)
    c.emit(b"\x68" + struct.pack("<I", VA_WIDE_BUF))                    # push VA_WIDE_BUF
    c.emit(b"\xFF\x75\x10")                                             # push y
    c.emit(b"\xFF\x75\x0C")                                             # push x
    c.emit(b"\xFF\x75\x08")                                             # push hdc
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_TEXTOUTW))
    c.emit(b"\x5D\xC2\x14\x00")                                         # pop ebp; ret 0x14
    c.mark("toa_empty")
    c.emit(b"\xB8\x01\x00\x00\x00")                                     # mov eax, 1
    c.emit(b"\x5D\xC2\x14\x00")                                         # pop ebp; ret 0x14

    va_my_gtep = c.label("MyGetTextExtentPoint32A")
    struct.pack_into("<I", c.buf, patch_gtep_pos, va_my_gtep)
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x8B\x4D\x10")                                             # mov ecx, [ebp+0x10] (c)
    c.emit(b"\x85\xC9")                                                 # test ecx, ecx
    c.jcc_rel(0x8E, "gtep_empty")
    c.emit(b"\x8B\x55\x0C")                                             # mov edx, [ebp+0x0C] (lpString)
    c.emit(b"\x85\xD2")                                                 # test edx, edx
    c.jcc_rel(0x84, "gtep_empty")
    c.emit(b"\x68\xFC\x03\x00\x00")                                     # push 1020
    c.emit(b"\x68" + struct.pack("<I", VA_WIDE_BUF))                    # push VA_WIDE_BUF
    c.emit(b"\x51")                                                     # push ecx (cbMultiByte)
    c.emit(b"\x52")                                                     # push edx (lpMultiByteStr)
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\x68\xB5\x03\x00\x00")                                     # push 949 (CP949 Korean)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_MultiByteToWideChar))
    c.emit(b"\xFF\x75\x14")                                             # push lpSize
    c.emit(b"\x50")                                                     # push eax (wideLen)
    c.emit(b"\x68" + struct.pack("<I", VA_WIDE_BUF))                    # push VA_WIDE_BUF
    c.emit(b"\xFF\x75\x08")                                             # push hdc
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTEXTEXTENTPOINT32W))
    c.emit(b"\x5D\xC2\x10\x00")                                         # pop ebp; ret 0x10
    c.mark("gtep_empty")
    c.emit(b"\x8B\x55\x14")                                             # mov edx, [ebp+0x14] (lpSize)
    c.emit(b"\x85\xD2")
    c.jcc_rel(0x84, "gtep_done")
    c.emit(b"\xC7\x02\x00\x00\x00\x00")                                 # mov dword ptr [edx], 0
    c.emit(b"\xC7\x42\x04\x00\x00\x00\x00")                             # mov dword ptr [edx+4], 0
    c.mark("gtep_done")
    c.emit(b"\xB8\x01\x00\x00\x00")                                     # mov eax, 1
    c.emit(b"\x5D\xC2\x10\x00")                                         # pop ebp; ret 0x10

    # =========================================================================
    # Helper: MyGetCursorPos(lpPoint) -> stdcall, ret 4
    # =========================================================================
    va_my_getcursorpos = c.label("MyGetCursorPos")
    struct.pack_into("<I", c.buf, patch_gcp_pos, va_my_getcursorpos)

    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi
    c.emit(b"\x8B\x75\x08")                                             # mov esi, [ebp+8] (lpPoint)
    c.emit(b"\x85\xF6")                                                 # test esi, esi
    c.jcc_rel(0x84, "gcp_fail")
    c.emit(b"\x56")                                                     # push esi
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_ORIG_GETCURSORPOS))
    c.emit(b"\x85\xC0")                                                 # test eax, eax
    c.jcc_rel(0x84, "gcp_use_cached")

    # Save latest raw cursor coordinates
    c.emit(b"\x8B\x06")                                                 # mov eax, [esi] (raw_x)
    c.emit(b"\x8B\x56\x04")                                             # mov edx, [esi+4] (raw_y)
    c.emit(b"\xA3" + struct.pack("<I", VA_LAST_RAW_X))                  # mov [VA_LAST_RAW_X], eax
    c.emit(b"\x89\x15" + struct.pack("<I", VA_LAST_RAW_Y))              # mov [VA_LAST_RAW_Y], edx

    # Map lpPoint->x
    c.emit(b"\x8B\x06")                                                 # mov eax, [esi] (raw_x)
    c.emit(b"\x2B\x05" + struct.pack("<I", VA_DST_X))                   # sub eax, [VA_DST_X]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x89, "gcp_x_pos")                                        # jns gcp_x_pos
    c.emit(b"\x31\xC0")                                                 # xor eax, eax
    c.mark("gcp_x_pos")
    c.emit(b"\x0F\xAF\x05" + struct.pack("<I", VA_G_WIDTH))             # imul eax, [VA_G_WIDTH]
    c.emit(b"\x31\xD2")                                                 # xor edx, edx
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_DST_W))                   # mov ecx, [VA_DST_W]
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x84, "gcp_save_x")
    c.emit(b"\xF7\xF1")                                                 # div ecx (eax = quotient)
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_G_WIDTH))
    c.emit(b"\x49")                                                     # dec ecx (g_width - 1)
    c.emit(b"\x39\xC8")                                                 # cmp eax, ecx
    c.jcc_rel(0x8E, "gcp_save_x")                                       # jle gcp_save_x
    c.emit(b"\x89\xC8")                                                 # mov eax, ecx
    c.mark("gcp_save_x")
    c.emit(b"\x89\x06")                                                 # mov [esi], eax
    c.emit(b"\xA3\x58\xCB\xC0\x00")                                     # mov [0x00C0CB58], eax (g_mouseX)

    # Map lpPoint->y
    c.emit(b"\x8B\x46\x04")                                             # mov eax, [esi+4] (raw_y)
    c.emit(b"\x2B\x05" + struct.pack("<I", VA_DST_Y))                   # sub eax, [VA_DST_Y]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x89, "gcp_y_pos")                                        # jns gcp_y_pos
    c.emit(b"\x31\xC0")                                                 # xor eax, eax
    c.mark("gcp_y_pos")
    c.emit(b"\x0F\xAF\x05" + struct.pack("<I", VA_G_HEIGHT))            # imul eax, [VA_G_HEIGHT]
    c.emit(b"\x31\xD2")                                                 # xor edx, edx
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_DST_H))                   # mov ecx, [VA_DST_H]
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x84, "gcp_save_y")
    c.emit(b"\xF7\xF1")                                                 # div ecx (eax = quotient)
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_G_HEIGHT))
    c.emit(b"\x49")                                                     # dec ecx (g_height - 1)
    c.emit(b"\x39\xC8")                                                 # cmp eax, ecx
    c.jcc_rel(0x8E, "gcp_save_y")                                       # jle gcp_save_y
    c.emit(b"\x89\xC8")                                                 # mov eax, ecx
    c.mark("gcp_save_y")
    c.emit(b"\x89\x46\x04")                                             # mov [esi+4], eax
    c.emit(b"\xA3\x5C\xCB\xC0\x00")                                     # mov [0x00C0CB5C], eax (g_mouseY)

    c.emit(b"\xB8\x01\x00\x00\x00")                                     # mov eax, 1
    c.emit(b"\x5F\x5E\x5B\x5D")                                         # pop edi; pop esi; pop ebx; pop ebp
    c.emit(b"\xC2\x04\x00")                                             # ret 4

    c.mark("gcp_use_cached")
    c.emit(b"\xA1" + struct.pack("<I", 0x00C0CB58))                     # mov eax, [0x00C0CB58] (g_mouseX)
    c.emit(b"\x89\x06")                                                 # mov [esi], eax
    c.emit(b"\xA1" + struct.pack("<I", 0x00C0CB5C))                     # mov eax, [0x00C0CB5C] (g_mouseY)
    c.emit(b"\x89\x46\x04")                                             # mov [esi+4], eax
    c.emit(b"\xB8\x01\x00\x00\x00")                                     # mov eax, 1
    c.emit(b"\x5F\x5E\x5B\x5D")
    c.emit(b"\xC2\x04\x00")

    c.mark("gcp_fail")
    c.emit(b"\x31\xC0")                                                 # xor eax, eax
    c.emit(b"\x5F\x5E\x5B\x5D")
    c.emit(b"\xC2\x04\x00")

    # =========================================================================
    # Helper: MyMouseMove -> naked hook from 0x0042434B
    # =========================================================================
    va_my_mousemove = c.label("MyMouseMove")
    struct.pack_into("<i", c.buf, patch_mouse_disp_pos, va_my_mousemove - (0x0042434B + 5))

    # Read lParam from [esp + 0x1C]
    c.emit(b"\x8B\x54\x24\x1C")                                         # mov edx, [esp+0x1C] (lParam)
    c.emit(b"\x0F\xBF\xCA")                                             # movsx ecx, dx (signed raw_x)
    c.emit(b"\xC1\xFA\x10")                                             # sar edx, 16 (signed raw_y)

    # Map raw_x in ecx to game_x
    c.emit(b"\x89\xC8")                                                 # mov eax, ecx
    c.emit(b"\x2B\x05" + struct.pack("<I", VA_DST_X))
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x89, "mm_x_pos")
    c.emit(b"\x31\xC0")
    c.mark("mm_x_pos")
    c.emit(b"\x0F\xAF\x05" + struct.pack("<I", VA_G_WIDTH))
    c.emit(b"\x52")                                                     # push edx (save raw_y)
    c.emit(b"\x31\xD2")
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_DST_W))
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x84, "mm_save_x")
    c.emit(b"\xF7\xF1")                                                 # div ecx
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_G_WIDTH))
    c.emit(b"\x49")                                                     # dec ecx (g_width - 1)
    c.emit(b"\x39\xC8")
    c.jcc_rel(0x8E, "mm_save_x")
    c.emit(b"\x89\xC8")
    c.mark("mm_save_x")
    c.emit(b"\x89\xC1")                                                 # mov ecx, eax (ecx = game_x)
    c.emit(b"\x5A")                                                     # pop edx (restore raw_y)

    # Map raw_y in edx to game_y
    c.emit(b"\x89\xD0")                                                 # mov eax, edx
    c.emit(b"\x2B\x05" + struct.pack("<I", VA_DST_Y))
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x89, "mm_y_pos")
    c.emit(b"\x31\xC0")
    c.mark("mm_y_pos")
    c.emit(b"\x0F\xAF\x05" + struct.pack("<I", VA_G_HEIGHT))
    c.emit(b"\x51")                                                     # push ecx (save game_x)
    c.emit(b"\x31\xD2")
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_DST_H))
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x84, "mm_save_y")
    c.emit(b"\xF7\xF1")                                                 # div ecx
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_G_HEIGHT))
    c.emit(b"\x49")                                                     # dec ecx (g_height - 1)
    c.emit(b"\x39\xC8")
    c.jcc_rel(0x8E, "mm_save_y")
    c.emit(b"\x89\xC8")
    c.mark("mm_save_y")
    # eax = game_y
    c.emit(b"\x59")                                                     # pop ecx (restore game_x)

    # Emulate original dawn.exe push sequence and save to globals
    c.emit(b"\x6A\x01")                                                 # push 1
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\x50")                                                     # push eax (game_y)
    c.emit(b"\x51")                                                     # push ecx (game_x)
    c.emit(b"\x6A\xFF")                                                 # push -1
    c.emit(b"\x6A\xFF")                                                 # push -1
    c.emit(b"\x89\x0D\x58\xCB\xC0\x00")                                 # mov [0x00C0CB58], ecx
    c.emit(b"\xA3\x5C\xCB\xC0\x00")                                     # mov [0x00C0CB5C], eax

    # Transfer control to 0x0042436F (call 0x4216b0) via jmp rel32
    c.emit(b"\xE9" + struct.pack("<i", 0x0042436F - (c.va + 5)))

    # =========================================================================
    # Helper: MySysKeyDown -> naked hook from 0x00424300 (WM_SYSKEYDOWN)
    # Allows Alt+F4 (VK_F4 = 0x73) to immediately destroy window and exit cleanly.
    # =========================================================================
    va_my_syskeydown = c.label("MySysKeyDown")
    struct.pack_into("<i", c.buf, patch_syskey_disp_pos, va_my_syskeydown - (0x00424300 + 5))

    c.emit(b"\x8B\x7C\x24\x18")                                         # mov edi, [esp+0x18] (wParam)
    c.emit(b"\x83\xFF\x73")                                             # cmp edi, 0x73 (VK_F4)
    c.jcc_rel(0x85, "syskey_not_f4")
    # DestroyWindow([0x00639348]) via IAT 0x004E51E0
    c.emit(b"\x66\xC7\x05\x18\xD8\x4E\x00\x0B\x00")                     # mov word ptr [0x004ED818], 0x0B
    c.emit(b"\xFF\x35\x48\x93\x63\x00")                                 # push dword ptr [0x00639348] (hWnd)
    c.emit(b"\xFF\x15\xE0\x51\x4E\x00")                                 # call dword ptr [0x004E51E0] (DestroyWindow)
    c.emit(b"\xE9" + struct.pack("<i", 0x00424343 - (c.va + 5)))        # jmp 0x00424343 (return 0)

    c.mark("syskey_not_f4")
    c.emit(b"\x83\xFF\x79")                                             # cmp edi, 0x79 (VK_F10)
    c.emit(b"\xE9" + struct.pack("<i", 0x00424307 - (c.va + 5)))        # jmp 0x00424307

    # =========================================================================
    # 4. Helper: PresentPrimary() -> cdecl, preserves ebx, esi, edi
    # =========================================================================
    c.label("PresentPrimary")
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi
    # Ensure game loop stays active and unpaused across state transitions
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00B643C8, 1))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x0066976C, 1))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00B64FE8, 0))
    c.emit(b"\x8B\x35" + struct.pack("<I", VA_G_PRIMARY))               # mov esi, [VA_G_PRIMARY]
    c.emit(b"\x85\xF6")                                                 # test esi, esi
    c.jcc_rel(0x84, "present_done")
    c.emit(b"\x8B\x1D" + struct.pack("<I", VA_G_HWND))                  # mov ebx, [VA_G_HWND]
    c.emit(b"\x85\xDB")                                                 # test ebx, ebx
    c.jcc_rel(0x84, "present_done")

    # Dynamic display resolution change detection
    c.emit(b"\x6A\x00")                                                 # push 0 (SM_CXSCREEN)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetSystemMetrics))
    c.emit(b"\x3B\x05" + struct.pack("<I", VA_SCREEN_W))
    c.jcc_rel(0x85, "present_res_changed")
    c.emit(b"\x6A\x01")                                                 # push 1 (SM_CYSCREEN)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetSystemMetrics))
    c.emit(b"\x3B\x05" + struct.pack("<I", VA_SCREEN_H))
    c.jcc_rel(0x84, "present_res_same")
    c.mark("present_res_changed")
    c.call_rel("UpdateScreenMetrics")
    # MoveWindow(ebx = g_hWnd, 0, 0, screen_w, screen_h, 1)
    c.emit(b"\x6A\x01")
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_H))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_W))
    c.emit(b"\x6A\x00")
    c.emit(b"\x6A\x00")
    c.emit(b"\x53")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_MoveWindow))
    c.mark("present_res_same")

    # GdiFlush()
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GDIFLUSH))

    # If bpp == 8: SetDIBColorTable(esi->memDC, 0, 256, VA_RGBQUADS)
    c.emit(b"\x83\x7E\x10\x08")                                         # cmp dword ptr [esi+0x10], 8
    c.jcc_rel(0x85, "present_blt")
    c.emit(b"\x68" + struct.pack("<I", VA_RGBQUADS))
    c.emit(b"\x68\x00\x01\x00\x00")                                     # push 256
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\xFF\x76\x18")                                             # push dword ptr [esi+0x18] (memDC)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_SETDIBCOLORTABLE))

    c.mark("present_blt")
    # edi = GetDC(g_hWnd)
    c.emit(b"\x53")                                                     # push ebx (g_hWnd)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetDC))
    c.emit(b"\x89\xC7")                                                 # mov edi, eax
    c.emit(b"\x85\xFF")                                                 # test edi, edi
    c.jcc_rel(0x84, "present_done")

    # Fill left/right pillarbox bars if dst_x > 0
    # Left bar: PatBlt(edi, 0, 0, dst_x, screen_h, BLACKNESS = 0x42)
    c.emit(b"\x8B\x05" + struct.pack("<I", VA_DST_X))                   # mov eax, [VA_DST_X]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x8E, "skip_pillarbox")
    c.emit(b"\x6A\x42")                                                 # push 0x42 (BLACKNESS)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_H))                # push [VA_SCREEN_H]
    c.emit(b"\x50")                                                     # push eax (dst_x)
    c.emit(b"\x6A\x00")                                                 # push 0 (y)
    c.emit(b"\x6A\x00")                                                 # push 0 (x)
    c.emit(b"\x57")                                                     # push edi (hdc)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_PATBLT))

    # Right bar: PatBlt(edi, dst_x + dst_w, 0, screen_w - (dst_x + dst_w), screen_h, BLACKNESS = 0x42)
    c.emit(b"\x8B\x05" + struct.pack("<I", VA_DST_X))
    c.emit(b"\x03\x05" + struct.pack("<I", VA_DST_W))                   # eax = dst_x + dst_w
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_SCREEN_W))
    c.emit(b"\x29\xC1")                                                 # ecx = screen_w - (dst_x + dst_w)
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x8E, "skip_pillarbox")
    c.emit(b"\x6A\x42")                                                 # push 0x42
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_H))
    c.emit(b"\x51")                                                     # push ecx (w)
    c.emit(b"\x6A\x00")                                                 # push 0 (y)
    c.emit(b"\x50")                                                     # push eax (x)
    c.emit(b"\x57")                                                     # push edi (hdc)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_PATBLT))
    c.mark("skip_pillarbox")

    # Fill top/bottom letterbox bars if dst_y > 0
    c.emit(b"\x8B\x05" + struct.pack("<I", VA_DST_Y))                   # mov eax, [VA_DST_Y]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x8E, "skip_letterbox")
    # Top bar
    c.emit(b"\x6A\x42")
    c.emit(b"\x50")                                                     # push eax (dst_y)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_W))
    c.emit(b"\x6A\x00")
    c.emit(b"\x6A\x00")
    c.emit(b"\x57")
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_PATBLT))
    # Bottom bar: PatBlt(edi, 0, dst_y + dst_h, screen_w, screen_h - (dst_y + dst_h), BLACKNESS)
    c.emit(b"\x8B\x05" + struct.pack("<I", VA_DST_Y))
    c.emit(b"\x03\x05" + struct.pack("<I", VA_DST_H))
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_SCREEN_H))
    c.emit(b"\x29\xC1")
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x8E, "skip_letterbox")
    c.emit(b"\x6A\x42")
    c.emit(b"\x51")                                                     # push ecx (h)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_W))                # push w
    c.emit(b"\x50")                                                     # push eax (y)
    c.emit(b"\x6A\x00")                                                 # push 0 (x)
    c.emit(b"\x57")                                                     # push edi
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_PATBLT))
    c.mark("skip_letterbox")

    # StretchBlt(edi, dst_x, dst_y, dst_w, dst_h, esi->memDC, 0, 0, wSrc, hSrc, SRCCOPY=0x00CC0020)
    c.emit(b"\x68\x20\x00\xCC\x00")                                     # push 0x00CC0020 (SRCCOPY)
    c.emit(b"\xFF\x76\x08")                                             # push [esi+8] (hSrc)
    c.emit(b"\xFF\x76\x04")                                             # push [esi+4] (wSrc)
    c.emit(b"\x6A\x00")                                                 # push 0 (ySrc)
    c.emit(b"\x6A\x00")                                                 # push 0 (xSrc)
    c.emit(b"\xFF\x76\x18")                                             # push [esi+0x18] (memDC)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DST_H))                   # push [VA_DST_H] (hDest)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DST_W))                   # push [VA_DST_W] (wDest)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DST_Y))                   # push [VA_DST_Y] (yDest)
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DST_X))                   # push [VA_DST_X] (xDest)
    c.emit(b"\x57")                                                     # push edi (hdcDest)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_StretchBlt))

    # ReleaseDC(g_hWnd, edi)
    c.emit(b"\x57")                                                     # push edi
    c.emit(b"\x53")                                                     # push ebx
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_ReleaseDC))

    c.mark("present_done")
    c.emit(b"\x5F\x5E\x5B")                                             # pop edi; pop esi; pop ebx
    c.emit(b"\xC3")                                                     # ret

    # =========================================================================
    # 5. Helper: CreateSurfaceObj(width, height, bpp, isPrimary) -> stdcall, ret 0x10
    # =========================================================================
    c.label("CreateSurfaceObj")
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi

    # VirtualAlloc(0, 64, 0x3000, 4) -> esi
    c.emit(b"\x6A\x04")
    c.emit(b"\x68\x00\x30\x00\x00")
    c.emit(b"\x6A\x40")
    c.emit(b"\x6A\x00")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_VirtualAlloc))
    c.emit(b"\x89\xC6")                                                 # mov esi, eax

    # vtable
    c.emit(b"\xC7\x06" + struct.pack("<I", VA_SURF_VTABLE))
    # width = max(1, [ebp+8])
    c.emit(b"\x8B\x45\x08")                                             # mov eax, [ebp+8]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x8F, "w_ok")
    c.emit(b"\xB8\x01\x00\x00\x00")
    c.mark("w_ok")
    c.emit(b"\x89\x46\x04")                                             # mov [esi+4], eax (width)

    # height = max(1, [ebp+0xC])
    c.emit(b"\x8B\x4D\x0C")                                             # mov ecx, [ebp+0xC]
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x8F, "h_ok")
    c.emit(b"\xB9\x01\x00\x00\x00")
    c.mark("h_ok")
    c.emit(b"\x89\x4E\x08")                                             # mov [esi+8], ecx (height)

    # bpp = [ebp+0x10]
    c.emit(b"\x8B\x55\x10")                                             # mov edx, [ebp+0x10]
    c.emit(b"\x89\x56\x10")                                             # mov [esi+0x10], edx (bpp)

    # pitch = ((width * (bpp >> 3)) + 3) & ~3
    c.emit(b"\xC1\xEA\x03")                                             # shr edx, 3
    c.emit(b"\x0F\xAF\xC2")                                             # imul eax, edx
    c.emit(b"\x83\xC0\x03")                                             # add eax, 3
    c.emit(b"\x83\xE0\xFC")                                             # and eax, ~3
    c.emit(b"\x89\x46\x0C")                                             # mov [esi+0xC], eax (pitch)

    # isPrimary = [ebp+0x14], default colorKeyLow = 0xFE
    c.emit(b"\x8B\x45\x14")
    c.emit(b"\x89\x46\x24")                                             # mov [esi+0x24], eax
    c.emit(b"\xC7\x46\x30\xFE\x00\x00\x00")                             # mov dword ptr [esi+0x30], 0xFE

    # memDC = CreateCompatibleDC(0)
    c.emit(b"\x6A\x00")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_CreateCompatibleDC))
    c.emit(b"\x89\x46\x18")                                             # mov [esi+0x18], eax (memDC)

    # Populate BITMAPINFO at VA_BMI_BUF
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_BMI_BUF + 0x00, 40))     # biSize = 40
    c.emit(b"\x8B\x46\x04")
    c.emit(b"\xA3" + struct.pack("<I", VA_BMI_BUF + 0x04))              # biWidth = width
    c.emit(b"\x8B\x46\x08")
    c.emit(b"\xF7\xD8")                                                 # neg eax (top-down DIB!)
    c.emit(b"\xA3" + struct.pack("<I", VA_BMI_BUF + 0x08))              # biHeight = -height
    c.emit(b"\x66\xC7\x05" + struct.pack("<IH", VA_BMI_BUF + 0x0C, 1))  # biPlanes = 1
    c.emit(b"\x8B\x46\x10")
    c.emit(b"\x66\xA3" + struct.pack("<I", VA_BMI_BUF + 0x0E))          # biBitCount = bpp
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_BMI_BUF + 0x10, 0))      # biCompression = BI_RGB

    # Copy 256 RGBQUADs from VA_RGBQUADS to VA_BMI_BUF + 40
    c.emit(b"\xFC")                                                     # cld
    c.emit(b"\x56")                                                     # push esi
    c.emit(b"\xBE" + struct.pack("<I", VA_RGBQUADS))
    c.emit(b"\xBF" + struct.pack("<I", VA_BMI_BUF + 40))
    c.emit(b"\xB9\x00\x01\x00\x00")                                     # mov ecx, 256
    c.emit(b"\xF3\xA5")                                                 # rep movsd
    c.emit(b"\x5E")                                                     # pop esi

    # CreateDIBSection(memDC, VA_BMI_BUF, 0, &esi->pBits, 0, 0)
    c.emit(b"\x6A\x00")                                                 # dwOffset = 0
    c.emit(b"\x6A\x00")                                                 # hSection = 0
    c.emit(b"\x8D\x46\x14")                                             # lea eax, [esi+0x14] (&pBits)
    c.emit(b"\x50")
    c.emit(b"\x6A\x00")                                                 # usage = DIB_RGB_COLORS (0)
    c.emit(b"\x68" + struct.pack("<I", VA_BMI_BUF))
    c.emit(b"\xFF\x76\x18")                                             # push [esi+0x18] (memDC)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_CREATEDIBSECTION))
    c.emit(b"\x89\x46\x1C")                                             # mov [esi+0x1C], eax (hDib)

    # SelectObject(memDC, hDib) -> oldBmp
    c.emit(b"\x50")                                                     # push eax (hDib)
    c.emit(b"\xFF\x76\x18")                                             # push [esi+0x18] (memDC)
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_SelectObject))
    c.emit(b"\x89\x46\x20")                                             # mov [esi+0x20], eax (oldBmp)

    c.emit(b"\x89\xF0")                                                 # mov eax, esi
    c.emit(b"\x5F\x5E\x5B")                                             # pop edi; pop esi; pop ebx
    c.emit(b"\x5D\xC2\x10\x00")                                         # pop ebp; ret 0x10

    # =========================================================================
    # 6. Helper: FreeSurfaceObj(surf) -> stdcall, ret 4
    # =========================================================================
    c.label("FreeSurfaceObj")
    c.emit(b"\x56")                                                     # push esi
    c.emit(b"\x8B\x74\x24\x08")                                         # mov esi, [esp+8]
    c.emit(b"\x85\xF6")
    c.jcc_rel(0x84, "free_surf_done")

    # SelectObject(memDC, oldBmp)
    c.emit(b"\xFF\x76\x20")
    c.emit(b"\xFF\x76\x18")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_SelectObject))

    # DeleteObject(hDib)
    c.emit(b"\xFF\x76\x1C")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_DeleteObject))

    # DeleteDC(memDC)
    c.emit(b"\xFF\x76\x18")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_DeleteDC))

    # VirtualFree(esi, 0, 0x8000 = MEM_RELEASE)
    c.emit(b"\x68\x00\x80\x00\x00")
    c.emit(b"\x6A\x00")
    c.emit(b"\x56")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_VirtualFree))

    c.mark("free_surf_done")
    c.emit(b"\x5E")                                                     # pop esi
    c.emit(b"\xC2\x04\x00")                                             # ret 4

    # =========================================================================
    # 7. Helper: UpdatePaletteEntries(start, count, lpEntries) -> stdcall, ret 0x0C
    # =========================================================================
    c.label("UpdatePaletteEntries")
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi
    c.emit(b"\x8B\x54\x24\x10")                                         # mov edx, [esp+0x10] (start)
    c.emit(b"\x8B\x4C\x24\x14")                                         # mov ecx, [esp+0x14] (count)
    c.emit(b"\x8B\x74\x24\x18")                                         # mov esi, [esp+0x18] (lpEntries)
    c.emit(b"\x85\xF6")
    c.jcc_rel(0x84, "pal_upd_done")
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x8E, "pal_upd_done")

    c.mark("pal_upd_loop")
    c.emit(b"\x81\xFA\x00\x01\x00\x00")                                 # cmp edx, 256
    c.jcc_rel(0x8D, "pal_upd_done")
    c.emit(b"\x8B\x06")                                                 # mov eax, [esi] (R, G, B, flags)
    c.emit(b"\x89\x04\x95" + struct.pack("<I", VA_PALENTRIES))          # mov [VA_PALENTRIES + edx*4], eax
    # Convert (R, G, B, flags) -> RGBQUAD (B, G, R, 0)
    c.emit(b"\x0F\xB6\x1E")                                             # movzx ebx, byte ptr [esi] (R)
    c.emit(b"\xC1\xE3\x10")                                             # shl ebx, 16
    c.emit(b"\x0F\xB6\x7E\x01")                                         # movzx edi, byte ptr [esi+1] (G)
    c.emit(b"\xC1\xE7\x08")                                             # shl edi, 8
    c.emit(b"\x09\xFB")                                                 # or ebx, edi
    c.emit(b"\x0F\xB6\x7E\x02")                                         # movzx edi, byte ptr [esi+2] (B)
    c.emit(b"\x09\xFB")                                                 # or ebx, edi
    c.emit(b"\x89\x1C\x95" + struct.pack("<I", VA_RGBQUADS))            # mov [VA_RGBQUADS + edx*4], ebx
    c.emit(b"\x83\xC6\x04")                                             # add esi, 4
    c.emit(b"\x42")                                                     # inc edx
    c.emit(b"\x49")                                                     # dec ecx
    c.jcc_rel(0x85, "pal_upd_loop")

    c.mark("pal_upd_done")
    c.emit(b"\x5F\x5E\x5B")
    c.emit(b"\xC2\x0C\x00")

    # =========================================================================
    # 8. IDirectDraw7 Vtable Methods
    # =========================================================================
    for nargs in (1, 2, 3, 4, 5, 6):
        c.label(f"Stub_Ret_{nargs*4}")
        c.emit(b"\x31\xC0")
        c.emit(b"\xC2" + struct.pack("<H", nargs * 4))

    # DD_QueryInterface(this, riid, ppvObj) -> E_NOINTERFACE (0x80004002)
    c.label("DD_QueryInterface")
    c.emit(b"\x8B\x44\x24\x0C")                                         # mov eax, [esp+0xC]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "qi_ret")
    c.emit(b"\xC7\x00\x00\x00\x00\x00")
    c.mark("qi_ret")
    c.emit(b"\xB8\x02\x40\x00\x80")                                     # mov eax, 0x80004002
    c.emit(b"\xC2\x0C\x00")

    # DD_AddRef(this) -> 1
    c.label("DD_AddRef")
    c.emit(b"\xB8\x01\x00\x00\x00")
    c.emit(b"\xC2\x04\x00")

    # DD_CreateClipper(this, dwFlags, lplpDDClipper, pUnkOuter) -> ret 0x10
    c.label("DD_CreateClipper")
    c.emit(b"\x8B\x44\x24\x0C")
    c.emit(b"\xC7\x00" + struct.pack("<I", VA_CLIP_OBJ))
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x10\x00")

    # DD_CreatePalette(this, dwFlags, lpDDColorArray, lplpDDPalette, pUnkOuter) -> ret 0x14
    c.label("DD_CreatePalette")
    c.emit(b"\xFF\x74\x24\x0C")                                         # push lpDDColorArray
    c.emit(b"\x68\x00\x01\x00\x00")                                     # push 256
    c.emit(b"\x6A\x00")                                                 # push 0
    c.call_rel("UpdatePaletteEntries")
    c.emit(b"\x8B\x44\x24\x10")                                         # mov eax, [esp+0x10] (lplpDDPalette)
    c.emit(b"\xC7\x00" + struct.pack("<I", VA_PAL_OBJ))
    c.call_rel("PresentPrimary")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x14\x00")

    # DD_CreateSurface(this, lpDDSD, lplpDDSurface, pUnkOuter) -> ret 0x10
    c.label("DD_CreateSurface")
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi
    c.emit(b"\x8B\x74\x24\x14")                                         # mov esi, [esp+0x14] (lpDDSD)
    c.emit(b"\x8B\x7C\x24\x18")                                         # mov edi, [esp+0x18] (lplpDDSurface)
    c.emit(b"\x8B\x46\x68")                                             # mov eax, [esi+0x68] (ddsCaps.dwCaps)
    c.emit(b"\xA9\x00\x02\x00\x00")                                     # test eax, 0x200 (DDSCAPS_PRIMARYSURFACE)
    c.jcc_rel(0x84, "create_offscreen")

    # Primary surface creation
    c.emit(b"\x6A\x01")                                                 # isPrimary = 1
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_BPP))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_HEIGHT))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_WIDTH))
    c.call_rel("CreateSurfaceObj")
    c.emit(b"\xA3" + struct.pack("<I", VA_G_PRIMARY))
    c.emit(b"\x89\x07")                                                 # mov [edi], eax
    c.emit(b"\x89\xC3")                                                 # mov ebx, eax

    # Also create attached backbuffer surface
    c.emit(b"\x6A\x00")                                                 # isPrimary = 0
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_BPP))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_HEIGHT))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_WIDTH))
    c.call_rel("CreateSurfaceObj")
    c.emit(b"\xA3" + struct.pack("<I", VA_G_BACK))
    c.emit(b"\x89\x43\x28")                                             # mov [ebx+0x28], eax (attachedBack)
    c.jmp_rel("create_surf_done")

    c.mark("create_offscreen")
    c.emit(b"\x6A\x00")                                                 # isPrimary = 0
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_BPP))
    c.emit(b"\xFF\x76\x08")                                             # push [esi+8] (dwHeight)
    c.emit(b"\xFF\x76\x0C")                                             # push [esi+0xC] (dwWidth)
    c.call_rel("CreateSurfaceObj")
    c.emit(b"\x89\x07")                                                 # mov [edi], eax

    c.mark("create_surf_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E\x5B")
    c.emit(b"\xC2\x10\x00")

    # DD_EnumDisplayModes(this, dwFlags, lpDDSD, lpContext, lpCallback) -> ret 0x14
    c.label("DD_EnumDisplayModes")
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi
    c.emit(b"\xBE" + struct.pack("<I", VA_MODE_TABLE))                  # mov esi, VA_MODE_TABLE
    c.emit(b"\xBB\x08\x00\x00\x00")                                     # mov ebx, 8 (8 modes)

    c.mark("enum_loop")
    # Zero VA_ENUM_DDSD (32 dwords)
    c.emit(b"\xFC")
    c.emit(b"\xBF" + struct.pack("<I", VA_ENUM_DDSD))
    c.emit(b"\xB9\x20\x00\x00\x00")
    c.emit(b"\x31\xC0")
    c.emit(b"\xF3\xAB")

    c.emit(b"\xC7\x05" + struct.pack("<II", VA_ENUM_DDSD + 0x00, 0x7C))  # dwSize = 0x7C
    c.emit(b"\x8B\x06")                                                 # mov eax, [esi] (width)
    c.emit(b"\xA3" + struct.pack("<I", VA_ENUM_DDSD + 0x0C))            # dwWidth
    c.emit(b"\x8B\x46\x04")                                             # mov eax, [esi+4] (height)
    c.emit(b"\xA3" + struct.pack("<I", VA_ENUM_DDSD + 0x08))            # dwHeight
    c.emit(b"\x8B\x46\x08")                                             # mov eax, [esi+8] (bpp)
    c.emit(b"\xA3" + struct.pack("<I", VA_ENUM_DDSD + 0x54))            # ddpfPixelFormat.dwRGBBitCount

    # Call lpCallback(VA_ENUM_DDSD, lpContext)
    c.emit(b"\xFF\x75\x14")                                             # push [ebp+0x14] (lpContext)
    c.emit(b"\x68" + struct.pack("<I", VA_ENUM_DDSD))
    c.emit(b"\xFF\x55\x18")                                             # call [ebp+0x18] (lpCallback)
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "enum_done")
    c.emit(b"\x83\xC6\x0C")                                             # add esi, 12
    c.emit(b"\x4B")                                                     # dec ebx
    c.jcc_rel(0x85, "enum_loop")

    c.mark("enum_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E\x5B\x5D")
    c.emit(b"\xC2\x14\x00")

    # DD_SetCooperativeLevel(this, hWnd, dwFlags) -> ret 0x0C
    c.label("DD_SetCooperativeLevel")
    c.emit(b"\x8B\x44\x24\x08")                                         # mov eax, [esp+8] (hWnd)
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "coop_skip")
    c.emit(b"\xA3" + struct.pack("<I", VA_G_HWND))
    c.call_rel("UpdateScreenMetrics")
    # MoveWindow(hWnd, 0, 0, screen_w, screen_h, 1)
    c.emit(b"\x6A\x01")
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_H))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_W))
    c.emit(b"\x6A\x00")
    c.emit(b"\x6A\x00")
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_G_HWND))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_MoveWindow))
    c.mark("coop_skip")
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x00B643C8, 1))
    c.emit(b"\xC7\x05" + struct.pack("<II", 0x0066976C, 1))
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x0C\x00")

    # DD_SetDisplayMode(this, w, h, bpp, refresh, flags) -> ret 0x18
    c.label("DD_SetDisplayMode")
    c.emit(b"\x8B\x44\x24\x08")
    c.emit(b"\xA3" + struct.pack("<I", VA_G_WIDTH))
    c.emit(b"\x8B\x4C\x24\x0C")
    c.emit(b"\x89\x0D" + struct.pack("<I", VA_G_HEIGHT))
    c.emit(b"\x8B\x54\x24\x10")
    c.emit(b"\x89\x15" + struct.pack("<I", VA_G_BPP))

    c.call_rel("UpdateScreenMetrics")

    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_G_HWND))
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x84, "mode_done")
    # MoveWindow(hWnd, 0, 0, screen_w, screen_h, 1)
    c.emit(b"\x6A\x01")
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_H))
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_SCREEN_W))
    c.emit(b"\x6A\x00")
    c.emit(b"\x6A\x00")
    c.emit(b"\x51")
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_MoveWindow))

    c.mark("mode_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x18\x00")

    # =========================================================================
    # 9. IDirectDrawSurface7 Vtable Methods
    # =========================================================================
    # Surf_Release(this) -> ret 4
    c.label("Surf_Release")
    c.emit(b"\x56")                                                     # push esi
    c.emit(b"\x8B\x74\x24\x08")                                         # mov esi, [esp+8] (this)
    c.emit(b"\x85\xF6")
    c.jcc_rel(0x84, "srel_done")

    # Is this == g_primary?
    c.emit(b"\x3B\x35" + struct.pack("<I", VA_G_PRIMARY))
    c.jcc_rel(0x85, "srel_check_back")
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_G_PRIMARY, 0))
    # Also free g_back if non-null
    c.emit(b"\xA1" + struct.pack("<I", VA_G_BACK))
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "srel_free_self")
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_G_BACK, 0))
    c.emit(b"\x50")
    c.call_rel("FreeSurfaceObj")
    c.jmp_rel("srel_free_self")

    c.mark("srel_check_back")
    c.emit(b"\x3B\x35" + struct.pack("<I", VA_G_BACK))
    c.jcc_rel(0x85, "srel_free_self")
    c.emit(b"\xC7\x05" + struct.pack("<II", VA_G_BACK, 0))

    c.mark("srel_free_self")
    c.emit(b"\x56")
    c.call_rel("FreeSurfaceObj")

    c.mark("srel_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5E")
    c.emit(b"\xC2\x04\x00")

    # Surf_Blt(this, lpDestRect, lpDDSrcSurface, lpSrcRect, dwFlags, lpDDBltFx) -> ret 0x18
    # Local frame:
    #   [ebp-4]:  dx0
    #   [ebp-8]:  dy0
    #   [ebp-12]: sx0
    #   [ebp-16]: sy0
    #   [ebp-20]: w
    #   [ebp-24]: h
    c.label("Surf_Blt")
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x83\xEC\x20")                                             # sub esp, 32
    c.emit(b"\x53\x56\x57")                                             # push ebx; push esi; push edi
    c.emit(b"\xFC")                                                     # cld

    c.emit(b"\x8B\x5D\x08")                                             # mov ebx, [ebp+8] (this = dst)
    c.emit(b"\x85\xDB")
    c.jcc_rel(0x84, "blt_exit")

    # Check DDBLT_COLORFILL (0x400)
    c.emit(b"\xF7\x45\x18\x00\x04\x00\x00")                             # test dword ptr [ebp+0x18], 0x400
    c.jcc_rel(0x84, "blt_check_src")

    # ColorFill: fill whole surface (or destRect) with [lpDDBltFx + 0x50]
    c.emit(b"\x31\xC0")                                                 # xor eax, eax
    c.emit(b"\x8B\x55\x1C")                                             # mov edx, [ebp+0x1C] (lpDDBltFx)
    c.emit(b"\x85\xD2")
    c.jcc_rel(0x84, "cf_have_color")
    c.emit(b"\x8B\x42\x50")                                             # mov eax, [edx+0x50] (dwFillColor)
    c.mark("cf_have_color")
    c.emit(b"\x8B\x7B\x14")                                             # mov edi, [ebx+0x14] (dst->pBits)
    c.emit(b"\x8B\x4B\x0C")                                             # mov ecx, [ebx+0x0C] (dst->pitch)
    c.emit(b"\x0F\xAF\x4B\x08")                                         # imul ecx, [ebx+0x08] (dst->height)
    c.emit(b"\xF3\xAA")                                                 # rep stosb
    c.jmp_rel("blt_maybe_present")

    c.mark("blt_check_src")
    c.emit(b"\x8B\x75\x10")                                             # mov esi, [ebp+0x10] (lpDDSrcSurface)
    c.emit(b"\x85\xF6")
    c.jcc_rel(0x84, "blt_maybe_present")

    # Determine sx0, sy0, w, h from lpSrcRect ([ebp+0x14]) or src dimensions
    c.emit(b"\x8B\x45\x14")                                             # mov eax, [ebp+0x14] (lpSrcRect)
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "blt_src_full")
    c.emit(b"\x8B\x10")                                                 # mov edx, [eax] (left)
    c.emit(b"\x89\x55\xF4")                                             # mov [ebp-12], edx (sx0)
    c.emit(b"\x8B\x48\x04")                                             # mov ecx, [eax+4] (top)
    c.emit(b"\x89\x4D\xF0")                                             # mov [ebp-16], ecx (sy0)
    c.emit(b"\x8B\x78\x08")                                             # mov edi, [eax+8] (right)
    c.emit(b"\x29\xD7")                                                 # sub edi, edx (w = right - left)
    c.emit(b"\x89\x7D\xEC")                                             # mov [ebp-20], edi (w)
    c.emit(b"\x8B\x78\x0C")                                             # mov edi, [eax+12] (bottom)
    c.emit(b"\x29\xCF")                                                 # sub edi, ecx (h = bottom - top)
    c.emit(b"\x89\x7D\xE8")                                             # mov [ebp-24], edi (h)
    c.jmp_rel("blt_dst_rect")

    c.mark("blt_src_full")
    c.emit(b"\xC7\x45\xF4\x00\x00\x00\x00")                             # sx0 = 0
    c.emit(b"\xC7\x45\xF0\x00\x00\x00\x00")                             # sy0 = 0
    c.emit(b"\x8B\x46\x04")
    c.emit(b"\x89\x45\xEC")                                             # w = src->width
    c.emit(b"\x8B\x46\x08")
    c.emit(b"\x89\x45\xE8")                                             # h = src->height

    c.mark("blt_dst_rect")
    c.emit(b"\x8B\x45\x0C")                                             # mov eax, [ebp+0x0C] (lpDestRect)
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "blt_dst_full")
    c.emit(b"\x8B\x10")
    c.emit(b"\x89\x55\xFC")                                             # dx0 = left
    c.emit(b"\x8B\x48\x04")
    c.emit(b"\x89\x4D\xF8")                                             # dy0 = top
    c.jmp_rel("blt_clamp")

    c.mark("blt_dst_full")
    c.emit(b"\xC7\x45\xFC\x00\x00\x00\x00")                             # dx0 = 0
    c.emit(b"\xC7\x45\xF8\x00\x00\x00\x00")                             # dy0 = 0

    c.mark("blt_clamp")
    # Clamp w to dst->width - dx0
    c.emit(b"\x8B\x43\x04")                                             # mov eax, [ebx+4] (dst->width)
    c.emit(b"\x2B\x45\xFC")                                             # sub eax, [ebp-4] (dx0)
    c.emit(b"\x39\x45\xEC")                                             # cmp [ebp-20], eax
    c.jcc_rel(0x8E, "clamp_w2")
    c.emit(b"\x89\x45\xEC")
    c.mark("clamp_w2")
    # Clamp h to dst->height - dy0
    c.emit(b"\x8B\x43\x08")                                             # mov eax, [ebx+8] (dst->height)
    c.emit(b"\x2B\x45\xF8")                                             # sub eax, [ebp-8] (dy0)
    c.emit(b"\x39\x45\xE8")                                             # cmp [ebp-24], eax
    c.jcc_rel(0x8E, "clamp_h2")
    c.emit(b"\x89\x45\xE8")
    c.mark("clamp_h2")

    c.emit(b"\x83\x7D\xEC\x00")                                         # cmp dword ptr [ebp-20], 0 (w <= 0?)
    c.jcc_rel(0x8E, "blt_maybe_present")
    c.emit(b"\x83\x7D\xE8\x00")                                         # cmp dword ptr [ebp-24], 0 (h <= 0?)
    c.jcc_rel(0x8E, "blt_maybe_present")

    # Compute bytesPerPixel = (dst->bpp >> 3)
    c.emit(b"\x8B\x4B\x10")                                             # mov ecx, [ebx+0x10] (dst->bpp)
    c.emit(b"\xC1\xE9\x03")                                             # shr ecx, 3

    # Compute srcRowPtr = src->pBits + sy0 * src->pitch + sx0 * bytesPerPixel
    c.emit(b"\x8B\x45\xF0")                                             # mov eax, [ebp-16] (sy0)
    c.emit(b"\x0F\xAF\x46\x0C")                                         # imul eax, [esi+0x0C] (src->pitch)
    c.emit(b"\x8B\x55\xF4")                                             # mov edx, [ebp-12] (sx0)
    c.emit(b"\x0F\xAF\xD1")                                             # imul edx, ecx
    c.emit(b"\x01\xD0")                                                 # add eax, edx
    c.emit(b"\x03\x46\x14")                                             # add eax, [esi+0x14] (src->pBits)
    c.emit(b"\x89\x45\xF4")                                             # [ebp-12] = srcRowPtr

    # Compute dstRowPtr = dst->pBits + dy0 * dst->pitch + dx0 * bytesPerPixel
    c.emit(b"\x8B\x45\xF8")                                             # mov eax, [ebp-8] (dy0)
    c.emit(b"\x0F\xAF\x43\x0C")                                         # imul eax, [ebx+0x0C] (dst->pitch)
    c.emit(b"\x8B\x55\xFC")                                             # mov edx, [ebp-4] (dx0)
    c.emit(b"\x0F\xAF\xD1")                                             # imul edx, ecx
    c.emit(b"\x01\xD0")                                                 # add eax, edx
    c.emit(b"\x03\x43\x14")                                             # add eax, [ebx+0x14] (dst->pBits)
    c.emit(b"\x89\x45\xFC")                                             # [ebp-4] = dstRowPtr

    # rowBytes = w * bytesPerPixel -> [ebp-20]
    c.emit(b"\x0F\xAF\x4D\xEC")                                         # imul ecx, [ebp-20]
    c.emit(b"\x89\x4D\xEC")                                             # [ebp-20] = rowBytes

    # Check if color key copy is needed: (dwFlags & 0x8000) and src->bpp == 8
    c.emit(b"\xF7\x45\x18\x00\x80\x00\x00")                             # test dword ptr [ebp+0x18], 0x8000
    c.jcc_rel(0x85, "blt_ckey_loop")

    # Fast row copy loop
    c.mark("blt_row_loop")
    c.emit(b"\x8B\x75\xF4")                                             # mov esi, [ebp-12] (srcRowPtr)
    c.emit(b"\x8B\x7D\xFC")                                             # mov edi, [ebp-4] (dstRowPtr)
    c.emit(b"\x8B\x4D\xEC")                                             # mov ecx, [ebp-20] (rowBytes)
    c.emit(b"\xF3\xA4")                                                 # rep movsb
    c.emit(b"\x8B\x55\x10")                                             # mov edx, [ebp+0x10] (src)
    c.emit(b"\x8B\x42\x0C")                                             # mov eax, [edx+0x0C] (src->pitch)
    c.emit(b"\x01\x45\xF4")                                             # add [ebp-12], eax
    c.emit(b"\x8B\x43\x0C")                                             # mov eax, [ebx+0x0C] (dst->pitch)
    c.emit(b"\x01\x45\xFC")                                             # add [ebp-4], eax
    c.emit(b"\xFF\x4D\xE8")                                             # dec dword ptr [ebp-24] (h)
    c.jcc_rel(0x85, "blt_row_loop")
    c.jmp_rel("blt_maybe_present")

    # Color-keyed 8-bit row copy loop
    c.mark("blt_ckey_loop")
    c.emit(b"\x8B\x55\x10")                                             # mov edx, [ebp+0x10] (src)
    c.emit(b"\x8A\x52\x30")                                             # mov dl, byte ptr [edx+0x30] (colorKeyLow)
    c.mark("ckey_row")
    c.emit(b"\x8B\x75\xF4")                                             # mov esi, [ebp-12]
    c.emit(b"\x8B\x7D\xFC")                                             # mov edi, [ebp-4]
    c.emit(b"\x8B\x4D\xEC")                                             # mov ecx, [ebp-20]
    c.mark("ckey_pix")
    c.emit(b"\x8A\x06")                                                 # mov al, [esi]
    c.emit(b"\x38\xD0")                                                 # cmp al, dl
    c.jcc_rel(0x84, "ckey_skip")
    c.emit(b"\x88\x07")                                                 # mov [edi], al
    c.mark("ckey_skip")
    c.emit(b"\x46\x47\x49")                                             # inc esi; inc edi; dec ecx
    c.jcc_rel(0x85, "ckey_pix")
    c.emit(b"\x8B\x45\x10")                                             # mov eax, [ebp+0x10] (src)
    c.emit(b"\x8B\x40\x0C")                                             # mov eax, [eax+0x0C] (src->pitch)
    c.emit(b"\x01\x45\xF4")                                             # add [ebp-12], eax
    c.emit(b"\x8B\x43\x0C")                                             # mov eax, [ebx+0x0C] (dst->pitch)
    c.emit(b"\x01\x45\xFC")                                             # add [ebp-4], eax
    c.emit(b"\xFF\x4D\xE8")                                             # dec dword ptr [ebp-24] (h)
    c.jcc_rel(0x85, "ckey_row")

    c.mark("blt_maybe_present")
    c.emit(b"\x3B\x1D" + struct.pack("<I", VA_G_PRIMARY))               # cmp ebx, [VA_G_PRIMARY]
    c.jcc_rel(0x85, "blt_exit")
    c.call_rel("PresentPrimary")

    c.mark("blt_exit")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E\x5B")
    c.emit(b"\x89\xEC\x5D")
    c.emit(b"\xC2\x18\x00")

    # Surf_BltFast(this, dwX, dwY, lpDDSrcSurface, lpSrcRect, dwTrans) -> ret 0x18
    c.label("Surf_BltFast")
    c.emit(b"\x55\x89\xE5")                                             # push ebp; mov ebp, esp
    c.emit(b"\x83\xEC\x10")                                             # sub esp, 16 (RECT at [ebp-16])
    c.emit(b"\x8B\x45\x0C")                                             # mov eax, [ebp+0x0C] (dwX)
    c.emit(b"\x89\x45\xF0")                                             # rect.left = dwX
    c.emit(b"\x8B\x4D\x10")                                             # mov ecx, [ebp+0x10] (dwY)
    c.emit(b"\x89\x4D\xF4")                                             # rect.top = dwY
    c.emit(b"\x31\xD2")                                                 # xor edx, edx
    c.emit(b"\xF6\x45\x1C\x01")                                         # test byte ptr [ebp+0x1C], 1 (DDBLTFAST_SRCCOLORKEY)
    c.jcc_rel(0x84, "bf_call")
    c.emit(b"\xBA\x00\x80\x00\x00")                                     # mov edx, 0x8000 (DDBLT_KEYSRC)
    c.mark("bf_call")
    c.emit(b"\x6A\x00")                                                 # lpDDBltFx = 0
    c.emit(b"\x52")                                                     # dwFlags = edx
    c.emit(b"\xFF\x75\x18")                                             # lpSrcRect
    c.emit(b"\xFF\x75\x14")                                             # lpDDSrcSurface
    c.emit(b"\x8D\x45\xF0")                                             # lea eax, [ebp-16] (&rect)
    c.emit(b"\x50")                                                     # lpDestRect
    c.emit(b"\xFF\x75\x08")                                             # this
    c.call_rel("Surf_Blt")
    c.emit(b"\x89\xEC\x5D")
    c.emit(b"\xC2\x18\x00")

    # Surf_Flip(this, lpDDSurfaceTargetOverride, dwFlags) -> ret 0x0C
    c.label("Surf_Flip")
    c.emit(b"\x56\x57")                                                 # push esi; push edi
    c.emit(b"\x8B\x7C\x24\x0C")                                         # mov edi, [esp+0x0C] (this)
    c.emit(b"\x3B\x3D" + struct.pack("<I", VA_G_PRIMARY))
    c.jcc_rel(0x85, "flip_done")
    c.emit(b"\x8B\x35" + struct.pack("<I", VA_G_BACK))
    c.emit(b"\x85\xF6")
    c.jcc_rel(0x84, "flip_done")
    c.emit(b"\xFC")
    c.emit(b"\x8B\x4F\x0C")                                             # mov ecx, [edi+0x0C] (pitch)
    c.emit(b"\x0F\xAF\x4F\x08")                                         # imul ecx, [edi+0x08] (height)
    c.emit(b"\xC1\xE9\x02")                                             # shr ecx, 2
    c.emit(b"\x8B\x76\x14")                                             # mov esi, [esi+0x14] (back->pBits)
    c.emit(b"\x8B\x7F\x14")                                             # mov edi, [edi+0x14] (pri->pBits)
    c.emit(b"\xF3\xA5")                                                 # rep movsd
    c.call_rel("PresentPrimary")
    c.mark("flip_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E")
    c.emit(b"\xC2\x0C\x00")

    # Surf_GetAttachedSurface(this, lpDDSCaps2, lplpDDAttachedSurface) -> ret 0x0C
    c.label("Surf_GetAttachedSurface")
    c.emit(b"\x8B\x44\x24\x0C")                                         # mov eax, [esp+0x0C]
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_G_BACK))
    c.emit(b"\x89\x08")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x0C\x00")

    # Surf_GetDC(this, lphDC) -> ret 8
    c.label("Surf_GetDC")
    c.emit(b"\x56")                                                     # push esi
    c.emit(b"\x8B\x74\x24\x08")                                         # mov esi, [esp+8] (this)
    c.emit(b"\x83\x7E\x10\x08")                                         # cmp dword ptr [esi+0x10], 8
    c.jcc_rel(0x85, "getdc_ret")
    c.emit(b"\x68" + struct.pack("<I", VA_RGBQUADS))
    c.emit(b"\x68\x00\x01\x00\x00")                                     # push 256
    c.emit(b"\x6A\x00")                                                 # push 0
    c.emit(b"\xFF\x76\x18")                                             # push dword ptr [esi+0x18] (memDC)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_SETDIBCOLORTABLE))
    c.mark("getdc_ret")
    c.emit(b"\x8B\x44\x24\x0C")                                         # mov eax, [esp+0x0C] (lphDC)
    c.emit(b"\x8B\x4E\x18")                                             # mov ecx, [esi+0x18] (memDC)
    c.emit(b"\x89\x08")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5E")
    c.emit(b"\xC2\x08\x00")

    # Surf_GetPixelFormat(this, lpDDPixelFormat) -> ret 8
    c.label("Surf_GetPixelFormat")
    c.emit(b"\x56\x57")                                                 # push esi; push edi
    c.emit(b"\x8B\x74\x24\x0C")                                         # mov esi, [esp+0x0C] (this)
    c.emit(b"\x8B\x7C\x24\x10")                                         # mov edi, [esp+0x10] (lpDDPixelFormat)
    c.emit(b"\xFC")
    c.emit(b"\x89\xFA")                                                 # mov edx, edi
    c.emit(b"\xB9\x08\x00\x00\x00")                                     # mov ecx, 8
    c.emit(b"\x31\xC0")
    c.emit(b"\xF3\xAB")
    c.emit(b"\x89\xD7")                                                 # mov edi, edx
    c.emit(b"\xC7\x07\x20\x00\x00\x00")                                 # dwSize = 0x20
    c.emit(b"\x8B\x46\x10")                                             # mov eax, [esi+0x10] (bpp)
    c.emit(b"\x89\x47\x0C")                                             # dwRGBBitCount = bpp
    c.emit(b"\x83\xF8\x08")
    c.jcc_rel(0x85, "pf_16")
    c.emit(b"\xC7\x47\x04\x20\x00\x00\x00")                             # dwFlags = 0x20 (DDPF_PALETTEINDEXED8)
    c.jmp_rel("pf_done")
    c.mark("pf_16")
    c.emit(b"\xC7\x47\x04\x40\x00\x00\x00")                             # dwFlags = 0x40 (DDPF_RGB)
    c.emit(b"\xC7\x47\x10\x00\x7C\x00\x00")                             # R mask = 0x7C00
    c.emit(b"\xC7\x47\x14\xE0\x03\x00\x00")                             # G mask = 0x03E0
    c.emit(b"\xC7\x47\x18\x1F\x00\x00\x00")                             # B mask = 0x001F
    c.mark("pf_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E")
    c.emit(b"\xC2\x08\x00")

    # Surf_Lock(this, lpDestRect, lpDDSD, dwFlags, hEvent) -> ret 0x14
    c.label("Surf_Lock")
    c.emit(b"\x56\x57")                                                 # push esi; push edi
    c.emit(b"\x8B\x74\x24\x0C")                                         # mov esi, [esp+0x0C] (this)
    c.emit(b"\x8B\x7C\x24\x14")                                         # mov edi, [esp+0x14] (lpDDSD)
    c.emit(b"\xC7\x47\x04\x0F\x10\x00\x00")                             # dwFlags = 0x100F
    c.emit(b"\x8B\x46\x08")
    c.emit(b"\x89\x47\x08")                                             # dwHeight
    c.emit(b"\x8B\x46\x04")
    c.emit(b"\x89\x47\x0C")                                             # dwWidth
    c.emit(b"\x8B\x46\x0C")
    c.emit(b"\x89\x47\x10")                                             # lPitch
    c.emit(b"\x8B\x46\x14")
    c.emit(b"\x89\x47\x24")                                             # lpSurface = pBits
    c.emit(b"\x8B\x46\x10")
    c.emit(b"\x89\x47\x54")                                             # ddpfPixelFormat.dwRGBBitCount
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E")
    c.emit(b"\xC2\x14\x00")

    # Surf_ReleaseDC(this, hDC) -> ret 8
    c.label("Surf_ReleaseDC")
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GDIFLUSH))
    c.emit(b"\x8B\x44\x24\x04")                                         # mov eax, [esp+4] (this)
    c.emit(b"\x3B\x05" + struct.pack("<I", VA_G_PRIMARY))
    c.jcc_rel(0x85, "reldc_done")
    c.call_rel("PresentPrimary")
    c.mark("reldc_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x08\x00")

    # Surf_SetColorKey(this, dwFlags, lpDDColorKey) -> ret 0x0C
    c.label("Surf_SetColorKey")
    c.emit(b"\x8B\x44\x24\x04")                                         # mov eax, [esp+4] (this)
    c.emit(b"\x8B\x4C\x24\x0C")                                         # mov ecx, [esp+0x0C] (lpDDColorKey)
    c.emit(b"\x85\xC9")
    c.jcc_rel(0x84, "sck_done")
    c.emit(b"\xC7\x40\x2C\x01\x00\x00\x00")                             # hasColorKey = 1
    c.emit(b"\x8B\x11")                                                 # mov edx, [ecx]
    c.emit(b"\x89\x50\x30")                                             # colorKeyLow = edx
    c.mark("sck_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x0C\x00")

    # Surf_Unlock_Or_SetPalette(this, arg) -> ret 8
    c.label("Surf_Unlock")
    c.emit(b"\x8B\x44\x24\x04")                                         # mov eax, [esp+4] (this)
    c.emit(b"\x3B\x05" + struct.pack("<I", VA_G_PRIMARY))
    c.jcc_rel(0x85, "unlock_done")
    c.call_rel("PresentPrimary")
    c.mark("unlock_done")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x08\x00")

    # =========================================================================
    # 10. IDirectDrawPalette Vtable Methods
    # =========================================================================
    # Pal_GetEntries(this, dwFlags, dwBase, dwNumEntries, lpEntries) -> ret 0x14
    c.label("Pal_GetEntries")
    c.emit(b"\x56\x57")
    c.emit(b"\xFC")
    c.emit(b"\x8B\x54\x24\x10")                                         # mov edx, [esp+0x10] (dwBase)
    c.emit(b"\x8B\x4C\x24\x14")                                         # mov ecx, [esp+0x14] (dwNumEntries)
    c.emit(b"\x8B\x7C\x24\x18")                                         # mov edi, [esp+0x18] (lpEntries)
    c.emit(b"\x8D\x34\x95" + struct.pack("<I", VA_PALENTRIES))          # lea esi, [VA_PALENTRIES + edx*4]
    c.emit(b"\xF3\xA5")                                                 # rep movsd
    c.emit(b"\x31\xC0")
    c.emit(b"\x5F\x5E")
    c.emit(b"\xC2\x14\x00")

    # Pal_SetEntries(this, dwFlags, dwStartingEntry, dwCount, lpEntries) -> ret 0x14
    c.label("Pal_SetEntries")
    c.emit(b"\xFF\x74\x24\x14")                                         # push lpEntries
    c.emit(b"\xFF\x74\x24\x14")                                         # push dwCount
    c.emit(b"\xFF\x74\x24\x14")                                         # push dwStartingEntry
    c.call_rel("UpdatePaletteEntries")
    c.call_rel("PresentPrimary")
    c.emit(b"\x31\xC0")
    c.emit(b"\xC2\x14\x00")

    raw_code = c.resolve()

    # Verify with Capstone that all instructions decode cleanly
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoded = list(md.disasm(raw_code, TEXT_VA))
    assert len(decoded) > 100, "Failed to disassemble generated code"
    return raw_code, c.labels


def build_pe_dll() -> bytes:
    code_bytes, labels = build_code()
    assert len(code_bytes) < 0x1800, f"Code size {len(code_bytes)} exceeds export area limit"

    # Build Export Directory in .text at offset 0x1800 (RVA 0x2800)
    text_sec = bytearray(0x2000)
    text_sec[: len(code_bytes)] = code_bytes

    exp_rva = TEXT_RVA + 0x1800
    dll_name_rva = exp_rva + 0x40
    func_name_rva = exp_rva + 0x60
    eat_rva = exp_rva + 0x80
    name_ptr_rva = exp_rva + 0x84
    ord_rva = exp_rva + 0x88

    init_asi_rva = labels["InitializeASI"] - IMAGE_BASE

    # IMAGE_EXPORT_DIRECTORY (40 bytes)
    exp_dir = struct.pack(
        "<IIHHIIIIIII",
        0,                  # Characteristics
        0,                  # TimeDateStamp
        0,                  # MajorVersion
        0,                  # MinorVersion
        dll_name_rva,       # Name
        1,                  # Base
        1,                  # NumberOfFunctions
        1,                  # NumberOfNames
        eat_rva,            # AddressOfFunctions
        name_ptr_rva,       # AddressOfNames
        ord_rva,            # AddressOfNameOrdinals
    )
    text_sec[0x1800 : 0x1800 + 40] = exp_dir
    text_sec[0x1840 : 0x1840 + 15] = b"parsec_gdi.asi\x00"
    text_sec[0x1860 : 0x1860 + 14] = b"InitializeASI\x00"
    struct.pack_into("<I", text_sec, 0x1880, init_asi_rva)
    struct.pack_into("<I", text_sec, 0x1884, func_name_rva)
    struct.pack_into("<H", text_sec, 0x1888, 0)

    # Build .data section (0x2000 bytes, RVA 0x3000)
    data_sec = bytearray(0x2000)
    struct.pack_into("<I", data_sec, 0x0000, VA_DD_VTABLE)
    struct.pack_into("<I", data_sec, 0x0004, VA_PAL_VTABLE)
    struct.pack_into("<I", data_sec, 0x0008, VA_CLIP_VTABLE)
    struct.pack_into("<I", data_sec, 0x0014, 640)   # default g_width
    struct.pack_into("<I", data_sec, 0x0018, 480)   # default g_height
    struct.pack_into("<I", data_sec, 0x001C, 8)     # default g_bpp

    # Initialize default screen metrics (1360x768 pillarboxed to 1024x768 at x=168)
    struct.pack_into("<I", data_sec, 0x0048, 1360)  # VA_SCREEN_W
    struct.pack_into("<I", data_sec, 0x004C, 768)   # VA_SCREEN_H
    struct.pack_into("<I", data_sec, 0x0050, 168)   # VA_DST_X
    struct.pack_into("<I", data_sec, 0x0054, 0)     # VA_DST_Y
    struct.pack_into("<I", data_sec, 0x0058, 1024)  # VA_DST_W
    struct.pack_into("<I", data_sec, 0x005C, 768)   # VA_DST_H

    # Populate ddVtable (32 entries at offset 0x0100)
    dd_vt = [labels["Stub_Ret_4"]] * 32
    dd_vt[0x00 // 4] = labels["DD_QueryInterface"]
    dd_vt[0x04 // 4] = labels["DD_AddRef"]
    dd_vt[0x08 // 4] = labels["Stub_Ret_4"]         # Release
    dd_vt[0x10 // 4] = labels["DD_CreateClipper"]
    dd_vt[0x14 // 4] = labels["DD_CreatePalette"]
    dd_vt[0x18 // 4] = labels["DD_CreateSurface"]
    dd_vt[0x20 // 4] = labels["DD_EnumDisplayModes"]
    dd_vt[0x28 // 4] = labels["Stub_Ret_4"]         # FlipToGDISurface
    dd_vt[0x50 // 4] = labels["DD_SetCooperativeLevel"]
    dd_vt[0x54 // 4] = labels["DD_SetDisplayMode"]
    dd_vt[0x58 // 4] = labels["Stub_Ret_12"]        # WaitForVerticalBlank
    dd_vt[0x64 // 4] = labels["Stub_Ret_4"]         # RestoreAllSurfaces
    for idx, fn_va in enumerate(dd_vt):
        struct.pack_into("<I", data_sec, 0x0100 + idx * 4, fn_va)

    # Populate surfVtable (40 entries at offset 0x0180)
    surf_vt = [labels["Stub_Ret_4"]] * 40
    surf_vt[0x00 // 4] = labels["DD_QueryInterface"]
    surf_vt[0x04 // 4] = labels["DD_AddRef"]
    surf_vt[0x08 // 4] = labels["Surf_Release"]
    surf_vt[0x14 // 4] = labels["Surf_Blt"]
    surf_vt[0x1C // 4] = labels["Surf_BltFast"]
    surf_vt[0x28 // 4] = labels["Surf_Flip"]
    surf_vt[0x30 // 4] = labels["Surf_GetAttachedSurface"]
    surf_vt[0x44 // 4] = labels["Surf_GetDC"]
    surf_vt[0x58 // 4] = labels["Surf_GetPixelFormat"]
    surf_vt[0x64 // 4] = labels["Surf_Lock"]
    surf_vt[0x68 // 4] = labels["Surf_ReleaseDC"]
    surf_vt[0x6C // 4] = labels["Stub_Ret_4"]       # Restore
    surf_vt[0x70 // 4] = labels["Stub_Ret_8"]       # SetClipper
    surf_vt[0x74 // 4] = labels["Surf_SetColorKey"]
    surf_vt[0x7C // 4] = labels["Surf_Unlock"]      # SetPalette
    surf_vt[0x80 // 4] = labels["Surf_Unlock"]      # Unlock
    for idx, fn_va in enumerate(surf_vt):
        struct.pack_into("<I", data_sec, 0x0180 + idx * 4, fn_va)

    # Populate palVtable (16 entries at offset 0x0220)
    pal_vt = [labels["Stub_Ret_4"]] * 16
    pal_vt[0x00 // 4] = labels["DD_QueryInterface"]
    pal_vt[0x04 // 4] = labels["DD_AddRef"]
    pal_vt[0x08 // 4] = labels["Stub_Ret_4"]        # Release
    pal_vt[0x10 // 4] = labels["Pal_GetEntries"]
    pal_vt[0x18 // 4] = labels["Pal_SetEntries"]
    for idx, fn_va in enumerate(pal_vt):
        struct.pack_into("<I", data_sec, 0x0220 + idx * 4, fn_va)

    # Populate clipVtable (16 entries at offset 0x0260)
    clip_vt = [labels["Stub_Ret_4"]] * 16
    clip_vt[0x00 // 4] = labels["DD_QueryInterface"]
    clip_vt[0x04 // 4] = labels["DD_AddRef"]
    clip_vt[0x08 // 4] = labels["Stub_Ret_4"]       # Release
    clip_vt[0x20 // 4] = labels["Stub_Ret_12"]      # SetHWnd
    for idx, fn_va in enumerate(clip_vt):
        struct.pack_into("<I", data_sec, 0x0260 + idx * 4, fn_va)

    # Populate mode table at offset 0x0300 (8 modes * 12 bytes)
    modes = [
        (320, 200, 8),
        (640, 480, 8),
        (640, 480, 16),
        (800, 600, 8),
        (800, 600, 16),
        (1024, 768, 8),
        (1024, 768, 16),
        (1280, 1024, 8),
    ]
    for idx, (w, h, bpp) in enumerate(modes):
        struct.pack_into("<III", data_sec, 0x0300 + idx * 12, w, h, bpp)

    # Populate strings at offset 0x1200
    def put_str(off: int, s: bytes) -> None:
        data_sec[off : off + len(s)] = s

    put_str(0x1200, b"KERNEL32.dll\x00")
    put_str(0x1210, b"VirtualProtect\x00")
    put_str(0x1224, b"GDI32.dll\x00")
    put_str(0x1230, b"CreateDIBSection\x00")
    put_str(0x1244, b"SetDIBColorTable\x00")
    put_str(0x1258, b"GdiFlush\x00")
    put_str(0x1268, b"PatBlt\x00")
    put_str(0x1278, b"CreateFontW\x00")
    put_str(0x1288, b"TextOutW\x00")
    put_str(0x1298, b"GetTextExtentPoint32W\x00")

    # Build PE Headers (0x400 bytes raw size, 0x1000 virtual alignment)
    headers = bytearray(0x400)
    # DOS Header
    headers[0:2] = b"MZ"
    struct.pack_into("<I", headers, 0x3C, 0x80)  # e_lfanew = 0x80

    # PE Signature + COFF File Header at 0x80
    pe_off = 0x80
    headers[pe_off : pe_off + 4] = b"PE\x00\x00"
    struct.pack_into(
        "<HHIIIHH",
        headers,
        pe_off + 4,
        0x014C,         # Machine = IMAGE_FILE_MACHINE_I386
        2,              # NumberOfSections = 2 (.text, .data)
        0,              # TimeDateStamp
        0,              # PointerToSymbolTable
        0,              # NumberOfSymbols
        0xE0,           # SizeOfOptionalHeader
        0x210E,         # Characteristics (EXECUTABLE_IMAGE | LINE_NUMS_STRIPPED | LOCAL_SYMS_STRIPPED | 32BIT_MACHINE | DLL)
    )

    opt_off = pe_off + 24
    entry_rva = labels["DllMain"] - IMAGE_BASE
    struct.pack_into(
        "<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII",
        headers,
        opt_off,
        0x010B,         # Magic = PE32
        14,             # MajorLinkerVersion
        0,              # MinorLinkerVersion
        0x2000,         # SizeOfCode
        0x2000,         # SizeOfInitializedData
        0,              # SizeOfUninitializedData
        entry_rva,      # AddressOfEntryPoint
        TEXT_RVA,       # BaseOfCode
        DATA_RVA,       # BaseOfData
        IMAGE_BASE,     # ImageBase
        0x1000,         # SectionAlignment
        0x0200,         # FileAlignment
        4,              # MajorOperatingSystemVersion
        0,              # MinorOperatingSystemVersion
        0,              # MajorImageVersion
        0,              # MinorImageVersion
        4,              # MajorSubsystemVersion
        0,              # MinorSubsystemVersion
        0,              # Win32VersionValue
        0x5000,         # SizeOfImage
        0x0400,         # SizeOfHeaders
        0,              # CheckSum
        2,              # Subsystem = IMAGE_SUBSYSTEM_WINDOWS_GUI
        0,              # DllCharacteristics (0 = fixed base, no ASLR)
        0x100000,       # SizeOfStackReserve
        0x1000,         # SizeOfStackCommit
        0x100000,       # SizeOfHeapReserve
        0x1000,         # SizeOfHeapCommit
        0,              # LoaderFlags
        16,             # NumberOfRvaAndSizes
    )

    # Data Directory 0: Export Table
    dd_off = opt_off + 96
    struct.pack_into("<II", headers, dd_off + 0, exp_rva, 0x100)

    # Section Headers at opt_off + 0xE0
    sec_off = opt_off + 0xE0
    # Section 0: .text
    struct.pack_into(
        "<8sIIIIIIHHI",
        headers,
        sec_off,
        b".text\x00\x00\x00",
        0x2000,         # VirtualSize
        TEXT_RVA,       # VirtualAddress
        0x2000,         # SizeOfRawData
        0x0400,         # PointerToRawData
        0, 0, 0, 0,
        0x60000020,     # IMAGE_SCN_CNT_CODE | IMAGE_SCN_MEM_EXECUTE | IMAGE_SCN_MEM_READ
    )
    # Section 1: .data
    struct.pack_into(
        "<8sIIIIIIHHI",
        headers,
        sec_off + 40,
        b".data\x00\x00\x00",
        0x2000,         # VirtualSize
        DATA_RVA,       # VirtualAddress
        0x2000,         # SizeOfRawData
        0x2400,         # PointerToRawData
        0, 0, 0, 0,
        0xC0000040,     # IMAGE_SCN_CNT_INITIALIZED_DATA | IMAGE_SCN_MEM_READ | IMAGE_SCN_MEM_WRITE
    )

    return bytes(headers + text_sec + data_sec)


def main() -> None:
    out_path = Path(__file__).resolve().parents[2] / "YM" / "dawn" / "parsec_gdi.asi"
    dll_bytes = build_pe_dll()
    out_path.write_bytes(dll_bytes)
    print(f"Built {out_path} ({len(dll_bytes)} bytes)")


if __name__ == "__main__":
    main()
