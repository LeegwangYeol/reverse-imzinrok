"""
test_verify_visual_assets.py - Standalone Verification Test Suite
for Joseon 5 Infantry Units Visual Assets.

Verifies:
1. All 5 unit sprite files (.spr) in YM/dawn/char/ unpack and render without error.
2. Dimensions, frame counts (168 frames), and Version 9 header specifications.
3. Player color remap indices (236..239) presence in sprites.
4. Command button frames (289..293) in YM/dawn/fnt/button_plus.Spr (34x34).
5. Selection portrait frames (165..169 & 175..179) in YM/dawn/fnt/portrait_plus.spr (68x68).
6. Palette rendering with imjin2.pal into PIL RGBA images.
"""

from __future__ import annotations

import math
import os
import struct
import sys
import unittest
from pathlib import Path

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.assets.constants import (
    FRAME_COUNT_UNIT,
    IDX_TEAM_BRIGHT,
    IDX_TEAM_DARK,
    IDX_TEAM_HIGH,
    IDX_TEAM_MID,
    UNIT_SPECS,
)
from tools.assets.palette import Palette
from tools.assets.sprite_rle import SpriteDecoder


class TestVisualAssetsPipeline(unittest.TestCase):
    """End-to-end verification of all visual deliverables."""

    @classmethod
    def setUpClass(cls):
        cls.root = PROJECT_ROOT
        cls.char_dir = cls.root / "YM" / "dawn" / "char"
        cls.fnt_dir = cls.root / "YM" / "dawn" / "fnt"
        cls.pal_path = cls.root / "YM" / "dawn" / "pal" / "imjin2.pal"

        cls.assertTrue(cls.char_dir.exists(), f"Char dir missing: {cls.char_dir}")
        cls.assertTrue(cls.fnt_dir.exists(), f"Fnt dir missing: {cls.fnt_dir}")
        cls.assertTrue(cls.pal_path.exists(), f"Palette missing: {cls.pal_path}")
        cls.palette = Palette.from_file(cls.pal_path)

    def test_01_unit_sprite_files_exist_and_headers_valid(self):
        """Verify all 5 unit .spr files exist and have valid Version 9 headers."""
        for key, spec in UNIT_SPECS.items():
            spr_path = self.char_dir / spec["file_name"]
            self.assertTrue(spr_path.exists(), f"Missing sprite file: {spr_path}")

            with open(spr_path, "rb") as f:
                header = f.read(3060)
            self.assertEqual(len(header), 3060, f"{spr_path.name}: Header too short")

            ver, w, h, fc = struct.unpack("<IIII", header[:16])
            self.assertEqual(ver, 9, f"{spr_path.name}: Version must be 9, got {ver}")
            self.assertEqual(w, spec["width"], f"{spr_path.name}: Width mismatch")
            self.assertEqual(h, spec["height"], f"{spr_path.name}: Height mismatch")
            self.assertEqual(fc, FRAME_COUNT_UNIT, f"{spr_path.name}: Frame count must be {FRAME_COUNT_UNIT}")

            dsize, aw, ah = struct.unpack("<III", header[0xBC8:0xBD4])
            self.assertGreater(dsize, 0, f"{spr_path.name}: data_size must be > 0")
            self.assertEqual(aw, spec["width"] * 8, f"{spr_path.name}: atlas_w mismatch")
            self.assertEqual(ah, spec["height"] * ((FRAME_COUNT_UNIT + 7) // 8), f"{spr_path.name}: atlas_h mismatch")

    def test_02_unit_sprite_frames_unpack_and_render(self):
        """Verify all 168 frames of every unit unpack and convert to valid RGBA images."""
        team_color_set = {IDX_TEAM_DARK, IDX_TEAM_MID, IDX_TEAM_HIGH, IDX_TEAM_BRIGHT}

        for key, spec in UNIT_SPECS.items():
            spr_path = self.char_dir / spec["file_name"]
            dec = SpriteDecoder.from_file(spr_path)
            self.assertEqual(dec.frame_count, FRAME_COUNT_UNIT)

            found_team_colors = False
            total_non_zero = 0

            for f_idx in range(dec.frame_count):
                raw = dec.decode_frame_raw(f_idx)
                self.assertEqual(
                    len(raw),
                    spec["width"] * spec["height"],
                    f"{spr_path.name} frame {f_idx}: Raw pixel buffer size mismatch",
                )

                # Check non-zero pixel presence
                frame_non_zero = sum(1 for b in raw if b != 0)
                self.assertGreater(
                    frame_non_zero,
                    50,
                    f"{spr_path.name} frame {f_idx}: Empty or degenerate frame (only {frame_non_zero} pixels)",
                )
                total_non_zero += frame_non_zero

                # Check team colors
                if any(b in team_color_set for b in raw):
                    found_team_colors = True

                # Test RGBA conversion
                img = dec.decode_frame_image(f_idx, self.palette)
                self.assertEqual(img.size, (spec["width"], spec["height"]))
                self.assertEqual(img.mode, "RGBA")

            self.assertTrue(
                found_team_colors,
                f"{spr_path.name}: Must contain team color indices (236..239) for dynamic player recoloring",
            )
            print(f"  [PASS] {spr_path.name}: {dec.frame_count} frames verified (avg {total_non_zero // dec.frame_count} px/frame)")

    def test_03_command_button_frames_in_button_plus(self):
        """Verify restored custom buttons 289..298 and Joseon infantry buttons [216, 218, 219, 220, 233] in button_plus.Spr."""
        button_spr_path = self.fnt_dir / "button_plus.Spr"
        self.assertTrue(button_spr_path.exists())

        dec = SpriteDecoder.from_file(button_spr_path)
        self.assertEqual(dec.version, 9)
        self.assertEqual(dec.width, 34)
        self.assertEqual(dec.height, 34)
        self.assertEqual(dec.frame_count, 299, f"button_plus.Spr must have exactly 299 frames, got {dec.frame_count}")

        # 1. Verify restored 10 custom unit buttons (289..298)
        for custom_idx in range(289, 299):
            raw = dec.decode_frame_raw(custom_idx)
            self.assertEqual(len(raw), 34 * 34)
            non_zero = sum(1 for b in raw if b != 0)
            self.assertGreaterEqual(
                non_zero,
                1000,
                f"Restored custom button {custom_idx} has too few pixels: {non_zero}/1156",
            )
            img = dec.decode_frame_image(custom_idx, self.palette)
            self.assertEqual(img.size, (34, 34))

        print("  [PASS] Restored custom buttons (frames 289..298) verified solid 34x34")

        # 2. Verify new 5 Joseon infantry buttons in unused slots [216, 218, 219, 220, 233]
        for key, spec in UNIT_SPECS.items():
            btn_idx = spec["btn_index"]
            self.assertIn(btn_idx, [216, 218, 219, 220, 233])
            self.assertLess(btn_idx, dec.frame_count)

            raw = dec.decode_frame_raw(btn_idx)
            self.assertEqual(len(raw), 34 * 34)

            non_zero = sum(1 for b in raw if b != 0)
            self.assertGreaterEqual(
                non_zero,
                1000,
                f"Button {btn_idx} ({key}) has too few pixels: {non_zero}/1156",
            )

            img = dec.decode_frame_image(btn_idx, self.palette)
            self.assertEqual(img.size, (34, 34))
            print(f"  [PASS] Button frame {btn_idx} ({spec['kor_name']}): {non_zero}/1156 pixels verified")

    def test_04_selection_portrait_frames_in_portrait_plus(self):
        """Verify selection portraits in portrait_plus.spr (165..174 restored and 175..179 Joseon 5 units)."""
        portrait_spr_path = self.fnt_dir / "portrait_plus.spr"
        self.assertTrue(portrait_spr_path.exists())

        dec = SpriteDecoder.from_file(portrait_spr_path)
        self.assertEqual(dec.version, 9)
        self.assertEqual(dec.width, 68)
        self.assertEqual(dec.height, 68)
        self.assertEqual(dec.frame_count, 195, f"portrait_plus.spr must have 195 frames, got {dec.frame_count}")

        cx, cy = 33.5, 33.5

        # 1. Verify restored 10 custom unit portraits (165..174)
        for custom_idx in range(165, 175):
            raw = dec.decode_frame_raw(custom_idx)
            self.assertEqual(len(raw), 68 * 68)
            non_zero = sum(1 for b in raw if b != 0)
            self.assertGreaterEqual(
                non_zero,
                3000,
                f"Restored custom portrait {custom_idx} too sparse: {non_zero} pixels",
            )
            # Check circular mask
            for y in range(68):
                for x in range(68):
                    dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if dist > 33.2:
                        self.assertEqual(
                            raw[y * 68 + x],
                            0,
                            f"Restored portrait {custom_idx} has non-transparent pixel outside circle at ({x},{y})",
                        )
        print("  [PASS] Restored custom portraits (frames 165..174) verified non-degenerate and masked")

        # 2. Verify new 5 unit portraits (175..179)
        for key, spec in UNIT_SPECS.items():
            for target_idx in (spec["portrait_index"], spec["portrait_alt_index"]):
                self.assertLess(target_idx, dec.frame_count)

                raw = dec.decode_frame_raw(target_idx)
                self.assertEqual(len(raw), 68 * 68)

                # Check circular mask: outside radius 33.2 must be transparent 0
                for y in range(68):
                    for x in range(68):
                        dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                        if dist > 33.2:
                            self.assertEqual(
                                raw[y * 68 + x],
                                0,
                                f"Portrait {target_idx} ({key}) has non-transparent pixel outside circle at ({x},{y})",
                            )

                non_zero = sum(1 for b in raw if b != 0)
                # Circular disc radius 33.2 area ≈ pi * 33.2^2 ≈ 3462 pixels
                self.assertGreaterEqual(
                    non_zero,
                    3000,
                    f"Portrait {target_idx} ({key}) too sparse: {non_zero} pixels",
                )

                img = dec.decode_frame_image(target_idx, self.palette)
                self.assertEqual(img.size, (68, 68))

            print(f"  [PASS] Portrait frame {spec['portrait_index']} ({spec['kor_name']}) verified")

    def test_05_original_backup_safety_audit(self):
        """Verify that verify_safety.py passes 204/204 clean and untouched."""
        import subprocess

        cmd = [sys.executable, str(self.root / "tools" / "verify_safety.py")]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.root))
        self.assertEqual(res.returncode, 0, f"Safety audit failed: {res.stdout}\n{res.stderr}")
        self.assertIn("AUDIT RESULT: PASSED (100% Clean & Untouched)", res.stdout)
        print("  [PASS] verify_safety.py: 204/204 original files verified 100% bit-exact")


if __name__ == "__main__":
    unittest.main(verbosity=2)
