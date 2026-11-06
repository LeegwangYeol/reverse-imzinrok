"""XOR 0x10 Codec for Imjinrok 2+ Dawn Archive System.

Binary Specifications:
- Data.hq: Line-oriented XOR 0x10 codec preserving CRLF (\\r\\n).
  Each entry line is encoded with CP949 and XORed with 0x10 byte-by-byte.
  Line separators (0x0D, 0x0A) are preserved in plaintext.
- Data: Unconditional byte ^ 0x10 across all 230,202 bytes.
  Engine loads slices into buffer and performs single-byte loop (VA 0x00420169~0x0042017c)
  without branch conditions on \\r or \\n.
"""

from typing import List


def xor_bytes(data: bytes, key: int = 0x10) -> bytes:
    """Perform unconditional byte-wise XOR with key.
    
    Since XOR is an involution (f(f(x)) == x), this function is used
    for both encryption and decryption of raw streams.
    """
    return bytes(b ^ key for b in data)


def decode_data_bytes(raw_bytes: bytes) -> bytes:
    """Decode raw Data archive bytes via unconditional XOR 0x10."""
    return xor_bytes(raw_bytes, 0x10)


def encode_data_bytes(plain_bytes: bytes) -> bytes:
    """Encode plain Data archive bytes via unconditional XOR 0x10."""
    return xor_bytes(plain_bytes, 0x10)


def decode_hq_line(line_bytes: bytes, encoding: str = "cp949") -> str:
    """Decode a single line of Data.hq (excluding CRLF)."""
    dec_bytes = xor_bytes(line_bytes, 0x10)
    return dec_bytes.decode(encoding, errors="replace")


def encode_hq_line(text: str, encoding: str = "cp949") -> bytes:
    """Encode a single line of Data.hq text into XOR 0x10 bytes (excluding CRLF)."""
    raw_bytes = text.encode(encoding)
    return xor_bytes(raw_bytes, 0x10)


def decode_hq_bytes(hq_bytes: bytes, encoding: str = "cp949") -> List[str]:
    """Decode entire Data.hq byte buffer into a list of decoded string lines.
    
    Data.hq uses CRLF (0x0D 0x0A) as record separators. The trailing empty line
    resulting from final CRLF is omitted.
    """
    raw_lines = hq_bytes.split(b"\r\n")
    if raw_lines and raw_lines[-1] == b"":
        raw_lines = raw_lines[:-1]
    
    return [decode_hq_line(line, encoding=encoding) for line in raw_lines]


def encode_hq_bytes(lines: List[str], encoding: str = "cp949") -> bytes:
    """Encode a list of text lines into Data.hq format with CRLF line delimiters."""
    encoded_lines = [encode_hq_line(line, encoding=encoding) for line in lines]
    return b"\r\n".join(encoded_lines) + b"\r\n"


def verify_data_roundtrip(data: bytes) -> bool:
    """Verify bit-exact round-trip preservation of Data payload."""
    return encode_data_bytes(decode_data_bytes(data)) == data


def verify_hq_roundtrip(hq_bytes: bytes, encoding: str = "cp949") -> bool:
    """Verify bit-exact round-trip preservation of Data.hq buffer."""
    return encode_hq_bytes(decode_hq_bytes(hq_bytes, encoding=encoding), encoding=encoding) == hq_bytes
