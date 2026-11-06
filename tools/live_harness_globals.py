"""Global live-process harness functions for Imjinrok 2+ (YM/dawn/dawn.exe).

Provides verified global functions for:
- Launching `YM/dawn/dawn.exe` and entering a 100% Joseon Skirmish battle (`State 3`)
- Direct 8-bit paletted framebuffer capture (`grab_framebuffer`) without black screens
- Reading active characters (`find_chars`), active projectiles (`find_bullets`), and active hit/explosion effects (`find_smokes`)
- Spawning/producing custom units (`0x70..0x79`) via Joseon HQ (`0x31`), Barracks (`0x32`), or Stables (`0x2F`)
- Issuing move/attack orders and centering camera for close-up combat screenshots
"""

import ctypes
import struct
import subprocess
import time
from PIL import Image

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

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
    (0x70, "유생", "unit_0x70_yusaeng"),
    (0x71, "검술 낭인", "unit_0x71_sword_ronin"),
    (0x72, "조총 낭인", "unit_0x72_gun_ronin"),
    (0x73, "구미호", "unit_0x73_gumiho"),
    (0x74, "대만 왕벌", "unit_0x74_hornet"),
    (0x75, "조선 호랑이", "unit_0x75_tiger"),
    (0x76, "털가면", "unit_0x76_furhead"),
    (0x77, "설녀", "unit_0x77_snowwoman"),
    (0x78, "조선 도깨비", "unit_0x78_dokkaebi"),
    (0x79, "불가살이", "unit_0x79_bulgasari"),
]

SLOT_CENTERS = {
    0: (669, 503),
    1: (705, 503),
    2: (741, 503),
    3: (777, 503),
    4: (669, 539),
    5: (705, 539),
    6: (741, 539),
    7: (777, 539),
    8: (669, 575),
    9: (705, 575),
    10: (741, 575),
    11: (777, 575),
}


def read_mem(hp: int, addr: int, size: int) -> bytes:
    buf = (ctypes.c_ubyte * size)()
    n = ctypes.c_size_t(0)
    kernel32.ReadProcessMemory(hp, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    return bytes(buf[: n.value])


def write_mem(hp: int, addr: int, data: bytes) -> None:
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    n = ctypes.c_size_t(0)
    kernel32.WriteProcessMemory(hp, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(n))


def read_u16(hp: int, addr: int) -> int:
    b = read_mem(hp, addr, 2)
    return struct.unpack("<H", b)[0] if len(b) == 2 else 0


def read_u32(hp: int, addr: int) -> int:
    b = read_mem(hp, addr, 4)
    return struct.unpack("<I", b)[0] if len(b) == 4 else 0


def get_lparam(hp: int, gx: int, gy: int) -> int:
    dst_x = read_u32(hp, 0x65403050)
    dst_y = read_u32(hp, 0x65403054)
    dst_w = read_u32(hp, 0x65403058) or 800
    dst_h = read_u32(hp, 0x6540305C) or 600
    g_w = read_u32(hp, 0x65403014) or 800
    g_h = read_u32(hp, 0x65403018) or 600
    sx = dst_x + int((gx + 0.5) * dst_w / g_w)
    sy = dst_y + int((gy + 0.5) * dst_h / g_h)
    return ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)


def move_mouse(hp: int, gx: int, gy: int) -> None:
    hwnd = read_u32(hp, 0x00639348)
    lparam = get_lparam(hp, gx, gy)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    write_mem(hp, 0x004ED814, struct.pack("<hh", gx, gy))
    if hwnd:
        user32.PostMessageA(hwnd, 0x0200, 0, lparam)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    write_mem(hp, 0x004ED814, struct.pack("<hh", gx, gy))


def click(hp: int, gx: int, gy: int, right: bool = False) -> None:
    hwnd = read_u32(hp, 0x00639348)
    lparam = get_lparam(hp, gx, gy)
    move_mouse(hp, gx, gy)
    time.sleep(0.05)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    write_mem(hp, 0x004ED814, struct.pack("<hh", gx, gy))
    down_msg = 0x0204 if right else 0x0201
    up_msg = 0x0205 if right else 0x0202
    wparam = 2 if right else 1
    if hwnd:
        user32.PostMessageA(hwnd, down_msg, wparam, lparam)
    time.sleep(0.05)
    write_mem(hp, 0x00C0CB58, struct.pack("<II", gx, gy))
    write_mem(hp, 0x004ED814, struct.pack("<hh", gx, gy))
    if hwnd:
        user32.PostMessageA(hwnd, up_msg, 0, lparam)
    time.sleep(0.06)


def wait_state(hp: int, target: int, timeout: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if read_u16(hp, 0x004ED818) == target:
            return True
        time.sleep(0.05)
    return False


def grab_framebuffer(hp: int) -> Image.Image:
    """Grab 800x600 8-bit paletted DirectDraw surface from `dawn.exe` process memory."""
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


def find_chars(hp: int) -> list[dict]:
    """Return all active `cltChar` entities in live game memory."""
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
            "max_hp": struct.unpack_from("<i", raw, 0x120)[0],
            "max_mp": struct.unpack_from("<i", raw, 0x124)[0],
            "atk_power": struct.unpack_from("<i", raw, 0x168)[0],
            "mover_type": raw[0x1BC],
            "atb1": struct.unpack_from("<I", raw, 0x1D8)[0],
            "atb2": struct.unpack_from("<I", raw, 0x1DC)[0],
            "attack_atb": struct.unpack_from("<I", raw, 0x1E4)[0],
            "range2": struct.unpack_from("<H", raw, 0x208)[0],
            "range1": struct.unpack_from("<H", raw, 0x20C)[0],
            "bldg_prog": struct.unpack_from("<i", raw, 0x1F4)[0],
            "train_prog": struct.unpack_from("<H", raw, 0x1F8)[0],
            "order": struct.unpack_from("<H", raw, 0x290)[0],
            "handle": struct.unpack_from("<I", raw, 0x29C)[0],
            "ani_act": struct.unpack_from("<I", raw, 0x3C)[0],
            "img_id": struct.unpack_from("<I", raw, 0x48)[0],
            "spr_frame": struct.unpack_from("<I", raw, 0x4C)[0],
            "ani_step": struct.unpack_from("<I", raw, 0x7C)[0],
            "ani_slot": struct.unpack_from("<I", raw, 0x80)[0],
            "x": struct.unpack_from("<H", raw, 0x2A2)[0],
            "y": struct.unpack_from("<H", raw, 0x2A4)[0],
            "px": struct.unpack_from("<i", raw, 0x0C)[0],
            "py": struct.unpack_from("<i", raw, 0x10)[0],
        })
    return found


def find_bullets(hp: int) -> list[dict]:
    """Return all active projectiles (`cltBullet`) in `0x004F9280` (slots `1..99`)."""
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
            "img_id": struct.unpack_from("<H", raw, 0x08)[0],
            "spr_frame": struct.unpack_from("<H", raw, 0x0C)[0],
            "damage": struct.unpack_from("<H", raw, 0x48)[0],
        })
    return bullets


def find_smokes(hp: int) -> list[dict]:
    """Return all active hit/explosion/shockwave effects (`cltSmoke`) in `0x00C16310` (slots `1..149`)."""
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
            "img_id": struct.unpack_from("<H", raw, 0x08)[0],
            "spr_frame": struct.unpack_from("<H", raw, 0x0C)[0],
        })
    return smokes


def select_single_char(hp: int, char_info: dict) -> None:
    """Select a character/building via engine selection array (`0x00899024` / `0x00899028`)."""
    for c in find_chars(hp):
        write_mem(hp, c["addr"], b"\x00")
    handle = read_u32(hp, char_info["addr"] + 0x29C)
    write_mem(hp, char_info["addr"], b"\x01")
    write_mem(hp, 0x00899028, struct.pack("<I", handle) + b"\x00" * 76)
    write_mem(hp, 0x00899024, struct.pack("<I", 1))
    time.sleep(0.15)


def issue_move_tile(hp: int, c_addr: int, tx: int, ty: int) -> None:
    write_mem(hp, c_addr + 0x380, struct.pack("<H", 0))
    write_mem(hp, c_addr + 0x388, struct.pack("<HH", max(2, min(136, tx)), max(2, min(136, ty))))
    write_mem(hp, c_addr + 0x38C, struct.pack("<I", 0))
    write_mem(hp, c_addr + 0x384, struct.pack("<H", 3))


def spawn_unit_via_hq(hp: int, hq_addr: int, kind_id: int, timeout: float = 12.0) -> dict:
    """Train and immediately complete custom unit `kind_id` (`0x70..0x79`) via `hq_addr`."""
    cmd_id = 0xAB + (kind_id - 0x70)
    write_mem(hp, 0x00956784, struct.pack("<II", 50000, 50000))
    write_mem(hp, hq_addr + 0x290, struct.pack("<H", 1))
    write_mem(hp, hq_addr + 0x380, struct.pack("<H", 0))
    write_mem(hp, hq_addr + 0x388, struct.pack("<II", 0, 0))
    write_mem(hp, hq_addr + 0x384, struct.pack("<I", cmd_id))

    t0 = time.time()
    while time.time() - t0 < timeout:
        hq_ord = read_u16(hp, hq_addr + 0x290)
        if hq_ord == 0x0F:
            write_mem(hp, hq_addr + 0x1F8, struct.pack("<H", 5000))
        for c in find_chars(hp):
            if c["kind"] == kind_id:
                return c
        time.sleep(0.02)
    raise RuntimeError(f"Failed to spawn unit kind 0x{kind_id:02X}")


def launch_and_enter_joseon_skirmish(dawn_exe_path: str = r"C:\src\reverse-imzinrok\YM\dawn\dawn.exe"):
    """Kill stale `dawn.exe`, launch a clean instance, and enter a 100% Joseon Skirmish (`State 3`).

    Returns `(proc, hp, hq_char, peasant_char)`.
    """
    subprocess.run(["taskkill", "/F", "/IM", "dawn.exe"], capture_output=True)
    time.sleep(0.3)

    CREATE_NEW_PROCESS_GROUP = 0x00000200
    proc = subprocess.Popen(
        [dawn_exe_path],
        cwd=r"C:\src\reverse-imzinrok\YM\dawn",
        creationflags=CREATE_NEW_PROCESS_GROUP,
    )
    hp = kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
    assert wait_state(hp, 9), "Failed to reach Main Menu (State 9)"
    write_mem(hp, 0x0041C916, b"\x90" * 11)
    time.sleep(0.3)

    click(hp, 200, 550)
    assert wait_state(hp, 7), "Failed to reach Protocol Select (State 7)"
    time.sleep(0.3)

    click(hp, 595, 558)
    assert wait_state(hp, 5), "Failed to reach Skirmish Lobby (State 5)"
    time.sleep(0.4)

    # Force Slot 0 = Player 0 Joseon (Nation=0), Slot 1 = AI Enemy (Nation=1)
    slots_raw = bytearray(read_mem(hp, 0x00632CC0, 48))
    slots_raw[0] = 1
    slots_raw[2] = 0  # Joseon!
    slots_raw[5] = 0
    slots_raw[6] = 2
    slots_raw[8] = 1
    slots_raw[11] = 1
    write_mem(hp, 0x00632CC0, bytes(slots_raw))
    write_mem(hp, 0x01065D22, struct.pack("<H", 1))
    time.sleep(0.2)

    click(hp, 595, 558)
    assert wait_state(hp, 3, timeout=20.0), "Failed to reach In-Game Skirmish (State 3)"
    time.sleep(1.0)

    write_mem(hp, 0x00956784, struct.pack("<II", 50000, 50000))
    init_chars = find_chars(hp)
    hq_char = next(c for c in init_chars if c["kind"] == 0x31 and c["player"] == 0)
    peasant_char = next(c for c in init_chars if c["kind"] < 0x28 and c["player"] == 0)
    return proc, hp, hq_char, peasant_char
