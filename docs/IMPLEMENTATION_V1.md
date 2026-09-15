# EvidenceGate v1 implementation notes

This document describes the first canonical implementation candidate for the frozen v1 specification.

## Authority identity

A policy authority is not only a label or URL. `add_policy_authority` binds all three of:

- canonical authority ID;
- exact GenLayer/EVM-style authority address; and
- exact canonical HTTPS publisher origin.

Only that bound authority address may register or advance evidence for its authority ID.

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
2. cap the body size;
3. SHA-256 the raw body;
4. require equality with the authority-registered digest;
5. decode UTF-8;
6. evaluate the question against the sealed criteria with `response_format="json"`; and
7. return only bounded decision fields.

Validators exactly compare:

- `kind`;
- `outcome`;
- `failure_code`; and
- `bundle_digest`.

No reasoning prose is persisted or compared.

## Deterministic state boundary

No storage read or write occurs inside the nondeterministic evaluator.

All storage-derived inputs are copied into ordinary in-memory values before the nondeterministic block.

Persistent request/attestation mutations occur only after the nondeterministic result returns, except deterministic preflight transitions such as expiry or detection of stale/non-latest on-chain evidence.

## Deliberate v1 limitations

The implementation cannot prove that a policy-approved authority is truthful. Authority selection is part of the policy trust boundary.

LLM classification may fail to converge even when all validators evaluate the same exact source bytes. That failure must not be converted into an attestation; consensus disagreement/rotation is safer than a false result.

No claim of supported-runtime or Bradbury finality is made until those later verification stages complete.
