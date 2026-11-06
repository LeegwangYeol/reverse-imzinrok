"""
VGA 6-bit DAC Palette Decoder (.pal) for Imjinrok 2+ (조선의 반격).

Specification:
- File Size: Exactly 768 bytes (256 colors * 3 channels: R, G, B).
- Channel Depth: 6 bits per channel (values 0..63).
- 8-bit Scaling Formula: (c * 255) // 63.
- Alpha Channel:
  - Color Index 0: Fully Transparent (RGBA: 0, 0, 0, 0).
  - Color Indices 1..255: Fully Opaque (RGBA: R, G, B, 255).
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import List, Tuple, Union, Optional
from PIL import Image
import numpy as np

RGBA = Tuple[int, int, int, int]
PALETTE_FILE_SIZE = 768
COLOR_COUNT = 256


@dataclass
class Palette:
    """Represents a 256-entry RGBA palette with transparency on index 0."""
    colors: List[RGBA]

    def __post_init__(self) -> None:
        if len(self.colors) != COLOR_COUNT:
            raise ValueError(f"Palette must contain exactly {COLOR_COUNT} colors, got {len(self.colors)}")

    @classmethod
    def from_bytes(cls, data: bytes) -> Palette:
        """Parse a 768-byte 6-bit VGA DAC palette from raw bytes."""
        if len(data) != PALETTE_FILE_SIZE:
            raise ValueError(
                f"Invalid palette byte size: expected {PALETTE_FILE_SIZE} bytes, got {len(data)}"
            )

        colors: List[RGBA] = []
        for i in range(COLOR_COUNT):
            r = data[i * 3]
            g = data[i * 3 + 1]
            b = data[i * 3 + 2]

            # Scale 6-bit VGA DAC (0..63) to 8-bit RGB (0..255)
            # Clamp to 63 if any out-of-range byte occurs
            r_8 = (min(r, 63) * 255) // 63
            g_8 = (min(g, 63) * 255) // 63
            b_8 = (min(b, 63) * 255) // 63

            # Color index 0 is transparent key
            a_8 = 0 if i == 0 else 255
            colors.append((r_8, g_8, b_8, a_8))

        return cls(colors=colors)

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike]) -> Palette:
        """Load and parse a 768-byte .pal file from disk."""
        with open(path, "rb") as f:
            data = f.read()
        return cls.from_bytes(data)

    def to_rgba_list(self) -> List[RGBA]:
        """Return colors as a list of 256 (R, G, B, A) tuples."""
        return list(self.colors)

    def to_lut_array(self) -> np.ndarray:
        """Return colors as a NumPy uint8 array of shape (256, 4)."""
        return np.array(self.colors, dtype=np.uint8)

    def to_lut_bytes(self) -> bytes:
        """Return colors as a raw contiguous 1,024-byte RGBA buffer."""
        return bytes([val for color in self.colors for val in color])

    def save_json(self, out_path: Union[str, os.PathLike]) -> str:
        """Save palette colors as human-readable JSON."""
        data = [
            {"index": i, "r": c[0], "g": c[1], "b": c[2], "a": c[3]}
            for i, c in enumerate(self.colors)
        ]
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(out_path)

    def save_swatch_image(
        self, out_path: Union[str, os.PathLike], cell_size: int = 16
    ) -> str:
        """Render a 16x16 grid swatch PNG of all 256 colors."""
        grid_dim = 16
        img_size = grid_dim * cell_size
        img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))

        for idx, color in enumerate(self.colors):
            gx = idx % grid_dim
            gy = idx // grid_dim
            cell = Image.new("RGBA", (cell_size, cell_size), color)
            img.paste(cell, (gx * cell_size, gy * cell_size))

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        img.save(out_path, "PNG")
        return str(out_path)


def convert_pal_to_rgba(pal_path: Union[str, os.PathLike]) -> List[RGBA]:
    """
    Standard interface contract:
    Loads a .pal file and returns a list of 256 RGBA tuples with index 0 transparent.
    """
    palette = Palette.from_file(pal_path)
    return palette.to_rgba_list()
