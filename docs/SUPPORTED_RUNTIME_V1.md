# EvidenceGate v1 supported-runtime verification

Status: **harness prepared; execution not yet authorized or certified**.

This layer exists to prove properties that Direct Mode cannot prove: GenVM execution through the Studio RPC path, multi-validator consensus, transaction finalization, and durable `LATEST_FINAL` state reads.

## Bound source

The harness is bound to:

```text
contracts/evidence_gate.py
SHA-256 719e83531ba38b87cce825d68788d64a0f2971336626201ce1ea2f0726b0f1b2
```

The v1 supported-runtime harness is intentionally restricted to **localnet Studio Mode**. Bradbury deployment and Bradbury writes are a later, separately authorized stage.

## Required finalized scenarios

One deployment is reused to reduce cost and state noise. Every state-changing operation waits for `TransactionStatus.FINALIZED`, and every consequential read explicitly uses `TransactionHashVariant.LATEST_FINAL`.

The single integration workflow proves:

1. sealed policy setup with two distinct authority addresses and origins;
2. exact positive outcome `YES`;
3. exact negative outcome `NO`;
4. digest mismatch materialized as `REPAIR_REQUIRED`;
5. registration of a strictly newer evidence version;
6. repair using the newer version;
7. repaired request resolving to exact `YES`;
8. the old historical attestation becoming non-current after lineage supersession; and
9. deadline-driven `EXPIRED`.

## Mock validator model

Each transaction context uses five serialized GenLayer mock validators. Resolution contexts provide the exact HTTP response bodies and exact bounded LLM JSON expected by the contract. Validators therefore execute the real GenVM contract path while external web/LLM inputs are reproducible.

The harness does not use leader-only mode.

## Finality and execution are separate gates

Waiting for `FINALIZED` is not treated as proof that contract execution succeeded. Each finalized receipt must also satisfy the testing-suite execution-success assertion.

`Accepted` is never used as the completion condition.

## Raw evidence preservation

For every transaction the harness requests `full_transaction=True` and writes the returned full transaction object to the ignored artifact directory before decoding any leader return value at the harness layer.

For consequential resolution transactions it also extracts and persists every raw field exposed by the runtime (`raw`, `tx_receipt`, `eq_outputs`, `genvm_result`, where present). A consequential resolution fails the harness if the runtime exposes none of those raw fields.

This is the strongest preservation available through the pinned `genlayer-py` surface: SDK-level decoding may already have occurred before the Python object is returned, but any raw representation that remains exposed is persisted before harness-level decoding.

## No automatic write resubmission

The harness submits each write exactly once and then polls that transaction hash for finalization. A timeout or RPC ambiguity raises and stops the run. It never submits a replacement transaction automatically.

## Execution guard

`verification/run_supported_runtime.sh` refuses to run unless an explicit authorization environment value is supplied. It also rejects every network except `localnet`.

Preparing or committing this harness does **not** authorize network writes.

## Artifacts

A successful authorized run writes an append-only run directory:

```text
artifacts/evidencegate-supported-runtime/<UTC_RUN_ID>/
```

It contains full transaction snapshots, exposed raw fields, and a final manifest binding source hash, contract address, policy/request identities, exact verdicts, finality state, and transaction hashes.

`artifacts/` is intentionally gitignored. A later verification stage will decide which normalized, non-secret evidence is suitable for append-only publication under `verification/`.
