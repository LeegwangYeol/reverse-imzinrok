import ctypes
import os
import struct
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.verify_all_mechanics_deep_check import (
    kernel32, user32, CHAR_BASE, CHAR_STRIDE, CHAR_ALIVE_ARRAY,
    read_mem, write_mem, read_u16, read_u32, wait_state, click,
    find_chars, train_unit
)

dawn_dir = Path("YM/dawn")
subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
time.sleep(0.3)

proc = subprocess.Popen([str(dawn_dir / "dawn.exe")], cwd=str(dawn_dir))
hp = kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
assert wait_state(hp, 9)
write_mem(hp, 0x0041C916, b"\x90" * 11)
time.sleep(0.2)
click(hp, 200, 550)
assert wait_state(hp, 7)
time.sleep(0.2)
click(hp, 595, 558)
assert wait_state(hp, 5)
time.sleep(0.3)
slots_raw = bytearray(read_mem(hp, 0x00632CC0, 48))
slots_raw[0] = 1; slots_raw[2] = 0; slots_raw[5] = 0
slots_raw[6] = 2; slots_raw[8] = 1; slots_raw[11] = 1
write_mem(hp, 0x00632CC0, bytes(slots_raw))
write_mem(hp, 0x01065D22, struct.pack("<H", 1))
time.sleep(0.2)
click(hp, 595, 558)
assert wait_state(hp, 3)
time.sleep(1.0)

# Zero out log memory
write_mem(hp, 0x009E5D00, b"\x00" * 128)

# Hook 0x00421A20:
# Dump:
# eax -> 0x009E5D00
# ecx -> 0x009E5D04
# edx -> 0x009E5D08
# ebx -> 0x009E5D0C
# esp -> 0x009E5D10
# ebp -> 0x009E5D14
# esi -> 0x009E5D18
# edi -> 0x009E5D1C
# [esp+0x00] -> 0x009E5D20
# [esp+0x04] -> 0x009E5D24
# [esp+0x08] -> 0x009E5D28
# [esp+0x0C] -> 0x009E5D2C
# [esp+0x10] -> 0x009E5D30
# [esp+0x14] -> 0x009E5D34
# [esp+0x18] -> 0x009E5D38
# [esp+0x1C] -> 0x009E5D3C
# [esp+0x20] -> 0x009E5D40
# [esp+0x24] -> 0x009E5D44
# inc [0x009E5D48]
# imul esi, edi, 0x758
# jmp 0x00470CE3
hook_asm = bytearray()
hook_asm += b"\xA3\x00\x5D\x9E\x00"                  # mov [0x009E5D00], eax
hook_asm += b"\x89\x0D\x04\x5D\x9E\x00"              # mov [0x009E5D04], ecx
hook_asm += b"\x89\x15\x08\x5D\x9E\x00"              # mov [0x009E5D08], edx
hook_asm += b"\x89\x1D\x0C\x5D\x9E\x00"              # mov [0x009E5D0C], ebx
hook_asm += b"\x89\x25\x10\x5D\x9E\x00"              # mov [0x009E5D10], esp
hook_asm += b"\x89\x2D\x14\x5D\x9E\x00"              # mov [0x009E5D14], ebp
hook_asm += b"\x89\x35\x18\x5D\x9E\x00"              # mov [0x009E5D18], esi
hook_asm += b"\x89\x3D\x1C\x5D\x9E\x00"              # mov [0x009E5D1C], edi

for off in range(0, 0x28, 4):
    dst = 0x009E5D20 + off
    hook_asm += b"\x8B\x44\x24" + bytes([off])        # mov eax, [esp + off]
    hook_asm += b"\xA3" + struct.pack("<I", dst)      # mov [dst], eax

hook_asm += b"\xFF\x05\x48\x5D\x9E\x00"              # inc dword ptr [0x009E5D48]
hook_asm += b"\x69\xF7\x58\x07\x00\x00"              # imul esi, edi, 0x758
# jmp 0x00470CE3
rel = 0x00470CE3 - (0x00421A20 + len(hook_asm) + 5)
hook_asm += b"\xE9" + struct.pack("<i", rel)

write_mem(hp, 0x00421A20, bytes(hook_asm))

write_mem(hp, 0x00956784, struct.pack("<II", 100000, 100000))
chars = find_chars(hp)
hq = next(c for c in chars if c["kind"] == 0x31 and c["player"] == 0)
peasant = next(c for c in chars if c["kind"] < 0x28 and c["player"] == 0)

target_x, target_y = hq["x"] + 2, hq["y"] + 4
write_mem(hp, peasant["addr"] + 0x380, struct.pack("<H", 0))
write_mem(hp, peasant["addr"] + 0x388, struct.pack("<HH", target_x, target_y))
write_mem(hp, peasant["addr"] + 0x384, struct.pack("<H", 3))
time.sleep(2.0)

yusaeng = train_unit(hp, hq["addr"], 0xAB, 0x70)
print(f"Yusaeng trained: idx={yusaeng['idx']}")
p_cur = next(c for c in find_chars(hp) if c["idx"] == peasant["idx"])
print(f"Peasant target: idx={peasant['idx']}")

write_mem(hp, peasant["addr"] + 0x8E, b"\x01")
write_mem(hp, peasant["addr"] + 0xB4, struct.pack("<i", 5000))
p_handle = read_u32(hp, peasant["addr"] + 0x29C)

# Order attack
write_mem(hp, yusaeng["addr"] + 0x380, struct.pack("<H", 1))
write_mem(hp, yusaeng["addr"] + 0x388, struct.pack("<HH", p_cur["x"], p_cur["y"]))
write_mem(hp, yusaeng["addr"] + 0x38C, struct.pack("<I", p_handle))
write_mem(hp, yusaeng["addr"] + 0x384, struct.pack("<H", 4))

print("Waiting for attack hit...")
for _ in range(15):
    hit_cnt = read_u32(hp, 0x009E5D48)
    if hit_cnt > 0:
        raw = read_mem(hp, 0x009E5D00, 0x48)
        regs = struct.unpack("<8I", raw[:32])
        stack = struct.unpack("<10I", raw[32:72])
        print(f"Hit registered! HitCnt={hit_cnt}")
        print(f"  EAX=0x{regs[0]:X}, ECX=0x{regs[1]:X}, EDX=0x{regs[2]:X}, EBX=0x{regs[3]:X} ({regs[3]})")
        print(f"  ESP=0x{regs[4]:X}, EBP=0x{regs[5]:X} ({regs[5]}), ESI=0x{regs[6]:X}, EDI=0x{regs[7]:X} ({regs[7]})")
        print("  Stack slots [esp+0x00 .. esp+0x24]:")
        for i, val in enumerate(stack):
            print(f"    [esp + 0x{i*4:02X}] = 0x{val:08X} ({val})")
        break
    time.sleep(0.5)

subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
