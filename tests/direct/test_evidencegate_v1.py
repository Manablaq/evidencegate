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


def _deploy(vm, deploy):
    vm.check_pickling = True
    contract = deploy("contracts/evidence_gate.py")
    owner = create_address("default_sender")
    vm.sender = owner
    vm.warp(NOW_ISO)
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


def _create_policy(
    vm,
    contract,
    owner,
    slug="shipment-policy",
    *,
    authority_count=2,
    outcomes="NO,YES",
    min_evidence=2,
    min_authorities=2,
    min_origins=2,
    max_age=MAX_AGE,
    min_validity=MIN_VALIDITY,
    max_lifetime=REQUEST_LIFETIME,
    max_evidence=4,
    ids=None,
    addresses=None,
    origins=None,
):
    auth = _authorities()[:authority_count]
    ids = ids if ids is not None else ",".join(x["id"] for x in auth)
    addresses = (
        addresses
        if addresses is not None
        else ",".join(x["address"].as_hex for x in auth)
    )
    origins = (
        origins
        if origins is not None
        else ",".join(x["origin"] for x in auth)
    )
    vm.sender = owner
    return contract.create_policy(
        slug,
        1,
        CRITERIA,
        ids,
        addresses,
        origins,
        outcomes,
        min_evidence,
        min_authorities,
        min_origins,
        max_age,
        min_validity,
        max_lifetime,
        max_evidence,
    )


def _register(
    vm,
    contract,
    policy_id,
    authority,
    stable_id,
    body,
    *,
    version=1,
    url=None,
    published_at=NOW - HOUR,
    expires_at=NOW + (10 * DAY),
):
    if url is None:
        url = authority["origin"] + "/records/" + stable_id
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    vm.sender = authority["address"]
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


def _setup(vm, contract, owner):
    authorities = _authorities()
    policy_id = _create_policy(vm, contract, owner)
    records = [
        _register(
            vm,
            contract,
            policy_id,
            authorities[0],
            "record-a",
            BODY_A,
        ),
        _register(
            vm,
            contract,
            policy_id,
            authorities[1],
            "record-b",
            BODY_B,
        ),
    ]
    records.sort(key=lambda item: item["evidence_id"])
    vm.sender = owner
    return policy_id, authorities, records


def _bundle(records):
    return ",".join(sorted(item["evidence_id"] for item in records))


def _request(
    vm,
    contract,
    owner,
    policy_id,
    records,
    claim_key="shipment-42",
    deadline=NOW + DAY,
):
    vm.sender = owner
    return contract.create_request(
        policy_id,
        claim_key,
        "Was shipment 42 delivered?",
        _bundle(records),
        deadline,
    )


def _mock_web(vm, records, body_overrides=None, status_overrides=None):
    body_overrides = body_overrides or {}
    status_overrides = status_overrides or {}
    for record in records:
        eid = record["evidence_id"]
        vm.mock_web(
            re.escape(record["url"]),
            {
                "status": status_overrides.get(eid, 200),
                "body": body_overrides.get(eid, record["body"]),
            },
        )


def _mock_llm(vm, contract, request_id, kind, outcome, failure_code, **extra):
    request = contract.get_request(request_id)
    payload = {
        "kind": kind,
        "outcome": outcome,
        "failure_code": failure_code,
        "bundle_digest": request.evidence_bundle_digest,
    }
    payload.update(extra)
    vm.mock_llm(r"(?s).*EvidenceGate evaluator.*", json.dumps(payload))


def _no_attestation(vm, contract, request_id):
    with vm.expect_revert("ATTESTATION_NOT_FOUND"):
        contract.get_attestation(request_id)


def _resolved_case(vm, deploy, outcome):
    contract, owner = _deploy(vm, deploy)
    policy_id, _, records = _setup(vm, contract, owner)
    request_id = _request(vm, contract, owner, policy_id, records)
    _mock_web(vm, records)
    _mock_llm(vm, contract, request_id, "RESOLVED", outcome, "")
    assert contract.resolve_request(request_id) == outcome
    request = contract.get_request(request_id)
    attestation = contract.get_attestation(request_id)
    policy = contract.get_policy(policy_id)
    assert request.status == "RESOLVED"
    assert request.outcome == outcome
    assert request.failure_code == ""
    assert attestation.outcome == outcome
    assert attestation.policy_fingerprint == policy.fingerprint
    assert int(attestation.evidence_count) == 2
    assert int(attestation.distinct_authority_count) == 2
    assert int(attestation.distinct_origin_count) == 2
    assert vm.run_validator() is True
    assert contract.is_attestation_current(request_id) is True
    return contract, owner, policy_id, records, request_id


def test_atomic_policy_identity_and_immutability(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id = _create_policy(direct_vm, contract, owner)
    policy = contract.get_policy(policy_id)
    assert policy.owner == owner
    assert policy.outcomes_csv == "NO,YES"
    assert len(policy.fingerprint) == 64
    assert not hasattr(contract, "add_policy_authority")
    assert not hasattr(contract, "add_policy_outcome")
    assert not hasattr(contract, "seal_policy")
    with direct_vm.expect_revert("POLICY_ALREADY_EXISTS"):
        _create_policy(direct_vm, contract, owner)


def test_policy_rejects_duplicate_authority_address(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    a = _authorities()
    addresses = a[0]["address"].as_hex + "," + a[0]["address"].as_hex
    with direct_vm.expect_revert("DUPLICATE_AUTHORITY_ADDRESS"):
        _create_policy(
            direct_vm,
            contract,
            owner,
            slug="duplicate-address",
            addresses=addresses,
        )


def test_policy_requires_distinct_origins(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    origin = _authorities()[0]["origin"]
    with direct_vm.expect_revert("INSUFFICIENT_POLICY_DIVERSITY"):
        _create_policy(
            direct_vm,
            contract,
            owner,
            slug="origin-diversity",
            origins=origin + "," + origin,
        )


def test_policy_bounds_sorted_and_reserved_outcomes(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    with direct_vm.expect_revert("MIN_EVIDENCE_BELOW_TWO"):
        _create_policy(
            direct_vm,
            contract,
            owner,
            slug="bad-evidence",
            min_evidence=1,
        )
    with direct_vm.expect_revert("INVALID_MAX_EVIDENCE_RECORDS"):
        _create_policy(
            direct_vm,
            contract,
            owner,
            slug="bad-max",
            max_evidence=7,
        )
    with direct_vm.expect_revert("OUTCOMES_NOT_STRICTLY_SORTED"):
        _create_policy(
            direct_vm,
            contract,
            owner,
            slug="bad-order",
            outcomes="YES,NO",
        )
    with direct_vm.expect_revert("OUTCOME_RESERVED"):
        _create_policy(
            direct_vm,
            contract,
            owner,
            slug="reserved",
            outcomes="OPEN,YES",
        )


def test_origin_canonicalization_hardening(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    a = _authorities()
    bad_origins = [
        "https://127.0.0.1",
        "https://UPPER.example.com",
        "https://alpha.example.com:443",
        "https://" + ("a" * 64) + ".example.com",
    ]
    for index, origin in enumerate(bad_origins):
        with direct_vm.expect_revert():
            _create_policy(
                direct_vm,
                contract,
                owner,
                slug=f"bad-origin-{index}",
                origins=origin + "," + a[1]["origin"],
            )


def test_evidence_requires_approved_authority_sender(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id = _create_policy(direct_vm, contract, owner)
    authority = _authorities()[0]
    direct_vm.sender = owner
    digest = hashlib.sha256(BODY_A.encode()).hexdigest()
    with direct_vm.expect_revert("ONLY_APPROVED_AUTHORITY"):
        contract.register_evidence(
            policy_id,
            "spoof",
            1,
            authority["id"],
            authority["origin"] + "/records/spoof",
            digest,
            NOW - HOUR,
            NOW + (10 * DAY),
        )


def test_source_origin_and_fragment_guards(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id = _create_policy(direct_vm, contract, owner)
    a = _authorities()
    digest = hashlib.sha256(BODY_A.encode()).hexdigest()
    direct_vm.sender = a[0]["address"]
    with direct_vm.expect_revert("SOURCE_ORIGIN_MISMATCH"):
        contract.register_evidence(
            policy_id,
            "wrong-origin",
            1,
            a[0]["id"],
            a[1]["origin"] + "/records/wrong",
            digest,
            NOW - HOUR,
            NOW + (10 * DAY),
        )
    with direct_vm.expect_revert("SOURCE_URL_FRAGMENT_NOT_ALLOWED"):
        contract.register_evidence(
            policy_id,
            "fragment",
            1,
            a[0]["id"],
            a[0]["origin"] + "/records/fragment#section",
            digest,
            NOW - HOUR,
            NOW + (10 * DAY),
        )


def test_evidence_lineage_authority_cannot_change(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id = _create_policy(direct_vm, contract, owner)
    a = _authorities()
    _register(
        direct_vm,
        contract,
        policy_id,
        a[0],
        "lineage",
        BODY_A,
    )
    direct_vm.sender = a[1]["address"]
    with direct_vm.expect_revert("LINEAGE_AUTHORITY_MISMATCH"):
        contract.register_evidence(
            policy_id,
            "lineage",
            2,
            a[1]["id"],
            a[1]["origin"] + "/records/lineage-v2",
            hashlib.sha256(BODY_B.encode()).hexdigest(),
            NOW - HOUR,
            NOW + (10 * DAY),
        )


def test_evidence_freshness_boundaries(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id = _create_policy(direct_vm, contract, owner)
    authority = _authorities()[0]
    digest = hashlib.sha256(BODY_A.encode()).hexdigest()
    direct_vm.sender = authority["address"]
    cases = [
        ("future", NOW + 1, NOW + DAY, "EVIDENCE_PUBLISHED_IN_FUTURE"),
        ("stale", NOW - MAX_AGE - 1, NOW + DAY, "EVIDENCE_TOO_OLD"),
        ("expired", NOW - HOUR, NOW - 1, "EVIDENCE_EXPIRED"),
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


def test_evidence_version_must_strictly_increase(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id = _create_policy(direct_vm, contract, owner)
    authority = _authorities()[0]
    _register(
        direct_vm,
        contract,
        policy_id,
        authority,
        "versioned",
        BODY_A,
        version=1,
    )
    with direct_vm.expect_revert("VERSION_NOT_INCREASING"):
        _register(
            direct_vm,
            contract,
            policy_id,
            authority,
            "versioned",
            BODY_A,
            version=1,
        )


def test_request_bundle_deadline_and_diversity_guards(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, authorities, records = _setup(direct_vm, contract, owner)
    assert contract.get_request(
        _request(direct_vm, contract, owner, policy_id, records)
    ).status == "OPEN"
    descending = ",".join(
        reversed(sorted(item["evidence_id"] for item in records))
    )
    direct_vm.sender = owner
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
            "after-validity",
            "Was shipment 42 delivered?",
            _bundle(records),
            NOW + (11 * DAY),
        )
    extra = _register(
        direct_vm,
        contract,
        policy_id,
        authorities[0],
        "record-a-extra",
        BODY_A + " extra",
    )
    first_a = next(
        item
        for item in records
        if item["authority_id"] == authorities[0]["id"]
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


def test_exact_yes_resolution(direct_vm, direct_deploy):
    _resolved_case(direct_vm, direct_deploy, "YES")


def test_exact_no_resolution(direct_vm, direct_deploy):
    _resolved_case(direct_vm, direct_deploy, "NO")


def test_validator_disagreement_is_detected(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    _mock_web(direct_vm, records)
    _mock_llm(direct_vm, contract, request_id, "RESOLVED", "YES", "")
    assert contract.resolve_request(request_id) == "YES"
    direct_vm.clear_mocks()
    _mock_web(direct_vm, records)
    _mock_llm(direct_vm, contract, request_id, "RESOLVED", "NO", "")
    assert direct_vm.run_validator() is False


def test_digest_mismatch_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        {target["evidence_id"]: target["body"] + " tampered"},
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    assert contract.get_request(request_id).failure_code == "SOURCE_DIGEST_MISMATCH"
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_non_200_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        status_overrides={target["evidence_id"]: 404},
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    assert (
        contract.get_request(request_id).failure_code
        == "SOURCE_HTTP_STATUS_NOT_OK"
    )
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_missing_source_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    first = records[0]
    direct_vm.mock_web(
        re.escape(first["url"]),
        {"status": 200, "body": first["body"]},
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    assert contract.get_request(request_id).failure_code == "SOURCE_FETCH_FAILED"
    _no_attestation(direct_vm, contract, request_id)


def test_per_source_byte_limit_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        {target["evidence_id"]: "X" * 65537},
    )
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    assert contract.get_request(request_id).failure_code == "SOURCE_TOO_LARGE"
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_global_source_bundle_byte_limit_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    authorities = _authorities()
    policy_id = _create_policy(
        direct_vm,
        contract,
        owner,
        slug="bundle-budget",
        authority_count=3,
        min_evidence=3,
        min_authorities=3,
        min_origins=3,
    )
    body = "X" * 50000
    records = [
        _register(
            direct_vm,
            contract,
            policy_id,
            authorities[index],
            f"big-{index}",
            body,
        )
        for index in range(3)
    ]
    records.sort(key=lambda item: item["evidence_id"])
    request_id = _request(
        direct_vm,
        contract,
        owner,
        policy_id,
        records,
        claim_key="bundle-budget",
    )
    _mock_web(direct_vm, records)
    assert contract.resolve_request(request_id) == "REPAIR_REQUIRED"
    assert (
        contract.get_request(request_id).failure_code
        == "SOURCE_BUNDLE_TOO_LARGE"
    )
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_conflicting_evidence_is_repairable(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
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
    assert (
        contract.get_request(request_id).failure_code
        == "CONFLICTING_OR_INSUFFICIENT_EVIDENCE"
    )
    _no_attestation(direct_vm, contract, request_id)
    assert direct_vm.run_validator() is True


def test_invalid_llm_outcome_cannot_mutate_request(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    _mock_web(direct_vm, records)
    _mock_llm(direct_vm, contract, request_id, "RESOLVED", "MAYBE", "")
    with direct_vm.expect_revert("LLM_OUTCOME_NOT_ALLOWED"):
        contract.resolve_request(request_id)
    request = contract.get_request(request_id)
    assert request.status == "OPEN"
    assert request.outcome == ""
    assert request.failure_code == ""
    _no_attestation(direct_vm, contract, request_id)


def test_llm_cannot_rebind_evidence_bundle(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
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
    with direct_vm.expect_revert("LLM_RESULT_INVALID"):
        contract.resolve_request(request_id)
    assert contract.get_request(request_id).status == "OPEN"
    _no_attestation(direct_vm, contract, request_id)


def test_llm_extra_fields_are_rejected(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    _mock_web(direct_vm, records)
    _mock_llm(
        direct_vm,
        contract,
        request_id,
        "RESOLVED",
        "YES",
        "",
        extra="forbidden",
    )
    with direct_vm.expect_revert("LLM_RESULT_SCHEMA_MISMATCH"):
        contract.resolve_request(request_id)
    assert contract.get_request(request_id).status == "OPEN"
    _no_attestation(direct_vm, contract, request_id)


def test_newer_evidence_requires_repair_then_resolves(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
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
        item for item in records if item["evidence_id"] != target["evidence_id"]
    )
    repaired_records = [replacement, other]
    contract.repair_request(request_id, _bundle(repaired_records))
    assert contract.get_request(request_id).status == "OPEN"
    assert int(contract.get_request(request_id).repair_count) == 1
    _mock_web(direct_vm, repaired_records)
    _mock_llm(direct_vm, contract, request_id, "RESOLVED", "YES", "")
    assert contract.resolve_request(request_id) == "YES"
    assert contract.is_attestation_current(request_id) is True
    assert direct_vm.run_validator() is True


def test_repair_is_requester_only_and_must_change_bundle(
    direct_vm, direct_deploy
):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    target = records[0]
    _mock_web(
        direct_vm,
        records,
        {target["evidence_id"]: target["body"] + " changed"},
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
    policy_id, _, records = _setup(direct_vm, contract, owner)
    expiry_id = _request(
        direct_vm,
        contract,
        owner,
        policy_id,
        records,
        claim_key="expiry",
        deadline=NOW + HOUR,
    )
    direct_vm.warp(LATER_ISO)
    contract.expire_request(expiry_id)
    assert contract.get_request(expiry_id).status == "EXPIRED"
    _no_attestation(direct_vm, contract, expiry_id)
    with direct_vm.expect_revert("REQUEST_NOT_OPEN"):
        contract.resolve_request(expiry_id)
    with direct_vm.expect_revert("REQUEST_NOT_EXPIRABLE"):
        contract.expire_request(expiry_id)

    resolved_id = _request(
        direct_vm,
        contract,
        owner,
        policy_id,
        records,
        claim_key="resolved-terminal",
        deadline=NOW + DAY,
    )
    _mock_web(direct_vm, records)
    _mock_llm(direct_vm, contract, resolved_id, "RESOLVED", "YES", "")
    assert contract.resolve_request(resolved_id) == "YES"
    with direct_vm.expect_revert("REQUEST_NOT_OPEN"):
        contract.resolve_request(resolved_id)
    with direct_vm.expect_revert("REQUEST_NOT_EXPIRABLE"):
        contract.expire_request(resolved_id)
    with direct_vm.expect_revert("REQUEST_NOT_REPAIRABLE"):
        contract.repair_request(resolved_id, _bundle(records))


def test_attestation_becomes_noncurrent_after_lineage_advance(
    direct_vm, direct_deploy
):
    contract, owner, policy_id, records, request_id = _resolved_case(
        direct_vm, direct_deploy, "YES"
    )
    assert contract.is_attestation_current(request_id) is True
    target = records[0]
    _register(
        direct_vm,
        contract,
        policy_id,
        target["authority"],
        target["stable_id"],
        target["body"] + " superseding version",
        version=2,
        url=target["url"] + "/v2",
    )
    assert contract.is_attestation_current(request_id) is False


def test_get_verdict_exact_projection(direct_vm, direct_deploy):
    contract, owner = _deploy(direct_vm, direct_deploy)
    policy_id, _, records = _setup(direct_vm, contract, owner)
    request_id = _request(direct_vm, contract, owner, policy_id, records)
    verdict = contract.get_verdict(request_id)
    assert verdict[0] == "OPEN"
    assert verdict[1] == ""
    assert verdict[2] == ""
    assert int(verdict[3]) > NOW
