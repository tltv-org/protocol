"""TLTV URI scheme — formatting and parsing.

Implements PROTOCOL.md section 3:
- tltv://<channel_id>
- tltv://<channel_id>@<host:port>
- tltv://<channel_id>?via=<host1>,<host2>
- tltv://<channel_id>?token=<access_token>&via=<host1>

Case sensitivity: channel IDs are case-sensitive (base58).
Implementations MUST NOT apply host normalization (lowercasing)
to the channel ID component (section 2.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse


@dataclass
class TltvUri:
    """Parsed tltv:// URI components."""

    channel_id: str
    hints: list[str] = field(default_factory=list)
    token: str | None = None


def format_tltv_uri(
    channel_id: str,
    hints: list[str] | None = None,
    token: str | None = None,
) -> str:
    """Format a tltv:// URI from components.

    Args:
        channel_id: TV-prefixed channel ID (case-sensitive).
        hints: Optional list of host:port peer hints.
        token: Optional access token for private channels.

    Returns:
        Formatted tltv:// URI string.

    Examples:
        >>> format_tltv_uri("TVMkVH...")
        'tltv://TVMkVH...'
        >>> format_tltv_uri("TVMkVH...", hints=["relay.example.com:8443"])
        'tltv://TVMkVH...?via=relay.example.com:8443'
        >>> format_tltv_uri("TVMkVH...", token="abc123")
        'tltv://TVMkVH...?token=abc123'
    """
    uri = f"tltv://{channel_id}"
    params: list[str] = []

    if token:
        params.append(f"token={token}")
    if hints:
        params.append(f"via={','.join(hints)}")

    if params:
        uri += "?" + "&".join(params)

    return uri


def parse_tltv_uri(uri: str) -> TltvUri:
    """Parse a tltv:// URI into components.

    Uses urlparse().netloc to preserve case (section 2.5).
    Does NOT apply host normalization.

    Args:
        uri: A tltv:// URI string.

    Returns:
        TltvUri with channel_id, hints, and token.

    Raises:
        ValueError: If the URI scheme is not 'tltv' or is malformed.
    """
    parsed = urlparse(uri)

    if parsed.scheme != "tltv":
        raise ValueError(f"Expected tltv:// scheme, got '{parsed.scheme}://'")

    # Extract channel ID from netloc (preserves case — section 2.5)
    # netloc may contain @host:port hint
    netloc = parsed.netloc
    if not netloc:
        raise ValueError("Missing channel ID in tltv:// URI")

    # Check for @hint format: channel_id@host:port
    if "@" in netloc:
        channel_id, hint = netloc.split("@", 1)
        hints = [hint] if hint else []
    else:
        channel_id = netloc
        hints = []

    if not channel_id:
        raise ValueError("Empty channel ID in tltv:// URI")

    # Parse query parameters
    query = parse_qs(parsed.query, keep_blank_values=False)

    token = query.get("token", [None])[0]

    # via parameter: comma-separated hints
    via_str = query.get("via", [None])[0]
    if via_str:
        via_hints = [h.strip() for h in via_str.split(",") if h.strip()]
        hints.extend(via_hints)

    return TltvUri(channel_id=channel_id, hints=hints, token=token)
