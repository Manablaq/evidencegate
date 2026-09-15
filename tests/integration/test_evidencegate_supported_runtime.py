import hashlib
import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from eth_utils import keccak
from hexbytes import HexBytes

from genlayer_py.types import SimConfig
from genlayer_py.types.transactions import (
    TRANSACTION_STATUS_NUMBER_TO_NAME,
)
from genlayer_py.utils.jsonifier import (
    result_to_user_friendly_json,
)
from gltest import get_validator_factory
from gltest.assertions import tx_execution_succeeded
from gltest.types import (
    TransactionHashVariant,
    TransactionStatus,
)
from gltest.utils import extract_contract_address
from gltest_cli.config.general import get_general_config


CONTRACT_PATH = Path("contracts/evidence_gate.py")
EXPECTED_CONTRACT_SHA256 = (
    "719e83531ba38b87cce825d68788d64a0f2971336626201ce1ea2f0726b0f1b2"
)

BASE_ISO = "2026-09-15T12:00:00Z"
EXPIRED_ISO = "2026-09-15T14:00:00Z"
BASE_NOW = 1_789_473_600
HOUR = 3600
DAY = 24 * HOUR

POLICY_SLUG = "supported-runtime-v1"
QUESTION = "Was shipment 42 delivered?"
CRITERIA = (
    "Return YES only when all supplied authoritative records explicitly "
    "confirm shipment 42 was delivered. Return NO only when all supplied "
    "authoritative records explicitly confirm it was not delivered. "
    "Otherwise require repair."
)

POSITIVE_BODY_A = "Authority A record: shipment 42 was delivered."
POSITIVE_BODY_B = "Authority B record: shipment 42 was delivered."
NEGATIVE_BODY_A = "Authority A record: shipment 42 was not delivered."
NEGATIVE_BODY_B = "Authority B record: shipment 42 was not delivered."


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _keccak_text(value: str) -> str:
    return keccak(text=value).hex()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, HexBytes):
        return {
            "__type__": "HexBytes",
            "hex": value.hex(),
        }
    if isinstance(value, bytes):
        return {
            "__type__": "bytes",
            "hex": value.hex(),
        }
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item)
            for item in value
        ]
    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value
    return {
        "__type__": (
            type(value).__module__
            + "."
            + type(value).__qualname__
        ),
        "repr": repr(value),
    }


def _atomic_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(
        path.suffix + ".tmp"
    )
    temp.write_text(
        json.dumps(
            _json_safe(value),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _collect_raw_exposed(
    value: Any,
    path: str = "$",
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if (
                key in {
                    "raw",
                    "tx_receipt",
                    "eq_outputs",
                    "genvm_result",
                }
                or key.endswith("_raw")
            ):
                found.append(
                    {
                        "path": child,
                        "value": item,
                    }
                )
            found.extend(
                _collect_raw_exposed(
                    item,
                    child,
                )
            )
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(
                _collect_raw_exposed(
                    item,
                    f"{path}[{index}]",
                )
            )

    return found


def _tx_hash_text(value: Any) -> str:
    if isinstance(value, (bytes, HexBytes)):
        return value.hex()
    return str(value)


def _status_name(receipt: dict[str, Any]) -> str:
    value = receipt.get("status_name")
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str):
        if value.startswith("TransactionStatus."):
            return value.split(".", 1)[1]
        return value

    raw = receipt.get("status")
    mapped = TRANSACTION_STATUS_NUMBER_TO_NAME.get(
        str(raw)
    )
    if mapped is None:
        return str(raw)
    return str(mapped.value)


def _persist_runtime_snapshot(
    artifact_root: Path,
    label: str,
    receipt: dict[str, Any],
    *,
    require_exposed_raw: bool,
) -> tuple[Path, int]:
    receipt_path = (
        artifact_root
        / f"{label}.full-transaction.json"
    )

    # This happens before any harness-level decoding of the
    # leader return value.
    _atomic_json(
        receipt_path,
        receipt,
    )

    raw_exposed = _collect_raw_exposed(
        receipt
    )
    raw_path = (
        artifact_root
        / f"{label}.raw-exposed-fields.json"
    )
    _atomic_json(
        raw_path,
        raw_exposed,
    )

    if require_exposed_raw and not raw_exposed:
        raise AssertionError(
            "runtime exposed no raw transaction/result "
            f"fields for consequential transaction {label}"
        )

    return receipt_path, len(raw_exposed)


def _assert_finalized_success(
    receipt: dict[str, Any],
) -> None:
    assert (
        _status_name(receipt)
        == TransactionStatus.FINALIZED.value
    ), receipt
    assert tx_execution_succeeded(receipt), receipt


def _sim_config(
    validators: list[dict[str, Any]],
    genvm_datetime: str,
) -> SimConfig:
    return SimConfig(
        validators=validators,
        genvm_datetime=genvm_datetime,
    )


def _mock_validator_configs(
    *,
    genvm_datetime: str,
    llm_result: dict[str, str] | None = None,
    web: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], SimConfig]:
    if llm_result is None:
        llm_result = {
            "kind": "RESOLVED",
            "outcome": "YES",
            "failure_code": "",
            "bundle_digest": "unused-deterministic-placeholder",
        }

    llm_response = {
        "nondet_exec_prompt": {
            ".*": json.dumps(
                llm_result,
                separators=(",", ":"),
                sort_keys=True,
            ),
        },
        "eq_principle_prompt_comparative": {},
        "eq_principle_prompt_non_comparative": {},
    }

    web_response = {
        "nondet_web_request": (
            web
            if web is not None
            else {}
        )
    }

    factory = get_validator_factory()
    validators = (
        factory.batch_create_mock_validators(
            count=5,
            mock_llm_response=llm_response,
            mock_web_response=web_response,
        )
    )
    serialized = [
        validator.to_dict()
        for validator in validators
    ]

    return (
        serialized,
        _sim_config(
            serialized,
            genvm_datetime,
        ),
    )


def _bundle_digest(
    policy_id: str,
    evidence_csv: str,
) -> str:
    return _keccak_text(
        "\x00".join(
            (
                "evidencegate-evidence-bundle-v1",
                policy_id,
                evidence_csv,
            )
        )
    )


def _evidence_csv(
    evidence_ids: list[str],
) -> str:
    return ",".join(
        sorted(evidence_ids)
    )


def _final_receipt(
    gl_client,
    artifact_root: Path,
    ledger: list[dict[str, Any]],
    *,
    label: str,
    tx_hash: Any,
    require_exposed_raw: bool,
) -> dict[str, Any]:
    interval = int(
        os.environ.get(
            "EVIDENCEGATE_WAIT_INTERVAL_MS",
            "1000",
        )
    )
    retries = int(
        os.environ.get(
            "EVIDENCEGATE_WAIT_RETRIES",
            "240",
        )
    )

    # Exactly one submitted transaction is polled. A timeout
    # raises; this helper never resubmits.
    receipt = (
        gl_client.wait_for_transaction_receipt(
            transaction_hash=tx_hash,
            status=TransactionStatus.FINALIZED,
            interval=interval,
            retries=retries,
            full_transaction=True,
        )
    )

    snapshot_path, raw_count = (
        _persist_runtime_snapshot(
            artifact_root,
            label,
            receipt,
            require_exposed_raw=require_exposed_raw,
        )
    )

    _assert_finalized_success(
        receipt
    )

    ledger.append(
        {
            "label": label,
            "submitted_tx_hash": _tx_hash_text(
                tx_hash
            ),
            "receipt_hash": _tx_hash_text(
                receipt.get("hash", "")
            ),
            "status": _status_name(receipt),
            "snapshot": snapshot_path.name,
            "raw_exposed_field_count": raw_count,
        }
    )

    return receipt


def _final_write(
    gl_client,
    artifact_root: Path,
    ledger: list[dict[str, Any]],
    *,
    label: str,
    contract_address: str,
    function_name: str,
    args: list[Any],
    account,
    sim_config: SimConfig,
    require_exposed_raw: bool = False,
) -> dict[str, Any]:
    tx_hash = gl_client.write_contract(
        address=contract_address,
        function_name=function_name,
        account=account,
        args=args,
        sim_config=sim_config,
    )

    return _final_receipt(
        gl_client,
        artifact_root,
        ledger,
        label=label,
        tx_hash=tx_hash,
        require_exposed_raw=require_exposed_raw,
    )


def _final_read(
    gl_client,
    *,
    contract_address: str,
    function_name: str,
    args: list[Any],
    account,
    sim_config: SimConfig,
):
    return gl_client.read_contract(
        address=contract_address,
        function_name=function_name,
        args=args,
        account=account,
        transaction_hash_variant=(
            TransactionHashVariant.LATEST_FINAL
        ),
        sim_config=sim_config,
    )


def _decode_return_after_snapshot(
    receipt: dict[str, Any],
):
    consensus = receipt.get(
        "consensus_data",
        {},
    )
    leader = consensus.get(
        "leader_receipt"
    )
    if leader is None:
        raise AssertionError(
            "leader_receipt missing"
        )

    receipts = (
        leader
        if isinstance(leader, list)
        else [leader]
    )
    if not receipts:
        raise AssertionError(
            "leader_receipt is empty"
        )

    result = receipts[0].get("result")
    if isinstance(result, str):
        result = (
            result_to_user_friendly_json(
                result
            )
        )

    if not isinstance(result, dict):
        raise AssertionError(
            "leader result is not decodable"
        )

    if result.get("status") != "return":
        raise AssertionError(
            f"leader result is not a return: {result}"
        )

    payload = result.get("payload")

    if (
        isinstance(payload, dict)
        and isinstance(
            payload.get("readable"),
            str,
        )
    ):
        return json.loads(
            payload["readable"]
        )

    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload

    return payload


def _register_evidence(
    gl_client,
    artifact_root: Path,
    ledger: list[dict[str, Any]],
    *,
    contract_address: str,
    policy_id: str,
    stable_id: str,
    version: int,
    authority_id: str,
    authority_account,
    source_url: str,
    body: str,
    base_config: SimConfig,
) -> dict[str, Any]:
    evidence_id = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="derive_evidence_id",
        args=[
            policy_id,
            stable_id,
            version,
        ],
        account=authority_account,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label=(
            "register-"
            + stable_id
            + "-v"
            + str(version)
        ),
        contract_address=contract_address,
        function_name="register_evidence",
        args=[
            policy_id,
            stable_id,
            version,
            authority_id,
            source_url,
            _sha256_text(body),
            BASE_NOW - HOUR,
            BASE_NOW + (10 * DAY),
        ],
        account=authority_account,
        sim_config=base_config,
    )

    stored = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_evidence",
        args=[evidence_id],
        account=authority_account,
        sim_config=base_config,
    )

    return {
        "evidence_id": evidence_id,
        "stable_id": stable_id,
        "version": version,
        "authority_id": authority_id,
        "authority_address": authority_account.address,
        "source_url": source_url,
        "body": body,
        "source_sha256": _sha256_text(body),
        "stored": stored,
    }


def _create_request(
    gl_client,
    artifact_root: Path,
    ledger: list[dict[str, Any]],
    *,
    label: str,
    contract_address: str,
    policy_id: str,
    claim_key: str,
    evidence_csv: str,
    deadline: int,
    owner,
    base_config: SimConfig,
) -> str:
    receipt = _final_write(
        gl_client,
        artifact_root,
        ledger,
        label=label,
        contract_address=contract_address,
        function_name="create_request",
        args=[
            policy_id,
            claim_key,
            QUESTION,
            evidence_csv,
            deadline,
        ],
        account=owner,
        sim_config=base_config,
    )

    request_id = (
        _decode_return_after_snapshot(
            receipt
        )
    )

    assert isinstance(
        request_id,
        str,
    )
    assert len(request_id) == 64

    return request_id


def _resolve_context(
    *,
    evidence: list[dict[str, Any]],
    bundle_digest: str,
    outcome: str,
    body_overrides: dict[str, str] | None = None,
    kind: str = "RESOLVED",
    failure_code: str = "",
) -> SimConfig:
    body_overrides = (
        body_overrides
        if body_overrides is not None
        else {}
    )

    web: dict[str, dict[str, Any]] = {}

    for record in evidence:
        url = record["source_url"]
        body = body_overrides.get(
            record["evidence_id"],
            record["body"],
        )
        web[url] = {
            "method": "GET",
            "status": 200,
            "body": body,
        }

    llm = {
        "kind": kind,
        "outcome": outcome,
        "failure_code": failure_code,
        "bundle_digest": bundle_digest,
    }

    _, config = _mock_validator_configs(
        genvm_datetime=BASE_ISO,
        llm_result=llm,
        web=web,
    )
    return config


@pytest.mark.integration
def test_evidencegate_supported_runtime_finality(
    gl_client,
    default_account,
    accounts,
):
    network_name = (
        get_general_config()
        .get_network_name()
    )
    assert network_name == "localnet"

    assert len(accounts) >= 3
    owner = default_account
    authority_a = accounts[1]
    authority_b = accounts[2]

    run_id = os.environ.get(
        "EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID"
    )
    assert run_id

    artifact_root = (
        Path("artifacts")
        / "evidencegate-supported-runtime"
        / run_id
    )
    assert not artifact_root.exists()
    artifact_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    source_bytes = CONTRACT_PATH.read_bytes()
    source_sha = _sha256_bytes(
        source_bytes
    )
    assert (
        source_sha
        == EXPECTED_CONTRACT_SHA256
    )

    source = source_bytes.decode(
        "utf-8"
    )

    ledger: list[dict[str, Any]] = []

    _, base_config = (
        _mock_validator_configs(
            genvm_datetime=BASE_ISO,
        )
    )

    deploy_hash = (
        gl_client.deploy_contract(
            code=source,
            account=owner,
            sim_config=base_config,
        )
    )
    deploy_receipt = _final_receipt(
        gl_client,
        artifact_root,
        ledger,
        label="deploy",
        tx_hash=deploy_hash,
        require_exposed_raw=False,
    )

    contract_address = (
        extract_contract_address(
            deploy_receipt
        )
    )

    policy_id = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="derive_policy_id",
        args=[
            owner.address,
            POLICY_SLUG,
            1,
        ],
        account=owner,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="create-policy",
        contract_address=contract_address,
        function_name="create_policy",
        args=[
            POLICY_SLUG,
            1,
            CRITERIA,
            2,
            2,
            2,
            30 * DAY,
            HOUR,
            14 * DAY,
            4,
        ],
        account=owner,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="add-authority-a",
        contract_address=contract_address,
        function_name="add_policy_authority",
        args=[
            policy_id,
            "authority-a",
            authority_a.address,
            "https://alpha.example.com",
        ],
        account=owner,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="add-authority-b",
        contract_address=contract_address,
        function_name="add_policy_authority",
        args=[
            policy_id,
            "authority-b",
            authority_b.address,
            "https://beta.example.com",
        ],
        account=owner,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="add-outcome-no",
        contract_address=contract_address,
        function_name="add_policy_outcome",
        args=[
            policy_id,
            "NO",
        ],
        account=owner,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="add-outcome-yes",
        contract_address=contract_address,
        function_name="add_policy_outcome",
        args=[
            policy_id,
            "YES",
        ],
        account=owner,
        sim_config=base_config,
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="seal-policy",
        contract_address=contract_address,
        function_name="seal_policy",
        args=[policy_id],
        account=owner,
        sim_config=base_config,
    )

    policy = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_policy",
        args=[policy_id],
        account=owner,
        sim_config=base_config,
    )

    # Positive / approval path.
    positive_a = _register_evidence(
        gl_client,
        artifact_root,
        ledger,
        contract_address=contract_address,
        policy_id=policy_id,
        stable_id="positive-a",
        version=1,
        authority_id="authority-a",
        authority_account=authority_a,
        source_url=(
            "https://alpha.example.com/"
            "records/positive-a-v1"
        ),
        body=POSITIVE_BODY_A,
        base_config=base_config,
    )
    positive_b = _register_evidence(
        gl_client,
        artifact_root,
        ledger,
        contract_address=contract_address,
        policy_id=policy_id,
        stable_id="positive-b",
        version=1,
        authority_id="authority-b",
        authority_account=authority_b,
        source_url=(
            "https://beta.example.com/"
            "records/positive-b-v1"
        ),
        body=POSITIVE_BODY_B,
        base_config=base_config,
    )

    positive_records = [
        positive_a,
        positive_b,
    ]
    positive_csv = _evidence_csv(
        [
            positive_a["evidence_id"],
            positive_b["evidence_id"],
        ]
    )
    positive_request = _create_request(
        gl_client,
        artifact_root,
        ledger,
        label="create-request-positive",
        contract_address=contract_address,
        policy_id=policy_id,
        claim_key="supported-positive",
        evidence_csv=positive_csv,
        deadline=BASE_NOW + DAY,
        owner=owner,
        base_config=base_config,
    )
    positive_bundle = _bundle_digest(
        policy_id,
        positive_csv,
    )
    positive_config = _resolve_context(
        evidence=positive_records,
        bundle_digest=positive_bundle,
        outcome="YES",
    )

    positive_receipt = _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="resolve-positive",
        contract_address=contract_address,
        function_name="resolve_request",
        args=[positive_request],
        account=owner,
        sim_config=positive_config,
        require_exposed_raw=True,
    )

    assert (
        _decode_return_after_snapshot(
            positive_receipt
        )
        == "YES"
    )

    positive_verdict = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_verdict",
        args=[positive_request],
        account=owner,
        sim_config=base_config,
    )
    assert positive_verdict[0:3] == [
        "RESOLVED",
        "YES",
        "",
    ]

    positive_attestation = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_attestation",
        args=[positive_request],
        account=owner,
        sim_config=base_config,
    )

    assert (
        _final_read(
            gl_client,
            contract_address=contract_address,
            function_name="is_attestation_current",
            args=[positive_request],
            account=owner,
            sim_config=base_config,
        )
        is True
    )

    # Negative / rejection path.
    negative_a = _register_evidence(
        gl_client,
        artifact_root,
        ledger,
        contract_address=contract_address,
        policy_id=policy_id,
        stable_id="negative-a",
        version=1,
        authority_id="authority-a",
        authority_account=authority_a,
        source_url=(
            "https://alpha.example.com/"
            "records/negative-a-v1"
        ),
        body=NEGATIVE_BODY_A,
        base_config=base_config,
    )
    negative_b = _register_evidence(
        gl_client,
        artifact_root,
        ledger,
        contract_address=contract_address,
        policy_id=policy_id,
        stable_id="negative-b",
        version=1,
        authority_id="authority-b",
        authority_account=authority_b,
        source_url=(
            "https://beta.example.com/"
            "records/negative-b-v1"
        ),
        body=NEGATIVE_BODY_B,
        base_config=base_config,
    )

    negative_records = [
        negative_a,
        negative_b,
    ]
    negative_csv = _evidence_csv(
        [
            negative_a["evidence_id"],
            negative_b["evidence_id"],
        ]
    )
    negative_request = _create_request(
        gl_client,
        artifact_root,
        ledger,
        label="create-request-negative",
        contract_address=contract_address,
        policy_id=policy_id,
        claim_key="supported-negative",
        evidence_csv=negative_csv,
        deadline=BASE_NOW + DAY,
        owner=owner,
        base_config=base_config,
    )
    negative_bundle = _bundle_digest(
        policy_id,
        negative_csv,
    )
    negative_config = _resolve_context(
        evidence=negative_records,
        bundle_digest=negative_bundle,
        outcome="NO",
    )

    negative_receipt = _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="resolve-negative",
        contract_address=contract_address,
        function_name="resolve_request",
        args=[negative_request],
        account=owner,
        sim_config=negative_config,
        require_exposed_raw=True,
    )

    assert (
        _decode_return_after_snapshot(
            negative_receipt
        )
        == "NO"
    )

    negative_verdict = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_verdict",
        args=[negative_request],
        account=owner,
        sim_config=base_config,
    )
    assert negative_verdict[0:3] == [
        "RESOLVED",
        "NO",
        "",
    ]

    negative_attestation = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_attestation",
        args=[negative_request],
        account=owner,
        sim_config=base_config,
    )

    # Repairable failure and repair with a newer evidence version.
    repair_request = _create_request(
        gl_client,
        artifact_root,
        ledger,
        label="create-request-repair",
        contract_address=contract_address,
        policy_id=policy_id,
        claim_key="supported-repair",
        evidence_csv=positive_csv,
        deadline=BASE_NOW + DAY,
        owner=owner,
        base_config=base_config,
    )
    repair_bundle = _bundle_digest(
        policy_id,
        positive_csv,
    )

    tampered = {
        positive_a["evidence_id"]: (
            POSITIVE_BODY_A
            + " tampered-after-registration"
        )
    }
    repair_failure_config = (
        _resolve_context(
            evidence=positive_records,
            bundle_digest=repair_bundle,
            outcome="",
            kind="REPAIR_REQUIRED",
            failure_code=(
                "CONFLICTING_OR_INSUFFICIENT_EVIDENCE"
            ),
            body_overrides=tampered,
        )
    )

    repair_failure_receipt = _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="resolve-repairable-failure",
        contract_address=contract_address,
        function_name="resolve_request",
        args=[repair_request],
        account=owner,
        sim_config=repair_failure_config,
        require_exposed_raw=True,
    )

    assert (
        _decode_return_after_snapshot(
            repair_failure_receipt
        )
        == "REPAIR_REQUIRED"
    )

    repair_failure_verdict = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_verdict",
        args=[repair_request],
        account=owner,
        sim_config=base_config,
    )
    assert repair_failure_verdict[0:3] == [
        "REPAIR_REQUIRED",
        "",
        "SOURCE_DIGEST_MISMATCH",
    ]

    positive_a_v2 = _register_evidence(
        gl_client,
        artifact_root,
        ledger,
        contract_address=contract_address,
        policy_id=policy_id,
        stable_id="positive-a",
        version=2,
        authority_id="authority-a",
        authority_account=authority_a,
        source_url=(
            "https://alpha.example.com/"
            "records/positive-a-v2"
        ),
        body=(
            POSITIVE_BODY_A
            + " Version 2 remains authoritative."
        ),
        base_config=base_config,
    )

    assert (
        _final_read(
            gl_client,
            contract_address=contract_address,
            function_name="is_attestation_current",
            args=[positive_request],
            account=owner,
            sim_config=base_config,
        )
        is False
    )

    repaired_records = [
        positive_a_v2,
        positive_b,
    ]
    repaired_csv = _evidence_csv(
        [
            positive_a_v2["evidence_id"],
            positive_b["evidence_id"],
        ]
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="repair-request-with-v2",
        contract_address=contract_address,
        function_name="repair_request",
        args=[
            repair_request,
            repaired_csv,
        ],
        account=owner,
        sim_config=base_config,
    )

    repaired_bundle = _bundle_digest(
        policy_id,
        repaired_csv,
    )
    repaired_config = _resolve_context(
        evidence=repaired_records,
        bundle_digest=repaired_bundle,
        outcome="YES",
    )

    repaired_resolve_receipt = _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="resolve-repaired-request",
        contract_address=contract_address,
        function_name="resolve_request",
        args=[repair_request],
        account=owner,
        sim_config=repaired_config,
        require_exposed_raw=True,
    )

    assert (
        _decode_return_after_snapshot(
            repaired_resolve_receipt
        )
        == "YES"
    )

    repaired_verdict = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_verdict",
        args=[repair_request],
        account=owner,
        sim_config=base_config,
    )
    assert repaired_verdict[0:3] == [
        "RESOLVED",
        "YES",
        "",
    ]

    assert (
        _final_read(
            gl_client,
            contract_address=contract_address,
            function_name="is_attestation_current",
            args=[repair_request],
            account=owner,
            sim_config=base_config,
        )
        is True
    )

    # Deadline-expiry path.
    expiry_request = _create_request(
        gl_client,
        artifact_root,
        ledger,
        label="create-request-expiry",
        contract_address=contract_address,
        policy_id=policy_id,
        claim_key="supported-expiry",
        evidence_csv=negative_csv,
        deadline=BASE_NOW + 60,
        owner=owner,
        base_config=base_config,
    )

    _, expired_config = (
        _mock_validator_configs(
            genvm_datetime=EXPIRED_ISO,
        )
    )

    _final_write(
        gl_client,
        artifact_root,
        ledger,
        label="expire-request",
        contract_address=contract_address,
        function_name="expire_request",
        args=[expiry_request],
        account=owner,
        sim_config=expired_config,
    )

    expiry_verdict = _final_read(
        gl_client,
        contract_address=contract_address,
        function_name="get_verdict",
        args=[expiry_request],
        account=owner,
        sim_config=expired_config,
    )
    assert expiry_verdict[0:3] == [
        "EXPIRED",
        "",
        "REQUEST_DEADLINE_REACHED",
    ]

    manifest = {
        "schema": "evidencegate-supported-runtime-v1",
        "run_id": run_id,
        "network": network_name,
        "contract_source_sha256": source_sha,
        "contract_address": contract_address,
        "policy_id": policy_id,
        "policy": policy,
        "positive": {
            "request_id": positive_request,
            "verdict": positive_verdict,
            "attestation": positive_attestation,
        },
        "negative": {
            "request_id": negative_request,
            "verdict": negative_verdict,
            "attestation": negative_attestation,
        },
        "repair": {
            "request_id": repair_request,
            "failure_verdict": repair_failure_verdict,
            "final_verdict": repaired_verdict,
        },
        "expiry": {
            "request_id": expiry_request,
            "verdict": expiry_verdict,
        },
        "transactions": ledger,
        "safety": {
            "latest_final_reads_only": True,
            "waited_for_finalized_status": True,
            "write_resubmission_on_timeout": False,
            "raw_runtime_snapshot_before_harness_return_decode": True,
            "mock_validator_count": 5,
        },
    }

    _atomic_json(
        artifact_root / "manifest.json",
        manifest,
    )

    assert len(ledger) >= 20
    assert all(
        tx["status"] == "FINALIZED"
        for tx in ledger
    )
