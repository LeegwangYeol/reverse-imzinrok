import ctypes
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, ".")

from tools.live_harness_globals import (
    kernel32, read_mem, write_mem, read_u16, read_u32, click,
    grab_framebuffer, find_chars, select_single_char, issue_move_tile,
    spawn_unit_via_hq, launch_and_enter_joseon_skirmish, CHAR_STRIDE
)

def run_showcase():
    print("=" * 70)
    print("  CAPTURING LIVE IN-GAME SCREENSHOTS FROM RUNNING DAWN.EXE")
    print("=" * 70)

    out_dir = Path("output/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    art_dir = Path(r"C:\Users\bpsco_93p6pse\.gemini\antigravity\brain\012fe533-910e-484f-9444-ed8db88cb5d7")

    proc, hp, hq, peasant = launch_and_enter_joseon_skirmish()
    print(f"[*] Skirmish Battle State 3 entered: Joseon HQ at ({hq['x']}, {hq['y']})")

    try:
        # 1. Select Joseon HQ to show custom training buttons in Command Card
        print("[*] Shot 1: Joseon HQ Selected (Command Card showing custom unit buttons)...")
        select_single_char(hp, hq)
        time.sleep(0.5)
        im1 = grab_framebuffer(hp)
        im1.save(out_dir / "01_joseon_hq_cmdcard.png")
        im1.save(art_dir / "01_joseon_hq_cmdcard.png")
        print("    [SAVED] 01_joseon_hq_cmdcard.png")

        # 2. Spawn units around HQ courtyard
        print("[*] Shot 2: Spawning Joseon New Units in Courtyard...")
        hq_x, hq_y = hq["x"], hq["y"]
        spawned = []
        # Spawn 유생 (0x70), 검술 낭인 (0x71), 조총 낭인 (0x72), 구미호 (0x73),
        # 조선 호랑이 (0x75), 털가면 (0x76), 설녀 (0x77), 조선 도깨비 (0x78), 불가살이 (0x79)
        unit_kinds = [0x70, 0x71, 0x72, 0x73, 0x75, 0x76, 0x77, 0x78, 0x79]
        for kind in unit_kinds:
            u = spawn_unit_via_hq(hp, hq["addr"], kind)
            spawned.append(u)
            print(f"    -> Spawned Unit Kind 0x{kind:02X} (idx={u['idx']})")

        # Arrange units in a neat two-row line in the courtyard
        for i, u in enumerate(spawned):
            tx = hq_x - 3 + (i % 5) * 2
            ty = hq_y + 3 + (i // 5) * 2
            issue_move_tile(hp, u["addr"], tx, ty)
        time.sleep(2.0)

        # Select 불가살이 (0x79) to show its custom portrait and status in UI
        bulgasari = next((u for u in spawned if u["kind"] == 0x79), spawned[-1])
        select_single_char(hp, bulgasari)
        time.sleep(0.5)
        im2 = grab_framebuffer(hp)
        im2.save(out_dir / "02_joseon_new_units_field.png")
        im2.save(art_dir / "02_joseon_new_units_field.png")
        print("    [SAVED] 02_joseon_new_units_field.png")

        # 3. Combat Showcase: 털가면 (0x76) attacks enemy peasant -> Freeze (0x3C01)
        print("[*] Shot 3: 털가면 Freeze Combat Action...")
        furhead = next((u for u in spawned if u["kind"] == 0x76), None)
        # Move peasant close to furhead
        p_addr = peasant["addr"]
        p_idx = peasant["idx"]
        write_mem(hp, p_addr + 0x8E, b"\x01")  # Enemy
        write_mem(hp, p_addr + 0xB4, struct.pack("<i", 10000))
        target_x, target_y = hq_x + 1, hq_y + 7
        issue_move_tile(hp, p_addr, target_x, target_y)
        time.sleep(1.0)
        p_cur = next(c for c in find_chars(hp) if c["idx"] == p_idx)
        p_handle = read_u32(hp, p_addr + 0x29C)

        # Order Furhead attack
        write_mem(hp, furhead["addr"] + 0x380, struct.pack("<H", 1))
        write_mem(hp, furhead["addr"] + 0x388, struct.pack("<HH", p_cur["x"], p_cur["y"]))
        write_mem(hp, furhead["addr"] + 0x38C, struct.pack("<I", p_handle))
        write_mem(hp, furhead["addr"] + 0x384, struct.pack("<H", 4))

        # Wait for freeze
        t_shot3 = time.time()
        while time.time() - t_shot3 < 6.0:
            para = read_u16(hp, 0x0066BB00 + p_idx * CHAR_STRIDE)
            if para > 0:
                print(f"    -> Freeze hit! Para timer={para}")
                break
            time.sleep(0.05)

        time.sleep(0.2)
        im3 = grab_framebuffer(hp)
        im3.save(out_dir / "03_furhead_freeze_combat.png")
        im3.save(art_dir / "03_furhead_freeze_combat.png")
        print("    [SAVED] 03_furhead_freeze_combat.png")

        # 4. Combat Showcase: 유생 (0x70) paralysis
        print("[*] Shot 4: 유생 Paralysis Action...")
        yusaeng = next((u for u in spawned if u["kind"] == 0x70), None)
        # Stop furhead
        write_mem(hp, furhead["addr"] + 0x380, struct.pack("<H", 0))
        write_mem(hp, furhead["addr"] + 0x384, struct.pack("<H", 1))

        # Order Yusaeng attack
        write_mem(hp, yusaeng["addr"] + 0x380, struct.pack("<H", 1))
        write_mem(hp, yusaeng["addr"] + 0x388, struct.pack("<HH", p_cur["x"], p_cur["y"]))
        write_mem(hp, yusaeng["addr"] + 0x38C, struct.pack("<I", p_handle))
        write_mem(hp, yusaeng["addr"] + 0x384, struct.pack("<H", 4))

        t_shot4 = time.time()
        while time.time() - t_shot4 < 5.0:
            para = read_u16(hp, 0x0066BB00 + p_idx * CHAR_STRIDE)
            if para > 100:
                print(f"    -> Yusaeng paralysis hit! Para timer={para}")
                break
            time.sleep(0.05)

        time.sleep(0.2)
        im4 = grab_framebuffer(hp)
        im4.save(out_dir / "04_yusaeng_paralysis_combat.png")
        im4.save(art_dir / "04_yusaeng_paralysis_combat.png")
        print("    [SAVED] 04_yusaeng_paralysis_combat.png")

        print("=" * 70)
        print("  ALL 4 LIVE IN-GAME SCREENSHOTS CAPTURED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)

if __name__ == "__main__":
    run_showcase()
