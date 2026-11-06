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

write_mem(hp, 0x00956784, struct.pack("<II", 100000, 100000))
chars = find_chars(hp)
hq = next(c for c in chars if c["kind"] == 0x31 and c["player"] == 0)
peasant = next(c for c in chars if c["kind"] < 0x28 and c["player"] == 0)
print(f"HQ at ({hq['x']}, {hq['y']})")
print(f"Peasant at ({peasant['x']}, {peasant['y']})")

# Move peasant right next to HQ
target_x, target_y = hq["x"] + 2, hq["y"] + 4
write_mem(hp, peasant["addr"] + 0x380, struct.pack("<H", 0))
write_mem(hp, peasant["addr"] + 0x388, struct.pack("<HH", target_x, target_y))
write_mem(hp, peasant["addr"] + 0x384, struct.pack("<H", 3))
time.sleep(2.0)

# Train yusaeng
yusaeng = train_unit(hp, hq["addr"], 0xAB, 0x70)
print(f"Yusaeng trained at ({yusaeng['x']}, {yusaeng['y']})")

# Re-read peasant pos
p_cur = next(c for c in find_chars(hp) if c["idx"] == peasant["idx"])
print(f"Peasant current pos: ({p_cur['x']}, {p_cur['y']})")

# Set enemy & HP
write_mem(hp, peasant["addr"] + 0x8E, b"\x01")
write_mem(hp, peasant["addr"] + 0xB4, struct.pack("<i", 5000))
p_handle = read_u32(hp, peasant["addr"] + 0x29C)

# Order attack
write_mem(hp, yusaeng["addr"] + 0x380, struct.pack("<H", 1))
write_mem(hp, yusaeng["addr"] + 0x388, struct.pack("<HH", p_cur["x"], p_cur["y"]))
write_mem(hp, yusaeng["addr"] + 0x38C, struct.pack("<I", p_handle))
write_mem(hp, yusaeng["addr"] + 0x384, struct.pack("<H", 4))

print("Monitoring combat for 10 seconds...")
t0 = time.time()
while time.time() - t0 < 10.0:
    p_cur = next(c for c in find_chars(hp) if c["idx"] == peasant["idx"])
    y_cur = next(c for c in find_chars(hp) if c["idx"] == yusaeng["idx"])
    para = read_u16(hp, 0x0066BB00 + peasant["idx"] * CHAR_STRIDE)
    print(f"t={time.time()-t0:.1f}s | Yusaeng pos=({y_cur['x']},{y_cur['y']}) slot={y_cur['ani_slot']} | Peasant HP={p_cur['hp']} para={para}")
    if para > 0:
        print("PARALYSIS DETECTED:", para)
        break
    time.sleep(0.5)

subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
