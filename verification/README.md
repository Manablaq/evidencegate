# EvidenceGate verification ladder

No verification layer may claim properties that belong to another layer.

Required before Bradbury deployment:

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

Until those gates pass, the repository must not claim Bradbury deployment/finality.

## Supported-runtime harness

The guarded localnet runtime harness is:

- `tests/integration/test_evidencegate_supported_runtime.py`
- `verification/run_supported_runtime.sh`
- `docs/SUPPORTED_RUNTIME_V1.md`
- `requirements-supported-runtime.txt`
- `requirements-supported-runtime-lock.txt`

`gltest.config.yaml` places Gltest's disposable artifacts under `.gltest-artifacts/`, while EvidenceGate run evidence is preserved separately under `artifacts/evidencegate-supported-runtime/`.

The harness is source-bound, toolchain-bound, finality-strict, `LATEST_FINAL`-strict, and asserts five validator receipts plus five agreeing votes for every finalized write.

The prepared harness is now bound to the compact contract SHA-256 `776dcd2ce4b0e6844d184831efe4b3e2b9b46eab2116d975bcf2f670b57562e5` and its atomic sealed-policy API. This adaptation has only been statically certified; it is not evidence of supported-runtime execution.

Direct Mode separately proves that the contract validator rejects a deliberately different independently derived consequential outcome. The pinned local supported runtime shares one deterministic mock set across validator executions, so the runtime layer does not falsely claim heterogeneous per-validator mock divergence.

The presence of this harness is not evidence that it has been executed. GenLayer network execution remains a separate explicitly authorized step.
