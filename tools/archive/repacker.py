"""Lossless bit-exact repacker for Data and Data.hq archives.

Binary Specifications:
- Recalculates total file count, individual file sizes, and cumulative offsets.
- Data.hq: Line-oriented XOR 0x10 with CRLF delimiters, CP949 encoded.
  Header format: `총라인수 : [<N>]\\r\\n`
  Entry format: `<filename>\\t[<size>]\\t[<offset>]\\r\\n`
- Data: Concatenation of all raw file byte streams, encoded with unconditional
  `byte ^ 0x10` across all bytes.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from tools.archive.codec import encode_data_bytes, encode_hq_bytes


def repack_archive(
    input_dir: Union[str, Path],
    output_archive_path: Union[str, Path],
    output_hq_path: Union[str, Path],
    manifest_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Repack files from an unpacked directory into Data and Data.hq archives.

    Args:
        input_dir: Directory containing the extracted files.
        output_archive_path: Path to write the repacked Data archive.
        output_hq_path: Path to write the repacked Data.hq index file.
        manifest_path: Optional explicit path to manifest.json. If None,
            looks for manifest.json inside input_dir. If still absent,
            scans input_dir recursively.

    Returns:
        True if repacking succeeded without errors.
    """
    input_dir = Path(input_dir)
    output_archive_path = Path(output_archive_path)
    output_hq_path = Path(output_hq_path)

    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {input_dir}")

    # Determine file list and order
    resolved_manifest = manifest_path or (input_dir / "manifest.json")
    if resolved_manifest and Path(resolved_manifest).exists():
        manifest_data = json.loads(Path(resolved_manifest).read_text(encoding="utf-8"))
        file_list = [f["name"] for f in manifest_data["files"]]
    else:
        # Fallback: discover files recursively (ignoring metadata folders and files)
        file_list = []
        ignore_dir_names = {"manifest.json", "catalog.json", ".git", ".gitignore", "utf8", "__pycache__"}
        for root, dirs, files in os.walk(input_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dir_names]
            for file in sorted(files):
                if file in ignore_dir_names or file.endswith(".json") or file.endswith(".bak"):
                    continue
                full_p = Path(root) / file
                rel_p = full_p.relative_to(input_dir)
                archive_name = str(rel_p).replace("/", "\\")
                file_list.append(archive_name)

    if not file_list:
        raise ValueError(f"No files found to pack in {input_dir}")

    payload_chunks: List[bytes] = []
    hq_entries: List[str] = []
    current_offset = 0

    for name in file_list:
        # Convert internal backslash path to local file path
        rel_parts = name.replace("/", "\\").split("\\")
        local_file_path = input_dir.joinpath(*rel_parts)

        if not local_file_path.exists():
            raise FileNotFoundError(f"File listed in archive not found on disk: {local_file_path}")

        file_bytes = local_file_path.read_bytes()
        file_size = len(file_bytes)

        payload_chunks.append(file_bytes)

        # Format: <name>\t[<size>]\t[<offset>]
        entry_line = f"{name}\t[{file_size}]\t[{current_offset}]"
        hq_entries.append(entry_line)

        current_offset += file_size

    # Reconstruct Data.hq
    header_line = f"총라인수 : [{len(hq_entries)}]"
    all_hq_lines = [header_line] + hq_entries
    encoded_hq = encode_hq_bytes(all_hq_lines, encoding="cp949")

    # Reconstruct Data
    plain_payload = b"".join(payload_chunks)
    encoded_data = encode_data_bytes(plain_payload)

    # Write output files
    output_archive_path.parent.mkdir(parents=True, exist_ok=True)
    output_hq_path.parent.mkdir(parents=True, exist_ok=True)

    output_archive_path.write_bytes(encoded_data)
    output_hq_path.write_bytes(encoded_hq)

    return True


def verify_bit_exact(
    orig_archive: Union[str, Path],
    repacked_archive: Union[str, Path],
) -> bool:
    """Verify that two archive files are 100% bit-exact matches."""
    orig_bytes = Path(orig_archive).read_bytes()
    repacked_bytes = Path(repacked_archive).read_bytes()
    return orig_bytes == repacked_bytes


def verify_archive_pair(
    orig_data: Union[str, Path],
    orig_hq: Union[str, Path],
    repacked_data: Union[str, Path],
    repacked_hq: Union[str, Path],
) -> Tuple[bool, Dict[str, Any]]:
    """Perform comprehensive bit-exact and structural verification between archive pairs.

    Returns:
        (is_identical, details_dict)
    """
    orig_data_p = Path(orig_data)
    orig_hq_p = Path(orig_hq)
    rep_data_p = Path(repacked_data)
    rep_hq_p = Path(repacked_hq)

    b_orig_data = orig_data_p.read_bytes()
    b_rep_data = rep_data_p.read_bytes()
    b_orig_hq = orig_hq_p.read_bytes()
    b_rep_hq = rep_hq_p.read_bytes()

    data_match = (b_orig_data == b_rep_data)
    hq_match = (b_orig_hq == b_rep_hq)
    overall_match = data_match and hq_match

    details = {
        "overall_bit_exact": overall_match,
        "data": {
            "bit_exact": data_match,
            "orig_size": len(b_orig_data),
            "repacked_size": len(b_rep_data),
            "orig_sha256": hashlib.sha256(b_orig_data).hexdigest(),
            "repacked_sha256": hashlib.sha256(b_rep_data).hexdigest(),
        },
        "hq": {
            "bit_exact": hq_match,
            "orig_size": len(b_orig_hq),
            "repacked_size": len(b_rep_hq),
            "orig_sha256": hashlib.sha256(b_orig_hq).hexdigest(),
            "repacked_sha256": hashlib.sha256(b_rep_hq).hexdigest(),
        },
    }

    if not data_match:
        for idx, (b1, b2) in enumerate(zip(b_orig_data, b_rep_data)):
            if b1 != b2:
                details["data"]["first_diff_offset"] = idx
                details["data"]["orig_byte"] = f"0x{b1:02x}"
                details["data"]["repacked_byte"] = f"0x{b2:02x}"
                break

    if not hq_match:
        for idx, (b1, b2) in enumerate(zip(b_orig_hq, b_rep_hq)):
            if b1 != b2:
                details["hq"]["first_diff_offset"] = idx
                details["hq"]["orig_byte"] = f"0x{b1:02x}"
                details["hq"]["repacked_byte"] = f"0x{b2:02x}"
                break

    return overall_match, details
