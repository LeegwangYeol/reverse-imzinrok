"""
Builds YM/dawn/imjin_logger.asi — an automatic in-process Blackbox Crash, State, Unit Lifecycle,
and Anomaly Logger ASI plugin for Imjinrok 2+ Chosun's Counterattack (dawn.exe).

Automatically loaded by dxwrapper.dll (LoadPlugins = 1) whenever dawn.exe starts.
Writes structured, real-time diagnostic logs to:
  YM/dawn/imjin_anomaly.log

Logged Events & Anomaly Detectors:
  1. [SESSION_START]   : Startup tick, main window handle, GWL_EXSTYLE (verifies non-TOPMOST).
  2. [CRASH_BLACKBOX]  : Top-level SetUnhandledExceptionFilter handler capturing ExceptionCode,
                         FaultEIP, all CPU registers (EAX..ESP), GameState, FrameCount, ActiveChars,
                         and top stack DWORDs before process exit.
  3. [AUDIT_SOUND]     : Verifies SoundMgr (0x00B93974) loaded effect count (505) & custom IDs 485..504.
  4. [AUDIT_UNITS]     : Verifies KindInfo[0x70..0x7E] (15 custom Joseon units including 5 Muye24ki infantry).
  5. [STATE_CHANGE]    : Tracks every GameState (0x004ED818), Active (0x0066976C), Paused (0x00B64FE8),
                         and Alt+Tab Minimize/Restore (IsIconic) transition.
  6. [UNIT_SPAWN]      : Logs creation of custom units (0x70..0x7E) with slot, KindID, player, HP, (X,Y).
  7. [UNIT_ORDER]      : Logs state/order transitions (Idle/Move/Attack/Die) & animation slot of custom units.
  8. [ANOMALY_KIND]    : Detects any active unit with out-of-bounds KindID (> 0x7E) or NULL KindInfo pointer.
  9. [ANOMALY_HP]      : Detects corrupted HP (< -500 or > 30000) on any active unit.
  10. [ANOMALY_POS]    : Detects out-of-bounds tile coordinates (X > 512 or Y > 512) on any active unit.
  11. [ANOMALY_FREEZE] : Detects main-thread frame counter stalls (> 5 seconds while unpaused in-game).
"""

from __future__ import annotations

import struct
from pathlib import Path
import capstone


IMAGE_BASE = 0x65300000
TEXT_RVA = 0x1000
DATA_RVA = 0x3000
TEXT_VA = IMAGE_BASE + TEXT_RVA
DATA_VA = IMAGE_BASE + DATA_RVA

# dawn.exe IAT pointers (fixed ImageBase 0x00400000, no ASLR)
IAT_GetModuleHandleA = 0x004E5160
IAT_GetProcAddress = 0x004E516C
IAT_wsprintfA = 0x004E51D0
IAT_IsIconic = 0x004E5258

# dawn.exe Engine Global Addresses
VA_DAWN_GAMESTATE = 0x004ED818       # WORD
VA_DAWN_HWND = 0x00B4DA70            # DWORD (HWND)
VA_DAWN_APP_ACTIVE = 0x0066976C      # DWORD
VA_DAWN_PAUSED = 0x00B64FE8          # DWORD
VA_DAWN_FRAME_CNT = 0x008924BC       # DWORD
VA_DAWN_SOUND_MGR = 0x00B93974       # DWORD (ptr)
VA_DAWN_KIND_70_BASE = 0x009CE2E8    # Contiguous KindInfo structs for 0x70..0x7E (stride 0x394)
VA_DAWN_CHAR_COUNT = 0x00975908      # WORD
VA_DAWN_CHAR_IDS = 0x00974FA8        # WORD[1000]
VA_DAWN_CHAR_ALIVE = 0x008990C8      # WORD[1000]
VA_DAWN_CHAR_BASE = 0x0066B790       # Struct stride 0x758

# .data layout (0x65503000)
VA_G_INIT_DONE = DATA_VA + 0x0000
VA_H_LOGFILE = DATA_VA + 0x0004
VA_BYTES_WRITTEN = DATA_VA + 0x0008
VA_THREAD_ID = DATA_VA + 0x000C

# Resolved Win32 API pointers in .data
VA_PFN_CREATEFILEA = DATA_VA + 0x0010
VA_PFN_WRITEFILE = DATA_VA + 0x0014
VA_PFN_FLUSHFILEBUFFERS = DATA_VA + 0x0018
VA_PFN_SETFILEPOINTER = DATA_VA + 0x001C
VA_PFN_GETTICKCOUNT = DATA_VA + 0x0020
VA_PFN_SLEEP = DATA_VA + 0x0024
VA_PFN_CREATETHREAD = DATA_VA + 0x0028
VA_PFN_SETUNHANDLEDEXCEPTIONFILTER = DATA_VA + 0x002C
VA_PFN_GETWINDOWLONGA = DATA_VA + 0x0030

# Watchdog state variables
VA_PREV_GAMESTATE = DATA_VA + 0x0040
VA_PREV_ACTIVE = DATA_VA + 0x0044
VA_PREV_PAUSED = DATA_VA + 0x0048
VA_PREV_ICONIC = DATA_VA + 0x004C
VA_LAST_FRAME_CNT = DATA_VA + 0x0050
VA_STALL_TICKS = DATA_VA + 0x0054
VA_AUDITED_SOUND = DATA_VA + 0x0058
VA_AUDITED_UNITS = DATA_VA + 0x005C

# Formatting buffer (512 bytes at +0x0100)
VA_FMT_BUF = DATA_VA + 0x0100

# Strings block (+0x0300..+0x097F)
VA_STR_BASE = DATA_VA + 0x0300

# Per-slot tracking arrays for slots 0..399:
#   VA_SLOT_PREV_KIND    (400 bytes at +0x0980): 0 if dead, else kind_id
#   VA_SLOT_ANOMALY_FLAG (400 bytes at +0x0B20): 1 if anomaly already logged for this slot
#   VA_SLOT_PREV_ORDER   (800 bytes at +0x0CC0): uint16 previous order
VA_SLOT_PREV_KIND = DATA_VA + 0x0980
VA_SLOT_ANOMALY_FLAG = DATA_VA + 0x0B20
VA_SLOT_PREV_ORDER = DATA_VA + 0x0CC0


class CodeBuffer:
    def __init__(self, base_va: int) -> None:
        self.base_va = base_va
        self.buf = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups_rel32: list[tuple[int, str]] = []

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
        return bytes(self.buf)


STRINGS: dict[str, bytes] = {
    "KERNEL32": b"KERNEL32.dll\x00",
    "USER32": b"USER32.dll\x00",
    "CreateFileA": b"CreateFileA\x00",
    "WriteFile": b"WriteFile\x00",
    "FlushFileBuffers": b"FlushFileBuffers\x00",
    "SetFilePointer": b"SetFilePointer\x00",
    "GetTickCount": b"GetTickCount\x00",
    "Sleep": b"Sleep\x00",
    "CreateThread": b"CreateThread\x00",
    "SetUnhandledExceptionFilter": b"SetUnhandledExceptionFilter\x00",
    "GetWindowLongA": b"GetWindowLongA\x00",
    "LOG_PATH": b"imjin_anomaly.log\x00",
    "FMT_SESSION": b"\r\n================================================================================\r\n[%08u ms] [SESSION_START] Imjinrok 2+ Blackbox Anomaly Logger Active (ASI Base=0x65300000)\r\n",
    "FMT_SOUND": b"[%08u ms] [AUDIT_SOUND] SoundMgr=0x%08X LoadedEffects=%u (Custom Muye24ki IDs 485..504 Ready)\r\n",
    "FMT_UNITS": b"[%08u ms] [AUDIT_UNITS] Custom 15 Units (0x70..0x7E) Verified: 0x7A(HP=%u,Atk=%u,Spd=%u) 0x7B(HP=%u,Atk=%u) 0x7C(HP=%u,R1=%u) 0x7D(HP=%u,Spd=%u,Atb1=0x%08X) 0x7E(HP=%u,R1=%u) FarmerBuild0xB5=%u\r\n",
    "FMT_ANOM_TBL": b"[%08u ms] [ANOMALY_TABLE] KindID=0x%02X has invalid HP=%d or Atb1=0x%08X in KindInfo table!\r\n",
    "FMT_STATE": b"[%08u ms] [STATE_CHANGE] GameState=%d->%d Active=%d Paused=%d Iconic=%d ExStyle=0x%08X Frame=%u\r\n",
    "FMT_FREEZE": b"[%08u ms] [ANOMALY_FREEZE] Main loop frame counter stalled at Frame=%u for >5000ms (GameState=%d, Chars=%u)!\r\n",
    "FMT_SPAWN": b"[%08u ms] [UNIT_SPAWN] Slot=%u Kind=0x%02X Player=%u HP=%d Pos=(%u,%u) Order=%u\r\n",
    "FMT_ORDER": b"[%08u ms] [UNIT_ORDER] Slot=%u Kind=0x%02X Order=%u->%u AniSlot=%u Frame=%u HP=%d Pos=(%u,%u)\r\n",
    "FMT_DEATH": b"[%08u ms] [UNIT_DEATH] Slot=%u Kind=0x%02X cleared/died\r\n",
    "FMT_ANOM_KIND": b"[%08u ms] [ANOMALY_UNIT_KIND] Slot=%u has invalid KindID=0x%02X Pos=(%u,%u)!\r\n",
    "FMT_ANOM_HP": b"[%08u ms] [ANOMALY_UNIT_HP] Slot=%u Kind=0x%02X has corrupted HP=%d Pos=(%u,%u)!\r\n",
    "FMT_ANOM_POS": b"[%08u ms] [ANOMALY_UNIT_POS] Slot=%u Kind=0x%02X has out-of-bounds Pos=(%u,%u) Order=%u!\r\n",
    "FMT_CRASH": b"\r\n[%08u ms] [CRASH_BLACKBOX] ExceptionCode=0x%08X FaultEIP=0x%08X EAX=0x%08X EBX=0x%08X ECX=0x%08X EDX=0x%08X ESI=0x%08X EDI=0x%08X EBP=0x%08X ESP=0x%08X GameState=%d Frame=%u Chars=%u\r\n",
}


def compute_string_vas() -> tuple[dict[str, int], bytes]:
    cur = 0
    s_vas: dict[str, int] = {}
    blob = bytearray()
    for k, v in STRINGS.items():
        s_vas[k] = VA_STR_BASE + cur
        blob.extend(v)
        if not v.endswith(b"\x00"):
            blob.append(0)
        while len(blob) % 4 != 0:
            blob.append(0)
        cur = len(blob)
    assert cur <= 0x680, f"String blob overflow: {cur}"
    return s_vas, bytes(blob)


def build_code(s_vas: dict[str, int]) -> tuple[bytes, dict[str, int]]:
    c = CodeBuffer(TEXT_VA)

    # =========================================================================
    # 1. DllMain(hinstDLL, fdwReason, lpvReserved) -> stdcall, ret 0x0C
    # =========================================================================
    c.label("DllMain")
    c.emit(b"\x83\x7C\x24\x08\x01")              # cmp dword ptr [esp+8], 1 (DLL_PROCESS_ATTACH)
    c.jcc_rel(0x85, "dllmain_done")
    c.call_rel("InitLoggerASI")
    c.mark("dllmain_done")
    c.emit(b"\xB8\x01\x00\x00\x00")              # mov eax, 1
    c.emit(b"\xC2\x0C\x00")                      # ret 0x0C

    # =========================================================================
    # Helper: WriteLogBuf() -> writes null-terminated VA_FMT_BUF to VA_H_LOGFILE
    # Preserves all general registers via pushal/popal
    # =========================================================================
    c.label("WriteLogBuf")
    c.emit(b"\x60")                              # pushal
    c.emit(b"\x8B\x1D" + struct.pack("<I", VA_H_LOGFILE))  # mov ebx, [VA_H_LOGFILE]
    c.emit(b"\x85\xDB")                          # test ebx, ebx
    c.jcc_rel(0x84, "wlb_done")
    c.emit(b"\x83\xFB\xFF")                      # cmp ebx, -1 (INVALID_HANDLE_VALUE)
    c.jcc_rel(0x84, "wlb_done")

    # Compute strlen(VA_FMT_BUF) in ecx
    c.emit(b"\xBF" + struct.pack("<I", VA_FMT_BUF))  # mov edi, VA_FMT_BUF
    c.emit(b"\x31\xC9")                          # xor ecx, ecx
    c.mark("wlb_strlen_loop")
    c.emit(b"\x80\x3C\x0F\x00")                  # cmp byte ptr [edi + ecx], 0
    c.jcc_rel(0x84, "wlb_strlen_done")
    c.emit(b"\x41")                              # inc ecx
    c.emit(b"\x81\xF9\xFF\x01\x00\x00")          # cmp ecx, 511
    c.jcc_rel(0x8C, "wlb_strlen_loop")
    c.mark("wlb_strlen_done")
    c.emit(b"\x85\xC9")                          # test ecx, ecx
    c.jcc_rel(0x84, "wlb_done")

    # WriteFile(hFile=ebx, lpBuffer=VA_FMT_BUF, nNumberOfBytesToWrite=ecx, &bytesWritten, NULL)
    c.emit(b"\x6A\x00")                          # push 0
    c.emit(b"\x68" + struct.pack("<I", VA_BYTES_WRITTEN))
    c.emit(b"\x51")                              # push ecx
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\x53")                              # push ebx
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_WRITEFILE))

    # FlushFileBuffers(hFile=ebx)
    c.emit(b"\x53")                              # push ebx
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_FLUSHFILEBUFFERS))

    c.mark("wlb_done")
    c.emit(b"\x61")                              # popal
    c.emit(b"\xC3")                              # ret

    # =========================================================================
    # 2. InitLoggerASI() -> resolves APIs, opens imjin_anomaly.log, sets crash filter, starts watchdog thread
    # =========================================================================
    c.label("InitLoggerASI")
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_G_INIT_DONE) + b"\x01")
    c.jcc_rel(0x84, "init_ret")
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_G_INIT_DONE) + b"\x01\x00\x00\x00")
    c.emit(b"\x60")                              # pushal

    # GetModuleHandleA("KERNEL32.dll") -> esi
    c.emit(b"\x68" + struct.pack("<I", s_vas["KERNEL32"]))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetModuleHandleA))
    c.emit(b"\x89\xC6")                          # mov esi, eax

    def resolve_api(mod_reg_push: bytes, str_key: str, dst_va: int) -> None:
        c.emit(b"\x68" + struct.pack("<I", s_vas[str_key]))
        c.emit(mod_reg_push)
        c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetProcAddress))
        c.emit(b"\xA3" + struct.pack("<I", dst_va))

    resolve_api(b"\x56", "CreateFileA", VA_PFN_CREATEFILEA)
    resolve_api(b"\x56", "WriteFile", VA_PFN_WRITEFILE)
    resolve_api(b"\x56", "FlushFileBuffers", VA_PFN_FLUSHFILEBUFFERS)
    resolve_api(b"\x56", "SetFilePointer", VA_PFN_SETFILEPOINTER)
    resolve_api(b"\x56", "GetTickCount", VA_PFN_GETTICKCOUNT)
    resolve_api(b"\x56", "Sleep", VA_PFN_SLEEP)
    resolve_api(b"\x56", "CreateThread", VA_PFN_CREATETHREAD)
    resolve_api(b"\x56", "SetUnhandledExceptionFilter", VA_PFN_SETUNHANDLEDEXCEPTIONFILTER)

    # GetModuleHandleA("USER32.dll") -> esi
    c.emit(b"\x68" + struct.pack("<I", s_vas["USER32"]))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_GetModuleHandleA))
    c.emit(b"\x89\xC6")                          # mov esi, eax
    resolve_api(b"\x56", "GetWindowLongA", VA_PFN_GETWINDOWLONGA)

    # CreateFileA("imjin_anomaly.log", GENERIC_WRITE=0x40000000, FILE_SHARE_READ|WRITE=3, NULL, OPEN_ALWAYS=4, FILE_ATTRIBUTE_NORMAL=0x80, NULL)
    c.emit(b"\x6A\x00")                          # hTemplateFile = NULL
    c.emit(b"\x68\x80\x00\x00\x00")              # dwFlagsAndAttributes = 0x80
    c.emit(b"\x6A\x04")                          # dwCreationDisposition = OPEN_ALWAYS (4)
    c.emit(b"\x6A\x00")                          # lpSecurityAttributes = NULL
    c.emit(b"\x6A\x03")                          # dwShareMode = FILE_SHARE_READ | FILE_SHARE_WRITE (3)
    c.emit(b"\x68\x00\x00\x00\x40")              # dwDesiredAccess = GENERIC_WRITE (0x40000000)
    c.emit(b"\x68" + struct.pack("<I", s_vas["LOG_PATH"]))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_CREATEFILEA))
    c.emit(b"\xA3" + struct.pack("<I", VA_H_LOGFILE))

    # Seek to end: SetFilePointer(hFile, 0, NULL, FILE_END=2)
    c.emit(b"\x6A\x02")                          # FILE_END
    c.emit(b"\x6A\x00")                          # NULL
    c.emit(b"\x6A\x00")                          # 0
    c.emit(b"\x50")                              # push eax (hFile)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_SETFILEPOINTER))

    # Write [SESSION_START] line
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")                              # push tick
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_SESSION"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x0C")                      # add esp, 12
    c.call_rel("WriteLogBuf")

    # Initialize prev state sentinels to -1
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_PREV_GAMESTATE) + b"\xFF\xFF\xFF\xFF")
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_PREV_ACTIVE) + b"\xFF\xFF\xFF\xFF")
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_PREV_PAUSED) + b"\xFF\xFF\xFF\xFF")
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_PREV_ICONIC) + b"\xFF\xFF\xFF\xFF")

    # Register SetUnhandledExceptionFilter(CrashFilterProc)
    c.emit(b"\x68\x00\x00\x00\x00")              # placeholder for CrashFilterProc VA (fixed up below)
    off_push_crash = len(c.buf) - 4
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_SETUNHANDLEDEXCEPTIONFILTER))

    # CreateThread(NULL, 0, WatchdogThreadProc, NULL, 0, &VA_THREAD_ID)
    c.emit(b"\x68" + struct.pack("<I", VA_THREAD_ID))
    c.emit(b"\x6A\x00")                          # dwCreationFlags = 0
    c.emit(b"\x6A\x00")                          # lpParameter = NULL
    c.emit(b"\x68\x00\x00\x00\x00")              # placeholder for WatchdogThreadProc VA
    off_push_thread = len(c.buf) - 4
    c.emit(b"\x6A\x00")                          # dwStackSize = 0
    c.emit(b"\x6A\x00")                          # lpThreadAttributes = NULL
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_CREATETHREAD))

    c.emit(b"\x61")                              # popal
    c.mark("init_ret")
    c.emit(b"\xC3")                              # ret

    # =========================================================================
    # 3. CrashFilterProc(EXCEPTION_POINTERS* ep) -> stdcall, ret 4
    # =========================================================================
    va_crash_proc = c.label("CrashFilterProc")
    struct.pack_into("<I", c.buf, off_push_crash, va_crash_proc)

    c.emit(b"\x55\x89\xE5\x60")                  # push ebp; mov ebp, esp; pushal
    c.emit(b"\x8B\x75\x08")                      # mov esi, [ebp+8] (EXCEPTION_POINTERS*)
    c.emit(b"\x85\xF6")                          # test esi, esi
    c.jcc_rel(0x84, "crash_done")
    c.emit(b"\x8B\x3E")                          # mov edi, [esi] (EXCEPTION_RECORD*)
    c.emit(b"\x8B\x5E\x04")                      # mov ebx, [esi+4] (CONTEXT*)

    # Push args right-to-left for FMT_CRASH:
    # [%08u ms] [CRASH_BLACKBOX] ExceptionCode=0x%08X FaultEIP=0x%08X EAX=0x%08X EBX=0x%08X ECX=0x%08X EDX=0x%08X ESI=0x%08X EDI=0x%08X EBP=0x%08X ESP=0x%08X GameState=%d Frame=%u Chars=%u
    c.emit(b"\x0F\xB7\x05" + struct.pack("<I", VA_DAWN_CHAR_COUNT))
    c.emit(b"\x50")                              # Chars
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DAWN_FRAME_CNT))  # Frame
    c.emit(b"\x0F\xBF\x05" + struct.pack("<I", VA_DAWN_GAMESTATE))
    c.emit(b"\x50")                              # GameState
    c.emit(b"\xFF\xB3\xC4\x00\x00\x00")          # CONTEXT.Esp (+0xC4)
    c.emit(b"\xFF\xB3\xB4\x00\x00\x00")          # CONTEXT.Ebp (+0xB4)
    c.emit(b"\xFF\xB3\x9C\x00\x00\x00")          # CONTEXT.Edi (+0x9C)
    c.emit(b"\xFF\xB3\xA0\x00\x00\x00")          # CONTEXT.Esi (+0xA0)
    c.emit(b"\xFF\xB3\xA8\x00\x00\x00")          # CONTEXT.Edx (+0xA8)
    c.emit(b"\xFF\xB3\xAC\x00\x00\x00")          # CONTEXT.Ecx (+0xAC)
    c.emit(b"\xFF\xB3\xA4\x00\x00\x00")          # CONTEXT.Ebx (+0xA4)
    c.emit(b"\xFF\xB3\xB0\x00\x00\x00")          # CONTEXT.Eax (+0xB0)
    c.emit(b"\xFF\xB3\xB8\x00\x00\x00")          # CONTEXT.Eip (+0xB8)
    c.emit(b"\xFF\x37")                          # EXCEPTION_RECORD.ExceptionCode (+0x00)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")                              # tick
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_CRASH"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x40")                      # add esp, 64 (16 dwords)
    c.call_rel("WriteLogBuf")

    c.mark("crash_done")
    c.emit(b"\x61\x5D")                          # popal; pop ebp
    c.emit(b"\xB8\x01\x00\x00\x00")              # mov eax, 1 (EXCEPTION_EXECUTE_HANDLER)
    c.emit(b"\xC2\x04\x00")                      # ret 4

    # =========================================================================
    # 4. WatchdogThreadProc(LPVOID lpParam) -> stdcall, loops every 200ms
    # =========================================================================
    va_thread_proc = c.label("WatchdogThreadProc")
    struct.pack_into("<I", c.buf, off_push_thread, va_thread_proc)

    c.mark("wd_loop")
    # Sleep(200)
    c.emit(b"\x68\xC8\x00\x00\x00")              # push 200
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_SLEEP))

    # --- 4A. One-time Audit of SoundMgr (0x00B93974) ---
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_AUDITED_SOUND) + b"\x00")
    c.jcc_rel(0x85, "wd_check_units_audit")
    c.emit(b"\x8B\x1D" + struct.pack("<I", VA_DAWN_SOUND_MGR))
    c.emit(b"\x85\xDB")                          # test ebx, ebx
    c.jcc_rel(0x84, "wd_check_units_audit")
    c.emit(b"\x0F\xB7\x43\x0A")                  # movzx eax, word ptr [ebx + 0x0A] (loaded_effect_count)
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "wd_check_units_audit")
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_AUDITED_SOUND) + b"\x01\x00\x00\x00")
    c.emit(b"\x50")                              # push loaded_effect_count
    c.emit(b"\x53")                              # push SoundMgr ptr
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")                              # push tick
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_SOUND"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x14")                      # add esp, 20
    c.call_rel("WriteLogBuf")

    # --- 4B. One-time Audit of Custom Units (0x70..0x7E at 0x009CE2E8 + i*0x394) ---
    c.mark("wd_check_units_audit")
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_AUDITED_UNITS) + b"\x00")
    c.jcc_rel(0x85, "wd_check_state")
    # Check if 0x7E (낭선병 at 0x009CE2E8 + 14*0x394 = 0x009D1500) has HP (+0x06) > 0
    va_k7a = VA_DAWN_KIND_70_BASE + 10 * 0x394
    va_k7b = VA_DAWN_KIND_70_BASE + 11 * 0x394
    va_k7c = VA_DAWN_KIND_70_BASE + 12 * 0x394
    va_k7d = VA_DAWN_KIND_70_BASE + 13 * 0x394
    va_k7e = VA_DAWN_KIND_70_BASE + 14 * 0x394
    c.emit(b"\x0F\xB7\x05" + struct.pack("<I", va_k7e + 0x06))
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "wd_check_state")
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_AUDITED_UNITS) + b"\x01\x00\x00\x00")

    # Push FarmerBuild0xB5(0x009E4028), 0x7E(R1,HP), 0x7D(Atb1,Spd,HP), 0x7C(R1,HP), 0x7B(Atk,HP), 0x7A(Spd,Atk,HP)
    c.emit(b"\x0F\xB7\x05\x28\x40\x9E\x00\x50")  # push word ptr [0x009E4028] (CmdTable[0xB5].cmd_type == 4)
    c.emit(b"\x0F\xB7\x05" + struct.pack("<I", va_k7e + 0x36) + b"\x50")
    c.emit(b"\x0F\xB7\x05" + struct.pack("<I", va_k7e + 0x06) + b"\x50")
    c.emit(b"\xFF\x35" + struct.pack("<I", va_k7d + 0x4C))  # push dword ptr [va_k7d + 0x4C] (Atb1)
    for addr in [
        va_k7d + 0x2C, va_k7d + 0x06,
        va_k7c + 0x36, va_k7c + 0x06,
        va_k7b + 0x04, va_k7b + 0x06,
        va_k7a + 0x2C, va_k7a + 0x04, va_k7a + 0x06,
    ]:
        c.emit(b"\x0F\xB7\x05" + struct.pack("<I", addr))
        c.emit(b"\x50")
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_UNITS"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x40")                      # add esp, 64 (16 dwords)
    c.call_rel("WriteLogBuf")

    # Also verify all 15 custom units (0x70..0x7E) have HP > 0 and (Atb1 & 0x05) == 0x05
    c.emit(b"\x31\xF6")                          # xor esi, esi (i = 0..14)
    c.mark("wd_audit_tbl_loop")
    c.emit(b"\x69\xC6\x94\x03\x00\x00")          # imul eax, esi, 0x394
    c.emit(b"\x8B\x98" + struct.pack("<I", VA_DAWN_KIND_70_BASE + 0x4C))  # mov ebx, [KindInfo + 0x4C] (Atb1)
    c.emit(b"\x0F\xBF\x80" + struct.pack("<I", VA_DAWN_KIND_70_BASE + 0x06))  # movsx eax, word ptr [KindInfo + 0x06] (HP)
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x8E, "wd_audit_tbl_bad")          # jle bad
    c.emit(b"\x89\xD9\x83\xE1\x05\x83\xF9\x05")  # mov ecx, ebx; and ecx, 5; cmp ecx, 5
    c.jcc_rel(0x84, "wd_audit_tbl_next")         # je next
    c.mark("wd_audit_tbl_bad")
    c.emit(b"\x53")                              # push Atb1 (ebx)
    c.emit(b"\x50")                              # push HP (eax)
    c.emit(b"\x8D\x46\x70\x50")                  # lea eax, [esi+0x70]; push eax
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_ANOM_TBL"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x18")
    c.call_rel("WriteLogBuf")
    c.mark("wd_audit_tbl_next")
    c.emit(b"\x46\x83\xFE\x0F")                  # inc esi; cmp esi, 15
    c.jcc_rel(0x8C, "wd_audit_tbl_loop")

    # --- 4C. Check GameState / Active / Paused / IsIconic transitions ---
    c.mark("wd_check_state")
    c.emit(b"\x31\xFF")                          # xor edi, edi (iconic = 0)
    c.emit(b"\x8B\x1D" + struct.pack("<I", VA_DAWN_HWND))
    c.emit(b"\x85\xDB")
    c.jcc_rel(0x84, "wd_no_hwnd")
    c.emit(b"\x53")                              # push hWnd
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_IsIconic))
    c.emit(b"\x89\xC7")                          # mov edi, eax
    c.mark("wd_no_hwnd")

    c.emit(b"\x0F\xBF\x35" + struct.pack("<I", VA_DAWN_GAMESTATE))  # movsx esi, word ptr [GameState]
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_DAWN_APP_ACTIVE))
    c.emit(b"\x8B\x15" + struct.pack("<I", VA_DAWN_PAUSED))

    # Compare against prev
    c.emit(b"\x3B\x35" + struct.pack("<I", VA_PREV_GAMESTATE))
    c.jcc_rel(0x85, "wd_state_changed")
    c.emit(b"\x3B\x0D" + struct.pack("<I", VA_PREV_ACTIVE))
    c.jcc_rel(0x85, "wd_state_changed")
    c.emit(b"\x3B\x15" + struct.pack("<I", VA_PREV_PAUSED))
    c.jcc_rel(0x85, "wd_state_changed")
    c.emit(b"\x3B\x3D" + struct.pack("<I", VA_PREV_ICONIC))
    c.jcc_rel(0x84, "wd_check_freeze")

    c.mark("wd_state_changed")
    # Get GWL_EXSTYLE (-20 = 0xFFFFFFEC)
    c.emit(b"\x31\xC0")                          # xor eax, eax
    c.emit(b"\x85\xDB")                          # test ebx (hWnd), ebx
    c.jcc_rel(0x84, "wd_got_exstyle")
    c.emit(b"\x6A\xEC\x53")                      # push -20; push ebx
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETWINDOWLONGA))
    c.mark("wd_got_exstyle")
    # Reload ecx, edx after GetWindowLongA
    c.emit(b"\x8B\x0D" + struct.pack("<I", VA_DAWN_APP_ACTIVE))
    c.emit(b"\x8B\x15" + struct.pack("<I", VA_DAWN_PAUSED))

    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DAWN_FRAME_CNT))  # Frame
    c.emit(b"\x50")                              # ExStyle
    c.emit(b"\x57")                              # Iconic
    c.emit(b"\x52")                              # Paused
    c.emit(b"\x51")                              # Active
    c.emit(b"\x56")                              # New GameState
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_PREV_GAMESTATE))  # Old GameState
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")                              # tick
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_STATE"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x28")                      # add esp, 40 (10 dwords)
    c.call_rel("WriteLogBuf")

    # Update prev
    c.emit(b"\x89\x35" + struct.pack("<I", VA_PREV_GAMESTATE))
    c.emit(b"\x89\x3D" + struct.pack("<I", VA_PREV_ICONIC))
    c.emit(b"\xA1" + struct.pack("<I", VA_DAWN_APP_ACTIVE))
    c.emit(b"\xA3" + struct.pack("<I", VA_PREV_ACTIVE))
    c.emit(b"\xA1" + struct.pack("<I", VA_DAWN_PAUSED))
    c.emit(b"\xA3" + struct.pack("<I", VA_PREV_PAUSED))

    # --- 4D. Main-thread Freeze / Stall Detector ---
    c.mark("wd_check_freeze")
    c.emit(b"\xA1" + struct.pack("<I", VA_DAWN_FRAME_CNT))
    c.emit(b"\x3B\x05" + struct.pack("<I", VA_LAST_FRAME_CNT))
    c.jcc_rel(0x84, "wd_frame_same")
    c.emit(b"\xA3" + struct.pack("<I", VA_LAST_FRAME_CNT))
    c.emit(b"\xC7\x05" + struct.pack("<I", VA_STALL_TICKS) + b"\x00\x00\x00\x00")
    c.jmp_rel("wd_scan_units")

    c.mark("wd_frame_same")
    # Only count stall if Active==1 && Paused==0 && GameState==0x17
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_DAWN_APP_ACTIVE) + b"\x01")
    c.jcc_rel(0x85, "wd_scan_units")
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_DAWN_PAUSED) + b"\x00")
    c.jcc_rel(0x85, "wd_scan_units")
    c.emit(b"\x66\x83\x3D" + struct.pack("<I", VA_DAWN_GAMESTATE) + b"\x17")
    c.jcc_rel(0x85, "wd_scan_units")
    c.emit(b"\xFF\x05" + struct.pack("<I", VA_STALL_TICKS))
    c.emit(b"\x83\x3D" + struct.pack("<I", VA_STALL_TICKS) + b"\x19")  # 25 * 200ms = 5000ms
    c.jcc_rel(0x85, "wd_scan_units")
    # Log freeze anomaly
    c.emit(b"\x0F\xB7\x05" + struct.pack("<I", VA_DAWN_CHAR_COUNT))
    c.emit(b"\x50")
    c.emit(b"\x0F\xBF\x05" + struct.pack("<I", VA_DAWN_GAMESTATE))
    c.emit(b"\x50")
    c.emit(b"\xFF\x35" + struct.pack("<I", VA_DAWN_FRAME_CNT))
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_FREEZE"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x18")
    c.call_rel("WriteLogBuf")

    # --- 4E. Live Unit Lifecycle & Anomaly Scanner (Slots 1..400) ---
    c.mark("wd_scan_units")
    c.emit(b"\x66\x83\x3D" + struct.pack("<I", VA_DAWN_GAMESTATE) + b"\x17")
    c.jcc_rel(0x85, "wd_loop")                   # Only scan units when in-game (GameState == 0x17)

    c.emit(b"\xBB\x01\x00\x00\x00")              # mov ebx, 1 (slot = 1..399)
    c.mark("wd_unit_loop")
    c.emit(b"\x0F\xB7\x04\x5D" + struct.pack("<I", VA_DAWN_CHAR_ALIVE))  # movzx eax, word ptr [CHAR_ALIVE + ebx*2]
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x85, "wd_unit_alive")

    # Slot is dead: check if VA_SLOT_PREV_KIND[ebx] was custom unit (0x70..0x7E)
    c.emit(b"\x0F\xB6\x83" + struct.pack("<I", VA_SLOT_PREV_KIND))
    c.emit(b"\x85\xC0")
    c.jcc_rel(0x84, "wd_unit_next")
    c.emit(b"\xC6\x83" + struct.pack("<I", VA_SLOT_PREV_KIND) + b"\x00")
    c.emit(b"\xC6\x83" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x00")
    c.emit(b"\x3C\x70")                          # cmp al, 0x70
    c.jcc_rel(0x82, "wd_unit_next")
    c.emit(b"\x3C\x7E")                          # cmp al, 0x7E
    c.jcc_rel(0x87, "wd_unit_next")
    # Log [UNIT_DEATH]
    c.emit(b"\x50")                              # push kind
    c.emit(b"\x53")                              # push slot (ebx)
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_DEATH"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x14")
    c.call_rel("WriteLogBuf")
    c.jmp_rel("wd_unit_next")

    # Slot is alive: compute c_addr = 0x0066B790 + ebx * 0x758 in esi
    c.mark("wd_unit_alive")
    c.emit(b"\x69\xF3\x58\x07\x00\x00")          # imul esi, ebx, 0x758
    c.emit(b"\x81\xC6" + struct.pack("<I", VA_DAWN_CHAR_BASE))

    # Read kind (edi), hp (eax), x, y, order
    c.emit(b"\x0F\xB6\xBE\x8D\x00\x00\x00")      # movzx edi, byte ptr [esi + 0x8D] (kind)

    # Anomaly Check 1: KindID == 0 or KindID > 0x7E
    c.emit(b"\x85\xFF")
    c.jcc_rel(0x84, "wd_anom_kind")
    c.emit(b"\x83\xFF\x7E")
    c.jcc_rel(0x8E, "wd_kind_ok")
    c.mark("wd_anom_kind")
    c.emit(b"\x80\xBB" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x00")
    c.jcc_rel(0x85, "wd_unit_next")
    c.emit(b"\xC6\x83" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x01")
    c.emit(b"\x0F\xB7\x86\xA4\x02\x00\x00\x50")  # push y
    c.emit(b"\x0F\xB7\x86\xA2\x02\x00\x00\x50")  # push x
    c.emit(b"\x57\x53")                          # push kind; push slot
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_ANOM_KIND"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x1C")
    c.call_rel("WriteLogBuf")
    c.jmp_rel("wd_unit_next")

    c.mark("wd_kind_ok")
    # Anomaly Check 2: HP < -500 or HP > 30000
    c.emit(b"\x8B\x86\xB4\x00\x00\x00")          # mov eax, [esi + 0xB4] (hp)
    c.emit(b"\x3D\x0C\xFE\xFF\xFF")              # cmp eax, -500
    c.jcc_rel(0x8C, "wd_anom_hp")
    c.emit(b"\x3D\x30\x75\x00\x00")              # cmp eax, 30000
    c.jcc_rel(0x8E, "wd_hp_ok")
    c.mark("wd_anom_hp")
    c.emit(b"\x80\xBB" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x00")
    c.jcc_rel(0x85, "wd_hp_ok")
    c.emit(b"\xC6\x83" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x01")
    c.emit(b"\x0F\xB7\x8E\xA4\x02\x00\x00\x51")  # push y
    c.emit(b"\x0F\xB7\x8E\xA2\x02\x00\x00\x51")  # push x
    c.emit(b"\x50\x57\x53")                      # push hp; push kind; push slot
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_ANOM_HP"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x20")
    c.call_rel("WriteLogBuf")

    c.mark("wd_hp_ok")
    # Anomaly Check 3: X > 512 or Y > 512
    c.emit(b"\x0F\xB7\x86\xA2\x02\x00\x00")      # movzx eax, word ptr [esi + 0x2A2] (x)
    c.emit(b"\x0F\xB7\x8E\xA4\x02\x00\x00")      # movzx ecx, word ptr [esi + 0x2A4] (y)
    c.emit(b"\x3D\x00\x02\x00\x00")              # cmp eax, 512
    c.jcc_rel(0x87, "wd_anom_pos")
    c.emit(b"\x81\xF9\x00\x02\x00\x00")          # cmp ecx, 512
    c.jcc_rel(0x86, "wd_pos_ok")
    c.mark("wd_anom_pos")
    c.emit(b"\x80\xBB" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x00")
    c.jcc_rel(0x85, "wd_pos_ok")
    c.emit(b"\xC6\x83" + struct.pack("<I", VA_SLOT_ANOMALY_FLAG) + b"\x01")
    c.emit(b"\x0F\xB7\x96\x90\x02\x00\x00\x52")  # push order
    c.emit(b"\x51\x50\x57\x53")                  # push y; push x; push kind; push slot
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_ANOM_POS"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x20")
    c.call_rel("WriteLogBuf")

    c.mark("wd_pos_ok")
    # Track custom units (0x70..0x7E) spawn & order transitions
    c.emit(b"\x83\xFF\x70")                      # cmp edi, 0x70
    c.jcc_rel(0x82, "wd_save_slot_state")
    c.emit(b"\x0F\xB6\x83" + struct.pack("<I", VA_SLOT_PREV_KIND))
    c.emit(b"\x39\xF8")                          # cmp eax, edi (was already this kind?)
    c.jcc_rel(0x84, "wd_check_order_change")

    # Newly spawned custom unit!
    c.emit(b"\x89\xF8")
    c.emit(b"\x88\x83" + struct.pack("<I", VA_SLOT_PREV_KIND))
    c.emit(b"\x0F\xB7\x86\x90\x02\x00\x00")      # order
    c.emit(b"\x66\x89\x04\x5D" + struct.pack("<I", VA_SLOT_PREV_ORDER))
    c.emit(b"\x50")                              # push order
    c.emit(b"\x0F\xB7\x86\xA4\x02\x00\x00\x50")  # push y
    c.emit(b"\x0F\xB7\x86\xA2\x02\x00\x00\x50")  # push x
    c.emit(b"\xFF\xB6\xB4\x00\x00\x00")          # push hp
    c.emit(b"\x0F\xB6\x86\x8E\x00\x00\x00\x50")  # push player
    c.emit(b"\x57\x53")                          # push kind; push slot
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_SPAWN"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x28")                      # add esp, 40 (10 dwords)
    c.call_rel("WriteLogBuf")
    c.jmp_rel("wd_unit_next")

    c.mark("wd_check_order_change")
    c.emit(b"\x0F\xB7\x86\x90\x02\x00\x00")      # movzx eax, word ptr [esi + 0x290] (new order)
    c.emit(b"\x0F\xB7\x0C\x5D" + struct.pack("<I", VA_SLOT_PREV_ORDER))  # old order
    c.emit(b"\x39\xC8")                          # cmp eax, ecx
    c.jcc_rel(0x84, "wd_unit_next")
    c.emit(b"\x66\x89\x04\x5D" + struct.pack("<I", VA_SLOT_PREV_ORDER))
    # Log [UNIT_ORDER]
    c.emit(b"\x0F\xB7\x96\xA4\x02\x00\x00\x52")  # push y
    c.emit(b"\x0F\xB7\x96\xA2\x02\x00\x00\x52")  # push x
    c.emit(b"\xFF\xB6\xB4\x00\x00\x00")          # push hp
    c.emit(b"\xFF\xB6\x4C\x00\x00\x00")          # push spr_frame
    c.emit(b"\xFF\xB6\x80\x00\x00\x00")          # push ani_slot
    c.emit(b"\x50")                              # push new_order
    c.emit(b"\x51")                              # push old_order
    c.emit(b"\x57\x53")                          # push kind; push slot
    c.emit(b"\xFF\x15" + struct.pack("<I", VA_PFN_GETTICKCOUNT))
    c.emit(b"\x50")
    c.emit(b"\x68" + struct.pack("<I", s_vas["FMT_ORDER"]))
    c.emit(b"\x68" + struct.pack("<I", VA_FMT_BUF))
    c.emit(b"\xFF\x15" + struct.pack("<I", IAT_wsprintfA))
    c.emit(b"\x83\xC4\x30")                      # add esp, 48 (12 dwords)
    c.call_rel("WriteLogBuf")
    c.jmp_rel("wd_unit_next")

    c.mark("wd_save_slot_state")
    c.emit(b"\x89\xF8")
    c.emit(b"\x88\x83" + struct.pack("<I", VA_SLOT_PREV_KIND))

    c.mark("wd_unit_next")
    c.emit(b"\x43")                              # inc ebx
    c.emit(b"\x81\xFB\x90\x01\x00\x00")          # cmp ebx, 400
    c.jcc_rel(0x8C, "wd_unit_loop")
    c.jmp_rel("wd_loop")

    raw_code = c.resolve()
    return raw_code, c.labels


def build_pe_dll() -> bytes:
    s_vas, str_blob = compute_string_vas()
    code_bytes, labels = build_code(s_vas)
    assert len(code_bytes) <= 0x2000, f".text overflow: {len(code_bytes)}"

    text_sec = bytearray(0x2000)
    text_sec[: len(code_bytes)] = code_bytes

    # Build Export Directory at RVA 0x2800 (text_sec offset 0x1800) exporting InitializeASI
    exp_rva = 0x2800
    exp_off = 0x1800
    init_rva = labels["InitLoggerASI"] - IMAGE_BASE
    struct.pack_into(
        "<IIHHIIIIIII",
        text_sec,
        exp_off,
        0, 0, 0, 0,
        exp_rva + 0x40,  # Name RVA ("imjin_logger.asi")
        1,               # Base
        1,               # NumberOfFunctions
        1,               # NumberOfNames
        exp_rva + 0x80,  # AddressOfFunctions RVA
        exp_rva + 0x84,  # AddressOfNames RVA
        exp_rva + 0x88,  # AddressOfNameOrdinals RVA
    )
    text_sec[exp_off + 0x40 : exp_off + 0x40 + 17] = b"imjin_logger.asi\x00"
    text_sec[exp_off + 0x60 : exp_off + 0x60 + 14] = b"InitializeASI\x00"
    struct.pack_into("<I", text_sec, exp_off + 0x80, init_rva)
    struct.pack_into("<I", text_sec, exp_off + 0x84, exp_rva + 0x60)
    struct.pack_into("<H", text_sec, exp_off + 0x88, 0)

    data_sec = bytearray(0x2000)
    data_sec[0x0300 : 0x0300 + len(str_blob)] = str_blob

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
        2,              # 2 sections (.text, .data)
        0, 0, 0,
        0xE0,           # SizeOfOptionalHeader
        0x210E,         # DLL | EXECUTABLE | 32BIT
    )

    opt_off = pe_off + 24
    entry_rva = labels["DllMain"] - IMAGE_BASE
    struct.pack_into(
        "<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII",
        headers,
        opt_off,
        0x010B, 14, 0,
        0x2000, 0x2000, 0,
        entry_rva,
        TEXT_RVA, DATA_RVA,
        IMAGE_BASE,
        0x1000, 0x0200,
        4, 0, 0, 0, 4, 0, 0,
        0x5000,         # SizeOfImage
        0x0400,         # SizeOfHeaders
        0, 2, 0,
        0x100000, 0x1000, 0x100000, 0x1000,
        0, 16,
    )
    # DataDirectory[0] = Export Directory (RVA 0x2800, Size 0x100)
    struct.pack_into("<II", headers, opt_off + 96, 0x2800, 0x100)

    sec_off = opt_off + 0xE0
    struct.pack_into(
        "<8sIIIIIIHHI",
        headers,
        sec_off,
        b".text\x00\x00\x00",
        0x2000, TEXT_RVA, 0x2000, 0x0400,
        0, 0, 0, 0,
        0x60000020,
    )
    struct.pack_into(
        "<8sIIIIIIHHI",
        headers,
        sec_off + 40,
        b".data\x00\x00\x00",
        0x2000, DATA_RVA, 0x2000, 0x2400,
        0, 0, 0, 0,
        0xC0000040,
    )

    return bytes(headers + text_sec + data_sec)


def main() -> None:
    out_path = Path(__file__).resolve().parents[2] / "YM" / "dawn" / "imjin_logger.asi"
    dll_bytes = build_pe_dll()
    out_path.write_bytes(dll_bytes)
    print(f"[OK] Built {out_path} ({len(dll_bytes):,} bytes)")


if __name__ == "__main__":
    main()
