"""
constants.py - Visual Asset Pipeline Constants for Joseon 5 Infantry Units
Imjinrok 2+ Chosun's Counterattack: Dawn (Version 9 .spr Format).
"""

from __future__ import annotations

# SPR Header Specification
SPR_HEADER_SIZE = 3060
SPR_VERSION = 9

# Direction mappings (5 stored directions, engine mirrors 3)
DIR_SOUTH = 0       # yaw = 0.0
DIR_SOUTH_WEST = 1  # yaw = pi / 4
DIR_WEST = 2        # yaw = pi / 2
DIR_NORTH_WEST = 3  # yaw = 3 * pi / 4
DIR_NORTH = 4       # yaw = pi

NUM_DIRECTIONS = 5
FRAMES_PER_DIR = 8

# Animation frame blocks (168 frames total)
# 0..39   : Move   (5 dirs x 8 frames = 40 frames)
# 40..47  : Die    (8 frames, frame 47 = resting corpse)
# 48..87  : Attack (5 dirs x 8 frames = 40 frames, hit at frame offset 5)
# 88..127 : Idle   (5 dirs x 8 frames = 40 frames)
# 128..167: Hit    (5 dirs x 8 frames = 40 frames, stagger / guard)
FRAME_COUNT_UNIT = 168

MOVE_START = 0
DIE_START = 40
DIE_COUNT = 8
CORPSE_FRAME = 47
ATTACK_START = 48
ATTACK_HIT_OFFSET = 5
IDLE_START = 88
HIT_START = 128

# Unit Dimensions and Bounding Boxes
UNIT_SPECS = {
    "dengpaesu": {
        "kor_name": "등패수",
        "desc": "Round rattan shield (등패) + hwando + dujeong-gap coat",
        "file_name": "dengpaesu.spr",
        "width": 68,
        "height": 68,
        "btn_index": 216,
        "portrait_index": 175,
        "portrait_alt_index": 175,
        "kind_id": 0x7A,
    },
    "ssangsudo": {
        "kor_name": "쌍수도병",
        "desc": "Two-handed 150cm streamlined curved greatsword (1.2x 쌍수도) + gyeongbeon-gap armor",
        "file_name": "ssangsudo.spr",
        "width": 96,
        "height": 88,
        "btn_index": 218,
        "portrait_index": 176,
        "portrait_alt_index": 176,
        "kind_id": 0x7B,
    },
    "jangchangsu": {
        "kor_name": "장창수",
        "desc": "Long 15-foot spear (2x length) + crimson tassel + pointed helmet",
        "file_name": "jangchangsu.spr",
        "width": 144,
        "height": 140,
        "btn_index": 219,
        "portrait_index": 177,
        "portrait_alt_index": 177,
        "kind_id": 0x7C,
    },
    "woldo": {
        "kor_name": "월도병",
        "desc": "Crescent blade halberd (언월도) + dragon collar + heavy dujeong-gap",
        "file_name": "woldo.spr",
        "width": 78,
        "height": 74,
        "btn_index": 220,
        "portrait_index": 178,
        "portrait_alt_index": 178,
        "kind_id": 0x7D,
    },
    "nangseon": {
        "kor_name": "낭선병",
        "desc": "Long 2x multi-branched bamboo spear (낭선) + prominent sub-twigs & iron barbs",
        "file_name": "nangseon.spr",
        "width": 144,
        "height": 140,
        "btn_index": 233,
        "portrait_index": 179,
        "portrait_alt_index": 179,
        "kind_id": 0x7E,
    },
}

# Authentic imjin2.pal color indices
IDX_TRANSPARENT = 0
IDX_OUTLINE = 228       # Translucent shadow outline

# Player Team Colors (Blue = Joseon default player 0; remapped by engine for P1..P4)
IDX_TEAM_DARK = 236     # RGB(0, 0, 40)
IDX_TEAM_MID = 237      # RGB(0, 0, 80)
IDX_TEAM_HIGH = 238     # RGB(0, 0, 121)
IDX_TEAM_BRIGHT = 239   # RGB(0, 0, 161)

# Black / Charcoal leather & hair ramp
IDX_BLACK_DEEP = 241    # RGB(16, 16, 16)
IDX_BLACK_DARK = 242    # RGB(32, 32, 32)
IDX_BLACK_MID = 243     # RGB(48, 48, 48)
IDX_BLACK_LIGHT = 244   # RGB(68, 68, 68)

# Steel / Iron weapon ramp
IDX_STEEL_GLEAM = 255   # RGB(255, 255, 255)
IDX_STEEL_HIGH = 253    # RGB(222, 222, 222)
IDX_STEEL_MID = 250     # RGB(170, 170, 170)
IDX_STEEL_LOW = 211     # RGB(161, 161, 161)
IDX_STEEL_DARK = 156    # RGB(93, 105, 105)

# Crimson / Red lacquer & tassel ramp
IDX_RED_BRIGHT = 69     # RGB(202, 0, 0)
IDX_RED_HIGH = 47       # RGB(161, 36, 4)
IDX_RED_MID = 113       # RGB(113, 20, 20)
IDX_RED_DARK = 232      # RGB(40, 0, 0)

# Gold / Brass rivet & ornament ramp
IDX_GOLD_BRIGHT = 35    # RGB(230, 170, 36)
IDX_GOLD_HIGH = 41      # RGB(224, 160, 28)
IDX_GOLD_MID = 33       # RGB(206, 133, 28)
IDX_GOLD_DARK = 214     # RGB(121, 85, 0)

# Rattan & Wood ramp
IDX_WOOD_LIGHT = 126    # RGB(210, 149, 117)
IDX_WOOD_MID = 106      # RGB(149, 105, 44)
IDX_WOOD_DARK = 99      # RGB(93, 72, 28)
IDX_WOOD_DEEP = 188     # RGB(60, 28, 0)

# Bamboo Green & Golden Bamboo ramp (낭선 branches & sub-twigs)
IDX_BAMBOO_GOLD = 21    # RGB(220, 176, 104) - bright golden bamboo
IDX_BAMBOO_VIVID = 70   # RGB(200, 200, 0)   - vivid yellow-green twig highlight
IDX_BAMBOO_LIGHT = 77   # RGB(145, 129, 89)
IDX_BAMBOO_HIGH = 27    # RGB(72, 129, 56)
IDX_BAMBOO_MID = 7      # RGB(44, 93, 40)
IDX_BAMBOO_DARK = 228   # RGB(0, 40, 0)

# Flesh / Skin tone ramp
IDX_FLESH_BRIGHT = 177  # RGB(255, 202, 145)
IDX_FLESH_HIGH = 176    # RGB(242, 177, 125)
IDX_FLESH_MID = 126     # RGB(210, 149, 117)
IDX_FLESH_DARK = 122    # RGB(165, 97, 85)

# White fur trim / headwrap ramp
IDX_WHITE_PURE = 255    # RGB(255, 255, 255)
IDX_WHITE_SOFT = 252    # RGB(206, 206, 206)
IDX_WHITE_SHADE = 248   # RGB(137, 137, 137)
