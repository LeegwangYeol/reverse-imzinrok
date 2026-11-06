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

# Build 75-byte compact status effect cave at 0x00421A20:
c_asm = bytearray()
def c_va(): return 0x00421A20 + len(c_asm)

c_asm += b"\x8B\x14\x24"                  # mov edx, [esp] (target unit index)
c_asm += b"\x81\xFA\xD0\x07\x00\x00"      # cmp edx, 2000
off_jae = len(c_asm); c_asm += b"\x73\x00"

c_asm += b"\x66\x83\x3C\x55\xC8\x90\x89\x00\x00" # cmp word ptr [edx*2 + 0x008990C8], 0 (alive check)
off_je_dead = len(c_asm); c_asm += b"\x74\x00"

c_asm += b"\x69\xC2\x58\x07\x00\x00"      # imul eax, edx, 0x758 (target char offset)
c_asm += b"\xF6\x80\x68\xB9\x66\x00\x02"  # test byte ptr [eax + 0x0066B968], 2 (building check)
off_jne_bld = len(c_asm); c_asm += b"\x75\x00"

c_asm += b"\x66\x83\xFB\x09"              # cmp bx, 9 (Yusaeng)
c_asm += b"\xB9\x96\x00\x00\x00"          # mov ecx, 150 (10.0 seconds)
off_je_apply = len(c_asm); c_asm += b"\x74\x00"

c_asm += b"\x66\x83\xFB\x1A"              # cmp bx, 26 (Furhead / Snow Woman)
off_jne_res = len(c_asm); c_asm += b"\x75\x00"

# .freeze:
c_asm += b"\x66\xC7\x80\xD0\xBA\x66\x00\x01\x3C" # mov word ptr [eax + 0x0066BAD0], 0x3C01
c_asm += b"\xB9\x5A\x00\x00\x00"          # mov ecx, 90 (6.0 seconds)

# .apply:
va_apply = c_va()
c_asm[off_je_apply + 1] = va_apply - (0x00421A20 + off_je_apply + 2)
c_asm += b"\x89\x88\x00\xBB\x66\x00"      # mov dword ptr [eax + 0x0066BB00], ecx

# .resume:
va_res = c_va()
c_asm[off_jae + 1] = va_res - (0x00421A20 + off_jae + 2)
c_asm[off_je_dead + 1] = va_res - (0x00421A20 + off_je_dead + 2)
c_asm[off_jne_bld + 1] = va_res - (0x00421A20 + off_jne_bld + 2)
c_asm[off_jne_res + 1] = va_res - (0x00421A20 + off_jne_res + 2)

c_asm += b"\x69\xF7\x58\x07\x00\x00"      # imul esi, edi, 0x758 (attacker char offset for resume)
rel_resume = 0x00470CE3 - (c_va() + 5)
c_asm += b"\xE9" + struct.pack("<i", rel_resume)

print(f"Cave length: {len(c_asm)} bytes (max 88 bytes)")
assert len(c_asm) <= 88, f"Cave too large: {len(c_asm)}"

write_mem(hp, 0x00421A20, bytes(c_asm))

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
for _ in range(20):
    p_cur = next(c for c in find_chars(hp) if c["idx"] == peasant["idx"])
    para = read_u16(hp, 0x0066BB00 + peasant["idx"] * CHAR_STRIDE)
    print(f"PeasantHP={p_cur['hp']}, ParalysisTimer={para}")
    if para > 0:
        print(f"SUCCESS! Paralysis timer = {para} ticks (~10s)!")
        break
    time.sleep(0.5)

subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
