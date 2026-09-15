# EvidenceGate v1 implementation notes

This document describes the first canonical implementation candidate for the frozen v1 specification.

## Authority identity

A policy authority is not only a label or URL. Atomic `create_policy` binds all three of:

- canonical authority ID;
- exact GenLayer/EVM-style authority address; and
- exact canonical HTTPS publisher origin.

Only that bound authority address may register or advance evidence for its authority ID. A policy cannot bind two authority IDs to the same authority address.

This closes the evidence-lineage spoofing problem that would exist if an arbitrary caller could publish a higher evidence version under a trusted authority label.

## Evidence lineage

The first evidence version fixes the stable record lineage's authority ID and publisher origin. Later versions must:

- be registered by the same approved authority address;
- retain the same authority ID;
- retain the same origin; and
- strictly increase the version.

A request may resolve only against the latest registered version.

## Consensus

The implementation uses `gl.vm.run_nondet_unsafe`.

The leader and each validator independently execute the same bounded evaluator:

1. fetch each exact source URL;
2. require HTTP status `200`;
3. cap the body size;
4. SHA-256 the raw body;
5. require equality with the authority-registered digest;
6. decode UTF-8;
7. evaluate the question against the sealed criteria with `response_format="json"`; and
8. return only bounded decision fields.

Validators exactly compare:

- `kind`;
- `outcome`;
- `failure_code`; and
- `bundle_digest`.

No reasoning prose is persisted or compared.

## Web transport compatibility

Status-bearing fetches use `gl.nondet.web.request(url, method="GET")`.
The convenience `web.get()` path is not used when the contract needs
`response.status`.

The fetch exception boundary covers the transport call only. Response
inspection is intentionally outside that catch so an SDK/runtime API
mismatch cannot be silently mislabeled as `SOURCE_FETCH_FAILED`.

The request question is JSON-quoted and explicitly treated as untrusted
data in the evaluator prompt. Evidence bodies remain untrusted data as
well; only the sealed policy criteria govern evaluation.

## Effective validity and reusable attestation safety

`valid_until` is the earliest exclusive timestamp implied by all three
policy constraints: evidence expiry, maximum evidence age, and minimum
remaining validity. This prevents a request deadline from extending past
the point where evidence would already violate its sealed policy.

Historical attestations remain queryable. For live consequential use,
callers must use `is_attestation_current(request_id)`, which rejects
attestations after evidence supersession or any current freshness/validity
failure.

LLM JSON is required to contain exactly the four decision-bearing fields
`kind`, `outcome`, `failure_code`, and `bundle_digest`; extra fields are
rejected.

## Deterministic state boundary

No storage read or write occurs inside the nondeterministic evaluator.

All storage-derived inputs are copied into ordinary in-memory values before the nondeterministic block.

Persistent request/attestation mutations occur only after the nondeterministic result returns, except deterministic preflight transitions such as expiry or detection of stale/non-latest on-chain evidence.

## Deliberate v1 limitations

The implementation cannot prove that a policy-approved authority is truthful. Authority selection is part of the policy trust boundary.

LLM classification may fail to converge even when all validators evaluate the same exact source bytes. That failure must not be converted into an attestation; consensus disagreement/rotation is safer than a false result.

No claim of supported-runtime or Bradbury finality is made until those later verification stages complete.

## Compact atomic policy construction

The Bradbury-feasibility redesign removes the mutable policy-building sequence. `create_policy` receives the complete bounded authority-ID, authority-address, publisher-origin, and outcome sets in one call, validates them, derives the policy fingerprint, and stores the policy atomically. This removes partially configured policy state while preserving the same trust bindings.

The compact candidate keeps six public views and six public writes. It also rejects source-URL fragments and enforces both a 65,536-byte per-source limit and a 131,072-byte aggregate fetched-bundle limit.

Certified compact source SHA-256: `776dcd2ce4b0e6844d184831efe4b3e2b9b46eab2116d975bcf2f670b57562e5`. The source is 16,113 bytes. A write-blocked Bradbury dry-run measured 13,633,575 gas for deployment; the send method was blocked locally, so this is feasibility evidence, not a deployment/finality claim.
