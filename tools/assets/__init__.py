"""
Proprietary Asset Decoder & Web-Ready Converter for Imjinrok 2+ (조선의 반격: 여명).

Submodules:
- palette: Decodes 768-byte 6-bit VGA DAC `.pal` files to 8-bit RGBA (index 0 transparent).
- audio: Decodes 26-byte `.YAV` PCM audio files to standard 44-byte RIFF `.wav` files.
- sprite_rle: Decodes Version 9 `.spr` files (0xFE skip RLE) to transparent PNGs + metadata JSON.
- tile_rle: Decodes Version 9 `.ytl` (diamond single-span) and `.ypr` (hill multi-span) to PNGs.
- cli: Command-line interface for individual and batch asset conversion.
"""

from tools.assets.palette import convert_pal_to_rgba, Palette, RGBA
from tools.assets.audio import convert_yav_to_wav, YAVAudio
from tools.assets.sprite_rle import decode_spr, SpriteMetadata, SpriteDecoder, FrameInfo
from tools.assets.tile_rle import (
    decode_ytl,
    decode_ypr,
    decode_tile,
    TileMetadata,
    TileDecoder,
    TileFrameInfo,
)

__all__ = [
    "convert_pal_to_rgba",
    "Palette",
    "RGBA",
    "convert_yav_to_wav",
    "YAVAudio",
    "decode_spr",
    "SpriteMetadata",
    "SpriteDecoder",
    "FrameInfo",
    "decode_ytl",
    "decode_ypr",
    "decode_tile",
    "TileMetadata",
    "TileDecoder",
    "TileFrameInfo",
]
