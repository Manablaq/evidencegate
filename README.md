# EvidenceGate

**EvidenceGate is a reusable GenLayer Intelligent Contract for converting policy-bound, corroborated web evidence into exact attestations for other contracts and autonomous agents.**

> Status: current fixed compact v1 candidate implemented, Direct Mode re-certified 28/28, and validated through an isolated five-validator supported-runtime finality run. An independent reviewer-style audit and the canonical clean-tree supported-runtime reproduction remain release gates. The current fixed source has not been deployed.

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
- reproducible GenLayer verification before any deployment of the current fixed candidate.

## Build order

1. Freeze specification, consensus model, and security invariants.
2. Implement the canonical contract candidate.
3. GenVM lint/typecheck.
4. Direct Mode deterministic regression.
5. Mocked web/LLM and adversarial failure tests.
6. Validator agreement/disagreement tests.
7. Supported-runtime finality tests with raw-response preservation.
8. Re-run source-sensitive verification after any contract change.
9. Independent reviewer-style audit.
10. Only then consider deployment of the current fixed candidate.

See `docs/SPEC_V1.md`.

## Current fixed compact candidate

- Contract SHA-256: `6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1`
- Source size: `16181` bytes.
- The GenVM runtime hardening snapshots request question, policy criteria, and allowed outcomes into ordinary memory before entering the nondeterministic leader closure.
- Isolated supported-runtime validation R22-R10 completed the existing five-validator finality harness, including exact positive and negative outcomes, repair/re-resolution, and deadline expiry.
- `verification/run_supported_runtime.sh` now prepares a disposable pinned simulator environment and isolated GLSim instance so the final reproducibility run does not depend on the external port-4000 Docker service.
- The guarded runner still requires one clean-tree authorized localnet execution before its publication artifacts can be treated as canonical reproducibility evidence.
- Direct Mode re-certification R22-R16 passed 28/28 tests against this exact fixed source; the source-security guard also passed.
- The independent reviewer-style audit must still be refreshed before release.
- Historical Bradbury estimate/deployment evidence belongs to a predecessor source and is not deployment or finality evidence for this fixed candidate.
