r"""
Native Joseon New Units Binary Patcher for Imjinrok 2+ Chosun's Counterattack (dawn.exe).

Adds 10 brand-new playable units to the Joseon (조선) faction in the original game:
  1. 유생 (Joseon Confucian Scholar):
     - Unit KindID : 0x70 (112, KindInfo[0x70] at VA 0x009CE2E8)
     - Command ID  : 0xAB (171, CmdTable[0xAB] at VA 0x009E3F38)
     - Button ID   : 0x44 (68, ButtonTable[0x44] at VA 0x00637E88, Icon=0x64, Hotkey='Y')
     - Sprite      : ImgFile.dat ID 267 (char\keon_1hs.Spr <- Gersang justicek.AGF, 176 frames)
     - Buildings   : 조선 본영 Slot 9 (Slot 7 empty)

  2. 검술 낭인 (Ronin Swordsman):
     - Unit KindID : 0x71 (113, KindInfo[0x71] at VA 0x009CE67C)
     - Command ID  : 0xAC (172, CmdTable[0xAC] at VA 0x009E3F50)
     - Button ID   : 0x45 (69, ButtonTable[0x45] at VA 0x00637E98, Icon=0x62, Hotkey='K')
     - Sprite      : ImgFile.dat ID 328 (char\SwordPirate_online.spr, 136 frames)
     - Buildings   : 조선 병영 Slot 8 (Slot 11 empty)

  3. 조총 낭인 (Ronin Musketeer):
     - Unit KindID : 0x72 (114, KindInfo[0x72] at VA 0x009CEA10)
     - Command ID  : 0xAD (173, CmdTable[0xAD] at VA 0x009E3F68)
     - Button ID   : 0x46 (70, ButtonTable[0x46] at VA 0x00637EA8, Icon=0x61, Hotkey='P')
     - Sprite      : ImgFile.dat ID 329 (char\GunPirate_online.spr, 136 frames)
     - Buildings   : 조선 병영 Slot 9 (replaces commented-out 조선 조총병; Slot 11 empty)

  4. 구미호 (Nine-Tailed Fox):
     - Unit KindID : 0x73 (115, KindInfo[0x73] at VA 0x009CEDA4)
     - Command ID  : 0xAE (174, CmdTable[0xAE] at VA 0x009E3F80)
     - Button ID   : 0x47 (71, ButtonTable[0x47] at VA 0x00637EB8, Icon=0x65, Hotkey='G')
     - Sprite      : ImgFile.dat ID 295 (char\fox.spr, 144 frames)
     - Buildings   : 조선 본영 Slot 11 (Slot 7 empty)

  5. 대만 왕벌 (Taiwanese Giant Bee):
     - Unit KindID : 0x74 (116, KindInfo[0x74] at VA 0x009CF138)
     - Command ID  : 0xAF (175, CmdTable[0xAF] at VA 0x009E3F98)
     - Button ID   : 0x48 (72, ButtonTable[0x48] at VA 0x00637EC8, Icon=0x66, Hotkey='B')
     - Sprite      : ImgFile.dat ID 314 (char\bat_online.spr <- Gersang hornet.AGF, 160 frames)
     - Buildings   : 조선 마구간 Slot 7 (Slot 11 empty)

  6. 조선 호랑이 (Joseon Tiger):
     - Unit KindID : 0x75 (117, KindInfo[0x75] at VA 0x009CF4CC)
     - Command ID  : 0xB0 (176, CmdTable[0xB0] at VA 0x009E3FB0)
     - Button ID   : 0x49 (73, ButtonTable[0x49] at VA 0x00637ED8, Icon=0x67, Hotkey='T')
     - Sprite      : ImgFile.dat ID 272 (char\Tiger.Spr, 136 frames)
     - Buildings   : 조선 마구간 Slot 8 (Slot 11 empty)

  7. 털가면 (FurHead Demon):
     - Unit KindID : 0x76 (118, KindInfo[0x76] at VA 0x009CF860)
     - Command ID  : 0xB1 (177, CmdTable[0xB1] at VA 0x009E3FC8)
     - Button ID   : 0x4A (74, ButtonTable[0x4A] at VA 0x00637EE8, Icon=0x68, Hotkey='M')
     - Sprite      : ImgFile.dat ID 311 (char\furheaddemon_online.spr, 130 frames)
     - Buildings   : 조선 병영 Slot 10 (Slot 11 empty)

  8. 설녀 (Snow Woman):
     - Unit KindID : 0x77 (119, KindInfo[0x77] at VA 0x009CFBF4)
     - Command ID  : 0xB2 (178, CmdTable[0xB2] at VA 0x009E3FE0)
     - Button ID   : 0x4B (75, ButtonTable[0x4B] at VA 0x00637EF8, Icon=0x69, Hotkey='I')
     - Sprite      : ImgFile.dat ID 334 (char\snowwoman_online.spr, 192 frames)
     - Buildings   : 조선 마구간 Slot 9 (Slot 11 empty)

  9. 조선 도깨비 (Joseon Dokkaebi):
     - Unit KindID : 0x78 (120, KindInfo[0x78] at VA 0x009CFF88)
     - Command ID  : 0xB3 (179, CmdTable[0xB3] at VA 0x009E3FF8)
     - Button ID   : 0x4C (76, ButtonTable[0x4C] at VA 0x00637F08, Icon=0x64, Hotkey='O')
     - Sprite      : ImgFile.dat ID 300 (char\oni_online.spr, 180 frames)
     - Buildings   : 조선 마구간 Slot 10 (Slot 11 empty)

  10. 불가살이 (Bulgasari):
     - Unit KindID : 0x79 (121, KindInfo[0x79] at VA 0x009D031C)
     - Command ID  : 0xB4 (180, CmdTable[0xB4] at VA 0x009E4010)
     - Button ID   : 0x4D (77, ButtonTable[0x4D] at VA 0x00637F18, Icon=0x6A, Hotkey='U')
     - Sprite      : ImgFile.dat ID 296 (char\starfish.spr, 216 frames)
     - Buildings   : 조선 본영 Slot 10 (Slot 7 empty)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import struct
import sys
import time
from pathlib import Path

import capstone

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

IMAGE_BASE = 0x00400000
ORIGINAL_SHA256 = "302735c2feaf0467a511a9b3bdb0b87d09e7ab7be903299ca4245a51a54aa67a"
ORIGINAL_SIZE = 1032192

# Engine Table Virtual Addresses
VA_KIND_TEMPLATE_6E = 0x009CDBC0  # KindInfo[0x6E] (FILE_CHAR_JUSTICEK)
VA_KIND_TEMPLATE_0C = 0x009B7D18  # KindInfo[0x0C] (FILE_CHAR_GUNJ1)

# 10 Joseon Unit KindInfo VAs (KindIDs 0x70..0x79, stride = 0x394)
VA_KIND_NEW_70 = 0x009CE2E8       # KindInfo[0x70] (유생)
VA_KIND_NEW_71 = 0x009CE67C       # KindInfo[0x71] (검술 낭인)
VA_KIND_NEW_72 = 0x009CEA10       # KindInfo[0x72] (조총 낭인)
VA_KIND_NEW_73 = 0x009CEDA4       # KindInfo[0x73] (구미호)
VA_KIND_NEW_74 = 0x009CF138       # KindInfo[0x74] (대만 왕벌)
VA_KIND_NEW_75 = 0x009CF4CC       # KindInfo[0x75] (조선 호랑이)
VA_KIND_NEW_76 = 0x009CF860       # KindInfo[0x76] (털가면)
VA_KIND_NEW_77 = 0x009CFBF4       # KindInfo[0x77] (설녀)
VA_KIND_NEW_78 = 0x009CFF88       # KindInfo[0x78] (조선 도깨비)
VA_KIND_NEW_79 = 0x009D031C       # KindInfo[0x79] (불가살이)

# 5 Joseon Infantry KindInfo VAs (KindIDs 0x7A..0x7E, stride = 0x394)
VA_KIND_NEW_7A = 0x009D06B0       # KindInfo[0x7A] (등패수)
VA_KIND_NEW_7B = 0x009D0A44       # KindInfo[0x7B] (쌍수도병)
VA_KIND_NEW_7C = 0x009D0DD8       # KindInfo[0x7C] (장창수)
VA_KIND_NEW_7D = 0x009D116C       # KindInfo[0x7D] (월도병)
VA_KIND_NEW_7E = 0x009D1500       # KindInfo[0x7E] (낭선병)

# 10 Joseon Unit CmdTable VAs (CmdIDs 0xAB..0xB4, stride = 0x18)
VA_CMD_NEW_AB = 0x009E3F38        # CmdTable[0xAB] (유생)
VA_CMD_NEW_AC = 0x009E3F50        # CmdTable[0xAC] (검술 낭인)
VA_CMD_NEW_AD = 0x009E3F68        # CmdTable[0xAD] (조총 낭인)
VA_CMD_NEW_AE = 0x009E3F80        # CmdTable[0xAE] (구미호)
VA_CMD_NEW_AF = 0x009E3F98        # CmdTable[0xAF] (대만 왕벌)
VA_CMD_NEW_B0 = 0x009E3FB0        # CmdTable[0xB0] (조선 호랑이)
VA_CMD_NEW_B1 = 0x009E3FC8        # CmdTable[0xB1] (털가면)
VA_CMD_NEW_B2 = 0x009E3FE0        # CmdTable[0xB2] (설녀)
VA_CMD_NEW_B3 = 0x009E3FF8        # CmdTable[0xB3] (조선 도깨비)
VA_CMD_NEW_B4 = 0x009E4010        # CmdTable[0xB4] (불가살이)

# 5 Joseon Infantry CmdTable VAs (CmdIDs 0xBF..0xC3, stride = 0x18; avoids 0xB5..0xB9 Joseon Farmer Build collisions)
VA_CMD_NEW_BF = 0x009E4118        # CmdTable[0xBF] (등패수)
VA_CMD_NEW_C0 = 0x009E4130        # CmdTable[0xC0] (쌍수도병)
VA_CMD_NEW_C1 = 0x009E4148        # CmdTable[0xC1] (장창수)
VA_CMD_NEW_C2 = 0x009E4160        # CmdTable[0xC2] (월도병)
VA_CMD_NEW_C3 = 0x009E4178        # CmdTable[0xC3] (낭선병)
VA_CMD_NEW_B5 = VA_CMD_NEW_BF
VA_CMD_NEW_B6 = VA_CMD_NEW_C0
VA_CMD_NEW_B7 = VA_CMD_NEW_C1
VA_CMD_NEW_B8 = VA_CMD_NEW_C2
VA_CMD_NEW_B9 = VA_CMD_NEW_C3

# Backward-compat aliases for CmdIDs
VA_CMD_NEW_54 = VA_CMD_NEW_B3
VA_CMD_NEW_58 = VA_CMD_NEW_AB
VA_CMD_NEW_59 = VA_CMD_NEW_AC

# 10 Joseon Unit ButtonTable VAs (ButtonIDs 0x44..0x4D, stride = 0x10)
VA_BTN_NEW_44 = 0x00637E88        # ButtonTable[0x44] (유생 [Y])
VA_BTN_NEW_45 = 0x00637E98        # ButtonTable[0x45] (검술 낭인 [K])
VA_BTN_NEW_46 = 0x00637EA8        # ButtonTable[0x46] (조총 낭인 [P])
VA_BTN_NEW_47 = 0x00637EB8        # ButtonTable[0x47] (구미호 [G])
VA_BTN_NEW_48 = 0x00637EC8        # ButtonTable[0x48] (대만 왕벌 [B])
VA_BTN_NEW_49 = 0x00637ED8        # ButtonTable[0x49] (조선 호랑이 [T])
VA_BTN_NEW_4A = 0x00637EE8        # ButtonTable[0x4A] (털가면 [M])
VA_BTN_NEW_4B = 0x00637EF8        # ButtonTable[0x4B] (설녀 [I])
VA_BTN_NEW_4C = 0x00637F08        # ButtonTable[0x4C] (조선 도깨비 [O])
VA_BTN_NEW_4D = 0x00637F18        # ButtonTable[0x4D] (불가살이 [U])

# 5 Joseon Infantry ButtonTable VAs (ButtonIDs 0x4E, 0x4F, 0x2E, 0x2F, 0x30; avoids 0x50, 0x52, 0x54 collisions)
VA_BTN_NEW_4E = 0x00637F28        # ButtonTable[0x4E] (등패수 [E])
VA_BTN_NEW_4F = 0x00637F38        # ButtonTable[0x4F] (쌍수도병 [V])
VA_BTN_NEW_2E = 0x00637D28        # ButtonTable[0x2E] (장창수 [J])
VA_BTN_NEW_2F = 0x00637D38        # ButtonTable[0x2F] (월도병 [W])
VA_BTN_NEW_30 = 0x00637D48        # ButtonTable[0x30] (낭선병 [N])
VA_BTN_NEW_50 = VA_BTN_NEW_2E
VA_BTN_NEW_52 = VA_BTN_NEW_2F
VA_BTN_NEW_54 = VA_BTN_NEW_30


# Sprite IDs in ImgFile.dat
IMG_ID_YUSAENG = 267              # char\keon_1hs.Spr
IMG_ID_GEOMSUL_NANGIN = 328       # char\SwordPirate_online.spr
IMG_ID_JOCHONG_NANGIN = 329       # char\GunPirate_online.spr
IMG_ID_GUMIHO = 295               # char\fox.spr
IMG_ID_DAEWAN_WANGBEOL = 314      # char\bat_online.spr
IMG_ID_JOSEON_HORANGI = 272       # char\Tiger.Spr
IMG_ID_TEOLGAMYEON = 311          # char\furheaddemon_online.spr
IMG_ID_SEOLNYEO = 334             # char\snowwoman_online.spr
IMG_ID_JOSEON_DOKKAEBI = 300      # char\oni_online.spr
IMG_ID_BULGASARI = 296            # char\starfish.spr
IMG_ID_DUEOKSINI = 317            # char\dueoksini_online.spr

# Engine Function Virtual Addresses
VA_CALC_KIND_CHECKSUM = 0x0049BD50
VA_CMD_INIT = 0x004AC4F0
VA_BTN_INIT = 0x00496320
VA_ADD_BUTTON = 0x00412000

# Hook Sites
VA_HOOK_INIT_KIND = 0x004A2FD2
VA_HOOK_INIT_KIND_RESUME = 0x004A2FD9

VA_HOOK_BARRACKS_K = 0x00480488
VA_HOOK_BARRACKS_K_RESUME = 0x0048048D

VA_HOOK_HQ_K = 0x00483048
VA_HOOK_HQ_K_RESUME = 0x0048304D

VA_HOOK_STABLES_K = 0x004818ED
VA_HOOK_STABLES_K_RESUME = 0x004818F2
VA_HOOK_STABLES_33_K = 0x0048075D
VA_HOOK_STABLES_33_K_RESUME = 0x00480762

VA_HOOK_DEFAULT_CMDCARD = 0x004801BB
VA_JUSTICEK_CMDCARD = 0x00486B50
VA_COMBAT_CMDCARD = 0x00486EE0

# Joseon AdvBarracks (조선 훈련도감, KindID 0x33, SetupCommandCard 0x00480660) Hook
VA_HOOK_ADVBARRACKS_K = 0x0048075D
VA_HOOK_ADVBARRACKS_K_RESUME = 0x00480762

# Joseon Hornet Instant Death & AI Difficulty Hooks
VA_HOOK_HORNET_DEATH = 0x00401AAF
VA_HOOK_HORNET_DEATH_RESUME = 0x00401AE0
VA_HOOK_AI_CHEAT_BYPASS = 0x0043F8BB
VA_HOOK_AI_CHEAT_NEUTRALIZE = 0x0043F8C1
VA_AI_ORDER3_HARVEST_ENTRY = 0x0043F8F0
VA_AI_CHEAT_RESUME = 0x0043FB62
VA_HOOK_SKIRMISH_UI_SLOT = 0x004BA2B0
VA_HOOK_ORDER9_MARCH = 0x0043FC2D

# Safe .text Code Caves for Extended Unit Abilities
# 1) Inside the bypassed 45-byte 50:50 cheat block (0x0043F8C3..0x0043F8EF):
VA_CAVE_INIT_EXTRA = 0x0043F8C3          # 41 bytes (0x0043F8C3..0x0043F8EC)

# 2) Inside Order 7 developer debug-log block (0x0043C8F5: EB 34 -> frees 52B at 0x0043C8F7..0x0043C92A):
VA_HOOK_ORDER7_DEBUG_BYPASS = 0x0043C8F5 # 2 bytes: EB 34 (jmp short 0x0043C92B)
VA_CAVE_GUMIHO_CMDCARD = 0x0043C8F8      # 49 bytes (0x0043C8F8..0x0043C929)

# 3) Inside Order 8 developer debug-log block (0x0043CB45: E9 A6 00 00 00 -> frees 166B at 0x0043CB4A..0x0043CBEF):
VA_HOOK_ORDER8_DEBUG_BYPASS = 0x0043CB45 # 5 bytes: E9 A6 00 00 00 (jmp 0x0043CBF0)
VA_CAVE_BULGASARI_MODE = 0x0043CB4A      # 138 bytes (0x0043CB4A..0x0043CBD4)
VA_CAVE_DOCLONE_KIND = 0x0043CBD4        # 22 bytes  (0x0043CBD4..0x0043CBEA)

# 4) Inside 100% unreferenced dead CD-check function (0x00421A20..0x00421AA0, 128 bytes exact):
VA_CAVE_CALC_ATTACK_STATUS = 0x00421A20  # 53 bytes  (0x00421A20..0x00421A55)
VA_CAVE_BULGASARI_MP = 0x00421A55        # 42 bytes  (0x00421A55..0x00421A7F)
VA_CAVE_KNOCKBACK_P3 = 0x00421A7F        # 33 bytes  (0x00421A7F..0x00421AA0)

# 5) Safe developer debug-log bypasses in Areas B/C:
# 5a) Order 8 debug-print block (0x0043CAD8..0x0043CB0D, 53 bytes):
VA_HOOK_ORDER8_DEBUG_BYPASS2 = 0x0043CAD8 # 2 bytes: EB 33 (jmp short 0x0043CB0D, frees 51B at 0x0043CADA..0x0043CB0D)
VA_CAVE_BARRACKS_SLOT11 = 0x0043CADA      # 24 bytes (0x0043CADA..0x0043CAF2)

# 5b) Order 8 second debug-print block (0x0043CED8..0x0043CF09, 50 bytes; 0x0043CF0A is a live jump target!):
VA_HOOK_ORDER8_DEBUG_BYPASS3 = 0x0043CED8 # 2 bytes: EB 43 (jmp short 0x0043CF1D, frees 48B at 0x0043CEDA..0x0043CF09)
VA_CAVE_ADVBARRACKS_HOOK = 0x0043CEDA     # 47 bytes (0x0043CEDA..0x0043CF08 <= 0x0043CF09, preserves 0x0043CF0A!)

# 5c) Order 8 third & fourth debug-print blocks (0x0043D14A..0x0043D17F and 0x0043D8D1..0x0043D8F8):
VA_HOOK_ORDER8_DEBUG_BYPASS4 = 0x0043D14A # 5 bytes: E9 F3 02 00 00 (jmp 0x0043D442, frees 48B at 0x0043D14F..0x0043D17F)
VA_CAVE_KNOCKBACK_P1 = 0x0043D14F         # 48 bytes (0x0043D14F..0x0043D17F <= 0x0043D17F)
VA_HOOK_ORDER8_DEBUG_BYPASS5 = 0x0043D8D1 # 2 bytes: EB 25 (jmp short 0x0043D8F8, frees 37B at 0x0043D8D3..0x0043D8F8)
VA_CAVE_KNOCKBACK_P2 = 0x0043D8D3         # 31 bytes (0x0043D8D3..0x0043D8F2 <= 0x0043D8F8)
VA_HOOK_DESYNC_DUMP_BYPASS = 0x00440C59   # 2 bytes: 90 90 (nop out jne 0x00440C63 so 0x00440C20 always returns at 0x00440C62)
VA_CAVE_INIT_INFANTRY5 = 0x00440C63       # 512 bytes (0x00440C63..0x00440E63) inside dead desync dump block 0x00440C63..0x00440F5F
VA_CAVE_ALTTAB_ACTIVATE = 0x00440E64      # 90 bytes  (0x00440E64..0x00440EBE) inside dead desync dump block 0x00440C63..0x00440F5F
VA_CAVE_ATTACK_EFFECTS = 0x00440EC0       # 156 bytes (0x00440EC0..0x00440F5C <= 0x00440F5F; preserves live 0x00489410 Kind 0x0E!)

# Alt+Tab / Non-Topmost Window & Minimize/Restore Hook Sites
VA_WINMAIN_EXSTYLE_TOPMOST = 0x00423CC8   # push 8 (WS_EX_TOPMOST) -> push 0
VA_HOOK_WM_ACTIVATEAPP = 0x00423F0E       # 6 bytes (mov eax, [esp+0x18]; xor esi, esi) -> jmp VA_CAVE_ALTTAB_ACTIVATE; nop
VA_HOOK_WM_ACTIVATEAPP_ORIG = 0x00423F14  # cmp eax, esi (startup fallback when lpDDSPrimary == NULL)
VA_HOOK_WM_ACTIVATEAPP_COMMON = 0x00423F53 # cmp eax, esi (bypasses [0x00B643C8] force-active override from parsec_gdi.asi)
VA_HOOK_WM_SYSKEYDOWN_DEFPROC = 0x00424343 # 8 bytes (xor eax,eax; pop edi..ret 0x10) -> jmp 0x0042451A (DefWindowProcA)

# Archer Voice & SFX Constants
ARCHER_SFX_SELECT = 164                  # 0x00A4
ARCHER_SFX_DYING = 223                   # 0x00DF
ARCHER_SFX_MOVE = 254                    # 0x00FE
ARCHER_SFX_TRYATTACK = 314               # 0x013A
ARCHER_VOICE_TPL_ID = 0x02               # FILE_CHAR_ARCHERK (Kind 0x02)

# Extended Hook Sites for Clone, Bulgasari Dual-Mode, and Status Effects
VA_HOOK_DOCLONE_KIND = 0x00477EC4
VA_HOOK_DOCLONE_KIND_RESUME = 0x00477ECC
VA_HOOK_CANCLONE_LVL = 0x00477CD1
VA_HOOK_CANCLONE_TECH = 0x00477CEC
VA_HOOK_CANAUTOCAST_TECH = 0x00475BD2
VA_HOOK_CLONE_TOOLTIP = 0x0049A815
VA_HOOK_UPDATE_CHAR_MODE = 0x0048CBB6
VA_HOOK_UPDATE_CHAR_MODE_RESUME = 0x0048CBBE
VA_HOOK_FIRETANK_BULLET = 0x00474D58
VA_HOOK_FIRETANK_BULLET_RESUME = 0x00474D5F
VA_HOOK_CALC_ATTACK_STATUS = 0x00470CD5
VA_HOOK_CALC_ATTACK_STATUS_RESUME = 0x00470CE3
VA_SET_BULLET = 0x00403800
VA_ORDER_STOP = 0x004AEDA0

# Skirmish Default Tab Sites
VA_PROTOCOL_SELECT_RETAIL_HONJA = 0x004B8CD8
VA_PROTOCOL_SELECT_RETAIL_YEOROT = 0x004B8CE4

# No-CD / Standalone Fallback Tab Sites (when [0x004ED81C] != 1)
VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL = 0x004B8D09
VA_PROTOCOL_SELECT_FALLBACK_HONJA_SEL = 0x004B8D15
VA_PROTOCOL_SELECT_FALLBACK_YEOROT_DIS = 0x004B8D21
VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN = 0x004B8D2D

# F1 Debug TreeView Limit Site & Value
VA_F1_DEBUG_TREEVIEW_LIMIT = 0x004A796C
MAX_KIND_ID = 0x7E

# Code Cave Layout in .text Slack Space (0x004E4C70..0x004E5000)
VA_CAVE_UNIT_NAME_BASE = 0x004E4C70
VA_CAVE_UNIT_NAME_YUSAENG = 0x004E4C70
VA_CAVE_UNIT_NAME_GEOMSUL_NANGIN = 0x004E4C80
VA_CAVE_UNIT_NAME_JOCHONG_NANGIN = 0x004E4C90
VA_CAVE_UNIT_NAME_GUMIHO = 0x004E4CA0
VA_CAVE_UNIT_NAME_DAEWAN_WANGBEOL = 0x004E4CB0
VA_CAVE_UNIT_NAME_JOSEON_HORANGI = 0x004E4CC0
VA_CAVE_UNIT_NAME_TEOLGAMYEON = 0x004E4CD0
VA_CAVE_UNIT_NAME_SEOLNYEO = 0x004E4CE0
VA_CAVE_UNIT_NAME_JOSEON_DOKKAEBI = 0x004E4CF0
VA_CAVE_UNIT_NAME_BULGASARI = 0x004E4D00

# Backward-compat aliases
VA_CAVE_UNIT_NAME_70 = VA_CAVE_UNIT_NAME_YUSAENG
VA_CAVE_UNIT_NAME_71 = VA_CAVE_UNIT_NAME_GEOMSUL_NANGIN
VA_CAVE_UNIT_NAME_72 = VA_CAVE_UNIT_NAME_JOCHONG_NANGIN
VA_CAVE_UNIT_NAME = VA_CAVE_UNIT_NAME_70

VA_CAVE_INIT_ROUTINE = 0x004E4D10
VA_CAVE_BARRACKS_HOOK = 0x004E4F04
VA_CAVE_HQ_HOOK = 0x004E4F44
VA_CAVE_STABLES_HOOK = 0x004E4F84
VA_CAVE_CMDCARD_DISPATCH = 0x004E4FD4
VA_CAVE_BBOX_WH_TABLE = 0x004E4FE6

UNIT_NAMES: list[str] = [
    "유생",
    "검술 낭인",
    "조총 낭인",
    "구미호",
    "조선왕벌",
    "조선 호랑이",
    "털가면",
    "설녀",
    "조선 도깨비",
    "불가살이",
]

# Per-unit (bot_0e, w_1e, h_20) Selection Box & Health Bar coordinates:
#   - bot_0e (uint8 at [esi - 5] = prev_name_slot + 0x0B -> KindInfo + 0x0E): Bottom Y margin from canvas_h (Bot_Y = canvas_h - bot_0e)
#   - w_1e   (uint8 at 0x004E4FE6 + i*2 -> KindInfo + 0x1E): Selection Box / Health Bar Width % of canvas_w
#   - h_20   (uint8 at 0x004E4FE7 + i*2 -> KindInfo + 0x20): Selection Box Height % of canvas_h (Top_Y = Bot_Y - h_20*canvas_h//100)
UNIT_BBOX_PARAMS: list[tuple[int, int, int]] = [
    (0, 40, 85),   # 0x70 유생 (106x97, Head Y=26, Feet Y=87): Top_Y=15 (HP 15..18, MP 20..23), Bot_Y=97, Box_W=42px
    (15, 42, 76),  # 0x71 검술 낭인 (94x100, Head Y=17, Feet Y=81): Top_Y=9 (HP 9..12), Bot_Y=85, Box_W=39px
    (11, 40, 72),  # 0x72 조총 낭인 (102x103, Head Y=27, Feet Y=92): Top_Y=18 (HP 18..21), Bot_Y=92, Box_W=40px
    (56, 18, 37),  # 0x73 구미호 (250x187, Head Y=72, Feet Y=128): Top_Y=62 (HP 62..65), Bot_Y=131, Box_W=45px
    (70, 50, 46),  # 0x74 대만 왕벌 (92x146, Head Y=16, Body Bot Y=71): Top_Y=9 (HP 9..12), Bot_Y=76, Box_W=46px
    (10, 52, 75),  # 0x75 조선 호랑이 (114x87, Head Y=20, Feet Y=75): Top_Y=12 (HP 12..15), Bot_Y=77, Box_W=59px
    (0, 54, 89),   # 0x76 털가면 (78x76, Head Y=20, Feet Y=72): Top_Y=9 (HP 9..12), Bot_Y=76, Box_W=42px
    (6, 48, 90),   # 0x77 설녀 (130x164, Head Y=19, Feet Y=155): Top_Y=11 (HP 11..14), Bot_Y=158, Box_W=62px
    (72, 24, 56),  # 0x78 조선 도깨비 (268x206, Head Y=25, Feet Y=131): Top_Y=19 (HP 19..22), Bot_Y=134, Box_W=64px
    (0, 26, 68),   # 0x79 불가살이 (272x188, Head Y=71, Feet Y=166): Top_Y=61 (HP 61..64), Bot_Y=188, Box_W=70px
]

# Per-unit (voice_tpl_id, hit_sfx, die_sfx) packed at offset +0x0C..+0x0F of each 16-byte unit name slot:
#   - voice_tpl_id (uint8) : Native KindID to copy SelVoice (+0x6C), MovVoice (+0x70), AtkVoice (+0x72) from
#   - hit_sfx      (uint8) : KindInfo +0x5C (1 = sword/claw slash, 8 = musket gunshot, 23 = heavy giant smash)
#   - die_sfx      (uint16): KindInfo +0x6E DieVoice EffectGroup ID (e.g. 362 = EFFECT_ON_DIE_STARFISH)
UNIT_VOICE_SFX: list[tuple[int, int, int]] = [
    (0x4E, 9, 221),   # 0x70 유생: 유성룡(선비) 음성 + 조선 남성 사망음(221) + 부채 기공탄/포박술(9, Bullet 0x0D + Smoke 0x1D)
    (0x03, 1, 224),   # 0x71 검술 낭인: 일본 무사 음성 + 일본 무사 사망음(224) + 검 타격음(1)
    (0x0C, 8, 230),   # 0x72 조총 낭인: 일본 조총병 음성 + 일본 조총병 사망음(230) + 조총 탄환/총성(8, Bullet 0x13)
    (0x10, 11, 227),  # 0x73 구미호: 무녀 여성 음성 + 여성 사망 비명(227) + 요술 구슬 발사체(11, Bullet 0x0F + Smoke 0x1D)
    (0x6C, 1, 236),   # 0x74 대만 왕벌: 비행 날개짓 효과음(292) + 비행 괴수 사망음(236) + 독침 타격음(1)
    (0x1C, 1, 235),   # 0x75 조선 호랑이: 맹수 저음 포효(178) + 맹수 단말마(235) + 발톱 타격음(1)
    (0x1C, 26, 235),  # 0x76 털가면: 괴수 저음 포효(178) + 괴수 사망음(235) + 냉동탄/빙결 발사체(26, Bullet 0x0C + Smoke 0x1D)
    (0x63, 26, 227),  # 0x77 설녀: 아사코 여성 음성 + 여성 사망 비명(227) + 눈보라 냉기 스플래쉬 발사체(26, Bullet 0x0C + Smoke 0x1D)
    (0x27, 23, 234),  # 0x78 조선 도깨비: 거대 괴수 포효(234) + 괴수 사망음(234) + 방망이 지면 충격파 강타(23, Smoke 0x37)
    (0x1C, 15, 362),  # 0x79 불가살이: 괴수 저음 울림(178) + 원작 불가살이 전용 사망음(362) + 일본 화염차/승천용 평소 불공격(15 / 0x0F, Bullet 7 + Smoke 0x1B + 지면 화재 SetFire)
]

NAME_VAS: list[int] = [VA_CAVE_UNIT_NAME_BASE + i * 16 for i in range(10)]

# 5 Joseon Infantry Units Metadata (Muye 24-gi historical units)
JOSEON_5_INFANTRY_METADATA = [
    {
        "name": "등패수",
        "kind_id": 0x7A,
        "kind_id_alt": 0x70,
        "cmd_id": 0xBF,
        "cmd_id_alt": 0xAB,
        "btn_id": 0x4E,
        "btn_id_alt": 0x44,
        "hotkey": "E",
        "hotkeys_allowed": ["E", "D"],
        "building": "조선 훈련소",
        "building_kind": 0x31,
        "slot": 11,
        "hp": 800,
        "base_atk": 40,
        "defense": 5,
        "speed": 18,
        "rice": 160,
        "potato": 0,
        "iron": 30,
        "btime": 5,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "방어 및 탱킹 특화 보병",
        "desc": "원형 방패(등패)와 환도, 조선 전통 갑주 착용. 높은 방어력과 체력의 전열 탱커.",
    },
    {
        "name": "쌍수도병",
        "kind_id": 0x7B,
        "kind_id_alt": 0x71,
        "cmd_id": 0xC0,
        "cmd_id_alt": 0xAC,
        "btn_id": 0x4F,
        "btn_id_alt": 0x45,
        "hotkey": "V",
        "hotkeys_allowed": ["C", "S", "V"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 8,
        "hp": 600,
        "base_atk": 85,
        "defense": 2,
        "speed": 21,
        "rice": 220,
        "potato": 0,
        "iron": 60,
        "btime": 6,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "고공격 강력 충격 보병",
        "desc": "거대한 양손 대검(쌍수도) 장착. 높은 공격력을 지닌 충격 보병.",
    },
    {
        "name": "장창수",
        "kind_id": 0x7C,
        "kind_id_alt": 0x72,
        "cmd_id": 0xC1,
        "cmd_id_alt": 0xAD,
        "btn_id": 0x2E,
        "btn_id_alt": 0x46,
        "hotkey": "J",
        "hotkeys_allowed": ["L", "J"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 9,
        "hp": 550,
        "base_atk": 55,
        "defense": 3,
        "speed": 18,
        "rice": 180,
        "potato": 30,
        "iron": 40,
        "btime": 6,
        "range1": 2,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "긴 사거리 찌르기 독립 유닛",
        "desc": "주칠장창 장착. 기존 창병 대비 긴 사거리(2타일)의 독립 생산 유닛.",
    },
    {
        "name": "월도병",
        "kind_id": 0x7D,
        "kind_id_alt": 0x73,
        "cmd_id": 0xC2,
        "cmd_id_alt": 0xAE,
        "btn_id": 0x2F,
        "btn_id_alt": 0x47,
        "hotkey": "W",
        "hotkeys_allowed": ["W"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 10,
        "hp": 700,
        "base_atk": 65,
        "defense": 4,
        "speed": 19,
        "rice": 240,
        "potato": 20,
        "iron": 70,
        "btime": 7,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "공방 일체형 충격 보병",
        "desc": "언월도 장착. 우수한 공격력과 준수한 방어력을 겸비한 공방 일체형 보병.",
    },
    {
        "name": "낭선병",
        "kind_id": 0x7E,
        "kind_id_alt": 0x74,
        "cmd_id": 0xC3,
        "cmd_id_alt": 0xAF,
        "btn_id": 0x30,
        "btn_id_alt": 0x48,
        "hotkey": "N",
        "hotkeys_allowed": ["N"],
        "building": "조선 훈련도감",
        "building_kind": 0x57,
        "slot": 11,
        "hp": 550,
        "base_atk": 50,
        "defense": 3,
        "speed": 18,
        "rice": 200,
        "potato": 50,
        "iron": 40,
        "btime": 7,
        "range1": 2,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x00000000,
        "attack_atb": 1,
        "voice_tpl_id": ARCHER_VOICE_TPL_ID,
        "select_sfx": ARCHER_SFX_SELECT,
        "dying_sfx": ARCHER_SFX_DYING,
        "move_sfx": ARCHER_SFX_MOVE,
        "try_attack_sfx": ARCHER_SFX_TRYATTACK,
        "role": "긴 사거리 및 넉백 제어 보병",
        "desc": "대나무 가지창(낭선) 장착. 긴 사거리(2타일) 및 피격 적 넉백 기믹.",
    },
]

# Combined 15 Joseon Units Definitions (10 Existing + 5 Muye 24-gi Infantry)
UNIT_DEFINITIONS = [
    {"name": "유생", "kind_id": 0x70, "cmd_id": 0xAB, "btn_id": 0x44, "hotkey": "Y", "hp": 450, "base_atk": 60, "defense": 0, "speed": 18, "rice": 250, "potato": 0, "iron": 0, "btime": 6, "range1": 5, "range2": 7, "attack_atb": 9},
    {"name": "검술 낭인", "kind_id": 0x71, "cmd_id": 0xAC, "btn_id": 0x45, "hotkey": "K", "hp": 600, "base_atk": 80, "defense": 0, "speed": 21, "rice": 180, "potato": 0, "iron": 0, "btime": 5, "range1": 1, "range2": 5, "attack_atb": 1},
    {"name": "조총 낭인", "kind_id": 0x72, "cmd_id": 0xAD, "btn_id": 0x46, "hotkey": "P", "hp": 480, "base_atk": 70, "defense": 0, "speed": 18, "rice": 240, "potato": 0, "iron": 0, "btime": 6, "range1": 6, "range2": 7, "attack_atb": 8},
    {"name": "구미호", "kind_id": 0x73, "cmd_id": 0xAE, "btn_id": 0x47, "hotkey": "G", "hp": 750, "base_atk": 85, "defense": 0, "speed": 22, "rice": 280, "potato": 50, "iron": 0, "btime": 7, "range1": 5, "range2": 6, "attack_atb": 11},
    {"name": "조선왕벌", "kind_id": 0x74, "cmd_id": 0xAF, "btn_id": 0x48, "hotkey": "B", "hp": 500, "base_atk": 90, "defense": 0, "speed": 25, "rice": 200, "potato": 50, "iron": 0, "btime": 6, "range1": 1, "range2": 5, "attack_atb": 1},
    {"name": "조선 호랑이", "kind_id": 0x75, "cmd_id": 0xB0, "btn_id": 0x49, "hotkey": "T", "hp": 950, "base_atk": 120, "defense": 0, "speed": 24, "rice": 300, "potato": 0, "iron": 0, "btime": 7, "range1": 1, "range2": 5, "attack_atb": 1},
    {"name": "털가면", "kind_id": 0x76, "cmd_id": 0xB1, "btn_id": 0x4A, "hotkey": "M", "hp": 700, "base_atk": 80, "defense": 0, "speed": 19, "rice": 220, "potato": 20, "iron": 0, "btime": 6, "range1": 5, "range2": 6, "attack_atb": 26},
    {"name": "설녀", "kind_id": 0x77, "cmd_id": 0xB2, "btn_id": 0x4B, "hotkey": "I", "hp": 850, "base_atk": 95, "defense": 0, "speed": 17, "rice": 320, "potato": 50, "iron": 0, "btime": 7, "range1": 6, "range2": 7, "attack_atb": 26},
    {"name": "조선 도깨비", "kind_id": 0x78, "cmd_id": 0xB3, "btn_id": 0x4C, "hotkey": "O", "hp": 1100, "base_atk": 110, "defense": 0, "speed": 18, "rice": 350, "potato": 0, "iron": 0, "btime": 8, "range1": 1, "range2": 5, "attack_atb": 23},
    {"name": "불가살이", "kind_id": 0x79, "cmd_id": 0xB4, "btn_id": 0x4D, "hotkey": "U", "hp": 1400, "base_atk": 130, "defense": 0, "speed": 14, "rice": 450, "potato": 100, "iron": 0, "btime": 9, "range1": 6, "range2": 7, "attack_atb": 15},
    *JOSEON_5_INFANTRY_METADATA,
]



def va_to_offset(va: int) -> int:
    return va - IMAGE_BASE


def encode_rel32(opcode: int, src_va: int, dst_va: int) -> bytes:
    rel = dst_va - (src_va + 5)
    return bytes([opcode]) + struct.pack("<i", rel)


def build_init_cave(cave_va: int) -> bytes:
    """Build Cave Routine #1 at 0x004E4D10 (InitJoseonNewUnits: 10 units table-driven loop with full sprite, bbox, animation & voice/SFX setup)."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # Save registers, clear direction flag, initialize unit_idx = 0 in edi, name_va in esi
    buf += b"\x60"                      # pushal
    buf += b"\xFC"                      # cld
    buf += b"\x31\xFF"                  # xor edi, edi (unit_idx = 0..9)
    off_ebp = len(buf)
    buf += b"\xBD\x00\x00\x00\x00"      # mov ebp, TABLE_VA (patched below)
    buf += b"\xBB\xE8\xE2\x9C\x00"      # mov ebx, 0x009CE2E8 (KindInfo[0x70])
    buf += b"\xBE\x70\x4C\x4E\x00"      # mov esi, 0x004E4C70 (VA_CAVE_UNIT_NAME_BASE)

    loop_top_va = cur_va()

    # 1. Copy template KindInfo[0x6E] (0x009CDBC0) to [ebx], save next KindInfo ptr on stack
    buf += b"\x57"                      # push edi (save unit_idx)
    buf += b"\x56"                      # push esi (save name_va)
    buf += b"\x89\xDF"                  # mov edi, ebx
    buf += b"\xBE\xC0\xDB\x9C\x00"      # mov esi, 0x009CDBC0 (VA_KIND_TEMPLATE_6E)
    buf += b"\x31\xC9"                  # xor ecx, ecx
    buf += b"\xB1\xE5"                  # mov cl, 0xE5 (0x394 bytes)
    buf += b"\xF3\xA5"                  # rep movsd (leaves ecx == 0 and edi == ebx + 0x394)
    buf += b"\x5E"                      # pop esi (esi = name_va)
    buf += b"\x5A"                      # pop edx (edx = unit_idx 0..9)
    buf += b"\x57"                      # push edi (save next KindInfo ptr = ebx + 0x394)

    # 2. Patch KindInfo stats from 20-byte record at [ebp]:
    # +0x00: hp(H), +0x02: img_id(H), +0x04: rice_half(B), +0x05: potato(B)
    # +0x06: range1(B), +0x07: speed(B), +0x08: base_atk(B), +0x09: max_mp(B)
    # +0x0A: hotkey_u(B), +0x0B: icon_frame(B)
    # +0x0C..+0x13: 4x (start_frame(B), frames(B)) for Idle, Move, Die, Attack
    buf += b"\x8B\x45\x00\x89\x43\x06"  # mov eax, [ebp+0]; mov [ebx+6], eax (hp at +0x06; +0x08 overwritten by checksum)
    buf += b"\x8B\x45\x06"              # mov eax, [ebp+6] (al=range1, ah=speed, high word=max_mp:base_atk)
    buf += b"\x88\x43\x36"              # mov [ebx+0x36], al (Range1 = 1, 5, or 6)
    buf += b"\x88\x63\x2C"              # mov [ebx+0x2C], ah (MoveSpeed)
    # Configure ranged attack flags (Atb1 |= 0x400 and Range2 = 6) when Range1 > 1
    buf += b"\x3C\x01"                  # cmp al, 1
    buf += b"\x7E\x07"                  # jle .skip_ranged (+7)
    buf += b"\x80\x4B\x4D\x04"          # or byte ptr [ebx+0x4D], 4 (Atb1 |= 0x400 Ranged flag)
    buf += b"\xFE\x43\x38"              # inc byte ptr [ebx+0x38] (Range2 = 6)
    buf += b"\xC1\xE8\x10"              # shr eax, 16 (al=base_atk, ah=max_mp)
    buf += b"\x88\x43\x04"              # mov [ebx+0x04], al (BaseAttackPower)
    buf += b"\x88\x63\x2E"              # mov [ebx+0x2E], ah (MaxMP)
    buf += b"\x8B\x45\x04"              # mov eax, [ebp+4] (al=rice_half, ah=potato)
    buf += b"\x88\x63\x14"              # mov [ebx+0x14], ah (cost_potato)
    buf += b"\xB4\x00\xD1\xE0"          # mov ah, 0; shl eax, 1 (ax = cost_rice)
    buf += b"\x66\x89\x43\x12"          # mov [ebx+0x12], ax (cost_rice)

    # 3. Patch Selection Box & Health Bar coordinates (+0x0E BotY, +0x1E Width%, +0x20 Height%)
    buf += b"\x8A\x46\xFB"              # mov al, [esi-5] (bot_0e from prev_name_slot + 0x0B)
    buf += b"\x88\x43\x0E"              # mov [ebx+0x0E], al (KindInfo +0x0E BotY margin; +0x0F is already 0)
    buf += b"\x8B\x04\x55" + struct.pack("<I", VA_CAVE_BBOX_WH_TABLE)  # mov eax, [edx*2 + 0x004E4FE6]
    buf += b"\x88\x43\x1E"              # mov [ebx+0x1E], al (KindInfo +0x1E Width%; +0x1F is already 0)
    buf += b"\x88\x63\x20"              # mov [ebx+0x20], ah (KindInfo +0x20 Height%; +0x21 is already 0)

    # 4. Patch HitSound (+0x5C) and Voice IDs (+0x6C..+0x73) from [esi + 0x0C..0x0F]
    buf += b"\x8B\x7E\x0C"              # mov edi, [esi+0x0C] (al=voice_tpl_id, ah=hit_sfx, high word=die_sfx)
    buf += b"\x89\xF8"                  # mov eax, edi
    buf += b"\x88\x63\x5C"              # mov [ebx+0x5C], ah (HitSound)
    buf += b"\x0F\xB6\xC0"              # movzx eax, al (voice_tpl_id)
    buf += b"\x69\xC0\x94\x03\x00\x00"  # imul eax, eax, 0x394
    buf += b"\x05\x94\x52\x9B\x00"      # add eax, 0x009B5294 (&KindInfo[voice_tpl_id].SelVoice)
    buf += b"\x66\x8B\x38"              # mov di, [eax] (low word = SelVoice, high word = die_sfx)
    buf += b"\x89\x7B\x6C"              # mov [ebx+0x6C], edi (writes SelVoice at +0x6C and DieVoice at +0x6E)
    buf += b"\x8B\x40\x04"              # mov eax, [eax+4] (MovVoice & AtkVoice)
    buf += b"\x89\x43\x70"              # mov [ebx+0x70], eax (writes MovVoice at +0x70 and AtkVoice at +0x72)

    # 5. Pre-push CmdInit args while ecx == 0 (called after CalcKindChecksum)
    buf += b"\x51"                      # push ecx (0: req_tech)
    buf += b"\x8D\x42\x70\x50"          # lea eax, [edx + 0x70]; push eax (kind_id)
    buf += b"\x6A\x02\x6A\x02\x51\x6A\x08"  # push 2; push 2; push ecx(0); push 8

    # 6. Patch 4 cltAnimInfo slots at ebx + 0x20C + i*0x1C (i=0: Idle, 1: Move, 2: Die, 3: Attack)
    buf += b"\x8D\xBB\x0C\x02\x00\x00"  # lea edi, [ebx + 0x20C]
    buf += b"\x89\x77\x98"              # mov [edi - 0x68], esi ([ebx + 0x1A4] = name_va)
    buf += b"\x80\xFA\x04"              # cmp dl, 4 (is KindID 0x74 대만 왕벌?)
    buf += b"\x75\x04"                  # jne .skip_air (+4)
    buf += b"\x80\x4B\x4C\x10"          # or byte ptr [ebx+0x4C], 0x10 (Atb1 |= 0x10 Air Unit flag)
    buf += b"\x90"                      # nop (aligns code length to exact 298 bytes)

    anim_loop_va = cur_va()
    buf += b"\x0F\xB7\x45\x02"          # movzx eax, word ptr [ebp + 2] (img_id)
    buf += b"\x89\x47\x08"              # mov [edi + 8], eax (ImgID)
    buf += b"\x8B\x44\x4D\x0C"          # mov eax, [ebp + ecx*2 + 0x0C] (al=start_frame, ah=frames_per_dir)
    buf += b"\x88\x47\x0C"              # mov [edi + 0x0C], al (StartFrame; high bytes already 0)
    buf += b"\x88\x67\x04"              # mov [edi + 4], ah (FramesPerDir; high bytes already 0)
    buf += b"\x83\xC7\x1C"              # add edi, 0x1C
    buf += b"\x41"                      # inc ecx
    buf += b"\x83\xF9\x04"              # cmp ecx, 4
    buf += b"\x7C" + struct.pack("b", anim_loop_va - (cur_va() + 2))

    # Now edi == ebx + 0x27C, and ah == atk_frames (from ecx=3 iteration)
    buf += b"\xD0\xEC\xFE\xC4"          # shr ah, 1; inc ah (atk_inst = atk_frames // 2 + 1)
    buf += b"\x88\x67\xF4"              # mov [edi - 0x0C], ah ([ebx + 0x270] = Attack InstantFrame; high bytes 0)
    buf += b"\x8B\x47\xCC\x48"          # mov eax, [edi - 0x34]; dec eax (die_frames - 1)
    buf += b"\x89\x47\xD8"              # mov [edi - 0x28], eax ([ebx + 0x254] = Die InstantFrame / Corpse)

    # Save unit_idx (0..9) in callee-saved edi
    buf += b"\x89\xD7"                  # mov edi, edx

    # 7. Extended KindInfo initialization + Checksum calculation (sets Portrait IDs 165..174, clears Atb2 0x20, sets Gumiho Atb2 0x800, sets Bulgasari burst 6, then calls CalcKindChecksum)
    buf += b"\x89\xD9"                  # mov ecx, ebx
    buf += encode_rel32(0xE8, cur_va(), VA_CAVE_INIT_EXTRA)
    buf += b"\x89\x43\x08"              # mov [ebx + 8], eax

    # 8. Register CmdTable entry (CmdID = 0xAB + edi; 6 args already pushed in Step 5; returns eax=0x70+edi, edx=0)
    buf += b"\x6B\xCF\x18"              # imul ecx, edi, 0x18
    buf += b"\x81\xC1\x38\x3F\x9E\x00"  # add ecx, 0x009E3F38 (CmdTable[0xAB])
    buf += encode_rel32(0xE8, cur_va(), VA_CMD_INIT)

    # 9. Register ButtonTable entry (BtnID = 0x44 + edi; CmdInit returned eax = 0x70 + edi and edx = 0)
    buf += b"\x52"                      # push edx (0: p7)
    buf += b"\x56"                      # push esi (name_va)
    buf += b"\x8A\x55\x0A"              # mov dl, [ebp + 0x0A] (edx = hotkey_u)
    buf += b"\x8D\x4A\x20\x51"          # lea ecx, [edx + 0x20]; push ecx (hotkey_l)
    buf += b"\x52"                      # push edx (hotkey_u)
    buf += b"\x6A\x00"                  # push 0 (icon_file)
    buf += b"\xB6\x01\x8A\x55\x0B\x52"  # mov dh, 1; mov dl, [ebp + 0x0B]; push edx (icon_frame = 0x0100 | icon_byte -> 289..298)
    buf += b"\x04\x3B\x50"              # add al, 0x3B; push eax (cmd_id = 0xAB + edi)
    buf += b"\x8D\x8E\x18\x32\x15\x00"  # lea ecx, [esi + 0x00153218] (ButtonTable[0x44 + edi])
    buf += encode_rel32(0xE8, cur_va(), VA_BTN_INIT)

    # 10. Advance KindInfo ptr (popped from stack), name_va (+16), record ptr (+20), increment unit_idx in edi
    buf += b"\x5B"                      # pop ebx (ebx = next KindInfo ptr = old ebx + 0x394)
    buf += b"\x83\xC6\x10"              # add esi, 16 (0x10)
    buf += b"\x83\xC5\x14"              # add ebp, 20 (0x14)
    buf += b"\x47"                      # inc edi
    buf += b"\x83\xFF\x0A"              # cmp edi, 10
    rel_jl = loop_top_va - (cur_va() + 6)
    buf += b"\x0F\x8C" + struct.pack("<i", rel_jl)

    # 11. Exit sequence: restore GPRs, displaced instructions, jump to resume
    buf += b"\x61"                      # popal
    buf += b"\x33\xC9"                  # xor ecx, ecx
    buf += b"\xB8\x30\x52\x9B\x00"      # mov eax, 0x009B5230
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_INIT_KIND_RESUME)

    table_va = cur_va()
    buf[off_ebp + 1 : off_ebp + 5] = struct.pack("<I", table_va)

    # 10 unit records (20 bytes each: <HHBBBBBBBBBBBBBBBB):
    # (hp, img_id, rice//2, potato, range1, speed, base_atk, max_mp, hotkey_u, icon,
    #  idle_s, idle_f, move_s, move_f, die_s, die_f, atk_s, atk_f)
    unit_descriptors = [
        # 1. 유생 (0x70, keon_1hs.Spr <- Gersang justicek.AGF, ImgID 267, 176 frames: Atk 0..39, Die 60..71, Idle 72..131, Move 132..171; Icon 289 / 0x0121)
        (450, IMG_ID_YUSAENG, 250 // 2, 0, 5, 18, 60, 100, ord("Y"), 0x21, 72, 12, 132, 8, 60, 12, 0, 8),
        # 2. 검술 낭인 (0x71, SwordPirate_online.spr, ImgID 328, 136 frames: Atk 0..39, Idle 40..79, Move 80..119, Die 120..128; Icon 290 / 0x0122)
        (600, IMG_ID_GEOMSUL_NANGIN, 180 // 2, 0, 1, 21, 80, 80, ord("K"), 0x22, 40, 8, 80, 8, 120, 9, 0, 8),
        # 3. 조총 낭인 (0x72, GunPirate_online.spr, ImgID 329, 136 frames: Atk 0..39, Idle 40..79, Move 80..119, Die 120..128; Icon 291 / 0x0123)
        (480, IMG_ID_JOCHONG_NANGIN, 240 // 2, 0, 6, 18, 70, 0, ord("P"), 0x23, 40, 8, 80, 8, 120, 9, 0, 8),
        # 4. 구미호 (0x73, fox.spr, ImgID 295, 144 frames: Atk 0..39, Idle 40..79, Move 80..119, Die 120..136; Icon 292 / 0x0124)
        (750, IMG_ID_GUMIHO, 280 // 2, 50, 5, 22, 85, 100, ord("G"), 0x24, 40, 8, 80, 8, 120, 17, 0, 8),
        # 5. 대만 왕벌 (0x74, bat_online.spr <- Gersang hornet.AGF, ImgID 314, 160 frames: Idle/Move 0..39, Atk 72..111, Die 144..154; Icon 293 / 0x0125)
        (500, IMG_ID_DAEWAN_WANGBEOL, 200 // 2, 50, 1, 25, 90, 0, ord("B"), 0x25, 0, 8, 0, 8, 144, 11, 72, 8),
        # 6. 조선 호랑이 (0x75, Tiger.Spr, ImgID 272, 136 frames: Atk 0..39, Idle 40..79, Move 80..119, Die 120..129; Icon 294 / 0x0126)
        (950, IMG_ID_JOSEON_HORANGI, 300 // 2, 0, 1, 24, 120, 0, ord("T"), 0x26, 40, 8, 80, 8, 120, 10, 0, 8),
        # 7. 털가면 (0x76, furheaddemon_online.spr, ImgID 311, 130 frames: Idle 0..39, Atk 40..79, Move 80..119, Die 120..129; Icon 295 / 0x0127)
        (700, IMG_ID_TEOLGAMYEON, 220 // 2, 20, 5, 19, 80, 80, ord("M"), 0x27, 0, 8, 80, 8, 120, 10, 40, 8),
        # 8. 설녀 (0x77, snowwoman_online.spr, ImgID 334, 192 frames: Atk 0..64, Die 65..83, Idle 84..133, Move 134..183; Icon 296 / 0x0128)
        (850, IMG_ID_SEOLNYEO, 320 // 2, 50, 6, 17, 95, 120, ord("I"), 0x28, 84, 10, 134, 10, 65, 19, 0, 13),
        # 9. 조선 도깨비 (0x78, oni_online.spr, ImgID 300, 180 frames: Atk 0..59, Idle 60..99, Move 100..139, Die 140..150; Icon 297 / 0x0129)
        (1100, IMG_ID_JOSEON_DOKKAEBI, 350 // 2, 0, 1, 18, 110, 0, ord("O"), 0x29, 60, 8, 100, 8, 140, 11, 0, 12),
        # 10. 불가살이 (0x79, starfish.spr, ImgID 296, 180 active frames: FireLungeAtk 0..79 (16f), Idle 80..119 (8f), Move 120..159 (8f), Die 160..179 (20f); Icon 298 / 0x012A)
        (1400, IMG_ID_BULGASARI, 450 // 2, 100, 6, 14, 130, 120, ord("U"), 0x2A, 80, 8, 120, 8, 160, 20, 0, 16),
    ]

    for record in unit_descriptors:
        buf += struct.pack("<HHBBBBBBBBBBBBBBBB", *record)

    return bytes(buf)


def build_building_buttons_cave(
    cave_va: int,
    resume_va: int,
    buttons: list[tuple[int, int]],
) -> bytes:
    """Build a command card hook cave that adds custom Joseon unit buttons."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # Execute displaced `call 0x00412000`
    buf += encode_rel32(0xE8, cur_va(), VA_ADD_BUTTON)
    buf += b"\x31\xC9"  # xor ecx, ecx

    for slot, btn_id in buttons:
        buf += b"\x51" * 6  # push ecx * 6 (p8..p3 = 0; 0x00412000 pops 0 into ecx on return)
        buf += b"\x6A" + struct.pack("B", btn_id)
        buf += b"\x6A" + struct.pack("B", slot)
        buf += b"\x8B\xCE"  # mov ecx, esi
        buf += encode_rel32(0xE8, cur_va(), VA_ADD_BUTTON)

    buf += encode_rel32(0xE9, cur_va(), resume_va)
    return bytes(buf)


def build_advbarracks_buttons_cave(
    cave_va: int = VA_CAVE_ADVBARRACKS_HOOK,
    resume_va: int = VA_HOOK_ADVBARRACKS_K_RESUME,
) -> bytes:
    """Build compact Joseon AdvBarracks (조선 훈련도감 0x33) command card hook cave (47 bytes).

    Displaces 'call 0x00412000' at 0x0048075D, then loops edi=8..11 to add custom buttons:
      - Slot 8 : 쌍수도병 (Btn 0x4F, Hotkey 'S')
      - Slot 9 : 장창수   (Btn 0x2E, Hotkey 'J')
      - Slot 10: 월도병   (Btn 0x2F, Hotkey 'W')
      - Slot 11: 낭선병   (Btn 0x30, Hotkey 'N')
    Ends at 0x0043CF09 <= 0x0043CF0A, preserving the live jump target at 0x0043CF0A!
    """
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # 1. Displaced instruction from 0x0048075D: call 0x00412000 (VA_ADD_BUTTON)
    # Note: 0x00412000 always pops 0 into ecx on return (0x004123EB: pop ecx; ret 0x20).
    buf += encode_rel32(0xE8, cur_va(), VA_ADD_BUTTON)

    # 2. Push callee-saved edi, loop 4 times (edi = 8..11)
    buf += b"\x57"                      # push edi (1B)
    buf += b"\x6A\x08\x5F"              # push 8; pop edi (3B)

    loop_top_va = cur_va()
    buf += b"\x51" * 6                  # push ecx * 6 (6B, args 3..8 = 0)

    # btn: (table_va - 8) + edi
    off_mov_btn = len(buf) + 3
    buf += b"\x0F\xB6\x87\x00\x00\x00\x00"  # movzx eax, byte ptr [edi + <table_va - 8>] (7B)
    buf += b"\x50"                      # push eax (btn_id) (1B)
    buf += b"\x57"                      # push edi (slot = 8..11) (1B)
    buf += b"\x89\xF1"                  # mov ecx, esi (this) (2B)
    buf += encode_rel32(0xE8, cur_va(), VA_ADD_BUTTON)  # call VA_ADD_BUTTON (5B)

    buf += b"\x47"                      # inc edi (1B)
    buf += b"\x83\xFF\x0C"              # cmp edi, 12 (3B)
    rel_loop = loop_top_va - (cur_va() + 2)
    buf += b"\x7C" + struct.pack("b", rel_loop)  # jl loop_top_va (2B)

    buf += b"\x5F"                      # pop edi (1B)
    buf += encode_rel32(0xE9, cur_va(), resume_va)  # jmp resume_va (5B)

    table_va = cur_va()
    struct.pack_into("<I", buf, off_mov_btn, table_va - 8)
    buf += b"\x4F\x2E\x2F\x30"          # 4 buttons (4B: 0x4F, 0x2E, 0x2F, 0x30)

    return bytes(buf)


def build_barracks_slot11_cave(
    cave_va: int = VA_CAVE_BARRACKS_SLOT11,
    resume_va: int = VA_HOOK_BARRACKS_K_RESUME,
) -> bytes:
    """Build Barracks slot 11 trampoline cave to add 등패수 (Btn 0x4E, Slot 11)."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x31\xC9"                  # xor ecx, ecx
    buf += b"\x51" * 6                  # push ecx * 6
    buf += b"\x6A\x4E"                  # push 0x4E (BtnID 0x4E = 등패수 [E])
    buf += b"\x6A\x0B"                  # push 11 (Slot 11)
    buf += b"\x8B\xCE"                  # mov ecx, esi
    buf += encode_rel32(0xE8, cur_va(), VA_ADD_BUTTON)
    buf += encode_rel32(0xE9, cur_va(), resume_va)
    return bytes(buf)



def build_stables_buttons_cave(
    cave_va: int,
    resume_va: int = VA_HOOK_STABLES_K_RESUME,
    buttons: list[tuple[int, int]] | None = None,
) -> bytes:
    """Build Joseon Stables command card hook cave that adds custom buttons.

    Default buttons: 4 units added at Slots 7, 8, 9, 10:
      - Slot 7: 대만 왕벌 (Btn 0x48)
      - Slot 8: 조선 호랑이 (Btn 0x49)
      - Slot 9: 설녀 (Btn 0x4B)
      - Slot 10: 조선 도깨비 (Btn 0x4C)
      - Slot 11: 100% EMPTY (satisfying the 1-empty-slot invariant).
    """
    if buttons is None:
        buttons = [(7, 0x48), (8, 0x49), (9, 0x4B), (10, 0x4C)]
    return build_building_buttons_cave(cave_va, resume_va, buttons)


def build_cmdcard_dispatcher(cave_va: int) -> bytes:
    """Dispatch KindID 0x73 (구미호) -> 0x0043F900 (Combat + Clone button [C]), all other 0x70..0x79 -> 0x00486EE0 (pure combat, no Righteous Army O/E buttons)."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # cmp byte ptr [ecx + 0x8D], 0x73
    buf += b"\x80\xB9\x8D\x00\x00\x00\x73"
    # je VA_CAVE_GUMIHO_CMDCARD (0x0F 0x84 rel32)
    rel_je = VA_CAVE_GUMIHO_CMDCARD - (cur_va() + 6)
    buf += b"\x0F\x84" + struct.pack("<i", rel_je)
    # jmp VA_COMBAT_CMDCARD
    buf += encode_rel32(0xE9, cur_va(), VA_COMBAT_CMDCARD)
    return bytes(buf)


def build_hornet_death_patch(hook_va: int = VA_HOOK_HORNET_DEATH) -> bytes:
    """Build 49-byte patch at 0x00401AAF..0x00401AE0 for Joseon Hornet instant death and ground corpse handling.

    Routes:
      - KindID == 0x74 (조선왕벌): xor eax, eax; ret (skips 0x00444060, zero ground carcass remnant)
      - KindID >= 0x70 (other custom Joseon units): jmp 0x00401BB0 (spawns ground corpse at die_frames - 1)
      - KindID < 0x70: vanilla flags1 checking at 0x004F8C5C + KindID * 40
    """
    buf = bytearray()
    start_va = hook_va

    def cur_va() -> int:
        return start_va + len(buf)

    # 1. cmp eax, 0x74; je .instant_vanish
    buf += b"\x83\xF8\x74"
    off_je_vanish = len(buf)
    buf += b"\x74\x00"

    # 2. cmp eax, 0x70; jae .spawn_corpse
    buf += b"\x83\xF8\x70"
    off_jae_corpse = len(buf)
    buf += b"\x73\x00"

    # 3. Vanilla logic for KindID < 0x70
    buf += b"\x8D\x14\x80"                  # lea edx, [eax + eax*4]
    buf += b"\x8B\x04\xD5\x5C\x8C\x4F\x00"  # mov eax, dword ptr [edx*8 + 0x004F8C5C]
    buf += b"\xA8\x01"                      # test al, 1
    off_jne_corpse = len(buf)
    buf += b"\x75\x00"

    buf += b"\xA9\x00\x00\x00\x02"          # test eax, 0x02000000
    off_jne_alt = len(buf)
    buf += b"\x75\x00"

    # .instant_vanish:
    va_vanish = cur_va()
    buf += b"\x33\xC0\xC3"                  # xor eax, eax; ret

    # .spawn_corpse:
    va_corpse = cur_va()
    rel_corpse = 0x00401BB0 - (cur_va() + 5)
    buf += b"\xE9" + struct.pack("<i", rel_corpse)

    # .spawn_corpse_alt:
    va_alt = cur_va()
    rel_alt = 0x00401AE0 - (cur_va() + 5)
    buf += b"\xE9" + struct.pack("<i", rel_alt)

    # Fixup short jumps
    buf[off_je_vanish + 1] = va_vanish - (start_va + off_je_vanish + 2)
    buf[off_jae_corpse + 1] = va_corpse - (start_va + off_jae_corpse + 2)
    buf[off_jne_corpse + 1] = va_corpse - (start_va + off_jne_corpse + 2)
    buf[off_jne_alt + 1] = va_alt - (start_va + off_jne_alt + 2)

    assert len(buf) <= 49, f"Hornet death patch exceeds 49 bytes: {len(buf)}"
    buf += b"\x90" * (49 - len(buf))
    return bytes(buf)


def build_init_extra_cave(cave_va: int = VA_CAVE_INIT_EXTRA) -> bytes:
    """Build helper at 0x0043F8D0 called from InitJoseonNewUnits before CalcKindChecksum.

    Sets:
      - Portrait Frame ID = 165 + edi (0xA5..0xAE) at word ptr [ebx + 0x00]
      - Clears Atb2 bit 0x20 (Righteous Army building-entry / ambush flag) at byte ptr [ebx + 0x50]
      - Sets Atb2 |= 0x800 (Clone ability flag) at byte ptr [ebx + 0x51] for 0x73 구미호 (edi == 3)
      - Sets AttackBurstCount = 6 at byte ptr [ebx + 0x3A] for 0x79 불가살이 (edi == 9)
      - When edi == 9, calls VA_CAVE_INIT_INFANTRY5 to initialize KindInfo[0x7A..0x7E], CmdTable[0xB5..0xB9], ButtonTable
      - Tail-jumps to CalcKindChecksum (0x0049BD50)
    """
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x8D\x87\xA5\x00\x00\x00"  # lea eax, [edi + 0xA5]
    buf += b"\x66\x89\x03"              # mov word ptr [ebx], ax
    buf += b"\x80\x63\x50\xDF"          # and byte ptr [ebx + 0x50], 0xDF
    buf += b"\x83\xFF\x03"              # cmp edi, 3 (0x73 구미호)
    buf += b"\x75\x04"                  # jne .check_79 (+4)
    buf += b"\x80\x4B\x51\x08"          # or byte ptr [ebx + 0x51], 0x08 (Atb2 |= 0x800)
    buf += b"\x83\xFF\x09"              # cmp edi, 9 (0x79 불가살이)
    buf += b"\x75\x09"                  # jne .calc_chk (+9)
    buf += b"\xC6\x43\x3A\x06"          # mov byte ptr [ebx + 0x3A], 6
    buf += encode_rel32(0xE8, cur_va(), VA_CAVE_INIT_INFANTRY5) # call VA_CAVE_INIT_INFANTRY5
    buf += encode_rel32(0xE9, cur_va(), VA_CALC_KIND_CHECKSUM)
    return bytes(buf)


def build_gumiho_cmdcard_cave(cave_va: int = VA_CAVE_GUMIHO_CMDCARD) -> bytes:
    """Build command card setup at 0x0043C8F8 for 0x73 구미호: standard combat buttons + 분신술 [C] (BtnID 0x39 at Slot 5) for originals only; clones ([esi+0x74] != 0) skip BtnID 0x39."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x56"                              # push esi
    buf += b"\x89\xCE"                          # mov esi, ecx
    buf += b"\xFF\x74\x24\x08"                  # push dword ptr [esp + 8]
    buf += encode_rel32(0xE8, cur_va(), VA_COMBAT_CMDCARD)
    buf += b"\x80\x7E\x74\x00"                  # cmp byte ptr [esi + 0x74], 0 (is clone?)
    off_jne = len(buf)
    buf += b"\x75\x00"                          # jne .done
    buf += b"\x31\xC9"                          # xor ecx, ecx
    buf += b"\x51" * 6                          # push ecx * 6
    buf += b"\x6A\x39"                          # push 0x39 (BtnID 0x39 = 분신술 [C])
    buf += b"\x6A\x05"                          # push 5 (Slot 5)
    buf += b"\x89\xF1"                          # mov ecx, esi
    buf += encode_rel32(0xE8, cur_va(), VA_ADD_BUTTON)
    va_done = cur_va()
    buf[off_jne + 1] = va_done - (cave_va + off_jne + 2)
    buf += b"\xB8\x01\x00\x00\x00"              # mov eax, 1
    buf += b"\x5E"                              # pop esi
    buf += b"\xC2\x04\x00"                      # ret 4
    return bytes(buf)


def build_doclone_kind_cave(cave_va: int = VA_CAVE_DOCLONE_KIND) -> bytes:
    """Build DoClone KindID selector at 0x0043F940: preserves 0x50 곽재우 -> 0x61, while cloning self KindID for 0x73 구미호."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x0F\xB6\x83\x8D\x00\x00\x00"      # movzx eax, byte ptr [ebx + 0x8D]
    buf += b"\x3C\x50"                          # cmp al, 0x50 (곽재우)
    buf += b"\x75\x02"                          # jne .store (+2)
    buf += b"\xB0\x61"                          # mov al, 0x61
    buf += b"\x89\x44\x24\x1C"                  # mov dword ptr [esp + 0x1C], eax
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_DOCLONE_KIND_RESUME)
    return bytes(buf)


def build_bulgasari_mode_cave(cave_va: int = VA_CAVE_BULGASARI_MODE) -> bytes:
    """Build Bulgasari (0x79) dual-mode controller at 0x0043F960 (hooked from 0x0048CBB6 after UpdateStats).

    - When MP >= 20: Ranged Fire-Breath mode (Range1 = 6, AttackAtb = 13 / 0x0D = FILE_FIRETANKBULLET, frames 80..119, 8f/dir, inst=4).
    - When MP < 20 : Melee Back-Spike Thrust mode (Range1 = 1, AttackAtb = 1, frames 0..79, 16f/dir, inst=9).
    """
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x3C\x79"                                  # cmp al, 0x79 (불가살이)
    off_jne_orig = len(buf)
    buf += b"\x75\x00"                                  # jne .orig

    # If already in melee mode ([esi+0x1E4] == 1) and actively executing Attack order ([esi+0x9C] == 0x0B),
    # hold MP at 0 so passive MP regen does not interrupt the melee back-spike thrust combo mid-attack.
    buf += b"\x83\xBE\xE4\x01\x00\x00\x01"              # cmp dword ptr [esi + 0x1E4], 1
    off_jne_check_mp = len(buf)
    buf += b"\x75\x00"                                  # jne .check_mp
    buf += b"\x80\xBE\x9C\x00\x00\x00\x0B"              # cmp byte ptr [esi + 0x9C], 0x0B
    off_jne_check_mp2 = len(buf)
    buf += b"\x75\x00"                                  # jne .check_mp
    buf += b"\xC7\x86\xB8\x00\x00\x00\x00\x00\x00\x00"  # mov dword ptr [esi + 0xB8], 0

    va_check_mp = cur_va()
    buf[off_jne_check_mp + 1] = va_check_mp - (cave_va + off_jne_check_mp + 2)
    buf[off_jne_check_mp2 + 1] = va_check_mp - (cave_va + off_jne_check_mp2 + 2)

    buf += b"\x83\xBE\xB8\x00\x00\x00\x14"              # cmp dword ptr [esi + 0xB8], 20 (MP >= 20?)
    off_jl_melee = len(buf)
    buf += b"\x7C\x00"                                  # jl .melee

    # Ranged Fire Mode (MP >= 20): uses full 16-frame forward-lunging fire-belch motion (frames 0..79, inst=9)
    buf += b"\xC7\x86\x0C\x02\x00\x00\x06\x00\x00\x00"  # mov dword ptr [esi + 0x20C], 6 (Range1 = 6)
    buf += b"\xC7\x86\xE4\x01\x00\x00\x0F\x00\x00\x00"  # mov dword ptr [esi + 0x1E4], 15 (AttackAtb = 0x0F, Bullet 7 + SetFire)
    buf += b"\xC6\x05\x80\x05\x9D\x00\x10"              # mov byte ptr [0x009D0580], 16 (FramesPerDir = 16)
    buf += b"\xC6\x05\x88\x05\x9D\x00\x00"              # mov byte ptr [0x009D0588], 0 (StartFrame = 0)
    buf += b"\xC6\x05\x8C\x05\x9D\x00\x09"              # mov byte ptr [0x009D058C], 9 (InstantFrame = 9)
    off_jmp_orig = len(buf)
    buf += b"\xEB\x00"                                  # jmp .orig

    # Melee Back-Spike Mode (MP < 20)
    va_melee = cur_va()
    buf[off_jl_melee + 1] = va_melee - (cave_va + off_jl_melee + 2)
    buf += b"\xC7\x86\x0C\x02\x00\x00\x01\x00\x00\x00"  # mov dword ptr [esi + 0x20C], 1 (Range1 = 1)
    buf += b"\xC7\x86\xE4\x01\x00\x00\x01\x00\x00\x00"  # mov dword ptr [esi + 0x1E4], 1 (AttackAtb = 1)
    buf += b"\xC6\x05\x80\x05\x9D\x00\x10"              # mov byte ptr [0x009D0580], 16 (FramesPerDir = 16)
    buf += b"\xC6\x05\x88\x05\x9D\x00\x00"              # mov byte ptr [0x009D0588], 0 (StartFrame = 0)
    buf += b"\xC6\x05\x8C\x05\x9D\x00\x09"              # mov byte ptr [0x009D058C], 9 (InstantFrame = 9)

    va_orig = cur_va()
    buf[off_jne_orig + 1] = va_orig - (cave_va + off_jne_orig + 2)
    buf[off_jmp_orig + 1] = va_orig - (cave_va + off_jmp_orig + 2)

    buf += b"\x3C\x46"                                  # cmp al, 0x46
    rel_jne_48cca0 = 0x0048CCA0 - (cur_va() + 6)
    buf += b"\x0F\x85" + struct.pack("<i", rel_jne_48cca0)
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_UPDATE_CHAR_MODE_RESUME)
    return bytes(buf)


def build_bulgasari_mp_cave(cave_va: int = VA_CAVE_BULGASARI_MP) -> bytes:
    """Build Bulgasari MP consumption hook at 0x0043F9F0 (hooked from 0x00474D58 when firing BulletID 9 = FILE_FIRETANKBULLET)."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x80\xBE\x8D\x00\x00\x00\x79"              # cmp byte ptr [esi + 0x8D], 0x79
    off_jne = len(buf)
    buf += b"\x75\x00"                                  # jne .fire
    buf += b"\x83\xAE\xB8\x00\x00\x00\x14"              # sub dword ptr [esi + 0xB8], 20
    off_jns = len(buf)
    buf += b"\x79\x00"                                  # jns .fire
    buf += b"\xC7\x86\xB8\x00\x00\x00\x00\x00\x00\x00"  # mov dword ptr [esi + 0xB8], 0

    va_fire = cur_va()
    buf[off_jne + 1] = va_fire - (cave_va + off_jne + 2)
    buf[off_jns + 1] = va_fire - (cave_va + off_jns + 2)

    buf += b"\x6A\x09"                                  # push 9
    buf += encode_rel32(0xE8, cur_va(), VA_SET_BULLET)
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_FIRETANK_BULLET_RESUME)
    return bytes(buf)


def build_calc_attack_status_cave(cave_va: int = VA_CAVE_CALC_ATTACK_STATUS) -> bytes:
    """Build CalcAttack status effect and knockback hook at 0x00421A20 (hooked from 0x00470CD5).

    Routes living non-building targets to VA_CAVE_ATTACK_EFFECTS (0x0043D370) for:
      - 0x7E / 0x74 낭선병 knockback (+-16px X/Y push) and stagger timer (10 frames)
      - 0x70 유생 10.0s 포박술
      - 0x76 털가면 / 0x77 설녀 6.0s 얼리기
    Replaces original instructions at 0x00470CD5 (computing esi = edi * 0x758) and resumes at 0x00470CE3.
    """
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # 1. Target unit index in edx = si (TargetNewID & 0xFFFF held in esi at 0x00470CD5)
    buf += b"\x0F\xB7\xD6"                      # movzx edx, si (3B)
    buf += b"\x81\xFA\xD0\x07\x00\x00"          # cmp edx, 2000 (6B)
    off_jae = len(buf)
    buf += b"\x73\x00"                          # jae .resume (2B)

    # 2. Target alive check (word ptr [edx*2 + 0x008990C8] != 0)
    buf += b"\x66\x83\x3C\x55\xC8\x90\x89\x00\x00" # cmp word ptr [edx*2 + 0x008990C8], 0 (9B)
    off_je_dead = len(buf)
    buf += b"\x74\x00"                          # je .resume (2B)

    # 3. Target character offset in eax = edx * 0x758
    buf += b"\x69\xC2\x58\x07\x00\x00"          # imul eax, edx, 0x758 (6B)

    # 4. Target non-building check (byte ptr [eax + 0x0066B968] & 2 == 0)
    buf += b"\xF6\x80\x68\xB9\x66\x00\x02"      # test byte ptr [eax + 0x0066B968], 2 (7B)
    off_jne_bld = len(buf)
    buf += b"\x75\x00"                          # jne .resume (2B)

    # 5. Jump to extended attack effects cave (0x0043D370)
    buf += encode_rel32(0xE9, cur_va(), VA_CAVE_ATTACK_EFFECTS)

    # .resume:
    va_res = cur_va()
    buf[off_jae + 1] = va_res - (cave_va + off_jae + 2)
    buf[off_je_dead + 1] = va_res - (cave_va + off_je_dead + 2)
    buf[off_jne_bld + 1] = va_res - (cave_va + off_jne_bld + 2)

    # Attacker character offset in esi = edi * 0x758 (displaced instruction from 0x00470CD5)
    buf += b"\x69\xF7\x58\x07\x00\x00"          # imul esi, edi, 0x758 (6B)
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_CALC_ATTACK_STATUS_RESUME)
    return bytes(buf)


def build_knockback_tile_caves(
    va_p1: int = VA_CAVE_KNOCKBACK_P1,
    va_p2: int = VA_CAVE_KNOCKBACK_P2,
    va_p3: int = VA_CAVE_KNOCKBACK_P3,
) -> tuple[bytes, bytes, bytes]:
    """Build true 1-tile grid knockback helpers (DeleteID -> IsColl -> TileX/TileY/RX/RY/MovePercent -> SetID -> CalculateRealXY).

    On entry (inside pushal..popal from build_attack_effects_cave):
      - ebx = &cltChar[target] (eax + 0x0066B790)
      - ecx = attacker_id * 0x758
    """
    p1 = bytearray()
    p1 += b"\x8D\xB3\xA2\x02\x00\x00"              # lea esi, [ebx + 0x2A2] (6B, &target.TileX)
    p1 += b"\x0F\xBF\x3E"                          # movsx edi, word ptr [esi] (3B, target.TileX)
    p1 += b"\x66\x3B\xB9\x32\xBA\x66\x00"          # cmp di, word ptr [ecx + 0x0066BA32] (7B, cmp target.TileX, attacker.TileX)
    p1 += b"\x74\x06"                              # je .x_done (2B, skips 2+1+2+1=6B)
    p1 += b"\x7F\x03"                              # jg .x_inc (2B, skips 1+2=3B)
    p1 += b"\x4F"                                  # dec edi (1B)
    p1 += b"\xEB\x01"                              # jmp .x_done (2B)
    p1 += b"\x47"                                  # inc edi (1B)
    # .x_done:
    p1 += b"\x0F\xBF\x6E\x02"                      # movsx ebp, word ptr [esi + 2] (4B, target.TileY)
    p1 += b"\x66\x3B\xA9\x34\xBA\x66\x00"          # cmp bp, word ptr [ecx + 0x0066BA34] (7B, cmp target.TileY, attacker.TileY)
    p1 += b"\x74\x06"                              # je .y_done (2B, skips 2+1+2+1=6B)
    p1 += b"\x7F\x03"                              # jg .y_inc (2B, skips 1+2=3B)
    p1 += b"\x4D"                                  # dec ebp (1B)
    p1 += b"\xEB\x01"                              # jmp .y_done (2B)
    p1 += b"\x45"                                  # inc ebp (1B)
    # .y_done:
    p1 += encode_rel32(0xE9, va_p1 + len(p1), va_p2)

    p2 = bytearray()
    p2 += b"\x89\xD9"                              # mov ecx, ebx (2B)
    p2 += encode_rel32(0xE8, va_p2 + len(p2), 0x0048C3E0)  # call cltChar::DeleteID (5B)
    p2 += b"\x0F\xB7\x46\x64"                      # movzx eax, word ptr [esi + 0x64] (4B, target.Block at +0x306)
    p2 += b"\x80\xCC\x20"                          # or ah, 0x20 (3B, BLOCK_CHAR)
    p2 += b"\x50"                                  # push eax (1B, block_mask)
    p2 += b"\x55"                                  # push ebp (1B, new_tile_y)
    p2 += b"\x57"                                  # push edi (1B, new_tile_x)
    p2 += b"\x89\xD9"                              # mov ecx, ebx (2B)
    p2 += encode_rel32(0xE8, va_p2 + len(p2), 0x00412A70)  # call cltChar::IsColl (5B)
    p2 += b"\x85\xC0"                              # test eax, eax (2B)
    p2 += encode_rel32(0xE9, va_p2 + len(p2), va_p3)

    p3 = bytearray()
    p3 += b"\x75\x11"                              # jne .restore (2B, skip if blocked)
    p3 += b"\x66\x89\x3E"                          # mov word ptr [esi], di (3B, TileX = new_tile_x)
    p3 += b"\x66\x89\x6E\x02"                      # mov word ptr [esi + 2], bp (4B, TileY = new_tile_y)
    p3 += b"\x89\x46\x2E"                          # mov dword ptr [esi + 0x2E], eax (3B, RX=0, RY=0 at +0x2D0)
    p3 += b"\x66\x89\x83\x92\x06\x00\x00"          # mov word ptr [ebx + 0x692], ax (7B, MovePercent=0)
    # .restore:
    p3 += b"\x89\xD9"                              # mov ecx, ebx (2B)
    p3 += encode_rel32(0xE8, va_p3 + len(p3), 0x0048BD10)  # call cltChar::SetID (5B)
    p3 += b"\x89\xD9"                              # mov ecx, ebx (2B)
    p3 += encode_rel32(0xE9, va_p3 + len(p3), 0x0048B210)  # jmp cltChar::CalculateRealXY (5B, tail-call returns to caller)

    return bytes(p1), bytes(p2), bytes(p3)


def build_attack_effects_cave(
    cave_va: int = VA_CAVE_ATTACK_EFFECTS,
    resume_va: int = 0x00421A4A,
) -> bytes:
    """Build extended attack effects cave at 0x00440EC0 for 낭선병 true knockback (without paralysis) and unit status effects."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # Attacker character offset in ecx = edi * 0x758 (preserved in ecx for knockback!)
    buf += b"\x69\xCF\x58\x07\x00\x00"                  # imul ecx, edi, 0x758 (6B)
    # Attacker KindID in dl = byte ptr [ecx + 0x0066B790 + 0x8D] = [ecx + 0x0066B81D]
    buf += b"\x8A\x91\x1D\xB8\x66\x00"                  # mov dl, byte ptr [ecx + 0x0066B81D] (6B)
    # Check if attacker is 낭선병 (0x7E or 0x74)
    buf += b"\x80\xFA\x7E"                              # cmp dl, 0x7E (3B)
    off_je_knock = len(buf)
    buf += b"\x74\x00"                                  # je .knockback (2B)
    buf += b"\x80\xFA\x74"                              # cmp dl, 0x74 (3B)
    off_jne_status = len(buf)
    buf += b"\x75\x00"                                  # jne .status_effects (2B)

    # .knockback:
    va_knock = cur_va()
    buf[off_je_knock + 1] = va_knock - (cave_va + off_je_knock + 2)
    # 1. Execute true 1-tile grid knockback (DeleteID -> IsColl -> TileX/TileY -> SetID -> CalculateRealXY)
    buf += b"\x60"                                      # pushal (1B)
    buf += b"\x8D\x98\x90\xB7\x66\x00"                  # lea ebx, [eax + 0x0066B790] (6B, target cltChar*)
    buf += encode_rel32(0xE8, cur_va(), VA_CAVE_KNOCKBACK_P1)  # call VA_CAVE_KNOCKBACK_P1 (5B)
    buf += b"\x61"                                      # popal (1B)

    # 2. Apply immediate +-16px recoil on CenterX (0x0066B94E) and CenterY (0x0066B950)
    buf += b"\x66\x8B\x90\x4E\xB9\x66\x00"              # mov dx, word ptr [eax + 0x0066B94E] (7B)
    buf += b"\x66\x2B\x91\x4E\xB9\x66\x00"              # sub dx, word ptr [ecx + 0x0066B94E] (7B)
    buf += b"\x66\x85\xD2"                              # test dx, dx (3B)
    off_js_neg_x = len(buf)
    buf += b"\x78\x00"                                  # js .neg_x (2B)
    buf += b"\x66\x83\x80\x4E\xB9\x66\x00\x10"          # add word ptr [eax + 0x0066B94E], 16 (8B)
    off_jmp_y = len(buf)
    buf += b"\xEB\x00"                                  # jmp .check_y (2B)

    # .neg_x:
    va_neg_x = cur_va()
    buf[off_js_neg_x + 1] = va_neg_x - (cave_va + off_js_neg_x + 2)
    buf += b"\x66\x83\xA8\x4E\xB9\x66\x00\x10"          # sub word ptr [eax + 0x0066B94E], 16 (8B)

    # .check_y:
    va_chk_y = cur_va()
    buf[off_jmp_y + 1] = va_chk_y - (cave_va + off_jmp_y + 2)
    buf += b"\x66\x8B\x90\x50\xB9\x66\x00"              # mov dx, word ptr [eax + 0x0066B950] (7B)
    buf += b"\x66\x2B\x91\x50\xB9\x66\x00"              # sub dx, word ptr [ecx + 0x0066B950] (7B)
    buf += b"\x66\x85\xD2"                              # test dx, dx (3B)
    off_js_neg_y = len(buf)
    buf += b"\x78\x00"                                  # js .neg_y (2B)
    buf += b"\x66\x83\x80\x50\xB9\x66\x00\x10"          # add word ptr [eax + 0x0066B950], 16 (8B)
    off_jmp_ret_knock = len(buf)
    buf += b"\xEB\x00"                                  # jmp .return (2B, do NOT set HaltTimer or fall through!)

    # .neg_y:
    va_neg_y = cur_va()
    buf[off_js_neg_y + 1] = va_neg_y - (cave_va + off_js_neg_y + 2)
    buf += b"\x66\x83\xA8\x50\xB9\x66\x00\x10"          # sub word ptr [eax + 0x0066B950], 16 (8B)
    off_jmp_ret_knock2 = len(buf)
    buf += b"\xEB\x00"                                  # jmp .return (2B, do NOT set HaltTimer or fall through!)

    # .status_effects:
    va_status = cur_va()
    buf[off_jne_status + 1] = va_status - (cave_va + off_jne_status + 2)
    # Gate strictly by Attacker KindID (dl = byte ptr [ecx + 0x0066B81D]), NOT AttackAtb (bl),
    # because vanilla cannons use AttackAtb == 7 and vanilla shamans/monks use AttackAtb == 9!
    # dl == 0x70: 유생 포박술 (150 frames)
    buf += b"\x80\xFA\x70"                              # cmp dl, 0x70 (3B)
    buf += b"\xB9\x96\x00\x00\x00"                      # mov ecx, 150 (5B)
    off_je_apply = len(buf)
    buf += b"\x74\x00"                                  # je .apply (2B)
    # dl == 0x76 (털가면) or 0x77 (설녀): 얼리기 (90 frames)
    buf += b"\x80\xFA\x76"                              # cmp dl, 0x76 (3B)
    off_je_frz = len(buf)
    buf += b"\x74\x00"                                  # je .freeze (2B)
    buf += b"\x80\xFA\x77"                              # cmp dl, 0x77 (3B)
    off_jne_ret = len(buf)
    buf += b"\x75\x00"                                  # jne .return (2B)

    # .freeze:
    va_frz = cur_va()
    buf[off_je_frz + 1] = va_frz - (cave_va + off_je_frz + 2)
    buf += b"\x66\xC7\x80\xD0\xBA\x66\x00\x01\x3C"      # mov word ptr [eax + 0x0066BAD0], 0x3C01 (9B)
    buf += b"\x6A\x5A"                                  # push 90 (2B)
    buf += b"\x59"                                      # pop ecx (1B)

    # .apply:
    va_apply = cur_va()
    buf[off_je_apply + 1] = va_apply - (cave_va + off_je_apply + 2)
    buf += b"\x89\x88\x00\xBB\x66\x00"                  # mov dword ptr [eax + 0x0066BB00], ecx (6B)

    # .return:
    va_ret = cur_va()
    buf[off_jne_ret + 1] = va_ret - (cave_va + off_jne_ret + 2)
    buf[off_jmp_ret_knock + 1] = va_ret - (cave_va + off_jmp_ret_knock + 2)
    buf[off_jmp_ret_knock2 + 1] = va_ret - (cave_va + off_jmp_ret_knock2 + 2)
    buf += encode_rel32(0xE9, cur_va(), resume_va)
    return bytes(buf)


def build_init_infantry5_cave(cave_va: int = VA_CAVE_INIT_INFANTRY5) -> bytes:
    """Build table-driven initialization cave at 0x00440C70 for 5 Joseon infantry units (0x7A..0x7E)."""
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    buf += b"\x60"                          # pushal
    buf += b"\xFC"                          # cld
    buf += b"\x31\xF6"                      # xor esi, esi (unit_idx = 0..4)

    loop_top_va = cur_va()
    # ebx = 0x009D06B0 + esi * 0x394 (KindInfo[0x7A + esi])
    buf += b"\x69\xC6\x94\x03\x00\x00"      # imul eax, esi, 0x394
    buf += b"\x05\xB0\x06\x9D\x00"          # add eax, 0x009D06B0
    buf += b"\x89\xC3"                      # mov ebx, eax

    # 1. Copy Kind 0x02 (0x009B5950 - Joseon Spearman / 조선 창병) to [ebx] (0xE5 dwords = 0x394 bytes)
    buf += b"\x56"                          # push esi
    buf += b"\x89\xDF"                      # mov edi, ebx
    buf += b"\xBE\x50\x59\x9B\x00"          # mov esi, 0x009B5950
    buf += b"\x31\xC9\xB1\xE5"              # xor ecx, ecx; mov cl, 0xE5
    buf += b"\xF3\xA5"                      # rep movsd
    buf += b"\x5E"                          # pop esi

    # 2. Pointer to descriptor: ebp = table_va + esi * 24
    off_ebp = len(buf) + 1
    buf += b"\xBD\x00\x00\x00\x00"          # mov ebp, <table_va> (patched later)
    buf += b"\x6B\xC6\x18"                  # imul eax, esi, 24
    buf += b"\x01\xC5"                      # add ebp, eax

    # 3. cltAnimInfo ImgIDs (318, 319, 320, 322, 323) and Wait0 frames_per_dir = 8
    buf += b"\x0F\xB7\x45\x00"              # movzx eax, word ptr [ebp + 0]
    buf += b"\xC6\x83\x10\x02\x00\x00\x08"  # mov byte ptr [ebx + 0x210], 8 (Wait0 frames_per_dir = 8 -> 128..167)

    # Scan loop to update all AnimSlots where ImgID == 84 (Joseon Spearman ImgID) to eax (318..323)
    buf += b"\x57"                          # push edi
    buf += b"\x89\xDF"                      # mov edi, ebx
    buf += b"\x31\xC9\xB1\xE5"              # xor ecx, ecx; mov cl, 0xE5
    scan_top = cur_va()
    buf += b"\x81\x3F\x54\x00\x00\x00"      # cmp dword ptr [edi], 84 (Joseon Spearman ImgID)
    buf += b"\x75\x02"                      # jne +2
    buf += b"\x89\x07"                      # mov [edi], eax
    buf += b"\x83\xC7\x04"                  # add edi, 4
    buf += b"\x49"                          # dec ecx
    buf += b"\x75" + struct.pack("b", scan_top - (cur_va() + 2))
    buf += b"\x5F"                          # pop edi

    # 4. Set stats from descriptor (preserving +0x0C small icon = 20, +0x0E BotY = 14, +0x38 Range2 = 5):
    buf += b"\x66\x8B\x45\x02"              # mov ax, [ebp + 2] (HP)
    buf += b"\x66\x89\x43\x06"              # mov [ebx + 0x06], ax
    buf += b"\x66\x8B\x45\x04"              # mov ax, [ebp + 4] (Atk)
    buf += b"\x66\x89\x43\x04"              # mov [ebx + 0x04], ax
    buf += b"\x66\x8B\x45\x06"              # mov ax, [ebp + 6] (Def)
    buf += b"\x66\x89\x43\x42"              # mov [ebx + 0x42], ax (Defense at +0x42, NOT +0x0C!)
    buf += b"\x66\x8B\x45\x08"              # mov ax, [ebp + 8] (Spd)
    buf += b"\x66\x89\x43\x2C"              # mov [ebx + 0x2C], ax
    buf += b"\x66\x8B\x45\x0A"              # mov ax, [ebp + 10] (Rice)
    buf += b"\x66\x89\x43\x12"              # mov [ebx + 0x12], ax
    buf += b"\x66\x8B\x45\x0C"              # mov ax, [ebp + 12] (Potato)
    buf += b"\x66\x89\x43\x14"              # mov [ebx + 0x14], ax
    buf += b"\x31\xC0"                      # xor eax, eax (clear tech/prereq at +0x24 and Atb2 at +0x50)
    buf += b"\x89\x43\x24"                  # mov [ebx + 0x24], eax
    buf += b"\x89\x43\x50"                  # mov [ebx + 0x50], eax
    buf += b"\x0F\xB6\x45\x11"              # movzx eax, byte ptr [ebp + 17] (BTime)
    buf += b"\x66\x89\x43\x10"              # mov [ebx + 0x10], ax
    buf += b"\x0F\xB6\x45\x10"              # movzx eax, byte ptr [ebp + 16] (Range1: 3 for 장창수 & 낭선병, 1 for others)
    buf += b"\x66\x89\x43\x36"              # mov [ebx + 0x36], ax

    # 5. Fixed attributes (Atb1 = 0x00410005; Nation=1 and AttackAtb=1 preserved from Kind 0x02):
    buf += b"\xC7\x43\x4C\x05\x00\x41\x00"  # mov dword ptr [ebx + 0x4C], 0x00410005 (Atb1)
    buf += b"\x83\xF8\x03"                  # cmp eax, 3 (장창수 & 낭선병 144x140 bbox override: bot_0e=46, w_1e=19, h_20=29)
    buf += b"\x75\x0C"                      # jne +12
    buf += b"\xC6\x43\x0E\x2E"              # mov byte ptr [ebx + 0x0E], 46
    buf += b"\xC6\x43\x1E\x13"              # mov byte ptr [ebx + 0x1E], 19
    buf += b"\xC6\x43\x20\x1D"              # mov byte ptr [ebx + 0x20], 29

    # 6. Custom Muye24ki Sageuk Voice SoundGroups (202..217, 238..241) -> EffectSound IDs (485..504)
    buf += b"\x0F\xB6\x55\x17"              # movzx edx, byte ptr [ebp + 23] (base_sound_group)
    buf += b"\x8D\x0C\xB5\xE5\x01\x00\x00"  # lea ecx, [esi*4 + 485] (base_effect_id)
    buf += b"\x31\xC0"                      # xor eax, eax (k = 0..3)
    sfx_loop_top = cur_va()
    buf += b"\x66\x89\x54\x43\x6C"          # mov word ptr [ebx + eax*2 + 0x6C], dx
    buf += b"\x89\xD7"                      # mov edi, edx
    buf += b"\xC1\xE7\x05"                  # shl edi, 5 (group_id * 32)
    buf += b"\x66\xC7\x87\xA0\x7C\x05\x01\x01\x00"  # mov word ptr [edi + 0x01057CA0], 1
    buf += b"\x66\x89\x8F\xA2\x7C\x05\x01"  # mov word ptr [edi + 0x01057CA2], cx
    buf += b"\x42"                          # inc edx
    buf += b"\x41"                          # inc ecx
    buf += b"\x40"                          # inc eax
    buf += b"\x3C\x04"                      # cmp al, 4
    buf += b"\x7C" + struct.pack("b", sfx_loop_top - (cur_va() + 2))
    buf += b"\xC6\x43\x5C\x01"              # mov byte ptr [ebx + 0x5C], 1

    # 7. Portrait: 175 + esi
    buf += b"\x8D\x86\xAF\x00\x00\x00"      # lea eax, [esi + 175]
    buf += b"\x66\x89\x03"                  # mov word ptr [ebx], ax

    # 8. Name pointer: names_base + [ebp + 18]
    off_names_base = len(buf) + 1
    buf += b"\xB8\x00\x00\x00\x00"          # mov eax, <names_base_va>
    buf += b"\x0F\xB6\x4D\x12"              # movzx ecx, byte ptr [ebp + 18]
    buf += b"\x01\xC8"                      # add eax, ecx
    buf += b"\x89\x83\xA4\x01\x00\x00"      # mov [ebx + 0x1A4], eax

    # 9. Checksum
    buf += b"\x89\xD9"                      # mov ecx, ebx
    buf += encode_rel32(0xE8, cur_va(), VA_CALC_KIND_CHECKSUM)
    buf += b"\x89\x43\x08"                  # mov [ebx + 8], eax

    # 10. CmdTable (CmdIDs 0xBF..0xC3 at 0x009E4118..0x009E4178; preserves 0xB5..0xB9 Joseon Farmer Build!)
    buf += b"\x6A\x00"                      # push 0 (arg6)
    buf += b"\x8D\x46\x7A"                  # lea eax, [esi + 0x7A]
    buf += b"\x50"                          # push eax (arg5 = kind_id)
    buf += b"\x6A\x02"                      # push 2 (arg4)
    buf += b"\x6A\x02"                      # push 2 (arg3)
    buf += b"\x6A\x00"                      # push 0 (arg2)
    buf += b"\x6A\x08"                      # push 8 (arg1)
    buf += b"\x6B\xC6\x18"                  # imul eax, esi, 0x18
    buf += b"\x05\x18\x41\x9E\x00"          # add eax, 0x009E4118 (CmdTable[0xBF])
    buf += b"\x89\xC1"                      # mov ecx, eax
    buf += encode_rel32(0xE8, cur_va(), VA_CMD_INIT)

    # 11. ButtonTable (BtnIDs 0x4E, 0x4F, 0x2E, 0x2F, 0x30; preserves 0x50, 0x52, 0x54!)
    buf += b"\x6A\x00"                      # push 0
    off_names_base_btn = len(buf) + 1
    buf += b"\xB8\x00\x00\x00\x00"          # mov eax, <names_base_va>
    buf += b"\x0F\xB6\x4D\x12"              # movzx ecx, byte ptr [ebp + 18]
    buf += b"\x01\xC8"                      # add eax, ecx
    buf += b"\x50"                          # push eax (tooltip)
    buf += b"\x0F\xB6\x45\x13"              # movzx eax, byte ptr [ebp + 19] (hotkey_u)
    buf += b"\x8D\x48\x20"                  # lea ecx, [eax + 0x20]
    buf += b"\x51"                          # push ecx (hotkey_l)
    buf += b"\x50"                          # push eax (hotkey_u)
    buf += b"\x6A\x00"                      # push 0 (icon_file)
    buf += b"\x0F\xB7\x45\x14"              # movzx eax, word ptr [ebp + 20] (icon_frame: 216, 218, 219, 220, 233)
    buf += b"\x50"                          # push eax (icon_frame)
    buf += b"\x8D\x86\xBF\x00\x00\x00"      # lea eax, [esi + 0xBF] (32-bit disp, positive 0xBF..0xC3)
    buf += b"\x50"                          # push eax (cmd_id)
    buf += b"\x0F\xB6\x4D\x16"              # movzx ecx, byte ptr [ebp + 22] (btn_id)
    buf += b"\xC1\xE1\x04"                  # shl ecx, 4
    buf += b"\x81\xC1\x48\x7A\x63\x00"      # add ecx, 0x00637A48 (ButtonTable[0] base)
    buf += encode_rel32(0xE8, cur_va(), VA_BTN_INIT)

    # Next unit:
    buf += b"\x46"                          # inc esi
    buf += b"\x83\xFE\x05"                  # cmp esi, 5
    rel_loop = loop_top_va - (cur_va() + 6)
    buf += b"\x0F\x8C" + struct.pack("<i", rel_loop)

    buf += b"\x61"                          # popal
    buf += b"\xC3"                          # ret

    va_descriptors = cur_va()
    struct.pack_into("<I", buf, off_ebp, va_descriptors)

    # (img_id, hp, base_atk, def, spd, rice, pot, iron, r1, btime, name_off, hotkey, icon, btn, base_sfx_group)
    # Note: r1=3 (3*45=135px) for 장창수 & 낭선병 so all 2-tile isometric directions (up to 128px East/West) are within range!
    descriptors = [
        (318, 800, 40, 5, 18, 160, 0, 30, 1, 1, 0, ord("E"), 216, 0x4E, 202),   # 등패수 (SoundGroups 202..205 -> EffectSound 485..488)
        (319, 600, 85, 2, 21, 220, 0, 60, 1, 1, 7, ord("V"), 218, 0x4F, 206),   # 쌍수도병 (SoundGroups 206..209 -> EffectSound 489..492)
        (320, 550, 55, 3, 18, 180, 30, 40, 3, 1, 16, ord("J"), 219, 0x2E, 210), # 장창수 (SoundGroups 210..213 -> EffectSound 493..496)
        (322, 700, 65, 4, 19, 240, 20, 70, 1, 1, 23, ord("W"), 220, 0x2F, 214), # 월도병 (SoundGroups 214..217 -> EffectSound 497..500)
        (323, 550, 50, 3, 18, 200, 50, 40, 3, 1, 30, ord("N"), 233, 0x30, 238), # 낭선병 (SoundGroups 238..241 -> EffectSound 501..504)
    ]
    for d in descriptors:
        buf += struct.pack("<HHHHHHHHBBBBHBB", *d)

    va_names_base = cur_va()
    struct.pack_into("<I", buf, off_names_base, va_names_base)
    struct.pack_into("<I", buf, off_names_base_btn, va_names_base)

    names = ["등패수", "쌍수도병", "장창수", "월도병", "낭선병"]
    for n in names:
        buf += n.encode("cp949") + b"\x00"

    return bytes(buf)


def build_alttab_activate_cave(cave_va: int = VA_CAVE_ALTTAB_ACTIVATE) -> bytes:
    """
    Hook at 0x00423F0E (WM_ACTIVATEAPP in WndProc) to cleanly support Alt+Tab:
      - When lpDDSPrimary ([0x00E5D430]) == 0 (during initial WinMain startup), execute original code.
      - When deactivating (wParam/edi == 0) via Alt+Tab:
        * If not already iconic, call ShowWindow(hWnd/ebx, SW_MINIMIZE=6) so the borderless
          fullscreen window disappears from the screen and dxwrapper's WH_MOUSE_LL hook
          (which checks IsIconic(MainhWnd)) immediately releases the mouse cursor.
        * Set eax=0, esi=0, ebx=1 and jump to 0x00423F3C.
      - When activating (wParam/edi != 0) via Alt+Tab or taskbar click:
        * If iconic, call ShowWindow(hWnd/ebx, SW_RESTORE=9) before setting g_bAppActive=1.
        * Set eax=1, esi=0, ebx=1 and jump to 0x00423F3C (which restores DirectDraw surfaces).
    """
    buf = bytearray()

    def cur_va() -> int:
        return cave_va + len(buf)

    # Check if DirectDraw primary surface ([0x00E5D430]) is initialized
    buf += b"\x83\x3D\x30\xD4\xE5\x00\x00"      # cmp dword ptr [0x00E5D430], 0
    off_je_orig = len(buf)
    buf += b"\x74\x00"                          # je orig_path

    # Check wParam (in edi)
    buf += b"\x85\xFF"                          # test edi, edi
    off_jz_deact = len(buf)
    buf += b"\x74\x00"                          # jz deact_path

    # --- Activating (edi != 0) ---
    buf += b"\x53"                              # push ebx (hWnd)
    buf += b"\xFF\x15\x58\x52\x4E\x00"          # call dword ptr [0x004E5258] (IsIconic)
    buf += b"\x85\xC0"                          # test eax, eax
    buf += b"\x74\x09"                          # jz +9 (not_iconic)
    buf += b"\x6A\x09"                          # push 9 (SW_RESTORE)
    buf += b"\x53"                              # push ebx (hWnd)
    buf += b"\xFF\x15\x78\x52\x4E\x00"          # call dword ptr [0x004E5278] (ShowWindow)
    # not_iconic:
    buf += b"\xB8\x01\x00\x00\x00"              # mov eax, 1
    off_jmp_common = len(buf)
    buf += b"\xEB\x00"                          # jmp common_tail

    # --- Deactivating (edi == 0) ---
    deact_off = len(buf)
    buf[off_jz_deact + 1] = deact_off - (off_jz_deact + 2)
    buf += b"\x53"                              # push ebx (hWnd)
    buf += b"\xFF\x15\x58\x52\x4E\x00"          # call dword ptr [0x004E5258] (IsIconic)
    buf += b"\x85\xC0"                          # test eax, eax
    buf += b"\x75\x09"                          # jnz +9 (already_iconic)
    buf += b"\x6A\x06"                          # push 6 (SW_MINIMIZE)
    buf += b"\x53"                              # push ebx (hWnd)
    buf += b"\xFF\x15\x78\x52\x4E\x00"          # call dword ptr [0x004E5278] (ShowWindow)
    # already_iconic:
    buf += b"\x31\xC0"                          # xor eax, eax (eax = 0)

    # --- Common tail ---
    common_off = len(buf)
    buf[off_jmp_common + 1] = common_off - (off_jmp_common + 2)
    buf += b"\x31\xF6"                          # xor esi, esi
    buf += b"\xBB\x01\x00\x00\x00"              # mov ebx, 1
    buf += b"\xA3\x6C\x97\x66\x00"              # mov dword ptr [0x0066976C], eax (g_bAppActive)
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_WM_ACTIVATEAPP_COMMON)

    # --- Original startup path (lpDDSPrimary == 0) ---
    orig_off = len(buf)
    buf[off_je_orig + 1] = orig_off - (off_je_orig + 2)
    buf += b"\x8B\x44\x24\x18"                  # mov eax, dword ptr [esp + 0x18]
    buf += b"\x31\xF6"                          # xor esi, esi
    buf += encode_rel32(0xE9, cur_va(), VA_HOOK_WM_ACTIVATEAPP_ORIG)

    return bytes(buf)



def sync_button_sprites(fnt_dir: Path, pal_path: Path, button_png_dir: Path) -> None:
    """Encode custom Joseon 34x34 button PNGs using imjin2.pal and sync into button_plus.Spr and button.spr."""
    if not pal_path.exists() or not button_png_dir.exists():
        return
    import numpy as np
    from PIL import Image

    pal_raw = pal_path.read_bytes()
    scale = 4 if max(pal_raw[:768]) <= 63 else 1
    pal_colors = np.array(
        [(pal_raw[i * 3] * scale, pal_raw[i * 3 + 1] * scale, pal_raw[i * 3 + 2] * scale) for i in range(256)],
        dtype=np.int32,
    )

    def encode_rle(canvas: np.ndarray) -> bytes:
        out = bytearray()
        h, w = canvas.shape
        for y in range(h):
            row = canvas[y]
            x = 0
            while x < w:
                if row[x] == 0:
                    run = 0
                    while x + run < w and row[x + run] == 0 and run < 255:
                        run += 1
                    out.append(0xFE)
                    out.append(run)
                    x += run
                else:
                    val = int(row[x])
                    if val == 0xFE:
                        val = 244
                    out.append(val)
                    x += 1
        return bytes(out)

    extra_frames_rle = []
    for i in range(0x70, 0x7A):
        png_path = button_png_dir / f"btn_unit_0x{i:02x}.png"
        if not png_path.exists():
            return
        im = Image.open(png_path).convert("RGBA")
        arr = np.array(im)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3]
        indexed = np.zeros((34, 34), dtype=np.uint8)
        for y in range(34):
            for x in range(34):
                if alpha[y, x] < 64:
                    indexed[y, x] = 0
                else:
                    c = rgb[y, x]
                    dists = np.sum((pal_colors[1:] - c) ** 2, axis=1)
                    indexed[y, x] = np.argmin(dists) + 1
        extra_frames_rle.append(encode_rle(indexed))

    for target_name in ["button_plus.Spr", "button.spr"]:
        target_path = fnt_dir / target_name
        if not target_path.exists():
            continue
        data = bytearray(target_path.read_bytes())
        ver, w, h, fc = struct.unpack("<IIII", data[:16])
        if fc >= 299:
            continue
        data_size = struct.unpack("<I", data[0xBC8:0xBCC])[0]
        offsets = list(struct.unpack(f"<{fc}I", data[0x4C0 : 0x4C0 + 4 * fc]))
        sizes = list(struct.unpack(f"<{fc}H", data[0x970 : 0x970 + 2 * fc]))

        extra_bytes = bytearray()
        for rle in extra_frames_rle:
            offsets.append(data_size + len(extra_bytes))
            sizes.append(len(rle))
            extra_bytes.extend(rle)

        new_fc = fc + len(extra_frames_rle)
        new_data_size = data_size + len(extra_bytes)
        new_atlas_h = 34 * ((new_fc + 7) // 8)

        struct.pack_into("<I", data, 0x00C, new_fc)
        struct.pack_into(f"<{new_fc}I", data, 0x4C0, *offsets)
        struct.pack_into(f"<{new_fc}H", data, 0x970, *sizes)
        struct.pack_into("<III", data, 0xBC8, new_data_size, 34 * 8, new_atlas_h)
        data.extend(extra_bytes)

        try:
            os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        target_path.write_bytes(data)


def apply_patch(exe_path: Path, backup_path: Path) -> None:
    if not backup_path.exists():
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe_path, backup_path)

    raw = bytearray(backup_path.read_bytes())
    sha = hashlib.sha256(raw).hexdigest()
    if sha != ORIGINAL_SHA256:
        raise RuntimeError(f"Unexpected backup SHA-256: {sha} != {ORIGINAL_SHA256}")

    # 1. Write 10 Korean unit names + bot_0e ([esi-5]) + 4-byte voice/SFX descriptors (+0x0C..+0x0F) at 0x004E4C70..0x004E4D0F (16 bytes per entry)
    for i, name in enumerate(UNIT_NAMES):
        encoded = name.encode("cp949") + b"\x00"
        assert len(encoded) <= 12, f"Unit name '{name}' exceeds 12-byte budget: {len(encoded)}"
        off = va_to_offset(NAME_VAS[i])
        raw[off : off + len(encoded)] = encoded
        voice_tpl_id, hit_sfx, die_sfx = UNIT_VOICE_SFX[i]
        raw[off + 0x0C : off + 0x10] = struct.pack("<BBH", voice_tpl_id, hit_sfx, die_sfx)
    for i, (bot_0e, _, _) in enumerate(UNIT_BBOX_PARAMS):
        if i > 0:
            raw[va_to_offset(NAME_VAS[i] - 5)] = bot_0e

    # 2. Write Cave Routine #1 (InitJoseonNewUnits) at 0x004E4D10
    cave1 = build_init_cave(VA_CAVE_INIT_ROUTINE)
    assert VA_CAVE_INIT_ROUTINE + len(cave1) <= VA_CAVE_BARRACKS_HOOK, f"Cave 1 overflow: {len(cave1)} bytes"
    off_cave1 = va_to_offset(VA_CAVE_INIT_ROUTINE)
    raw[off_cave1 : off_cave1 + len(cave1)] = cave1

    # 3. Write Cave Routine #2 (Joseon Barracks Slot 8, 9, 10 hook) at 0x004E4F04
    # Note: 조선 조총병 (KindID=0x71, BtnID=0x49) is commented out from command card!
    barracks_buttons = [
        (8, 0x45),  # 검술 낭인 (Btn 0x45)
        # (9, 0x49),  # 조선 조총병 commented out
        (9, 0x46),  # 조총 낭인 (Btn 0x46)
        (10, 0x4A), # 털가면 (Btn 0x4A)
        # Slot 11: 100% EMPTY
    ]
    cave2 = build_building_buttons_cave(
        VA_CAVE_BARRACKS_HOOK,
        VA_CAVE_BARRACKS_SLOT11,
        buttons=barracks_buttons,
    )
    assert VA_CAVE_BARRACKS_HOOK + len(cave2) <= VA_CAVE_HQ_HOOK, f"Cave 2 overflow: {len(cave2)} bytes"
    off_cave2 = va_to_offset(VA_CAVE_BARRACKS_HOOK)
    raw[off_cave2 : off_cave2 + len(cave2)] = cave2

    # 4. Write Cave Routine #3 (Joseon HQ Slot 9, 10, 11 hook) at 0x004E4F44
    # Native HQ uses Slots 0..6 and Slot 8 (0x004832CB), leaving Slot 7 empty!
    hq_buttons = [
        (9, 0x44),   # 유생 (Btn 0x44)
        (10, 0x4D),  # 불가살이 (Btn 0x4D)
        (11, 0x47),  # 구미호 (Btn 0x47)
        # Slot 7: 100% EMPTY
    ]
    cave3 = build_building_buttons_cave(
        VA_CAVE_HQ_HOOK,
        VA_HOOK_HQ_K_RESUME,
        buttons=hq_buttons,
    )
    assert VA_CAVE_HQ_HOOK + len(cave3) <= VA_CAVE_STABLES_HOOK, f"Cave 3 overflow: {len(cave3)} bytes"
    off_cave3 = va_to_offset(VA_CAVE_HQ_HOOK)
    raw[off_cave3 : off_cave3 + len(cave3)] = cave3

    # 5. Write Cave Routine #4 (Joseon Stables Slot 7, 8, 9, 10 hook) at 0x004E4F84
    stables_buttons = [
        (7, 0x48),  # 대만 왕벌 (Btn 0x48)
        (8, 0x49),  # 조선 호랑이 (Btn 0x49)
        (9, 0x4B),  # 설녀 (Btn 0x4B)
        (10, 0x4C), # 조선 도깨비 (Btn 0x4C)
        # Slot 11: 100% EMPTY
    ]
    cave4 = build_stables_buttons_cave(
        VA_CAVE_STABLES_HOOK,
        VA_HOOK_STABLES_K_RESUME,
        buttons=stables_buttons,
    )
    assert VA_CAVE_STABLES_HOOK + len(cave4) <= VA_CAVE_CMDCARD_DISPATCH, f"Cave 4 overflow: {len(cave4)} bytes"
    off_cave4 = va_to_offset(VA_CAVE_STABLES_HOOK)
    raw[off_cave4 : off_cave4 + len(cave4)] = cave4

    # 6. Write Cave Routine #5 (Command Card Dispatcher for KindIDs 0x70..0x79) at 0x004E4FD4
    cave5 = build_cmdcard_dispatcher(VA_CAVE_CMDCARD_DISPATCH)
    assert VA_CAVE_CMDCARD_DISPATCH + len(cave5) <= VA_CAVE_BBOX_WH_TABLE, f"Cave 5 overflow: {len(cave5)} bytes"
    off_cave5 = va_to_offset(VA_CAVE_CMDCARD_DISPATCH)
    raw[off_cave5 : off_cave5 + len(cave5)] = cave5

    # 6b. Write 20-byte (w_1e, h_20) Selection Box & Health Bar table at 0x004E4FE6..0x004E4FF9
    bbox_wh_bytes = b"".join(struct.pack("<BB", w_1e, h_20) for _, w_1e, h_20 in UNIT_BBOX_PARAMS)
    assert len(bbox_wh_bytes) == 20
    off_bbox_wh = va_to_offset(VA_CAVE_BBOX_WH_TABLE)
    raw[off_bbox_wh : off_bbox_wh + len(bbox_wh_bytes)] = bbox_wh_bytes

    # 7. Patch Hook Site #1: End of InitAllKindInfo (0x004A2FD2, 7 bytes)
    hook1 = encode_rel32(0xE9, VA_HOOK_INIT_KIND, VA_CAVE_INIT_ROUTINE) + b"\x90\x90"
    off_h1 = va_to_offset(VA_HOOK_INIT_KIND)
    raw[off_h1 : off_h1 + 7] = hook1

    # 8. Patch Hook Site #2: Joseon Barracks command card (0x00480488, 5 bytes)
    hook2 = encode_rel32(0xE9, VA_HOOK_BARRACKS_K, VA_CAVE_BARRACKS_HOOK)
    off_h2 = va_to_offset(VA_HOOK_BARRACKS_K)
    raw[off_h2 : off_h2 + 5] = hook2

    # 9. Patch Hook Site #3: Joseon HQ command card (0x00483048, 5 bytes)
    hook3 = encode_rel32(0xE9, VA_HOOK_HQ_K, VA_CAVE_HQ_HOOK)
    off_h3 = va_to_offset(VA_HOOK_HQ_K)
    raw[off_h3 : off_h3 + 5] = hook3

    # 10. Patch Hook Site #4: Joseon Stables command card (0x004818ED, 5 bytes)
    hook_stables = encode_rel32(0xE9, VA_HOOK_STABLES_K, VA_CAVE_STABLES_HOOK)
    off_hs = va_to_offset(VA_HOOK_STABLES_K)
    raw[off_hs : off_hs + 5] = hook_stables

    # 11. Patch Default SetupCommandCard (0x004801BB) to call Cave #5 Dispatcher
    hook_cmdcard = encode_rel32(0xE8, VA_HOOK_DEFAULT_CMDCARD, VA_CAVE_CMDCARD_DISPATCH)
    off_hc = va_to_offset(VA_HOOK_DEFAULT_CMDCARD)
    raw[off_hc : off_hc + 5] = hook_cmdcard

    # 12. Default the '여럿이하기' protocol screen to select the '혼자하기' (Single-Player Skirmish) tab (retail path)
    raw[va_to_offset(VA_PROTOCOL_SELECT_RETAIL_HONJA) : va_to_offset(VA_PROTOCOL_SELECT_RETAIL_HONJA) + 2] = b"\x6A\x01"
    raw[va_to_offset(VA_PROTOCOL_SELECT_RETAIL_YEOROT) : va_to_offset(VA_PROTOCOL_SELECT_RETAIL_YEOROT) + 2] = b"\x6A\x00"

    # 13. Fix the no-CD / standalone fallback branch at 0x004B8D09..0x004B8D38 (when [0x004ED81C] != 1)
    raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL) : va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_SEL) + 2] = b"\x6A\x00"
    raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_SEL) : va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_SEL) + 2] = b"\x6A\x01"
    raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_DIS) : va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_YEOROT_DIS) + 2] = b"\x6A\x00"
    raw[va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN) : va_to_offset(VA_PROTOCOL_SELECT_FALLBACK_HONJA_EN) + 2] = b"\x6A\x01"

    # 14. Update F1 debug dialog unit list upper bound check from 0x6F to 0x79
    raw[va_to_offset(VA_F1_DEBUG_TREEVIEW_LIMIT)] = MAX_KIND_ID

    # 15. Patch Joseon Hornet instant death and ground corpse bypass at 0x00401AAF (49 bytes)
    hornet_patch = build_hornet_death_patch(VA_HOOK_HORNET_DEATH)
    assert len(hornet_patch) == 49
    off_hd = va_to_offset(VA_HOOK_HORNET_DEATH)
    raw[off_hd : off_hd + 49] = hornet_patch

    # 16 & 17. Bypass ONLY the 47-byte 50:50 resource cheat (0x0043F8C1 -> 0x0043F8F0)
    # Preserves 0x0043F8BB (jle 0x0043FB62) and 0x0043F8F0 (Order 3 Worker Resource Harvesting)!
    raw[va_to_offset(VA_HOOK_AI_CHEAT_NEUTRALIZE) : va_to_offset(VA_HOOK_AI_CHEAT_NEUTRALIZE) + 2] = b"\xEB\x2D"

    # 17a. Bypass developer-only AI debug print blocks in Order 7 (0x0043C8F5) and Order 8 (0x0043CB45)
    raw[va_to_offset(VA_HOOK_ORDER7_DEBUG_BYPASS) : va_to_offset(VA_HOOK_ORDER7_DEBUG_BYPASS) + 2] = b"\xEB\x34"
    raw[va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS) : va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS) + 5] = encode_rel32(
        0xE9, VA_HOOK_ORDER8_DEBUG_BYPASS, 0x0043CBF0
    )

    # 17a1. Bypass developer debug check in Order 8 at 0x0043CAD8 (frees 51B at 0x0043CADA..0x0043CB0D)
    raw[va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS2) : va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS2) + 2] = b"\xEB\x33"
    cave_barracks_slot11 = build_barracks_slot11_cave(VA_CAVE_BARRACKS_SLOT11)
    assert VA_CAVE_BARRACKS_SLOT11 + len(cave_barracks_slot11) <= 0x0043CB0D, f"Barracks Slot 11 cave overflow: {len(cave_barracks_slot11)}"
    raw[va_to_offset(VA_CAVE_BARRACKS_SLOT11) : va_to_offset(VA_CAVE_BARRACKS_SLOT11) + len(cave_barracks_slot11)] = cave_barracks_slot11

    # 17a2. Bypass developer debug check in Order 8 at 0x0043CED8 (frees 48B at 0x0043CEDA..0x0043CF09; 0x0043CF0A is live!)
    raw[va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS3) : va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS3) + 2] = b"\xEB\x43"
    cave_advbarracks = build_advbarracks_buttons_cave(VA_CAVE_ADVBARRACKS_HOOK)
    assert VA_CAVE_ADVBARRACKS_HOOK + len(cave_advbarracks) <= 0x0043CF0A, f"AdvBarracks cave overflow into live 0x0043CF0A: {len(cave_advbarracks)}"
    raw[va_to_offset(VA_CAVE_ADVBARRACKS_HOOK) : va_to_offset(VA_CAVE_ADVBARRACKS_HOOK) + len(cave_advbarracks)] = cave_advbarracks

    # Patch Joseon AdvBarracks (조선 훈련도감, KindID 0x33, 0x00480660) hook at 0x0048075D (5 bytes)
    hook_advbarracks = encode_rel32(0xE9, VA_HOOK_ADVBARRACKS_K, VA_CAVE_ADVBARRACKS_HOOK)
    raw[va_to_offset(VA_HOOK_ADVBARRACKS_K) : va_to_offset(VA_HOOK_ADVBARRACKS_K) + 5] = hook_advbarracks
    # Compact native Joseon AdvBarracks (0x00480660) hero recruit/research slots into Row 1 (Slots 4..7: 의병=4, 김시민=5, 유성룡=6, 이여송=7)
    # so Row 2 (Slots 8, 9, 10, 11) is 100% dedicated to 쌍수도병(8), 장창수(9), 월도병(10), 낭선병(11) without slot collisions!
    raw[va_to_offset(0x004808DB) + 1] = 0x05  # 김시민 연구: Slot 6 -> Slot 5 (shares Slot 5 with 김시민 등용)
    raw[va_to_offset(0x00480940) + 1] = 0x06  # 유성룡 등용 (path A): Slot 7 -> Slot 6
    raw[va_to_offset(0x004809BC) + 1] = 0x06  # 유성룡 등용 (path B): Slot 7 -> Slot 6
    raw[va_to_offset(0x00480A2D) + 1] = 0x06  # 유성룡 연구 (path A): Slot 8 -> Slot 6
    raw[va_to_offset(0x00480A7F) + 1] = 0x06  # 유성룡 연구 (path B): Slot 8 -> Slot 6
    raw[va_to_offset(0x00480AE4) + 1] = 0x07  # 이여송 등용 (path A): Slot 9 -> Slot 7
    raw[va_to_offset(0x00480B64) + 1] = 0x07  # 이여송 등용 (path B): Slot 9 -> Slot 7

    # 17b. Write Extended Unit Ability & Combat Caves into verified dead/bypassed .text regions
    cave_init_extra = build_init_extra_cave(VA_CAVE_INIT_EXTRA)
    assert VA_CAVE_INIT_EXTRA + len(cave_init_extra) <= VA_AI_ORDER3_HARVEST_ENTRY
    raw[va_to_offset(VA_CAVE_INIT_EXTRA) : va_to_offset(VA_CAVE_INIT_EXTRA) + len(cave_init_extra)] = cave_init_extra

    cave_gumiho_cmd = build_gumiho_cmdcard_cave(VA_CAVE_GUMIHO_CMDCARD)
    assert VA_CAVE_GUMIHO_CMDCARD + len(cave_gumiho_cmd) <= 0x0043C92B
    raw[va_to_offset(VA_CAVE_GUMIHO_CMDCARD) : va_to_offset(VA_CAVE_GUMIHO_CMDCARD) + len(cave_gumiho_cmd)] = cave_gumiho_cmd

    cave_bulgasari_mode = build_bulgasari_mode_cave(VA_CAVE_BULGASARI_MODE)
    assert VA_CAVE_BULGASARI_MODE + len(cave_bulgasari_mode) <= VA_CAVE_DOCLONE_KIND
    raw[va_to_offset(VA_CAVE_BULGASARI_MODE) : va_to_offset(VA_CAVE_BULGASARI_MODE) + len(cave_bulgasari_mode)] = cave_bulgasari_mode

    cave_doclone_kind = build_doclone_kind_cave(VA_CAVE_DOCLONE_KIND)
    assert VA_CAVE_DOCLONE_KIND + len(cave_doclone_kind) <= 0x0043CBF0
    raw[va_to_offset(VA_CAVE_DOCLONE_KIND) : va_to_offset(VA_CAVE_DOCLONE_KIND) + len(cave_doclone_kind)] = cave_doclone_kind

    cave_calc_attack_status = build_calc_attack_status_cave(VA_CAVE_CALC_ATTACK_STATUS)
    assert VA_CAVE_CALC_ATTACK_STATUS + len(cave_calc_attack_status) <= VA_CAVE_BULGASARI_MP
    raw[va_to_offset(VA_CAVE_CALC_ATTACK_STATUS) : va_to_offset(VA_CAVE_CALC_ATTACK_STATUS) + len(cave_calc_attack_status)] = cave_calc_attack_status

    cave_bulgasari_mp = build_bulgasari_mp_cave(VA_CAVE_BULGASARI_MP)
    assert VA_CAVE_BULGASARI_MP + len(cave_bulgasari_mp) <= VA_CAVE_KNOCKBACK_P3
    raw[va_to_offset(VA_CAVE_BULGASARI_MP) : va_to_offset(VA_CAVE_BULGASARI_MP) + len(cave_bulgasari_mp)] = cave_bulgasari_mp

    # 17b2. Write Nangseonbyung (0x7E) true tile knockback caves & bypasses (no paralysis/HaltTimer)
    raw[va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS4) : va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS4) + 5] = encode_rel32(
        0xE9, VA_HOOK_ORDER8_DEBUG_BYPASS4, 0x0043D442
    )
    raw[va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS5) : va_to_offset(VA_HOOK_ORDER8_DEBUG_BYPASS5) + 2] = b"\xEB\x25"
    kb_p1, kb_p2, kb_p3 = build_knockback_tile_caves()
    assert VA_CAVE_KNOCKBACK_P1 + len(kb_p1) <= 0x0043D17F
    assert VA_CAVE_KNOCKBACK_P2 + len(kb_p2) <= 0x0043D8F8
    assert VA_CAVE_KNOCKBACK_P3 + len(kb_p3) <= 0x00421AA0
    raw[va_to_offset(VA_CAVE_KNOCKBACK_P1) : va_to_offset(VA_CAVE_KNOCKBACK_P1) + len(kb_p1)] = kb_p1
    raw[va_to_offset(VA_CAVE_KNOCKBACK_P2) : va_to_offset(VA_CAVE_KNOCKBACK_P2) + len(kb_p2)] = kb_p2
    raw[va_to_offset(VA_CAVE_KNOCKBACK_P3) : va_to_offset(VA_CAVE_KNOCKBACK_P3) + len(kb_p3)] = kb_p3

    # Bypass dead multiplayer desync file-dump branch at 0x00440C59 (jne 0x00440C63 -> nop; nop)
    raw[va_to_offset(VA_HOOK_DESYNC_DUMP_BYPASS) : va_to_offset(VA_HOOK_DESYNC_DUMP_BYPASS) + 2] = b"\x90\x90"

    cave_init_infantry5 = build_init_infantry5_cave(VA_CAVE_INIT_INFANTRY5)
    assert VA_CAVE_INIT_INFANTRY5 + len(cave_init_infantry5) <= VA_CAVE_ALTTAB_ACTIVATE, f"InitInfantry5 cave overflow: {len(cave_init_infantry5)}"
    raw[va_to_offset(VA_CAVE_INIT_INFANTRY5) : va_to_offset(VA_CAVE_INIT_INFANTRY5) + len(cave_init_infantry5)] = cave_init_infantry5

    cave_alttab = build_alttab_activate_cave(VA_CAVE_ALTTAB_ACTIVATE)
    assert VA_CAVE_ALTTAB_ACTIVATE + len(cave_alttab) <= VA_CAVE_ATTACK_EFFECTS, f"AltTab cave overflow: {len(cave_alttab)}"
    raw[va_to_offset(VA_CAVE_ALTTAB_ACTIVATE) : va_to_offset(VA_CAVE_ALTTAB_ACTIVATE) + len(cave_alttab)] = cave_alttab

    # 17g. Patch WinMain & WndProc for clean Alt+Tab window switching & minimize/restore
    raw[va_to_offset(VA_WINMAIN_EXSTYLE_TOPMOST) : va_to_offset(VA_WINMAIN_EXSTYLE_TOPMOST) + 2] = b"\x6A\x00"
    hook_wm_activateapp = encode_rel32(0xE9, VA_HOOK_WM_ACTIVATEAPP, VA_CAVE_ALTTAB_ACTIVATE) + b"\x90"
    assert len(hook_wm_activateapp) == 6
    raw[va_to_offset(VA_HOOK_WM_ACTIVATEAPP) : va_to_offset(VA_HOOK_WM_ACTIVATEAPP) + 6] = hook_wm_activateapp
    hook_wm_syskeydown = encode_rel32(0xE9, VA_HOOK_WM_SYSKEYDOWN_DEFPROC, 0x0042451A) + b"\x90\x90\x90"
    assert len(hook_wm_syskeydown) == 8
    raw[va_to_offset(VA_HOOK_WM_SYSKEYDOWN_DEFPROC) : va_to_offset(VA_HOOK_WM_SYSKEYDOWN_DEFPROC) + 8] = hook_wm_syskeydown

    cave_attack_effects = build_attack_effects_cave(VA_CAVE_ATTACK_EFFECTS, resume_va=0x00421A4A)
    assert VA_CAVE_ATTACK_EFFECTS + len(cave_attack_effects) <= 0x00440F60, f"AttackEffects cave overflow: {len(cave_attack_effects)}"
    raw[va_to_offset(VA_CAVE_ATTACK_EFFECTS) : va_to_offset(VA_CAVE_ATTACK_EFFECTS) + len(cave_attack_effects)] = cave_attack_effects

    # 17f. Aggressive Native AI Enhancement Patches (Normal Economy + Fast Build/Squad/Assault)
    # P2: Balance worker harvesting to 50% Food (30% Rice + 20% Potato) / 50% Wood without 50:50 cheat
    raw[va_to_offset(0x004B04C2) : va_to_offset(0x004B04C2) + 4] = b"\x66\x83\xFB\x08"
    # P3..P8: Accelerate AI Decision Wheel cooldowns
    raw[va_to_offset(0x0043F7F7) : va_to_offset(0x0043F7F7) + 5] = b"\x3D\x2C\x01\x00\x00"  # Order 21 (Resource Scan): 1000 -> 300 ticks
    raw[va_to_offset(0x0043F880) : va_to_offset(0x0043F880) + 3] = b"\x83\xF8\x1E"          # Order 1 (Build): 100 -> 30 ticks
    raw[va_to_offset(0x0043F8B6) : va_to_offset(0x0043F8B6) + 5] = b"\x3D\x28\x00\x00\x00"  # Order 3 (Harvest): 200 -> 40 ticks
    raw[va_to_offset(0x0043F922) : va_to_offset(0x0043F922) + 5] = b"\x3D\x90\x01\x00\x00"  # Order 6 (Repair): 2000 -> 400 ticks
    raw[va_to_offset(0x0043F9CC) : va_to_offset(0x0043F9CC) + 5] = b"\x3D\x32\x00\x00\x00"  # Order 9/17 (Attack Wave): 200 -> 50 ticks
    raw[va_to_offset(0x0043FA94) : va_to_offset(0x0043FA94) + 5] = b"\x3D\x90\x01\x00\x00"  # Order 15 (Recruit Hero): 2000 -> 400 ticks
    raw[va_to_offset(0x0043FAF6) : va_to_offset(0x0043FAF6) + 5] = b"\x3D\x78\x00\x00\x00"  # Order 20 (Form Squads): 1500 -> 120 ticks
    # P9..P10: Uncap unit production crowding (7 -> 24) and relax per-type ratio cap (2x)
    raw[va_to_offset(0x00406C44) : va_to_offset(0x00406C44) + 6] = b"\x66\x83\x7C\x24\x10\x18"
    raw[va_to_offset(0x0043E8DA) : va_to_offset(0x0043E8DA) + 3] = b"\xD1\xE0\x90"
    # P11..P12: Remove 2x/3x defense overestimation in Order 8 and eliminate 1000-tick waypoint stall in Order 9
    raw[va_to_offset(0x0043CA91) : va_to_offset(0x0043CA91) + 10] = b"\x90\x90\x90\x90\x90\x90\x66\x6B\xC9\x01"
    raw[va_to_offset(0x0043D03B) : va_to_offset(0x0043D03B) + 3] = b"\x83\xF8\x0C"
    raw[va_to_offset(0x0043D1B9) : va_to_offset(0x0043D1B9) + 5] = b"\x3D\x50\x00\x00\x00"

    # 17c. Patch Clone Skill Hooks (0x73 구미호 분신술 + prevent summoned clones [esi+0x74]!=0 from cloning)
    hook_doclone_kind = encode_rel32(0xE9, VA_HOOK_DOCLONE_KIND, VA_CAVE_DOCLONE_KIND) + b"\x90\x90\x90"
    assert len(hook_doclone_kind) == 8
    raw[va_to_offset(VA_HOOK_DOCLONE_KIND) : va_to_offset(VA_HOOK_DOCLONE_KIND) + 8] = hook_doclone_kind
    raw[va_to_offset(VA_HOOK_CANCLONE_LVL) : va_to_offset(VA_HOOK_CANCLONE_LVL) + 2] = b"\x90\x90"
    # Replace 0x00477CE3..0x00477CED (9B tech cmp + 2B je) with: cmp byte ptr [esi + 0x74], 0; nop*5; jne 0x00477D02 (return 0 if clone)
    raw[va_to_offset(0x00477CE3) : va_to_offset(0x00477CE3) + 11] = b"\x80\x7E\x74\x00\x90\x90\x90\x90\x90\x75\x14"
    raw[va_to_offset(VA_HOOK_CANAUTOCAST_TECH) : va_to_offset(VA_HOOK_CANAUTOCAST_TECH) + 6] = b"\x90" * 6
    raw[va_to_offset(VA_HOOK_CLONE_TOOLTIP) : va_to_offset(VA_HOOK_CLONE_TOOLTIP) + 6] = encode_rel32(0xE9, VA_HOOK_CLONE_TOOLTIP, 0x0049AA4B) + b"\x90"

    # 17d. Patch Bulgasari Dual-Mode Hooks (0x79 불가살이 마나 소비 불공격 / 근접 등 가시 찌르기)
    hook_update_char_mode = encode_rel32(0xE9, VA_HOOK_UPDATE_CHAR_MODE, VA_CAVE_BULGASARI_MODE) + b"\x90\x90\x90"
    assert len(hook_update_char_mode) == 8
    raw[va_to_offset(VA_HOOK_UPDATE_CHAR_MODE) : va_to_offset(VA_HOOK_UPDATE_CHAR_MODE) + 8] = hook_update_char_mode

    hook_firetank_bullet = encode_rel32(0xE9, VA_HOOK_FIRETANK_BULLET, VA_CAVE_BULGASARI_MP) + b"\x90\x90"
    assert len(hook_firetank_bullet) == 7
    raw[va_to_offset(VA_HOOK_FIRETANK_BULLET) : va_to_offset(VA_HOOK_FIRETANK_BULLET) + 7] = hook_firetank_bullet

    # 17e. Patch CalcAttack Status Effect Hook (0x70 유생 10초 포박 마비 카운터 리셋 + 0x76 털가면 / 0x77 설녀 얼리기)
    hook_calc_attack_status = encode_rel32(0xE9, VA_HOOK_CALC_ATTACK_STATUS, VA_CAVE_CALC_ATTACK_STATUS) + b"\x90"
    assert len(hook_calc_attack_status) == 6
    raw[va_to_offset(VA_HOOK_CALC_ATTACK_STATUS) : va_to_offset(VA_HOOK_CALC_ATTACK_STATUS) + 6] = hook_calc_attack_status

    # 18. Sync genuine Gersang sprites for 유생 (ImgID 267: char\keon_1hs.Spr) and 대만 왕벌 (ImgID 314: char\Bat_online.spr)
    repo_root = Path(__file__).resolve().parent.parent.parent
    ext_assets = repo_root / "extracted_gersang_assets"
    char_dir = exe_path.parent / "char"
    if ext_assets.is_dir() and char_dir.is_dir():
        for src_name, dst_name in [
            ("justicek_gersang.spr", "keon_1hs.Spr"),
            ("hornet.spr", "Bat_online.spr"),
        ]:
            src_spr = ext_assets / src_name
            dst_spr = char_dir / dst_name
            if src_spr.exists() and (not dst_spr.exists() or dst_spr.read_bytes() != src_spr.read_bytes()):
                shutil.copy2(src_spr, dst_spr)

    # 19. Sync authentic 34x34 button sprites for all 10 Joseon custom units into button_plus.Spr and button.spr
    fnt_dir = exe_path.parent / "fnt"
    pal_path = exe_path.parent / "pal" / "imjin2.pal"
    button_png_dir = repo_root / "web_prototype" / "assets" / "ui" / "buttons"
    if fnt_dir.is_dir() and pal_path.is_file() and button_png_dir.is_dir():
        sync_button_sprites(fnt_dir, pal_path, button_png_dir)

    assert len(raw) == ORIGINAL_SIZE, f"Binary size altered: {len(raw)} != {ORIGINAL_SIZE}"
    if not exe_path.exists() or exe_path.read_bytes() != bytes(raw):
        if exe_path.exists():
            try:
                os.chmod(exe_path, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass

        for attempt in range(5):
            try:
                exe_path.write_bytes(raw)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1)

    print(f"[OK] Patched {exe_path} successfully ({len(raw):,} bytes).")
    for i, name in enumerate(UNIT_NAMES):
        print(f"     Unit #{i+1:<2d}: '{name}' (KindID=0x{0x70+i:02X}, CmdID=0x{0xAB+i:02X}, BtnID=0x{0x44+i:02X}) at 0x{NAME_VAS[i]:08X}")
    for i, u in enumerate(JOSEON_5_INFANTRY_METADATA):
        print(f"     Infantry #{i+1:<2d}: '{u['name']}' (KindID=0x{u['kind_id']:02X}, CmdID=0x{u['cmd_id']:02X}, BtnID=0x{u['btn_id']:02X})")
    print(f"     Cave #1   : 0x{VA_CAVE_INIT_ROUTINE:08X} ({len(cave1)} bytes)")
    print(f"     Cave #2   : 0x{VA_CAVE_BARRACKS_HOOK:08X} ({len(cave2)} bytes)")
    print(f"     Cave #3   : 0x{VA_CAVE_HQ_HOOK:08X} ({len(cave3)} bytes)")
    print(f"     Cave #4   : 0x{VA_CAVE_STABLES_HOOK:08X} ({len(cave4)} bytes)")
    print(f"     Cave #5   : 0x{VA_CAVE_CMDCARD_DISPATCH:08X} ({len(cave5)} bytes)")
    print(f"     Cave #BarracksSlot11: 0x{VA_CAVE_BARRACKS_SLOT11:08X} ({len(cave_barracks_slot11)} bytes)")
    print(f"     Cave #AdvBarracks   : 0x{VA_CAVE_ADVBARRACKS_HOOK:08X} ({len(cave_advbarracks)} bytes)")
    print(f"     Cave #InitInfantry5 : 0x{VA_CAVE_INIT_INFANTRY5:08X} ({len(cave_init_infantry5)} bytes)")
    print(f"     Cave #AttackEffects : 0x{VA_CAVE_ATTACK_EFFECTS:08X} ({len(cave_attack_effects)} bytes)")


def verify_disassembly(exe_path: Path) -> None:
    data = exe_path.read_bytes()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    cave1_len = len(build_init_cave(VA_CAVE_INIT_ROUTINE))
    cave2_len = len(build_building_buttons_cave(VA_CAVE_BARRACKS_HOOK, VA_CAVE_BARRACKS_SLOT11, [(8, 0x45), (9, 0x46), (10, 0x4A)]))
    cave3_len = len(build_building_buttons_cave(VA_CAVE_HQ_HOOK, VA_HOOK_HQ_K_RESUME, [(9, 0x44), (10, 0x4D), (11, 0x47)]))
    cave4_len = len(build_stables_buttons_cave(VA_CAVE_STABLES_HOOK, VA_HOOK_STABLES_K_RESUME, [(7, 0x48), (8, 0x49), (9, 0x4B), (10, 0x4C)]))
    cave5_len = len(build_cmdcard_dispatcher(VA_CAVE_CMDCARD_DISPATCH))
    cave_adv_len = len(build_advbarracks_buttons_cave(VA_CAVE_ADVBARRACKS_HOOK))
    cave_b11_len = len(build_barracks_slot11_cave(VA_CAVE_BARRACKS_SLOT11))
    cave_init_inf_len = len(build_init_infantry5_cave(VA_CAVE_INIT_INFANTRY5))
    cave_atk_eff_len = len(build_attack_effects_cave(VA_CAVE_ATTACK_EFFECTS, resume_va=0x00421A4A))

    regions = [
        ("Hook #1: InitAllKindInfo (0x004A2FD2)", 0x004A2FD2, 0x004A2FEB),
        ("Hook #2: Joseon Barracks (0x00480482)", 0x00480482, 0x00480494),
        ("Hook #3: Joseon HQ (0x00483042)", 0x00483042, 0x00483054),
        ("Hook #4: Joseon Stables (0x004818E5)", 0x004818E5, 0x004818F9),
        ("Hook #AdvBarracks (0x004810A0)", VA_HOOK_ADVBARRACKS_K, VA_HOOK_ADVBARRACKS_K + 5),
        ("Hook #5: Default SetupCommandCard (0x004801AE)", 0x004801AE, 0x004801C5),
        ("Hook #6A: Protocol Tab Selection - Retail (0x004B8CD8)", 0x004B8CD8, 0x004B8CF0),
        ("Hook #6B: Protocol Tab Selection - Standalone Fallback (0x004B8D09)", 0x004B8D09, 0x004B8D39),
        ("Hook #HornetDeath: Joseon Hornet Instant Death (0x00401AAF)", VA_HOOK_HORNET_DEATH, VA_HOOK_HORNET_DEATH_RESUME),
        ("Hook #AICheat: Economy 50:50 Cheat Bypass & Neutralize (0x0043F8BB)", VA_HOOK_AI_CHEAT_BYPASS, VA_HOOK_AI_CHEAT_NEUTRALIZE + 7),
        ("F1 Debug Dialog TreeView Limit (0x004A796A)", 0x004A796A, 0x004A7974),
        ("Cave #1: InitJoseonNewUnits", VA_CAVE_INIT_ROUTINE, VA_CAVE_INIT_ROUTINE + cave1_len - 200),
        ("Cave #2: JoseonBarracksHook", VA_CAVE_BARRACKS_HOOK, VA_CAVE_BARRACKS_HOOK + cave2_len),
        ("Cave #3: JoseonHQHook", VA_CAVE_HQ_HOOK, VA_CAVE_HQ_HOOK + cave3_len),
        ("Cave #4: JoseonStablesHook", VA_CAVE_STABLES_HOOK, VA_CAVE_STABLES_HOOK + cave4_len),
        ("Cave #5: CmdCardDispatcher", VA_CAVE_CMDCARD_DISPATCH, VA_CAVE_CMDCARD_DISPATCH + cave5_len),
        ("Cave #BarracksSlot11", VA_CAVE_BARRACKS_SLOT11, VA_CAVE_BARRACKS_SLOT11 + cave_b11_len),
        ("Cave #AdvBarracks", VA_CAVE_ADVBARRACKS_HOOK, VA_CAVE_ADVBARRACKS_HOOK + cave_adv_len),
        ("Cave #InitInfantry5", VA_CAVE_INIT_INFANTRY5, VA_CAVE_INIT_INFANTRY5 + min(120, cave_init_inf_len)),
        ("Cave #AttackEffects", VA_CAVE_ATTACK_EFFECTS, VA_CAVE_ATTACK_EFFECTS + min(120, cave_atk_eff_len)),
    ]

    for title, start_va, end_va in regions:
        print(f"\n=== {title} ===")
        chunk = data[va_to_offset(start_va) : va_to_offset(end_va)]
        for insn in md.disasm(chunk, start_va):
            print(f"  0x{insn.address:08X}: {insn.bytes.hex(' '):24s}  {insn.mnemonic:6s} {insn.op_str}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Patch Joseon New Units into dawn.exe")
    parser.add_argument("--exe", type=Path, default=Path("YM/dawn/dawn.exe"), help="Target dawn.exe path")
    parser.add_argument(
        "--backup",
        type=Path,
        default=Path("YM_backup_original/dawn.exe"),
        help="Bit-exact unpatched backup dawn.exe path",
    )
    parser.add_argument("--restore", action="store_true", help="Restore original unpatched dawn.exe")
    parser.add_argument("--verify", action="store_true", help="Print disassembly verification of hooks and caves")
    args = parser.parse_args()

    if args.restore:
        if not args.backup.exists():
            print(f"[ERR] Backup not found: {args.backup}", file=sys.stderr)
            return 1
        if args.exe.exists():
            try:
                os.chmod(args.exe, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
        for attempt in range(5):
            try:
                shutil.copy2(args.backup, args.exe)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1)
        print(f"[OK] Restored {args.exe} from {args.backup}")
        return 0

    apply_patch(args.exe, args.backup)
    if args.verify:
        verify_disassembly(args.exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
