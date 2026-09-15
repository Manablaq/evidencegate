from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "evidence_gate.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


source = CONTRACT.read_text(encoding="utf-8")
tree = ast.parse(source)

contract = next(
    node
    for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name == "EvidenceGate"
)

public = set()
for node in contract.body:
    if not isinstance(node, ast.FunctionDef):
        continue
    for decorator in node.decorator_list:
        rendered = ast.unparse(decorator)
        if rendered in ("gl.public.view", "gl.public.write"):
            public.add((node.name, rendered))
            break

expected_public = {
    ("get_policy", "gl.public.view"),
    ("get_evidence", "gl.public.view"),
    ("get_request", "gl.public.view"),
    ("get_attestation", "gl.public.view"),
    ("get_verdict", "gl.public.view"),
    ("is_attestation_current", "gl.public.view"),
    ("create_policy", "gl.public.write"),
    ("register_evidence", "gl.public.write"),
    ("create_request", "gl.public.write"),
    ("resolve_request", "gl.public.write"),
    ("repair_request", "gl.public.write"),
    ("expire_request", "gl.public.write"),
}
require(public == expected_public, f"unexpected public API: {sorted(public)!r}")

required = [
    'evidencegate-sealed-policy-v1',
    'evidencegate-evidence-v1',
    'evidencegate-evidence-bundle-v1',
    'evidencegate-request-v1',
    'evidencegate-claim-v1',
    '"DUPLICATE_AUTHORITY_ADDRESS"',
    '"INSUFFICIENT_POLICY_DIVERSITY"',
    '"SOURCE_URL_FRAGMENT_NOT_ALLOWED"',
    '"LINEAGE_AUTHORITY_MISMATCH"',
    '"LINEAGE_ORIGIN_MISMATCH"',
    '"EVIDENCE_NOT_LATEST_VERSION"',
    '"SOURCE_HTTP_STATUS_NOT_OK"',
    '"SOURCE_BUNDLE_TOO_LARGE"',
    '"SOURCE_DIGEST_MISMATCH"',
    '"SOURCE_NOT_UTF8"',
    '"CONFLICTING_OR_INSUFFICIENT_EVIDENCE"',
    '"LLM_RESULT_SCHEMA_MISMATCH"',
    '"LLM_RESULT_INVALID"',
    '"LLM_OUTCOME_NOT_ALLOWED"',
    '"CONSENSUS_RESULT_NOT_OBJECT"',
    '"CONSENSUS_BUNDLE_DIGEST_MISMATCH"',
    '"CONSENSUS_REPAIR_CODE_NOT_ALLOWED"',
    '"CONSENSUS_INVALID_RESOLUTION"',
    '"REPAIR_MUST_CHANGE_EVIDENCE"',
    '"REQUEST_DEADLINE_REACHED"',
    '"REQUEST_DEADLINE_NOT_REACHED"',
    '"EVIDENCE_VALIDITY_ENDS_BEFORE_DEADLINE"',
    "def is_attestation_current(",
    "gl.vm.run_nondet_unsafe(",
    "gl.nondet.web.request(",
    'method="GET"',
    "w.status!=200",
    "w.body",
    "hashlib.sha256(x).hexdigest()",
    "gl.nondet.exec_prompt(",
    'response_format="json"',
    "gl.storage.copy_to_memory(",
]
for marker in required:
    require(marker in source, f"missing security surface: {marker}")

require(
    source.count("gl.nondet.web.request(") == 1,
    "unexpected nondeterministic web-request count",
)
require(
    source.count("gl.nondet.exec_prompt(") == 1,
    "unexpected nondeterministic LLM-call count",
)
require(
    "response.status_code" not in source,
    "incompatible response.status_code surface present",
)
require(
    'if not isinstance(x,dict):raise gl.vm.UserError("CONSENSUS_RESULT_NOT_OBJECT")'
    in source,
    "consensus return is not explicitly type-narrowed",
)

# Atomic policy construction replaces a partially configured mutable policy.
create_policy = next(
    node
    for node in contract.body
    if isinstance(node, ast.FunctionDef) and node.name == "create_policy"
)
create_args = [arg.arg for arg in create_policy.args.args]
for name in (
    "authority_ids_csv",
    "authority_addresses_csv",
    "publisher_origins_csv",
    "outcomes_csv",
):
    require(name in create_args, f"atomic policy binding missing argument: {name}")

for removed in (
    "def add_policy_authority(",
    "def add_policy_outcome(",
    "def seal_policy(",
):
    require(removed not in source, f"obsolete mutable-policy surface present: {removed}")

for forbidden in (
    "@gl.public.write.payable",
    "gl.message.value",
    "gl.get_contract_at(",
    "ContractAt(",
    "InternalContract(",
    ".emit(",
    "root.upgraders",
    "root.code",
    "self.balance",
    "transfer(",
    "exec(",
    "eval(",
):
    require(forbidden not in source, f"forbidden v1 surface: {forbidden}")

# The compact design must keep both a per-source and whole-bundle byte bound.
require("MS=65536" in source, "per-source body limit changed")
require("MB=131072" in source, "global source bundle limit changed")
require(
    "total+=len(x)" in source and "if total>MB:" in source,
    "global source budget is not enforced in evaluator",
)

print("EVIDENCEGATE_COMPACT_SOURCE_GUARDS=PASS")


def test_source_guards_module_checks() -> None:
    """Make this guard module directly collectible by pytest."""
    assert True
