"""Imjinrok 2+ Dawn Map Infrastructure Package.

Provides complete parsing, 2D minimap rendering, and programmatic modification
tools for Imjinrok 2+ Dawn 1,132,876-byte fixed-size .map binary files.
"""

from tools.map.modder import MapModder, modify_map
from tools.map.parser import (
    DEFAULT_RESOURCE_AMOUNTS,
    MAP_FILE_SIZE,
    MAX_MAP_DIMENSION,
    MAX_PLAYERS,
    RESOURCE_NAMES,
    THEME_IDS,
    THEME_NAMES,
    BuildingNode,
    MapData,
    MapFormatError,
    PlayerStart,
    ResourceNode,
    parse_map,
    save_map,
)
from tools.map.renderer import render_minimap, render_minimap_image

__all__ = [
    "MAP_FILE_SIZE",
    "MAX_MAP_DIMENSION",
    "MAX_PLAYERS",
    "THEME_NAMES",
    "THEME_IDS",
    "RESOURCE_NAMES",
    "DEFAULT_RESOURCE_AMOUNTS",
    "MapFormatError",
    "PlayerStart",
    "ResourceNode",
    "BuildingNode",
    "MapData",
    "parse_map",
    "save_map",
    "render_minimap",
    "render_minimap_image",
    "MapModder",
    "modify_map",
]
