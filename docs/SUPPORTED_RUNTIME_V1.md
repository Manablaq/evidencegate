# EvidenceGate v1 supported-runtime verification

Status: **harness prepared and statically reviewed; execution still requires explicit authorization**.

This layer exists to prove properties that Direct Mode cannot prove: GenVM execution through the local GenLayer RPC path, multi-validator consensus execution, transaction finalization, and durable `LATEST_FINAL` state reads.

## Bound source

The harness is bound to:

```text
contracts/evidence_gate.py
SHA-256 719e83531ba38b87cce825d68788d64a0f2971336626201ce1ea2f0726b0f1b2
```

The v1 supported-runtime harness is intentionally restricted to localnet. Bradbury deployment and Bradbury writes remain a later, separately authorized stage.

## Reproducible toolchain

The harness uses a repository-local `.venv`, not another project's environment.

Top-level supported-runtime dependencies are pinned in:

```text
requirements-supported-runtime.txt
```

The complete resolved environment is frozen in:

```text
requirements-supported-runtime-lock.txt
```

The execution runner verifies Python 3.12 and the exact required versions of `genlayer-test`, `genlayer-py`, `pytest`, and `eth-utils` before any GenLayer network preflight.

## Runtime artifact isolation

Gltest clears its configured artifacts directory when a test session starts. To prevent one verification run from deleting evidence from a previous run, `gltest.config.yaml` sends Gltest's disposable artifacts to:

```text
.gltest-artifacts/
```

EvidenceGate's own run evidence is stored separately under:

```text
artifacts/evidencegate-supported-runtime/<UTC_RUN_ID>/
```

A new run refuses to reuse an existing run ID.

## Required finalized scenarios

One deployment is reused to reduce state noise. Every state-changing operation waits for `TransactionStatus.FINALIZED`, and every consequential read explicitly uses `TransactionHashVariant.LATEST_FINAL`.

The integration workflow verifies:

1. sealed policy setup with two distinct authority addresses and origins;
2. exact positive outcome `YES`;
3. exact negative outcome `NO`;
4. digest mismatch materialized as `REPAIR_REQUIRED`;
5. registration of a strictly newer evidence version;
6. repair using the newer version;
7. repaired request resolving to exact `YES`;
8. the old historical attestation becoming non-current after lineage supersession; and
9. deadline-driven `EXPIRED`.

The workflow also asserts exact attestation fields, evidence/diversity counts, repair count, and evidence-bundle bindings.

## Consensus evidence

Every finalized write receipt must expose exactly five validator receipts and exactly five votes, and all five votes must be `agree`. The manifest records validator/vote counts for each transaction.

This proves that the pinned local runtime executed the contract through its multi-validator consensus path for the finalized positive and negative outcomes.

The pinned local simulator applies one reproducible mock web/LLM set to all validator executions. Therefore this layer does **not** claim heterogeneous per-validator mock divergence. Validator rejection on a deliberately different independently derived outcome is covered separately by the Direct Mode regression test. This distinction is intentional.

## Finality and execution are separate gates

Waiting for `FINALIZED` is not treated as proof that contract execution succeeded. Each finalized receipt must also satisfy the testing-suite execution-success assertion and the five-validator consensus assertions.

`ACCEPTED` is never used as the completion condition.

## Raw evidence preservation

For every transaction the harness requests `full_transaction=True` and writes the returned full transaction object before any harness-level decoding of the leader return value.

For consequential resolution transactions it also extracts and persists every raw representation still exposed by the pinned runtime (`raw`, `tx_receipt`, `eq_outputs`, `genvm_result`, where present). A consequential resolution fails if the runtime exposes none of those raw fields.

SDK-level decoding may occur before the Python object is returned; the harness does not claim access to bytes that the SDK no longer exposes. It persists all raw representations still available before doing its own return decoding.

## No automatic write resubmission

Each write is submitted exactly once and then the same transaction hash is polled for finalization. A timeout or RPC ambiguity stops the run. The harness never submits a replacement write automatically.

## Execution guard

`verification/run_supported_runtime.sh` refuses to run unless an explicit authorization environment value is supplied. Before the first write it verifies:

- clean build branch;
- exact contract SHA-256;
- exact integration-test/config/requirements/lock identities;
- repository-local toolchain versions;
- local GenLayer RPC reachability; and
- an RPC chain ID exactly matching the pinned `genlayer-py` `localnet` chain object.

Preparing, reviewing, or committing this harness does **not** authorize GenLayer network writes.

## Evidence manifest

A successful authorized run writes a manifest binding:

- contract source SHA-256;
- integration harness SHA-256;
- config and requirements identities;
- exact runtime package versions;
- contract/policy/request identities;
- positive, negative, repair, and expiry verdicts;
- transaction hashes and finality states; and
- per-transaction validator/vote counts.

`artifacts/` remains gitignored. A later stage will normalize suitable non-secret evidence for append-only publication under `verification/`.
