# TLTV Federation Protocol

**Version:** 1.0
**Date:** March 16, 2026
**Status:** Final

---

## 1. Introduction

TLTV is a federation protocol for 24/7 television channels. Each channel is an always-on server identified by an Ed25519 public key. Channels serve video over HLS and metadata over HTTPS. Any node can relay a public channel's stream without permission. There is no central discovery server, no DNS dependency, and no required registry.

This document specifies protocol version 1: public and private channels, direct connections, open relay for public channels, peer exchange.

### 1.1 Scope

This specification defines the wire protocol between TLTV nodes, viewers, and relays. It does not define:

- How a channel generates or schedules content (management API).
- How an operator configures their server (implementation detail).
- How content is produced (showrunner, manual, or otherwise).

The current TLTV codebase is one possible implementation. Any software that implements the endpoints and behaviors defined here can participate in the network.

### 1.2 Principles

1. **Channels are infrastructure.** They run 24/7. They don't sleep.
2. **Identity is cryptographic.** Public key = channel identity. No DNS, no registrar.
3. **Single-writer authority.** Only the channel's private key can sign its metadata. No multi-party consensus needed.
4. **Relays are HTTP caches.** Any node can mirror a public channel. Signed metadata means relays don't need to be trusted.
5. **Protocol, not application.** The spec defines endpoints and data formats. Everything else is implementation choice. TLTV provides a reference implementation, but nobody has to use it.

### 1.3 Actors

| Actor | Role |
|---|---|
| **Channel** | Always-on server. Generates video, serves HLS, signs metadata. Has the private key. |
| **Viewer** | Resolves `tltv://` URIs, fetches metadata, plays HLS streams. Browser, native app, or CLI. |
| **Relay** | Caches and re-serves a public channel's HLS segments and signed metadata. Does not have the private key. |
| **Node** | Any server that implements the protocol API. A node may be a channel, a relay, or both. |

### 1.4 Conventions

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in RFC 2119. In short: MUST means absolute requirement; SHOULD means recommended with exceptions; MAY means optional.

---

## 2. Identity

### 2.1 Channel Identity

A channel's identity is an Ed25519 keypair (RFC 8032). The public key, encoded with a version prefix in base58, is the channel's globally unique identifier.

| Component | Size | Encoding |
|---|---|---|
| Public key | 32 bytes | Raw Ed25519 public key |
| Channel ID | 34 bytes | 2-byte version prefix + public key, base58-encoded (46 characters) |
| Private key (seed) | 32 bytes | Raw bytes, stored on origin server |
| Signature | 64 bytes | Base58 (86-88 characters) |

Generate a keypair and you have a globally unique channel. No registration, no coordination, no namespace authority. The Ed25519 keyspace (2^255) makes collisions effectively impossible.

### 2.2 Version Prefix

Channel IDs are prefixed with a 2-byte version prefix before base58 encoding:

```
channel_id = base58(version_prefix || pubkey_bytes)
```

V1 uses version prefix `0x1433`. This produces channel IDs that always start with the characters `TV`, making them visually distinguishable from Bitcoin addresses, Nostr keys, and other base58-encoded identifiers. The `TV` prefix was chosen because `0x1433` is mathematically guaranteed to produce a `TV`-prefixed base58 string for all possible 32-byte Ed25519 public keys.

Example channel ID: `TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3`

To extract the raw pubkey from a channel ID:

```
raw_bytes = base58_decode(channel_id)
version = raw_bytes[0:2]     # 0x1433 for V1
pubkey = raw_bytes[2:34]     # 32-byte Ed25519 public key
```

Implementations MUST verify that the version prefix is `0x1433` before accepting a V1 channel ID. An unrecognized version prefix means the ID uses a format this implementation does not support.

The version prefix identifies the **key encoding format**, not the protocol version. A future protocol version that uses the same key type (Ed25519) would use the same channel IDs. A new version prefix is only introduced when the key type or encoding changes, allowing clients to distinguish formats by the leading characters of the channel ID. Proposed future allocation: `0x1436` (`U` prefix) for a hypothetical V2 key format.

### 2.3 Base58 Encoding

Base58 uses the Bitcoin alphabet:

```
123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
```

No `0`, `O`, `l`, or `I` — avoids visual ambiguity. Case-sensitive.

Encoding procedure: treat the input bytes as a big-endian unsigned integer, repeatedly divide by 58, map remainders to the alphabet. Preserve leading zero bytes as leading `1` characters.

### 2.4 Human-Readable Names

The channel ID is the canonical identity. Human-readable names are carried in signed channel metadata (section 5). Clients display the name and expose the channel ID as an inspectable detail — like a TLS certificate fingerprint.

Nobody types channel IDs. They click `tltv://` links, scan QR codes, or browse a channel list. The ID is visible only when a user wants to verify identity.

### 2.5 URI Scheme and Case Sensitivity

Channel IDs are case-sensitive (base58 is case-sensitive). The `tltv://` URI scheme places the channel ID in the authority component of the URI. Some URI parsing libraries normalize the authority (host) to lowercase, which would corrupt the channel ID.

Implementations MUST NOT apply host normalization (lowercasing, punycode encoding, IDNA processing) to the channel ID component when parsing `tltv://` URIs. Implementations SHOULD use raw string extraction rather than standard URI host-parsing APIs. For example, in Python, use `urlparse(uri).netloc` (preserves case), not `urlparse(uri).hostname` (lowercases).

This is the same approach taken by other protocols that use case-sensitive identifiers in custom URI schemes.

### 2.6 Key Management

The private key is generated once when the channel is created and stored on the origin server. There is no recovery mechanism. The key IS the channel. Operators SHOULD back up their private key.

For planned key rotation, the operator generates a new keypair and publishes a signed migration document (section 5.14) that directs clients to the new channel. Clients that support migration will automatically follow the pointer.

If a key is compromised, the attacker can also sign documents — including a competing migration. Migration alone is not a reliable recovery mechanism after compromise. The operator should migrate immediately if they still have the key, but must also announce the situation through out-of-band channels (social media, website, other channels).

If the old key is lost entirely, migration is not possible and the operator must re-establish trust out-of-band.

---

## 3. URI Scheme

### 3.1 Format

```
tltv://<channel_id>
tltv://<channel_id>@<host:port>
tltv://<channel_id>?via=<host1>,<host2>
tltv://<channel_id>?token=<access_token>&via=<host1>
```

| Component | Required | Description |
|---|---|---|
| `tltv://` | Yes | Scheme identifier. |
| `<channel_id>` | Yes | Base58-encoded channel ID (version prefix + pubkey). |
| `@<host:port>` | No | Single peer hint (where to find this channel). |
| `?via=<hosts>` | No | Comma-separated peer hints. |
| `?token=<value>` | No | Access token for private channels (section 5.7). |

If port is omitted, the default is 443 (HTTPS). Clients MUST NOT include a default port explicitly in normalized URIs (i.e., `tltv://TVabc...@example.com` and `tltv://TVabc...@example.com:443` are equivalent, but the former is canonical).

**Parsing rules:**

- **Duplicate query parameters.** If a query parameter appears more than once (e.g., `?token=a&token=b`), the client MUST use the first occurrence and ignore subsequent duplicates. This applies to all parameters (`token`, `via`).
- **IPv6 in hints.** IPv6 addresses in `@host:port` or `via=` hints MUST use bracketed notation: `[2001:db8::1]:443`. Unbracketed IPv6 addresses are malformed and MUST be rejected. Clients MUST parse the bracket-delimited host before extracting the port.
- **Private and loopback addresses.** Clients MUST NOT contact hints that resolve to loopback addresses (`127.0.0.0/8`, `::1`), link-local addresses (`169.254.0.0/16`, `fe80::/10`), RFC 1918 private addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), IPv6 unique local addresses (`fc00::/7`), or shared/CGN address space (`100.64.0.0/10`, RFC 6598) unless the client is explicitly configured to allow local-network resolution (e.g., a development mode or LAN-only viewer). Implementations MUST normalize IPv4-mapped IPv6 addresses (`::ffff:0:0/96`, e.g. `::ffff:127.0.0.1`) to their IPv4 equivalent before applying these checks — this is a common SSRF bypass vector. This prevents URI-based SSRF attacks where a malicious URI directs the client to probe the viewer's local network.
- **Malformed hints.** Hints that do not conform to the `host:port` format (missing port, empty host, port > 65535, non-numeric port) MUST be silently skipped. Clients MUST NOT treat a malformed hint as a fatal error — try the next hint.
- **Maximum URI length.** Clients SHOULD accept URIs up to 2048 characters. Clients MAY reject URIs longer than 2048 characters.

### 3.2 Peer Hints

Since there is no central discovery, URIs include hints about where to find the channel. Hints are provided by whoever shared the URI — their client includes nodes that have worked.

```
tltv://TVMkVHiXF9...@192.168.1.100:8000
tltv://TVMkVHiXF9...?via=relay1.example.com,relay2.example.com:8443
```

Hints are advisory. A hint that doesn't respond is silently skipped. Both DNS names and IP addresses are valid as hints. DNS is more human-friendly; IP addresses have no DNS dependency. The protocol is agnostic — use whatever works for your network.

### 3.3 Resolution

When a viewer encounters a `tltv://` URI:

1. Extract the channel ID and any peer hints. If a `token` parameter is present, retain it for authenticated requests.
2. If a `token` parameter is present (private channel), skip step 3 but still fetch `/.well-known/tltv` from each hint for version negotiation (section 14.3) before proceeding to step 4. Private channels are not listed in `/.well-known/tltv`, but the `versions` array is still needed.
3. For each peer hint (in order), fetch `GET https://<hint>/.well-known/tltv`. Check if the response lists the target channel ID in `channels` or `relaying`. If it does, the hint is confirmed. Retain the `versions` array for version negotiation.
4. For each confirmed hint (or each hint directly, for private channels), negotiate the protocol version using the `versions` array from step 2 or 3 (section 14.3). Fetch `GET /tltv/v{n}/channels/<channel_id>` from that node using the negotiated version prefix (with `?token=` if present). If `/.well-known/tltv` was not fetched or did not include a `versions` array, default to V1 (`/tltv/v1/`).
5. Verify the metadata signature against the pubkey extracted from the channel ID (section 7). The `id` field in the response MUST exactly match the channel ID from the URI. If verification fails or the ID does not match, discard the response and try the next node.
6. If no hints succeed, check the viewer's cached peer list for nodes that previously served this channel.
7. Display the channel name from the verified metadata. Begin HLS playback from the `stream` URL.

If the channel cannot be found at any known node, resolution fails. The viewer MUST display a clear error — not a loading spinner.

**Expected resolution times:**

| Scenario | Time |
|---|---|
| URI with working hint, warm cache | <1 second |
| URI with working hint, cold start | 1-3 seconds |
| URI with dead hint, cached peer available | 2-5 seconds |
| No hints, peer exchange only | 5-30 seconds |

---

## 4. Canonical JSON

All signed documents in this protocol use canonical JSON serialization. The signature covers the canonical byte representation, ensuring that any implementation can reproduce and verify the signed payload.

### 4.1 Rules

Canonical JSON serialization MUST conform to RFC 8785 (JSON Canonicalization Scheme, JCS). The key requirements are:

1. **Sort keys** by UTF-16 code unit values at each nesting level, per RFC 8785 section 3.2.3.
2. **No whitespace** between tokens (no spaces after `:` or `,`, no newlines).
3. **String escaping** per RFC 8259 section 7. Characters U+0000 through U+001F MUST be escaped. Forward slash (`/`) MUST NOT be escaped.
4. **Number representation** per RFC 8785 section 3.2.2.3 (IEEE 754 serialization for floats, no leading zeros for integers, no `-0`).
5. **No duplicate keys** within the same object.
6. **Encode as UTF-8** with no byte order mark.

Implementations MUST use a JCS-conforming library or follow RFC 8785 exactly. Any conforming JCS implementation will produce correct output for this protocol.

**Additional constraints on signed TLTV documents:** signed documents MUST NOT contain floating-point numbers (all numeric values MUST be integers) and MUST NOT contain `null` values. These constraints simplify implementation — a canonicalizer that handles only strings, integers, booleans, arrays, and objects is sufficient for all TLTV documents.

### 4.2 Example

Input (with formatting):
```json
{
  "name": "Test Channel",
  "v": 1,
  "seq": 1742000000,
  "id": "TVMkVHiXF9...",
  "updated": "2026-03-14T12:00:00Z"
}
```

Canonical form (as bytes):
```
{"id":"TVMkVHiXF9...","name":"Test Channel","seq":1742000000,"updated":"2026-03-14T12:00:00Z","v":1}
```

---

## 5. Channel Metadata

Every channel publishes a signed metadata document. This is the source of truth for the channel's name, description, and stream location. Relays serve this document verbatim — the signature proves it came from the channel.

### 5.1 Format

```json
{
  "v": 1,
  "seq": 1742000000,
  "id": "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3",
  "name": "TLTV Channel One",
  "description": "24/7 experimental television",
  "icon": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/icon.png",
  "tags": ["experimental", "generative", "archive"],
  "language": "en",
  "timezone": "America/New_York",
  "stream": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/stream.m3u8",
  "guide": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/guide.json",
  "access": "public",
  "origins": ["origin.example.com:443"],
  "updated": "2026-03-14T12:00:00Z",
  "signature": "<base58-encoded Ed25519 signature>"
}
```

### 5.2 Fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `v` | integer | Yes | Metadata format version. MUST be `1`. |
| `seq` | integer | Yes | Unix epoch timestamp in seconds (section 5.5). |
| `id` | string | Yes | Channel ID (version prefix + pubkey, base58). |
| `name` | string | Yes | Human-readable channel name. 1-64 Unicode code points. |
| `description` | string | No | Channel description. Max 256 Unicode code points. |
| `icon` | string | No | Path to channel icon/logo image, relative to the serving node. See section 5.9. |
| `tags` | array | No | Channel categories/tags for discovery. See section 5.10. |
| `language` | string | No | Primary language of the channel. ISO 639-1 code (e.g., `"en"`, `"ja"`, `"es"`). |
| `timezone` | string | No | Channel's preferred timezone. IANA timezone name (e.g., `"America/New_York"`, `"Europe/London"`, `"Asia/Tokyo"`). See section 5.12. |
| `stream` | string | Yes | Path to HLS manifest, relative to the serving node. |
| `guide` | string | No | Path to JSON guide endpoint, relative to the serving node. |
| `access` | string | No | `"public"` (default) or `"token"`. Unrecognized values: see below. See section 5.7. |
| `on_demand` | boolean | No | If `true`, stream starts on first viewer request. See section 5.11. |
| `status` | string | No | `"active"` (default) or `"retired"`. Unrecognized values: see below. See section 5.13. |
| `origins` | array | No | List of `host:port` strings for this channel's origin nodes. See section 5.8. |
| `updated` | string | Yes | ISO 8601 timestamp in UTC. Format: `YYYY-MM-DDTHH:MM:SSZ`. Second precision, no fractional seconds (section 6.4). |
| `signature` | string | Yes | Base58-encoded Ed25519 signature (section 7). |

String length constraints are measured in Unicode code points (not grapheme clusters, not UTF-8 bytes). A single emoji like U+1F600 counts as 1 code point.

**Unrecognized enum values.** If the `access` field contains a value other than `"public"` or `"token"`, clients MUST treat the channel as inaccessible and MUST NOT attempt to stream it. This ensures forward compatibility — a future access mode (e.g., a V2 authentication scheme) will not be silently treated as public by V1 clients. Similarly, if the `status` field contains an unrecognized value, clients SHOULD treat the channel as inactive and display the raw value for user inspection.

The `stream` and `guide` fields MUST be absolute paths starting with `/`. They are resolved relative to the node's origin (scheme + host + port). This means a relay serves the same paths as the origin — the signed metadata is valid on any node.

### 5.3 Signing

The signature covers all fields except `signature` itself:

1. Construct a JSON object containing all fields except `signature`.
2. Serialize to canonical JSON (section 4).
3. Sign the resulting UTF-8 bytes with Ed25519 using the channel's private key.
4. Base58-encode the 64-byte signature.
5. Add the `signature` field to the document.

### 5.4 Verification

A client or relay verifies metadata by:

1. Parse the JSON document.
2. **Identity binding.** Verify that the `id` field exactly matches the channel ID that was requested (from the URI or path parameter). If they do not match, the document MUST be discarded. This prevents a malicious node from returning a different channel's valid metadata.
3. Remove the `signature` field. Retain all other fields (including any unknown fields).
4. Serialize the remaining object to canonical JSON (section 4).
5. Decode the channel ID from `id` to extract the 32-byte pubkey (section 2.2).
6. Decode the `signature` value from base58 to obtain the 64-byte signature.
7. Verify the Ed25519 signature against the canonical JSON bytes and the public key.

If verification fails at any step, the document MUST be discarded.

### 5.5 Updates and Ordering

The channel updates metadata by signing a new document with a higher `seq` value and a later `updated` timestamp.

**Ordering rules.** The `seq` field is the primary ordering mechanism. A document with a higher `seq` always supersedes one with a lower `seq`, regardless of `updated` timestamp. The `updated` timestamp provides human-readable context but is not the ordering authority.

- The `seq` value MUST be a positive integer representing a Unix epoch timestamp in seconds (the number of seconds since 1970-01-01T00:00:00Z). This ensures `seq` values are globally monotonic and recoverable — after state loss, the current time always exceeds any previously issued value.
- If multiple updates occur within the same second, the channel MUST use the current timestamp or `last_seq + 1`, whichever is greater.
- Relays MUST replace their cached copy when they receive a document with a higher `seq`.
- Clients MUST reject metadata with a `seq` strictly lower than their cached copy for the same channel. If the incoming `seq` equals the cached `seq`, the client MUST accept the document only if the `signature` field is identical to the cached copy's `signature`; otherwise the client MUST discard the incoming document and retain its cache. (Ed25519 is deterministic — the same key signing the same canonical content always produces the same signature. Comparing signature strings is sufficient: if the signatures match, the signed content is identical by definition. This avoids ambiguity about JSON formatting differences between servers.)

**Persistence.** Operators SHOULD persist the last issued `seq` value to durable storage. In the event of state loss, using the current Unix timestamp as `seq` provides automatic recovery — it is guaranteed to exceed any previously issued value (assuming the system clock is approximately correct).

**Future timestamp rejection.** Clients MUST reject any signed document (metadata, guide, or migration) with an `updated` or `migrated` timestamp more than 1 hour in the future relative to the client's clock. This limits the damage from key compromise — an attacker cannot sign a far-future timestamp to permanently supersede the legitimate operator's updates. Because `seq` is also a timestamp, the same 1-hour tolerance applies: clients MUST reject any signed document with a `seq` value more than 3600 seconds ahead of the client's current Unix time.

### 5.6 Unknown Fields and Size Limits

Receivers MUST ignore fields they do not recognize. This allows future additive extensions without a version bump (section 14.2). Unknown fields MUST be preserved when re-serving signed documents (removing them would invalidate the signature).

**Size limits.** Implementations SHOULD reject signed documents larger than 64 KB. This prevents abuse through oversized unknown fields while leaving ample room for future extensions.

### 5.7 Private Channels

A channel with `"access": "token"` is a private channel. Access requires a bearer token.

**Behavior:**

- Private channels are NOT listed in `/.well-known/tltv` (section 8.1).
- All protocol endpoints for the channel require a `?token=<value>` query parameter.
- Without a valid token, the node MUST return 403 Forbidden.
- The token is included in the `tltv://` URI: `tltv://<channel_id>?token=<value>&via=<hint>`.
- Sharing the URI = sharing access. Anyone with the URI can watch.
- The operator manages tokens through the management API (not part of this protocol).
- Rotating the token invalidates all existing URIs.
- Conforming relays MUST NOT relay private channels. The relay model (section 10) applies only to public channels. Note: the protocol cannot prevent a token holder from restreaming content; this is a conformance rule for TLTV nodes, not a hard security property.

**Token format.** Tokens are opaque URL-safe strings, maximum 256 characters. The token format and generation are implementation-specific. Tokens MUST contain only characters that are safe in URI query parameters without percent-encoding (unreserved characters per RFC 3986: `A-Z a-z 0-9 - . _ ~`).

**HLS playlist graph authentication.** The `?token=` parameter on the stream endpoint authenticates the initial manifest request, but URIs within HLS playlists do not inherit query parameters from the parent URL (per RFC 3986 relative reference resolution). For private channels, the node MUST embed the token in **every URI** within the HLS playlist graph. This includes:

- **Segment URIs** (`.ts`, `.m4s`, `.fmp4`) in media playlists.
- **Variant playlist URIs** in multivariant (master) playlists (`EXT-X-STREAM-INF`).
- **Rendition playlist URIs** for alternate audio or subtitle tracks (`EXT-X-MEDIA`).
- **Encryption key URIs** (`EXT-X-KEY`, `EXT-X-SESSION-KEY`), if any.
- **Map URIs** (`EXT-X-MAP`), if any.

This ensures players can traverse the full playlist graph without special token-propagation logic:

```
#EXTM3U
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:42
#EXTINF:2.0,
seg-0042.ts?token=abc123
#EXTINF:2.0,
seg-0043.ts?token=abc123
```

For multivariant playlists, variant and rendition URIs also require the token:

```
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x720
video-720p.m3u8?token=abc123
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
video-360p.m3u8?token=abc123
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",URI="audio-eng.m3u8?token=abc123"
```

This means all playlists for private channels must be generated per-request to include the token. For public channels, playlists remain static. This pattern is standard in the IPTV ecosystem and is compatible with all major HLS players and IPTV clients.

**Implementation simplification.** Implementations that want to avoid the complexity of tokenizing multivariant playlists MAY serve private channels as single media playlists only (no multivariant playlist, no alternate renditions). This is a valid implementation choice — the node serves a single quality level with the token embedded in segment URIs. Multivariant playlist support for private channels is not required, but if offered, the full playlist graph MUST be tokenized as described above.

**Token leakage.** This is a capability-URL model (see W3C TAG Finding on Capability URLs). Tokens in query parameters appear in server access logs, browser history, HTTP Referer headers, and shared URIs. Nodes serving private channels MUST include the following headers on **all** responses for that channel:

- `Referrer-Policy: no-referrer` — prevents token leakage via the Referer header.
- `Cache-Control: private, no-store` — prevents tokens and private content from being stored in shared caches (CDN, proxy) or persisted to disk by the client.

Operators should understand that sharing the `tltv://` URI shares the token — there is no way to share a private channel reference without sharing access in V1.

Private channels provide access control at the "unlisted video with password" level: simple and effective. Per-viewer authentication and fine-grained revocation are deferred to V2.

If the `access` field is absent, the channel is public.

### 5.8 Signed Origins

The optional `origins` field lists the `host:port` addresses of nodes that originate this channel. Since this field is inside signed metadata, it cannot be forged by relays. Only the channel's private key holder can add or remove origins.

**Origin authority.** All nodes listed in `origins` are authoritative. They hold the channel's private key, can sign metadata, and serve the channel's stream. From the protocol's perspective, every origin is equivalent — any origin can serve as the primary or as a mirror (section 10.8). A node NOT listed in `origins` that serves the channel is a relay, not an origin.

Viewers that see `origins` know which nodes are authoritative for the stream content. Viewers SHOULD prefer origin nodes over relays when both are available (section 10.5), as origins provide stronger stream authenticity guarantees (section 13.4). When the current origin is unreachable, viewers MUST try other origins from the `origins` list before falling back to relays (section 12.1).

If `origins` is absent, the viewer has no cryptographic way to distinguish origin from relay. The channel operator is encouraged to include `origins` but is not required to.

Hints use the same `host:port` format as peer exchange (section 8.6).

**Updating origins.** The operator adds or removes origins by signing new metadata with an updated `origins` list and a higher `seq`. Clients and relays MUST use the `origins` list from the highest-`seq` metadata they have verified. Origins from superseded (lower-`seq`) metadata MUST be discarded.

**Stale origin protection.** When an origin is removed from the `origins` list (e.g., a server is decommissioned), clients that refresh metadata will learn the updated list within the metadata cache lifetime (recommended `max-age=60`, section 8.8). A decommissioned server that is later taken over by an attacker cannot forge valid metadata (no private key), and clients that have refreshed metadata will not have it in their `origins` list. Clients MUST refresh metadata at least once per cache lifetime to stay current with origin changes.

**Censorship considerations.** The `origins` field provides stream authenticity at the cost of origin visibility. A signed document listing origin server addresses propagates across the network and cannot be retracted — it tells anyone, including censors, exactly which servers to target. Operators concerned about censorship resistance SHOULD omit the `origins` field and distribute their channel through multiple relays. Without `origins`, a censor must identify and take down every node serving the channel rather than targeting a declared origin. Using proxy services or CDNs as intermediaries provides additional indirection. The real censorship resistance story is V2: key delegation (section 16.2) enables multiple independent signing nodes so no single server is critical, and Tor/I2P transport (section 16.6) enables hidden origins that never expose their network address.

### 5.9 Channel Icon

The optional `icon` field provides a path to a channel logo or icon image. This is the visual identity of the channel — displayed in channel lists, EPG guides, and IPTV clients.

The path MUST be an absolute path starting with `/`, resolved relative to the serving node (same convention as `stream` and `guide`). The node MUST serve the image at that path. Relays MUST fetch and re-serve the icon from upstream, just as they do for HLS segments.

**Image requirements:**

- Format: PNG or JPEG. Nodes MUST support both. SVG is NOT required.
- Dimensions: SHOULD be square. Recommended 256x256 or 512x512 pixels. Clients MAY resize.
- Size: SHOULD be under 256 KB. Clients MAY reject images larger than 1 MB.

If `icon` is absent, the client has no channel image. Clients SHOULD display a placeholder (e.g., the first letter of the channel name).

**IPTV mapping.** The `icon` path maps directly to the XMLTV `<icon src="...">` element in channel entries and to the `tvg-logo` attribute in M3U playlists. When generating XMLTV or M3U output, the node resolves the relative path to an absolute URL using its own origin.

### 5.10 Channel Tags

The optional `tags` field provides channel-level categories for discovery and sorting. Tags are free-text strings that describe the channel's content, genre, or style.

**Constraints:**

- Array of strings. Maximum 5 tags.
- Each tag: 1-32 Unicode code points, lowercase recommended.
- No predefined vocabulary. Operators choose tags that describe their channel.
- Examples: `"film"`, `"music"`, `"ambient"`, `"news"`, `"experimental"`, `"archive"`, `"generative"`.

Tags are advisory — clients use them for grouping and filtering but MUST NOT treat them as authoritative content ratings. A channel tagged `"film"` is the operator's self-description, not a verified classification.

**IPTV mapping.** When generating M3U playlists, the first tag maps to the `group-title` attribute — the standard mechanism IPTV clients (TiviMate, IPTV Smarters, Kodi PVR) use to organize channels into folders. When multiple tags are present, implementations MAY list the channel in multiple groups.

**Discovery.** Viewers browsing a peer exchange list (section 8.6) see only channel IDs and names. Tags — carried in signed metadata — give viewers a way to filter and sort large channel lists without fetching every channel's guide. A viewer with 1000 collected channels can filter to `"film"` channels or `"ambient"` channels without additional network requests.

### 5.11 On-Demand Channels

A channel with `"on_demand": true` is an on-demand channel. On-demand channels publish metadata and guides like any other channel, but only produce a stream when at least one viewer requests it.

**Behavior:**

- The channel's metadata and guide are always available. The guide shows the full schedule — what would be playing at any given time.
- When no viewer is connected, the stream endpoint returns 503 (`stream_unavailable`). This is normal, not an error.
- When a viewer requests the stream, the node starts producing HLS segments. There is a brief warm-up delay (typically 2-5 seconds) before the first segments are available.
- After all viewers disconnect, the node MAY stop producing segments after a cooldown period (implementation-defined, recommended 30-60 seconds).
- On-demand channels MUST NOT be relayed (section 10.2). A relay continuously polls for segments, which would keep the channel permanently on — defeating the purpose.
- On-demand channels appear in `/.well-known/tltv` and peer exchange like any other public channel.

**Why on-demand matters.** Always-on channels require continuous encoding resources (CPU, memory, bandwidth) whether anyone is watching or not. For operators running many channels — ten thematic channels on a single server, for example — on-demand mode lets them offer a full channel lineup without proportional resource costs. The guide is populated, the channels appear in the EPG, viewers can browse and select — but only the channels being watched consume encoding resources.

**Viewer experience.** A viewer selecting an on-demand channel experiences a brief cold-start delay (2-5 seconds longer than an always-on channel). Clients that understand the `on_demand` field SHOULD display "Starting..." rather than "Stream unavailable" during this warm-up. Clients that do not recognize `on_demand` treat the 503 as a normal stream interruption and retry with backoff — which also works, since the stream becomes available within seconds.

**Distinction from a dead channel.** An on-demand channel serves metadata and a guide at all times — proving it is alive and maintained. A dead channel stops serving metadata entirely, or its metadata `updated` timestamp grows stale. Viewers can distinguish the two by checking whether the metadata endpoint responds with a valid, recently-signed document.

If the `on_demand` field is absent, the channel is assumed to be always-on.

### 5.12 Channel Timezone

The optional `timezone` field declares the channel's preferred timezone. This is a display hint — all protocol timestamps remain in UTC.

The value MUST be a valid IANA timezone name from the [IANA Time Zone Database](https://www.iana.org/time-zones) (e.g., `"America/New_York"`, `"Europe/London"`, `"Asia/Tokyo"`, `"UTC"`). Do not use fixed UTC offsets like `"+05:00"` or deprecated abbreviations like `"EST"` — IANA names handle daylight saving transitions correctly.

**Usage.** Clients MAY use this field to:

- Display guide times in the channel's local time ("This channel's schedule is in Eastern time").
- Indicate when the channel's operators are likely active.
- Group channels by timezone in multi-channel views.

If `timezone` is absent, clients SHOULD display all times in the viewer's local timezone or UTC.

### 5.13 Channel Status

The optional `status` field signals the channel's lifecycle state.

| Value | Meaning |
|---|---|
| `"active"` | Channel is operating normally. This is the default if `status` is absent. |
| `"retired"` | Channel is permanently shut down. The operator has intentionally ended the channel. |

A signed metadata document with `"status": "retired"` is a cryptographic declaration that the channel is done. This is the only way to distinguish "permanently gone" from "temporarily offline."

**Behavior when retired:**

- The origin node SHOULD continue serving the signed metadata (with `"status": "retired"`) for at least 30 days after retirement, so clients and relays learn the channel's status.
- The stream endpoint MAY return 503 or stop serving entirely.
- Relays MUST stop relaying a retired channel. They SHOULD serve the final signed metadata for reference but MUST NOT poll for new stream segments.
- Peers MUST remove retired channels from their peer exchange responses.
- Clients SHOULD display the channel as retired and stop attempting reconnection.

If `status` is absent, the channel is assumed to be active.

### 5.14 Key Migration

A channel MAY declare migration to a new identity by publishing a signed migration document. This allows planned key rotation — moving to a new identity while the channel's audience follows automatically, without out-of-band coordination.

**What migration solves:** proactive key rotation, infrastructure changes (moving to a different key management setup), and operational handoff (transferring a channel to a new operator). In all these cases the operator possesses the old key and signs the migration voluntarily.

**What migration does not solve:** if the key is lost (no backup, server destroyed), the operator cannot sign anything and migration is not possible (see section 2.6). If the key is compromised (an attacker also has the key), migration is a race — both the legitimate operator and the attacker can sign migration documents pointing to different targets, and nodes have no way to distinguish them. Migration is not a reliable recovery mechanism after compromise. Operators who suspect key exposure should migrate immediately, but should also announce the situation through out-of-band channels as a fallback.

**Migration document format:**

```json
{
  "v": 1,
  "seq": 1742000000,
  "type": "migration",
  "from": "<old-channel-id>",
  "to": "<new-channel-id>",
  "reason": "key rotation",
  "migrated": "2026-03-14T12:00:00Z",
  "signature": "<signed by old key>"
}
```

**Fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `v` | integer | Yes | Migration document format version. MUST be `1`. |
| `seq` | integer | Yes | Unix epoch timestamp in seconds. Same rules as metadata `seq` (section 5.5). A migration document with a higher `seq` supersedes one with a lower `seq` for the same `from` channel. |
| `type` | string | Yes | MUST be `"migration"`. Distinguishes this from regular metadata (which has no `type` field). |
| `from` | string | Yes | Channel ID of the old (migrating) channel. |
| `to` | string | Yes | Channel ID of the new channel. MUST be a valid V1 channel ID. |
| `reason` | string | No | Human-readable reason for migration. Max 256 Unicode code points. |
| `migrated` | string | Yes | Timestamp of migration. ISO 8601 UTC (`...Z`). |
| `signature` | string | Yes | Base58-encoded Ed25519 signature (section 7). |

The `v` field allows future versions to change migration document semantics without ambiguity. The `seq` field provides replay protection and ordering — clients MUST reject a migration document with a `seq` lower than a previously seen migration for the same `from` channel, applying the same ordering and future-timestamp rules as metadata `seq` (section 5.5). Migration documents, metadata documents, and guide documents each maintain independent `seq` sequences — a migration `seq` is compared only against other migration documents for the same `from` channel.

The `to` field MUST be a different channel ID from `from`. A channel cannot migrate to itself. The migration document MUST NOT include the new channel's private key or any secrets — it is a signed pointer, nothing more.

**Signing procedure:**

The migration document is signed by the **old** channel's private key:

1. Construct the document with all fields except `signature`.
2. Serialize to canonical JSON (section 4).
3. Sign with the old channel's Ed25519 private key.
4. Base58-encode the 64-byte signature.
5. Add the `signature` field.

**Verification:**

1. Confirm `"type"` is `"migration"`. This distinguishes the verification path from metadata and guide documents.
2. Confirm `"v"` is a supported version (MUST be `1`).
3. **Identity binding.** Verify that the `from` field exactly matches the channel ID that was requested (from the URI or path parameter). If they do not match, the document MUST be discarded. This prevents a malicious node from returning a migration document for a different channel.
4. Verify that the `to` field is a valid V1 channel ID (correct version prefix, correct length) and differs from `from`.
5. Remove the `signature` field.
6. Serialize to canonical JSON.
7. Extract the public key from the `from` field (the old channel ID).
8. Decode the signature from base58 to 64 bytes.
9. Verify the Ed25519 signature against the canonical JSON bytes.
10. Apply `seq` replay protection: reject the document if its `seq` is lower than a previously verified migration for the same `from` channel (section 5.5).

Verification extracts the public key from the `from` field, not an `id` field. The `from` field serves the same identity-binding role as `id` does in metadata and guide documents. Implementations MUST branch their verification logic on the `type` field — migration documents use `from` for identity binding, while metadata and guide documents use `id`.

**Serving:**

The migration document is served at the old channel's metadata endpoint (`GET /tltv/v1/channels/{old-id}`). When a node has a migration document for a channel, it returns the migration document instead of the regular metadata. The `type` field distinguishes migration documents from regular metadata — regular metadata has no `type` field. The response `Content-Type` remains `application/json`.

The origin node SHOULD continue serving the migration document for at least 90 days after migration, giving clients, relays, and cached URIs time to discover the migration.

**Private channel migration.** When a private channel publishes a migration document, the token requirement on the metadata endpoint remains in effect — only holders of the existing token can discover the migration. The migration document itself contains no secrets (only channel IDs), but revealing that a private channel has migrated and where it went is a privacy-relevant signal.

**Client behavior:**

When a client fetches metadata and receives a document with `"type": "migration"`:

1. Verify the signature against the public key extracted from the `from` field.
2. Verify that the `from` field matches the channel ID that was requested.
3. If valid, follow the migration by fetching metadata for the `to` channel ID from the peer hints originally used or from the client's cached peer list.
4. Alert the viewer that the channel has migrated (e.g., "This channel has moved to a new identity").
5. Update any cached references (bookmarks, peer lists) to point to the new channel ID.

Clients that do not understand migration documents will see an unexpected document with no `name`, `stream`, or other expected metadata fields. They will treat this as a resolution failure and try the next node — which is correct graceful degradation for V1 clients that predate migration support.

**Migration chains:**

Migration chains (A -> B -> C) are supported. When following a migration, if the target channel has also migrated, the client follows the chain. Clients MUST impose a maximum chain depth of 5 hops to prevent loops or abuse. If the chain exceeds 5 hops, the client MUST report a resolution failure.

A migration from A to B followed later by a migration from B to C is valid — it means the channel has moved twice. Clients that cached the A -> B migration will learn about B -> C when they fetch B's metadata.

**Irreversibility:**

Migration is permanent and irreversible. Once a channel signs a migration document, the old identity is declaring itself retired in favor of the new one. The old key's sole remaining purpose is to authenticate the migration pointer. A node MUST NOT serve regular metadata for a channel after it has published a migration document — the migration supersedes all metadata.

**Interaction with channel status:**

A migration document implicitly retires the old channel. Nodes SHOULD NOT publish `"status": "retired"` metadata alongside a migration — the migration document is sufficient and more informative (it tells the client where to go). If a client encounters both, the migration document takes precedence.

**Relays and migration:**

When a relay fetches updated metadata for a channel and receives a migration document, it MUST cache and re-serve the migration document verbatim (the signature proves authenticity). The relay MUST stop relaying the old channel's stream. The relay MAY begin relaying the new channel if it is public.

---

## 6. Channel Guide

A channel MAY publish a program guide describing what is or will be on air. The guide is a signed document covering a time window.

### 6.1 Format

```json
{
  "v": 1,
  "seq": 1742000042,
  "id": "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3",
  "from": "2026-03-14T05:00:00Z",
  "until": "2026-03-16T05:00:00Z",
  "entries": [
    {
      "start": "2026-03-15T00:00:00Z",
      "end": "2026-03-15T00:15:00Z",
      "title": "Channel One Intro"
    },
    {
      "start": "2026-03-15T00:15:00Z",
      "end": "2026-03-15T01:00:00Z",
      "title": "Evening Clips",
      "description": "Curated selection of short films",
      "category": "film"
    },
    {
      "start": "2026-03-15T01:00:00Z",
      "end": "2026-03-15T01:30:00Z",
      "title": "Channel Two Documentary Hour",
      "category": "relay",
      "relay_from": "TVabc123..."
    }
  ],
  "updated": "2026-03-14T03:00:00Z",
  "signature": "<base58>"
}
```

### 6.2 Top-Level Fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `v` | integer | Yes | Guide format version. MUST be `1`. |
| `seq` | integer | Yes | Unix epoch timestamp in seconds. Same rules as metadata `seq` (section 5.5). |
| `id` | string | Yes | Channel ID (version prefix + pubkey, base58). |
| `from` | string | Yes | Start of the window this guide covers. ISO 8601 UTC (`...Z`). |
| `until` | string | Yes | End of the window. ISO 8601 UTC (`...Z`). |
| `entries` | array | Yes | Ordered list of guide entries. MAY be empty. |
| `updated` | string | Yes | When this guide was last generated. ISO 8601 UTC (`...Z`). |
| `signature` | string | Yes | Base58-encoded Ed25519 signature. |

The `seq` timestamp for guides is independent from the metadata `seq` timestamp — each signed document type maintains its own sequence.

### 6.3 Entry Fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `start` | string | Yes | Program start time. ISO 8601 UTC (`...Z`). |
| `end` | string | Yes | Program end time. ISO 8601 UTC (`...Z`). |
| `title` | string | Yes | Program title. 1-128 UTF-8 characters. |
| `description` | string | No | Program description. Max 512 UTF-8 characters. |
| `category` | string | No | Free-text category. Max 32 UTF-8 characters. |
| `relay_from` | string | No | Channel ID of the source channel being relayed during this entry. |

Entries MUST be ordered by `start` time. Entries MUST NOT overlap. Gaps between entries are permitted — they indicate unscheduled time (the channel is still broadcasting, but the guide has no listing).

The `relay_from` field indicates that this entry is relaying content from another channel. Clients that understand this field MAY display a link to the source channel. Clients that don't understand it display the entry normally (per section 5.6 — unknown fields are ignored). This enables use cases like cross-channel promotion and channel surfing previews, where a channel relays short clips from many channels for viewers to discover.

**Note:** `relay_from` is a display hint, not a verifiable claim. A channel can assert `relay_from` any other channel ID without proof. Clients SHOULD NOT treat it as authoritative evidence of a relationship between channels.

### 6.4 Timestamps

All timestamps in signed documents MUST be ISO 8601 in UTC with a `Z` suffix:

```
2026-03-15T00:00:00Z
```

- Second precision. No fractional seconds.
- No timezone offsets. UTC only. Channels that want to communicate their local timezone use the `timezone` metadata field (section 5.12).
- Clients convert to the viewer's local time (or the channel's `timezone`) for display.

This uniformity eliminates timezone normalization as a source of signature verification failures — all implementations produce identical byte representations for the same instant in time.

### 6.5 Signing and Verification

Same procedure as channel metadata (sections 5.3 and 5.4): sign all fields except `signature` using canonical JSON. The identity binding requirement applies — the `id` field in the guide MUST match the requested channel ID.

### 6.6 XMLTV and IPTV Compatibility

Nodes SHOULD also serve the guide in XMLTV format at the path ending `.xml` (e.g., `/tltv/v1/channels/{id}/guide.xml`). The XMLTV document is NOT signed — it is a convenience format for compatibility with existing EPG tools. Clients that require authenticity MUST use the signed JSON guide.

**IPTV integration.** XMLTV is the standard EPG format used by IPTV clients: TiviMate, Emby, Plex Live TV, Jellyfin, IPTV Smarters, Kodi PVR, and others. A TLTV channel that serves XMLTV is immediately consumable by these applications. The HLS stream URL can be used directly by any IPTV player — it is standard HLS.

Channel metadata fields map to standard IPTV conventions:

| TLTV field | XMLTV element | M3U attribute |
|---|---|---|
| `name` | `<display-name>` | `tvg-name` |
| `icon` | `<icon src="...">` | `tvg-logo` |
| `tags[0]` | — | `group-title` |
| `language` | `<display-name lang="...">` | — |
| `id` | `<channel id="...">` | `tvg-id` |

A TLTV node MAY aggregate multiple channels' guides into a single XMLTV document and M3U playlist (the standard IPTV format pair), making the node appear as an IPTV provider to existing apps. This requires no protocol changes — it is a presentation concern built on top of the per-channel guide endpoints.

This compatibility means TLTV channels can federate with the existing IPTV ecosystem. The IPTV network is already out there — the problems are discovery and inter-channel communication. TLTV solves both without requiring viewers to install new software.

**IPTV and failover.** IPTV clients consume HLS stream URLs directly and have no awareness of TLTV protocol features such as signed metadata, the `origins` field, or automatic failover between origins (section 10.8). If a stream URL becomes unreachable, the IPTV client reports "stream unavailable" — it cannot discover or switch to a mirror. Operators who need failover for IPTV clients should use standard infrastructure techniques (DNS failover, load balancer, CDN) so that the HLS URL remains stable across origin changes. TLTV-native viewers handle this automatically through the `origins` list.

### 6.7 Guide Aggregation

The protocol does not define a multi-channel aggregated guide. Each channel publishes its own guide independently. A viewer or relay that tracks multiple channels constructs a combined view client-side by fetching each channel's guide separately.

This is lightweight: each guide is a few KB of JSON. Fetching 100 channels' guides is 100 small HTTP requests (parallelized, cached locally). The HLS stream (megabits per second) dwarfs guide data by orders of magnitude. Aggregation is never a bottleneck.

---

## 7. Signatures

All signed documents use Ed25519 (RFC 8032) over canonical JSON (section 4).

### 7.1 Signing Procedure

```
payload = canonical_json(document_without_signature_field)
signature_bytes = ed25519_sign(private_key, payload)
signature_string = base58_encode(signature_bytes)
```

The `payload` is the UTF-8 byte representation of the canonical JSON string.

### 7.2 Verification Procedure

```
payload = canonical_json(document_without_signature_field)
signature_bytes = base58_decode(document.signature)
pubkey_bytes = extract_pubkey(document.id)   # strip version prefix
valid = ed25519_verify(pubkey_bytes, payload, signature_bytes)
```

Verification MUST be performed before trusting any signed document. A failed verification means the document was forged or corrupted.

### 7.3 Which Documents Are Signed

| Document | Signed | Why |
|---|---|---|
| Channel metadata | Yes | Proves channel identity and ownership of name/stream/guide. |
| Channel guide | Yes | Proves the schedule came from the channel. |
| Migration document | Yes | Proves the old channel authorized the migration (section 5.14). Signed by the old key. Identity binding uses `from`, not `id`. |
| Node info | No | Node-local data, not channel-authoritative. |
| Peer list | No | Node-local data, advisory only. |
| HLS manifest | No | Standard HLS. Authenticity established by the metadata signature chain. |

---

## 8. Protocol Endpoints

These are the endpoints a TLTV node exposes to the network. All are read-only (GET). The management API (creating channels, setting schedules, generating content) is implementation-specific and not part of this protocol.

### 8.1 Node Info

```
GET /.well-known/tltv
```

Returns the node's identity and the channels it serves.

**Response** (200):

```json
{
  "protocol": "tltv",
  "versions": [1],
  "channels": [
    {
      "id": "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3",
      "name": "TLTV Channel One"
    }
  ],
  "relaying": [
    {
      "id": "TVabc123...",
      "name": "Some Other Channel"
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `protocol` | string | Yes | MUST be `"tltv"`. |
| `versions` | array | Yes | Protocol versions this node supports. Array of integers. MUST include `1`. |
| `channels` | array | Yes | Public channels this node originates. MAY be empty. |
| `relaying` | array | Yes | Public channels this node relays. MAY be empty. |

Each entry in `channels` and `relaying`:

| Field | Type | Required |
|---|---|---|
| `id` | string | Yes |
| `name` | string | Yes |

The `name` fields in this response are **advisory, not authoritative**. For `channels`, the name comes from the node's own configuration. For `relaying`, the name comes from the last verified channel metadata. In both cases, viewers MUST NOT treat these names as verified until they fetch the channel's signed metadata (section 5.4). A malicious node can return any name it wants in this unsigned response.

This endpoint MUST NOT require authentication. It is the entry point for URI resolution and peer discovery. Private channels (section 5.7) MUST NOT appear in this response.

### 8.2 Channel Metadata

```
GET /tltv/v1/channels/{id}
GET /tltv/v1/channels/{id}?token=<value>
```

Returns the signed channel metadata document (section 5), or a signed migration document (section 5.14) if the channel has migrated to a new identity.

**Path parameters:**
- `{id}`: Base58-encoded channel ID (with version prefix).

**Query parameters:**
- `token`: Required for private channels. Ignored for public channels.

**Response** (200): Channel metadata or migration document JSON with `Content-Type: application/json`. A migration document has `"type": "migration"`; regular metadata has no `type` field. Clients MUST check for the `type` field to distinguish the two.

**Response** (403): Valid channel, but access denied (private channel, missing or invalid token).

**Response** (404): This node does not serve this channel.

```json
{"error": "channel_not_found"}
```

The client MUST verify the signature before trusting the response. For migration documents, verification uses the `from` field (section 5.14) instead of the `id` field.

### 8.3 Channel Stream

```
GET /tltv/v1/channels/{id}/stream.m3u8
GET /tltv/v1/channels/{id}/stream.m3u8?token=<value>
```

Returns the HLS manifest for the channel's live stream.

**Response** (200): HLS manifest with `Content-Type: application/vnd.apple.mpegurl`.

**Response** (302): Redirect to the HLS manifest at another path on this node or an external URL. Viewers MUST follow redirects.

**Response** (403): Private channel, missing or invalid token.

**Response** (404): Channel not found.

**Response** (503): Channel exists but stream is currently unavailable.

If the node responds with 200, the manifest MUST be a valid HLS playlist. Segment URIs in the manifest SHOULD be relative paths. The node MUST serve those segments at the resolved paths.

For private channels, the manifest MUST include the access token in each segment URI (section 5.7). The node MUST also accept the token on segment requests. Segment URIs in the manifest for private channels will look like `seg-0042.ts?token=<value>`.

If the node responds with 302, the `Location` header contains the actual HLS manifest URL. The redirect target MAY be on the same node (e.g., `/hls/channel-one/stream.m3u8`) or an external CDN. For private channels, the redirect target MUST include the token in the query string. The redirect MUST NOT target a different origin (cross-origin redirect) for private channels — this would leak the token to a third-party host via the URL. Same-origin redirects (same host and port, different path) with the token are permitted.

A relay MUST NOT redirect to the origin server. A relay serves from its own cache or returns 503 if the cache is empty.

### 8.4 Channel Guide (JSON)

```
GET /tltv/v1/channels/{id}/guide.json
GET /tltv/v1/channels/{id}/guide.json?token=<value>
```

Returns the signed channel guide document (section 6).

**Response** (200): Guide JSON with `Content-Type: application/json`.

**Response** (403): Private channel, missing or invalid token.

**Response** (404): Channel not found or no guide available.

The client MUST verify the guide signature before trusting the response.

### 8.5 Channel Guide (XMLTV)

```
GET /tltv/v1/channels/{id}/guide.xml
GET /tltv/v1/channels/{id}/guide.xml?token=<value>
```

Returns the channel guide in XMLTV format.

**Response** (200): XMLTV document with `Content-Type: application/xml`.

**Response** (403): Private channel, missing or invalid token.

**Response** (404): Channel not found or no guide available.

This document is NOT signed. It is a convenience format for IPTV client compatibility. Clients requiring authenticity MUST use the JSON guide.

### 8.6 Peer Exchange

```
GET /tltv/v1/peers
```

Returns channels this node knows about — both local and discovered from other peers. This is a gossip-based discovery mechanism (section 11).

**Response** (200):

```json
{
  "peers": [
    {
      "id": "TVxyz789...",
      "name": "Another Channel",
      "hints": ["relay1.example.com:8000", "192.168.1.50:8000"],
      "last_seen": "2026-03-14T12:00:00Z"
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `peers` | array | Yes | Known public channels. MAY be empty. |

Each peer entry:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Channel ID. |
| `name` | string | Yes | Display name from last verified metadata. |
| `hints` | array | Yes | Known `host:port` locations. MAY be empty. |
| `last_seen` | string | Yes | Last successful contact. ISO 8601 UTC. |

**Hint format.** Each hint in the `hints` array MUST be a string in `host:port` format. The `host` component MUST be one of: a DNS hostname, an IPv4 address, or a bracketed IPv6 address (e.g., `[::1]`). The `port` component MUST always be present (no default inference). Examples: `relay.example.com:8443`, `192.168.1.100:8000`, `[2001:db8::1]:443`.

A node MUST NOT include a peer unless it has successfully fetched and verified that peer's signed metadata (section 5.4) at least once. This prevents gossip pollution — a malicious node cannot inject fake channels into the network without also serving valid signed metadata for them, which requires the channel's private key.

A node SHOULD NOT include peers it has not successfully contacted in the past 7 days. Stale entries pollute the network.

A node SHOULD limit its peer list to at most 100 entries. Larger lists waste bandwidth and are a potential amplification vector.

Private channels MUST NOT appear in peer exchange responses.

### 8.7 Endpoint Summary

| Endpoint | Method | Auth | Signed Response | Content-Type |
|---|---|---|---|---|
| `/.well-known/tltv` | GET | No | No | `application/json` |
| `/tltv/v1/channels/{id}` | GET | Token* | Yes | `application/json` |
| `/tltv/v1/channels/{id}/stream.m3u8` | GET | Token* | No | `application/vnd.apple.mpegurl` |
| `/tltv/v1/channels/{id}/guide.json` | GET | Token* | Yes | `application/json` |
| `/tltv/v1/channels/{id}/guide.xml` | GET | Token* | No | `application/xml` |
| `/tltv/v1/peers` | GET | No | No | `application/json` |

\* Token required only for private channels (section 5.7).

All endpoints are read-only. No POST, PUT, or DELETE in V1.

### 8.8 HTTP Requirements

**Content type.** All JSON responses MUST use `Content-Type: application/json; charset=utf-8`.

**CORS.** Nodes MUST include CORS headers to allow browser-based viewers:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

Public channels are public. Restricting CORS defeats the purpose.

**TLS.** Nodes MUST use TLS (HTTPS) for all protocol endpoints when serving remote clients. HTTP without TLS is only permitted when client and node are on the same host (localhost / 127.0.0.1) or the same trusted local network during development and testing. Self-signed TLS certificates are acceptable when the operator explicitly trusts the node. Clients MUST NOT disable TLS certificate verification by default — explicit opt-in is required for self-signed certificates. In practice, nodes behind a domain will use Let's Encrypt. Nodes on raw IPs will use self-signed certs with explicit trust.

TLS provides transport security. Ed25519 provides channel identity. These are complementary — TLS protects unsigned data (node info, peer lists, HLS segments, redirects) that Ed25519 signatures do not cover. Relaxing TLS verification exposes all unsigned endpoints to MITM attacks.

**Referrer-Policy.** Nodes serving private channels MUST include `Referrer-Policy: no-referrer` on all responses to prevent token leakage via the Referer header. Nodes serving private channels MUST also include `Cache-Control: private, no-store` (see section 5.7 for the complete set of required privacy headers).

**HTTP caching.** Nodes SHOULD return appropriate `Cache-Control` and `ETag` headers. Recommended policies:

| Resource | Cache-Control | Rationale |
|---|---|---|
| Channel metadata | `max-age=60` | Changes rarely. |
| Guide | `max-age=300` | Changes at most daily. |
| HLS manifest | `max-age=1, no-cache` | Must track live edge. |
| HLS segments | `max-age=3600` | Immutable once written. |
| Node info | `max-age=60` | Changes rarely. |
| Peer list | `max-age=300` | Changes slowly. |

Relays SHOULD use HTTP conditional requests (`If-None-Match`, `If-Modified-Since`) when polling upstream to reduce bandwidth.

**Error responses.** All error responses MUST be JSON:

```json
{"error": "<error_code>"}
```

Standard error codes:

| HTTP Status | Error Code | Meaning |
|---|---|---|
| 400 | `invalid_request` | Malformed channel ID, invalid base58, wrong version prefix, or invalid query parameters. |
| 403 | `access_denied` | Private channel, missing or invalid token. |
| 404 | `channel_not_found` | Node does not serve this channel. |
| 422 | `invalid_document` | Document failed signature verification or has an invalid `seq`/`updated`. |
| 503 | `stream_unavailable` | Channel exists but stream is down. |
| 503 | `service_unavailable` | Node is overloaded or starting up. |

Nodes MAY include an optional `message` field with a human-readable explanation. Clients MUST NOT parse the `message` field programmatically.

---

## 9. Stream Transport

### 9.1 HLS

Video is delivered over HLS (HTTP Live Streaming). HLS is the required stream format in V1.

Requirements:

- The stream endpoint MAY return either a media playlist or a multivariant (master) playlist. Clients MUST handle both.
- Media playlists with MPEG-2 Transport Stream (`.ts`) segments are the baseline. All conforming viewers MUST support this profile.
- Multivariant playlists MAY offer multiple quality levels (adaptive bitrate), audio-only renditions, and subtitle tracks. Viewers SHOULD support adaptive bitrate selection. Viewers MAY support alternate audio and subtitle renditions.
- Served over HTTPS (section 8.8).
- No DRM, no encryption (V1 — public channels are unencrypted; private channels use token-based access control, not stream encryption).
- Segment duration SHOULD be 2 seconds.
- Manifests SHOULD contain at least 3 segments.
- Segment URIs SHOULD be relative paths (section 9.2).

Conforming viewers MUST support media playlists with `.ts` segments at minimum. Viewers SHOULD support multivariant playlists for adaptive bitrate. Viewers MAY support additional HLS features (fMP4, CMAF, etc.) but MUST NOT require them.

HLS is HTTP-based (cacheable, proxyable, CDN-friendly), widely supported (every browser via HLS.js, native on Safari/iOS), and trivial to relay (an HTTP cache is a relay).

V1 requires HLS. Future protocol versions may support additional transport formats through an additive `streams` field in channel metadata, allowing the `stream` field to remain for backwards compatibility while new formats are offered alongside.

### 9.2 Segment Serving

When a node serves the stream directly (200 response on the stream endpoint), it MUST also serve all segments referenced by the manifest. Segment URIs in the manifest SHOULD be relative paths. The node MUST serve those segments at paths relative to the manifest URL.

Example: if the manifest at `/tltv/v1/channels/{id}/stream.m3u8` contains:

```
#EXTINF:2.0,
seg-0042.ts
```

Then `seg-0042.ts` MUST be available at `/tltv/v1/channels/{id}/seg-0042.ts`.

### 9.3 Latency

V1 does not target low latency. Typical end-to-end latency is 4-8 seconds (2-second segments, player buffering 2-3 segments behind live edge). This is acceptable for 24/7 television.

### 9.4 Stream Availability

An always-on channel MUST always be producing output. If the channel has no scheduled content, it MUST play a fallback (slate, test pattern, filler). An always-on channel that produces no HLS segments is indistinguishable from a dead channel.

On-demand channels (section 5.11) are exempt from this requirement. They produce output only when a viewer is connected. Their liveness is established by serving metadata and guide data, not by continuous HLS output.

The protocol does not define uptime guarantees. Channels are infrastructure and are expected to run continuously, but outages happen. The protocol provides mechanisms for viewers and relays to detect and handle unavailability:

- **503 on stream endpoint**: The node explicitly reports the stream is down.
- **Stale HLS manifest**: The manifest's `EXT-X-MEDIA-SEQUENCE` stops incrementing. Viewers detect this via normal HLS playback behavior.
- **Stale metadata**: The `updated` timestamp hasn't changed in a long time. This suggests the channel may be abandoned (or simply stable — there is no required update frequency).

Viewers SHOULD handle stream interruptions gracefully: retry with backoff, display a clear "reconnecting" state, and resume automatically when the stream returns.

---

## 10. Relay Model

A relay is any node that serves a public channel it doesn't originate. For public channels, anyone can relay without permission.

### 10.1 How Relaying Works

A relay is an HTTP proxy/cache with signature verification:

1. **Signed metadata.** The relay fetches the channel metadata document from the origin (or another relay) and re-serves it verbatim. The signature proves it came from the channel. The relay cannot modify it.

2. **Signed guide.** Same as metadata — fetched and re-served. Signature proves authenticity.

3. **HLS segments.** The relay fetches `.m3u8` manifests and `.ts` segments from upstream and re-serves them at the protocol path (`/tltv/v1/channels/{id}/stream.m3u8` and segments). Standard HTTP caching semantics apply. The relay MUST serve segments directly — it MUST NOT redirect the viewer to the origin.

4. **Node info.** The relay lists the channel under `relaying` in its `/.well-known/tltv` response.

### 10.2 What a Relay Does NOT Do

- A relay does not have the channel's private key.
- A relay cannot sign metadata or guide updates.
- A relay cannot modify signed documents (signature verification would fail).
- Conforming relays MUST NOT relay private channels (section 5.7).
- Conforming relays MUST NOT relay on-demand channels (section 5.11). A relay's continuous segment polling would keep the channel permanently on, defeating the resource savings that on-demand mode provides.
- If the origin goes down, the relay serves cached segments until they expire (typically seconds). **Relays extend availability, not immortality.**

**Trust model.** Relays need not be trusted for signed metadata and guide authenticity — the signature proves these came from the channel. However, relays remain trusted for unsigned content: HLS manifests, HLS segments (video/audio), and redirect targets. In V1, there is no mechanism to verify stream content through untrusted relays. V2 stream content verification (section 16.3) will address this gap.

### 10.3 Freshness

Relays SHOULD poll upstream for updates at these intervals:

| Resource | Suggested Interval | Rationale |
|---|---|---|
| Channel metadata | 60 seconds | Must stay within the metadata cache lifetime (section 8.8) to support stale origin protection (section 5.8). |
| Guide | 15 minutes | Schedules change at most daily. |
| HLS manifest | Every segment duration (~2s) | Must track live edge. |
| Peer list | 30 minutes | Peer topology changes slowly. |

Relays MUST NOT poll metadata less frequently than the metadata cache lifetime (recommended 60 seconds). The stale origin protection in section 5.8 depends on clients learning about `origins` changes within the cache lifetime — a relay that polls metadata less frequently than the cache header advertises creates a window where relay-connected clients believe their metadata is fresh (within `max-age`) but the relay's upstream copy is stale. This defeats the stale origin protection guarantee. Regardless of the cache header, relays SHOULD NOT poll metadata more frequently than once per 10 seconds to limit upstream load from misconfigured or adversarial cache lifetimes.

When a relay receives metadata with the same `seq` as its cached copy, the relay MUST apply the same rule as clients (section 5.5): retain the cached copy unless the `signature` field is identical, in which case the document is accepted as equivalent.

For other resources, these are recommendations. More aggressive polling gives fresher data; less aggressive polling reduces upstream load. A relay MAY use HTTP conditional requests (`If-None-Match`, `If-Modified-Since`) to reduce bandwidth — metadata polls at 60-second intervals are lightweight when most return 304 Not Modified.

### 10.4 Relay Announcement

A relay advertises the channels it carries in two ways:

1. The `/.well-known/tltv` response lists relayed channels under `relaying`.
2. The `/tltv/v1/peers` response includes the channel with the relay's own address as a hint.

### 10.5 Origin Equivalence

From a viewer's perspective, a relay is indistinguishable from the origin for signed data. Both serve the same signed metadata, the same guide data, and the viewer verifies signatures against the channel ID from the URI. If the signature is valid, the metadata is authentic — regardless of which server served it.

For unsigned content (HLS segments), origin and relay may differ. A malicious relay could serve valid signed metadata but substitute the video stream (section 13.4). To mitigate this, viewers SHOULD prefer nodes listed in the channel's signed `origins` field (section 5.8) when available, and fall back to other nodes when origins are unreachable. The `origins` field is inside signed metadata and cannot be forged by relays, unlike the `channels`/`relaying` distinction in unsigned `/.well-known/tltv` responses.

### 10.6 Access Mode Transitions

When a relay fetches updated metadata for a previously public channel and the new metadata has `"access": "token"`, the relay MUST stop relaying that channel immediately and remove it from its `relaying` list. The relay cannot serve private channels (section 5.7). The relay's cached segments and metadata become stale and MUST NOT be served after the transition is detected.

Similarly, when a relay fetches updated metadata and the new metadata has `"on_demand": true`, the relay MUST stop relaying that channel immediately. On-demand channels MUST NOT be relayed (section 10.2) — a relay's continuous segment polling would keep the channel permanently on.

### 10.7 Why Open Relay

Public channels are public. The operator chose to broadcast to anyone. Preventing relay would require DRM or encryption, which contradicts the design principles. Open relay provides:

- **Resilience.** More relays = more availability.
- **Performance.** Viewers connect to the nearest relay.
- **Censorship resistance.** Taking down the origin doesn't immediately kill all relays (cached content continues briefly). Mirrors (section 10.8) provide true origin-level redundancy. Key delegation (V2 — section 16.2) will enable multiple independent signing nodes for the same channel identity.

### 10.8 Mirror Nodes

A mirror is an origin node that replicates the stream from another origin. Unlike a relay, a mirror holds the channel's private key and is listed in the signed `origins` field. From the protocol's perspective, a mirror IS an origin — the distinction is operational, not protocol-level.

**What makes a mirror different from a relay:**

| | Relay | Mirror |
|---|---|---|
| Has private key | No | Yes |
| Listed in `origins` | No | Yes |
| Can sign metadata | No | Yes |
| Can take over as primary | No | Yes |
| Clients trust for stream | TLS only | Origin authority |

**Mirror operation:**

1. **Replication.** The mirror fetches the HLS manifest and segments from the primary origin at the segment interval (~2 seconds). It caches them locally and serves them at the same protocol paths. Viewers connecting to the mirror get byte-identical segments to the primary.

2. **Promotion.** When the primary goes down, the mirror has recently cached segments. It starts its own stream generation (e.g., ffmpeg), continuing from the next HLS media sequence number after the last replicated segment. Viewers see no discontinuity — the manifest continues, segments continue.

3. **Demotion.** When the primary returns, the mirror stops generating and resumes replicating from the primary. This transition is also seamless — the mirror switches back to serving the primary's segments.

4. **Metadata.** Both primary and mirror hold the same key, but only one node MUST be the active metadata signer at any given time. The other origins fetch and re-serve the active signer's metadata verbatim. During promotion (when the primary is down), the mirror takes over metadata signing — this is the only time the signing role transfers. This single-active-signer rule ensures `seq` ordering remains unambiguous and avoids conflicting documents with equal `seq` values across origins. (Multiple independent signers require durable `seq` coordination — see key delegation, section 16.2.)

**Seamless failover.** The critical requirement for zero-downtime failover is HLS media sequence continuity. When a mirror promotes, it MUST continue the media sequence counter from where the primary left off. If the primary was at media sequence 500, the mirror's first self-generated segment MUST be 501. A media sequence reset would break every connected viewer's player.

**Setting up a mirror:**

1. Copy the channel's private key to the mirror node.
2. Configure the mirror to replicate from the primary origin.
3. Sign and publish new metadata with both nodes in `origins`.
4. The mirror is now live — viewers can connect to either node.

**Maintenance workflow:**

```
1. Primary is running, serving the channel
2. Spin up mirror, configure to replicate from primary
3. Update origins to include mirror, sign new metadata
4. Mirror is warm — replicating segments in real-time
5. Take primary down for maintenance
6. Mirror promotes — starts generating its own segments
7. Viewers fail over to mirror (section 12.1) — no interruption
8. Maintenance complete — bring primary back
9. Mirror demotes — resumes replicating from primary
10. Optionally remove mirror from origins, sign new metadata
```

**Mirror vs. multiple independent origins.** A mirror replicates segments from a primary to ensure byte-identical content and seamless failover. Multiple independent origins (both running their own ffmpeg on the same source) produce equivalent but not identical segments — different segment boundaries, different encoding artifacts. Switching between independent origins may cause a brief visual glitch. Mirrors avoid this by serving replicated segments during normal operation.

The mechanics of segment replication, sequence tracking, promotion, and demotion are implementation concerns — the protocol defines the origin model and failover behavior, not the replication machinery.

---

## 11. Discovery

No central discovery server. Channels find each other through peer exchange and direct links.

### 11.1 Direct Link

Someone gives you a `tltv://` URI with peer hints. You connect. This is how most viewers will find their first channel.

### 11.2 Peer Exchange

Every node exposes `GET /tltv/v1/peers`. A viewer that knows one node can discover others:

```
Viewer knows Node A
  -> GET /tltv/v1/peers from Node A
  -> Learns about channels B, C, D with connection hints
  -> GET /tltv/v1/peers from Node B
  -> Learns about channels E, F
```

The network grows organically. Each node's peer list is curated by its operator — nodes share what they want to share. This is a gossip-based protocol, similar to Bitcoin's `addr` message propagation and BitTorrent's PEX (Peer Exchange, BEP 11).

### 11.3 Bootstrap Peers

A viewer application MAY ship with a list of well-known nodes as first-contact points for peer exchange. Bootstrap peers are a convenience, not a dependency — a viewer that already knows a peer doesn't need them. This is the same model as Bitcoin's DNS seeds and BitTorrent's hardcoded bootstrap nodes.

**Curated directories.** The protocol does not prohibit centralized channel directories — it simply does not require them. Anyone can build a directory, search engine, or curated channel guide on top of the protocol using the same public endpoints (peer exchange, channel metadata, guide data). A directory is just a node that tracks many channels and presents them to viewers. A channel that aggregates other channels' streams (using `relay_from` in its guide entries to credit sources) is itself a form of live directory. All discovery can live in channels as much as possible — the broadcast IS the network.

### 11.4 Gossip Properties

Peer exchange creates a gossip network with these properties:

- **No flooding.** Nodes share their direct peers, not transitive peers. Discovery takes multiple hops.
- **Operator curated.** A node only lists peers its operator has added or that it has discovered and verified.
- **Stale hints are harmless.** A peer hint that no longer responds is silently skipped.
- **No global view.** No single node knows all channels. This is intentional.

### 11.5 Peer Validation

When a node discovers a new peer through peer exchange, it SHOULD:

1. Fetch `/.well-known/tltv` from the advertised hint.
2. Verify the response contains the expected channel ID.
3. Fetch and verify the channel's signed metadata.
4. Only then add the peer to its own peer list.

A node MUST NOT blindly propagate unverified peer entries. This prevents poisoning attacks where a malicious node advertises thousands of fake peers.

---

## 12. Client Conformance

### 12.1 Conforming Viewer — Required (MUST)

A conforming viewer MUST:

1. Parse `tltv://` URIs and extract channel ID, peer hints, and access token without applying host normalization (section 2.5).
2. Decode the channel ID to extract and verify the 2-byte version prefix (section 2.2).
3. Fetch `/.well-known/tltv` from peer hints during URI resolution (except for private channels — section 3.3).
4. Fetch channel metadata from `/tltv/v1/channels/{id}`.
5. Verify that the `id` field in the response matches the requested channel ID (identity binding — section 5.4).
6. Verify Ed25519 signatures on channel metadata before trusting any field.
7. Reject metadata with `seq` strictly lower than cached metadata. For equal `seq`, accept only if the `signature` field matches the cached copy (section 5.5). Reject metadata with `updated` or `seq` more than 1 hour in the future (section 5.5).
8. Play HLS streams from the path in the verified metadata (resolving relative to the node's origin).
9. Follow HTTP 302 redirects on the stream endpoint.
10. Display the channel `name` from verified metadata.
11. Handle stream unavailability gracefully (retry with backoff, display status to user).
12. Pass the `token` query parameter on all requests when present in the URI.
13. **Fail over between origins.** When the current node becomes unreachable (connection timeout, repeated 503, or HLS manifest stops updating), the viewer MUST try other origins from the `origins` list in cached metadata before falling back to relays or reporting failure. The viewer MUST attempt each origin in order, fetching and verifying metadata from each. The first origin that responds with a valid stream becomes the active node.
14. Refresh metadata at least once per cache lifetime (recommended 60 seconds) to stay current with `origins` changes (section 5.8).
15. Refuse to contact peer hints that resolve to loopback, link-local, private, or shared-address-space addresses unless explicitly configured for local-network use (section 3.1).
16. Reject signed documents with a `v` value the viewer does not support (section 14.3).
17. Ignore unknown fields in signed documents and preserve them when re-serving (section 5.6).

### 12.2 Conforming Viewer — Recommended (SHOULD)

A conforming viewer SHOULD:

1. Cache verified channel metadata and the node it was fetched from.
2. Cache peer lists from nodes it has contacted.
3. Fetch and display the channel guide (verifying signature and identity binding).
4. Try multiple nodes (from hints, cache, and peer exchange) before reporting failure.
5. Allow the user to inspect the channel ID.
6. Prefer nodes listed in the signed `origins` field (section 5.8) when available.
7. Follow migration documents (section 5.14) by fetching metadata from the new channel ID and alerting the viewer that the channel has migrated. Follow migration chains up to 5 hops.

### 12.3 Conforming Viewer — Optional (MAY)

A conforming viewer MAY:

1. Implement peer exchange (fetch `/tltv/v1/peers` to discover new channels).
2. Display XMLTV guide data.
3. Support multiple channels simultaneously (channel list, switching).
4. Cache HLS segments for brief offline resilience.
5. Implement channel search across known peers.
6. Ship with bootstrap peers.
7. Display `relay_from` guide entries as links to the source channel.

### 12.4 Conforming Node — Required

A node that originates a channel MUST:

1. Serve `/.well-known/tltv` listing its public channels.
2. Serve signed channel metadata at `/tltv/v1/channels/{id}`.
3. Serve an HLS stream (directly or via redirect) at `/tltv/v1/channels/{id}/stream.m3u8`.
4. Include CORS headers on all protocol endpoints (section 8.8).
5. Use TLS for all protocol endpoints serving remote clients (section 8.8).
6. Sign metadata with the channel's Ed25519 private key per section 5.3.
7. Produce continuous HLS output when the channel is on (section 9.4).
8. Enforce token authentication for private channels (section 5.7).
9. Return JSON error responses on all endpoints (section 8.8).

A node that relays a channel MUST:

1. Serve `/.well-known/tltv` listing the channel under `relaying`.
2. Serve the origin's signed metadata verbatim at `/tltv/v1/channels/{id}`.
3. Serve HLS segments directly (not redirect to origin) at `/tltv/v1/channels/{id}/stream.m3u8`.
4. Include CORS headers on all protocol endpoints.
5. Use TLS for all protocol endpoints serving remote clients.
6. Only relay public channels (not private channels).
7. Only relay always-on channels (not on-demand channels — section 10.2).
8. Poll upstream metadata at least as frequently as the metadata cache lifetime (section 10.3).
9. Stop relaying a channel immediately when updated metadata shows `"access": "token"` or `"on_demand": true` (section 10.6).
10. Preserve all fields (including unknown fields) when re-serving signed documents (section 5.6).
11. Return JSON error responses on all endpoints (section 8.8).

### 12.5 Minimum Viable Implementation

The simplest conforming channel is a static file server serving a **public, single-channel origin without peer exchange or private access**:

- A keypair.
- A signed metadata JSON file at the right path (including `seq`).
- An HLS stream at the right path.
- A `/.well-known/tltv` file.
- A TLS certificate.

No dynamic server required. No database. No peer exchange. Private channels require dynamic manifest generation (section 5.7) and cannot use this static model. The protocol is intentionally simple enough that a public channel can be a directory of files behind nginx.

---

## 13. Security Considerations

### 13.1 Metadata Replay

An attacker who has captured a valid signed metadata document can serve it from their own node. Since the signature is valid, a naive client would accept it.

**Mitigation.** Clients MUST track the `seq` value for each channel (section 5.5). A document with a `seq` strictly lower than the cached value MUST be rejected. For equal `seq`, the client accepts the document only if the `signature` field matches the cached copy (section 5.5). Clients MUST also reject documents with `updated` more than 1 hour in the future. These checks together prevent replay of old documents and injection of far-future-timestamped documents from a compromised key. Since metadata is public and the channel is public, replaying the *current* metadata is equivalent to relaying — which is permitted.

### 13.2 Peer List Poisoning

A malicious node could advertise a large number of fake peers in its `/tltv/v1/peers` response, wasting a client's time and bandwidth as it tries to contact non-existent nodes.

**Mitigation.** Clients and nodes SHOULD validate peers before adding them to their own peer list (section 11.5). Clients SHOULD limit the number of peers they cache (100 is a reasonable cap). Clients SHOULD use timeouts (2-5 seconds) when contacting peer hints.

### 13.3 Impersonation

Without the private key, an attacker cannot forge metadata or guide documents. They can, however, create a different channel with a similar human-readable name.

**Mitigation.** The channel ID is the identity, not the name. Clients SHOULD allow users to inspect the channel ID. Saved/bookmarked channels are identified by channel ID, not name. A name change in metadata does not create a new channel — the ID is immutable.

### 13.4 Stream Substitution

A malicious relay could serve valid signed metadata (proving the channel identity) but substitute the HLS stream with different video content — including adding bugs, lower thirds, watermarks, or replacing the stream entirely. The metadata signature covers the stream path, not the stream content.

**Mitigation (V1).** Channels SHOULD include the `origins` field in signed metadata (section 5.8), listing their authoritative nodes. Viewers SHOULD prefer nodes listed in `origins` over unlisted nodes. Since `origins` is inside signed metadata, a relay cannot forge it. This does not prevent stream substitution by a listed origin operator (who has the private key), but it prevents the specific attack where a random relay claims to be the origin. Note that the `channels`/`relaying` distinction in unsigned `/.well-known/tltv` is NOT a reliable signal — a malicious relay can claim origin status in its unsigned node info.

V2 will introduce stream content verification via per-segment hashing (section 16.3), which is the only way to guarantee stream integrity through untrusted relays.

**Practical note.** Stream substitution requires the attacker to operate a relay and convince viewers to connect to it. For small networks with direct links and origin-preferring clients, this is low probability.

### 13.5 Denial of Service

Protocol endpoints are unauthenticated (except private channels) and read-only. A node can be overwhelmed by request volume.

**Mitigation.** Standard HTTP rate limiting and DDoS protection. This is an operational concern, not a protocol concern — handled by the operator's infrastructure (reverse proxy, CDN, firewall).

### 13.6 TLS and Authenticity

TLS provides transport security. Ed25519 provides channel identity. These are complementary:

- **Signed data** (metadata, guide): Ed25519 signatures prove authenticity regardless of which node served it. TLS is not needed for authenticity here, but still provides transport confidentiality.
- **Unsigned data** (node info, peer lists, HLS manifests and segments, redirects): TLS is the only protection against MITM. Without TLS verification, an attacker can modify any unsigned response.

A node with a valid TLS certificate for `tv.example.com` is not inherently more trustworthy than a node on a raw IP with a self-signed cert — both are equally valid if they serve correctly signed metadata. However, clients MUST NOT disable TLS certificate verification by default. Self-signed certificates require explicit operator trust configuration.

### 13.7 Content Responsibility

The protocol does not inspect or filter content. Like HTTP, email, and BitTorrent, the protocol is a neutral transport.

**Relay operators are responsible for the channels they choose to relay.** A relay operator who discovers they are carrying illegal or objectionable content SHOULD stop relaying that channel. This is the same model as ISPs and hosting providers — the infrastructure operator is responsible for responding to legal notices.

**Blocklists.** Nodes SHOULD support channel blocklists (by channel ID) to enable operators to refuse relaying specific channels. Blocklists are voluntary and locally-enforced — there is no central blocklist authority. Operators MAY subscribe to community-maintained blocklists, similar to DNS-based blocklists for email spam.

**Traceability.** Every channel has a stable pseudonymous identity (channel ID). Every piece of metadata is signed. Persistent bad actors can be identified by their channel ID and blocked across the network through voluntary blocklist sharing. Creating a new channel ID is trivial (generate a new keypair), but building an audience from zero is not — social trust is the real Sybil resistance.

---

## 14. Versioning

### 14.1 Version Number

The protocol version is an integer, currently `1`. It appears in:

- `/.well-known/tltv` response (`"versions": [1]`).
- API path prefix (`/tltv/v1/...`).
- Channel metadata (`"v": 1`).
- Channel guide (`"v": 1`).

The channel ID version prefix (`0x1433` for V1 Ed25519 keys) identifies the key encoding format, not the protocol version (section 2.2). A protocol version bump does not change channel IDs.

### 14.2 Compatibility Rules

- **Patch changes** (bug fixes, clarifications): No version bump. Same endpoints, same behavior.
- **Additive changes** (new optional fields, new endpoints): No version bump. Receivers MUST ignore unknown fields in JSON documents. This is critical for forward compatibility.
- **Breaking changes** (removed fields, changed semantics, changed signing scheme): Version bump. Old and new endpoints coexist (`/tltv/v1/...` and `/tltv/v2/...`).

A node MAY support multiple versions simultaneously by listing them in the `versions` array: `"versions": [1, 2]`.

### 14.3 Version Negotiation

When a client encounters a node, it MUST check the `versions` array in `/.well-known/tltv`:

1. Select the highest version that both the client and node support.
2. Use the corresponding API path prefix (`/tltv/v1/...`, `/tltv/v2/...`, etc.).
3. If no mutually supported version exists, the client MUST treat the node as incompatible and try the next node. The client MUST NOT attempt to use an unsupported version.

Clients MUST reject signed documents with a `v` value they do not support. A V1 client that receives a document with `"v": 2` MUST discard it — the signing or field semantics may have changed.

### 14.4 TLTV Improvement Proposals (TIPs)

Changes to the protocol are proposed, discussed, and documented through **TIPs** (TLTV Improvement Proposals). Each TIP gets a number, a status, and a document.

**TIP lifecycle:**

| Status | Meaning |
|---|---|
| Draft | Proposal under discussion. Not yet accepted. |
| Accepted | Community consensus to include. Implementation may begin. |
| Final | Implemented and deployed. Part of the protocol. |
| Rejected | Considered and declined. Rationale documented. |
| Withdrawn | Author withdrew the proposal. |

**TIP format:**

```
TIP: <number>
Title: <short title>
Status: Draft | Accepted | Final | Rejected | Withdrawn
Created: <date>

## Abstract
<one paragraph summary>

## Motivation
<why this change is needed>

## Specification
<precise technical changes to the protocol>

## Backwards Compatibility
<impact on existing implementations>

## Reference Implementation
<link to implementation, if any>
```

Additive changes (new optional fields, new endpoints) are documented as TIPs but do not require a version bump. Breaking changes require a TIP AND a version bump.

This is modeled after Bitcoin's BIPs and BitTorrent's BEPs — both of which have successfully evolved their protocols over 15+ years using this pattern.

---

## 15. V1 Scope

| Feature | V1 | Notes |
|---|---|---|
| Ed25519 channel identity | Yes | Keypair generation, 2-byte version prefix (`TV`), base58 encoding. |
| `tltv://` URI scheme | Yes | With peer hints and access tokens. |
| Signed channel metadata | Yes | Name, description, icon, tags, language, timezone, stream path, guide path, access mode, on-demand, seq timestamp, status, signed origins. |
| Signed channel guide | Yes | JSON format with relay linking. XMLTV for IPTV compat. |
| HLS stream delivery | Yes | Media and multivariant playlists, `.ts` segments. |
| Public channels | Yes | Open access, open relay. |
| Private channels | Yes | Bearer token access with tokenized HLS segments, origin-only (not relayable). |
| On-demand channels | Yes | Stream starts on viewer request. Guide always available. Not relayable. |
| Open relay | Yes | Anyone can cache public, always-on channels. |
| Peer exchange | Yes | Gossip-based `GET /tltv/v1/peers`. |
| IPTV compatibility | Yes | XMLTV + HLS = standard IPTV. |
| Protocol versioning | Yes | Version 1, path-prefixed, TIP process. |
| Client conformance levels | Yes | MUST/SHOULD/MAY requirements. |
| Mirror nodes | Yes | Origin-level redundancy with seamless failover (section 10.8). |
| Client origin failover | Yes | Viewers try other origins from signed metadata when current node is unreachable. |
| Key migration | Yes | Signed migration document for key rotation (section 5.14). |
| Stream content signing | No | V2 — segment hashes for relay trust. |
| Key delegation | No | V2 — multi-node origins, censorship resistance. |
| Per-viewer authentication | No | V2 — viewer keypairs, fine-grained revocation. |
| Agent-to-agent messaging | No | V2 — showrunner collaboration. |
| DHT discovery | No | V2 — pubkey-to-location lookup when network is large enough. |
| Low-latency streaming | No | V2 — LL-HLS, WebRTC, SRT. |
| Tor/I2P transport | No | V2 — onion/garlic routing for censorship resistance. |

---

## 16. Future Directions (V2)

These are areas identified for future protocol versions. They are not commitments. Each will be proposed as a TIP when the time comes.

### 16.1 Advanced Mirroring

V1 supports basic mirror nodes (section 10.8): origins that replicate the live stream and can promote when the primary goes down. V2 mirroring extends this to full media library replication — a mirror that holds the complete archive of a channel's content and can independently reconstruct the schedule.

Advanced mirroring requires:
- A signed media manifest (list of files + hashes) published by the origin.
- A replication protocol for mirrors to sync the full library (not just live segments).
- Content-addressable segment storage for deduplication across mirrors.

This enables a channel to survive permanent origin loss — as long as one mirror has the full library and the private key, the channel lives on.

### 16.2 Key Delegation

The master private key authorizes sub-keys held by other nodes:

```json
{
  "id": "<channel-id>",
  "delegates": [
    {
      "pubkey": "<node-B-pubkey>",
      "capabilities": ["sign_metadata", "sign_guide", "serve_stream"],
      "expires": "2026-06-01T00:00:00Z"
    }
  ],
  "signature": "<signed by master key>"
}
```

Each delegate can independently sign metadata and serve streams. If one node is taken down, others continue. The master key can revoke a delegate. This is the multi-headed architecture needed for censorship resistance — removing one node does not kill the channel.

**Ordering considerations.** V1's single-writer model assumes one signer per document type. If multiple delegates can sign metadata independently, they must coordinate to avoid `seq` collisions — since `seq` is a Unix epoch timestamp, two delegates signing at the same second would produce the same value. Possible approaches: a shared atomic counter, delegate-specific sub-second offsets, or a leader-election model where only one delegate signs at a time. The exact mechanism is deferred to the V2 delegation specification.

### 16.3 Stream Content Verification

Signing or hashing HLS segments to prevent stream substitution attacks (section 13.4). The origin publishes a signed manifest of segment hashes. Viewers verify each segment. This is expensive (per-segment overhead) but is the only way to guarantee stream integrity through untrusted relays.

### 16.4 Per-Viewer Authentication

Access control via signed allow-lists with viewer keypairs. Viewers prove identity via challenge-response. Per-viewer revocation without rotating the channel token. Capability tokens for bearer-link sharing.

### 16.5 Agent-to-Agent Communication

Showrunner agents on different channels communicate for creative collaboration. Read-only awareness (fetching other channels' guides) works in V1. Structured negotiation (simulcasts, cross-promotion) requires a dedicated endpoint and message format.

### 16.6 Enhanced Discovery

- **DHT.** Distributed hash table (Kademlia) mapping channel IDs to connection hints. Eliminates the need for peer hints in URIs. Only justified when the network grows to hundreds or thousands of channels — peer exchange gossip is sufficient for smaller networks. BitTorrent launched in 2001 and added DHT in 2005.
- **mDNS.** Find TLTV nodes on the local network.
- **Tor/I2P.** Onion and garlic routing for transport-level censorship resistance. Channel hints would use `.onion` or I2P addresses instead of IP/DNS.

### 16.7 Key Migration — Advanced

V1 provides basic key migration through signed migration documents (section 5.14). This covers planned key rotation: a channel declares "I've moved to a new identity" with a cryptographic proof, and clients follow the pointer. V1 migration is honest about its limits — it does not reliably handle key compromise (an attacker with the key can sign a competing migration) or key loss (cannot sign without the key).

Future versions may extend migration with:

- **Counter-signed migration.** The new channel signs a document accepting the migration, providing bidirectional proof rather than V1's one-way pointer. This would let clients distinguish a legitimate migration from an attacker's competing migration — only the legitimate operator controls both keys.
- **Partial migration.** Migrating specific capabilities (e.g., guide signing) to a new key while retaining the original identity — overlaps with key delegation (section 16.2).
- **Migration revocation.** Allowing the old key to revoke a migration within a time window. V1 migration is permanent and irreversible by design.
- **Automated migration discovery.** A protocol-level mechanism for nodes to proactively notify connected viewers about channel migrations, rather than relying on viewers to poll the metadata endpoint.

### 16.8 Signed Relay List

A channel currently has no protocol-level way to declare "you can find me at these nodes." The `origins` field in V1 metadata partially addresses this for origin nodes. A more complete signed relay list would let the channel declare both origins and authorized relays:

```json
{
  "id": "<channel-id>",
  "origins": ["origin1.example.com:443"],
  "relays": ["relay1.example.com:8443", "relay2.example.com:443"],
  "updated": "2026-03-14T12:00:00Z",
  "signature": "<signed by channel key>"
}
```

This would be especially valuable when the origin changes IP/domain, giving viewers a signed update mechanism for connection hints. Could be delivered as a field in metadata or as a separate signed document.

### 16.9 Additional Stream Formats

The `stream` field in metadata could be supplemented with a `streams` array offering multiple formats:

```json
{
  "stream": "/tltv/v1/channels/.../stream.m3u8",
  "streams": [
    {"format": "hls", "url": "/tltv/v1/channels/.../stream.m3u8"},
    {"format": "ll-hls", "url": "/tltv/v1/channels/.../ll-stream.m3u8"},
    {"format": "srt", "url": "srt://..."}
  ]
}
```

The V1 `stream` field stays for backwards compatibility. New formats are additive.

---

## Appendix A: Why Not an Event DAG

Matrix uses an event DAG because multiple homeservers can modify room state concurrently. The DAG plus state resolution algorithm determines which write wins.

TLTV is single-writer. All channel state is signed by one key. Concurrent conflicting writes cannot happen in normal operation because only one key can sign. (Mirror nodes share the same key but are operationally constrained to single-active-signer — see section 10.8. The equal-seq rule in section 5.5 provides safety if this constraint is briefly violated during promotion.)

| State | Writer | Conflict possible? |
|---|---|---|
| Channel metadata | Channel private key | No — single writer. |
| Guide/EPG | Channel private key | No — single writer. |
| Allow-list (V2) | Channel private key | No — single writer. |
| Peer list | Each node independently | No — each node has its own list. |

Every piece of federated state is either single-writer (signed by one key) or node-local (not shared). There is no shared mutable state that multiple parties write to concurrently.

What we use instead: signed documents with epoch timestamps as ordering. The channel signs a document with a `seq` value set to the current Unix epoch time. Relays cache it. When the channel updates, it signs a new document with a higher `seq`. Highest-seq-wins, and there's only one writer.

This eliminates: Merkle hashing, topological sorting, state resolution algorithms, conflict handling, event storage, and compaction. If TLTV ever introduces key delegation (section 16.2), delegated keys are still single-writer per operation — the master key delegates, sub-keys sign independently. No DAG needed.

## Appendix B: Relationship to Multi-Channel

A single TLTV instance can serve multiple channels. Each channel has its own keypair, metadata, stream, and guide. The protocol makes no distinction between a single-channel server and a multi-channel instance — both implement the same endpoints.

```
# Single-channel node
GET /.well-known/tltv -> {"channels": [{"id": "TVMkVH..."}]}

# Multi-channel node
GET /.well-known/tltv -> {"channels": [{"id": "TVMkVH..."}, {"id": "TVxyz7..."}]}
```

The internal architecture (shared containers, per-channel contexts) is an implementation detail invisible to the protocol.

## Appendix C: Test Vectors

These test vectors use the Ed25519 test keypair from [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032#section-7.1) (section 7.1, test vector 1). This keypair is published in an IETF standard and used by every Ed25519 implementation for testing.

**WARNING:** The private key below is public knowledge. The channel ID `TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3` MUST NOT be used for production channels — anyone who has read this spec or RFC 8032 can sign valid metadata for it. Implementations MAY reject this channel ID with a warning (e.g., "This is a well-known test key and cannot be used in production").

### C.1 Channel Identity

```
Private key (seed): 9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
Public key:         d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
Version prefix:     1433
Payload (prefix || pubkey):
  1433d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
Channel ID:         TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3
```

Verification: decode `TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3` from base58, confirm the result is 34 bytes, confirm bytes 0-1 are `0x1433`, confirm bytes 2-33 match the public key above.

### C.2 Metadata Signing

Document fields (before signing):

```json
{
  "v": 1,
  "seq": 1742000000,
  "id": "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3",
  "name": "Test Channel",
  "description": "A test channel for protocol verification",
  "stream": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/stream.m3u8",
  "guide": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/guide.json",
  "access": "public",
  "updated": "2026-03-14T12:00:00Z"
}
```

Canonical JSON (382 bytes):

```
{"access":"public","description":"A test channel for protocol verification","guide":"/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/guide.json","id":"TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3","name":"Test Channel","seq":1742000000,"stream":"/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/stream.m3u8","updated":"2026-03-14T12:00:00Z","v":1}
```

```
Signature (hex):    49064ea6d6a8dce519874e51c1c4d58fdf18bc4b267dd995cfea0320
                    0fdf3f94a1fcb6fb0f76998f7af941b689da95cbf5738caaa162ba6f
                    32a844000512ac0a
Signature (base58): 2TgRpS4h1UREKn3rRGk3cMRQ9fXQZ2TYX76oWCkHnDbHmUm2hTNAcXy8nSphcFVwareooGM2hqwvWgoGigaCNaob
```

### C.3 Complete Signed Document

```json
{
  "v": 1,
  "seq": 1742000000,
  "id": "TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3",
  "name": "Test Channel",
  "description": "A test channel for protocol verification",
  "stream": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/stream.m3u8",
  "guide": "/tltv/v1/channels/TVMkVHiXF9W1NgM9KLgs7tcBMvC1YtF4Daj4yfTrJercs3/guide.json",
  "access": "public",
  "updated": "2026-03-14T12:00:00Z",
  "signature": "2TgRpS4h1UREKn3rRGk3cMRQ9fXQZ2TYX76oWCkHnDbHmUm2hTNAcXy8nSphcFVwareooGM2hqwvWgoGigaCNaob"
}
```

Verification: remove the `signature` field, canonicalize to JSON (keys sorted, no whitespace), verify the Ed25519 signature against the canonical bytes using the public key extracted from the `id` field.

