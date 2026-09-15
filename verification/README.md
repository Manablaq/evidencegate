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

The guarded Studio Mode harness is:

- `tests/integration/test_evidencegate_supported_runtime.py`
- `verification/run_supported_runtime.sh`
- `docs/SUPPORTED_RUNTIME_V1.md`

The harness is source-bound and finality-strict, but its presence is not evidence that it has been executed. Network execution remains a separate explicitly authorized step.
