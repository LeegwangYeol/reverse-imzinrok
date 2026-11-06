"""
Version 9 Tile Decoder (.ytl and .ypr) for Imjinrok 2+ (조선의 반격: 여명).

Specification:
- Header: Fixed 3,060 bytes (0xBF4), identical Version 9 container header as .spr.
  - 0x000: uint32 version (9)
  - 0x004: uint32 width (usually 64 for .ytl, 80 for .ypr)
  - 0x008: uint32 height (usually 48 for .ytl, 60 for .ypr)
  - 0x00C: uint32 frame_count (number of tile variants/frames)
  - 0x4C0..: uint32 frame_offsets[frame_count]
  - 0xBC8: uint32 data_size
  - 0xBCC: uint32 atlas_width
  - 0xBD0: uint32 atlas_height

Decoding Algorithms:
1. Algorithm B: Single-Span Diamond Line Encoding (.ytl)
   - For each line y in 0..height-1:
     - skip = stream[s_idx++]
     - count = stream[s_idx++]
     - if count > 0: copy stream[s_idx .. s_idx+count] to canvas[y * width + skip]
     - s_idx += count
     - Rest of line (width - skip - count) remains transparent (0x00).
   - If stream ends before height lines, remaining rows are transparent.

2. Algorithm C: Multi-Span Hill Line Encoding (.ypr)
   - For each line y in 0..height-1:
     - curr_x = 0
     - while s_idx + 1 < len(stream):
       - skip = stream[s_idx++]
       - count = stream[s_idx++]
       - curr_x += skip
       - if count == 0: break line
       - copy stream[s_idx .. s_idx+count] to canvas[y * width + curr_x]
       - s_idx += count
       - curr_x += count
   - If stream ends before height lines, remaining rows are transparent.
"""

from __future__ import annotations
import json
import os
import struct
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Union, Optional, Any
from PIL import Image
import numpy as np

from tools.assets.palette import Palette, convert_pal_to_rgba

TILE_HEADER_SIZE = 3060


@dataclass
class TileFrameInfo:
    """Metadata for a single tile variant/frame."""
    index: int
    offset: int
    data_length: int
    width: int
    height: int
    file_name: Optional[str] = None


@dataclass
class TileMetadata:
    """Metadata for a decoded tile file."""
    name: str
    tile_type: str  # 'ytl' or 'ypr'
    version: int
    width: int
    height: int
    frame_count: int
    atlas_width: int
    atlas_height: int
    data_size: int
    frames: List[TileFrameInfo] = field(default_factory=list)
    atlas_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to JSON-serializable dictionary."""
        return asdict(self)

    def save_json(self, out_path: Union[str, os.PathLike]) -> str:
        """Write metadata to JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return str(out_path)


class TileDecoder:
    """Decodes Version 9 tile files (.ytl and .ypr) into PNG images and sheets."""

    def __init__(self, data: bytes, name: str = "tile", tile_type: Optional[str] = None):
        if len(data) < TILE_HEADER_SIZE:
            raise ValueError(
                f"File data too short for Tile header: expected >= {TILE_HEADER_SIZE} bytes, got {len(data)}"
            )

        self.name = name
        self.raw_data = data
        self.header = data[:TILE_HEADER_SIZE]
        self.tile_type = tile_type.lower() if tile_type else "ytl"

        # Parse header
        self.version, self.width, self.height, self.frame_count = struct.unpack(
            "<IIII", self.header[:16]
        )
        if self.version != 9:
            raise ValueError(f"Unsupported Tile version: expected 9, got {self.version}")
        if self.width <= 0 or self.height <= 0 or self.frame_count <= 0:
            raise ValueError(
                f"Invalid Tile dimensions: {self.width}x{self.height}, frames={self.frame_count}"
            )

        self.data_size, self.atlas_width, self.atlas_height = struct.unpack(
            "<III", self.header[0xBC8:0xBD4]
        )

        # Parse frame offsets table at 0x4C0
        raw_offsets = struct.unpack(
            f"<{self.frame_count}I",
            self.header[0x4C0 : 0x4C0 + 4 * self.frame_count],
        )
        self.offsets = list(raw_offsets)

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike], tile_type: Optional[str] = None) -> TileDecoder:
        name = os.path.splitext(os.path.basename(path))[0]
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if tile_type is None:
            tile_type = ext if ext in ("ytl", "ypr") else "ytl"
        with open(path, "rb") as f:
            data = f.read()
        return cls(data, name=name, tile_type=tile_type)

    def decode_frame_raw(self, frame_index: int) -> bytearray:
        """
        Decompress a single frame's line-span stream into raw 8-bit index pixels.
        Dispatches to single-span (.ytl) or multi-span (.ypr) decoder.
        """
        if frame_index < 0 or frame_index >= self.frame_count:
            raise IndexError(f"Frame index {frame_index} out of range (0..{self.frame_count - 1})")

        start_off = self.offsets[frame_index]
        if frame_index + 1 < self.frame_count:
            end_off = self.offsets[frame_index + 1]
        else:
            end_off = self.data_size

        stream = self.raw_data[TILE_HEADER_SIZE + start_off : TILE_HEADER_SIZE + end_off]
        canvas = bytearray(self.width * self.height)
        s_len = len(stream)
        s_idx = 0

        if self.tile_type == "ypr":
            # Multi-Span Hill Algorithm
            for y in range(self.height):
                if s_idx >= s_len:
                    break
                curr_x = 0
                while s_idx + 1 < s_len:
                    skip = stream[s_idx]
                    count = stream[s_idx + 1]
                    s_idx += 2
                    curr_x += skip

                    if count == 0:
                        break

                    pixel_end = s_idx + count
                    dest_start = y * self.width + curr_x
                    dest_end = dest_start + count
                    if pixel_end <= s_len and dest_end <= len(canvas):
                        canvas[dest_start:dest_end] = stream[s_idx:pixel_end]

                    s_idx += count
                    curr_x += count
        else:
            # Single-Span Diamond Algorithm (.ytl)
            for y in range(self.height):
                if s_idx >= s_len:
                    break
                skip = stream[s_idx]
                count = stream[s_idx + 1]
                s_idx += 2

                if count > 0:
                    pixel_end = s_idx + count
                    dest_start = y * self.width + skip
                    dest_end = dest_start + count
                    if pixel_end <= s_len and dest_end <= len(canvas):
                        canvas[dest_start:dest_end] = stream[s_idx:pixel_end]
                    s_idx += count

        return canvas

    def decode_frame_image(self, frame_index: int, palette: Palette) -> Image.Image:
        """Decode a single tile frame into a transparent PIL RGBA Image."""
        raw_pixels = self.decode_frame_raw(frame_index)
        lut = palette.to_lut_array()
        rgba_buffer = lut[np.frombuffer(raw_pixels, dtype=np.uint8)].tobytes()
        return Image.frombytes("RGBA", (self.width, self.height), rgba_buffer)

    def export(
        self,
        output_dir: Union[str, os.PathLike],
        palette: Union[Palette, str, os.PathLike],
        export_frames: bool = True,
        export_atlas: bool = True,
    ) -> TileMetadata:
        """
        Export all tile frames as PNG files and metadata JSON.
        """
        os.makedirs(output_dir, exist_ok=True)

        if isinstance(palette, (str, os.PathLike)):
            pal = Palette.from_file(palette)
        else:
            pal = palette

        lut = pal.to_lut_array()
        frames_info: List[TileFrameInfo] = []
        decoded_images: List[Image.Image] = []

        for f_idx in range(self.frame_count):
            raw_pixels = self.decode_frame_raw(f_idx)
            rgba_buffer = lut[np.frombuffer(raw_pixels, dtype=np.uint8)].tobytes()
            frame_img = Image.frombytes("RGBA", (self.width, self.height), rgba_buffer)
            decoded_images.append(frame_img)

            frame_file_name: Optional[str] = None
            if export_frames:
                frame_file_name = f"{self.name}_frame_{f_idx:03d}.png"
                frame_path = os.path.join(output_dir, frame_file_name)
                frame_img.save(frame_path, "PNG")

            off = self.offsets[f_idx]
            next_off = self.offsets[f_idx + 1] if f_idx + 1 < self.frame_count else self.data_size
            data_len = next_off - off

            info = TileFrameInfo(
                index=f_idx,
                offset=off,
                data_length=data_len,
                width=self.width,
                height=self.height,
                file_name=frame_file_name,
            )
            frames_info.append(info)

        # Generate Atlas sheet if requested and valid
        atlas_file_name: Optional[str] = None
        if export_atlas and self.atlas_width > 0 and self.atlas_height > 0:
            cols = self.atlas_width // self.width
            rows = self.atlas_height // self.height

            if cols > 0 and rows > 0 and cols * rows >= self.frame_count:
                atlas_img = Image.new("RGBA", (self.atlas_width, self.atlas_height), (0, 0, 0, 0))
                for idx, f_img in enumerate(decoded_images):
                    col = idx % cols
                    row = idx // cols
                    atlas_img.paste(f_img, (col * self.width, row * self.height))

                atlas_file_name = f"{self.name}_atlas.png"
                atlas_path = os.path.join(output_dir, atlas_file_name)
                atlas_img.save(atlas_path, "PNG")

        metadata = TileMetadata(
            name=self.name,
            tile_type=self.tile_type,
            version=self.version,
            width=self.width,
            height=self.height,
            frame_count=self.frame_count,
            atlas_width=self.atlas_width,
            atlas_height=self.atlas_height,
            data_size=self.data_size,
            frames=frames_info,
            atlas_file=atlas_file_name,
        )

        json_path = os.path.join(output_dir, f"{self.name}_meta.json")
        metadata.save_json(json_path)

        return metadata


def decode_ytl(
    ytl_path: Union[str, os.PathLike],
    pal_path: Union[str, os.PathLike, Palette],
    output_dir: Union[str, os.PathLike],
    export_atlas: bool = True,
    export_frames: bool = True,
) -> TileMetadata:
    """
    Standard interface contract:
    Decodes a Version 9 diamond isometric .ytl tile file into PNGs and metadata.
    """
    decoder = TileDecoder.from_file(ytl_path, tile_type="ytl")
    return decoder.export(
        output_dir=output_dir,
        palette=pal_path,
        export_frames=export_frames,
        export_atlas=export_atlas,
    )


def decode_ypr(
    ypr_path: Union[str, os.PathLike],
    pal_path: Union[str, os.PathLike, Palette],
    output_dir: Union[str, os.PathLike],
    export_atlas: bool = True,
    export_frames: bool = True,
) -> TileMetadata:
    """
    Standard interface contract:
    Decodes a Version 9 multi-span hill .ypr tile file into PNGs and metadata.
    """
    decoder = TileDecoder.from_file(ypr_path, tile_type="ypr")
    return decoder.export(
        output_dir=output_dir,
        palette=pal_path,
        export_frames=export_frames,
        export_atlas=export_atlas,
    )


def decode_tile(
    tile_path: Union[str, os.PathLike],
    pal_path: Union[str, os.PathLike, Palette],
    output_dir: Union[str, os.PathLike],
    export_atlas: bool = True,
    export_frames: bool = True,
) -> TileMetadata:
    """Auto-detects .ytl or .ypr and decodes into PNGs and metadata."""
    ext = os.path.splitext(tile_path)[1].lower().lstrip(".")
    if ext == "ypr":
        return decode_ypr(
            tile_path, pal_path, output_dir, export_atlas=export_atlas, export_frames=export_frames
        )
    return decode_ytl(
        tile_path, pal_path, output_dir, export_atlas=export_atlas, export_frames=export_frames
    )
