"""Validate the TLTV reference implementation against protocol test vectors.

Test vectors are from PROTOCOL.md Appendix C, extracted to test-vectors/*.json.
Any conforming implementation should pass these tests.
"""

import json
from pathlib import Path

import pytest

from tltv.identity import b58decode, b58encode, make_channel_id, parse_channel_id
from tltv.signing import (
    canonical_json,
    sign_document,
    verify_document,
    verify_migration_document,
)
from tltv.uri import TltvUri, format_tltv_uri, parse_tltv_uri

VECTORS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "test-vectors"


def _load_vector(name: str) -> dict:
    return json.loads((VECTORS_DIR / name).read_text())


# ── C.1 Channel Identity ──


class TestC1Identity:
    """PROTOCOL.md Appendix C.1 — channel identity encoding."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c1-identity.json")

    def test_version_prefix(self):
        from tltv.identity import VERSION_PREFIX

        assert VERSION_PREFIX == bytes.fromhex(self.v["version_prefix_hex"])

    def test_make_channel_id(self):
        pubkey = bytes.fromhex(self.v["public_key_hex"])
        channel_id = make_channel_id(pubkey)
        assert channel_id == self.v["channel_id"]

    def test_parse_channel_id_roundtrip(self):
        pubkey = bytes.fromhex(self.v["public_key_hex"])
        channel_id = self.v["channel_id"]
        extracted = parse_channel_id(channel_id)
        assert extracted == pubkey

    def test_payload_encoding(self):
        payload = bytes.fromhex(self.v["payload_hex"])
        assert b58encode(payload) == self.v["channel_id"]

    def test_payload_decoding(self):
        raw = b58decode(self.v["channel_id"])
        assert raw == bytes.fromhex(self.v["payload_hex"])

    def test_channel_id_starts_with_tv(self):
        assert self.v["channel_id"].startswith("TV")

    def test_decoded_length_34_bytes(self):
        raw = b58decode(self.v["channel_id"])
        assert len(raw) == 34  # 2 prefix + 32 pubkey


# ── C.2 Metadata Signing ──


class TestC2Signing:
    """PROTOCOL.md Appendix C.2 — canonical JSON + Ed25519 signature."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c2-signing.json")

    def test_canonical_json_length(self):
        doc = self.v["document"]
        canon = canonical_json(doc)
        assert len(canon) == self.v["canonical_json_length"]

    def test_canonical_json_sorted_keys(self):
        doc = self.v["document"]
        canon = canonical_json(doc)
        text = canon.decode("utf-8")
        # First key should be "access" (alphabetically first)
        assert text.startswith('{"access":')

    def test_canonical_json_no_whitespace(self):
        doc = self.v["document"]
        canon = canonical_json(doc)
        text = canon.decode("utf-8")
        # No spaces after colons or commas
        assert ": " not in text
        assert ", " not in text

    def test_signature_matches(self):
        private_key = bytes.fromhex(self.v["private_key_seed_hex"])
        doc = dict(self.v["document"])  # copy
        signed = sign_document(doc, private_key)
        assert signed["signature"] == self.v["signature_base58"]

    def test_signature_hex_matches(self):
        sig_bytes = b58decode(self.v["signature_base58"])
        assert sig_bytes.hex() == self.v["signature_hex"]


# ── C.3 Complete Signed Document ──


class TestC3CompleteDocument:
    """PROTOCOL.md Appendix C.3 — full signed document verification."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c3-complete-document.json")

    def test_verify_valid_signature(self):
        doc = self.v["signed_document"]
        channel_id = self.v["channel_id"]
        assert verify_document(doc, channel_id) is True

    def test_verify_rejects_tampered_name(self):
        doc = dict(self.v["signed_document"])
        doc["name"] = "Tampered Name"
        assert verify_document(doc, self.v["channel_id"]) is False

    def test_verify_rejects_wrong_channel_id(self):
        doc = self.v["signed_document"]
        assert verify_document(doc, "TVinvalidchannelid") is False

    def test_verify_rejects_missing_signature(self):
        doc = {k: v for k, v in self.v["signed_document"].items() if k != "signature"}
        assert verify_document(doc, self.v["channel_id"]) is False

    def test_identity_binding(self):
        """Document 'id' field must match the channel_id argument."""
        doc = dict(self.v["signed_document"])
        doc["id"] = "TVsomeOtherChannelIdThatDoesNotMatch123456"
        assert verify_document(doc, self.v["channel_id"]) is False

    def test_sign_then_verify_roundtrip(self):
        """Sign a fresh document, then verify it."""
        c1 = _load_vector("c1-identity.json")
        private_key = bytes.fromhex(c1["private_key_seed_hex"])
        channel_id = c1["channel_id"]

        doc = {
            "v": 1,
            "seq": 42,
            "id": channel_id,
            "name": "Roundtrip Test",
            "access": "public",
        }
        signed = sign_document(doc, private_key)
        assert verify_document(signed, channel_id) is True


# ── URI Scheme ──


class TestUriScheme:
    """PROTOCOL.md section 3 — tltv:// URI parsing and formatting."""

    CHANNEL_ID = "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3"

    def test_format_basic(self):
        uri = format_tltv_uri(self.CHANNEL_ID)
        assert uri == f"tltv://{self.CHANNEL_ID}"

    def test_format_with_hint(self):
        uri = format_tltv_uri(self.CHANNEL_ID, hints=["node.example.com:8443"])
        assert "via=node.example.com:8443" in uri

    def test_format_with_token(self):
        uri = format_tltv_uri(self.CHANNEL_ID, token="secret123")
        assert "token=secret123" in uri

    def test_parse_basic(self):
        uri = f"tltv://{self.CHANNEL_ID}"
        parsed = parse_tltv_uri(uri)
        assert parsed.channel_id == self.CHANNEL_ID
        assert parsed.hints == []
        assert parsed.token is None

    def test_parse_with_at_hint(self):
        uri = f"tltv://{self.CHANNEL_ID}@node.example.com:8443"
        parsed = parse_tltv_uri(uri)
        assert parsed.channel_id == self.CHANNEL_ID
        assert "node.example.com:8443" in parsed.hints

    def test_parse_with_via(self):
        uri = f"tltv://{self.CHANNEL_ID}?via=a.com:8000,b.com:8000"
        parsed = parse_tltv_uri(uri)
        assert len(parsed.hints) == 2

    def test_parse_with_token(self):
        uri = f"tltv://{self.CHANNEL_ID}?token=abc123"
        parsed = parse_tltv_uri(uri)
        assert parsed.token == "abc123"

    def test_roundtrip(self):
        original = format_tltv_uri(
            self.CHANNEL_ID,
            hints=["relay.example.com:8443"],
            token="secret",
        )
        parsed = parse_tltv_uri(original)
        assert parsed.channel_id == self.CHANNEL_ID
        assert parsed.token == "secret"
        assert "relay.example.com:8443" in parsed.hints

    def test_parse_wrong_scheme_raises(self):
        with pytest.raises(ValueError, match="tltv://"):
            parse_tltv_uri("https://example.com")

    def test_parse_empty_channel_raises(self):
        with pytest.raises(ValueError):
            parse_tltv_uri("tltv://")

    def test_case_sensitivity(self):
        """Channel IDs are case-sensitive (section 2.5)."""
        uri = f"tltv://{self.CHANNEL_ID}"
        parsed = parse_tltv_uri(uri)
        # Must preserve exact case, not lowercase
        assert parsed.channel_id == self.CHANNEL_ID
        assert parsed.channel_id != self.CHANNEL_ID.lower()


# ── C.4 URI Parsing (from test vectors) ──


class TestC4UriParsing:
    """Test URI parsing against c4-uri-parsing.json test vectors."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c4-uri-parsing.json")

    def test_valid_cases(self):
        for case in self.v["cases"]:
            parsed = parse_tltv_uri(case["uri"])
            expected = case["expected"]
            assert parsed.channel_id == expected["channel_id"], (
                f"Failed {case['name']}: channel_id"
            )
            assert parsed.hints == expected["hints"], f"Failed {case['name']}: hints"
            assert parsed.token == expected["token"], f"Failed {case['name']}: token"

    def test_invalid_cases(self):
        for case in self.v["invalid_cases"]:
            with pytest.raises(ValueError):
                parse_tltv_uri(case["uri"])


# ── C.5 Guide Document ──


class TestC5GuideDocument:
    """Test signed guide document against c5-guide-document.json vectors."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c5-guide-document.json")

    def test_canonical_json_length(self):
        doc = self.v["document"]
        canon = canonical_json(doc)
        assert len(canon) == self.v["canonical_json_length"]

    def test_signature_matches(self):
        private_key = bytes.fromhex(self.v["private_key_seed_hex"])
        doc = dict(self.v["document"])
        signed = sign_document(doc, private_key)
        assert signed["signature"] == self.v["signature_base58"]

    def test_signature_hex_matches(self):
        sig_bytes = b58decode(self.v["signature_base58"])
        assert sig_bytes.hex() == self.v["signature_hex"]

    def test_verify_signed_document(self):
        doc = self.v["signed_document"]
        channel_id = self.v["channel_id"]
        assert verify_document(doc, channel_id) is True

    def test_verify_rejects_tampered_entry(self):
        doc = json.loads(json.dumps(self.v["signed_document"]))  # deep copy
        doc["entries"][0]["title"] = "Tampered Title"
        assert verify_document(doc, self.v["channel_id"]) is False

    def test_guide_entries_ordered(self):
        """Guide entries must be ordered by start time (section 6.3)."""
        entries = self.v["document"]["entries"]
        starts = [e["start"] for e in entries]
        assert starts == sorted(starts)


# ── C.6 Invalid Inputs ──


class TestC6InvalidInputs:
    """Test rejection of invalid inputs from c6-invalid-inputs.json vectors."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c6-invalid-inputs.json")

    def test_invalid_channel_ids(self):
        for case in self.v["identity"]["cases"]:
            with pytest.raises((ValueError, Exception)):
                parse_channel_id(case["channel_id"])

    def test_tampered_document_rejected(self):
        case = self.v["verification"]["cases"][0]  # tampered name
        assert case["error"] == "invalid_signature"
        result = verify_document(case["document"], self.v["valid_channel_id"])
        assert result is False

    def test_missing_signature_rejected(self):
        case = self.v["verification"]["cases"][1]  # missing signature
        assert case["error"] == "missing_signature"
        result = verify_document(case["document"], self.v["valid_channel_id"])
        assert result is False

    def test_identity_binding_mismatch_rejected(self):
        case = self.v["verification"]["cases"][2]  # id mismatch
        assert case["error"] == "identity_binding_mismatch"
        result = verify_document(case["document"], case["verify_against_channel_id"])
        assert result is False

    def test_truncated_signature_rejected(self):
        case = self.v["verification"]["cases"][3]  # truncated signature
        assert case["error"] == "invalid_signature_length"
        result = verify_document(case["document"], self.v["valid_channel_id"])
        assert result is False


# ── C.7 Key Migration ──


class TestC7KeyMigration:
    """PROTOCOL.md section 5.14 — key migration document."""

    @pytest.fixture(autouse=True)
    def load_vector(self):
        self.v = _load_vector("c7-key-migration.json")

    def test_canonical_json_length(self):
        doc = self.v["document"]
        canon = canonical_json(doc)
        assert len(canon) == self.v["canonical_json_length"]

    def test_canonical_json_sorted_keys(self):
        doc = self.v["document"]
        canon = canonical_json(doc)
        text = canon.decode("utf-8")
        # First key should be "from" (alphabetically first)
        assert text.startswith('{"from":')

    def test_signature_matches(self):
        """Sign the migration document with the old key, verify signature."""
        private_key = bytes.fromhex(self.v["old_private_key_seed_hex"])
        doc = dict(self.v["document"])  # copy
        signed = sign_document(doc, private_key)
        assert signed["signature"] == self.v["signature_base58"]

    def test_signature_hex_matches(self):
        sig_bytes = b58decode(self.v["signature_base58"])
        assert sig_bytes.hex() == self.v["signature_hex"]

    def test_verify_signed_migration(self):
        """Verify the signed migration document against the old channel ID."""
        doc = self.v["signed_document"]
        old_channel_id = self.v["old_channel_id"]
        assert verify_migration_document(doc, old_channel_id) is True

    def test_verify_rejects_tampered_reason(self):
        doc = dict(self.v["signed_document"])
        doc["reason"] = "tampered reason"
        assert verify_migration_document(doc, self.v["old_channel_id"]) is False

    def test_verify_rejects_tampered_to(self):
        doc = dict(self.v["signed_document"])
        doc["to"] = "TVsomeOtherChannelIdThatDoesNotMatch123456"
        assert verify_migration_document(doc, self.v["old_channel_id"]) is False

    def test_verify_rejects_wrong_old_channel_id(self):
        """Identity binding: 'from' must match the expected old channel ID."""
        doc = self.v["signed_document"]
        assert verify_migration_document(doc, "TVwrongChannelId") is False

    def test_new_channel_id_is_valid(self):
        """The 'to' channel ID must decode to a valid 32-byte pubkey."""
        new_pubkey = parse_channel_id(self.v["new_channel_id"])
        assert len(new_pubkey) == 32
        assert new_pubkey.hex() == self.v["new_public_key_hex"]

    def test_migration_has_type_field(self):
        """Migration documents have 'type': 'migration' (section 5.14)."""
        assert self.v["signed_document"]["type"] == "migration"

    def test_from_and_to_differ(self):
        """A channel cannot migrate to itself."""
        assert self.v["signed_document"]["from"] != self.v["signed_document"]["to"]

    def test_migration_has_v_field(self):
        """Migration documents must have 'v': 1 (section 5.14)."""
        assert self.v["signed_document"]["v"] == 1

    def test_migration_has_seq_field(self):
        """Migration documents must have a seq field (section 5.14)."""
        assert "seq" in self.v["signed_document"]
        assert isinstance(self.v["signed_document"]["seq"], int)

    def test_verify_rejects_wrong_type(self):
        """verify_migration_document rejects docs without type=migration."""
        doc = dict(self.v["signed_document"])
        doc["type"] = "metadata"
        assert verify_migration_document(doc, self.v["old_channel_id"]) is False

    def test_verify_rejects_wrong_version(self):
        """verify_migration_document rejects docs with unsupported v."""
        doc = dict(self.v["signed_document"])
        doc["v"] = 99
        assert verify_migration_document(doc, self.v["old_channel_id"]) is False


# ── Canonical JSON Validation ──


class TestCanonicalJsonValidation:
    """PROTOCOL.md section 4.1 — null and float rejection."""

    def test_rejects_null_value(self):
        with pytest.raises(ValueError, match="null"):
            canonical_json({"key": None})

    def test_rejects_nested_null(self):
        with pytest.raises(ValueError, match="null"):
            canonical_json({"outer": {"inner": None}})

    def test_rejects_null_in_array(self):
        with pytest.raises(ValueError, match="null"):
            canonical_json({"items": [1, None, 3]})

    def test_rejects_float_value(self):
        with pytest.raises(ValueError, match="float"):
            canonical_json({"key": 3.14})

    def test_rejects_nested_float(self):
        with pytest.raises(ValueError, match="float"):
            canonical_json({"outer": {"inner": 1.0}})

    def test_accepts_valid_tltv_types(self):
        """Strings, integers, booleans, arrays, and objects are all valid."""
        result = canonical_json(
            {
                "str": "hello",
                "int": 42,
                "bool": True,
                "arr": [1, 2, 3],
                "obj": {"nested": "value"},
            }
        )
        assert isinstance(result, bytes)
