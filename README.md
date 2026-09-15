# EvidenceGate

**EvidenceGate is a reusable GenLayer Intelligent Contract for converting policy-bound, corroborated web evidence into exact attestations for other contracts and autonomous agents.**

> Status: v1 specification frozen for implementation. Not deployed.

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
