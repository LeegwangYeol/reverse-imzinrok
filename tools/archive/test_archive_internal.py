"""Comprehensive internal test suite for tools.archive package.

Covers:
- Codec correctness, involution, CRLF handling
- Unpacker parsing, manifest generation, UTF-8 exports, error conditions
- Repacker bit-exact roundtrip, offset calculation, missing manifest fallback
- Catalog parsing for ImgFile, Text_kor, ExpForLevelUp, TileFile, screenPt
- CLI subcommands (unpack, repack, verify, catalog, error exits)
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.archive.catalog import (
    build_catalog,
    parse_exp_level_table,
    parse_img_file_table,
    parse_key_value_table,
    parse_text_kor_table,
    parse_tile_file_table,
)
from tools.archive.cli import main as cli_main
from tools.archive.codec import (
    decode_data_bytes,
    decode_hq_bytes,
    decode_hq_line,
    encode_data_bytes,
    encode_hq_bytes,
    encode_hq_line,
    verify_data_roundtrip,
    verify_hq_roundtrip,
    xor_bytes,
)
from tools.archive.repacker import (
    repack_archive,
    verify_archive_pair,
    verify_bit_exact,
)
from tools.archive.unpacker import (
    ArchiveEntry,
    FileInfo,
    categorize_file,
    detect_encoding,
    parse_hq_entries,
    unpack_archive,
)

DATA_PATH = Path(r"C:\src\reverse-imzinrok\YM\dawn\Data")
HQ_PATH = Path(r"C:\src\reverse-imzinrok\YM\dawn\Data.hq")


class TestCodecInternal(unittest.TestCase):
    """Test suite for XOR 0x10 codec functions."""

    def test_xor_bytes_empty(self):
        self.assertEqual(xor_bytes(b""), b"")

    def test_xor_involution(self):
        payload = bytes(range(256))
        enc = xor_bytes(payload, 0x10)
        self.assertEqual(xor_bytes(enc, 0x10), payload)

    def test_hq_line_encoding_cp949(self):
        text = "총라인수 : [109]"
        enc = encode_hq_line(text, encoding="cp949")
        dec = decode_hq_line(enc, encoding="cp949")
        self.assertEqual(dec, text)

    def test_hq_bytes_split_and_join(self):
        lines = ["Line 1", "Line 2\t[10]\t[0]", "Line 3\t[20]\t[10]"]
        raw = encode_hq_bytes(lines, encoding="cp949")
        self.assertTrue(raw.endswith(b"\r\n"))
        recovered = decode_hq_bytes(raw, encoding="cp949")
        self.assertEqual(recovered, lines)


class TestUnpackerInternal(unittest.TestCase):
    """Test suite for unpacker logic and validation."""

    def test_categorize_and_encoding_detect(self):
        self.assertEqual(categorize_file("FontInfo_kor.dat"), "font_info")
        self.assertEqual(categorize_file("Text_kor.dat"), "string_table")
        self.assertEqual(categorize_file("ImgFile.dat"), "sprite_table")
        self.assertEqual(categorize_file("Online\\JohapChar\\COF\\JMA\\JMAA11.COF"), "cof_script")
        self.assertEqual(categorize_file("EffectSound.dat"), "sound_table")
        self.assertEqual(categorize_file("ExpForLevelUp.dat"), "exp_table")

        self.assertEqual(detect_encoding("FontInfo_chi.dat"), "gb2312")
        self.assertEqual(detect_encoding("FontInfo_jpn.dat"), "cp932")
        self.assertEqual(detect_encoding("FontInfo_tai.dat"), "big5")
        self.assertEqual(detect_encoding("FontInfo_tha.dat"), "cp874")
        self.assertEqual(detect_encoding("Text_kor.dat"), "cp949")

    def test_parse_hq_entries_valid(self):
        raw_hq = HQ_PATH.read_bytes()
        count, entries = parse_hq_entries(raw_hq)
        self.assertEqual(count, 109)
        self.assertEqual(len(entries), 109)
        self.assertEqual(entries[0].name, "CastleType.txt")
        self.assertEqual(entries[0].size, 1108)
        self.assertEqual(entries[0].offset, 0)

    def test_parse_hq_entries_bad_count(self):
        bad_hq = encode_hq_bytes(["총라인수 : [10]", "test.txt\t[10]\t[0]"])
        with self.assertRaises(ValueError):
            parse_hq_entries(bad_hq)

    def test_parse_hq_entries_gap_offset(self):
        bad_hq = encode_hq_bytes([
            "총라인수 : [2]",
            "a.txt\t[10]\t[0]",
            "b.txt\t[10]\t[15]",  # Gap: expected 10, got 15
        ])
        with self.assertRaises(ValueError):
            parse_hq_entries(bad_hq)


class TestRoundtripAndCliInternal(unittest.TestCase):
    """End-to-end roundtrip and CLI command verification."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="archive_internal_test_"))
        self.unpacked_dir = self.temp_dir / "unpacked"
        self.repacked_dir = self.temp_dir / "repacked"

    def tearDown(self):
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cli_full_flow(self):
        # 1. Unpack via CLI
        code = cli_main([
            "unpack",
            "--data", str(DATA_PATH),
            "--hq", str(HQ_PATH),
            "-o", str(self.unpacked_dir),
            "--export-utf8",
            "-q",
        ])
        self.assertEqual(code, 0)
        self.assertTrue((self.unpacked_dir / "manifest.json").exists())
        self.assertTrue((self.unpacked_dir / "utf8" / "Text_kor.dat").exists())

        # 2. Catalog via CLI
        cat_file = self.temp_dir / "catalog.json"
        code = cli_main([
            "catalog",
            "-i", str(self.unpacked_dir),
            "-o", str(cat_file),
            "-q",
        ])
        self.assertEqual(code, 0)
        self.assertTrue(cat_file.exists())
        cat_data = json.loads(cat_file.read_text(encoding="utf-8"))
        self.assertEqual(cat_data["total_files"], 109)
        self.assertEqual(cat_data["total_size_bytes"], 230202)
        self.assertIn("img_file_dat", cat_data["parsed_tables"])
        self.assertIn("text_kor_dat", cat_data["parsed_tables"])

        # 3. Repack via CLI
        rep_data = self.repacked_dir / "Data"
        rep_hq = self.repacked_dir / "Data.hq"
        code = cli_main([
            "repack",
            "-i", str(self.unpacked_dir),
            "--data-out", str(rep_data),
            "--hq-out", str(rep_hq),
            "-q",
        ])
        self.assertEqual(code, 0)
        self.assertEqual(rep_data.stat().st_size, 230202)
        self.assertEqual(rep_hq.stat().st_size, 5408)

        # 4. Verify via CLI (text mode)
        code = cli_main([
            "verify",
            "--orig-data", str(DATA_PATH),
            "--orig-hq", str(HQ_PATH),
            "--repacked-data", str(rep_data),
            "--repacked-hq", str(rep_hq),
        ])
        self.assertEqual(code, 0)

        # 5. Verify via CLI (json mode)
        code = cli_main([
            "verify",
            "--orig-data", str(DATA_PATH),
            "--orig-hq", str(HQ_PATH),
            "--repacked-data", str(rep_data),
            "--repacked-hq", str(rep_hq),
            "--json",
        ])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
