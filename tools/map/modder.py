"""Imjinrok 2+ Dawn Map Modder.

Programmatic and fluent API for modifying Imjinrok 2+ .map files:
- Edit or shift player starting positions
- Add, remove, or modify resource nodes (potatoes, bamboo, trees, rice)
- Bulk adjust resource amounts (scaling, capping, multiplying)
- Modify terrain types (water, ground), walkability (passable, cliff), and elevation
- Add or remove pre-placed building blocks
- Change tileset theme (0..6)
- Guarantees saving back to a strictly valid 1,132,876-byte binary with pitch 180.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from tools.map.parser import (
    DEFAULT_RESOURCE_AMOUNTS,
    MAX_MAP_DIMENSION,
    MAX_PLAYERS,
    RESOURCE_NAMES,
    THEME_NAMES,
    MapData,
    MapFormatError,
    parse_map,
    save_map,
)


class MapModder:
    """Fluent API for programmatic modification of MapData."""

    def __init__(self, map_target: Union[MapData, str, Path, bytes, bytearray]):
        if isinstance(map_target, MapData):
            # Create an independent clone of the map data
            self.map_data = MapData(bytes(map_target.raw_data))
        else:
            self.map_data = parse_map(map_target)

    # Player Starting Positions
    def set_player_start(self, player_id: int, x: int, y: int) -> MapModder:
        """Sets starting coordinate for player_id (0..7)."""
        self.map_data.set_player_start(player_id, x, y)
        return self

    def clear_player_start(self, player_id: int) -> MapModder:
        """Disables player_id starting slot."""
        self.map_data.clear_player_start(player_id)
        return self

    # Theme
    def set_theme(self, theme: Union[int, str]) -> MapModder:
        """Changes the tileset theme."""
        self.map_data.set_theme(theme)
        return self

    # Resources
    def set_resource(
        self,
        x: int,
        y: int,
        type_id: int,
        amount: Optional[int] = None,
        variant: int = 0,
        state: int = 5,
    ) -> MapModder:
        """Places or overrides a resource cell."""
        self.map_data.set_resource(x, y, type_id, amount=amount, variant=variant, state=state)
        return self

    def set_resource_amount(self, x: int, y: int, amount: int) -> MapModder:
        """Modifies the quantity of an existing resource at (x, y)."""
        res = self.map_data.get_resource(x, y)
        if res is None:
            raise ValueError(f"No resource exists at ({x}, {y})")
        self.map_data.set_resource(
            x, y, res.type_id, amount=amount, variant=res.variant, state=res.state
        )
        return self

    def remove_resource(self, x: int, y: int) -> MapModder:
        """Clears any resource at (x, y)."""
        self.map_data.remove_resource(x, y)
        return self

    def set_all_resources_of_type(self, type_id: int, amount: int) -> MapModder:
        """Sets the amount of all resources matching type_id across the map."""
        amount_clamped = min(255, max(0, amount))
        for res in self.map_data.get_all_resources():
            if res.type_id == type_id:
                self.map_data.set_resource(
                    res.x,
                    res.y,
                    res.type_id,
                    amount=amount_clamped,
                    variant=res.variant,
                    state=res.state,
                )
        return self

    def scale_resources(
        self, factor: float, type_id: Optional[int] = None
    ) -> MapModder:
        """Multiplies resource amounts by a factor, clamping between 1 and 255."""
        for res in self.map_data.get_all_resources():
            if type_id is None or res.type_id == type_id:
                new_amt = min(255, max(1, int(round(res.amount * factor))))
                self.map_data.set_resource(
                    res.x,
                    res.y,
                    res.type_id,
                    amount=new_amt,
                    variant=res.variant,
                    state=res.state,
                )
        return self

    # Terrain, Walkability, Elevation
    def set_terrain_cell(
        self,
        x: int,
        y: int,
        terrain_type: Optional[int] = None,
        walkability: Optional[int] = None,
        elevation: Optional[int] = None,
        water_depth: Optional[int] = None,
    ) -> MapModder:
        """Modifies attributes of a specific cell."""
        if terrain_type is not None:
            self.map_data.set_terrain_type(x, y, terrain_type)
        if walkability is not None:
            self.map_data.set_walkability(x, y, walkability)
        if elevation is not None:
            self.map_data.set_elevation(x, y, elevation)
        if water_depth is not None:
            self.map_data.set_water_depth(x, y, water_depth)
        return self

    def fill_terrain_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        terrain_type: Optional[int] = None,
        walkability: Optional[int] = None,
        elevation: Optional[int] = None,
    ) -> MapModder:
        """Applies terrain modifications to an inclusive rectangular area [x1..x2, y1..y2]."""
        min_x, max_x = max(0, min(x1, x2)), min(self.map_data.width - 1, max(x1, x2))
        min_y, max_y = max(0, min(y1, y2)), min(self.map_data.height - 1, max(y1, y2))
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                self.set_terrain_cell(
                    x, y, terrain_type=terrain_type, walkability=walkability, elevation=elevation
                )
        return self

    # Buildings
    def set_building(
        self, x: int, y: int, building_id: int, owner_id: int = 0, state: int = 0
    ) -> MapModder:
        """Places a building block at (x, y)."""
        self.map_data.set_building(x, y, building_id, owner_id=owner_id, state=state)
        return self

    def remove_building(self, x: int, y: int) -> MapModder:
        """Removes a pre-placed building block at (x, y)."""
        self.map_data.remove_building(x, y)
        return self

    # Batch Modification
    def apply_modifications(self, modifications: Dict[str, Any]) -> MapModder:
        """Applies a dictionary of structured modifications.

        Supported keys:
            theme: int or str
            player_starts: list of dicts [{"player_id": int, "x": int, "y": int}] or dict {pid: [x, y]}
            clear_player_starts: list of player_ids
            resources:
                set: list of dicts [{"x": int, "y": int, "type_id": int, "amount": int, ...}]
                remove: list of [x, y] coordinates
                set_type_amount: dict of {type_id: amount}
                scale: float or dict of {type_id: factor}
            terrain:
                cells: list of dicts [{"x": int, "y": int, "type": int, "walkability": int, "elevation": int}]
                rects: list of dicts [{"rect": [x1, y1, x2, y2], "type": int, "walkability": int, "elevation": int}]
            buildings:
                set: list of dicts [{"x": int, "y": int, "building_id": int, "owner_id": int}]
                remove: list of [x, y] coordinates
        """
        # Theme
        if "theme" in modifications:
            self.set_theme(modifications["theme"])

        # Player starts
        if "player_starts" in modifications:
            pstarts = modifications["player_starts"]
            if isinstance(pstarts, dict):
                for pid, coords in pstarts.items():
                    self.set_player_start(int(pid), int(coords[0]), int(coords[1]))
            elif isinstance(pstarts, list):
                for ps in pstarts:
                    self.set_player_start(int(ps["player_id"]), int(ps["x"]), int(ps["y"]))

        if "clear_player_starts" in modifications:
            for pid in modifications["clear_player_starts"]:
                self.clear_player_start(int(pid))

        # Resources
        if "resources" in modifications:
            res_ops = modifications["resources"]
            if "set" in res_ops:
                for r in res_ops["set"]:
                    self.set_resource(
                        x=int(r["x"]),
                        y=int(r["y"]),
                        type_id=int(r["type_id"]),
                        amount=r.get("amount"),
                        variant=r.get("variant", 0),
                        state=r.get("state", 5),
                    )
            if "remove" in res_ops:
                for coords in res_ops["remove"]:
                    self.remove_resource(int(coords[0]), int(coords[1]))
            if "set_type_amount" in res_ops:
                for tid, amt in res_ops["set_type_amount"].items():
                    self.set_all_resources_of_type(int(tid), int(amt))
            if "scale" in res_ops:
                scale_val = res_ops["scale"]
                if isinstance(scale_val, (int, float)):
                    self.scale_resources(float(scale_val))
                elif isinstance(scale_val, dict):
                    for tid, factor in scale_val.items():
                        self.scale_resources(float(factor), type_id=int(tid))

        # Terrain
        if "terrain" in modifications:
            t_ops = modifications["terrain"]
            if "cells" in t_ops:
                for c in t_ops["cells"]:
                    self.set_terrain_cell(
                        x=int(c["x"]),
                        y=int(c["y"]),
                        terrain_type=c.get("type"),
                        walkability=c.get("walkability"),
                        elevation=c.get("elevation"),
                    )
            if "rects" in t_ops:
                for r in t_ops["rects"]:
                    coords = r["rect"]
                    self.fill_terrain_rect(
                        x1=int(coords[0]),
                        y1=int(coords[1]),
                        x2=int(coords[2]),
                        y2=int(coords[3]),
                        terrain_type=r.get("type"),
                        walkability=r.get("walkability"),
                        elevation=r.get("elevation"),
                    )

        # Buildings
        if "buildings" in modifications:
            b_ops = modifications["buildings"]
            if "set" in b_ops:
                for b in b_ops["set"]:
                    self.set_building(
                        x=int(b["x"]),
                        y=int(b["y"]),
                        building_id=int(b["building_id"]),
                        owner_id=int(b.get("owner_id", 0)),
                        state=int(b.get("state", 0)),
                    )
            if "remove" in b_ops:
                for coords in b_ops["remove"]:
                    self.remove_building(int(coords[0]), int(coords[1]))

        return self

    def save(self, output_path: Union[str, Path]) -> bool:
        """Saves the modified map data to an exact 1,132,876-byte file."""
        return self.map_data.save(output_path)


def modify_map(
    map_data: Union[MapData, str, Path], modifications: Dict[str, Any]
) -> MapData:
    """Modifies a MapData instance according to a modification dictionary.

    Matches interface contract:
    modify_map(map_data, modifications) -> MapData

    Args:
        map_data: MapData object or path to .map file.
        modifications: Dictionary describing operations to apply.

    Returns:
        New modified MapData instance.
    """
    modder = MapModder(map_data)
    modder.apply_modifications(modifications)
    return modder.map_data
