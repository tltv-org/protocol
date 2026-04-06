---
title: "Schemas & API"
weight: 2
description: "machine-readable definitions for tltv implementors"
---

Machine-readable definitions for implementors.

## OpenAPI

The [OpenAPI 3.1 specification](/schemas/openapi.yaml) defines all protocol endpoints from section 8.

## JSON Schemas

| Schema | Covers |
|---|---|
| [channel-metadata.json](/schemas/channel-metadata.json) | Signed metadata documents (section 5) |
| [channel-guide.json](/schemas/channel-guide.json) | Signed guide documents (section 6) |
| [migration.json](/schemas/migration.json) | Signed key migration documents (section 5.14) |
| [node-info.json](/schemas/node-info.json) | `/.well-known/tltv` responses (section 8.1) |
| [peer-exchange.json](/schemas/peer-exchange.json) | `/tltv/v1/peers` responses (section 8.6) |
| [defs.json](/schemas/defs.json) | Shared type definitions |

## Test Vectors

| File | Coverage |
|---|---|
| [c1-identity.json](/test-vectors/c1-identity.json) | Channel ID encoding (RFC 8032 test keypair) |
| [c2-signing.json](/test-vectors/c2-signing.json) | Canonical JSON + Ed25519 signatures |
| [c3-complete-document.json](/test-vectors/c3-complete-document.json) | Full signed metadata document |
| [c4-uri-parsing.json](/test-vectors/c4-uri-parsing.json) | URI parsing valid/invalid cases |
| [c5-guide-document.json](/test-vectors/c5-guide-document.json) | Guide document signing |
| [c6-invalid-inputs.json](/test-vectors/c6-invalid-inputs.json) | Negative test cases |
| [c7-key-migration.json](/test-vectors/c7-key-migration.json) | Key migration document |
