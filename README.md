# TLTV Federation Protocol

**TLTV** (Time Loop TV) is a federation protocol for 24/7 television channels. Each channel is an always-on server identified by an Ed25519 public key. Channels serve video over HLS and metadata over HTTPS. Any node can relay a public channel's stream without permission. There is no central discovery server, no DNS dependency, and no required registry.

This repository contains the protocol specification, machine-readable test vectors, and a Python reference implementation of the core primitives.

## Overview

- **Identity is cryptographic.** A channel is an Ed25519 keypair. The public key, base58-encoded with a `TV` prefix, is the channel's globally unique ID. No registration required.
- **Metadata is signed.** Channel metadata and guide documents are JSON signed with the channel's private key. Relays don't need to be trusted.
- **Relays are HTTP caches.** Any node can mirror a public channel. Signed metadata ensures integrity without trust.
- **URIs are self-contained.** `tltv://` URIs encode the channel ID, host, port, relay hints, and access tokens.

## Specification

The full protocol specification is in [`PROTOCOL.md`](PROTOCOL.md) (v1.0, 16 sections + appendices):

| Section | Topic |
|---|---|
| 1 | Introduction |
| 2 | Identity (Ed25519 keypairs, channel ID encoding) |
| 3 | URI scheme (`tltv://`) |
| 4 | Canonical JSON (RFC 8785) |
| 5 | Channel metadata |
| 6 | Channel guide (EPG) |
| 7 | Signatures (Ed25519 over canonical JSON) |
| 8 | Protocol endpoints |
| 9 | Stream transport (HLS) |
| 10 | Relay model |
| 11 | Discovery (peer exchange) |
| 12 | Client conformance |
| 13 | Security considerations |
| 14 | Versioning |
| 15 | V1 scope |
| 16 | Future directions (V2) |

## Schemas

Machine-readable definitions for implementors:

- [`schemas/openapi.yaml`](schemas/openapi.yaml) -- OpenAPI 3.1 spec for all protocol endpoints (section 8)
- [`schemas/channel-metadata.json`](schemas/channel-metadata.json) -- JSON Schema for signed metadata documents (section 5)
- [`schemas/channel-guide.json`](schemas/channel-guide.json) -- JSON Schema for signed guide documents (section 6)
- [`schemas/node-info.json`](schemas/node-info.json) -- JSON Schema for `/.well-known/tltv` responses (section 8.1)
- [`schemas/peer-exchange.json`](schemas/peer-exchange.json) -- JSON Schema for `/tltv/v1/peers` responses (section 8.6)
- [`schemas/migration.json`](schemas/migration.json) -- JSON Schema for signed migration documents (section 5.14)
- [`schemas/defs.json`](schemas/defs.json) -- Shared type definitions (channel IDs, signatures, timestamps, errors)

## Test Vectors

Machine-readable test vectors for validating implementations:

| File | Coverage |
|---|---|
| [`c1-identity.json`](test-vectors/c1-identity.json) | Channel ID encoding using the RFC 8032 test keypair |
| [`c2-signing.json`](test-vectors/c2-signing.json) | Canonical JSON serialization and Ed25519 signatures |
| [`c3-complete-document.json`](test-vectors/c3-complete-document.json) | Full signed metadata document round-trip |
| [`c4-uri-parsing.json`](test-vectors/c4-uri-parsing.json) | `tltv://` URI parsing: 8 valid cases + 3 invalid cases |
| [`c5-guide-document.json`](test-vectors/c5-guide-document.json) | Signed guide document with entries (section 6) |
| [`c6-invalid-inputs.json`](test-vectors/c6-invalid-inputs.json) | Invalid channel IDs, tampered documents, missing signatures |

## Reference Implementation

A Python library in `reference/python/` implements the core primitives with a single dependency (`cryptography` for Ed25519):

- **Identity** -- base58 encode/decode, channel ID creation and parsing (spec sections 2.1-2.3)
- **Signing** -- canonical JSON serialization, document signing and verification (sections 4, 7)
- **URIs** -- `tltv://` URI parsing and formatting (section 3)

### Running Tests

```bash
cd reference/python
pip install -r requirements.txt pytest
PYTHONPATH=. pytest tests/test_vectors.py -v
```

## Repository Structure

```
PROTOCOL.md                         # The specification
schemas/
  openapi.yaml                      # OpenAPI 3.1 endpoint definitions
  channel-metadata.json             # JSON Schema: signed metadata
  channel-guide.json                # JSON Schema: signed guide
  node-info.json                    # JSON Schema: /.well-known/tltv
  peer-exchange.json                # JSON Schema: /tltv/v1/peers
  defs.json                         # Shared type definitions
test-vectors/
  c1-identity.json                  # Channel ID encoding vectors
  c2-signing.json                   # Canonical JSON + signature vectors
  c3-complete-document.json         # Complete signed document vectors
  c4-uri-parsing.json               # URI parsing vectors (valid + invalid)
  c5-guide-document.json            # Signed guide document vectors
  c6-invalid-inputs.json            # Invalid input rejection vectors
reference/
  python/
    tltv/
      identity.py                   # Channel ID encoding
      signing.py                    # Canonical JSON + Ed25519 signing
      uri.py                        # tltv:// URI handling
    tests/
      test_vectors.py               # Tests against spec vectors
    requirements.txt                # cryptography>=41.0
```

## License

MIT -- see [LICENSE](LICENSE).
