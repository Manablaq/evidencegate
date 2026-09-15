from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "evidence_gate.py"


def text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


source = text()
ast.parse(source)

required = [
    "class EvidenceGate(gl.Contract):",
    "def create_policy(",
    "def add_policy_authority(",
    "def add_policy_outcome(",
    "def seal_policy(",
    "def register_evidence(",
    "def create_request(",
    "def resolve_request(",
    "def repair_request(",
    "def expire_request(",
    "def get_attestation(",
    "def get_verdict(",
]
for marker in required:
    require(marker in source, f"missing required surface: {marker}")

forbidden = [
    "@gl.public.write.payable",
    "gl.get_contract_at(",
    ".emit(",
    "root.upgraders",
    "root.code",
    "self.balance",
    "transfer(",
]
for marker in forbidden:
    require(marker not in source, f"forbidden v1 surface: {marker}")

require(
    "gl.message.sender_address != expected_address" in source,
    "evidence registration is not bound to the approved authority address",
)
require(
    '"ONLY_APPROVED_AUTHORITY"' in source,
    "approved authority enforcement missing",
)
require(
    '"LINEAGE_AUTHORITY_MISMATCH"' in source,
    "authority lineage lock missing",
)
require(
    '"LINEAGE_ORIGIN_MISMATCH"' in source,
    "origin lineage lock missing",
)

require(
    "validator_result = evaluate()" in source,
    "validator does not independently rerun evaluation",
)
require(
    "gl.vm.run_nondet_unsafe(" in source,
    "custom nondeterministic consensus missing",
)
for field in ("kind", "outcome", "failure_code", "bundle_digest"):
    require(
        f'leader_data.get("{field}")' in source,
        f"leader field not compared: {field}",
    )
    require(
        f'validator_result.get("{field}")' in source,
        f"validator field not compared: {field}",
    )

require(
    source.count("gl.nondet.web.get(") == 1,
    "unexpected web-fetch surface",
)
require(
    source.count("gl.nondet.exec_prompt(") == 1,
    "unexpected LLM surface",
)
require(
    'response_format="json"' in source,
    "structured LLM response not enforced",
)
require(
    'STATUS_REPAIR_REQUIRED = "REPAIR_REQUIRED"' in source,
    "repair state missing",
)
require(
    'STATUS_EXPIRED = "EXPIRED"' in source,
    "expiry state missing",
)
require(
    '"REPAIR_MUST_CHANGE_EVIDENCE"' in source,
    "repair must change evidence bundle",
)
require(
    '"REQUEST_DEADLINE_NOT_REACHED"' in source,
    "deadline expiry guard missing",
)
require(
    "hashlib.sha256(body).hexdigest()" in source,
    "raw source SHA-256 verification missing",
)
require(
    "if body is None:" in source,
    "optional web response body is not handled fail-closed",
)
require(
    "if not isinstance(result, dict):" in source,
    "consensus result is not type-checked before use",
)
require(
    '"CONSENSUS_BUNDLE_DIGEST_MISMATCH"' in source,
    "post-consensus evidence-bundle binding missing",
)

print("EVIDENCEGATE_STAGE2_SOURCE_GUARDS=PASS")
