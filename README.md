# EvidenceGate

**EvidenceGate is a reusable GenLayer Intelligent Contract for converting policy-bound, corroborated web evidence into exact attestations for other contracts and autonomous agents.**

> Status: compact v1 contract implemented and Direct Mode certified; supported-runtime harness adapted but not yet executed. Not deployed.

## Scope

EvidenceGate v1 is intentionally contract-first:

- one Intelligent Contract;
- no frontend;
- no token;
- no escrow or value custody;
- no backend or database;
- no cross-contract dependency;
- exact consequential outcomes;
- explicit repair and expiry semantics; and
- reproducible GenLayer verification before any Bradbury deployment.

## Build order

1. Freeze specification, consensus model, and security invariants.
2. Implement the canonical contract candidate.
3. GenVM lint/typecheck.
4. Direct Mode deterministic regression.
5. Mocked web/LLM and adversarial failure tests.
6. Validator agreement/disagreement tests.
7. Supported-runtime finality tests with raw-response preservation.
8. Independent reviewer-style audit.
9. Only then consider Bradbury deployment.

See `docs/SPEC_V1.md`.

## Current compact candidate

- Contract SHA-256: `776dcd2ce4b0e6844d184831efe4b3e2b9b46eab2116d975bcf2f670b57562e5`
- Source size: `16,113` bytes.
- Full Direct Mode regression: `28/28` passed twice.
- Write-blocked Bradbury `eth_estimateGas`: `13,633,575` gas for `16,356` bytes of deployment calldata.
- The Bradbury estimate was read-only; no deployment or transaction was submitted.
- Supported-runtime finality execution and independent final audit remain required before a new Bradbury deployment authorization is requested.
