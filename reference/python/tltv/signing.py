"""Canonical JSON serialization and Ed25519 document signing.

Implements PROTOCOL.md sections 4 (Canonical JSON / JCS) and 7 (Signatures).

Canonical JSON rules (RFC 8785, simplified for TLTV):
- Sort keys at each nesting level
- No whitespace between tokens
- No null values, no floats (integers only)
- UTF-8 encoding, no BOM

Signing procedure (section 7.1):
1. Remove 'signature' field from document
2. Serialize to canonical JSON bytes
3. Sign with Ed25519 private key
4. Base58-encode the 64-byte signature
5. Add 'signature' field to document
"""

from __future__ import annotations

import json

from tltv.identity import b58decode, b58encode, parse_channel_id


def _check_no_nulls_or_floats(obj, path=""):
    """Validate that a value contains no None or float types.

    TLTV signed documents MUST NOT contain null values or floating-point
    numbers (PROTOCOL.md section 4.1). This function enforces that constraint
    before serialization.

    Raises:
        ValueError: If a null or float is found, with the path to the value.
    """
    if obj is None:
        raise ValueError(
            f"null value at {path or 'root'}: TLTV documents must not contain null"
        )
    if isinstance(obj, float):
        raise ValueError(
            f"float value at {path or 'root'}: TLTV documents must use integers only"
        )
    if isinstance(obj, dict):
        for k, v in obj.items():
            _check_no_nulls_or_floats(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_no_nulls_or_floats(v, f"{path}[{i}]")


def canonical_json(obj: dict) -> bytes:
    """Serialize a dict to canonical JSON bytes (RFC 8785 / JCS).

    For TLTV documents (ASCII keys, integers only, no nulls),
    json.dumps with sort_keys=True is sufficient. The key sort order
    matches RFC 8785 section 3.2.3 for ASCII-only keys.

    Args:
        obj: Dictionary to serialize. Must not contain None values
            or float numbers.

    Returns:
        UTF-8 encoded canonical JSON bytes.

    Raises:
        ValueError: If the document contains null values or floats.
    """
    _check_no_nulls_or_floats(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign_document(doc: dict, private_key_bytes: bytes) -> dict:
    """Sign a TLTV document with an Ed25519 private key.

    Implements PROTOCOL.md section 7.1:
    1. Remove 'signature' field if present
    2. Serialize to canonical JSON
    3. Sign with Ed25519
    4. Base58-encode signature
    5. Add 'signature' to document

    Args:
        doc: Document dict (will be modified in place).
        private_key_bytes: 32-byte Ed25519 private key seed.

    Returns:
        The document with 'signature' field added.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    # Step 1: Remove signature if present
    doc_without_sig = {k: v for k, v in doc.items() if k != "signature"}

    # Step 2: Canonical JSON
    payload = canonical_json(doc_without_sig)

    # Step 3: Sign
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    signature_bytes = private_key.sign(payload)

    # Step 4: Base58-encode
    signature_b58 = b58encode(signature_bytes)

    # Step 5: Add to document
    doc["signature"] = signature_b58
    return doc


def verify_document(doc: dict, channel_id: str) -> bool:
    """Verify a signed TLTV metadata or guide document.

    Implements PROTOCOL.md section 7.2:
    1. Remove 'signature' field
    2. Serialize to canonical JSON
    3. Decode channel ID to get pubkey
    4. Decode signature from base58
    5. Verify Ed25519 signature

    Also checks identity binding (section 5.4): the document's 'id'
    field must match the expected channel_id.

    For migration documents (type == "migration"), use
    verify_migration_document() instead.

    Args:
        doc: Signed document dict (must have 'signature' and 'id' fields).
        channel_id: Expected channel ID (for identity binding check).

    Returns:
        True if signature is valid and identity matches.
        False otherwise.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    # Identity binding check
    if doc.get("id") != channel_id:
        return False

    signature_b58 = doc.get("signature")
    if not signature_b58:
        return False

    # Step 1: Remove signature
    doc_without_sig = {k: v for k, v in doc.items() if k != "signature"}

    # Step 2: Canonical JSON
    payload = canonical_json(doc_without_sig)

    try:
        # Step 3: Extract pubkey from channel ID
        pubkey_bytes = parse_channel_id(channel_id)

        # Step 4: Decode signature
        signature_bytes = b58decode(signature_b58)
        if len(signature_bytes) != 64:
            return False

        # Step 5: Verify
        public_key = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        public_key.verify(signature_bytes, payload)
        return True

    except Exception:
        return False


def verify_migration_document(doc: dict, old_channel_id: str) -> bool:
    """Verify a signed migration document.

    Implements PROTOCOL.md section 5.14 verification:
    1. Confirm type is "migration"
    2. Confirm v is supported (must be 1)
    3. Remove signature field
    4. Serialize to canonical JSON
    5. Extract pubkey from 'from' field (old channel ID)
    6. Decode signature from base58
    7. Verify Ed25519 signature

    Migration documents use the 'from' field for identity binding
    (not 'id' as in metadata/guide documents). The signature is
    verified against the old channel's public key.

    Does not enforce seq replay protection — that requires stateful
    tracking which is the caller's responsibility.

    Args:
        doc: Signed migration document dict.
        old_channel_id: Expected old channel ID (for identity binding).

    Returns:
        True if type is migration, v is 1, signature is valid,
        and 'from' matches old_channel_id.
        False otherwise.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    # Step 1: Check type
    if doc.get("type") != "migration":
        return False

    # Step 2: Check version
    if doc.get("v") != 1:
        return False

    # Identity binding: 'from' must match the expected old channel ID
    if doc.get("from") != old_channel_id:
        return False

    signature_b58 = doc.get("signature")
    if not signature_b58:
        return False

    # Step 3: Remove signature
    doc_without_sig = {k: v for k, v in doc.items() if k != "signature"}

    # Step 4: Canonical JSON
    payload = canonical_json(doc_without_sig)

    try:
        # Step 5: Extract pubkey from old channel ID
        pubkey_bytes = parse_channel_id(old_channel_id)

        # Step 6: Decode signature
        signature_bytes = b58decode(signature_b58)
        if len(signature_bytes) != 64:
            return False

        # Step 7: Verify
        public_key = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        public_key.verify(signature_bytes, payload)
        return True

    except Exception:
        return False
