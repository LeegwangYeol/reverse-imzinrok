"""
Test Suite for R2: Data.hq and Data Archive Codec, Unpacker, Repacker, and Catalog
Imjinrok 2+ Dawn Modding Toolkit
"""

import os
import unittest
from pathlib import Path

from tests.conftest import (
    DATA_FILE,
    DATA_HQ_FILE,
    DAWN_DIR,
    ORIGINAL_DATA_SIZE,
    ORIGINAL_DATA_HQ_SIZE,
    get_temp_dir,
    sha256_file,
)
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
    ArchiveEntry,
)
from tools.archive.repacker import (
    repack_archive,
    verify_bit_exact,
    verify_archive_pair,
)
from tools.archive.catalog import (
    parse_img_file_table,
    parse_text_kor_table,
    parse_exp_level_table,
    parse_key_value_table,
)


class TestArchiveCodec(unittest.TestCase):
    """Tier 1: Unit tests for XOR 0x10 Codec."""

    def test_xor_stream_involution(self):
        """Verify that XOR 0x10 is an involution (f(f(x)) == x)."""
        sample_data = b"Hello, Imjinrok 2+ Dawn \x00\x0d\x0a\xff\x10\xef"
        encoded = encode_data_bytes(sample_data)
        self.assertNotEqual(encoded, sample_data)
        decoded = decode_data_bytes(encoded)
        self.assertEqual(decoded, sample_data)
        self.assertTrue(verify_data_roundtrip(sample_data))

    def test_unconditional_xor_on_crlf_in_data(self):
        """Verify that \\r (0x0D) and \\n (0x0A) are unconditionally XORed in Data."""
        crlf = b"\r\n"
        encoded_crlf = encode_data_bytes(crlf)
        self.assertEqual(encoded_crlf, b"\x1d\x1a")
        self.assertEqual(decode_data_bytes(encoded_crlf), crlf)

    def test_line_oriented_hq_codec_preserves_crlf(self):
        """Verify that Data.hq encoding preserves CRLF delimiters as plaintext 0x0D 0x0A."""
        lines = ["총라인수 : [2]", "Test.txt\t[100]\t[0]"]
        encoded_hq = encode_hq_bytes(lines, encoding="cp949")
        # Ensure raw 0x0D 0x0A appears in encoded output
        self.assertIn(b"\r\n", encoded_hq)
        self.assertTrue(encoded_hq.endswith(b"\r\n"))

        # Roundtrip decode
        decoded_lines = decode_hq_bytes(encoded_hq, encoding="cp949")
        self.assertEqual(decoded_lines, lines)
        self.assertTrue(verify_hq_roundtrip(encoded_hq, encoding="cp949"))


class TestArchiveUnpacker(unittest.TestCase):
    """Tier 1 & Tier 2: Unpacker tests on Data.hq and Data."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("archive_unpack_test_")
        cls.extracted_files = unpack_archive(
            archive_path=DATA_FILE,
            hq_path=DATA_HQ_FILE,
            output_dir=cls.temp_dir,
            write_manifest=True,
            export_utf8=True,
        )

    def test_unpack_file_count_and_sizes(self):
        """Verify that exactly 109 files are unpacked and cumulative size equals 230,202 bytes."""
        self.assertEqual(len(self.extracted_files), 109)
        total_size = sum(f.size for f in self.extracted_files)
        self.assertEqual(
            total_size,
            ORIGINAL_DATA_SIZE,
            f"Expected sum of unpacked file sizes to be {ORIGINAL_DATA_SIZE}, got {total_size}",
        )

    def test_all_extracted_files_exist_on_disk(self):
        """Verify that all 109 extracted files exist and have exact byte sizes."""
        for finfo in self.extracted_files:
            file_path = self.temp_dir / finfo.local_path
            self.assertTrue(file_path.exists(), f"Extracted file missing: {file_path}")
            self.assertEqual(
                file_path.stat().st_size,
                finfo.size,
                f"File size mismatch on disk for {finfo.name}",
            )

    def test_manifest_json_generation(self):
        """Verify that manifest.json is generated with valid structure."""
        manifest_path = self.temp_dir / "manifest.json"
        self.assertTrue(manifest_path.exists())
        import json
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["total_files"], 109)
        self.assertEqual(manifest["total_size"], ORIGINAL_DATA_SIZE)
        self.assertEqual(len(manifest["files"]), 109)

    def test_table_files_readable_content(self):
        """Verify key decrypted table files: Text_kor.dat, ImgFile.dat, ExpForLevelUp.dat."""
        # 1. Text_kor.dat (CP949)
        text_kor_path = self.temp_dir / "Text_kor.dat"
        self.assertTrue(text_kor_path.exists())
        text_kor_content = text_kor_path.read_text(encoding="cp949")
        parsed_text = parse_text_kor_table(text_kor_content)
        self.assertGreater(len(parsed_text), 500, "Expected > 500 string table entries")
        # Check presence of known units
        all_strings = " ".join(item["text"] for item in parsed_text)
        self.assertIn("조선", all_strings)

        # 2. ImgFile.dat (CP949)
        img_file_path = self.temp_dir / "ImgFile.dat"
        self.assertTrue(img_file_path.exists())
        img_content = img_file_path.read_text(encoding="cp949")
        parsed_sprites = parse_img_file_table(img_content)
        self.assertGreater(len(parsed_sprites), 200, "Expected > 200 sprite definitions")

        # 3. ExpForLevelUp.dat
        exp_path = self.temp_dir / "ExpForLevelUp.dat"
        self.assertTrue(exp_path.exists())
        exp_content = exp_path.read_text(encoding="cp949")
        parsed_exp = parse_exp_level_table(exp_content)
        self.assertEqual(len(parsed_exp), 99, "Expected 99 level-up progression rows (levels 1-99)")
        self.assertEqual(parsed_exp[0]["level"], 1)
        self.assertEqual(parsed_exp[-1]["level"], 99)

    def test_corrupted_hq_rejection(self):
        """Tier 2: Corrupted Data.hq must raise ValueError."""
        # Invalid header
        bad_hq = b"Invalid Header Line\r\n"
        with self.assertRaises(ValueError):
            parse_hq_entries(bad_hq)

        # Gap in offsets
        bad_lines = [
            "총라인수 : [2]",
            "file1.txt\t[100]\t[0]",
            "file2.txt\t[50]\t[150]",  # Expected offset 100, not 150
        ]
        bad_hq_bytes = encode_hq_bytes(bad_lines, encoding="cp949")
        with self.assertRaises(ValueError):
            parse_hq_entries(bad_hq_bytes)


class TestArchiveRoundTripExact(unittest.TestCase):
    """Tier 4: 100% Bit-Exact Round-Trip Match Verification."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("archive_roundtrip_test_")
        cls.unpacked_dir = cls.temp_dir / "unpacked"
        cls.repacked_dir = cls.temp_dir / "repacked"

        # Unpack original
        unpack_archive(
            archive_path=DATA_FILE,
            hq_path=DATA_HQ_FILE,
            output_dir=cls.unpacked_dir,
            write_manifest=True,
        )

        # Repack into new archives
        cls.repacked_data = cls.repacked_dir / "Data"
        cls.repacked_hq = cls.repacked_dir / "Data.hq"

        repack_archive(
            input_dir=cls.unpacked_dir,
            output_archive_path=cls.repacked_data,
            output_hq_path=cls.repacked_hq,
        )

    def test_bit_exact_data_match(self):
        """Verify that repacked Data matches original YM\\dawn\\Data 100% byte-for-byte."""
        orig_bytes = DATA_FILE.read_bytes()
        repacked_bytes = self.repacked_data.read_bytes()

        self.assertEqual(len(repacked_bytes), len(orig_bytes))
        self.assertEqual(len(repacked_bytes), ORIGINAL_DATA_SIZE)
        self.assertEqual(
            sha256_file(self.repacked_data),
            sha256_file(DATA_FILE),
            "SHA-256 hash mismatch between original and repacked Data archive!",
        )
        self.assertTrue(verify_bit_exact(DATA_FILE, self.repacked_data))

    def test_bit_exact_data_hq_match(self):
        """Verify that repacked Data.hq matches original YM\\dawn\\Data.hq 100% byte-for-byte."""
        orig_hq_bytes = DATA_HQ_FILE.read_bytes()
        repacked_hq_bytes = self.repacked_hq.read_bytes()

        self.assertEqual(len(repacked_hq_bytes), len(orig_hq_bytes))
        self.assertEqual(len(repacked_hq_bytes), ORIGINAL_DATA_HQ_SIZE)
        self.assertEqual(
            sha256_file(self.repacked_hq),
            sha256_file(DATA_HQ_FILE),
            "SHA-256 hash mismatch between original and repacked Data.hq index!",
        )
        self.assertTrue(verify_bit_exact(DATA_HQ_FILE, self.repacked_hq))

    def test_verify_archive_pair_helper(self):
        """Verify that verify_archive_pair returns overall_bit_exact == True."""
        is_identical, details = verify_archive_pair(
            orig_data=DATA_FILE,
            orig_hq=DATA_HQ_FILE,
            repacked_data=self.repacked_data,
            repacked_hq=self.repacked_hq,
        )
        self.assertTrue(is_identical, f"Archive pair verification failed: {details}")
        self.assertTrue(details["overall_bit_exact"])
        self.assertTrue(details["data"]["bit_exact"])
        self.assertTrue(details["hq"]["bit_exact"])


if __name__ == "__main__":
    unittest.main()
