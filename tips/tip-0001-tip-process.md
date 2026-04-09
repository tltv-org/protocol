---
tip: 1
title: The TIP Process
status: Draft
type: Process
author: Philo Farnsworth <farnsworth27@protonmail.com>
created: 2026-04-09
---

# TIP-1: The TIP Process

## Abstract

This document defines the process for proposing, discussing, and adopting changes to the tltv protocol. It replaces the skeletal format in PROTOCOL.md Section 14.4 with a complete specification of the TIP lifecycle, format, and governance. TIP stands for **tltv Improvement Proposal**.

## Motivation

The tltv protocol shipped V1.0 on March 16, 2026 with a brief outline of the TIP process (Section 14.4). That outline established the concept — numbered proposals with lifecycle states — but left the mechanics undefined: where proposals live, how they're formatted, what sections are required, how numbering works, and how decisions are made.

As the protocol matures and other implementors appear, a well-defined process prevents ambiguity about what is part of the protocol and what isn't. Every successful long-lived protocol (BitTorrent, Matrix, Python) has a formal proposal process. The tltv protocol should too.

This TIP is modeled after BitTorrent's BEPs, Python's PEPs, Matrix's MSCs, and Rust's RFCs — taking what works and leaving what doesn't.

## Specification

### 1. What is a TIP?

A TIP is a design document that proposes a change to the tltv protocol. Each TIP is a standalone Markdown file with a structured preamble and required sections. TIPs are the mechanism through which the protocol evolves.

A TIP may propose:

- New optional fields in signed documents (additive extension).
- New optional endpoints (additive extension).
- New behaviors for existing endpoints (clarification or extension).
- Changes to the TIP process itself (process change).
- Breaking changes that require a protocol version bump.

A TIP does NOT cover:

- Implementation details of specific software (cathode, tltv-cli, etc.).
- Content creation, scheduling, or management APIs.
- Operational guidance (how to run a relay, how to deploy).

**Not every change needs a TIP.** Typo fixes, editorial clarifications, broken examples, and other non-behavioral improvements to PROTOCOL.md can be committed directly without a TIP. A TIP is needed when a change affects what an implementation must do — new fields, new endpoints, new behaviors, or changed semantics.

### 2. TIP Types

| Type | Purpose |
|---|---|
| **Standards Track** | Changes to the protocol: new fields, new endpoints, new behaviors, version bumps. |
| **Process** | Changes to the TIP process itself, governance, or project-level decisions. |

### 3. TIP Numbering

TIP numbers are sequential integers starting at 1. The author proposes the next available number. If two TIPs collide, the one merged first keeps the number.

Numbers are zero-padded to 4 digits in filenames (`tip-0001`) but written without padding in prose ("TIP-1").

### 4. File Naming and Location

TIPs live in the `tips/` directory of the protocol repository.

**Filename format:** `tip-NNNN-short-title.md`

- `NNNN` is the zero-padded TIP number.
- `short-title` is a lowercase, hyphen-separated slug (max 50 characters).
- Auxiliary files (diagrams, examples) go in a `tip-NNNN/` subdirectory.

A template is provided at `tips/tip-template.md` — copy it to get started.

Examples:

```
tips/tip-template.md                    ← copy this
tips/tip-0001-tip-process.md
tips/tip-0002-relay-delay.md
tips/tip-0002/delay-sequence.png
tips/tip-0003-viewer-hint.md
```

### 5. TIP Format

Every TIP is a Markdown document with a YAML front matter preamble followed by the required sections.

#### 5.1 Preamble

The preamble is YAML front matter delimited by `---`:

```yaml
---
tip: <number>
title: <short title>
status: Draft | Accepted | Final | Withdrawn | Rejected | Superseded
type: Standards Track | Process
author: <name> <<email>> [, <name> <<email>>]*
created: <YYYY-MM-DD>
requires: <TIP number(s)>          # optional
supersedes: <TIP number(s)>        # optional
superseded-by: <TIP number(s)>     # optional
---
```

**Required fields:** `tip`, `title`, `status`, `type`, `author`, `created`.

**Optional fields:** `requires` (TIPs this depends on), `supersedes` (TIPs this replaces), `superseded-by` (TIP that replaced this one, added when superseded).

The `author` field uses the format `Name <email>`. Multiple authors are comma-separated.

#### 5.2 Required Sections

Every TIP MUST include the following sections, in order:

| Section | Contents |
|---|---|
| **Abstract** | One paragraph. What this TIP does and why, in plain language. A reader should know whether this TIP is relevant to them after reading the abstract. |
| **Motivation** | The problem this TIP solves. What's broken, missing, or inadequate in the current protocol? Include concrete use cases. |
| **Specification** | The precise technical changes to the protocol. Written as spec text — clear enough that an independent implementor can build from this section alone. Use RFC 2119 keywords (MUST, SHOULD, MAY) consistently. |
| **Backwards Compatibility** | Impact on existing V1.0 implementations. For additive changes: confirm that unknown fields are ignored per Section 5.6 of the protocol. For breaking changes: describe the migration path and version bump. |
| **Security Considerations** | Security implications of this TIP. Threat model changes, new attack surfaces, privacy impact. This section is mandatory even if the answer is "this TIP introduces no new security considerations" — that itself must be argued. |
| **Rejected Alternatives** | Other approaches that were considered and why they were not chosen. This prevents relitigating settled design decisions. |
| **Reference Implementation** | Link to a working implementation, or "None yet" for Draft TIPs. An implementation MUST exist before a TIP can reach Final status. |

#### 5.3 Optional Sections

Authors MAY include additional sections where useful:

- **Test Vectors** — for TIPs that change signing, encoding, or validation.
- **Examples** — JSON examples, workflow diagrams, request/response pairs.
- **Changelog** — for TIPs that evolve significantly during the Draft phase.

### 6. TIP Lifecycle

```
Draft ──> Accepted ──> Final
  │          │
  │          └──> Superseded
  │
  ├──> Withdrawn
  ├──> Rejected
  └──> Superseded
```

| Status | Meaning | Who Decides |
|---|---|---|
| **Draft** | Proposal exists and is open for discussion. The author considers it ready for review. | Author submits. |
| **Accepted** | The proposal has consensus. Implementation may begin (or continue). The technical design is settled. | Maintainers. |
| **Final** | Implemented, deployed, and part of the protocol. Permanent. | Maintainers, after verifying a reference implementation exists. |
| **Withdrawn** | The author has withdrawn the proposal. The TIP number is reserved and cannot be reused. | Author. |
| **Rejected** | The proposal was considered and declined. The rationale MUST be documented in the TIP or in a linked discussion. | Maintainers. |
| **Superseded** | Replaced by a newer TIP. The `superseded-by` field is added to the preamble. | Maintainers, when the replacement TIP reaches Accepted. |

**State transition rules:**

- A TIP enters the repository as **Draft**.
- Only the author may move a TIP to **Withdrawn**.
- **Draft to Accepted** requires maintainer consensus that the design is sound and the protocol should include this change.
- **Accepted to Final** requires a reference implementation that passes any applicable test vectors.
- **Draft TIPs may be freely revised** by their author. This is the working phase — expect iteration.
- **Accepted TIPs may only be revised** for non-substantive changes (typos, wording clarity, updated links). Any change to the technical design requires reverting to Draft or writing a new TIP.
- **Final is permanent.** A Final TIP cannot be modified except for errata (typo fixes, clarifications that don't change behavior). Substantive changes require a new TIP that supersedes it.
- A TIP number is never reused, regardless of status.

#### 6.1 Versioning Rules

These rules are inherited from PROTOCOL.md Section 14.2 and restated here for completeness:

- **Additive changes** (new optional fields, new optional endpoints) are documented as TIPs but do NOT require a protocol version bump. Existing implementations ignore unknown fields per Section 5.6.
- **Breaking changes** (removed fields, changed semantics, changed signing) require a TIP AND a protocol version bump. The new version's endpoints coexist with old ones (`/tltv/v1/`, `/tltv/v2/`).

### 7. Relationship to the Protocol Spec

TIPs are proposals. PROTOCOL.md is the single source of truth. A new implementor should be able to read PROTOCOL.md alone and build a conformant implementation — they should never need to read individual TIPs to understand the current protocol.

This means TIPs feed the spec, not replace it.

#### 7.1 The Fold-In Rule

When a Standards Track TIP reaches **Final** status, its specification text MUST be incorporated into PROTOCOL.md. The TIP remains in the `tips/` directory as the permanent record of motivation, alternatives considered, and design rationale — but the spec is where implementors go.

The fold-in process:

1. The TIP's Specification section is adapted into spec prose and added to the appropriate section of PROTOCOL.md.
2. A changelog entry is added to PROTOCOL.md referencing the TIP.
3. The spec's minor version is bumped.
4. The TIP's status is updated to Final (if not already).

Process TIPs (like this one) do not get folded into PROTOCOL.md. They are self-contained documents that govern the project.

#### 7.2 Spec Versioning

PROTOCOL.md uses `major.minor` versioning:

```
V1.0  — March 16, 2026 (initial release)
V1.1  — first batch of Final TIPs incorporated
V1.2  — more TIPs incorporated
...
V2.0  — major version bump (breaking changes, clean consolidation)
```

**Minor version bumps** occur when Final TIPs are folded into the spec. Multiple TIPs MAY be batched into a single minor release. The minor version is a monotonic counter with no semantic meaning — V1.3 is not "more breaking" than V1.2.

**Major version bumps** occur when breaking changes are introduced (new path prefix, changed signing semantics, removed fields). A major bump consolidates the previous version's spec and all its TIPs into a clean document. For example, V2.0 would be a fresh PROTOCOL.md incorporating V1.0 plus every V1.x TIP. The V1 spec and its TIPs become historical archive.

**Patch versions** (V1.1.1) are reserved for errata — typo fixes and clarifications that don't change protocol behavior. They do not require a TIP.

#### 7.3 Changelog

PROTOCOL.md MUST include a changelog section tracking every version:

```markdown
## Changelog

### V1.1 — YYYY-MM-DD
- Added `delay` field to well-known relay entries (TIP-2).
- Added `viewer_hint` field to channel metadata (TIP-3).

### V1.0 — 2026-03-16
- Initial release.
```

Each entry references the TIP that introduced the change. This is the bridge between the spec (what) and the TIPs (why).

#### 7.4 Inline Annotations

When spec text is added or changed by a TIP, the change SHOULD be annotated inline:

```markdown
The `relaying` array entries MAY include a `delay` field (integer,
seconds) indicating the relay serves the stream with a time offset.
*[Added in V1.1 (TIP-2)]*
```

These annotations help implementors who are upgrading from an earlier version identify what changed. They are informational and do not affect protocol semantics.

#### 7.5 What Implementors Read

| Audience | Reads |
|---|---|
| New implementor | PROTOCOL.md (latest version). Everything they need is there. |
| Upgrading implementor | The changelog and inline annotations to find what changed since their last version. |
| Protocol designer | The TIP for motivation, rejected alternatives, and security analysis. |
| Historian | The full TIP archive in `tips/` for the complete decision record. |

### 8. Governance

The tltv protocol is currently maintained by its original author. "Maintainers" in this document refers to whoever holds commit access to the protocol repository.

As the project grows, this section should be updated (via a new Process TIP) to define:

- How maintainers are added or removed.
- Whether a formal review period (FCP) is needed before acceptance.
- How disputes are resolved when maintainers disagree.

Until then, the process is intentionally lightweight: write the TIP, discuss it, build consensus, ship it.

### 9. TIP Index

The protocol repository SHOULD maintain an index of all TIPs in `tips/README.md` with columns for number, title, type, and status.

## Backwards Compatibility

This TIP expands on PROTOCOL.md Section 14.4. It does not contradict it:

- The five lifecycle states from Section 14.4 (Draft, Accepted, Final, Rejected, Withdrawn) are preserved. This TIP adds **Superseded** as a sixth state.
- The format from Section 14.4 (TIP number, title, status, created, five sections) is preserved and extended. This TIP adds a YAML preamble, three new required sections (Security Considerations, Rejected Alternatives, a structured Abstract), and optional sections.
- The versioning rules from Section 14.2 (additive = no bump, breaking = bump) are unchanged.
- The spec versioning scheme (Section 7.2) introduces `major.minor` numbering for PROTOCOL.md. The existing V1.0 header becomes the first entry in this scheme. No changes to existing implementations are required.

Section 14.4 of the protocol spec should be updated to reference this TIP for the full process definition.

## Security Considerations

This TIP defines a process, not a protocol change. It introduces no new attack surfaces.

However, the TIP process itself has a security-relevant property: it requires a **Security Considerations** section in every TIP. This is a deliberate design choice. The absence of security analysis in protocol proposals has historically led to deployed features with unexamined attack surfaces. Making the section mandatory — even when the answer is "no new considerations" — forces authors to think adversarially about their proposals.

## Rejected Alternatives

### PR-based numbering (Rust RFCs, Matrix MSCs)

Using the pull request number as the TIP number eliminates the need for manual numbering. However, it couples proposal identity to a specific hosting platform (GitHub, Forgejo) and produces arbitrary numbers that don't reflect chronological order of intent. Sequential numbering is simpler for a small project and produces cleaner references ("TIP-2" vs "TIP-47").

### MediaWiki format

Some older proposal systems use MediaWiki markup. It's harder to render locally, has worse tooling support, and creates an unnecessary barrier to contribution. Markdown is the standard for modern technical writing.

### reStructuredText (BitTorrent BEPs, Python PEPs)

RST is powerful but has a steeper learning curve than Markdown. The additional features (directives, roles, domain-specific markup) are not needed for protocol proposals.

### No preamble / lightweight preamble (Matrix MSCs)

Matrix MSCs have no formal preamble — status is tracked entirely via GitHub labels. This works for a project with dedicated tooling but makes the documents less self-contained. A TIP should be understandable without access to the hosting platform's metadata.

### Complex type system

Some proposal systems use three or more types with layer sub-classifications (Consensus, Peer Services, API/RPC, Applications). This level of taxonomy is premature for a protocol with one version and a handful of implementors. Two types (Standards Track, Process) cover our needs. A future Process TIP can add categories if the corpus grows large enough to need them.

### Formal FCP timer

Rust (10 days) and Matrix (5 days) both use a formal Final Comment Period before acceptance. This makes sense for projects with many stakeholders where "silence is consent" needs a deadline. The tltv project is not there yet. Adding an FCP timer now would be governance theater. This TIP defines a hook for it in the Governance section — a future Process TIP can add it when the community warrants it.

## Reference Implementation

This document is the reference implementation. The `tips/` directory structure and this file demonstrate the format.

## Copyright

This TIP is licensed under the [MIT License](../LICENSE), consistent with the tltv protocol specification.
