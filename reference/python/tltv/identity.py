"""TLTV channel identity — Ed25519 keypair, base58, version prefix.

Implements PROTOCOL.md sections 2.1-2.3:
- Channel ID = base58(0x1433 || Ed25519_pubkey)
- Always starts with "TV" (46 characters)
- Base58 uses Bitcoin alphabet (no 0, O, l, I)
"""

from __future__ import annotations

# Base58 alphabet (Bitcoin variant — no 0, O, l, I)
_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# V1 version prefix — produces "TV" leading characters in base58
VERSION_PREFIX = b"\x14\x33"

# RFC 8032 test vector 1 — public knowledge, MUST NOT be used in production.
# See PROTOCOL.md Appendix C.
_TEST_CHANNEL_ID = "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3"


def is_test_channel(channel_id: str) -> bool:
    """Check if a channel ID is the well-known RFC 8032 test key.

    This keypair is published in IETF RFC 8032 and in the TLTV test vectors.
    Anyone can sign valid metadata for it. It MUST NOT be used for production
    channels.
    """
    return channel_id == _TEST_CHANNEL_ID


def b58encode(data: bytes) -> str:
    """Encode bytes to base58 (Bitcoin alphabet)."""
    n = int.from_bytes(data, "big")
    result = bytearray()
    while n > 0:
        n, r = divmod(n, 58)
        result.append(_B58_ALPHABET[r])
    # Preserve leading zero bytes
    for b in data:
        if b == 0:
            result.append(_B58_ALPHABET[0])
        else:
            break
    return bytes(reversed(result)).decode("ascii")


def b58decode(s: str) -> bytes:
    """Decode base58 string to bytes."""
    n = 0
    for c in s.encode("ascii"):
        n = n * 58 + _B58_ALPHABET.index(c)
    # Count leading '1's (zero bytes)
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    result = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + result


def make_channel_id(pubkey: bytes) -> str:
    """Encode a 32-byte Ed25519 public key as a TLTV channel ID.

    Prepends the V1 version prefix (0x1433) before base58 encoding.
    The result always starts with "TV" and is 46 characters long.

    Args:
        pubkey: 32-byte Ed25519 public key.

    Returns:
        Channel ID string (e.g. "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3").
    """
    if len(pubkey) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(pubkey)}")
    return b58encode(VERSION_PREFIX + pubkey)


def parse_channel_id(channel_id: str) -> bytes:
    """Decode a TLTV channel ID to extract the 32-byte Ed25519 public key.

    Verifies the V1 version prefix (0x1433).

    Args:
        channel_id: Base58-encoded channel ID starting with "TV".

    Returns:
        32-byte Ed25519 public key.

    Raises:
        ValueError: If the channel ID is invalid (bad base58, wrong prefix,
            wrong length).
    """
    try:
        raw = b58decode(channel_id)
    except Exception as exc:
        raise ValueError(f"Invalid base58 in channel ID: {exc}") from exc

    if len(raw) != 34:
        raise ValueError(
            f"Channel ID must decode to 34 bytes (2 prefix + 32 pubkey), got {len(raw)}"
        )

    prefix = raw[:2]
    if prefix != VERSION_PREFIX:
        raise ValueError(
            f"Unknown version prefix 0x{prefix.hex()} "
            f"(expected 0x{VERSION_PREFIX.hex()})"
        )

    return raw[2:]
