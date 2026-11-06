r"""
Capture All Distinct In-Game Attack Motion Frames (Step 0..N) + Projectile + Target Hit for All 10 Joseon Units (0x70..0x79).

For every unit (0x70..0x79), this script:
1. Spawns the unit in live YM/dawn/dawn.exe skirmish battle.
2. Orders the unit to attack an enemy target (8000 HP).
3. Captures the live in-game framebuffer at EVERY distinct attack animation step (`cltChar + 0x7C`: Step 0, 1, 2, 3, 4, 5, 6, 7...)
   as well as active projectile (`cltBullet`) and on-hit smoke (`cltSmoke`) frames.
4. Saves:
   - Distinct full-screen action frames (windup, swing/cast, impact/projectile, follow-through)
   - A composite multi-motion strip (`unit_0xXX_attack_motions.png`) showing 6~8 distinct in-game attack frames + target hit side-by-side (2x zoomed) so every motion of the attack is clearly visible.
"""

from __future__ import annotations

import ctypes
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

from tools.live_skirmish_combat_capture import (
    CHAR_ALIVE_ARRAY,
    CHAR_BASE,
    CHAR_STRIDE,
    UNIT_SPECS,
    click,
    find_bullets,
    find_chars,
    find_smokes,
    grab_framebuffer,
    issue_move_tile,
    read_mem,
    read_u16,
    read_u32,
    wait_state,
    write_mem,
)

kernel32 = ctypes.windll.kernel32


def capture_all_10_unit_attack_motions(
    dawn_dir: Path,
    output_dir: Path,
    artifact_dir: Path,
    target_kinds: list[int] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
    time.sleep(0.3)

    p = subprocess.Popen([str(dawn_dir / "dawn.exe")], cwd=str(dawn_dir))
    hp = kernel32.OpenProcess(0x1F0FFF, False, p.pid)

    try:
        assert wait_state(hp, 9), "Main Menu (State 9) timeout"
        write_mem(hp, 0x0041C916, b"\x90" * 11)
        time.sleep(0.2)
        click(hp, 200, 550)

        assert wait_state(hp, 7), "Protocol Select (State 7) timeout"
        time.sleep(0.2)
        click(hp, 595, 558)

        assert wait_state(hp, 5), "Skirmish Lobby (State 5) timeout"
        time.sleep(0.3)

        slots_raw = bytearray(read_mem(hp, 0x00632CC0, 48))
        slots_raw[0] = 1
        slots_raw[2] = 0
        slots_raw[5] = 0
        slots_raw[6] = 2
        slots_raw[8] = 1
        slots_raw[11] = 1
        write_mem(hp, 0x00632CC0, bytes(slots_raw))
        write_mem(hp, 0x01065D22, struct.pack("<H", 1))
        time.sleep(0.2)
        click(hp, 595, 558)

        assert wait_state(hp, 3, timeout=20.0), "In-Game Battle (State 3) timeout"
        time.sleep(0.8)
        write_mem(hp, 0x00956784, struct.pack("<II", 100000, 100000))

        chars = find_chars(hp)
        hq_char = next(c for c in chars if c["kind"] == 0x31 and c["player"] == 0)
        hq_addr = hq_char["addr"]
        hx, hy = hq_char["x"], hq_char["y"]

        peasant = next(c for c in chars if c["kind"] < 0x28 and c["player"] == 0)
        p_addr = peasant["addr"]
        p_idx = peasant["idx"]
        p_alive = peasant["alive"]
        p_handle = read_u32(hp, p_addr + 0x29C)

        # Move peasant to courtyard in front of HQ
        issue_move_tile(hp, p_addr, hx + 2, hy + 4)
        time.sleep(1.8)
        p_cur = next(c for c in find_chars(hp) if c["idx"] == p_idx)
        px, py = p_cur["x"], p_cur["y"]
        print(f"[*] Peasant settled at ({px}, {py})")

        specs_to_run = [s for s in UNIT_SPECS if (target_kinds is None or s["kind"] in target_kinds)]

        for spec in specs_to_run:
            kind_id = spec["kind"]
            u_name = spec["name"]
            cmd_id = 0xAB + spec["cmd_idx"]
            is_ranged = spec["is_ranged"]

            # Hide peasant during spawn and move
            write_mem(hp, CHAR_ALIVE_ARRAY + p_idx * 2, struct.pack("<H", 0))

            # Train unit at HQ
            write_mem(hp, hq_addr + 0x290, struct.pack("<H", 1))
            write_mem(hp, hq_addr + 0x380, struct.pack("<H", 0))
            write_mem(hp, hq_addr + 0x388, struct.pack("<II", 0, 0))
            write_mem(hp, hq_addr + 0x384, struct.pack("<I", cmd_id))

            u_addr = None
            u_char_idx = None
            t0 = time.time()
            while time.time() - t0 < 8.0:
                if read_u16(hp, hq_addr + 0x290) == 0x0F:
                    write_mem(hp, hq_addr + 0x1F8, struct.pack("<H", 5000))
                for c in find_chars(hp):
                    if c["kind"] == kind_id:
                        u_addr = c["addr"]
                        u_char_idx = c["idx"]
                        break
                if u_addr:
                    break
                time.sleep(0.02)

            assert u_addr is not None, f"Failed to spawn 0x{kind_id:02X}"
            time.sleep(0.3)

            # Move unit to open courtyard in front of HQ so roof never obscures sprite
            if not is_ranged:
                issue_move_tile(hp, u_addr, hx + 2, hy + 3)
                time.sleep(1.4)

            # Unhide peasant as Enemy Player 1 with 9000 HP
            write_mem(hp, CHAR_ALIVE_ARRAY + p_idx * 2, struct.pack("<H", p_alive))
            write_mem(hp, p_addr + 0x8E, b"\x01")
            write_mem(hp, p_addr + 0xB4, struct.pack("<i", 9000))
            write_mem(hp, p_addr + 0x290, struct.pack("<H", 1))  # Keep target standing still
            p_cur = next(c for c in find_chars(hp) if c["idx"] == p_idx)
            px, py = p_cur["x"], p_cur["y"]

            if kind_id in (0x70, 0x71, 0x73, 0x76, 0x77, 0x79):
                write_mem(hp, u_addr + 0xB8, struct.pack("<i", 120))  # Full MP at +0xB8
                write_mem(hp, u_addr + 0xB0, struct.pack("<H", 120))

            # Order unit to attack peasant
            write_mem(hp, u_addr + 0x380, struct.pack("<H", 1))
            write_mem(hp, u_addr + 0x388, struct.pack("<HH", px, py))
            write_mem(hp, u_addr + 0x38C, struct.pack("<I", p_handle))
            write_mem(hp, u_addr + 0x384, struct.pack("<H", 4))

            # Map step_idx -> (Image, spr_frame, ux, uy, bullets, smokes)
            step_frames: dict[int, tuple[Image.Image, int, int, int, int, int]] = {}
            hit_smoking_frames: list[tuple[Image.Image, int, int, int, int]] = []

            t_start = time.time()
            prev_ehp = 9000
            while time.time() - t_start < 8.0:
                c_raw = read_mem(hp, u_addr, CHAR_STRIDE)
                slot_val = struct.unpack_from("<I", c_raw, 0x80)[0]
                step_val = struct.unpack_from("<I", c_raw, 0x7C)[0]
                spr_val = struct.unpack_from("<I", c_raw, 0x4C)[0]
                ux, uy = struct.unpack_from("<HH", c_raw, 0x2A2)
                ehp = struct.unpack_from("<i", read_mem(hp, p_addr + 0xB4, 4))[0]
                bullets = find_bullets(hp)
                smokes = find_smokes(hp)

                # Re-issue attack if unit stopped at destination before attacking
                if slot_val == 1 and len(step_frames) == 0:
                    write_mem(hp, u_addr + 0x380, struct.pack("<H", 1))
                    write_mem(hp, u_addr + 0x388, struct.pack("<HH", px, py))
                    write_mem(hp, u_addr + 0x38C, struct.pack("<I", p_handle))
                    write_mem(hp, u_addr + 0x384, struct.pack("<H", 4))

                if slot_val == 4:
                    im = grab_framebuffer(hp)
                    if step_val not in step_frames or (len(bullets) + len(smokes) > step_frames[step_val][4] + step_frames[step_val][5]):
                        step_frames[step_val] = (im, spr_val, ux, uy, len(bullets), len(smokes))
                    if len(smokes) > 0 or len(bullets) > 0 or ehp < prev_ehp:
                        hit_smoking_frames.append((im, step_val, spr_val, ux, uy))
                        prev_ehp = ehp

                if len(step_frames) >= 8 and len(hit_smoking_frames) >= 2:
                    break
                time.sleep(0.012)

            sorted_steps = sorted(step_frames.keys())
            print(
                f"[0x{kind_id:02X} {u_name}] Captured {len(sorted_steps)} distinct attack steps: {sorted_steps} "
                f"(spr_frames={[step_frames[s][1] for s in sorted_steps]})"
            )

            if sorted_steps:
                _, _, ux, uy, _, _ = step_frames[sorted_steps[0]]
            else:
                im_fb = grab_framebuffer(hp)
                c_raw = read_mem(hp, u_addr, CHAR_STRIDE)
                ux, uy = struct.unpack_from("<HH", c_raw, 0x2A2)
                step_frames[0] = (im_fb, 0, ux, uy, 0, 0)
                sorted_steps = [0]

            pcx = 420 + (px - hx - (py - hy)) * 32
            pcy = 210 + (px - hx + (py - hy)) * 24

            panel_w, panel_h = 150, 150
            steps_to_show = sorted_steps[:8]
            num_panels = max(1, len(steps_to_show) + (1 if hit_smoking_frames else 0))
            strip_img = Image.new("RGB", (panel_w * num_panels, panel_h + 26), (18, 20, 26))
            draw = ImageDraw.Draw(strip_img)

            for idx_p, s_val in enumerate(steps_to_show):
                im_s, spr_s, u_x, u_y, b_cnt, sm_cnt = step_frames[s_val]
                cx = max(90, min(710, 420 + (u_x - hx - (u_y - hy)) * 32))
                cy = max(90, min(410, 210 + (u_x - hx + (u_y - hy)) * 24))
                crop = im_s.crop((cx - 75, cy - 75, cx + 75, cy + 75))
                strip_img.paste(crop, (idx_p * panel_w, 26))
                draw.rectangle([idx_p * panel_w, 0, (idx_p + 1) * panel_w - 1, panel_h + 25], outline=(90, 100, 120))
                draw.text((idx_p * panel_w + 6, 6), f"Atk Step {s_val} (Spr#{spr_s})", fill=(255, 230, 120))

            if hit_smoking_frames:
                im_h, s_h, spr_h, _, _ = hit_smoking_frames[-1]
                cx_p = max(90, min(710, pcx))
                cy_p = max(90, min(410, pcy))
                crop_h = im_h.crop((cx_p - 75, cy_p - 75, cx_p + 75, cy_p + 75))
                idx_p = len(steps_to_show)
                strip_img.paste(crop_h, (idx_p * panel_w, 26))
                draw.rectangle([idx_p * panel_w, 0, (idx_p + 1) * panel_w - 1, panel_h + 25], outline=(255, 100, 100))
                draw.text((idx_p * panel_w + 6, 6), "Target Hit / Effect", fill=(255, 130, 130))

            strip_name = f"unit_0x{kind_id:02X}_attack_motions.png"
            strip_path = output_dir / strip_name
            strip_img.save(strip_path)
            shutil.copy2(strip_path, artifact_dir / strip_name)

            if len(sorted_steps) >= 3:
                s_early = sorted_steps[0]
                s_mid = sorted_steps[len(sorted_steps) // 2]
                s_late = sorted_steps[-1]
                for tag, s_k in [("step1_windup", s_early), ("step2_swing", s_mid), ("step3_follow", s_late)]:
                    fn = f"unit_0x{kind_id:02X}_{tag}.png"
                    p_out = output_dir / fn
                    step_frames[s_k][0].save(p_out)
                    shutil.copy2(p_out, artifact_dir / fn)

            # Clean up unit
            write_mem(hp, CHAR_ALIVE_ARRAY + u_char_idx * 2, struct.pack("<H", 0))
            write_mem(hp, u_addr + 0xB4, struct.pack("<i", 0))

        kernel32.CloseHandle(hp)
    finally:
        p.terminate()
        try:
            p.wait(timeout=3)
        except Exception:
            p.kill()


if __name__ == "__main__":
    targets = [int(x, 0) for x in sys.argv[1:]] if len(sys.argv) > 1 else None
    capture_all_10_unit_attack_motions(
        dawn_dir=Path("YM/dawn").resolve(),
        output_dir=Path("output/screenshots_round7").resolve(),
        artifact_dir=Path(r"C:\Users\bpsco_93p6pse\.gemini\antigravity\brain\012fe533-910e-484f-9444-ed8db88cb5d7"),
        target_kinds=targets,
    )
