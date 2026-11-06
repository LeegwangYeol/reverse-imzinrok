python -c "
import struct, subprocess, time, ctypes, sys
from pathlib import Path
sys.path.insert(0, '.')
from tools.live_skirmish_combat_capture import wait_state, click, write_mem, read_u16, find_chars, kernel32, read_mem
from tools.modding.patch_joseon_new_unit import (
    va_to_offset, encode_rel32, UNIT_NAMES,
    VA_ADD_BUTTON, VA_CMD_INIT, VA_BTN_INIT, VA_CALC_KIND_CHECKSUM,
    VA_HOOK_INIT_KIND, VA_HOOK_INIT_KIND_RESUME,
    VA_HOOK_BARRACKS_K, VA_HOOK_BARRACKS_K_RESUME,
    VA_HOOK_HQ_K, VA_HOOK_HQ_K_RESUME,
    VA_HOOK_STABLES_K, VA_HOOK_STABLES_K_RESUME,
    VA_HOOK_DEFAULT_CMDCARD, VA_COMBAT_CMDCARD,
    VA_HOOK_HORNET_DEATH, build_hornet_death_patch,
    VA_F1_DEBUG_TREEVIEW_LIMIT,
    VA_PROTOCOL_SELECT_RETAIL_HONJA, VA_PROTOCOL_SELECT_RETAIL_YEOROT,
    VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL, VA_PROTOCOL_SELECT_FALLBACK_HONJA_SEL,
    VA_PROTOCOL_SELECT_FALLBACK_YEOROT_DIS, VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN,
    VA_HOOK_DOCLONE_KIND, VA_HOOK_DOCLONE_KIND_RESUME,
    VA_HOOK_CANCLONE_LVL, VA_HOOK_CANCLONE_TECH, VA_HOOK_CANAUTOCAST_TECH, VA_HOOK_CLONE_TOOLTIP,
    VA_HOOK_UPDATE_CHAR_MODE, VA_HOOK_UPDATE_CHAR_MODE_RESUME,
    VA_HOOK_FIRETANK_BULLET, VA_HOOK_FIRETANK_BULLET_RESUME,
    VA_HOOK_CALC_ATTACK_STATUS, VA_HOOK_CALC_ATTACK_STATUS_RESUME,
    VA_SET_BULLET, VA_ORDER_STOP,
    IMG_ID_YUSAENG, IMG_ID_GEOMSUL_NANGIN, IMG_ID_JOCHONG_NANGIN, IMG_ID_GUMIHO,
    IMG_ID_DAEWAN_WANGBEOL, IMG_ID_JOSEON_HORANGI, IMG_ID_TEOLGAMYEON, IMG_ID_SEOLNYEO,
    IMG_ID_JOSEON_DOKKAEBI, IMG_ID_BULGASARI
)

orig = bytearray(Path('YM_backup_original/dawn.exe').read_bytes())
raw = bytearray(orig)

# 1. RData tables
VA_RDATA_DESCRIPTORS = 0x004EBEEB
VA_RDATA_BBOX = VA_RDATA_DESCRIPTORS + 200

unit_descriptors = [
    (450, IMG_ID_YUSAENG, 250 // 2, 0, 5, 18, 60, 100, ord('Y'), 0x21, 72, 12, 132, 8, 60, 12, 0, 8),
    (600, IMG_ID_GEOMSUL_NANGIN, 180 // 2, 0, 1, 21, 80, 80, ord('K'), 0x22, 40, 8, 80, 8, 120, 9, 0, 8),
    (480, IMG_ID_JOCHONG_NANGIN, 240 // 2, 0, 6, 18, 70, 0, ord('N'), 0x23, 40, 8, 80, 8, 120, 9, 0, 8),
    (750, IMG_ID_GUMIHO, 280 // 2, 50, 5, 22, 85, 100, ord('F'), 0x24, 40, 8, 80, 8, 120, 17, 0, 8),
    (500, IMG_ID_DAEWAN_WANGBEOL, 200 // 2, 50, 1, 25, 90, 0, ord('B'), 0x25, 0, 8, 0, 8, 144, 11, 72, 8),
    (950, IMG_ID_JOSEON_HORANGI, 300 // 2, 0, 1, 24, 120, 0, ord('T'), 0x26, 40, 8, 80, 8, 120, 10, 0, 8),
    (700, IMG_ID_TEOLGAMYEON, 220 // 2, 20, 5, 19, 80, 80, ord('M'), 0x27, 0, 8, 80, 8, 120, 10, 40, 8),
    (850, IMG_ID_SEOLNYEO, 320 // 2, 50, 6, 17, 95, 120, ord('S'), 0x28, 84, 10, 134, 10, 65, 19, 0, 13),
    (1100, IMG_ID_JOSEON_DOKKAEBI, 350 // 2, 0, 1, 18, 110, 0, ord('D'), 0x29, 60, 8, 100, 8, 140, 11, 0, 12),
    (1800, IMG_ID_BULGASARI, 450 // 2, 100, 6, 16, 130, 120, ord('I'), 0x2A, 80, 8, 120, 8, 160, 20, 80, 8),
]
desc_raw = bytearray()
for rec in unit_descriptors: desc_raw += struct.pack('<HHBBBBBBBBBBBBBBBB', *rec)
bbox_raw = bytearray()
for w_pct, h_pct in [(40, 50), (45, 55), (45, 55), (55, 65), (35, 45), (60, 60), (45, 55), (50, 60), (55, 65), (75, 75)]:
    bbox_raw += struct.pack('<BB', w_pct, h_pct)

raw[va_to_offset(VA_RDATA_DESCRIPTORS) : va_to_offset(VA_RDATA_DESCRIPTORS) + 200] = desc_raw
raw[va_to_offset(VA_RDATA_BBOX) : va_to_offset(VA_RDATA_BBOX) + 20] = bbox_raw

# 2. Unit Names (160 bytes at 0x004E4C70)
VA_NAMES = 0x004E4C70
voice_tpl = [0, 0, 0, 0x18, 0, 0x16, 0x15, 0x25, 0x19, 0x17]
hit_sfx   = [0x2C, 0x2E, 0x2C, 0x2E, 0x2C, 0x2E, 0x2E, 0x2C, 0x2E, 0x2E]
die_sfx   = [0x19, 0x18, 0x18, 0x30, 0x1A, 0x2F, 0x2F, 0x2F, 0x2F, 0x2F]
bot_y     = [0, 0, 0, 0, 0, 5, 0, 0, 0, 0]

for i, name in enumerate(UNIT_NAMES):
    nb = name.encode('cp949') + b'\x00'
    slot = bytearray(16)
    slot[:len(nb)] = nb
    slot[0x0B] = bot_y[i]
    slot[0x0C] = voice_tpl[i]
    slot[0x0D] = hit_sfx[i]
    slot[0x0E] = die_sfx[i]
    va_name = VA_NAMES + i * 16
    raw[va_to_offset(va_name) : va_to_offset(va_name) + 16] = slot

# Next: dynamically allocate and chain all caves!
curr_va = VA_NAMES + 160

# Cave 1: Init Routine
VA_INIT = curr_va
buf1 = bytearray()
def c1_va(): return VA_INIT + len(buf1)
buf1 += b'\x60\xBB\x28\x52\x9B\x00\xBE\x70\x4C\x4E\x00\xBD' + struct.pack('<I', VA_RDATA_DESCRIPTORS) + b'\x31\xFF'
loop1_top = c1_va()
buf1 += b'\x57\x56\x89\xDF\xBE\xC0\xDB\x9C\x00\x31\xC9\xB1\xE5\xF3\xA5\x5E\x5A\x57'
buf1 += b'\x8B\x45\x00\x89\x43\x06\x8B\x45\x06\x88\x43\x36\x88\x63\x2C\x3C\x01\x7E\x07\x80\x4B\x4D\x04\xFE\x43\x38'
buf1 += b'\xC1\xE8\x10\x88\x43\x04\x88\x63\x2E\x8B\x45\x04\x88\x63\x14\xB4\x00\xD1\xE0\x66\x89\x43\x12'
buf1 += b'\x8A\x46\xFB\x88\x43\x0E\x8B\x04\x55' + struct.pack('<I', VA_RDATA_BBOX) + b'\x88\x43\x1E\x88\x63\x20'
buf1 += b'\x8B\x7E\x0C\x89\xF8\x88\x63\x5C\x0F\xB6\xC0\x69\xC0\x94\x03\x00\x00\x05\x94\x52\x9B\x00\x66\x8B\x38\x89\x7B\x6C\x8B\x40\x04\x89\x43\x70'
buf1 += b'\x51\x8D\x42\x70\x50\x6A\x02\x6A\x02\x51\x6A\x08'
buf1 += b'\x8D\xBB\x0C\x02\x00\x00\x89\x77\x98\x80\xFA\x04\x75\x04\x80\x4B\x4C\x10'
anim1_loop = c1_va()
buf1 += b'\x0F\xB7\x45\x02\x89\x47\x08\x8B\x44\x4D\x0C\x88\x47\x0C\x88\x67\x04\x83\xC7\x1C\x41\x83\xF9\x04'
buf1 += b'\x7C' + struct.pack('b', anim1_loop - (c1_va() + 2))
buf1 += b'\xD0\xEC\xFE\xC4\x88\x67\xF4\x8B\x47\xCC\x48\x89\x47\xD8\x89\xD7'
buf1 += b'\x8D\x87\xA5\x00\x00\x00\x66\x89\x03\x81\xA3\xE0\x01\x00\x00\xFF\xDF\xFF\xFF\x83\xFF\x03\x75\x0A\x81\x8B\xE0\x01\x00\x00\x00\x08\x00\x00'
buf1 += b'\x83\xFF\x09\x75\x04\xC6\x43\x3A\x06'
buf1 += b'\x89\xD9' + encode_rel32(0xE8, c1_va() + 2, VA_CALC_KIND_CHECKSUM) + b'\x89\x43\x08'
buf1 += b'\x6B\xCF\x18\x81\xC1\x38\x3F\x9E\x00' + encode_rel32(0xE8, c1_va() + 9, VA_CMD_INIT)
buf1 += b'\x52\x56\x8A\x55\x0A\x8D\x4A\x20\x51\x52\x6A\x00\xB6\x01\x8A\x55\x0B\x52\x04\x3B\x50\x8D\x8E\x18\x32\x15\x00' + encode_rel32(0xE8, c1_va() + 27, VA_BTN_INIT)
buf1 += b'\x5B\x83\xC6\x10\x83\xC5\x14\x47\x83\xFF\x0A'
buf1 += b'\x0F\x8C' + struct.pack('<i', loop1_top - (c1_va() + 6))
buf1 += b'\x61\x33\xC9\xB8\x30\x52\x9B\x00' + encode_rel32(0xE9, c1_va() + 8, VA_HOOK_INIT_KIND_RESUME)
raw[va_to_offset(VA_INIT) : va_to_offset(VA_INIT) + len(buf1)] = buf1
curr_va += len(buf1)

# Button Helper
VA_HELPER_BUTTONS = curr_va
buf_hb = bytearray()
def hb_va(): return VA_HELPER_BUTTONS + len(buf_hb)
buf_hb += b'\x53'
loop_hb = hb_va()
buf_hb += b'\x31\xC0\x50\x50\x50\x50\x50\x50\x8A\x42\x01\x50\x8A\x02\x50\x51\x52\x8B\xCE'
buf_hb += encode_rel32(0xE8, hb_va(), VA_ADD_BUTTON)
buf_hb += b'\x5A\x59\x83\xC2\x02\x49'
buf_hb += b'\x75' + struct.pack('b', loop_hb - (hb_va() + 2))
buf_hb += b'\x5B\xC3'
raw[va_to_offset(VA_HELPER_BUTTONS) : va_to_offset(VA_HELPER_BUTTONS) + len(buf_hb)] = buf_hb
curr_va += len(buf_hb)

# Button tables
VA_TBL_BARRACKS = curr_va
tbl_b = bytes([8, 0x45, 9, 0x46, 10, 0x4A])
raw[va_to_offset(VA_TBL_BARRACKS) : va_to_offset(VA_TBL_BARRACKS) + len(tbl_b)] = tbl_b
curr_va += len(tbl_b)

VA_TBL_HQ = curr_va
tbl_hq = bytes([9, 0x44, 10, 0x4D, 11, 0x47])
raw[va_to_offset(VA_TBL_HQ) : va_to_offset(VA_TBL_HQ) + len(tbl_hq)] = tbl_hq
curr_va += len(tbl_hq)

VA_TBL_STABLES = curr_va
tbl_s = bytes([7, 0x48, 8, 0x49, 9, 0x4B, 10, 0x4C])
raw[va_to_offset(VA_TBL_STABLES) : va_to_offset(VA_TBL_STABLES) + len(tbl_s)] = tbl_s
curr_va += len(tbl_s)

# Cave 2: Barracks Hook
VA_CAVE_BARRACKS = curr_va
buf_b = bytearray()
def b_va(): return VA_CAVE_BARRACKS + len(buf_b)
buf_b += encode_rel32(0xE8, b_va(), VA_ADD_BUTTON)
buf_b += b'\xBA' + struct.pack('<I', VA_TBL_BARRACKS) + b'\xB9\x03\x00\x00\x00'
buf_b += encode_rel32(0xE8, b_va(), VA_HELPER_BUTTONS)
buf_b += encode_rel32(0xE9, b_va(), VA_HOOK_BARRACKS_K_RESUME)
raw[va_to_offset(VA_CAVE_BARRACKS) : va_to_offset(VA_CAVE_BARRACKS) + len(buf_b)] = buf_b
curr_va += len(buf_b)

# Cave 3: HQ Hook
VA_CAVE_HQ = curr_va
buf_hq = bytearray()
def hq_va(): return VA_CAVE_HQ + len(buf_hq)
buf_hq += encode_rel32(0xE8, hq_va(), VA_ADD_BUTTON)
buf_hq += b'\xBA' + struct.pack('<I', VA_TBL_HQ) + b'\xB9\x03\x00\x00\x00'
buf_hq += encode_rel32(0xE8, hq_va(), VA_HELPER_BUTTONS)
buf_hq += encode_rel32(0xE9, hq_va(), VA_HOOK_HQ_K_RESUME)
raw[va_to_offset(VA_CAVE_HQ) : va_to_offset(VA_CAVE_HQ) + len(buf_hq)] = buf_hq
curr_va += len(buf_hq)

# Cave 4: Stables Hook
VA_CAVE_STABLES = curr_va
buf_s = bytearray()
def s_va(): return VA_CAVE_STABLES + len(buf_s)
buf_s += encode_rel32(0xE8, s_va(), VA_ADD_BUTTON)
buf_s += b'\xBA' + struct.pack('<I', VA_TBL_STABLES) + b'\xB9\x04\x00\x00\x00'
buf_s += encode_rel32(0xE8, s_va(), VA_HELPER_BUTTONS)
buf_s += encode_rel32(0xE9, s_va(), VA_HOOK_STABLES_K_RESUME)
raw[va_to_offset(VA_CAVE_STABLES) : va_to_offset(VA_CAVE_STABLES) + len(buf_s)] = buf_s
curr_va += len(buf_s)

# Cave 5: CmdCard Dispatcher
VA_CAVE_CMDCARD = curr_va
# Gumiho cave will be at VA_CAVE_CMDCARD + 18
VA_CAVE_GUMIHO_CMD = VA_CAVE_CMDCARD + 18
buf_cmd = bytearray()
def cmd_va(): return VA_CAVE_CMDCARD + len(buf_cmd)
buf_cmd += b'\x80\xB9\x8D\x00\x00\x00\x73'
buf_cmd += b'\x0F\x84' + struct.pack('<i', VA_CAVE_GUMIHO_CMD - (cmd_va() + 6))
buf_cmd += encode_rel32(0xE9, cmd_va(), VA_COMBAT_CMDCARD)
assert len(buf_cmd) == 18
raw[va_to_offset(VA_CAVE_CMDCARD) : va_to_offset(VA_CAVE_CMDCARD) + len(buf_cmd)] = buf_cmd
curr_va += len(buf_cmd)

# Cave 6: Gumiho CmdCard
buf_g = bytearray()
def g_va(): return VA_CAVE_GUMIHO_CMD + len(buf_g)
buf_g += b'\x56\x8B\x74\x24\x08\x56\x8B\xCE'
buf_g += encode_rel32(0xE8, g_va(), VA_COMBAT_CMDCARD)
buf_g += b'\x83\xBE\x94\x00\x00\x00\x00\x75\x13\x31\xC9\x51\x51\x51\x51\x51\x51\x6A\x39\x6A\x05\x89\xF1'
buf_g += encode_rel32(0xE8, g_va(), VA_ADD_BUTTON)
buf_g += b'\xB8\x01\x00\x00\x00\x5E\xC2\x04\x00'
raw[va_to_offset(VA_CAVE_GUMIHO_CMD) : va_to_offset(VA_CAVE_GUMIHO_CMD) + len(buf_g)] = buf_g
curr_va += len(buf_g)

# Cave 7: DoClone Kind
VA_CAVE_DOCLONE = curr_va
buf_dc = bytearray()
def dc_va(): return VA_CAVE_DOCLONE + len(buf_dc)
buf_dc += b'\x3C\x50\x75\x02\xB0\x61\x3C\x73\x75\x02\xB0\x73\x89\x44\x24\x1C'
buf_dc += encode_rel32(0xE9, dc_va(), VA_HOOK_DOCLONE_KIND_RESUME)
raw[va_to_offset(VA_CAVE_DOCLONE) : va_to_offset(VA_CAVE_DOCLONE) + len(buf_dc)] = buf_dc
curr_va += len(buf_dc)

# Cave 8: Bulgasari Mode
VA_CAVE_BG_MODE = curr_va
buf_bgm = bytearray()
def bgm_va(): return VA_CAVE_BG_MODE + len(buf_bgm)
buf_bgm += b'\x80\xBE\x8D\x00\x00\x00\x79\x75\x41'
buf_bgm += b'\x83\xBE\xE4\x01\x00\x00\x01\x75\x1A\x83\xBE\xB8\x00\x00\x00\x14\x7D\x2F'
buf_bgm += b'\xC7\x86\xE4\x01\x00\x00\x00\x00\x00\x00\xC6\x46\x36\x01\x80\x66\x4D\xFB\xC6\x86\x70\x02\x00\x00\x09\xEB\x17'
buf_bgm += b'\x83\xBE\xB8\x00\x00\x00\x14\x7C\x0F'
buf_bgm += b'\xC7\x86\xE4\x01\x00\x00\x01\x00\x00\x00\xC6\x46\x36\x06\x80\x4E\x4D\x04\xC6\x86\x70\x02\x00\x00\x05'
buf_bgm += b'\x8B\x86\x80\x00\x00\x00'
buf_bgm += encode_rel32(0xE9, bgm_va(), VA_HOOK_UPDATE_CHAR_MODE_RESUME)
raw[va_to_offset(VA_CAVE_BG_MODE) : va_to_offset(VA_CAVE_BG_MODE) + len(buf_bgm)] = buf_bgm
curr_va += len(buf_bgm)

# Cave 9: Bulgasari MP
VA_CAVE_BG_MP = curr_va
buf_bmp = bytearray()
def bmp_va(): return VA_CAVE_BG_MP + len(buf_bmp)
buf_bmp += b'\x80\xBE\x8D\x00\x00\x00\x79\x75\x0A\x83\xAE\xB8\x00\x00\x00\x14\x79\x02\x31\xC0'
buf_bmp += encode_rel32(0xE8, bmp_va(), VA_SET_BULLET)
buf_bmp += encode_rel32(0xE9, bmp_va(), VA_HOOK_FIRETANK_BULLET_RESUME)
raw[va_to_offset(VA_CAVE_BG_MP) : va_to_offset(VA_CAVE_BG_MP) + len(buf_bmp)] = buf_bmp
curr_va += len(buf_bmp)

# Cave 10: CalcAttack Status
VA_CAVE_CALC_ATTACK = curr_va
buf_ca = bytearray()
def ca_va(): return VA_CAVE_CALC_ATTACK + len(buf_ca)
buf_ca += b'\x50\x51\x52\x53'
buf_ca += b'\x85\xFF\x7E\x3C\x69\xC7\x58\x07\x00\x00\x8A\x90\x1D\xB8\x66\x00'
buf_ca += b'\x0F\xBF\xCE\x85\xC9\x7E\x2B\x69\xC9\x58\x07\x00\x00'
buf_ca += b'\x83\xB9\x44\xB8\x66\x00\x00\x7E\x1C\xF6\x81\x68\xB9\x66\x00\x02\x75\x13'
buf_ca += b'\x80\xFA\x70\x75\x0B\xC7\x81\x00\xBB\x66\x00\x96\x00\x00\x00\xEB\x18'
buf_ca += b'\x80\xFA\x76\x74\x05\x80\xFA\x77\x75\x1A'
buf_ca += b'\xC7\x81\x00\xBB\x66\x00\x5A\x00\x00\x00\x66\xC7\x81\xD0\xBA\x66\x00\x01\x3C'
buf_ca += b'\x6A\x00\x56'
buf_ca += encode_rel32(0xE8, ca_va(), VA_ORDER_STOP)
buf_ca += b'\x83\xC4\x08'
buf_ca += b'\x5B\x5A\x59\x58'
buf_ca += b'\x69\xF7\x58\x07\x00\x00'
buf_ca += encode_rel32(0xE9, ca_va(), VA_HOOK_CALC_ATTACK_STATUS_RESUME)
raw[va_to_offset(VA_CAVE_CALC_ATTACK) : va_to_offset(VA_CAVE_CALC_ATTACK) + len(buf_ca)] = buf_ca
curr_va += len(buf_ca)

print(f'Final cave end VA: 0x{curr_va:08X} (Total .text padding left: {0x004E5000 - curr_va} bytes)')
assert curr_va <= 0x004E5000

# Hook sites:
hook1 = encode_rel32(0xE9, VA_HOOK_INIT_KIND, VA_INIT) + b'\x90\x90'
raw[va_to_offset(VA_HOOK_INIT_KIND) : va_to_offset(VA_HOOK_INIT_KIND) + 7] = hook1
raw[va_to_offset(VA_HOOK_BARRACKS_K) : va_to_offset(VA_HOOK_BARRACKS_K) + 5] = encode_rel32(0xE9, VA_HOOK_BARRACKS_K, VA_CAVE_BARRACKS)
raw[va_to_offset(VA_HOOK_HQ_K) : va_to_offset(VA_HOOK_HQ_K) + 5] = encode_rel32(0xE9, VA_HOOK_HQ_K, VA_CAVE_HQ)
raw[va_to_offset(VA_HOOK_STABLES_K) : va_to_offset(VA_HOOK_STABLES_K) + 5] = encode_rel32(0xE9, VA_HOOK_STABLES_K, VA_CAVE_STABLES)
raw[va_to_offset(VA_HOOK_DEFAULT_CMDCARD) : va_to_offset(VA_HOOK_DEFAULT_CMDCARD) + 5] = encode_rel32(0xE8, VA_HOOK_DEFAULT_CMDCARD, VA_CAVE_CMDCARD)

# Hornet death:
raw[va_to_offset(VA_HOOK_HORNET_DEATH) : va_to_offset(VA_HOOK_HORNET_DEATH) + 49] = build_hornet_death_patch(VA_HOOK_HORNET_DEATH)
raw[va_to_offset(VA_F1_DEBUG_TREEVIEW_LIMIT)] = 0x7A

# Protocol tabs:
raw[va_to_offset(VA_PROTOCOL_SELECT_RETAIL_HONJA)] = 0
raw[va_to_offset(VA_PROTOCOL_SELECT_RETAIL_YEOROT)] = 1
raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL)] = 0
raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_SEL)] = 1
raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_DIS)] = 0
raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN)] = 1

# Clone skill hooks:
raw[va_to_offset(VA_HOOK_DOCLONE_KIND) : va_to_offset(VA_HOOK_DOCLONE_KIND) + 8] = encode_rel32(0xE9, VA_HOOK_DOCLONE_KIND, VA_CAVE_DOCLONE) + b'\x90\x90\x90'
raw[va_to_offset(VA_HOOK_CANCLONE_LVL) : va_to_offset(VA_HOOK_CANCLONE_LVL) + 2] = b'\x90\x90'
raw[va_to_offset(VA_HOOK_CANCLONE_TECH) : va_to_offset(VA_HOOK_CANCLONE_TECH) + 2] = b'\x90\x90'
raw[va_to_offset(VA_HOOK_CANAUTOCAST_TECH) : va_to_offset(VA_HOOK_CANAUTOCAST_TECH) + 6] = b'\x90' * 6
raw[va_to_offset(VA_HOOK_CLONE_TOOLTIP) : va_to_offset(VA_HOOK_CLONE_TOOLTIP) + 6] = encode_rel32(0xE9, VA_HOOK_CLONE_TOOLTIP, 0x0049AA4B) + b'\x90'

# Bulgasari dual mode:
raw[va_to_offset(VA_HOOK_UPDATE_CHAR_MODE) : va_to_offset(VA_HOOK_UPDATE_CHAR_MODE) + 8] = encode_rel32(0xE9, VA_HOOK_UPDATE_CHAR_MODE, VA_CAVE_BG_MODE) + b'\x90\x90\x90'
raw[va_to_offset(VA_HOOK_FIRETANK_BULLET) : va_to_offset(VA_HOOK_FIRETANK_BULLET) + 7] = encode_rel32(0xE9, VA_HOOK_FIRETANK_BULLET, VA_CAVE_BG_MP) + b'\x90\x90'

# CalcAttack status:
raw[va_to_offset(VA_HOOK_CALC_ATTACK_STATUS) : va_to_offset(VA_HOOK_CALC_ATTACK_STATUS) + 6] = encode_rel32(0xE9, VA_HOOK_CALC_ATTACK_STATUS, VA_CAVE_CALC_ATTACK) + b'\x90'

Path('YM/dawn/dawn_test.exe').write_bytes(raw)
print('Wrote dawn_test.exe successfully! Now testing live in-game battle...')

subprocess.run(['taskkill', '/F', '/IM', 'dawn_test.exe'], capture_output=True)
p = subprocess.Popen(['YM/dawn/dawn_test.exe'], cwd='YM/dawn')
hp = kernel32.OpenProcess(0x1F0FFF, False, p.pid)

assert wait_state(hp, 9, 15), 'State 9 timeout'
write_mem(hp, 0x0041C916, b'\x90' * 11)
time.sleep(0.1)
click(hp, 200, 550)

assert wait_state(hp, 7, 10), 'State 7 timeout'
time.sleep(0.1)
click(hp, 595, 558)

assert wait_state(hp, 5, 10), 'State 5 timeout'
time.sleep(0.2)

slots_raw = bytearray(read_mem(hp, 0x00632CC0, 48))
slots_raw[0] = 1; slots_raw[2] = 0; slots_raw[5] = 0; slots_raw[6] = 2; slots_raw[8] = 1; slots_raw[11] = 1
write_mem(hp, 0x00632CC0, bytes(slots_raw))
write_mem(hp, 0x01065D22, struct.pack('<H', 1))
time.sleep(0.1)
click(hp, 595, 558)

print('Waiting for State 3 in dawn_test.exe...')
for t in range(40):
    time.sleep(0.2)
    poll = p.poll()
    if poll is not None:
        print('CRASHED! Code:', poll)
        sys.exit(1)
    if read_u16(hp, 0x004ED818) == 3:
        print('Reached State 3 successfully at %.1fs!' % (t * 0.2))
        break

print('Testing stability in State 3 for 10 seconds...')
for s in range(20):
    time.sleep(0.5)
    poll = p.poll()
    if poll is not None:
        print('CRASHED in State 3 after %.1fs! Code: %d' % (s * 0.5, poll))
        sys.exit(1)

print('*** SUCCESS! 100% ROCK SOLID STABLE IN STATE 3! NO CRASH AT ALL! ***')
p.terminate()
"