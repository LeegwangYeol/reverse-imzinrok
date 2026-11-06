"""Imjinrok 2+ Dawn .map Binary Parser.

Parses the fixed-size 1,132,876-byte (0x11494C) .map binary files used by
Imjinrok 2+ Chosun's Counterattack: Dawn (임진록 2+ 조선의 반격: 여명).

Format Architecture:
- Fixed file size: Exactly 1,132,876 bytes across all maps (70x70 up to 180x180).
- Memory dump of the engine's CMap singleton (0x00b3dda8) at max dimension 180x180.
- Fixed 2D array row stride (pitch) = 180.
- Out-of-bounds area [width..180, height..180] is zero-padded.
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Exact fixed size expected by the engine
MAP_FILE_SIZE = 1_132_876  # 0x11494C bytes
MAX_MAP_DIMENSION = 180
MAX_PLAYERS = 8

# Binary File Offsets
OFFSET_VERSION = 0x000000
OFFSET_NUM_PLAYERS = 0x000088
OFFSET_WIDTH = 0x00008C
OFFSET_HEIGHT = 0x00008E
OFFSET_THEME_ID = 0x000090
OFFSET_MAP_MODE = 0x0000B0
OFFSET_PLAYER_STARTS = 0x0000B4  # 8 slots * 8 bytes (x: uint32, y: uint32)
OFFSET_PLAYER_CONFIGS = 0x0000F4  # 8 slots * 6 bytes

# 180x180 Tile Layers (uint16, 64,800 bytes each)
OFFSET_TILE_LAYER_1 = 0x003AE4  # Lower terrain tile sprite index
OFFSET_TILE_LAYER_2 = 0x013804  # Middle terrain tile sprite index
OFFSET_TILE_LAYER_3 = 0x023524  # Main terrain tile block ID

# 180x180 Byte Grids (uint8, 32,400 bytes each)
OFFSET_BYTE_GRID_0 = 0x033244  # Terrain type (1=water/river, 2=ground/plain)
OFFSET_BYTE_GRID_1 = 0x03B0D4  # Walkability (0=passable, 1..32=obstacle/cliff)
OFFSET_BYTE_GRID_2 = 0x042F64  # Elevation / height level (0..5)
OFFSET_BYTE_GRID_3 = 0x04ADF4  # Water depth / shoreline transition
OFFSET_BYTE_GRID_4_0 = 0x052C84  # Vision / fog of war mask

# 180x180 Building Grids (uint8, 32,400 bytes each)
OFFSET_BUILDING_ID = 0x0B5A8C  # Pre-placed building part / block ID
OFFSET_BUILDING_OWNER = 0x0BD91C  # Building owner player ID (0..7, 2=neutral)
OFFSET_BUILDING_STATE = 0x0C57AC  # Building state / flags

# 180x180 Resource Grids (uint8, 32,400 bytes each)
OFFSET_RESOURCE_TYPE = 0x0CD63C  # Resource type (1=potato, 2=bamboo, 3=tree, 100=rice, etc.)
OFFSET_RESOURCE_VARIANT = 0x0D54CC  # Sprite variant ID
OFFSET_RESOURCE_AMOUNT = 0x0DD35C  # Resource quantity / amount
OFFSET_RESOURCE_STATE = 0x0E51EC  # Resource state / respawn cycle (default 5)

# Theme Mapping (from Map Editor.exe 0x00418ccc jump table)
THEME_NAMES = {
    0: "normal",  # tile\normal\ (temperate plain)
    1: "snow",  # tile\snow\ (snowfield / ice)
    2: "brown",  # tile\brown\ (wasteland / clay)
    3: "green",  # tile\green\ (dense grassland / jungle)
    4: "dark",  # tile\dark\ (rocky night battlefield)
    5: "volcano",  # tile\volcano\ (volcano rock)
    6: "bright",  # tile\bright\ (desert / coastal beach)
}

THEME_IDS = {name: tid for tid, name in THEME_NAMES.items()}

# Resource Mapping
RESOURCE_NAMES = {
    1: "potato",  # Potato patch (식량 / 감자밭)
    2: "bamboo",  # Bamboo (목재 / 대나무)
    3: "tree",  # Wood / Tree (주 목재 / 나무)
    100: "rice",  # Rice field (식량 / 벼/논)
    6: "landmark_rock",
    7: "landmark_shrine",
    8: "landmark_ruins",
    9: "landmark_stone",
    10: "landmark_grave",
    11: "landmark_gate",
    30: "neutral_castle_gate",
    50: "neutral_building",
    61: "neutral_relic",
}

DEFAULT_RESOURCE_AMOUNTS = {
    1: 70,  # Potato
    2: 25,  # Bamboo
    3: 170,  # Tree
    100: 40,  # Rice
}


class MapFormatError(Exception):
    """Raised when a .map file fails format or integrity validation."""


@dataclass
class PlayerStart:
    """Represents a player starting position."""

    player_id: int
    x: int
    y: int
    is_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceNode:
    """Represents a single placed resource cell."""

    x: int
    y: int
    type_id: int
    type_name: str
    variant: int
    amount: int
    state: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BuildingNode:
    """Represents a pre-placed building or block."""

    x: int
    y: int
    building_id: int
    owner_id: int
    state: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MapData:
    """In-memory representation of an Imjinrok 2+ Dawn .map file.

    Maintains the full 1,132,876-byte buffer to guarantee 100% bit-exact
    preservation of untouched structures, tables, and padding during round-trips.
    """

    def __init__(self, raw_bytes: Union[bytes, bytearray]):
        if len(raw_bytes) != MAP_FILE_SIZE:
            raise MapFormatError(
                f"Invalid .map file size: expected {MAP_FILE_SIZE} bytes, got {len(raw_bytes)} bytes."
            )
        self.raw_data = bytearray(raw_bytes)
        self._unpack_header()

    def _unpack_header(self) -> None:
        """Parses the fixed header values."""
        self.version = struct.unpack_from("<I", self.raw_data, OFFSET_VERSION)[0]
        self.num_players = struct.unpack_from("<I", self.raw_data, OFFSET_NUM_PLAYERS)[0]
        self.width, self.height = struct.unpack_from("<HH", self.raw_data, OFFSET_WIDTH)
        self.theme_id = struct.unpack_from("<I", self.raw_data, OFFSET_THEME_ID)[0]
        self.map_mode = struct.unpack_from("<I", self.raw_data, OFFSET_MAP_MODE)[0]

        if not (70 <= self.width <= MAX_MAP_DIMENSION and 70 <= self.height <= MAX_MAP_DIMENSION):
            raise MapFormatError(
                f"Map dimensions out of supported range (70..180): {self.width}x{self.height}"
            )
        if not (1 <= self.num_players <= MAX_PLAYERS):
            raise MapFormatError(
                f"Number of players out of supported range (1..8): {self.num_players}"
            )

    @property
    def theme_name(self) -> str:
        return THEME_NAMES.get(self.theme_id, f"unknown_{self.theme_id}")

    # Coordinate indexing helpers
    def _validate_coords(self, x: int, y: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(
                f"Coordinate ({x}, {y}) out of map bounds ({self.width}x{self.height})"
            )

    def _cell_offset_8(self, layer_base: int, x: int, y: int) -> int:
        return layer_base + (y * MAX_MAP_DIMENSION + x)

    def _cell_offset_16(self, layer_base: int, x: int, y: int) -> int:
        return layer_base + (y * MAX_MAP_DIMENSION + x) * 2

    # Player start locations
    def get_player_starts(self) -> List[PlayerStart]:
        """Returns all 8 player start slot entries."""
        starts: List[PlayerStart] = []
        for i in range(MAX_PLAYERS):
            offset = OFFSET_PLAYER_STARTS + i * 8
            px, py = struct.unpack_from("<II", self.raw_data, offset)
            active = px != 0xFFFFFFFF and py != 0xFFFFFFFF and px < self.width and py < self.height
            starts.append(PlayerStart(player_id=i, x=px, y=py, is_active=active))
        return starts

    def get_active_player_starts(self) -> List[PlayerStart]:
        """Returns only active player start locations."""
        return [ps for ps in self.get_player_starts() if ps.is_active]

    def set_player_start(self, player_id: int, x: int, y: int) -> None:
        """Sets the starting position for a player slot (0..7)."""
        if not (0 <= player_id < MAX_PLAYERS):
            raise ValueError(f"Player ID must be 0..{MAX_PLAYERS - 1}, got {player_id}")
        self._validate_coords(x, y)
        offset = OFFSET_PLAYER_STARTS + player_id * 8
        struct.pack_into("<II", self.raw_data, offset, x, y)

    def clear_player_start(self, player_id: int) -> None:
        """Deactivates a player starting slot."""
        if not (0 <= player_id < MAX_PLAYERS):
            raise ValueError(f"Player ID must be 0..{MAX_PLAYERS - 1}, got {player_id}")
        offset = OFFSET_PLAYER_STARTS + player_id * 8
        struct.pack_into("<II", self.raw_data, offset, 0xFFFFFFFF, 0xFFFFFFFF)

    # Theme and Header modification
    def set_theme(self, theme: Union[int, str]) -> None:
        """Changes the map theme ID."""
        if isinstance(theme, str):
            if theme not in THEME_IDS:
                raise ValueError(
                    f"Unknown theme name '{theme}'. Valid: {list(THEME_IDS.keys())}"
                )
            tid = THEME_IDS[theme]
        else:
            if theme not in THEME_NAMES:
                raise ValueError(f"Unknown theme ID {theme}. Valid: {list(THEME_NAMES.keys())}")
            tid = theme
        self.theme_id = tid
        struct.pack_into("<I", self.raw_data, OFFSET_THEME_ID, tid)

    # Terrain Layer Accessors
    def get_terrain_type(self, x: int, y: int) -> int:
        """ByteGrid 0: 1=water, 2=ground."""
        self._validate_coords(x, y)
        return self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_0, x, y)]

    def set_terrain_type(self, x: int, y: int, val: int) -> None:
        self._validate_coords(x, y)
        if val not in (1, 2):
            raise ValueError(f"Terrain type must be 1 (water) or 2 (ground), got {val}")
        self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_0, x, y)] = val

    def get_walkability(self, x: int, y: int) -> int:
        """ByteGrid 1: 0=walkable/passable, !=0 cliff/obstacle."""
        self._validate_coords(x, y)
        return self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_1, x, y)]

    def set_walkability(self, x: int, y: int, val: int) -> None:
        self._validate_coords(x, y)
        self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_1, x, y)] = val & 0xFF

    def get_elevation(self, x: int, y: int) -> int:
        """ByteGrid 2: Elevation level (0..5)."""
        self._validate_coords(x, y)
        return self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_2, x, y)]

    def set_elevation(self, x: int, y: int, val: int) -> None:
        self._validate_coords(x, y)
        self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_2, x, y)] = val & 0xFF

    def get_water_depth(self, x: int, y: int) -> int:
        """ByteGrid 3: Water depth / shoreline."""
        self._validate_coords(x, y)
        return self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_3, x, y)]

    def set_water_depth(self, x: int, y: int, val: int) -> None:
        self._validate_coords(x, y)
        self.raw_data[self._cell_offset_8(OFFSET_BYTE_GRID_3, x, y)] = val & 0xFF

    def get_tile(self, layer: int, x: int, y: int) -> int:
        """Retrieves tile sprite/block index from TileLayer 1, 2, or 3."""
        self._validate_coords(x, y)
        if layer == 1:
            base = OFFSET_TILE_LAYER_1
        elif layer == 2:
            base = OFFSET_TILE_LAYER_2
        elif layer == 3:
            base = OFFSET_TILE_LAYER_3
        else:
            raise ValueError(f"Layer must be 1, 2, or 3, got {layer}")
        return struct.unpack_from("<H", self.raw_data, self._cell_offset_16(base, x, y))[0]

    def set_tile(self, layer: int, x: int, y: int, tile_id: int) -> None:
        self._validate_coords(x, y)
        if layer == 1:
            base = OFFSET_TILE_LAYER_1
        elif layer == 2:
            base = OFFSET_TILE_LAYER_2
        elif layer == 3:
            base = OFFSET_TILE_LAYER_3
        else:
            raise ValueError(f"Layer must be 1, 2, or 3, got {layer}")
        struct.pack_into("<H", self.raw_data, self._cell_offset_16(base, x, y), tile_id & 0xFFFF)

    # Resource Layer Accessors
    def get_resource(self, x: int, y: int) -> Optional[ResourceNode]:
        """Gets resource node at (x, y) if present, or None."""
        self._validate_coords(x, y)
        off_t = self._cell_offset_8(OFFSET_RESOURCE_TYPE, x, y)
        rtype = self.raw_data[off_t]
        if rtype == 0:
            return None
        rvar = self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_VARIANT, x, y)]
        ramt = self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_AMOUNT, x, y)]
        rst = self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_STATE, x, y)]
        rname = RESOURCE_NAMES.get(rtype, f"unknown_resource_{rtype}")
        return ResourceNode(
            x=x, y=y, type_id=rtype, type_name=rname, variant=rvar, amount=ramt, state=rst
        )

    def set_resource(
        self,
        x: int,
        y: int,
        type_id: int,
        amount: Optional[int] = None,
        variant: int = 0,
        state: int = 5,
    ) -> None:
        """Places or updates a resource at (x, y)."""
        self._validate_coords(x, y)
        if amount is None:
            amount = DEFAULT_RESOURCE_AMOUNTS.get(type_id, 100)
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_TYPE, x, y)] = type_id & 0xFF
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_VARIANT, x, y)] = variant & 0xFF
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_AMOUNT, x, y)] = min(255, max(0, amount))
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_STATE, x, y)] = state & 0xFF

    def remove_resource(self, x: int, y: int) -> None:
        """Clears resource at (x, y)."""
        self._validate_coords(x, y)
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_TYPE, x, y)] = 0
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_VARIANT, x, y)] = 0
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_AMOUNT, x, y)] = 0
        self.raw_data[self._cell_offset_8(OFFSET_RESOURCE_STATE, x, y)] = 0

    def get_all_resources(self) -> List[ResourceNode]:
        """Returns all placed resource nodes within map bounds."""
        nodes: List[ResourceNode] = []
        for y in range(self.height):
            for x in range(self.width):
                res = self.get_resource(x, y)
                if res is not None:
                    nodes.append(res)
        return nodes

    def resource_summary(self) -> Dict[str, Dict[str, int]]:
        """Summarizes resource counts and total quantities by type."""
        summary: Dict[str, Dict[str, int]] = {}
        for res in self.get_all_resources():
            name = res.type_name
            if name not in summary:
                summary[name] = {"count": 0, "total_amount": 0, "type_id": res.type_id}
            summary[name]["count"] += 1
            summary[name]["total_amount"] += res.amount
        return summary

    # Pre-placed Building Accessors
    def get_building(self, x: int, y: int) -> Optional[BuildingNode]:
        """Gets pre-placed building part at (x, y) if present, or None."""
        self._validate_coords(x, y)
        bid = self.raw_data[self._cell_offset_8(OFFSET_BUILDING_ID, x, y)]
        if bid == 0:
            return None
        owner = self.raw_data[self._cell_offset_8(OFFSET_BUILDING_OWNER, x, y)]
        st = self.raw_data[self._cell_offset_8(OFFSET_BUILDING_STATE, x, y)]
        return BuildingNode(x=x, y=y, building_id=bid, owner_id=owner, state=st)

    def set_building(
        self, x: int, y: int, building_id: int, owner_id: int = 0, state: int = 0
    ) -> None:
        """Places a building part at (x, y)."""
        self._validate_coords(x, y)
        self.raw_data[self._cell_offset_8(OFFSET_BUILDING_ID, x, y)] = building_id & 0xFF
        self.raw_data[self._cell_offset_8(OFFSET_BUILDING_OWNER, x, y)] = owner_id & 0xFF
        self.raw_data[self._cell_offset_8(OFFSET_BUILDING_STATE, x, y)] = state & 0xFF

    def remove_building(self, x: int, y: int) -> None:
        """Clears pre-placed building at (x, y)."""
        self._validate_coords(x, y)
        self.raw_data[self._cell_offset_8(OFFSET_BUILDING_ID, x, y)] = 0
        self.raw_data[self._cell_offset_8(OFFSET_BUILDING_OWNER, x, y)] = 0
        self.raw_data[self._cell_offset_8(OFFSET_BUILDING_STATE, x, y)] = 0

    def get_all_buildings(self) -> List[BuildingNode]:
        """Returns all pre-placed building blocks within map bounds."""
        buildings: List[BuildingNode] = []
        for y in range(self.height):
            for x in range(self.width):
                b = self.get_building(x, y)
                if b is not None:
                    buildings.append(b)
        return buildings

    # Serialization and Export
    def to_dict(self, include_grids: bool = False) -> Dict[str, Any]:
        """Converts map metadata and summaries to a dictionary."""
        data: Dict[str, Any] = {
            "version": self.version,
            "num_players": self.num_players,
            "width": self.width,
            "height": self.height,
            "theme_id": self.theme_id,
            "theme_name": self.theme_name,
            "map_mode": self.map_mode,
            "file_size": len(self.raw_data),
            "player_starts": [ps.to_dict() for ps in self.get_active_player_starts()],
            "resource_summary": self.resource_summary(),
            "total_resources": len(self.get_all_resources()),
            "total_buildings": len(self.get_all_buildings()),
        }
        if include_grids:
            data["resources"] = [r.to_dict() for r in self.get_all_resources()]
            data["buildings"] = [b.to_dict() for b in self.get_all_buildings()]
        return data

    def to_json(self, indent: int = 2, include_grids: bool = False) -> str:
        """Serializes map metadata to JSON."""
        return json.dumps(self.to_dict(include_grids=include_grids), indent=indent)

    def save(self, output_path: Union[str, Path]) -> bool:
        """Saves the exact 1,132,876-byte buffer to file."""
        if len(self.raw_data) != MAP_FILE_SIZE:
            raise MapFormatError(
                f"Cannot save corrupted map: size is {len(self.raw_data)}, expected {MAP_FILE_SIZE}"
            )
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.raw_data)
        return True


def parse_map(map_path_or_bytes: Union[str, Path, bytes, bytearray]) -> MapData:
    """Parses a 1,132,876-byte .map file or byte buffer into a MapData object.

    Args:
        map_path_or_bytes: Path to .map file or in-memory byte buffer.

    Returns:
        MapData instance.
    """
    if isinstance(map_path_or_bytes, (bytes, bytearray)):
        return MapData(map_path_or_bytes)
    path = Path(map_path_or_bytes)
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")
    with open(path, "rb") as f:
        data = f.read()
    return MapData(data)


def save_map(map_data: MapData, output_path: Union[str, Path]) -> bool:
    """Saves a MapData instance to an exact 1,132,876-byte .map file.

    Args:
        map_data: The MapData instance to save.
        output_path: Destination file path.

    Returns:
        True on success.
    """
    return map_data.save(output_path)
