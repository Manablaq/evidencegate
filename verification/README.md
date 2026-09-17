# EvidenceGate verification ladder

No verification layer may claim properties that belong to another layer.

## Release verification ladder

The canonical v1 release followed this ladder before Bradbury deployment:

1. Python syntax/source guards.
2. GenVM lint and typecheck.
3. Direct Mode deterministic state regression.
4. Mocked web/LLM success and failure cases.
5. Validator agreement/disagreement tests.
6. Supported-runtime finality tests.
7. Independent reviewer-style security audit.
8. Exact source freeze and hash.

The supported-runtime suite must finalize at least:

- one positive/approval outcome;
- one negative/rejection outcome;
- one repairable evidence failure;
- repair using newer/replacement evidence; and
- deadline expiry.

The supported-runtime harness must persist raw nondeterministic response bytes before decoding where the runtime exposes those bytes.

Historical Bradbury activity for a predecessor source must not be presented as deployment or finality evidence for the current fixed candidate.

## Supported-runtime harness

The guarded localnet runtime harness is:

- `tests/integration/test_evidencegate_supported_runtime.py`
- `verification/run_supported_runtime.sh`
- `docs/SUPPORTED_RUNTIME_V1.md`
- `requirements-supported-runtime.txt`
- `requirements-supported-runtime-lock.txt`

`gltest.config.yaml` places Gltest's disposable artifacts under `.gltest-artifacts/`, while EvidenceGate run evidence is preserved separately under `artifacts/evidencegate-supported-runtime/`.

The harness is source-bound, toolchain-bound, finality-strict, `LATEST_FINAL`-strict, and asserts five validator receipts plus five agreeing votes for every finalized write.

The harness is bound to the fixed compact contract SHA-256 `6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1` and its atomic sealed-policy API. R22-R10 completed an isolated five-validator supported-runtime validation of this fixed source, covering finalized positive and negative outcomes, repair/re-resolution, and expiry. The self-contained guarded runner reproduces that environment from the exact lockfile, and canonical clean-tree execution plus artifact capture completed in R22-R19.

The guarded runner starts an isolated GLSim instance rather than depending on the external port-4000 Studio service. Its simulator-only compatibility shim normalizes GenLayer `Address` wrappers in GLSim read results before SDK calldata encoding; it does not change EvidenceGate contract code or validator consensus logic.

Precommit execution R22-R15 passed the full supported-runtime harness with five validators and produced 37 local evidence files. Its manifest SHA-256 is `319fb36e0dcb5c2b05dc6a31a3190895368e66e9291941c6129e21642fc32f22` and its runner-runtime record SHA-256 is `915d1a69093ba83db34f97a6a9a463987355f2f1a73b71847befbfdff9c33621`. No Bradbury transaction was submitted. R22-R16 subsequently passed the source-security guard and all 28 Direct Mode tests against the same fixed contract source.

Canonical clean-tree execution R22-R19 completed after commit `03f7ceb20667f71c901e27940217ce4e9ab0f3a8` using the exact committed runner unchanged. It produced 37 evidence files and 17 finalized writes with five agreeing validators. The canonical manifest SHA-256 is `e8aba5d2abc6595b815aaa8220d4d9971cad9f6bb5a66b219401358709af2a8e`, the runner-runtime record SHA-256 is `1ed995e331a82924e8af66923c9c52edaf91dbcfbbf79fce4921e7d497000a16`, and the GLSim log SHA-256 is `1dcd1b6e1f4b251bf80da99ff3717cabcbc0f4eec235b12f57bb3fa4017300a2`. No Bradbury transaction was submitted.

Reviewer-style audit R22-R20R then passed without finding an implementation defect. The audit preserves two explicit trust-boundary limitations: the contract cannot cryptographically prove the truthfulness of an approved authority, and distinct on-chain authority addresses/origins cannot prove independent real-world organizational control.

Direct Mode separately proves that the contract validator rejects a deliberately different independently derived consequential outcome. The pinned local supported runtime shares one deterministic mock set across validator executions, so the runtime layer does not falsely claim heterogeneous per-validator mock divergence.

The harness source alone is not evidence of execution; the canonical R22-R19 run identities above provide the reproducibility record for the supported-runtime layer. Bradbury live-network verification is a separate layer documented in `docs/BRADBURY_LIVE_PROOF_V1.md`, and neither layer substitutes for the other.
