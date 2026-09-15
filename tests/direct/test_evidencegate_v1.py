import hashlib
import json
import re

from gltest.direct import create_address

NOW_ISO = "2026-09-15T12:00:00Z"
LATER_ISO = "2026-09-15T14:00:00Z"
NOW = 1_789_473_600
HOUR = 3600
DAY = 24 * HOUR
MAX_AGE = 30 * DAY
MIN_VALIDITY = HOUR
REQUEST_LIFETIME = 14 * DAY

CRITERIA = (
    "Return YES only when all supplied authoritative records explicitly confirm "
    "shipment 42 was delivered. Return NO only when all supplied authoritative "
    "records explicitly confirm it was not delivered. Otherwise require repair."
)
BODY_A = "Authority A record: shipment 42 was delivered."
BODY_B = "Authority B record: shipment 42 was delivered."


def _deploy(direct_vm, direct_deploy):
    direct_vm.check_pickling = True
    contract = direct_deploy("contracts/evidence_gate.py")
    owner = create_address("default_sender")
    direct_vm.sender = owner
    direct_vm.warp(NOW_ISO)
    return contract, owner


def _authorities():
    return [
        {
            "id": "authority-a",
            "address": create_address("evidencegate-authority-a"),
            "origin": "https://alpha.example.com",
        },
        {
            "id": "authority-b",
            "address": create_address("evidencegate-authority-b"),
            "origin": "https://beta.example.com",
        },
        {
            "id": "authority-c",
            "address": create_address("evidencegate-authority-c"),
            "origin": "https://gamma.example.com",
        },
    ]


def _create_policy(contract, slug="shipment-policy", **overrides):
    values = {
        "min_evidence": 2,
        "min_authorities": 2,
        "min_origins": 2,
        "max_age": MAX_AGE,
        "min_validity": MIN_VALIDITY,
        "max_lifetime": REQUEST_LIFETIME,
        "max_evidence": 4,
    }
    values.update(overrides)
    return contract.create_policy(
        slug,
        1,
        CRITERIA,
        values["min_evidence"],
        values["min_authorities"],
        values["min_origins"],
        values["max_age"],
        values["min_validity"],
        values["max_lifetime"],
        values["max_evidence"],
    )


def _seal_standard(direct_vm, contract, owner, slug="shipment-policy"):
    direct_vm.sender = owner
    policy_id = _create_policy(contract, slug)
    authorities = _authorities()
    for authority in authorities[:2]:
        contract.add_policy_authority(
            policy_id,
            authority["id"],
            authority["address"].as_hex,
            authority["origin"],
        )
    contract.add_policy_outcome(policy_id, "NO")
    contract.add_policy_outcome(policy_id, "YES")
    fingerprint = contract.seal_policy(policy_id)
    return policy_id, authorities, fingerprint


def _register(
    direct_vm,
    contract,
    policy_id,
    authority,
    stable_id,
    body,
    version=1,
    url=None,
    published_at=NOW - HOUR,
    expires_at=NOW + (10 * DAY),
):
    if url is None:
        url = authority["origin"] + "/records/" + stable_id
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    direct_vm.sender = authority["address"]
    evidence_id = contract.register_evidence(
        policy_id,
        stable_id,
        version,
        authority["id"],
        url,
        digest,
        published_at,
        expires_at,
    )
    return {
        "evidence_id": evidence_id,
        "stable_id": stable_id,
        "authority": authority,
        "authority_id": authority["id"],
        "url": url,
        "body": body,
        "digest": digest,
    }


def _setup(direct_vm, contract, owner):
    policy_id, authorities, fingerprint = _seal_standard(
        direct_vm, contract, owner
    )
    records = [
        _register(
            direct_vm,
            contract,
            policy_id,
            authorities[0],
            "record-a",
            BODY_A,
        ),
        _register(
            direct_vm,
            contract,
            policy_id,
            authorities[1],
            "record-b",
            BODY_B,
        ),
    ]
    records.sort(key=lambda item: item["evidence_id"])
    direct_vm.sender = owner
    return policy_id, authorities, records, fingerprint


def _bundle(records):
    return ",".join(sorted(item["evidence_id"] for item in records))


def _request(
    direct_vm,
    contract,
    owner,
    policy_id,
    records,
    claim_key="shipment-42",
    deadline=NOW + DAY,
):
    direct_vm.sender = owner
    return contract.create_request(
        policy_id,
        claim_key,
        "Was shipment 42 delivered?",
        _bundle(records),
        deadline,
    )


def _mock_web(direct_vm, records, body_overrides=None, status_overrides=None):
    body_overrides = body_overrides or {}
    status_overrides = status_overrides or {}
    for record in records:
        evidence_id = record["evidence_id"]
        direct_vm.mock_web(
            re.escape(record["url"]),
            {
                "status": status_overrides.get(evidence_id, 200),
                "body": body_overrides.get(evidence_id, record["body"]),
            },
        )


def _mock_llm(direct_vm, contract, request_id, kind, outcome, failure_code):
    request = contract.get_request(request_id)
    direct_vm.mock_llm(
        r"(?s).*EvidenceGate evaluator.*",
        json.dumps(
            {
                "kind": kind,
                "outcome": outcome,
                "failure_code": failure_code,
                "bundle_digest": request.evidence_bundle_digest,
            }
        ),
    )


def _no_attestation(direct_vm, contract, request_id):
    with direct_vm.expect_revert("ATTESTATION_NOT_FOUND"):
        contract.get_attestation(request_id)


def test_policy_identity_immutability_and_counts(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, authorities, fingerprint = _seal_standard(
        direct_vm, contract, owner
    )
    policy = contract.get_policy(policy_id)
    assert policy.sealed is True
    assert policy.fingerprint == fingerprint
    assert len(fingerprint) == 64
    assert int(policy.authority_count) == 2
    assert int(policy.origin_count) == 2
    assert policy.outcomes_csv == "NO,YES"
    assert contract.derive_policy_id(
        owner.as_hex, "shipment-policy", 1
    ) == policy_id
    with direct_vm.expect_revert("POLICY_SEALED"):
        contract.add_policy_authority(
            policy_id,
            "authority-c",
            authorities[2]["address"].as_hex,
            authorities[2]["origin"],
        )
    with direct_vm.expect_revert("POLICY_SEALED"):
        contract.add_policy_outcome(policy_id, "ZZZ")


def test_authority_address_uniqueness_owner_and_origin_diversity(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    authorities = _authorities()
    policy_id = _create_policy(contract, "authority-hardening")
    outsider = create_address("evidencegate-outsider")

    direct_vm.sender = outsider
    with direct_vm.expect_revert("ONLY_POLICY_OWNER"):
        contract.add_policy_authority(
            policy_id,
            "authority-a",
            authorities[0]["address"].as_hex,
            authorities[0]["origin"],
        )

    direct_vm.sender = owner
    contract.add_policy_authority(
        policy_id,
        "authority-a",
        authorities[0]["address"].as_hex,
        authorities[0]["origin"],
    )
    with direct_vm.expect_revert("DUPLICATE_AUTHORITY_ADDRESS"):
        contract.add_policy_authority(
            policy_id,
            "authority-b",
            authorities[0]["address"].as_hex,
            authorities[1]["origin"],
        )

    contract.add_policy_authority(
        policy_id,
        "authority-b",
        authorities[1]["address"].as_hex,
        authorities[0]["origin"],
    )
    contract.add_policy_outcome(policy_id, "NO")
    contract.add_policy_outcome(policy_id, "YES")
    with direct_vm.expect_revert("INSUFFICIENT_POLICY_ORIGINS"):
        contract.seal_policy(policy_id)


def test_policy_bounds_and_sorted_outcomes(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    with direct_vm.expect_revert("MIN_EVIDENCE_BELOW_TWO"):
        _create_policy(contract, "bad-evidence", min_evidence=1)
    with direct_vm.expect_revert("MIN_AUTHORITIES_BELOW_TWO"):
        _create_policy(contract, "bad-authority", min_authorities=1)
    with direct_vm.expect_revert("MIN_ORIGINS_BELOW_TWO"):
        _create_policy(contract, "bad-origin", min_origins=1)
    with direct_vm.expect_revert("INVALID_MAX_EVIDENCE_RECORDS"):
        _create_policy(contract, "bad-max", max_evidence=7)

    policy_id = _create_policy(contract, "outcome-order")
    authorities = _authorities()
    for authority in authorities[:2]:
        contract.add_policy_authority(
            policy_id,
            authority["id"],
            authority["address"].as_hex,
            authority["origin"],
        )
    contract.add_policy_outcome(policy_id, "YES")
    with direct_vm.expect_revert("OUTCOMES_NOT_STRICTLY_SORTED"):
        contract.add_policy_outcome(policy_id, "NO")


def test_evidence_requires_bound_authority_origin_and_lineage(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, authorities, _ = _seal_standard(direct_vm, contract, owner)
    digest = hashlib.sha256(BODY_A.encode()).hexdigest()

    direct_vm.sender = owner
    with direct_vm.expect_revert("ONLY_APPROVED_AUTHORITY"):
        contract.register_evidence(
            policy_id,
            "spoof",
            1,
            authorities[0]["id"],
            authorities[0]["origin"] + "/records/spoof",
            digest,
            NOW - HOUR,
            NOW + (10 * DAY),
        )

    direct_vm.sender = authorities[0]["address"]
    with direct_vm.expect_revert("SOURCE_ORIGIN_MISMATCH"):
        contract.register_evidence(
            policy_id,
            "wrong-origin",
            1,
            authorities[0]["id"],
            authorities[1]["origin"] + "/records/wrong",
            digest,
            NOW - HOUR,
            NOW + (10 * DAY),
        )

    _register(
        direct_vm,
        contract,
        policy_id,
        authorities[0],
        "lineage",
        BODY_A,
    )
    direct_vm.sender = authorities[1]["address"]
    with direct_vm.expect_revert("LINEAGE_AUTHORITY_MISMATCH"):
        contract.register_evidence(
            policy_id,
            "lineage",
            2,
            authorities[1]["id"],
            authorities[1]["origin"] + "/records/lineage-v2",
            hashlib.sha256(BODY_B.encode()).hexdigest(),
            NOW - HOUR,
            NOW + (10 * DAY),
        )


def test_evidence_freshness_boundaries(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, authorities, _ = _seal_standard(direct_vm, contract, owner)
    authority = authorities[0]
    digest = hashlib.sha256(BODY_A.encode()).hexdigest()
    direct_vm.sender = authority["address"]

    cases = [
        (
            "future",
            NOW + 1,
            NOW + DAY,
            "EVIDENCE_PUBLISHED_IN_FUTURE",
        ),
        (
            "stale",
            NOW - MAX_AGE - 1,
            NOW + DAY,
            "EVIDENCE_TOO_OLD",
        ),
        (
            "expired",
            NOW - HOUR,
            NOW - 1,
            "EVIDENCE_EXPIRED",
        ),
        (
            "short",
            NOW - HOUR,
            NOW + MIN_VALIDITY - 1,
            "EVIDENCE_INSUFFICIENT_REMAINING_VALIDITY",
        ),
    ]
    for stable_id, published, expires, error in cases:
        with direct_vm.expect_revert(error):
            contract.register_evidence(
                policy_id,
                stable_id,
                1,
                authority["id"],
                authority["origin"] + "/records/" + stable_id,
                digest,
                published,
                expires,
            )


def test_request_bundle_and_deadline_guards(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, authorities, records, _ = _setup(
        direct_vm, contract, owner
    )
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    assert contract.get_request(request_id).status == "OPEN"

    descending = ",".join(
        reversed(sorted(item["evidence_id"] for item in records))
    )
    with direct_vm.expect_revert("INVALID_EVIDENCE_BUNDLE"):
        contract.create_request(
            policy_id,
            "unsorted",
            "Was shipment 42 delivered?",
            descending,
            NOW + DAY,
        )
    with direct_vm.expect_revert("INSUFFICIENT_EVIDENCE_RECORDS"):
        contract.create_request(
            policy_id,
            "single",
            "Was shipment 42 delivered?",
            records[0]["evidence_id"],
            NOW + DAY,
        )
    with direct_vm.expect_revert("REQUEST_LIFETIME_TOO_LONG"):
        contract.create_request(
            policy_id,
            "too-long",
            "Was shipment 42 delivered?",
            _bundle(records),
            NOW + REQUEST_LIFETIME + 1,
        )
    with direct_vm.expect_revert("EVIDENCE_VALIDITY_ENDS_BEFORE_DEADLINE"):
        contract.create_request(
            policy_id,
            "after-expiry",
            "Was shipment 42 delivered?",
            _bundle(records),
            NOW + (11 * DAY),
        )

    first_a = next(
        item for item in records
        if item["authority_id"] == authorities[0]["id"]
    )
    extra = _register(
        direct_vm,
        contract,
        policy_id,
        authorities[0],
        "record-a-extra",
        BODY_A + " extra",
    )
    direct_vm.sender = owner
    with direct_vm.expect_revert("INSUFFICIENT_DISTINCT_AUTHORITIES"):
        contract.create_request(
            policy_id,
            "same-authority",
            "Was shipment 42 delivered?",
            _bundle([first_a, extra]),
            NOW + DAY,
        )


def _resolved_case(direct_vm, direct_deploy, outcome):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, fingerprint = _setup(
        direct_vm, contract, owner
    )
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm,
        contract,
        request_id,
        "RESOLVED",
        outcome,
        "",
    )
    assert contract.resolve_request(request_id) == outcome
    request = contract.get_request(request_id)
    attestation = contract.get_attestation(request_id)
    assert request.status == "RESOLVED"
    assert request.outcome == outcome
    assert request.failure_code == ""
    assert attestation.outcome == outcome
    assert attestation.policy_fingerprint == fingerprint
    assert int(attestation.evidence_count) == 2
    assert int(attestation.distinct_authority_count) == 2
    assert int(attestation.distinct_origin_count) == 2
    assert direct_vm.run_validator() is True
    return contract, owner, records, request_id


def test_exact_yes_resolution(direct_vm, direct_deploy):
    _resolved_case(direct_vm, direct_deploy, "YES")


def test_exact_no_resolution(direct_vm, direct_deploy):
    _resolved_case(direct_vm, direct_deploy, "NO")


def test_validator_disagreement_is_detectable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm, contract, request_id, "RESOLVED", "YES", ""
    )
    assert contract.resolve_request(request_id) == "YES"

    direct_vm.clear_mocks()
    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm, contract, request_id, "RESOLVED", "NO", ""
    )
    assert direct_vm.run_validator() is False


def test_digest_mismatch_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        body_overrides={
            target["evidence_id"]: target["body"] + " tampered"
        },
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    request = contract.get_request(request_id)
    assert request.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert request.outcome == ""
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_non_200_status_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        status_overrides={target["evidence_id"]: 404},
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    request = contract.get_request(request_id)
    assert request.failure_code == "SOURCE_HTTP_STATUS_NOT_OK"
    assert request.outcome == ""
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_conflicting_evidence_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm,
        contract,
        request_id,
        "REPAIR_REQUIRED",
        "",
        "CONFLICTING_OR_INSUFFICIENT_EVIDENCE",
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    request = contract.get_request(request_id)
    assert (
        request.failure_code
        == "CONFLICTING_OR_INSUFFICIENT_EVIDENCE"
    )
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_newer_evidence_forces_repair_then_resolves(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    target = records[0]
    replacement = _register(
        direct_vm,
        contract,
        policy_id,
        target["authority"],
        target["stable_id"],
        target["body"] + " version 2",
        version=2,
        url=target["url"] + "/v2",
    )

    direct_vm.sender = owner
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    assert (
        contract.get_request(request_id).failure_code
        == "EVIDENCE_NOT_LATEST_VERSION"
    )

    other = next(
        item for item in records
        if item["evidence_id"] != target["evidence_id"]
    )
    repaired_records = [replacement, other]
    contract.repair_request(request_id, _bundle(repaired_records))
    repaired = contract.get_request(request_id)
    assert repaired.status == "OPEN"
    assert int(repaired.repair_count) == 1

    _mock_web(direct_vm, repaired_records)
    _mock_llm(
        direct_vm, contract, request_id, "RESOLVED", "YES", ""
    )
    assert contract.resolve_request(request_id) == "YES"
    assert contract.get_attestation(request_id).outcome == "YES"
    assert direct_vm.run_validator() is True


def test_repair_is_requester_only_and_must_change_bundle(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        body_overrides={
            target["evidence_id"]: target["body"] + " changed"
        },
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    current_bundle = contract.get_request(request_id).evidence_ids_csv

    direct_vm.sender = create_address("not-requester")
    with direct_vm.expect_revert("ONLY_REQUESTER"):
        contract.repair_request(request_id, current_bundle)

    direct_vm.sender = owner
    with direct_vm.expect_revert("REPAIR_MUST_CHANGE_EVIDENCE"):
        contract.repair_request(request_id, current_bundle)


def test_expiry_and_resolved_terminality(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm,
        contract,
        owner,
        policy_id,
        records,
        claim_key="expiry-path",
        deadline=NOW + HOUR,
    )
    direct_vm.warp(LATER_ISO)
    contract.expire_request(request_id)
    request = contract.get_request(request_id)
    assert request.status == "EXPIRED"
    assert request.failure_code == "REQUEST_DEADLINE_REACHED"
    _no_attestation(direct_vm, contract, request_id)
    with direct_vm.expect_revert("REQUEST_NOT_OPEN"):
        contract.resolve_request(request_id)
    with direct_vm.expect_revert("REQUEST_NOT_EXPIRABLE"):
        contract.expire_request(request_id)

    second_id = _request(
        direct_vm,
        contract,
        owner,
        policy_id,
        records,
        claim_key="resolved-terminal",
    )
    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm, contract, second_id, "RESOLVED", "YES", ""
    )
    assert contract.resolve_request(second_id) == "YES"
    with direct_vm.expect_revert("REQUEST_NOT_OPEN"):
        contract.resolve_request(second_id)
    with direct_vm.expect_revert("REQUEST_NOT_EXPIRABLE"):
        contract.expire_request(second_id)
    with direct_vm.expect_revert("REQUEST_NOT_REPAIRABLE"):
        contract.repair_request(second_id, _bundle(records))

def test_missing_web_mock_is_repairable_fetch_failure(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )

    first = records[0]
    direct_vm.mock_web(
        re.escape(first["url"]),
        {
            "status": 200,
            "body": first["body"],
        },
    )

    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    request = contract.get_request(request_id)
    assert request.status == "REPAIR_REQUIRED"
    assert request.failure_code == "SOURCE_FETCH_FAILED"
    assert request.outcome == ""
    _no_attestation(direct_vm, contract, request_id)


def test_oversized_source_is_repairable(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )

    target = records[0]
    _mock_web(
        direct_vm,
        records,
        body_overrides={
            target["evidence_id"]: "X" * 65537
        },
    )

    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    request = contract.get_request(request_id)
    assert request.failure_code == "SOURCE_TOO_LARGE"
    assert request.outcome == ""
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_invalid_llm_outcome_cannot_mutate_request(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )

    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm,
        contract,
        request_id,
        "RESOLVED",
        "MAYBE",
        "",
    )

    with direct_vm.expect_revert("LLM_OUTCOME_NOT_ALLOWED"):
        contract.resolve_request(request_id)

    request = contract.get_request(request_id)
    assert request.status == "OPEN"
    assert request.outcome == ""
    assert request.failure_code == ""
    _no_attestation(direct_vm, contract, request_id)


def test_llm_cannot_rebind_evidence_bundle(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )

    _mock_web(direct_vm, records)
    direct_vm.mock_llm(
        r"(?s).*EvidenceGate evaluator.*",
        json.dumps(
            {
                "kind": "RESOLVED",
                "outcome": "YES",
                "failure_code": "",
                "bundle_digest": "0" * 64,
            }
        ),
    )

    with direct_vm.expect_revert("LLM_BUNDLE_DIGEST_MISMATCH"):
        contract.resolve_request(request_id)

    request = contract.get_request(request_id)
    assert request.status == "OPEN"
    assert request.outcome == ""
    assert request.failure_code == ""
    _no_attestation(direct_vm, contract, request_id)

def test_origin_and_reserved_outcome_hardening(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    direct_vm.sender = owner
    policy_id = _create_policy(
        contract,
        "origin-outcome-hardening",
    )
    authority = _authorities()[0]

    with direct_vm.expect_revert(
        "ORIGIN_IP_LITERAL_NOT_ALLOWED"
    ):
        contract.add_policy_authority(
            policy_id,
            authority["id"],
            authority["address"].as_hex,
            "https://127.0.0.1",
        )

    with direct_vm.expect_revert(
        "ORIGIN_INVALID_HOST"
    ):
        contract.add_policy_authority(
            policy_id,
            authority["id"],
            authority["address"].as_hex,
            "https://bad.-label.com",
        )

    with direct_vm.expect_revert(
        "OUTCOME_RESERVED"
    ):
        contract.add_policy_outcome(
            policy_id,
            "RESOLVED",
        )


def test_effective_validity_horizon_and_currentness(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    direct_vm.sender = owner

    policy_id = _create_policy(
        contract,
        "short-freshness",
        max_age=60,
        min_validity=1,
        max_lifetime=300,
    )
    authorities = _authorities()

    for authority in authorities[:2]:
        contract.add_policy_authority(
            policy_id,
            authority["id"],
            authority["address"].as_hex,
            authority["origin"],
        )

    contract.add_policy_outcome(policy_id, "NO")
    contract.add_policy_outcome(policy_id, "YES")
    contract.seal_policy(policy_id)

    records = [
        _register(
            direct_vm,
            contract,
            policy_id,
            authorities[0],
            "freshness-a",
            BODY_A,
            published_at=NOW,
            expires_at=NOW + DAY,
        ),
        _register(
            direct_vm,
            contract,
            policy_id,
            authorities[1],
            "freshness-b",
            BODY_B,
            published_at=NOW,
            expires_at=NOW + DAY,
        ),
    ]
    records.sort(key=lambda item: item["evidence_id"])

    direct_vm.sender = owner

    with direct_vm.expect_revert(
        "EVIDENCE_VALIDITY_ENDS_BEFORE_DEADLINE"
    ):
        contract.create_request(
            policy_id,
            "too-close-to-stale",
            "Was shipment 42 delivered?",
            _bundle(records),
            NOW + 61,
        )

    request_id = contract.create_request(
        policy_id,
        "freshness-currentness",
        "Was shipment 42 delivered?",
        _bundle(records),
        NOW + 30,
    )

    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm,
        contract,
        request_id,
        "RESOLVED",
        "YES",
        "",
    )

    assert contract.resolve_request(request_id) == "YES"
    attestation = contract.get_attestation(request_id)
    assert int(attestation.valid_until) == NOW + 61
    assert contract.is_attestation_current(request_id) is True

    direct_vm.warp("2026-09-15T12:01:01Z")
    assert contract.is_attestation_current(request_id) is False


def test_attestation_becomes_noncurrent_after_lineage_advance(
    direct_vm, direct_deploy
):
    contract, owner, records, request_id = _resolved_case(
        direct_vm,
        direct_deploy,
        "YES",
    )

    assert contract.is_attestation_current(request_id) is True

    target = records[0]
    _register(
        direct_vm,
        contract,
        contract.get_request(request_id).policy_id,
        target["authority"],
        target["stable_id"],
        target["body"] + " superseding version",
        version=2,
        url=target["url"] + "/v2",
    )

    assert contract.is_attestation_current(request_id) is False
    assert contract.get_attestation(request_id).outcome == "YES"


def test_llm_result_rejects_extra_fields(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records, _ = _setup(direct_vm, contract, owner)
    request_id = _request(
        direct_vm, contract, owner, policy_id, records
    )

    _mock_web(direct_vm, records)
    request = contract.get_request(request_id)

    direct_vm.mock_llm(
        r"(?s).*EvidenceGate evaluator.*",
        json.dumps(
            {
                "kind": "RESOLVED",
                "outcome": "YES",
                "failure_code": "",
                "bundle_digest": request.evidence_bundle_digest,
                "explanation": "must not enter consensus",
            }
        ),
    )

    with direct_vm.expect_revert(
        "LLM_RESULT_SCHEMA_MISMATCH"
    ):
        contract.resolve_request(request_id)

    request = contract.get_request(request_id)
    assert request.status == "OPEN"
    assert request.outcome == ""
    assert request.failure_code == ""
    _no_attestation(direct_vm, contract, request_id)
