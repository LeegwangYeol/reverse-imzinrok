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
write_mem(hp, 0x009E5D00, b"\x00" * 32)

# Patch Cave D entry at 0x00421A20 to log ebx, edi, and a hit counter
# 89 1D 00 5D 9E 00  (mov dword ptr [0x009E5D00], ebx)
# 89 3D 04 5D 9E 00  (mov dword ptr [0x009E5D04], edi)
# FF 05 08 5D 9E 00  (inc dword ptr [0x009E5D08])
# 69 F7 58 07 00 00  (imul esi, edi, 0x758)
log_bytes = bytes.fromhex("891D005D9E00" + "893D045D9E00" + "FF05085D9E00" + "69F758070000")
write_mem(hp, 0x00421A20, log_bytes)

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

write_mem(hp, peasant["addr"] + 0x8E, b"\x01")
write_mem(hp, peasant["addr"] + 0xB4, struct.pack("<i", 5000))
p_handle = read_u32(hp, peasant["addr"] + 0x29C)

# Order attack
write_mem(hp, yusaeng["addr"] + 0x380, struct.pack("<H", 1))
write_mem(hp, yusaeng["addr"] + 0x388, struct.pack("<HH", p_cur["x"], p_cur["y"]))
write_mem(hp, yusaeng["addr"] + 0x38C, struct.pack("<I", p_handle))
write_mem(hp, yusaeng["addr"] + 0x384, struct.pack("<H", 4))

print("Waiting for attack...")
for _ in range(15):
    hit_cnt = read_u32(hp, 0x009E5D08)
    ebx_val = read_u32(hp, 0x009E5D00)
    edi_val = read_u32(hp, 0x009E5D04)
    p_cur = next(c for c in find_chars(hp) if c["idx"] == peasant["idx"])
    print(f"HitCnt={hit_cnt}, EBX={ebx_val} (bx={ebx_val&0xFFFF}), EDI={edi_val} (PeasantIdx={peasant['idx']}), PeasantHP={p_cur['hp']}")
    if hit_cnt > 0:
        break
    time.sleep(0.5)

subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
