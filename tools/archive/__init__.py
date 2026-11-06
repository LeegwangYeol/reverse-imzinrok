"""Imjinrok 2+ Dawn Archive & Index Toolkit (tools.archive).

Exports:
- unpack_archive: Unpack all 109 internal files from Data using Data.hq
- repack_archive: Lossless repacker generating valid Data and Data.hq archives
- verify_bit_exact: Binary comparison verifying 100% bit-exact equivalence
- verify_archive_pair: Structural and cryptographic hash verification for Data + Data.hq
- build_catalog: Generates structured JSON catalog of tables, strings, and sprites
- xor_bytes: Byte-wise XOR codec
- decode_data_bytes / encode_data_bytes: Full Data stream XOR 0x10 codec
- decode_hq_bytes / encode_hq_bytes: CRLF-preserving Data.hq index codec
- FileInfo / ArchiveEntry: Data models for archive metadata
"""

from tools.archive.catalog import (
    build_catalog,
    parse_exp_level_table,
    parse_img_file_table,
    parse_key_value_table,
    parse_text_kor_table,
    parse_tile_file_table,
)
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

__all__ = [
    "unpack_archive",
    "repack_archive",
    "verify_bit_exact",
    "verify_archive_pair",
    "build_catalog",
    "xor_bytes",
    "decode_data_bytes",
    "encode_data_bytes",
    "decode_hq_bytes",
    "encode_hq_bytes",
    "decode_hq_line",
    "encode_hq_line",
    "verify_data_roundtrip",
    "verify_hq_roundtrip",
    "FileInfo",
    "ArchiveEntry",
    "detect_encoding",
    "categorize_file",
    "parse_hq_entries",
    "parse_img_file_table",
    "parse_text_kor_table",
    "parse_exp_level_table",
    "parse_key_value_table",
    "parse_tile_file_table",
]
