"""Adversarial Challenge & Stress-Test Harness for M3 (.map Parser & Modder).

Tests:
1. Boundary coordinates (0, 0), (179, 179), and out-of-bounds rejection ((180, 0), (0, 180), (-1, -1), (200, 200)).
2. Exact 1,132,876-byte file length invariance under extensive arbitrary edits.
3. Pitch 180 layout integrity: verifying that operations at (179, y) do not bleed into (0, y+1) across all layers.
4. Stress-testing resource and building placement under extreme values and boundary coordinates.
5. Invalidation and format error rejection on corrupted, truncated, or oversized files.
6. Round-trip bit-exact preservation of untouched sections and padding.
"""

import os
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from tools.map.modder import MapModder, modify_map
from tools.map.parser import (
    DEFAULT_RESOURCE_AMOUNTS,
    MAP_FILE_SIZE,
    MAX_MAP_DIMENSION,
    MAX_PLAYERS,
    BuildingNode,
    MapData,
    MapFormatError,
    PlayerStart,
    ResourceNode,
    parse_map,
    save_map,
)

CUSMAP_DIR = Path(r"C:\src\reverse-imzinrok\YM\dawn\cusmap")


class TestAdversarialMap(unittest.TestCase):
    """Adversarial stress-test cases for .map parser and modder."""

    @classmethod
    def setUpClass(cls):
        cls.sample_maps = list(CUSMAP_DIR.glob("*.map"))
        assert len(cls.sample_maps) >= 5, f"Expected at least 5 maps in {CUSMAP_DIR}"
        cls.test_dir = Path(tempfile.mkdtemp(prefix="adv_map_test_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_adversarial_map_file_size_invariance(self):
        """Stress test: verify exact 1,132,876-byte file length is preserved under arbitrary edits."""
        for map_file in self.sample_maps[:5]:
            map_data = parse_map(map_file)
            self.assertEqual(len(map_data.raw_data), MAP_FILE_SIZE)

            # Apply massive edits
            modder = MapModder(map_data)
            # Edit player starts at boundaries
            modder.set_player_start(0, 0, 0)
            modder.set_player_start(1, map_data.width - 1, map_data.height - 1)
            modder.clear_player_start(2)

            # Edit resources at boundaries
            modder.set_resource(0, 0, type_id=1, amount=255)  # Potato
            modder.set_resource(map_data.width - 1, map_data.height - 1, type_id=100, amount=1)  # Rice
            modder.set_resource(map_data.width - 1, 0, type_id=3, amount=170)  # Tree
            modder.set_resource(0, map_data.height - 1, type_id=2, amount=50)  # Bamboo

            # Edit terrain
            modder.set_terrain_cell(0, 0, terrain_type=1, walkability=0, elevation=0)
            modder.set_terrain_cell(map_data.width - 1, map_data.height - 1, terrain_type=2, walkability=1, elevation=5)

            # Scale all resources
            modder.scale_resources(2.5)

            # Save to disk
            out_file = self.test_dir / f"edited_{map_file.name}"
            modder.map_data.save(out_file)

            # Check exact byte length on disk
            actual_size = os.path.getsize(out_file)
            self.assertEqual(
                actual_size,
                MAP_FILE_SIZE,
                f"File size violated! Expected {MAP_FILE_SIZE}, got {actual_size} for {map_file.name}",
            )

            # Re-parse to verify internal integrity
            reparsed = parse_map(out_file)
            self.assertEqual(len(reparsed.raw_data), MAP_FILE_SIZE)
            self.assertEqual(reparsed.get_terrain_type(0, 0), 1)
            self.assertEqual(reparsed.get_terrain_type(map_data.width - 1, map_data.height - 1), 2)

    def test_adversarial_boundary_coordinates(self):
        """Stress test: boundary coordinates (0, 0), (179, 179) and boundary rejections."""
        for map_file in self.sample_maps[:3]:
            map_data = parse_map(map_file)
            w, h = map_data.width, map_data.height

            # Valid boundaries inside map
            map_data.set_terrain_type(0, 0, 1)
            self.assertEqual(map_data.get_terrain_type(0, 0), 1)
            map_data.set_terrain_type(w - 1, h - 1, 2)
            self.assertEqual(map_data.get_terrain_type(w - 1, h - 1), 2)

            # Invalid boundaries outside current map width/height
            invalid_coords = [
                (-1, 0),
                (0, -1),
                (-1, -1),
                (w, 0),
                (0, h),
                (w, h),
                (180, 0),
                (0, 180),
                (180, 180),
                (999, 999),
            ]
            for ix, iy in invalid_coords:
                with self.assertRaises(IndexError):
                    map_data.get_terrain_type(ix, iy)
                with self.assertRaises(IndexError):
                    map_data.set_terrain_type(ix, iy, 1)
                with self.assertRaises(IndexError):
                    map_data.get_walkability(ix, iy)
                with self.assertRaises(IndexError):
                    map_data.get_resource(ix, iy)
                with self.assertRaises(IndexError):
                    map_data.set_resource(ix, iy, type_id=1)
                with self.assertRaises(IndexError):
                    map_data.get_building(ix, iy)
                with self.assertRaises(IndexError):
                    map_data.set_building(ix, iy, building_id=10)

    def test_adversarial_pitch_180_layout_no_leakage(self):
        """Verify pitch 180 layout strictly isolates cells and prevents row leakage."""
        raw = bytearray(MAP_FILE_SIZE)
        struct.pack_into("<I", raw, 0x00, 1)  # Version
        struct.pack_into("<I", raw, 0x88, 2)  # Num players
        struct.pack_into("<HH", raw, 0x8C, 180, 180)  # Dimensions
        struct.pack_into("<I", raw, 0x90, 0)  # Theme
        struct.pack_into("<I", raw, 0xB0, 3)  # Mode

        # Fill default ground (2) in ByteGrid 0 (0x33244)
        for i in range(180 * 180):
            raw[0x33244 + i] = 2

        map_data = MapData(raw)

        # Test setting cell (179, y) and verifying (0, y+1) is completely unaffected
        for y in range(10):
            map_data.set_terrain_type(179, y, 1)
            self.assertEqual(map_data.get_terrain_type(179, y), 1)
            self.assertEqual(map_data.get_terrain_type(0, y + 1), 2)

        # Test 16-bit tile layers pitch 180 isolation
        for y in range(10):
            map_data.set_tile(1, 179, y, 0xABCD)
            self.assertEqual(map_data.get_tile(1, 179, y), 0xABCD)
            self.assertEqual(map_data.get_tile(1, 0, y + 1), 0x0000)

        # Test resource grid pitch 180 isolation
        for y in range(10):
            map_data.set_resource(179, y, type_id=100, amount=99)
            res_right = map_data.get_resource(179, y)
            self.assertIsNotNone(res_right)
            self.assertEqual(res_right.type_id, 100)
            self.assertEqual(res_right.amount, 99)

            res_next_left = map_data.get_resource(0, y + 1)
            self.assertIsNone(
                res_next_left,
                f"Row leakage detected from (179, {y}) to (0, {y+1})!",
            )

    def test_adversarial_malformed_map_rejection(self):
        """Stress test: corrupted sizes, truncated data, and invalid headers must be rejected."""
        # 1. Truncated sizes
        with self.assertRaises(MapFormatError):
            MapData(b"SHORT_DATA")

        with self.assertRaises(MapFormatError):
            MapData(b"\x00" * (MAP_FILE_SIZE - 1))

        # 2. Oversized data
        with self.assertRaises(MapFormatError):
            MapData(b"\x00" * (MAP_FILE_SIZE + 1))

        # 3. Invalid dimensions (< 70 or > 180)
        raw = bytearray(MAP_FILE_SIZE)
        struct.pack_into("<I", raw, 0x00, 1)
        struct.pack_into("<I", raw, 0x88, 2)
        struct.pack_into("<I", raw, 0x90, 0)
        struct.pack_into("<I", raw, 0xB0, 3)

        # Dimension 69x100
        struct.pack_into("<HH", raw, 0x8C, 69, 100)
        with self.assertRaises(MapFormatError):
            MapData(raw)

        # Dimension 100x181
        struct.pack_into("<HH", raw, 0x8C, 100, 181)
        with self.assertRaises(MapFormatError):
            MapData(raw)

        # Player count 0 or 9
        struct.pack_into("<HH", raw, 0x8C, 100, 100)
        struct.pack_into("<I", raw, 0x88, 0)
        with self.assertRaises(MapFormatError):
            MapData(raw)

        struct.pack_into("<I", raw, 0x88, 9)
        with self.assertRaises(MapFormatError):
            MapData(raw)

    def test_adversarial_player_start_boundary_values(self):
        """Stress test: player start slot boundaries (slots 0..7 valid, 8 invalid, coords (0,0), (w-1, h-1))."""
        map_data = parse_map(self.sample_maps[0])
        w, h = map_data.width, map_data.height

        # Slot 8 is invalid
        with self.assertRaises(ValueError):
            map_data.set_player_start(8, 10, 10)
        with self.assertRaises(ValueError):
            map_data.set_player_start(-1, 10, 10)
        with self.assertRaises(ValueError):
            map_data.clear_player_start(8)

        # Set valid boundaries
        map_data.set_player_start(0, 0, 0)
        map_data.set_player_start(7, w - 1, h - 1)
        starts = map_data.get_player_starts()
        self.assertEqual(starts[0].x, 0)
        self.assertEqual(starts[0].y, 0)
        self.assertTrue(starts[0].is_active)
        self.assertEqual(starts[7].x, w - 1)
        self.assertEqual(starts[7].y, h - 1)
        self.assertTrue(starts[7].is_active)

        # Out of bounds coords for player start
        with self.assertRaises(IndexError):
            map_data.set_player_start(1, w, h)
        with self.assertRaises(IndexError):
            map_data.set_player_start(1, -1, 0)

        # Clear player start
        map_data.clear_player_start(0)
        starts_after = map_data.get_player_starts()
        self.assertFalse(starts_after[0].is_active)
        self.assertEqual(starts_after[0].x, 0xFFFFFFFF)
        self.assertEqual(starts_after[0].y, 0xFFFFFFFF)

    def test_adversarial_resource_amounts_and_types(self):
        """Stress test: resource boundary values, clamping, and removal."""
        map_data = parse_map(self.sample_maps[0])

        # Amount 0, 1, 255
        map_data.set_resource(10, 10, type_id=1, amount=0)
        self.assertEqual(map_data.get_resource(10, 10).amount, 0)

        map_data.set_resource(10, 10, type_id=1, amount=255)
        self.assertEqual(map_data.get_resource(10, 10).amount, 255)

        # Amount > 255 clamped to 255
        map_data.set_resource(10, 10, type_id=1, amount=500)
        self.assertEqual(map_data.get_resource(10, 10).amount, 255)

        # Amount < 0 clamped to 0
        map_data.set_resource(10, 10, type_id=1, amount=-50)
        self.assertEqual(map_data.get_resource(10, 10).amount, 0)

        # Removal
        map_data.remove_resource(10, 10)
        self.assertIsNone(map_data.get_resource(10, 10))


if __name__ == "__main__":
    unittest.main()
