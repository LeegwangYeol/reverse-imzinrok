"""
tools.modding
~~~~~~~~~~~~~
Complete Imjinrok 2+: Dawn Unit, Building, and Skill Reverse Engineering & Binary Modding Tool.

Provides:
- UnitCatalog: query and explore all 111 units/buildings, stats, Korean names, and diffs.
- BinaryPatcher: safely patch movement speed, HP, MP, attack, range, delay, cost in Dawn binaries.
- CommandCardInjector: decode 6 Dawn code cave hooks and inject new buttons into available slack space.
- Exhaustive PE binary integrity verification guaranteeing PE headers and sections remain intact.
"""

from tools.modding.binary_patcher import (
    EXPECTED_BINARY_SIZE,
    IMAGE_BASE,
    BinaryPatcher,
    PatchResult,
    check_binary_integrity,
    modify_unit_stat,
    patch_movement_speed,
    verify_binary_integrity,
)
from tools.modding.command_card import (
    BUILDING_HOOK_PRESETS,
    DAWN_CAVE_END_VA,
    DAWN_CAVE_SIZE,
    DAWN_CAVE_START_VA,
    DAWN_HOOKS_METADATA,
    SLACK_END_VA,
    SLACK_START_VA,
    TOTAL_SLACK_BYTES,
    CommandCardInjector,
    decode_cave_hooks,
    inject_command_card_button,
)
from tools.modding.unit_catalog import (
    UnitCatalog,
    load_unit_catalog,
)

__version__ = "1.0.0"

__all__ = [
    # Catalog
    "UnitCatalog",
    "load_unit_catalog",
    # Patcher
    "BinaryPatcher",
    "PatchResult",
    "modify_unit_stat",
    "patch_movement_speed",
    "check_binary_integrity",
    "verify_binary_integrity",
    "EXPECTED_BINARY_SIZE",
    "IMAGE_BASE",
    # Command Card / Cave
    "CommandCardInjector",
    "inject_command_card_button",
    "decode_cave_hooks",
    "BUILDING_HOOK_PRESETS",
    "DAWN_HOOKS_METADATA",
    "DAWN_CAVE_START_VA",
    "DAWN_CAVE_END_VA",
    "DAWN_CAVE_SIZE",
    "SLACK_START_VA",
    "SLACK_END_VA",
    "TOTAL_SLACK_BYTES",
]
