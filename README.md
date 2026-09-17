# EvidenceGate

**EvidenceGate is a reusable GenLayer Intelligent Contract for converting policy-bound, corroborated web evidence into exact attestations for other contracts and autonomous agents.**

> Status: the current fixed compact v1 source is implemented, reproducibly verified, deployed on GenLayer Bradbury, and live-network finalized. Direct Mode re-certified 28/28, the exact committed clean-tree supported-runtime finality run passed with five validators, the reviewer-style audit passed, and the canonical Bradbury request resolved to a finalized `YES` attestation with five-validator exact agreement.

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
- reproducible GenLayer verification across Direct Mode, isolated supported runtime, and a separately authorized Bradbury live proof.

## Verification path

1. Freeze specification, consensus model, and security invariants.
2. Implement the canonical contract candidate.
3. GenVM lint/typecheck.
4. Direct Mode deterministic regression.
5. Mocked web/LLM and adversarial failure tests.
6. Validator agreement/disagreement tests.
7. Supported-runtime finality tests with raw-response preservation.
8. Re-run source-sensitive verification after any contract change.
9. Independent reviewer-style audit.
10. Deploy the exact fixed source to Bradbury only after the earlier gates pass, then verify policy creation, two-authority evidence registration, request creation, resolution, validator agreement, and network finality.

See `docs/SPEC_V1.md`, `docs/SUPPORTED_RUNTIME_V1.md`, and `docs/BRADBURY_LIVE_PROOF_V1.md`.

## Current fixed compact v1

- Contract SHA-256: `6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1`
- Source size: `16181` bytes.
- Canonical Bradbury contract: `0xbd403771f876F72540319480EC2453d01de27a2b`.
- Canonical deployment transaction: `0xa3849f47e9f2e97b7957544407000a996398772dd716ba36bf5f6f1544122a1e` (`Finalized|7`).
- The GenVM runtime hardening snapshots request question, policy criteria, and allowed outcomes into ordinary memory before entering the nondeterministic leader closure.
- Isolated supported-runtime validation R22-R10 completed the existing five-validator finality harness, including exact positive and negative outcomes, repair/re-resolution, and deadline expiry.
- `verification/run_supported_runtime.sh` prepares a disposable pinned simulator environment and isolated GLSim instance so reproducibility does not depend on the external port-4000 Docker service.
- Canonical clean-tree execution R22-R19 ran that exact committed runner unchanged against five validators: all 17 writes reached `FINALIZED`, all five votes agreed on every finalized receipt, and 37 evidence artifacts were produced.
- Direct Mode re-certification R22-R16 passed 28/28 tests against this exact fixed source; the source-security guard also passed.
- Reviewer-style audit R22-R20R passed with no implementation defect found. Its remaining findings are explicit trust-boundary limitations: policy-approved authority truthfulness and real-world organizational independence are not cryptographically provable on-chain.
- R22-R50R re-verified the full Bradbury live path: deployment, policy creation, two evidence registrations, request creation, and resolution are all `Finalized|7`; the final request is `RESOLVED` with outcome `YES`.
- The finalized resolve round used five validators. All five votes were `AGREE`, and all five validator result hashes were identical to `0x8627ec61ad8c347cd2e86d5a3e4cf36699b3832a44dc69b71497f9f213dcad3f`.
- The finalized attestation binds policy fingerprint `4123169fde60475e1e6b831d8c1d6aed1f505597662360d121e9453e719c9bc8`, claim digest `017353226c04b05672fd2a3c2499af5d4ea7cb271d406dfa75ab1377ad02d43b`, evidence-bundle digest `18b392e491446e4b1b5991bbcb3383d7c5922f4fa9b39256f411b70d34f3f2a2`, two evidence records, two distinct authorities, and two distinct publisher origins.
- The live attestation has `valid_until = 1790229381`; R22-R50R observed it as current at chain timestamp `1789663471`.
- Historical Bradbury estimate/deployment evidence for the predecessor source remains historical only and is not evidence for this fixed source.

## Canonical Bradbury live proof

The reviewer-facing live proof is recorded in `docs/BRADBURY_LIVE_PROOF_V1.md`. It preserves the exact contract/source identity, transaction hashes, policy/evidence/request identifiers, immutable evidence hashes, finalized consensus result, and the remaining trust-boundary limitations.

The live proof does not claim that distinct on-chain authority addresses or publisher origins cryptographically prove independent real-world organizational control. Those are policy trust assumptions, not properties EvidenceGate can prove on-chain.
