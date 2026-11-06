"""
Test Suite for R4: Proprietary Asset Decoders (.pal, .YAV, .spr, .ytl, .ypr)
Imjinrok 2+ Dawn Modding Toolkit
"""

import os
import unittest
import wave
from pathlib import Path
from PIL import Image

from tests.conftest import (
    DAWN_DIR,
    DEFAULT_PAL,
    IMJIN2_PAL,
    EFT_DIR,
    MUSIC_DIR,
    CHAR_DIR,
    TILE_DIR,
    FNT_DIR,
    BATTLE_SPR,
    get_temp_dir,
)
from tools.assets.palette import (
    Palette,
    convert_pal_to_rgba,
    PALETTE_FILE_SIZE,
    COLOR_COUNT,
)
from tools.assets.audio import (
    YAVAudio,
    convert_yav_to_wav,
    YAV_HEADER_SIZE,
)
from tools.assets.sprite_rle import (
    SpriteDecoder,
    SpriteMetadata,
    decode_spr,
    SPR_HEADER_SIZE,
)
from tools.assets.tile_rle import (
    TileDecoder,
    TileMetadata,
    decode_ytl,
    decode_ypr,
    decode_tile,
    TILE_HEADER_SIZE,
)


class TestPaletteConverter(unittest.TestCase):
    """Tier 1 & Tier 2: 6-bit VGA DAC .pal to 8-bit RGBA Palette Converter Tests."""

    def test_default_palette_size_and_count(self):
        """Verify palette file size is 768 bytes and yields 256 colors."""
        self.assertTrue(DEFAULT_PAL.exists(), f"Palette file not found: {DEFAULT_PAL}")
        self.assertEqual(DEFAULT_PAL.stat().st_size, PALETTE_FILE_SIZE)

        colors = convert_pal_to_rgba(DEFAULT_PAL)
        self.assertEqual(len(colors), COLOR_COUNT)

    def test_alpha_transparency_on_index_0(self):
        """Verify index 0 has alpha = 0 (transparent) and index 1..255 have alpha = 255 (opaque)."""
        colors = convert_pal_to_rgba(DEFAULT_PAL)
        r0, g0, b0, a0 = colors[0]
        self.assertEqual(a0, 0, "Index 0 must have Alpha = 0 (fully transparent)")

        for i in range(1, COLOR_COUNT):
            _, _, _, a_i = colors[i]
            self.assertEqual(a_i, 255, f"Index {i} must have Alpha = 255 (opaque)")

    def test_6bit_to_8bit_scaling_formula(self):
        """Verify that 6-bit values (0..63) are scaled to 8-bit range (0..255)."""
        pal_bytes = DEFAULT_PAL.read_bytes()
        # All 6-bit channel values must be <= 63
        for b in pal_bytes:
            self.assertLessEqual(b, 63, f"Found out-of-range 6-bit DAC value: {b}")

        colors = convert_pal_to_rgba(DEFAULT_PAL)
        for i in range(COLOR_COUNT):
            r, g, b, _ = colors[i]
            self.assertTrue(0 <= r <= 255)
            self.assertTrue(0 <= g <= 255)
            self.assertTrue(0 <= b <= 255)

    def test_invalid_palette_size_rejection(self):
        """Tier 2: Truncated or oversized palette bytes raise ValueError."""
        with self.assertRaises(ValueError):
            Palette.from_bytes(b"\x00" * 500)
        with self.assertRaises(ValueError):
            Palette.from_bytes(b"\x00" * 1000)


class TestAudioConverter(unittest.TestCase):
    """Tier 1, Tier 2 & Tier 4: .YAV to RIFF WAV Audio Converter Tests."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("audio_test_")
        cls.eft_files = sorted(list(EFT_DIR.glob("*.yav")))
        cls.music_files = sorted(list(MUSIC_DIR.glob("*.yav"))) if MUSIC_DIR.exists() else []
        cls.test_yavs = cls.eft_files[:4] + cls.music_files[:2]
        if len(cls.test_yavs) < 5:
            # Fall back to more EFT files if music is missing
            cls.test_yavs = cls.eft_files[:6]
        if len(cls.test_yavs) < 5:
            raise FileNotFoundError(f"Expected at least 5 .yav files in {EFT_DIR}")

    def test_parse_yav_header(self):
        """Verify 26-byte header fields: fmt_size=18, format_tag=1 (PCM)."""
        sample_yav = self.test_yavs[0]
        audio = YAVAudio.from_file(sample_yav)

        self.assertEqual(audio.fmt_size, 18)
        self.assertEqual(audio.format_tag, 1)  # WAVE_FORMAT_PCM
        self.assertIn(audio.channels, (1, 2))
        self.assertIn(audio.bits_per_sample, (8, 16))
        self.assertGreater(audio.sample_rate, 5000)
        self.assertEqual(audio.cb_size, 0)
        self.assertEqual(len(audio.pcm_data), audio.data_size)
        self.assertEqual(sample_yav.stat().st_size, YAV_HEADER_SIZE + audio.data_size)

    def test_single_yav_to_wav_conversion(self):
        """Convert a single YAV and verify using Python standard wave module."""
        sample_yav = self.test_yavs[0]
        out_wav = self.temp_dir / f"{sample_yav.stem}.wav"

        success = convert_yav_to_wav(sample_yav, out_wav)
        self.assertTrue(success)
        self.assertTrue(out_wav.exists())

        # Validate with wave module
        with wave.open(str(out_wav), "rb") as wf:
            self.assertIn(wf.getnchannels(), (1, 2))
            self.assertIn(wf.getsampwidth(), (1, 2))
            self.assertGreater(wf.getframerate(), 5000)
            self.assertGreater(wf.getnframes(), 0)

    def test_batch_convert_5_yav_files(self):
        """Tier 4: Convert at least 5 distinct .YAV files and verify playable PCM headers."""
        converted_count = 0
        for yav_path in self.test_yavs[:5]:
            out_wav = self.temp_dir / f"batch_{yav_path.stem}.wav"
            success = convert_yav_to_wav(yav_path, out_wav)
            self.assertTrue(success, f"Failed to convert {yav_path.name}")
            self.assertTrue(out_wav.exists())

            with wave.open(str(out_wav), "rb") as wf:
                audio = YAVAudio.from_file(yav_path)
                self.assertEqual(wf.getnchannels(), audio.channels)
                self.assertEqual(wf.getframerate(), audio.sample_rate)
                self.assertEqual(wf.getnframes(), audio.sample_count)
            converted_count += 1

        self.assertGreaterEqual(converted_count, 5)

    def test_truncated_yav_rejection(self):
        """Tier 2: Truncated YAV header or payload raises ValueError."""
        # Truncated header
        with self.assertRaises(ValueError):
            YAVAudio.from_bytes(b"\x12\x00\x00\x00")

        # Header specifies 100 bytes data but buffer has only 10
        import struct
        fake_header = struct.pack("<IHHIIHHHI", 18, 1, 1, 22050, 22050, 1, 8, 0, 100)
        with self.assertRaises(ValueError):
            YAVAudio.from_bytes(fake_header + b"\x00" * 10)


class TestSpriteAndTileDecoders(unittest.TestCase):
    """Tier 1, Tier 3 & Tier 4: Version 9 .spr, .ytl, .ypr Decoders Tests."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("sprite_tile_test_")
        cls.pal_path = IMJIN2_PAL if IMJIN2_PAL.exists() else DEFAULT_PAL

    def test_decode_ui_sprite_back(self):
        """Decode BattleSpr\\Back.Spr and verify dimensions and transparency."""
        self.assertTrue(BATTLE_SPR.exists(), f"Back.Spr not found at {BATTLE_SPR}")
        out_dir = self.temp_dir / "back_spr"
        meta = decode_spr(BATTLE_SPR, self.pal_path, out_dir, export_atlas=False, export_frames=True)

        self.assertEqual(meta.version, 9)
        self.assertGreater(meta.width, 0)
        self.assertGreater(meta.height, 0)
        self.assertGreater(meta.frame_count, 0)

        # Check that exported PNG exists and is valid
        self.assertGreater(len(meta.frames), 0)
        frame_0_name = meta.frames[0].file_name or f"{meta.name}_000.png"
        frame_0_path = out_dir / frame_0_name
        self.assertTrue(frame_0_path.exists())
        with Image.open(frame_0_path) as img:
            self.assertEqual(img.size, (meta.width, meta.height))
            self.assertEqual(img.mode, "RGBA")

    def test_decode_unit_sprite_farmerk(self):
        """Decode char\\farmerk.spr with multi-frame atlas."""
        farmerk_path = CHAR_DIR / "farmerk.spr"
        self.assertTrue(farmerk_path.exists(), f"farmerk.spr not found at {farmerk_path}")
        out_dir = self.temp_dir / "farmerk"
        meta = decode_spr(farmerk_path, self.pal_path, out_dir, export_atlas=True, export_frames=False)

        self.assertEqual(meta.version, 9)
        self.assertEqual(meta.width, 80)
        self.assertEqual(meta.height, 60)
        self.assertEqual(meta.frame_count, 288)
        self.assertIsNotNone(meta.atlas_file)

        atlas_path = out_dir / meta.atlas_file
        self.assertTrue(atlas_path.exists())
        with Image.open(atlas_path) as img:
            self.assertEqual(img.size, (meta.atlas_width, meta.atlas_height))
            self.assertEqual(img.mode, "RGBA")

    def test_decode_diamond_tile_ytl(self):
        """Decode Version 9 .ytl diamond isometric tile."""
        ytl_files = list(TILE_DIR.glob("**/*.ytl"))
        self.assertTrue(len(ytl_files) > 0, "No .ytl files found in tile/")
        sample_ytl = ytl_files[0]

        out_dir = self.temp_dir / f"ytl_{sample_ytl.stem}"
        meta = decode_ytl(sample_ytl, self.pal_path, out_dir, export_atlas=False, export_frames=True)

        self.assertEqual(meta.version, 9)
        self.assertEqual(meta.width, 64)
        self.assertEqual(meta.height, 48)
        self.assertGreater(meta.frame_count, 0)

        # Verify frame PNG
        self.assertGreater(len(meta.frames), 0)
        frame_0_name = meta.frames[0].file_name or f"{meta.name}_000.png"
        frame_0 = out_dir / frame_0_name
        self.assertTrue(frame_0.exists())
        with Image.open(frame_0) as img:
            self.assertEqual(img.size, (64, 48))
            self.assertEqual(img.mode, "RGBA")

    def test_decode_hill_tile_ypr(self):
        """Decode Version 9 .ypr multi-span hill tile."""
        ypr_files = list(TILE_DIR.glob("**/*.ypr"))
        self.assertTrue(len(ypr_files) > 0, "No .ypr files found in tile/")
        sample_ypr = ypr_files[0]

        out_dir = self.temp_dir / f"ypr_{sample_ypr.stem}"
        meta = decode_ypr(sample_ypr, self.pal_path, out_dir, export_atlas=False, export_frames=True)

        self.assertEqual(meta.version, 9)
        self.assertGreater(meta.width, 0)
        self.assertGreater(meta.height, 0)
        self.assertGreater(meta.frame_count, 0)

    def test_batch_decode_10_distinct_assets(self):
        """Tier 4: Batch decode at least 10 distinct .spr, .ytl, and .ypr files."""
        candidate_assets = [
            BATTLE_SPR,
            FNT_DIR / "mouse.spr",
            CHAR_DIR / "farmerk.spr",
            CHAR_DIR / "swordk.spr",
            CHAR_DIR / "arrowk.spr",
            CHAR_DIR / "monkk.spr",
        ]
        # Add tile files
        ytl_files = list(TILE_DIR.glob("**/*.ytl"))
        ypr_files = list(TILE_DIR.glob("**/*.ypr"))
        candidate_assets.extend(ytl_files[:4])
        candidate_assets.extend(ypr_files[:2])

        # Filter existing
        existing_assets = [p for p in candidate_assets if p.exists()]
        self.assertGreaterEqual(
            len(existing_assets),
            10,
            f"Expected at least 10 candidate asset files, found {len(existing_assets)}",
        )

        decoded_count = 0
        out_batch_dir = self.temp_dir / "batch_10"

        for asset_path in existing_assets[:10]:
            ext = asset_path.suffix.lower()
            sub_dir = out_batch_dir / asset_path.stem
            if ext == ".spr":
                meta = decode_spr(asset_path, self.pal_path, sub_dir, export_atlas=False, export_frames=True)
            elif ext == ".ytl":
                meta = decode_ytl(asset_path, self.pal_path, sub_dir, export_atlas=False, export_frames=True)
            elif ext == ".ypr":
                meta = decode_ypr(asset_path, self.pal_path, sub_dir, export_atlas=False, export_frames=True)
            else:
                continue

            self.assertEqual(meta.version, 9)
            # Verify frame 0 exists
            self.assertGreater(len(meta.frames), 0)
            f0_name = meta.frames[0].file_name or f"{meta.name}_000.png"
            f0 = sub_dir / f0_name
            self.assertTrue(f0.exists(), f"Frame 0 missing for {asset_path.name}")
            with Image.open(f0) as img:
                self.assertEqual(img.size, (meta.width, meta.height))
            decoded_count += 1

        self.assertGreaterEqual(decoded_count, 10)


class TestAssetCLI(unittest.TestCase):
    """Tier 1: CLI invocation tests for imjinrok-asset-tool."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("cli_test_")
        cls.pal_path = str(IMJIN2_PAL if IMJIN2_PAL.exists() else DEFAULT_PAL)

    def test_cli_convert_pal(self):
        from tools.assets.cli import main as cli_main

        out_json = str(self.temp_dir / "cli_pal.json")
        ret = cli_main(["convert-pal", self.pal_path, "-o", out_json])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(out_json))

    def test_cli_convert_yav(self):
        from tools.assets.cli import main as cli_main

        yav_sample = str(sorted(list(EFT_DIR.glob("*.YAV")))[0])
        out_wav = str(self.temp_dir / "cli_audio.wav")
        ret = cli_main(["convert-yav", yav_sample, "-o", out_wav])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(out_wav))

    def test_cli_decode_spr(self):
        from tools.assets.cli import main as cli_main

        spr_sample = str(BATTLE_SPR)
        out_dir = str(self.temp_dir / "cli_spr")
        ret = cli_main(["decode-spr", spr_sample, "-p", self.pal_path, "-o", out_dir])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "Back_frame_000.png")))

    def test_cli_decode_ytl(self):
        from tools.assets.cli import main as cli_main

        ytl_sample = str(list(TILE_DIR.glob("**/*.ytl"))[0])
        out_dir = str(self.temp_dir / "cli_ytl")
        ret = cli_main(["decode-ytl", ytl_sample, "-p", self.pal_path, "-o", out_dir])
        self.assertEqual(ret, 0)

    def test_cli_batch_convert(self):
        from tools.assets.cli import main as cli_main

        out_dir = str(self.temp_dir / "cli_batch")
        in_dir = str(TILE_DIR / "bright")
        ret = cli_main([
            "batch-convert",
            "-i", in_dir,
            "-o", out_dir,
            "-p", self.pal_path,
            "--types", "ytl",
            "-m", "3",
        ])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()

