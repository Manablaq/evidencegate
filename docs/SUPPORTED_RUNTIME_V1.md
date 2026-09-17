# EvidenceGate v1 supported-runtime verification

Status: **the current fixed source passed the exact committed clean-tree supported-runtime reproduction in R22-R19 with five validators and finalized consensus; R22-R20R then passed the reviewer-style audit with no implementation defect found**.

This layer exists to prove properties that Direct Mode cannot prove: GenVM execution through the local GenLayer RPC path, multi-validator consensus execution, transaction finalization, and durable `LATEST_FINAL` state reads.

## Bound source

The harness is bound to:

```text
contracts/evidence_gate.py
SHA-256 6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1
```

The v1 supported-runtime harness is intentionally restricted to isolated localnet. Bradbury live-network verification is a separate layer documented in `BRADBURY_LIVE_PROOF_V1.md`; its writes were separately authorized and are not part of the supported-runtime harness. Historical Bradbury activity for the predecessor source is not deployment or finality evidence for this source.

## Reproducible toolchain

The guarded runner creates a disposable Python 3.12 virtual environment from the exact repository lockfile rather than depending on another project's environment or the developer's existing `.venv`.

Top-level supported-runtime dependencies are pinned in:

```text
requirements-supported-runtime.txt
```

The complete resolved environment is frozen in:

```text
requirements-supported-runtime-lock.txt
```

The execution runner verifies the exact locked runtime, including `genlayer-test`, `genlayer-py`, `pytest`, `eth-utils`, the simulator extra dependencies, and the explicitly pinned NumPy runtime before starting its isolated GLSim instance.

## GLSim compatibility boundary

The pinned `genlayer-test` 0.29.2 simulator supports the two-parameter `eth_sendRawTransaction` form used by `genlayer-py` 0.16.3. Its published simulator environment requires the simulator extra dependencies and NumPy; those are now included in the supported-runtime requirements and exact lock.

R22-R10 also identified a simulator-only read-result codec limitation: GLSim cannot directly encode a GenLayer `Address` wrapper nested in a returned dataclass on the `gen_call` path. The successful isolated validation normalized only those simulator return wrappers before SDK calldata encoding. The guarded runner reproduces that boundary with a temporary `sitecustomize.py` shim inside its disposable environment. The contract source and consensus harness are not patched by that shim.

The runner starts its own isolated GLSim instance on port 4011 by default, chain ID 61999, with five validators and three maximum rotations. It does not depend on the separately running Studio/Docker service on port 4000.

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

1. atomic sealed-policy creation with two distinct authority addresses and origins;
2. exact positive outcome `YES`;
3. exact negative outcome `NO`;
4. digest mismatch materialized as `REPAIR_REQUIRED`;
5. registration of a strictly newer evidence version;
6. repair using the newer version;
7. repaired request resolving to exact `YES`;
8. the old historical attestation becoming non-current after lineage supersession; and
9. deadline-driven `EXPIRED`.

The workflow also asserts exact attestation fields, evidence/diversity counts, repair count, and evidence-bundle bindings.

For the compact API, a successful complete run is expected to contain exactly 17 finalized state-changing transactions including deployment. The policy is created and sealed in one transaction rather than a mutable setup sequence.

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
- required host tools;
- an exact disposable Python 3.12 environment recreated from the lockfile;
- the temporary GLSim compatibility shim with a local round-trip proof;
- availability of the isolated GLSim port;
- an isolated chain ID of 61999; and
- five configured validators.

Preparing, reviewing, or committing this harness does **not** authorize GenLayer network writes.

## Verified precommit execution

R22-R15 reproduced the current fixed source through the self-contained isolated localnet path with five validators and finality. The run used chain ID 61999 and produced 37 local evidence files. It submitted no Bradbury transaction.

The precommit run is bound by:

```text
run id: r22-r15-precommit-self-contained
manifest SHA-256: 319fb36e0dcb5c2b05dc6a31a3190895368e66e9291941c6129e21642fc32f22
runner-runtime SHA-256: 915d1a69093ba83db34f97a6a9a463987355f2f1a73b71847befbfdff9c33621
GLSim log SHA-256: 95cb6efc24eed1443cd910422e5d34d1c068b35a6117f28b621b3699d81be729
GLSim compatibility shim SHA-256: 595e4802b04c18e88a23a957d12d7d97dda38181cbfef2f8f47439973f800bd7
```

R22-R16 then re-certified the same source in Direct Mode: the source-security guard passed and the full Direct Mode regression passed 28/28. Neither R22-R16 nor its source guard submitted a GenLayer network transaction.

Because R22-R15 necessarily adapted only the runner's clean-tree guard while the candidate was still uncommitted, one execution of the exact committed canonical runner from a clean tree remains the final reproducibility gate. The temporary runner adaptation did not change the contract, integration harness, toolchain bindings, simulator configuration, consensus logic, or transaction behavior.

## Canonical clean-tree execution

R22-R19 executed the exact committed `verification/run_supported_runtime.sh` unchanged from canonical commit `03f7ceb20667f71c901e27940217ce4e9ab0f3a8`. The repository was clean before and after execution. The isolated run used localnet chain ID 61999 with five validators, produced 17 finalized writes and 37 evidence files, and submitted no Bradbury transaction.

The canonical evidence identities are:

```text
run id: r22-r19-canonical-clean-tree
manifest SHA-256: e8aba5d2abc6595b815aaa8220d4d9971cad9f6bb5a66b219401358709af2a8e
runner-runtime SHA-256: 1ed995e331a82924e8af66923c9c52edaf91dbcfbbf79fce4921e7d497000a16
GLSim log SHA-256: 1dcd1b6e1f4b251bf80da99ff3717cabcbc0f4eec235b12f57bb3fa4017300a2
contract SHA-256: 6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1
integration-test SHA-256: 71a34d8c258292d30f445a303d77a37d6f5aeeeb01ed0d6c6b63a5e17b98cda0
runner SHA-256: 5e1fcbdd3da642c0630111f376167e3736abbfecc0e10293bb35bdcbf49bf36e
```

R22-R20R independently rechecked the committed contract surface, provenance/versioning/freshness controls, repair and expiry semantics, nondeterministic isolation, exact validator comparison of consequential fields, finalized artifact evidence, and raw-before-decode snapshots. It found no implementation defect. It explicitly does not claim that on-chain checks can prove a policy-approved authority is truthful or that distinct authority addresses and publisher origins are controlled by independent real-world organizations.

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

`artifacts/` remains gitignored. Reviewer-facing non-secret Bradbury live-proof identifiers are documented in `BRADBURY_LIVE_PROOF_V1.md`; runtime artifacts remain local and are not represented as public Bradbury evidence.
