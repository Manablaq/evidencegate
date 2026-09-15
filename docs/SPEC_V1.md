# EvidenceGate v1 specification

## Purpose

EvidenceGate converts explicitly policy-bound, independently corroborated web evidence into an exact GenLayer attestation. It is a reusable primitive, not a complete application.

## Core guarantee

EvidenceGate MUST NOT create a consequential attestation unless all of the following hold:

1. the request references a sealed policy;
2. every evidence record belongs to that policy;
3. every record is bound to a policy-approved authority and exact HTTPS publisher origin;
4. every record is the latest registered version of its stable evidence lineage;
5. every record satisfies freshness, expiry, and minimum remaining-validity rules;
6. the bundle satisfies minimum evidence, distinct-authority, and distinct-origin thresholds;
7. every fetched source body matches its registered SHA-256 digest;
8. leader and validators independently derive the same decision-bearing result; and
9. the exact resolved outcome is one of the sealed policy's finite allowed outcomes.

A correctable evidence failure becomes `REPAIR_REQUIRED`, not a false negative verdict.

## Request states

- `OPEN`
- `RESOLVED`
- `REPAIR_REQUIRED`
- `EXPIRED`

Only `RESOLVED` creates an attestation.

`RESOLVED` and `EXPIRED` are terminal.

`REPAIR_REQUIRED` may return to `OPEN` only when the original requester supplies a changed evidence bundle that passes deterministic policy checks before the original deadline. Repair never extends the deadline.

## Policy

A policy binds:

- creator/owner;
- stable slug and version;
- bounded natural-language evaluation criteria;
- approved authority IDs;
- one exact HTTPS publisher origin per authority;
- finite uppercase outcome codes;
- minimum evidence records;
- minimum distinct authorities;
- minimum distinct origins;
- maximum evidence age;
- minimum remaining validity;
- maximum request lifetime; and
- maximum evidence records per request.

Authorities and outcomes are added canonically and incorporated into a deterministic policy fingerprint. Once sealed, policy trust assumptions are immutable.

## Evidence

Each evidence record binds:

- policy ID;
- stable record ID;
- strictly increasing version;
- approved authority ID;
- policy-bound publisher origin;
- source URL under that origin;
- SHA-256 of the exact source body;
- publication time;
- expiry time; and
- registration time.

Registration may be permissionless because trust does not come from the submitter. Trust comes from the sealed policy binding plus later source-body verification.

A request can use only the latest registered version of an evidence lineage.

## Corroboration

Every policy requires at least two evidence records, two distinct authorities, and two distinct origins. A single publisher duplicated under multiple URLs cannot satisfy the independence requirement.

## Request

A request binds:

- requester;
- policy ID;
- stable claim key;
- bounded question;
- strictly sorted evidence IDs;
- evidence bundle digest;
- creation time; and
- immutable deadline.

At creation or repair, evidence must remain valid beyond the request deadline.

## Consensus

Leader and validators independently:

1. fetch every registered source URL;
2. bound the response body size;
3. SHA-256 the exact fetched bytes;
4. require the digest to match the registered digest;
5. evaluate only those verified bytes under the sealed policy criteria; and
6. return a bounded structured result.

Decision-bearing fields are compared exactly. At minimum:

- result kind;
- exact outcome;
- bounded failure code; and
- evidence bundle digest.

No score, similarity threshold, or percentage tolerance may transform one consequential outcome into another.

A validator that merely checks the leader's schema is invalid. The validator must independently rerun the evidence fetch/evaluation path.

## Repair semantics

Correctable conditions include:

- source fetch failure;
- source body above the size bound;
- registered digest not matching fetched bytes;
- stale/expired/non-latest evidence discovered at resolution; and
- materially conflicting or insufficient evidence.

These conditions must not silently become a substantive negative outcome.

Repair requires a changed evidence bundle and cannot extend the deadline.

## Liveness

Every request has an immutable policy-bounded deadline. At or after the deadline, unresolved or repairable requests can become `EXPIRED`. No request may remain consequentially open forever.

## Attestation

A successful resolution stores at least:

- request ID;
- policy ID;
- sealed policy fingerprint;
- claim digest;
- exact outcome;
- evidence bundle digest;
- evidence count;
- distinct-authority count;
- distinct-origin count;
- resolution time; and
- validity bound inherited from the evidence bundle.

The resolved request is terminal, making the attestation immutable for that request.

## v1 bounds

The implementation must cap authority count, outcome count, evidence count, question bytes, criteria bytes, fetched source bytes, evidence age, and request lifetime.

## Explicit exclusions

EvidenceGate v1 does not:

- custody or transfer value;
- automatically settle another contract;
- call another contract;
- upgrade itself;
- make a malicious approved authority truthful;
- make unavailable web evidence available;
- treat a URL or hash alone as authority; or
- treat a local test as proof of Bradbury finality.

These are deliberate trust/scope boundaries.
