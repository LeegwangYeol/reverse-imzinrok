"""
spr_encoder.py - Version 9 Sprite Encoder/Decoder for Imjinrok 2+.
Supports 0xFE transparent-skip RLE encoding, header packing, and frame injection.
"""

from __future__ import annotations

import os
import stat
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

SPR_HEADER_SIZE = 3060
SPR_VERSION = 9


def encode_frame_rle_row_aligned(canvas: np.ndarray) -> bytes:
    """
    Encode a 2D (height, width) uint8 array into row-aligned Joymax 0xFE skip RLE.
    Ensures that transparent runs do not cross scanline boundaries.
    """
    out = bytearray()
    h, w = canvas.shape
    for y in range(h):
        row = canvas[y]
        x = 0
        while x < w:
            if row[x] == 0:
                run = 0
                while x + run < w and row[x + run] == 0 and run < 255:
                    run += 1
                out.append(0xFE)
                out.append(run)
                x += run
            else:
                val = int(row[x])
                if val == 0xFE:
                    val = 244  # Avoid conflicting with RLE control marker
                out.append(val)
                x += 1
    return bytes(out)


def decode_frame_rle_row_aligned(stream: bytes, width: int, height: int) -> np.ndarray:
    """
    Decode a 0xFE skip RLE byte stream into a 2D (height, width) uint8 array.
    """
    canvas = np.zeros((height, width), dtype=np.uint8)
    s_ptr = 0
    s_len = len(stream)
    for y in range(height):
        x = 0
        while x < width and s_ptr < s_len:
            byte_val = stream[s_ptr]
            s_ptr += 1
            if byte_val == 0xFE:
                if s_ptr < s_len:
                    skip = stream[s_ptr]
                    s_ptr += 1
                    x += skip
            else:
                canvas[y, x] = byte_val
                x += 1
    return canvas


def build_spr_v9(width: int, height: int, frames: List[np.ndarray]) -> bytes:
    """
    Construct a complete Version 9 .spr binary with a 3,060-byte header and RLE payload.
    """
    frame_count = len(frames)
    encoded_streams: List[bytes] = []
    offsets: List[int] = []
    sizes_low16: List[int] = []
    cur_off = 0

    for f_canvas in frames:
        rle = encode_frame_rle_row_aligned(f_canvas)
        offsets.append(cur_off)
        sizes_low16.append(len(rle) & 0xFFFF)
        encoded_streams.append(rle)
        cur_off += len(rle)

    data_size = cur_off
    cols = 8
    rows = (frame_count + cols - 1) // cols
    atlas_w = width * cols
    atlas_h = height * rows

    header = bytearray(SPR_HEADER_SIZE)
    # 0x000: version, width, height, frame_count
    struct.pack_into("<IIII", header, 0x000, SPR_VERSION, width, height, frame_count)
    # 0x970: size table (or hotspot anchors) - pack sizes first, capped at min(frame_count, 300)
    sz_count = min(frame_count, 300)
    struct.pack_into(f"<{sz_count}H", header, 0x970, *sizes_low16[:sz_count])
    # 0x4C0: offsets table - pack offsets second so frame offsets >= 300 take precedence over 0x970
    struct.pack_into(f"<{frame_count}I", header, 0x4C0, *offsets)
    # 0xBC8: data_size, atlas_w, atlas_h
    struct.pack_into("<III", header, 0xBC8, data_size, atlas_w, atlas_h)

    return bytes(header) + b"".join(encoded_streams)


def inject_frames_into_spr_file(
    spr_path: Path,
    new_frames: Dict[int, bytes],
    expected_width: int,
    expected_height: int,
    target_frame_count: Optional[int] = None,
) -> int:
    """
    Inject or replace specific frame indices in an existing .spr file.
    If target_frame_count is specified, fixes the output frame count to exactly that number.
    Otherwise expands frame_count if target frame indices exceed current frame count.
    Preserves all existing unreferenced frames within total_frames.
    """
    spr_path = Path(spr_path)
    if not spr_path.exists():
        raise FileNotFoundError(f"Sprite file not found: {spr_path}")

    raw = bytearray(spr_path.read_bytes())
    ver, w, h, fc = struct.unpack("<IIII", raw[:16])
    if ver != SPR_VERSION:
        raise ValueError(f"Expected Version 9 .spr, got {ver} for {spr_path}")

    data_size, aw, ah = struct.unpack("<III", raw[0xBC8:0xBD4])
    offs = list(struct.unpack(f"<{fc}I", raw[0x4C0 : 0x4C0 + 4 * fc]))
    szs = list(struct.unpack(f"<{fc}H", raw[0x970 : 0x970 + 2 * fc]))

    if target_frame_count is not None:
        total_frames = target_frame_count
    else:
        target_max_frame = max(new_frames.keys())
        total_frames = max(fc, target_max_frame + 1)

    frame_chunks: List[bytes] = []
    for i in range(min(fc, total_frames)):
        start = SPR_HEADER_SIZE + offs[i]
        end = (SPR_HEADER_SIZE + offs[i + 1]) if (i + 1 < fc) else (SPR_HEADER_SIZE + data_size)
        frame_chunks.append(bytes(raw[start:end]))

    # Blank RLE fallback for new extended slots
    blank_line = b"\xFE" + bytes([w])
    blank_rle = blank_line * h
    while len(frame_chunks) < total_frames:
        frame_chunks.append(blank_rle)

    for f_idx, rle_bytes in new_frames.items():
        if f_idx < total_frames:
            frame_chunks[f_idx] = rle_bytes

    new_offs: List[int] = []
    new_szs: List[int] = []
    new_body = bytearray()
    for chunk in frame_chunks:
        new_offs.append(len(new_body))
        new_szs.append(len(chunk) & 0xFFFF)
        new_body.extend(chunk)

    cols = 8
    rows = (total_frames + cols - 1) // cols
    new_aw = max(aw, w * cols)
    new_ah = max(ah, h * rows)

    header = bytearray(raw[:SPR_HEADER_SIZE])
    struct.pack_into("<I", header, 0x00C, total_frames)
    # 0x970: size table (capped at 300 entries to not overflow 0xBC8)
    sz_count = min(total_frames, 300)
    struct.pack_into(f"<{sz_count}H", header, 0x970, *new_szs[:sz_count])
    # 0x4C0: offsets table - packed second so offsets >= 300 (starting at 0x970) are not clobbered
    struct.pack_into(f"<{total_frames}I", header, 0x4C0, *new_offs)
    struct.pack_into("<III", header, 0xBC8, len(new_body), new_aw, new_ah)

    out_bytes = bytes(header) + bytes(new_body)

    try:
        os.chmod(spr_path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass

    spr_path.write_bytes(out_bytes)
    return total_frames
