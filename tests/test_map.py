"""
Test Suite for R3: .map Binary Parser, Minimap Preview Renderer, and Map Modder
Imjinrok 2+ Dawn Modding Toolkit
"""

import os
import unittest
from pathlib import Path
from PIL import Image

from tests.conftest import (
    CUSMAP_DIR,
    ORIGINAL_MAP_SIZE,
    get_temp_dir,
    clone_map_file,
)
from tools.map.parser import (
    MapData,
    MapFormatError,
    parse_map,
    save_map,
    THEME_NAMES,
    MAX_MAP_DIMENSION,
    MAX_PLAYERS,
)
from tools.map.renderer import (
    render_minimap,
    render_minimap_image,
)


class TestMapParser(unittest.TestCase):
    """Tier 1 & Tier 2: Unit tests for .map binary parser."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("map_parser_test_")
        cls.sample_maps = list(CUSMAP_DIR.glob("*.map"))
        if not cls.sample_maps:
            raise FileNotFoundError(f"No .map files found in {CUSMAP_DIR}")
        cls.first_map = cls.sample_maps[0]

    def test_map_file_size(self):
        """Verify the sample map has exactly 1,132,876 bytes."""
        self.assertEqual(
            self.first_map.stat().st_size,
            ORIGINAL_MAP_SIZE,
            f"Map file size mismatch for {self.first_map.name}",
        )

    def test_parse_header_fields(self):
        """Verify header extraction: version, player count, width, height, theme ID."""
        map_data = parse_map(self.first_map)
        self.assertEqual(map_data.version, 1, "Expected map version == 1")
        self.assertIn(
            map_data.num_players,
            range(1, 9),
            f"Player count {map_data.num_players} out of valid range (1..8)",
        )
        self.assertTrue(
            70 <= map_data.width <= MAX_MAP_DIMENSION,
            f"Map width {map_data.width} out of range (70..180)",
        )
        self.assertTrue(
            70 <= map_data.height <= MAX_MAP_DIMENSION,
            f"Map height {map_data.height} out of range (70..180)",
        )
        self.assertIn(
            map_data.theme_id,
            range(0, 7),
            f"Theme ID {map_data.theme_id} out of range (0..6)",
        )
        self.assertIn(map_data.theme_name, THEME_NAMES.values())

    def test_player_start_locations(self):
        """Verify parsing of 8 player start coordinate slots."""
        map_data = parse_map(self.first_map)
        starts = map_data.get_player_starts()
        self.assertEqual(len(starts), MAX_PLAYERS)

        active_starts = map_data.get_active_player_starts()
        self.assertGreaterEqual(
            len(active_starts),
            map_data.num_players,
            "Active start count must be >= configured player count",
        )
        for ps in active_starts:
            self.assertTrue(ps.is_active)
            self.assertTrue(0 <= ps.x < map_data.width, f"Player {ps.player_id} x={ps.x} out of bounds")
            self.assertTrue(0 <= ps.y < map_data.height, f"Player {ps.player_id} y={ps.y} out of bounds")

    def test_fixed_pitch_180_tile_and_byte_layers(self):
        """Verify 180 pitch layout across tile layers and byte grids."""
        map_data = parse_map(self.first_map)
        # Check boundary cells
        w, h = map_data.width, map_data.height
        # Cell inside bounds should not raise IndexError
        t0 = map_data.get_terrain_type(0, 0)
        t_corner = map_data.get_terrain_type(w - 1, h - 1)
        self.assertIn(t0, [1, 2])
        self.assertIn(t_corner, [1, 2])

        # Walkability, elevation, and tile layers
        walk = map_data.get_walkability(0, 0)
        elev = map_data.get_elevation(0, 0)
        tile1 = map_data.get_tile(1, 0, 0)
        tile2 = map_data.get_tile(2, 0, 0)
        tile3 = map_data.get_tile(3, 0, 0)
        self.assertIsInstance(walk, int)
        self.assertIsInstance(elev, int)
        self.assertIsInstance(tile1, int)
        self.assertIsInstance(tile2, int)
        self.assertIsInstance(tile3, int)

    def test_resource_and_building_grids(self):
        """Verify extraction of resource nodes and placed buildings."""
        map_data = parse_map(self.first_map)
        resources = map_data.get_all_resources()
        self.assertIsInstance(resources, list)
        self.assertGreater(len(resources), 0, "Expected at least 1 resource node on map")

        summary = map_data.resource_summary()
        self.assertIsInstance(summary, dict)
        total_count = sum(item["count"] for item in summary.values())
        self.assertGreater(total_count, 0)

        first_res = resources[0]
        self.assertTrue(0 <= first_res.x < map_data.width)
        self.assertTrue(0 <= first_res.y < map_data.height)
        self.assertGreater(first_res.amount, 0)

    def test_invalid_map_size_rejection(self):
        """Tier 2: Corrupted or truncated map buffer must raise MapFormatError."""
        bad_buffer = b"\x00" * 1000
        with self.assertRaises(MapFormatError):
            parse_map(bad_buffer)

        bad_oversized = b"\x00" * (ORIGINAL_MAP_SIZE + 10)
        with self.assertRaises(MapFormatError):
            parse_map(bad_oversized)

    def test_out_of_bounds_coordinate_access(self):
        """Tier 2: Accessing coordinates beyond map bounds raises IndexError."""
        map_data = parse_map(self.first_map)
        with self.assertRaises(IndexError):
            map_data.get_terrain_type(map_data.width + 5, 0)
        with self.assertRaises(IndexError):
            map_data.get_terrain_type(0, map_data.height + 5)
        with self.assertRaises(IndexError):
            map_data.get_terrain_type(-1, 0)


class TestMinimapRenderer(unittest.TestCase):
    """Tier 1 & Tier 4: Minimap Preview Renderer Tests."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("minimap_test_")
        cls.test_maps = sorted(list(CUSMAP_DIR.glob("*.map")))[:5]
        if len(cls.test_maps) < 5:
            raise FileNotFoundError(f"Expected at least 5 .map files in {CUSMAP_DIR}")

    def test_render_single_minimap(self):
        """Render a 400x400 minimap PNG and verify image properties."""
        map_data = parse_map(self.test_maps[0])
        out_png = self.temp_dir / "preview_single.png"
        res = render_minimap(map_data, out_png, width=400, height=400)
        self.assertTrue(res)
        self.assertTrue(out_png.exists())

        # Verify with PIL
        with Image.open(out_png) as img:
            self.assertEqual(img.size, (400, 400))
            self.assertEqual(img.mode, "RGB")
            # Verify image is not blank/monochrome
            extrema = img.getextrema()
            for ch_min, ch_max in extrema:
                self.assertGreater(ch_max - ch_min, 20, "Minimap appears to be a blank or flat color")

    def test_batch_render_5_maps(self):
        """Tier 4: Render minimaps across at least 5 distinct custom maps."""
        for idx, map_path in enumerate(self.test_maps):
            out_png = self.temp_dir / f"minimap_{idx}_{map_path.stem}.png"
            res = render_minimap(map_path, out_png, width=300, height=300)
            self.assertTrue(res, f"Failed to render minimap for {map_path.name}")
            self.assertTrue(out_png.exists())
            self.assertGreater(out_png.stat().st_size, 1000, f"Rendered PNG too small for {map_path.name}")

            with Image.open(out_png) as img:
                self.assertEqual(img.size, (300, 300))


class TestMapModderRoundtrip(unittest.TestCase):
    """Tier 1, Tier 3 & Tier 4: Map modification and bit-exact size roundtrip."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("map_mod_test_")
        cls.source_map = sorted(list(CUSMAP_DIR.glob("*.map")))[0]

    def test_modify_starting_positions_and_save(self):
        """Modify player start location, save, re-read and assert exact 1,132,876 bytes."""
        cloned_map = clone_map_file(self.source_map, self.temp_dir)
        map_data = parse_map(cloned_map)

        # Modify player 0 start coordinate
        orig_starts = map_data.get_active_player_starts()
        target_player = orig_starts[0].player_id
        new_x = 25
        new_y = 35
        map_data.set_player_start(target_player, new_x, new_y)

        # Save to output file
        saved_path = self.temp_dir / "modified_start.map"
        success = save_map(map_data, saved_path)
        self.assertTrue(success)

        # Verify exact file size
        self.assertEqual(
            saved_path.stat().st_size,
            ORIGINAL_MAP_SIZE,
            "Modified .map file size must be exactly 1,132,876 bytes",
        )

        # Re-read and verify modified value persisted
        re_parsed = parse_map(saved_path)
        p0_start = [ps for ps in re_parsed.get_player_starts() if ps.player_id == target_player][0]
        self.assertEqual(p0_start.x, new_x)
        self.assertEqual(p0_start.y, new_y)
        self.assertTrue(p0_start.is_active)

    def test_modify_resources_and_terrain(self):
        """Modify resource node and terrain grid, save, and verify persistence."""
        cloned_map = clone_map_file(self.source_map, self.temp_dir)
        map_data = parse_map(cloned_map)

        # Place a custom potato resource (type_id=1) at (50, 50) with 200 amount
        target_x, target_y = 50, 50
        map_data.set_resource(target_x, target_y, type_id=1, amount=200, variant=2, state=5)
        # Modify terrain type
        map_data.set_terrain_type(target_x, target_y, 2)  # Ground
        map_data.set_walkability(target_x, target_y, 0)   # Passable
        map_data.set_elevation(target_x, target_y, 3)     # Elevation 3

        # Save
        saved_path = self.temp_dir / "modified_res_terrain.map"
        map_data.save(saved_path)
        self.assertEqual(saved_path.stat().st_size, ORIGINAL_MAP_SIZE)

        # Re-parse and verify
        re_map = parse_map(saved_path)
        res_node = re_map.get_resource(target_x, target_y)
        self.assertIsNotNone(res_node)
        self.assertEqual(res_node.type_id, 1)
        self.assertEqual(res_node.amount, 200)
        self.assertEqual(re_map.get_terrain_type(target_x, target_y), 2)
        self.assertEqual(re_map.get_walkability(target_x, target_y), 0)
        self.assertEqual(re_map.get_elevation(target_x, target_y), 3)

    def test_modify_map_interface_contract(self):
        """Verify the PROJECT.md interface contract: modify_map(map_data, modifications) -> MapData."""
        from tools.map.modder import modify_map
        cloned_map = clone_map_file(self.source_map, self.temp_dir)

        modifications = {
            "player_starts": [
                {"player_id": 1, "x": 60, "y": 70},
            ],
            "resources": {
                "set": [
                    {"x": 10, "y": 10, "type_id": 3, "amount": 150},
                ],
            },
        }
        modified_data = modify_map(cloned_map, modifications)
        self.assertEqual(len(modified_data.raw_data), ORIGINAL_MAP_SIZE)

        # Check modified values
        p1 = [ps for ps in modified_data.get_player_starts() if ps.player_id == 1][0]
        self.assertEqual(p1.x, 60)
        self.assertEqual(p1.y, 70)

        res = modified_data.get_resource(10, 10)
        self.assertIsNotNone(res)
        self.assertEqual(res.type_id, 3)
        self.assertEqual(res.amount, 150)


if __name__ == "__main__":
    unittest.main()
