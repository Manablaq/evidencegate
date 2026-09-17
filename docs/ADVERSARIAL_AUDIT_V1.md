# EvidenceGate v1 adversarial audit — Stage 3

Status: **historical pre-deployment implementation audit.** This document preserves the findings and fixes from that phase; current canonical deployment and finality evidence is documented separately in `BRADBURY_LIVE_PROOF_V1.md`.

## Findings fixed

### EG-AUD-001 — duplicate authority-address masquerading

The first implementation required distinct authority IDs and origins but did not prohibit two authority IDs from sharing one signing address. That could let one key occupy multiple authority slots.

Fix: a sealed policy now requires each configured authority ID to use an address not already bound in that policy. `DUPLICATE_AUTHORITY_ADDRESS` fails closed.

Residual boundary: distinct addresses/origins are mechanical independence constraints. They cannot prove two real-world organizations are socially or economically independent. Policy authors must choose trustworthy authorities.

### EG-AUD-002 — HTTP status not checked

The first implementation verified exact response-body SHA-256 but did not require a successful HTTP status.

Fix: only HTTP `200` is eligible for evidence evaluation. Any other status becomes `REPAIR_REQUIRED` with `SOURCE_HTTP_STATUS_NOT_OK`; no attestation is created.

### EG-AUD-003 — deterministic post-consensus repair-code whitelist

The evaluator already emitted a small bounded repair-code set and validators compared the code exactly. The deterministic post-consensus boundary previously required only a non-empty repair code.

Fix: the boundary now rejects any code outside the explicit repair-code whitelist using `CONSENSUS_REPAIR_CODE_NOT_ALLOWED`.

### EG-AUD-004 — GenLayer Response field mismatch

Severity: High for availability/correct classification.

The Stage 3R3 Direct Mode run proved that the pinned GenLayer `Response`
object exposes HTTP status as `.status`, not Requests-style
`.status_code`. The earlier Stage 3R3 change correctly made the GET
method explicit with `gl.nondet.web.request(..., method="GET")`, but it
still read the wrong response attribute, causing every web-backed path to
fail before evidence evaluation.

Fix:

- read `response.status`;
- forbid `response.status_code` in source guards;
- retain explicit `web.request(..., method="GET")`;
- preserve non-200 -> `REPAIR_REQUIRED` semantics; and
- verify success, non-200, missing-fetch, digest-mismatch, oversized-body,
  exact-outcome, and validator paths in Direct Mode.

### EG-AUD-005 — untrusted request question was interpolated as raw prompt text

Severity: Medium.

The request question is user-controlled and was interpolated directly
into the evaluator prompt. Exact validator agreement does not protect
against a prompt-injection instruction that all validators follow.

Fix:

- JSON-quote the request question;
- label the question and evidence as untrusted data, never instructions;
- state that only sealed policy criteria govern evaluation;
- preserve exact bounded output validation and allowed-outcome checks.

This reduces prompt-injection risk but does not claim that LLM prompt
injection can be eliminated absolutely.

### EG-AUD-006 — raw expiry overstated policy-valid lifetime

Severity: High for freshness semantics.

The initial `valid_until` calculation used only `expires_at`. That could
allow a request deadline or historical attestation to outlive the point
where `max_evidence_age_seconds` or
`min_remaining_validity_seconds` would already fail.

Fix: derive one exclusive effective-validity horizon from all sealed
freshness/validity constraints and require request/repair deadlines to
remain strictly before it.

### EG-AUD-007 — historical attestation could look current after evidence supersession

Severity: High for reusable downstream safety.

A resolved attestation is immutable, but an approved authority may later
register a newer version of a bound stable evidence lineage. Without an
explicit currentness check, a downstream integration could reuse the old
attestation as though the superseded evidence were still current.

Fix: add `is_attestation_current(request_id)`. It rechecks the exact
request bundle against latest lineage versions, policy freshness, the
stored policy fingerprint, evidence-bundle digest, outcome, and effective
validity horizon. Historical attestations remain queryable but are not
implicitly current forever.

### EG-AUD-008 — specification contradicted authority-authenticated registration

Severity: Medium documentation/reviewer risk.

The implementation requires the exact policy-bound authority address to
register evidence, while the original specification still said
registration "may be permissionless."

Fix: align the specification with the implemented authority-authenticated
provenance model.

### EG-AUD-009 — LLM result accepted irrelevant extra keys

Severity: Low / defense in depth.

Only four decision-bearing fields are part of consensus. The evaluator
now rejects any LLM JSON object that is not exactly those four fields,
reducing ambiguity and keeping the consensus surface minimal.

### EG-AUD-010 — authority origins allowed literal IPv4 hosts

Severity: Medium configuration hardening.

The canonical-origin parser accepted dotted numeric IPv4 hosts. v1 now
requires a canonical HTTPS DNS hostname with valid label boundaries and
rejects literal numeric IP origins. DNS resolution remains a runtime
boundary and is documented as such.

## Direct-mode coverage

The Stage 3 suite covers policy immutability and authorization, sorted authority/outcome sets, unique authority addresses, origin diversity, policy bounds, authority-signed evidence registration, source-origin binding, evidence lineage/versioning, freshness/expiry boundaries, request bundle and deadline bounds, exact YES and NO outcomes, validator agreement and disagreement, digest mismatch, non-200 HTTP, conflicting/insufficient evidence, repair with newer evidence, requester-only repair, changed-bundle enforcement, expiry, and terminal resolved state.

## Remaining trust boundaries

Direct Mode is in-memory verification and, by itself, does not prove live multi-validator finality or Bradbury network behavior. The later supported-runtime and Bradbury proofs are separate verification layers.

EvidenceGate cannot make a malicious approved authority truthful. The policy trust choice is explicit and sealed.

LLM classification may fail to converge. EvidenceGate must prefer disagreement/rotation or repair over weakening exact consequential agreement.

This historical audit does not itself make a deployment or Bradbury-finality claim; the later canonical live proof is the authoritative record for those claims.

## Stage 5 compact-source hardening

### EG-AUD-011 — partially configured policy state removed

The Bradbury-size redesign replaces the multi-transaction policy-building sequence with one atomic `create_policy` call carrying the complete authority IDs, unique bound addresses, exact origins, outcomes, and numeric policy bounds. A failed creation stores no partial policy configuration.

### EG-AUD-012 — URL fragments and aggregate evidence size

Source URLs now reject fragments. In addition to the 65,536-byte per-source bound, the evaluator caps the aggregate fetched source bundle at 131,072 bytes and returns `SOURCE_BUNDLE_TOO_LARGE` as a repairable failure.

### Historical predecessor certification evidence

The certification evidence in this subsection is bound to the predecessor source and must not be presented as an audit of the current fixed candidate.

- Historical predecessor compact contract SHA-256: `776dcd2ce4b0e6844d184831efe4b3e2b9b46eab2116d975bcf2f670b57562e5`.
- Historical predecessor source size: 16,113 bytes.
- Full predecessor Direct Mode regression: 28/28 tests passed twice.
- At the time of this audit, the write-blocked Bradbury deployment estimate was 13,633,575 gas for 16,356 calldata bytes and no deployment transaction was submitted by that audit step.
- The canonical fixed source SHA-256 is `6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1`.
- R22-R10 subsequently completed isolated five-validator supported-runtime finality validation against the fixed source after the nondeterministic-storage hardening.
- Reviewer-style audit R22-R20R subsequently passed against the committed fixed source with no implementation defect found. This document retains the predecessor audit evidence above as historical evidence rather than relabeling it as evidence for the fixed source.
