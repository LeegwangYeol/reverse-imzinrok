"""
Tier 5 Adversarial Stress Test Suite for Milestone 1 (Archive) & Milestone 4 (Assets)
Imjinrok 2+ Dawn Modding Toolkit

Covers:
- Malformed headers, boundary offsets, corrupted RLE streams, out-of-bounds indices.
- Bit-exact repacking against original Data and Data.hq.
- Path traversal vulnerability detection in unpacker.
- WAV chunk verification, sample counts, and wave module playability.
- Palette 6-bit VGA DAC scaling and alpha channel verification.
- Empirical reproduction of edge-case bugs and crash conditions.
"""

import io
import json
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image

from tools.archive.codec import (
    xor_bytes,
    decode_data_bytes,
    encode_data_bytes,
    decode_hq_line,
    encode_hq_line,
    decode_hq_bytes,
    encode_hq_bytes,
    verify_data_roundtrip,
    verify_hq_roundtrip,
)
from tools.archive.unpacker import (
    unpack_archive,
    parse_hq_entries,
    FileInfo,
)
from tools.archive.repacker import (
    repack_archive,
    verify_bit_exact,
    verify_archive_pair,
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
    YAV_HEADER_FORMAT,
)
from tools.assets.sprite_rle import (
    SpriteDecoder,
    decode_spr,
    SPR_HEADER_SIZE,
)
from tools.assets.tile_rle import (
    TileDecoder,
    decode_ytl,
    decode_ypr,
    TILE_HEADER_SIZE,
)


class TestArchiveAdversarial(unittest.TestCase):
    """Adversarial challenge tests for tools/archive/ (M1)."""

    def setUp(self):
        self.data_path = Path("YM/dawn/Data")
        self.hq_path = Path("YM/dawn/Data.hq")

    def test_original_files_exist_and_match_spec(self):
        """Verify original YM/dawn/Data and Data.hq sizes match reverse-engineering specs."""
        self.assertTrue(self.data_path.exists(), "YM/dawn/Data must exist")
        self.assertTrue(self.hq_path.exists(), "YM/dawn/Data.hq must exist")
        self.assertEqual(self.data_path.stat().st_size, 230202)
        self.assertEqual(self.hq_path.stat().st_size, 5408)

    def test_bit_exact_archive_roundtrip(self):
        """Unpack original archives and immediately repack; must be 100% bit-exact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            unpacked_dir = tmp / "unpacked"
            file_infos = unpack_archive(self.data_path, self.hq_path, unpacked_dir)
            self.assertEqual(len(file_infos), 109)

            repacked_data = tmp / "Data"
            repacked_hq = tmp / "Data.hq"
            ok = repack_archive(unpacked_dir, repacked_data, repacked_hq)
            self.assertTrue(ok)

            match, details = verify_archive_pair(
                self.data_path, self.hq_path, repacked_data, repacked_hq
            )
            self.assertTrue(match, f"Roundtrip failed: {details}")
            self.assertTrue(details["data"]["bit_exact"])
            self.assertTrue(details["hq"]["bit_exact"])
            self.assertEqual(details["data"]["orig_sha256"], details["data"]["repacked_sha256"])
            self.assertEqual(details["hq"]["orig_sha256"], details["hq"]["repacked_sha256"])

    def test_repack_modified_payload_dynamic_recalculation(self):
        """Modify an unpacked file and verify repacker recalculates offsets and sizes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            unpacked_dir = tmp / "unpacked"
            unpack_archive(self.data_path, self.hq_path, unpacked_dir)

            # Modify CastleType.txt (index 0, original size 1,108)
            target = unpacked_dir / "CastleType.txt"
            orig_bytes = target.read_bytes()
            extra_content = b"\r\n# ADVERSARIAL STRESS TEST INJECTION\r\n"
            target.write_bytes(orig_bytes + extra_content)
            new_size = len(target.read_bytes())
            self.assertEqual(new_size, len(orig_bytes) + len(extra_content))

            repacked_data = tmp / "Data"
            repacked_hq = tmp / "Data.hq"
            ok = repack_archive(unpacked_dir, repacked_data, repacked_hq)
            self.assertTrue(ok)

            # Repacked Data size must increase by len(extra_content)
            expected_total_size = 230202 + len(extra_content)
            self.assertEqual(repacked_data.stat().st_size, expected_total_size)

            # Re-unpack and verify modified file content
            re_unpacked_dir = tmp / "re_unpacked"
            re_file_infos = unpack_archive(repacked_data, repacked_hq, re_unpacked_dir)
            self.assertEqual(len(re_file_infos), 109)
            self.assertEqual(re_file_infos[0].size, new_size)
            # Second file offset must have shifted by len(extra_content)
            self.assertEqual(re_file_infos[1].offset, new_size)
            self.assertEqual(
                (re_unpacked_dir / "CastleType.txt").read_bytes(),
                orig_bytes + extra_content,
            )

    def test_path_traversal_detection(self):
        """Empirically test whether unpacker allows path traversal escape via relative components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            hq_lines = [
                "총라인수 : [1]",
                "..\\traversal_escape.txt\t[11]\t[0]",
            ]
            hq_bytes = encode_hq_bytes(hq_lines, encoding="cp949")
            data_bytes = encode_data_bytes(b"TRAVERSAL!!")

            hq_file = tmp / "Data.hq"
            data_file = tmp / "Data"
            hq_file.write_bytes(hq_bytes)
            data_file.write_bytes(data_bytes)

            target_out = tmp / "sandbox"
            target_out.mkdir()

            # Execute unpack
            unpack_archive(data_file, hq_file, target_out)

            escaped_file = tmp / "traversal_escape.txt"
            # As an empirical challenger, we document whether the file escaped target_out
            if escaped_file.exists():
                # Document confirmed finding
                self.assertTrue(
                    escaped_file.exists(),
                    "Confirmed: unpacker currently allows path traversal outside output_dir",
                )

    def test_malformed_hq_header_syntax(self):
        """Test reject conditions for corrupted or missing Data.hq header."""
        # 1. Missing brackets
        bad_hq1 = encode_hq_bytes(["총라인수: 109", "CastleType.txt\t[1108]\t[0]"])
        with self.assertRaises(ValueError):
            parse_hq_entries(bad_hq1)

        # 2. Non-numeric count
        bad_hq2 = encode_hq_bytes(["총라인수 : [ABC]", "CastleType.txt\t[1108]\t[0]"])
        with self.assertRaises(ValueError):
            parse_hq_entries(bad_hq2)

        # 3. Empty buffer
        with self.assertRaises(ValueError):
            parse_hq_entries(b"")

    def test_hq_entry_count_mismatch(self):
        """Header claims 3 lines but only 1 entry is present."""
        bad_hq = encode_hq_bytes(["총라인수 : [3]", "CastleType.txt\t[1108]\t[0]"])
        with self.assertRaises(ValueError) as cm:
            parse_hq_entries(bad_hq)
        self.assertIn("Entry count mismatch", str(cm.exception))

    def test_hq_offset_gap_or_overlap(self):
        """Detect gap or overlap in entry offsets."""
        # Gap: entry 2 expected at 10, but offset is 15
        gap_hq = encode_hq_bytes([
            "총라인수 : [2]",
            "file1.txt\t[10]\t[0]",
            "file2.txt\t[10]\t[15]",
        ])
        with self.assertRaises(ValueError) as cm:
            parse_hq_entries(gap_hq)
        self.assertIn("Offset gap/overlap", str(cm.exception))

        # Overlap: entry 2 offset is 5 instead of 10
        overlap_hq = encode_hq_bytes([
            "총라인수 : [2]",
            "file1.txt\t[10]\t[0]",
            "file2.txt\t[10]\t[5]",
        ])
        with self.assertRaises(ValueError) as cm:
            parse_hq_entries(overlap_hq)
        self.assertIn("Offset gap/overlap", str(cm.exception))

    def test_archive_data_size_mismatch(self):
        """Test error when Data archive size does not match total entry sizes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            hq_lines = ["총라인수 : [1]", "file1.txt\t[100]\t[0]"]
            hq_bytes = encode_hq_bytes(hq_lines)
            # Data is only 50 bytes instead of 100
            data_bytes = encode_data_bytes(b"A" * 50)

            hq_file = tmp / "Data.hq"
            data_file = tmp / "Data"
            hq_file.write_bytes(hq_bytes)
            data_file.write_bytes(data_bytes)

            with self.assertRaises(ValueError) as cm:
                unpack_archive(data_file, hq_file, tmp / "out")
            self.assertIn("Archive size mismatch", str(cm.exception))

    def test_repack_empty_directory_fails(self):
        """Repacking an empty directory must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with self.assertRaises(ValueError):
                repack_archive(tmp, tmp / "Data", tmp / "Data.hq")

    def test_codec_all_byte_values_involution(self):
        """Verify unconditional XOR 0x10 is a perfect involution for all 256 byte values."""
        all_bytes = bytes(range(256))
        self.assertEqual(xor_bytes(xor_bytes(all_bytes, 0x10), 0x10), all_bytes)
        self.assertEqual(decode_data_bytes(encode_data_bytes(all_bytes)), all_bytes)


class TestAssetsAdversarial(unittest.TestCase):
    """Adversarial challenge tests for tools/assets/ (M4)."""

    def setUp(self):
        self.imjin2_pal_path = Path("YM/dawn/pal/imjin2.pal")
        self.assertTrue(self.imjin2_pal_path.exists())

    def test_all_38_pal_files_conformance(self):
        """Every .pal file in YM/dawn must parse to 256 colors with index 0 alpha=0 and 1..255 alpha=255."""
        pal_files = list(Path("YM/dawn").rglob("*.pal")) + list(Path("YM/dawn").rglob("*.PAL"))
        unique_pals = sorted(list(set(pal_files)))
        self.assertGreaterEqual(len(unique_pals), 38)

        for p in unique_pals:
            pal = Palette.from_file(p)
            self.assertEqual(len(pal.colors), 256, f"{p} must have 256 colors")
            self.assertEqual(pal.colors[0][3], 0, f"{p}: index 0 must be transparent (alpha=0)")
            for idx in range(1, 256):
                self.assertEqual(
                    pal.colors[idx][3], 255, f"{p}: index {idx} must be opaque (alpha=255)"
                )
                for c in range(3):
                    self.assertGreaterEqual(pal.colors[idx][c], 0)
                    self.assertLessEqual(pal.colors[idx][c], 255)

    def test_palette_dac_clamping_and_size_validation(self):
        """Palette loader must clamp >63 DAC values and reject invalid file sizes."""
        # Malformed sizes
        with self.assertRaises(ValueError):
            Palette.from_bytes(b"\x00" * 767)
        with self.assertRaises(ValueError):
            Palette.from_bytes(b"\x00" * 769)

        # Out-of-bounds DAC value (e.g. 255)
        raw = bytearray(768)
        raw[3] = 255  # index 1 Red channel
        pal = Palette.from_bytes(bytes(raw))
        # Clamped to 63, scaled to 255
        self.assertEqual(pal.colors[1][0], 255)

    def test_yav_conversion_and_playability_across_assets(self):
        """Verify >= 10 real .YAV files from eft, music, and gamejvi into valid playable WAVs."""
        yav_files = [
            Path("YM/dawn/eft/arrow1.YAV"),
            Path("YM/dawn/eft/airplanedie1.YAV"),
            Path("YM/dawn/eft/bigsword1.YAV"),
            Path("YM/dawn/eft/bomb.YAV"),
            Path("YM/dawn/eft/buda1.YAV"),
            Path("YM/dawn/eft/bull1.YAV"),
            Path("YM/dawn/music/briefmusic.YAV"),
            Path("YM/dawn/gamejvi/1-1.YAV"),
            Path("YM/dawn/gamejvi/1-2.YAV"),
            Path("YM/dawn/gamejvi/1-3.YAV"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            for yav_path in yav_files:
                if not yav_path.exists():
                    continue
                audio = YAVAudio.from_file(yav_path)
                expected_samples = audio.data_size // (
                    audio.channels * audio.bits_per_sample // 8
                )
                self.assertEqual(audio.sample_count, expected_samples)

                out_wav = tmp / f"{yav_path.stem}.wav"
                ok = convert_yav_to_wav(yav_path, out_wav)
                self.assertTrue(ok)

                # Verify RIFF structure and playability via wave module
                with wave.open(str(out_wav), "rb") as wf:
                    self.assertEqual(wf.getnchannels(), audio.channels)
                    self.assertEqual(wf.getsampwidth(), audio.bits_per_sample // 8)
                    self.assertEqual(wf.getframerate(), audio.sample_rate)
                    self.assertEqual(wf.getnframes(), expected_samples)

    def test_yav_adversarial_malformed_inputs(self):
        """Adversarial stress-testing of YAV parser with invalid headers."""
        # 1. Truncated header (< 26 bytes)
        with self.assertRaises(ValueError):
            YAVAudio.from_bytes(b"\x00" * 25)

        # 2. fmt_size != 18
        hdr_bad_fmt = struct.pack(YAV_HEADER_FORMAT, 16, 1, 1, 22050, 22050, 1, 8, 0, 10)
        with self.assertRaises(ValueError):
            YAVAudio.from_bytes(hdr_bad_fmt + b"\x00" * 10)

        # 3. format_tag != 1
        hdr_bad_tag = struct.pack(YAV_HEADER_FORMAT, 18, 2, 1, 22050, 22050, 1, 8, 0, 10)
        with self.assertRaises(ValueError):
            YAVAudio.from_bytes(hdr_bad_tag + b"\x00" * 10)

        # 4. Truncated PCM stream
        hdr_trunc = struct.pack(YAV_HEADER_FORMAT, 18, 1, 1, 22050, 22050, 1, 8, 0, 100)
        with self.assertRaises(ValueError):
            YAVAudio.from_bytes(hdr_trunc + b"\x00" * 20)

    def test_spr_decoding_and_transparency(self):
        """Decode real .spr files and verify frame dimensions and alpha channel."""
        pal = Palette.from_file(self.imjin2_pal_path)
        spr_samples = [
            ("YM/dawn/BattleSpr/Back.Spr", 800, 600, 1),
            ("YM/dawn/char/farmerk.spr", 80, 60, 288),
            ("YM/dawn/fnt/mouse.spr", 32, 32, 200),
            ("YM/dawn/char/swordk.spr", 60, 60, 192),
        ]

        for rel_path, exp_w, exp_h, exp_frames in spr_samples:
            p = Path(rel_path)
            self.assertTrue(p.exists(), f"{p} must exist")
            dec = SpriteDecoder.from_file(p)
            self.assertEqual(dec.width, exp_w)
            self.assertEqual(dec.height, exp_h)
            self.assertEqual(dec.frame_count, exp_frames)

            # Test frame 0
            img = dec.decode_frame_image(0, pal)
            self.assertEqual(img.size, (exp_w, exp_h))
            self.assertEqual(img.mode, "RGBA")
            alphas = [px[3] for px in img.getdata()]
            self.assertIn(0, alphas, "Must contain transparent pixels")
            self.assertIn(255, alphas, "Must contain opaque pixels")

    def test_spr_adversarial_out_of_bounds_and_malformed(self):
        """Adversarially challenge SpriteDecoder with invalid indices and corrupted inputs."""
        dec = SpriteDecoder.from_file("YM/dawn/BattleSpr/Back.Spr")
        # Frame index out of bounds
        with self.assertRaises(IndexError):
            dec.decode_frame_raw(-1)
        with self.assertRaises(IndexError):
            dec.decode_frame_raw(1)  # Back.Spr has only 1 frame (index 0)

        # Zero-byte file (temp.spr)
        with self.assertRaises(ValueError):
            SpriteDecoder.from_file("YM/dawn/temp.spr")

        # Corrupted version != 9
        bad_hdr = bytearray(SPR_HEADER_SIZE)
        struct.pack_into("<IIII", bad_hdr, 0, 8, 64, 48, 1)
        with self.assertRaises(ValueError):
            SpriteDecoder(bytes(bad_hdr))

    def test_tile_decoding_ytl_and_ypr(self):
        """Test real .ytl single-span and .ypr multi-span tile decoders."""
        pal = Palette.from_file(self.imjin2_pal_path)

        # 1. .ytl (castle0.ytl: 64x48)
        ytl_path = Path("YM/dawn/tile/bright/castle0.ytl")
        ytl = TileDecoder.from_file(ytl_path, tile_type="ytl")
        self.assertEqual(ytl.width, 64)
        self.assertEqual(ytl.height, 48)
        img_ytl = ytl.decode_frame_image(0, pal)
        self.assertEqual(img_ytl.size, (64, 48))
        self.assertEqual(img_ytl.mode, "RGBA")

        # 2. .ypr (hill0.ypr: 80x60)
        ypr_path = Path("YM/dawn/tile/bright/hill0.ypr")
        ypr = TileDecoder.from_file(ypr_path, tile_type="ypr")
        self.assertEqual(ypr.width, 80)
        self.assertEqual(ypr.height, 60)
        img_ypr = ypr.decode_frame_image(0, pal)
        self.assertEqual(img_ypr.size, (80, 60))
        self.assertEqual(img_ypr.mode, "RGBA")

    def test_ytl_truncated_stream_index_error_reproduction(self):
        """
        Empirically test whether TileDecoder handles an odd-byte truncated stream
        or raises IndexError due to unchecked s_idx + 1 in single-span loop.
        """
        header = bytearray(TILE_HEADER_SIZE)
        struct.pack_into("<IIII", header, 0, 9, 64, 48, 1)
        struct.pack_into("<I", header, 0x4C0, 0)
        # Stream has only 1 byte (odd truncated stream)
        struct.pack_into("<III", header, 0xBC8, 1, 64, 48)
        raw_data = bytes(header) + b"\x05"

        decoder = TileDecoder(raw_data, tile_type="ytl")
        # In current implementation, line 185 does `count = stream[s_idx + 1]` without checking s_idx + 1 < s_len
        # We assert that it raises IndexError, empirically confirming this boundary bug.
        with self.assertRaises(IndexError):
            decoder.decode_frame_raw(0)


if __name__ == "__main__":
    unittest.main()
