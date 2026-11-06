"""
YAV Audio Decoder (.YAV to standard RIFF .wav) for Imjinrok 2+ (조선의 반격).

Specification:
- File Header: 26 bytes packed (fmt_size + WAVEFORMATEX + data_size)
  - 0x00: uint32 fmt_size (always 18 / 0x12)
  - 0x04: uint16 wFormatTag (always 1 / WAVE_FORMAT_PCM)
  - 0x06: uint16 nChannels (1 for mono, 2 for stereo)
  - 0x08: uint32 nSamplesPerSec (sampling rate: 11025, 22050, 44100, etc.)
  - 0x0C: uint32 nAvgBytesPerSec (rate * block_align)
  - 0x10: uint16 nBlockAlign (channels * bits_per_sample / 8)
  - 0x12: uint16 wBitsPerSample (8 or 16)
  - 0x14: uint16 cbSize (always 0)
  - 0x16: uint32 data_size (PCM audio payload size in bytes)
- Payload: data_size bytes of raw uncompressed PCM audio starting at offset 0x1A.
- Total File Size: Exactly 26 + data_size bytes.

Output:
- Standard 44-byte RIFF .wav file with PCM 'fmt ' and 'data' chunks.
- Verifiable by standard Python `wave` module and playable in all web browsers.
"""

from __future__ import annotations
import io
import os
import struct
import wave
from dataclasses import dataclass
from typing import Union

YAV_HEADER_SIZE = 26
YAV_HEADER_FORMAT = "<IHHIIHHHI"


@dataclass
class YAVAudio:
    """Represents a decoded YAV audio asset."""
    fmt_size: int
    format_tag: int
    channels: int
    sample_rate: int
    avg_bytes_per_sec: int
    block_align: int
    bits_per_sample: int
    cb_size: int
    data_size: int
    pcm_data: bytes

    def __post_init__(self) -> None:
        if len(self.pcm_data) != self.data_size:
            raise ValueError(
                f"PCM data size mismatch: header specifies {self.data_size} bytes, "
                f"but buffer contains {len(self.pcm_data)} bytes"
            )

    @property
    def sample_count(self) -> int:
        """Total number of audio frames/samples."""
        if self.block_align <= 0:
            return 0
        return self.data_size // self.block_align

    @property
    def duration_seconds(self) -> float:
        """Audio duration in seconds."""
        if self.sample_rate <= 0:
            return 0.0
        return self.sample_count / self.sample_rate

    @classmethod
    def from_bytes(cls, data: bytes) -> YAVAudio:
        """Parse YAV audio from raw bytes."""
        if len(data) < YAV_HEADER_SIZE:
            raise ValueError(
                f"Data too short for YAV header: expected at least {YAV_HEADER_SIZE} bytes, "
                f"got {len(data)}"
            )

        (
            fmt_size,
            format_tag,
            channels,
            sample_rate,
            avg_bytes_per_sec,
            block_align,
            bits_per_sample,
            cb_size,
            data_size,
        ) = struct.unpack(YAV_HEADER_FORMAT, data[:YAV_HEADER_SIZE])

        if fmt_size != 18:
            raise ValueError(f"Invalid YAV fmt_size: expected 18, got {fmt_size}")
        if format_tag != 1:
            raise ValueError(f"Unsupported YAV format_tag: expected 1 (PCM), got {format_tag}")

        pcm_data = data[YAV_HEADER_SIZE : YAV_HEADER_SIZE + data_size]
        if len(pcm_data) != data_size:
            raise ValueError(
                f"Truncated YAV PCM stream: expected {data_size} bytes, got {len(pcm_data)}"
            )

        return cls(
            fmt_size=fmt_size,
            format_tag=format_tag,
            channels=channels,
            sample_rate=sample_rate,
            avg_bytes_per_sec=avg_bytes_per_sec,
            block_align=block_align,
            bits_per_sample=bits_per_sample,
            cb_size=cb_size,
            data_size=data_size,
            pcm_data=pcm_data,
        )

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike]) -> YAVAudio:
        """Load and parse a .YAV file from disk."""
        with open(path, "rb") as f:
            data = f.read()
        return cls.from_bytes(data)

    def to_riff_wav_bytes(self) -> bytes:
        """
        Synthesize standard 44-byte RIFF WAV container header and append PCM data.
        RIFF Structure:
        - [0x00] 'RIFF'
        - [0x04] uint32(36 + data_size)
        - [0x08] 'WAVE'
        - [0x0C] 'fmt '
        - [0x10] uint32(16) [fmt chunk size for PCM]
        - [0x14] uint16(format_tag)
        - [0x16] uint16(channels)
        - [0x18] uint32(sample_rate)
        - [0x1C] uint32(avg_bytes_per_sec)
        - [0x20] uint16(block_align)
        - [0x22] uint16(bits_per_sample)
        - [0x24] 'data'
        - [0x28] uint32(data_size)
        - [0x2C] pcm_data[data_size]
        """
        riff_header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + self.data_size,
            b"WAVE",
            b"fmt ",
            16,
            self.format_tag,
            self.channels,
            self.sample_rate,
            self.avg_bytes_per_sec,
            self.block_align,
            self.bits_per_sample,
            b"data",
            self.data_size,
        )
        return riff_header + self.pcm_data

    def verify_with_wave(self) -> bool:
        """Verify the generated WAV bytes using Python standard wave module."""
        wav_bytes = self.to_riff_wav_bytes()
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            if wf.getnchannels() != self.channels:
                return False
            if wf.getsampwidth() != self.bits_per_sample // 8:
                return False
            if wf.getframerate() != self.sample_rate:
                return False
            if wf.getnframes() != self.sample_count:
                return False
        return True

    def save_wav(self, out_path: Union[str, os.PathLike]) -> str:
        """Save standard .wav file to disk."""
        wav_bytes = self.to_riff_wav_bytes()
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(wav_bytes)
        return str(out_path)


def convert_yav_to_wav(
    yav_path: Union[str, os.PathLike], wav_path: Union[str, os.PathLike]
) -> bool:
    """
    Standard interface contract:
    Converts a .YAV file to standard RIFF .wav file and verifies playability.
    """
    try:
        audio = YAVAudio.from_file(yav_path)
        if not audio.verify_with_wave():
            return False
        audio.save_wav(wav_path)
        return True
    except Exception:
        return False
