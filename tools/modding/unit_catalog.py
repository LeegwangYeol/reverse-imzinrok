"""
tools.modding.unit_catalog
~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit, building, and hero catalog loader, query API, and CSV/JSON exporter.
Contains reverse-engineered definitions for all 111 game objects in Imjinrok 2+: Dawn.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Optional, Union


class UnitCatalog:
    """Catalog holding all reverse-engineered unit, hero, and building definitions."""

    def __init__(self, data_path: Optional[str] = None) -> None:
        if data_path is None:
            data_path = os.path.join(os.path.dirname(__file__), "dataset.json")
        self.data_path = os.path.abspath(data_path)
        if not os.path.isfile(self.data_path):
            raise FileNotFoundError(f"Unit catalog dataset not found: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            self._units: List[Dict[str, Any]] = json.load(f)

        # Index caches for fast O(1) lookup
        self._by_index: Dict[int, Dict[str, Any]] = {}
        self._by_name: Dict[str, Dict[str, Any]] = {}
        self._by_sprite_name: Dict[str, Dict[str, Any]] = {}

        for u in self._units:
            idx = u.get("index")
            if idx is not None:
                self._by_index[idx] = u
            kn = u.get("korean_name")
            if kn:
                self._by_name[kn.strip()] = u
            sn = u.get("sprite_name")
            if sn:
                self._by_sprite_name[sn.strip().upper()] = u

    def __len__(self) -> int:
        return len(self._units)

    def __iter__(self):
        return iter(self._units)

    def __getitem__(self, item: Union[int, str]) -> Dict[str, Any]:
        unit = self.get_unit(item)
        if unit is None:
            raise KeyError(f"Unit not found: {item}")
        return unit

    def get_unit(self, identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Look up a unit by index (int/str), Korean name, or sprite name."""
        if isinstance(identifier, int):
            return self._by_index.get(identifier)

        ident_str = str(identifier).strip()
        # Check if integer string
        if ident_str.isdigit():
            idx = int(ident_str)
            if idx in self._by_index:
                return self._by_index[idx]

        # Check exact Korean name
        if ident_str in self._by_name:
            return self._by_name[ident_str]

        # Check sprite name (case-insensitive)
        upper_ident = ident_str.upper()
        if upper_ident in self._by_sprite_name:
            return self._by_sprite_name[upper_ident]

        # Check substring match on Korean name
        for kn, u in self._by_name.items():
            if ident_str in kn:
                return u

        # Check substring match on sprite name
        for sn, u in self._by_sprite_name.items():
            if upper_ident in sn:
                return u

        return None

    def list_units(
        self,
        filter_patched: bool = False,
        faction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List units with optional filtering by patch status and faction.

        Factions: '조선', '일본', '명', or None for all.
        """
        results = []
        for u in self._units:
            if filter_patched and u.get("total_patches_in_unit", 0) <= 0:
                continue
            if faction:
                kn = u.get("korean_name", "")
                if not kn.startswith(faction):
                    continue
            results.append(u)
        return results

    def find_units(self, query: str) -> List[Dict[str, Any]]:
        """Search units matching query in Korean name or sprite name."""
        q = query.strip()
        q_upper = q.upper()
        matches = []
        for u in self._units:
            kn = u.get("korean_name", "")
            sn = u.get("sprite_name", "")
            if q in kn or q_upper in sn.upper():
                matches.append(u)
        return matches

    def get_stat(self, identifier: Union[int, str], stat_name: str) -> Any:
        """Retrieve a specific stat value for a given unit."""
        unit = self.get_unit(identifier)
        if unit is None:
            raise KeyError(f"Unit not found: {identifier}")

        stat = stat_name.lower().strip()
        if stat in ("speed", "move_speed", "base_speed"):
            return unit.get("speed_field", {}).get("dawn_val")
        if stat in ("hp", "max_hp", "health"):
            return unit.get("hp_field", {}).get("dawn_val")
        if stat in ("mp", "max_mp", "mana"):
            return unit.get("mp_field", {}).get("dawn_val")
        if stat in ("attack", "attack_power", "damage"):
            return unit.get("attack_field", {}).get("dawn_val")
        if stat in ("delay", "attack_delay", "attack_speed"):
            return unit.get("attack_delay", {}).get("dawn_val")
        if stat in ("range", "attack_range"):
            return unit.get("attack_range", {}).get("dawn_val")
        if stat in ("defense", "armor"):
            return unit.get("defense", {}).get("dawn_val")
        if stat in ("rice", "cost_rice"):
            return unit.get("cost", {}).get("rice", {}).get("dawn")
        if stat in ("potato", "cost_potato"):
            return unit.get("cost", {}).get("potato", {}).get("dawn")
        if stat in ("money", "gold", "cost_money"):
            return unit.get("cost", {}).get("money", {}).get("dawn")

        raise KeyError(f"Unknown stat field: '{stat_name}'")

    def get_diff_summary(self) -> List[Dict[str, Any]]:
        """Return all units that differ between UseMap (vanilla) and Dawn."""
        diffs = []
        for u in self._units:
            if u.get("total_patches_in_unit", 0) > 0:
                diff_entry = {
                    "index": u["index"],
                    "korean_name": u["korean_name"],
                    "sprite_name": u["sprite_name"],
                    "call_va": u["call_va"],
                    "total_patches": u["total_patches_in_unit"],
                    "speed_diff": (
                        f"{u['speed_field']['usemap_val']} -> {u['speed_field']['dawn_val']}"
                        if u["speed_field"]["patched"]
                        else None
                    ),
                    "hp_diff": (
                        f"{u['hp_field']['usemap_val']} -> {u['hp_field']['dawn_val']}"
                        if u["hp_field"]["patched"]
                        else None
                    ),
                    "mp_diff": (
                        f"{u['mp_field']['usemap_val']} -> {u['mp_field']['dawn_val']}"
                        if u["mp_field"]["patched"]
                        else None
                    ),
                    "attack_diff": (
                        f"{u['attack_field']['usemap_val']} -> {u['attack_field']['dawn_val']}"
                        if u["attack_field"]["patched"]
                        else None
                    ),
                    "delay_diff": (
                        f"{u['attack_delay']['usemap_val']} -> {u['attack_delay']['dawn_val']}"
                        if u["attack_delay"]["patched"]
                        else None
                    ),
                    "range_diff": (
                        f"{u['attack_range']['usemap_val']} -> {u['attack_range']['dawn_val']}"
                        if u["attack_range"]["patched"]
                        else None
                    ),
                    "defense_diff": (
                        f"{u['defense']['usemap_val']} -> {u['defense']['dawn_val']}"
                        if u["defense"]["patched"]
                        else None
                    ),
                    "cost_diff": (
                        f"Rice: {u['cost']['rice']['usemap']}->{u['cost']['rice']['dawn']}, "
                        f"Pot: {u['cost']['potato']['usemap']}->{u['cost']['potato']['dawn']}, "
                        f"Money: {u['cost']['money']['usemap']}->{u['cost']['money']['dawn']}"
                        if u["cost"]["patched"]
                        else None
                    ),
                }
                diffs.append(diff_entry)
        return diffs

    def export_to_json(self, output_path: str, indent: int = 2) -> None:
        """Export the full dataset to a formatted JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self._units, f, indent=indent, ensure_ascii=False)

    def export_to_csv(self, output_path: str) -> None:
        """Export the unit catalog to a clean UTF-8 CSV with Excel-compatible BOM."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fieldnames = [
            "index",
            "korean_name",
            "sprite_id",
            "sprite_name",
            "sprite_path",
            "call_va",
            "call_file_offset",
            "speed_dawn",
            "speed_usemap",
            "speed_patched",
            "hp_dawn",
            "hp_usemap",
            "hp_patched",
            "mp_dawn",
            "mp_usemap",
            "mp_patched",
            "attack_dawn",
            "attack_usemap",
            "attack_patched",
            "attack_delay_dawn",
            "attack_range_dawn",
            "defense_dawn",
            "cost_rice_dawn",
            "cost_potato_dawn",
            "cost_money_dawn",
            "cost_patched",
            "total_patches",
        ]

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for u in self._units:
                row = {
                    "index": u.get("index"),
                    "korean_name": u.get("korean_name"),
                    "sprite_id": u.get("sprite_id"),
                    "sprite_name": u.get("sprite_name"),
                    "sprite_path": u.get("sprite_path"),
                    "call_va": u.get("call_va"),
                    "call_file_offset": u.get("call_file_offset"),
                    "speed_dawn": u.get("speed_field", {}).get("dawn_val"),
                    "speed_usemap": u.get("speed_field", {}).get("usemap_val"),
                    "speed_patched": u.get("speed_field", {}).get("patched"),
                    "hp_dawn": u.get("hp_field", {}).get("dawn_val"),
                    "hp_usemap": u.get("hp_field", {}).get("usemap_val"),
                    "hp_patched": u.get("hp_field", {}).get("patched"),
                    "mp_dawn": u.get("mp_field", {}).get("dawn_val"),
                    "mp_usemap": u.get("mp_field", {}).get("usemap_val"),
                    "mp_patched": u.get("mp_field", {}).get("patched"),
                    "attack_dawn": u.get("attack_field", {}).get("dawn_val"),
                    "attack_usemap": u.get("attack_field", {}).get("usemap_val"),
                    "attack_patched": u.get("attack_field", {}).get("patched"),
                    "attack_delay_dawn": u.get("attack_delay", {}).get("dawn_val"),
                    "attack_range_dawn": u.get("attack_range", {}).get("dawn_val"),
                    "defense_dawn": u.get("defense", {}).get("dawn_val"),
                    "cost_rice_dawn": u.get("cost", {}).get("rice", {}).get("dawn"),
                    "cost_potato_dawn": u.get("cost", {}).get("potato", {}).get("dawn"),
                    "cost_money_dawn": u.get("cost", {}).get("money", {}).get("dawn"),
                    "cost_patched": u.get("cost", {}).get("patched"),
                    "total_patches": u.get("total_patches_in_unit", 0),
                }
                writer.writerow(row)


def load_unit_catalog(data_path: Optional[str] = None) -> UnitCatalog:
    """Convenience helper to instantiate and return a UnitCatalog."""
    return UnitCatalog(data_path)
