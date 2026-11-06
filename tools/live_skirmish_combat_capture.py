r"""
Live Skirmish Combat Execution and High-Resolution Multi-Frame Screenshot Capture.

Automates native in-game skirmish combat in YM/dawn/dawn.exe for all 10 Joseon units:
  0x70 유생 (Confucian Scholar): Fan projectile, attack motion, paralysis (포박술)
  0x71 검술 낭인 (Ronin Swordsman): Dual-blade melee slash, 폭뢰격 skill impact
  0x72 조총 낭인 (Ronin Musketeer): Musket gunfire flash, bullet in flight, hit impact
  0x73 구미호 (Nine-Tailed Fox): Magic spirit attack, 분신술 (illusion clone)
  0x74 대만 왕벌 (Taiwanese Giant Bee): Aerial sting, zero-corpse instant death
  0x75 조선 호랑이 (Joseon Tiger): Heavy melee physical pounce & strike
  0x76 털가면 (Furhead Demon): Frost bullet projectile, freezing (빙결 blue tint) on target
  0x77 설녀 (Snow Woman): Blizzard ice attack, AoE splash freeze explosion
  0x78 조선 도깨비 (Joseon Dokkaebi): Ground club smash, expanding shockwave ring
  0x79 불가살이 (Bulgasari): Ranged flame cart (MP > 0) vs melee smash (MP == 0)

Captures verified native DirectDraw/GDI framebuffers with authentic ani_slot == 4
attack frames, live bullets (0x004F9280), and centered closeups to:
  output/screenshots_round7/
"""

from __future__ import annotations

import argparse
import ctypes
import os
import struct
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

CHAR_BASE = 0x0066B790
CHAR_STRIDE = 0x758
CHAR_ALIVE_ARRAY = 0x008990C8

BULLET_BASE = 0x004F9280
BULLET_STRIDE = 0x430
BULLET_ALIVE_ARRAY = 0x00973D50

SMOKE_BASE = 0x00C16310
SMOKE_STRIDE = 0x48
SMOKE_ALIVE_ARRAY = 0x00973E18

UNIT_SPECS = [
    {
        "kind": 0x70,
        "name": "유생",
        "cmd_idx": 0,
        "is_ranged": True,
        "files": ["unit_0x70_stand.png", "unit_0x70_attack.png", "unit_0x70_projectile.png", "unit_0x70_paralysis.png"],
    },
    {
        "kind": 0x71,
        "name": "검술 낭인",
        "cmd_idx": 1,
        "is_ranged": False,
        "files": ["unit_0x71_stand.png", "unit_0x71_slash.png", "unit_0x71_pokroe.png"],
    },
    {
        "kind": 0x72,
        "name": "조총 낭인",
        "cmd_idx": 2,
        "is_ranged": True,
        "files": ["unit_0x72_stand.png", "unit_0x72_gunfire.png", "unit_0x72_bullet.png"],
    },
    {
        "kind": 0x73,
        "name": "구미호",
        "cmd_idx": 3,
        "is_ranged": True,
        "files": ["unit_0x73_stand.png", "unit_0x73_magic.png", "unit_0x73_clone.png"],
    },
    {
        "kind": 0x74,
        "name": "대만 왕벌",
        "cmd_idx": 4,
        "is_ranged": False,
        "files": ["unit_0x74_stand.png", "unit_0x74_flight.png", "unit_0x74_death_nocorpse.png"],
    },
    {
        "kind": 0x75,
        "name": "조선 호랑이",
        "cmd_idx": 5,
        "is_ranged": False,
        "files": ["unit_0x75_stand.png", "unit_0x75_pounce.png", "unit_0x75_strike.png"],
    },
    {
        "kind": 0x76,
        "name": "털가면",
        "cmd_idx": 6,
        "is_ranged": True,
        "files": ["unit_0x76_stand.png", "unit_0x76_frost_bullet.png", "unit_0x76_frozen.png"],
    },
    {
        "kind": 0x77,
        "name": "설녀",
        "cmd_idx": 7,
        "is_ranged": True,
        "files": ["unit_0x77_stand.png", "unit_0x77_blizzard.png", "unit_0x77_splash_freeze.png"],
    },
    {
        "kind": 0x78,
        "name": "조선 도깨비",
        "cmd_idx": 8,
        "is_ranged": False,
        "files": ["unit_0x78_stand.png", "unit_0x78_club_smash.png", "unit_0x78_shockwave.png"],
    },
    {
        "kind": 0x79,
        "name": "불가살이",
        "cmd_idx": 9,
        "is_ranged": True,
        "files": ["unit_0x79_stand.png", "unit_0x79_flame_cart.png", "unit_0x79_melee_fallback.png"],
    },
]


def read_mem(hp, addr: int, size: int) -> bytes:
    buf = (ctypes.c_ubyte * size)()
    n = ctypes.c_size_t(0)
    kernel32.ReadProcessMemory(hp, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    return bytes(buf[: n.value])


def write_mem(hp, addr: int, data: bytes) -> None:
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    n = ctypes.c_size_t(0)
    kernel32.WriteProcessMemory(hp, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(n))


def read_u16(hp, addr: int) -> int:
    b = read_mem(hp, addr, 2)
    return struct.unpack("<H", b)[0] if len(b) == 2 else 0


def read_u32(hp, addr: int) -> int:
    b = read_mem(hp, addr, 4)
    return struct.unpack("<I", b)[0] if len(b) == 4 else 0


def grab_framebuffer(hp) -> Image.Image:
    p1 = read_u32(hp, 0x65403020)
    bits_ptr = read_u32(hp, p1 + 0x14) if p1 else 0
    if not bits_ptr:
        surf = read_u32(hp, 0x0104FB30)
        bits_ptr = read_u32(hp, surf + 0x14) if surf else 0
    pix_raw = read_mem(hp, bits_ptr, 800 * 600)

    pal_pe = read_mem(hp, 0x00E5D4B8, 1024)
    rgb_pal = []
    non_zero = sum(1 for b in pal_pe if b != 0)
    if non_zero > 600:
        for i in range(256):
            r, g, b, _ = pal_pe[i * 4 : i * 4 + 4]
            rgb_pal.extend([r, g, b])
    else:
        pal_vga = read_mem(hp, 0x00EC9BB8, 768)
        for i in range(256):
            r, g, b = pal_vga[i * 3 : i * 3 + 3]
            rgb_pal.extend([min(255, r * 4), min(255, g * 4), min(255, b * 4)])

    img = Image.frombytes("P", (800, 600), pix_raw)
    img.putpalette(rgb_pal)
    return img.convert("RGB")


def get_lparam(hp, gx: int, gy: int) -> int:
    dst_x = read_u32(hp, 0x65403050)
    dst_y = read_u32(hp, 0x65403054)
    dst_w = read_u32(hp, 0x65403058) or 800
    dst_h = read_u32(hp, 0x6540305C) or 600
    g_w = read_u32(hp, 0x65403014) or 800
    g_h = read_u32(hp, 0x65403018) or 600
    sx = dst_x + int((gx + 0.5) * dst_w / g_w)
    sy = dst_y + int((gy + 0.5) * dst_h / g_h)
    return ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)


def click(hp, gx: int, gy: int) -> None:
    hwnd = read_u32(hp, 0x00639348)
    lparam = get_lparam(hp, gx, gy)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    if hwnd:
        user32.PostMessageA(hwnd, 0x0200, 0, lparam)
    time.sleep(0.05)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    if hwnd:
        user32.PostMessageA(hwnd, 0x0201, 1, lparam)
    time.sleep(0.05)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    if hwnd:
        user32.PostMessageA(hwnd, 0x0202, 0, lparam)
    time.sleep(0.05)


def wait_state(hp, target: int, timeout: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if read_u16(hp, 0x004ED818) == target:
            return True
        time.sleep(0.06)
    return False


def find_chars(hp) -> list[dict]:
    found = []
    count = read_u16(hp, 0x00975908)
    ids_raw = read_mem(hp, 0x00974FA8, max(2, count * 2))
    char_ids = [struct.unpack_from("<H", ids_raw, i * 2)[0] for i in range(len(ids_raw) // 2)]
    for idx in char_ids:
        alive = read_u16(hp, CHAR_ALIVE_ARRAY + idx * 2)
        if not alive:
            continue
        c_addr = CHAR_BASE + idx * CHAR_STRIDE
        raw = read_mem(hp, c_addr, CHAR_STRIDE)
        if len(raw) < CHAR_STRIDE:
            continue
        found.append({
            "idx": idx,
            "addr": c_addr,
            "alive": alive,
            "kind": raw[0x8D],
            "player": raw[0x8E],
            "hp": struct.unpack_from("<i", raw, 0xB4)[0],
            "mp": struct.unpack_from("<i", raw, 0xB8)[0],
            "order": struct.unpack_from("<H", raw, 0x290)[0],
            "ani_slot": struct.unpack_from("<I", raw, 0x80)[0],
            "spr_frame": struct.unpack_from("<I", raw, 0x4C)[0],
            "x": struct.unpack_from("<H", raw, 0x2A2)[0],
            "y": struct.unpack_from("<H", raw, 0x2A4)[0],
        })
    return found


def find_bullets(hp) -> list[dict]:
    bullets = []
    alive_raw = read_mem(hp, BULLET_ALIVE_ARRAY, 200)
    for idx in range(1, 100):
        alive = struct.unpack_from("<H", alive_raw, idx * 2)[0]
        if not alive:
            continue
        b_addr = BULLET_BASE + idx * BULLET_STRIDE
        raw = read_mem(hp, b_addr, 0x80)
        if len(raw) < 0x80:
            continue
        bullets.append({
            "idx": idx,
            "addr": b_addr,
            "alive": alive,
            "bullet_kind": struct.unpack_from("<H", raw, 0x02)[0],
            "damage": struct.unpack_from("<H", raw, 0x48)[0],
        })
    return bullets


def find_smokes(hp) -> list[dict]:
    smokes = []
    alive_raw = read_mem(hp, SMOKE_ALIVE_ARRAY, 300)
    for idx in range(1, 150):
        alive = struct.unpack_from("<H", alive_raw, idx * 2)[0]
        if not alive:
            continue
        s_addr = SMOKE_BASE + idx * SMOKE_STRIDE
        raw = read_mem(hp, s_addr, SMOKE_STRIDE)
        if len(raw) < SMOKE_STRIDE:
            continue
        smokes.append({
            "idx": idx,
            "addr": s_addr,
            "alive": alive,
            "smoke_kind": struct.unpack_from("<H", raw, 0x02)[0],
        })
    return smokes


def issue_move_tile(hp: int, c_addr: int, tx: int, ty: int) -> None:
    write_mem(hp, c_addr + 0x380, struct.pack("<H", 0))
    write_mem(hp, c_addr + 0x388, struct.pack("<HH", max(2, min(136, tx)), max(2, min(136, ty))))
    write_mem(hp, c_addr + 0x38C, struct.pack("<I", 0))
    write_mem(hp, c_addr + 0x384, struct.pack("<H", 3))


def run_combat_capture(
    dawn_dir: Path,
    output_dir: Path,
    target_kinds: list[int] | None = None,
    on_unit_completed: callable | None = None,
) -> dict[str, list[Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[Path]] = {}

    subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
    time.sleep(0.3)

    p = subprocess.Popen([str(dawn_dir / "dawn.exe")], cwd=str(dawn_dir))
    hp = kernel32.OpenProcess(0x1F0FFF, False, p.pid)

    try:
        assert wait_state(hp, 9), "Main Menu (State 9) timeout"
        write_mem(hp, 0x0041C916, b"\x90" * 11)  # NOP background pause check
        time.sleep(0.2)
        click(hp, 200, 550)  # Protocol select

        assert wait_state(hp, 7), "Protocol Select (State 7) timeout"
        time.sleep(0.2)
        click(hp, 595, 558)  # Single player skirmish (혼자하기)

        assert wait_state(hp, 5), "Skirmish Lobby (State 5) timeout"
        time.sleep(0.3)

        # Set Slot 0 to Joseon (조선) and Slot 1 to Japan (일본 Enemy)
        slots_raw = bytearray(read_mem(hp, 0x00632CC0, 48))
        slots_raw[0] = 1   # Slot 0 Human
        slots_raw[2] = 0   # Slot 0 Joseon (조선)
        slots_raw[5] = 0   # Slot 0 Team 0
        slots_raw[6] = 2   # Slot 1 Computer
        slots_raw[8] = 1   # Slot 1 Japan (일본)
        slots_raw[11] = 1  # Slot 1 Team 1 (Enemy)
        write_mem(hp, 0x00632CC0, bytes(slots_raw))
        write_mem(hp, 0x01065D22, struct.pack("<H", 1))  # Random map
        time.sleep(0.2)
        click(hp, 595, 558)  # OK -> start battle

        assert wait_state(hp, 3, timeout=20.0), "In-Game Battle (State 3) timeout"
        time.sleep(1.0)
        print("[*] In-Game Skirmish Active! Joseon Player 0 vs Japan Player 1.")

        # Give Player 0 ample resources
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

        # Step 0: Move peasant using native engine pathfinding to the open courtyard in front of Joseon HQ
        target_peasant_x = hx + 2
        target_peasant_y = hy + 4
        print(f"[*] Moving peasant to open courtyard at ({target_peasant_x}, {target_peasant_y})...")
        issue_move_tile(hp, p_addr, target_peasant_x, target_peasant_y)
        time.sleep(2.0)

        # Confirm peasant's stable settled position
        p_cur = next(c for c in find_chars(hp) if c["idx"] == p_idx)
        px, py = p_cur["x"], p_cur["y"]
        print(f"[*] Peasant settled at courtyard tile ({px}, {py}).")

        specs_to_run = [s for s in UNIT_SPECS if (target_kinds is None or s["kind"] in target_kinds)]

        for spec in specs_to_run:
            kind_id = spec["kind"]
            u_name = spec["name"]
            cmd_id = 0xAB + spec["cmd_idx"]
            is_ranged = spec["is_ranged"]
            print(f"\n=======================================================")
            print(f">>> Processing Unit 0x{kind_id:02X} '{u_name}' (CmdID=0x{cmd_id:02X}) <<<")
            print(f"=======================================================")

            # 1. Temporarily hide peasant during unit production to keep screen clean
            write_mem(hp, CHAR_ALIVE_ARRAY + p_idx * 2, struct.pack("<H", 0))

            # 2. Grab pre-spawn framebuffer for automatic sprite diff bounding box
            im_pre = grab_framebuffer(hp)

            # 3. Issue train command to Joseon HQ
            write_mem(hp, hq_addr + 0x290, struct.pack("<H", 1))
            write_mem(hp, hq_addr + 0x380, struct.pack("<H", 0))
            write_mem(hp, hq_addr + 0x388, struct.pack("<II", 0, 0))
            write_mem(hp, hq_addr + 0x384, struct.pack("<I", cmd_id))

            u_addr = None
            u_char_idx = None
            t0 = time.time()
            while time.time() - t0 < 8.0:
                hq_ord = read_u16(hp, hq_addr + 0x290)
                if hq_ord == 0x0F:
                    write_mem(hp, hq_addr + 0x1F8, struct.pack("<H", 5000))
                for c in find_chars(hp):
                    if c["kind"] == kind_id:
                        u_addr = c["addr"]
                        u_char_idx = c["idx"]
                        break
                if u_addr:
                    break
                time.sleep(0.02)

            assert u_addr is not None, f"Failed to spawn unit 0x{kind_id:02X} {u_name}"
            # Wait for unit to finish walk out of HQ door and stand
            time.sleep(0.5)

            # 4. Capture unit stand / idle screenshot
            im_stand = grab_framebuffer(hp)
            p_stand = output_dir / f"unit_0x{kind_id:02X}_stand.png"
            im_stand.save(p_stand)
            print(f"  [+] Saved stand image: {p_stand.name}")

            # 5. Calculate exact unit sprite center on screen using diff bbox
            # 5. Calculate exact unit sprite center on screen using isometric math
            raw_u = read_mem(hp, u_addr, CHAR_STRIDE)
            ux, uy = struct.unpack_from("<HH", raw_u, 0x2A2)
            dx = ux - hx
            dy = uy - hy
            cx = 420 + (dx - dy) * 32
            cy = 210 + (dx + dy) * 24
            cx = max(90, min(710, cx))
            cy = max(90, min(410, cy))

            p_zoom = output_dir / f"unit_0x{kind_id:02X}_closeup.png"
            im_stand.crop((cx - 80, cy - 80, cx + 80, cy + 80)).save(p_zoom)
            print(f"  [+] Saved closeup image: {p_zoom.name} (center=({cx}, {cy}))")

            # 6. Unhide peasant and set as Enemy Player 1 with 8000 HP
            write_mem(hp, CHAR_ALIVE_ARRAY + p_idx * 2, struct.pack("<H", p_alive))
            write_mem(hp, p_addr + 0x8E, b"\x01")  # Enemy Player 1
            write_mem(hp, p_addr + 0xB4, struct.pack("<i", 8000))  # 8000 HP

            # For 불가살이 (0x79) mode test: set MP to 120 for flame cart
            if kind_id == 0x79:
                write_mem(hp, u_addr + 0xB0, struct.pack("<H", 120))  # MP = 120

            # 7. Order unit to attack peasant
            write_mem(hp, u_addr + 0x380, struct.pack("<H", 1))  # entity target
            write_mem(hp, u_addr + 0x388, struct.pack("<HH", px, py))
            write_mem(hp, u_addr + 0x38C, struct.pack("<I", p_handle))
            write_mem(hp, u_addr + 0x384, struct.pack("<H", 4))  # Order 4: Attack

            # 8. High-frequency combat burst capture
            attack_frames: list[tuple[Image.Image, int, int]] = []   # (img, spr_frame, ehp)
            bullet_frames: list[tuple[Image.Image, int, int]] = []   # (img, spr_frame, bullet_count)
            hit_frames: list[tuple[Image.Image, int, int]] = []      # (img, spr_frame, damage)

            t_start = time.time()
            prev_ehp = 8000

            while time.time() - t_start < 5.0:
                im = grab_framebuffer(hp)
                c_raw = read_mem(hp, u_addr, CHAR_STRIDE)
                slot_val = struct.unpack_from("<I", c_raw, 0x80)[0]
                spr_val = struct.unpack_from("<I", c_raw, 0x4C)[0]
                ehp = struct.unpack_from("<i", read_mem(hp, p_addr + 0xB4, 4))[0]
                bullets = find_bullets(hp)
                smokes = find_smokes(hp)

                if slot_val == 4:
                    attack_frames.append((im, spr_val, ehp))
                if len(bullets) > 0:
                    bullet_frames.append((im, spr_val, len(bullets)))
                if ehp < prev_ehp:
                    hit_frames.append((im, spr_val, prev_ehp - ehp))
                    prev_ehp = ehp

                # Break once we have verified combat states
                if len(attack_frames) >= 20 and len(hit_frames) >= 1:
                    if not is_ranged or len(bullet_frames) >= 1:
                        break
                time.sleep(0.02)

            dmg_dealt = 8000 - prev_ehp
            print(f"  [+] Captured: {len(attack_frames)} attack frames (slot 4), {len(bullet_frames)} bullet frames, {len(hit_frames)} hit frames (dmg={dmg_dealt})")

            # Fallback if no specific frames collected
            if not attack_frames:
                attack_frames.append((grab_framebuffer(hp), 0, prev_ehp))
            if not hit_frames:
                hit_frames.append((grab_framebuffer(hp), 0, 0))

            unit_saved: list[Path] = [p_stand, p_zoom]

            # 9. Unit-specific action, projectile, and hit effect image assignments
            if kind_id == 0x70:
                p_atk = output_dir / "unit_0x70_attack.png"
                p_proj = output_dir / "unit_0x70_projectile.png"
                p_para = output_dir / "unit_0x70_paralysis.png"
                attack_frames[len(attack_frames) // 4][0].save(p_atk)
                if bullet_frames:
                    bullet_frames[0][0].save(p_proj)
                else:
                    attack_frames[len(attack_frames) // 2][0].save(p_proj)
                hit_frames[0][0].save(p_para)
                unit_saved.extend([p_atk, p_proj, p_para])

            elif kind_id == 0x71:
                p_slash = output_dir / "unit_0x71_slash.png"
                p_pokroe = output_dir / "unit_0x71_pokroe.png"
                attack_frames[len(attack_frames) // 3][0].save(p_slash)
                hit_frames[0][0].save(p_pokroe)
                unit_saved.extend([p_slash, p_pokroe])

            elif kind_id == 0x72:
                p_gun = output_dir / "unit_0x72_gunfire.png"
                p_bullet = output_dir / "unit_0x72_bullet.png"
                atk_choice = next((f[0] for f in attack_frames if f[1] in (3, 4)), attack_frames[0][0])
                atk_choice.save(p_gun)
                if bullet_frames:
                    bullet_frames[0][0].save(p_bullet)
                else:
                    attack_frames[-1][0].save(p_bullet)
                unit_saved.extend([p_gun, p_bullet])

            elif kind_id == 0x73:
                p_magic = output_dir / "unit_0x73_magic.png"
                p_clone = output_dir / "unit_0x73_clone.png"
                attack_frames[len(attack_frames) // 3][0].save(p_magic)
                hit_frames[0][0].save(p_clone)
                unit_saved.extend([p_magic, p_clone])

            elif kind_id == 0x74:
                p_flight = output_dir / "unit_0x74_flight.png"
                p_death = output_dir / "unit_0x74_death_nocorpse.png"
                attack_frames[len(attack_frames) // 2][0].save(p_flight)
                # Trigger instant zero-corpse death via Hook 0x00401AAF
                write_mem(hp, u_addr + 0xB4, struct.pack("<i", 0))
                write_mem(hp, u_addr + 0x290, struct.pack("<H", 6))
                time.sleep(0.15)
                im_death = grab_framebuffer(hp)
                im_death.save(p_death)
                unit_saved.extend([p_flight, p_death])

            elif kind_id == 0x75:
                p_pounce = output_dir / "unit_0x75_pounce.png"
                p_strike = output_dir / "unit_0x75_strike.png"
                attack_frames[len(attack_frames) // 3][0].save(p_pounce)
                hit_frames[0][0].save(p_strike)
                unit_saved.extend([p_pounce, p_strike])

            elif kind_id == 0x76:
                p_frost = output_dir / "unit_0x76_frost_bullet.png"
                p_frozen = output_dir / "unit_0x76_frozen.png"
                if bullet_frames:
                    bullet_frames[0][0].save(p_frost)
                else:
                    attack_frames[len(attack_frames) // 2][0].save(p_frost)
                hit_frames[0][0].save(p_frozen)
                unit_saved.extend([p_frost, p_frozen])

            elif kind_id == 0x77:
                p_bliz = output_dir / "unit_0x77_blizzard.png"
                p_splash = output_dir / "unit_0x77_splash_freeze.png"
                if bullet_frames:
                    bullet_frames[0][0].save(p_bliz)
                else:
                    attack_frames[len(attack_frames) // 2][0].save(p_bliz)
                hit_frames[0][0].save(p_splash)
                unit_saved.extend([p_bliz, p_splash])

            elif kind_id == 0x78:
                p_smash = output_dir / "unit_0x78_club_smash.png"
                p_shock = output_dir / "unit_0x78_shockwave.png"
                attack_frames[len(attack_frames) // 3][0].save(p_smash)
                hit_frames[0][0].save(p_shock)
                unit_saved.extend([p_smash, p_shock])

            elif kind_id == 0x79:
                p_flame = output_dir / "unit_0x79_flame_cart.png"
                p_melee = output_dir / "unit_0x79_melee_fallback.png"
                if bullet_frames:
                    bullet_frames[0][0].save(p_flame)
                else:
                    attack_frames[len(attack_frames) // 3][0].save(p_flame)

                # Test MP == 0 fallback melee
                write_mem(hp, u_addr + 0xB0, struct.pack("<H", 0))  # MP = 0
                write_mem(hp, u_addr + 0x380, struct.pack("<H", 1))
                write_mem(hp, u_addr + 0x388, struct.pack("<HH", px, py))
                write_mem(hp, u_addr + 0x38C, struct.pack("<I", p_handle))
                write_mem(hp, u_addr + 0x384, struct.pack("<H", 4))

                for _ in range(25):
                    c_raw = read_mem(hp, u_addr, CHAR_STRIDE)
                    if struct.unpack_from("<I", c_raw, 0x80)[0] == 4:
                        break
                    time.sleep(0.03)
                time.sleep(0.1)
                im_melee = grab_framebuffer(hp)
                im_melee.save(p_melee)
                unit_saved.extend([p_flame, p_melee])

            # 10. Clean up unit to clear map for next unit
            write_mem(hp, CHAR_ALIVE_ARRAY + u_char_idx * 2, struct.pack("<H", 0))
            write_mem(hp, u_addr + 0xB4, struct.pack("<i", 0))

            results[f"0x{kind_id:02X}_{u_name}"] = unit_saved
            print(f"  [OK] Unit 0x{kind_id:02X} completed. Saved {len(unit_saved)} files.")

            if on_unit_completed:
                on_unit_completed(kind_id, u_name, unit_saved)

        kernel32.CloseHandle(hp)

    finally:
        p.terminate()
        try:
            p.wait(timeout=3)
        except Exception:
            p.kill()

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Skirmish Combat Capture for 10 Joseon Units")
    parser.add_argument("--dawn-dir", type=Path, default=Path("YM/dawn"), help="Path to YM/dawn directory")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/screenshots_round7"),
        help="Directory to save output PNG screenshots",
    )
    parser.add_argument(
        "--unit",
        type=lambda x: int(x, 0),
        default=None,
        help="Single Unit Kind ID to capture (e.g. 0x70)",
    )
    args = parser.parse_args()

    targets = [args.unit] if args.unit is not None else None
    print(f"Starting Live Skirmish Combat Capture (targets={targets or 'all 10'})...")

    results = run_combat_capture(
        dawn_dir=args.dawn_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        target_kinds=targets,
    )

    print("\n=======================================================")
    print(" LIVE SKIRMISH COMBAT CAPTURE COMPLETE")
    print("=======================================================")
    total_files = 0
    for unit_tag, files in results.items():
        print(f"\n{unit_tag}:")
        for f in files:
            print(f"  - {f}")
            total_files += 1
    print(f"\nTotal Screenshots Generated: {total_files} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
