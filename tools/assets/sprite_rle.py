"""
Version 9 Sprite Decoder (.spr) for Imjinrok 2+ (조선의 반격: 여명).

Specification:
- Header: Fixed 3,060 bytes (0xBF4).
  - 0x000: uint32 version (must be 9)
  - 0x004: uint32 width (frame pixel width)
  - 0x008: uint32 height (frame pixel height)
  - 0x00C: uint32 frame_count (1..300)
  - 0x010..0x4BF: Reserved padding (1,168 bytes)
  - 0x4C0..: uint32 frame_offsets[frame_count] (relative to 3,060)
  - 0x970..: int16 frame_sizes / hotspots[frame_count]
  - 0xBC8: uint32 data_size
  - 0xBCC: uint32 atlas_width (cols * width)
  - 0xBD0: uint32 atlas_height (rows * height)
  - 0xBD4..0xBF3: Reserved
- Pixel Stream:
  - Located at 3060 + frame_offsets[i].
  - 0xFE Transparent Skip RLE:
    - byte == 0xFE: next byte is skip count; skip that many pixels (transparent 0x00).
    - byte != 0xFE: literal 8-bit palette index pixel.
- Output:
  - Individual transparent PNG frames.
  - Optional composite Atlas sprite sheet (cols x rows).
  - Frame metadata JSON with dimensions, offsets, and hotspot anchors.
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

SPR_HEADER_SIZE = 3060


@dataclass
class FrameInfo:
    """Metadata for a single sprite frame."""
    index: int
    offset: int
    data_length: int
    width: int
    height: int
    hotspot_x: int
    hotspot_y: int
    file_name: Optional[str] = None


@dataclass
class SpriteMetadata:
    """Metadata for a decoded sprite file."""
    name: str
    version: int
    width: int
    height: int
    frame_count: int
    atlas_width: int
    atlas_height: int
    data_size: int
    frames: List[FrameInfo] = field(default_factory=list)
    hotspots: List[Dict[str, int]] = field(default_factory=list)
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


class SpriteDecoder:
    """Decodes Version 9 sprite files (.spr) into PNG frames and sprite sheets."""

    def __init__(self, data: bytes, name: str = "sprite"):
        if len(data) < SPR_HEADER_SIZE:
            raise ValueError(
                f"File data too short for SPR header: expected >= {SPR_HEADER_SIZE} bytes, got {len(data)}"
            )

        self.name = name
        self.raw_data = data
        self.header = data[:SPR_HEADER_SIZE]

        # Parse header
        self.version, self.width, self.height, self.frame_count = struct.unpack(
            "<IIII", self.header[:16]
        )
        if self.version != 9:
            raise ValueError(f"Unsupported SPR version: expected 9, got {self.version}")
        if self.width <= 0 or self.height <= 0 or self.frame_count <= 0:
            raise ValueError(
                f"Invalid SPR dimensions: {self.width}x{self.height}, frames={self.frame_count}"
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

        # Parse hotspots / anchor values at 0x970
        # If available, read int16 values
        self.hotspot_raw: List[int] = []
        if self.frame_count > 0:
            raw_hs = struct.unpack(
                f"<{self.frame_count}h",
                self.header[0x970 : 0x970 + 2 * self.frame_count],
            )
            self.hotspot_raw = list(raw_hs)

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike]) -> SpriteDecoder:
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, "rb") as f:
            data = f.read()
        return cls(data, name=name)

    def decode_frame_raw(self, frame_index: int) -> bytearray:
        """
        Decompress a single frame's 0xFE skip RLE stream into raw 8-bit index pixels.
        Returns a bytearray of size (width * height).
        """
        if frame_index < 0 or frame_index >= self.frame_count:
            raise IndexError(f"Frame index {frame_index} out of range (0..{self.frame_count - 1})")

        start_off = self.offsets[frame_index]
        if frame_index + 1 < self.frame_count:
            end_off = self.offsets[frame_index + 1]
        else:
            end_off = self.data_size

        stream = self.raw_data[SPR_HEADER_SIZE + start_off : SPR_HEADER_SIZE + end_off]
        target_pixels = self.width * self.height
        canvas = bytearray(target_pixels)

        s_ptr = 0
        c_ptr = 0
        s_len = len(stream)

        while c_ptr < target_pixels and s_ptr < s_len:
            byte_val = stream[s_ptr]
            s_ptr += 1

            if byte_val == 0xFE:
                # Transparent skip run
                if s_ptr < s_len:
                    skip_count = stream[s_ptr]
                    s_ptr += 1
                    c_ptr += skip_count
            else:
                # Literal palette index pixel
                canvas[c_ptr] = byte_val
                c_ptr += 1

        return canvas

    def decode_frame_image(self, frame_index: int, palette: Palette) -> Image.Image:
        """Decode a single frame and convert to a transparent PIL RGBA Image."""
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
    ) -> SpriteMetadata:
        """
        Decode and export all frames to PNG files and metadata JSON.
        Returns SpriteMetadata describing the decoded asset.
        """
        os.makedirs(output_dir, exist_ok=True)

        if isinstance(palette, (str, os.PathLike)):
            pal = Palette.from_file(palette)
        else:
            pal = palette

        lut = pal.to_lut_array()
        frames_info: List[FrameInfo] = []
        hotspots_list: List[Dict[str, int]] = []
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

            # Offset and length
            off = self.offsets[f_idx]
            next_off = self.offsets[f_idx + 1] if f_idx + 1 < self.frame_count else self.data_size
            data_len = next_off - off

            # Hotspot: default center or parsed 16-bit anchor
            hs_val = self.hotspot_raw[f_idx] if f_idx < len(self.hotspot_raw) else 0
            # Center coordinates as reference anchor
            hs_x = self.width // 2
            hs_y = self.height // 2
            if 0 < hs_val < self.width:
                hs_x = hs_val

            info = FrameInfo(
                index=f_idx,
                offset=off,
                data_length=data_len,
                width=self.width,
                height=self.height,
                hotspot_x=hs_x,
                hotspot_y=hs_y,
                file_name=frame_file_name,
            )
            frames_info.append(info)
            hotspots_list.append({"index": f_idx, "x": hs_x, "y": hs_y})

        # Generate Atlas sprite sheet if dimensions valid and requested
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

        metadata = SpriteMetadata(
            name=self.name,
            version=self.version,
            width=self.width,
            height=self.height,
            frame_count=self.frame_count,
            atlas_width=self.atlas_width,
            atlas_height=self.atlas_height,
            data_size=self.data_size,
            frames=frames_info,
            hotspots=hotspots_list,
            atlas_file=atlas_file_name,
        )

        json_path = os.path.join(output_dir, f"{self.name}_meta.json")
        metadata.save_json(json_path)

        return metadata


def decode_spr(
    spr_path: Union[str, os.PathLike],
    pal_path: Union[str, os.PathLike, Palette],
    output_dir: Union[str, os.PathLike],
    export_atlas: bool = True,
    export_frames: bool = True,
) -> SpriteMetadata:
    """
    Standard interface contract:
    Decodes a Version 9 .spr file into transparent PNG frames and metadata JSON.
    """
    decoder = SpriteDecoder.from_file(spr_path)
    return decoder.export(
        output_dir=output_dir,
        palette=pal_path,
        export_frames=export_frames,
        export_atlas=export_atlas,
    )
