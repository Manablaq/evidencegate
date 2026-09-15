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
- approved authority IDs, each bound to a unique authority address within the policy;
- one exact HTTPS publisher origin per authority;
- finite uppercase outcome codes;
- minimum evidence records;
- minimum distinct authorities;
- minimum distinct origins;
- maximum evidence age;
- minimum remaining validity;
- maximum request lifetime; and
- maximum evidence records per request.

A policy is created atomically with canonically sorted authority IDs, exact authority addresses, publisher origins, and outcomes. Successful creation immediately stores the sealed policy fingerprint; there is no partially configured policy state to mutate later.

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

Registration is authority-authenticated: only the exact address bound to an approved authority ID may register or advance that authority's evidence lineage. Trust still depends on the sealed policy, provenance binding, and later source-body verification rather than on a URL/hash alone.

Source URLs must remain under the exact policy-bound HTTPS origin and may not contain URL fragments. Authority origins must be canonical HTTPS DNS hostnames.

A request can use only the latest registered version of an evidence lineage.

## Corroboration

Every policy requires at least two evidence records, two distinct authority IDs backed by distinct authority addresses, and two distinct origins. One signing address or publisher duplicated under multiple labels/URLs cannot satisfy the mechanical independence requirement.

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

At creation or repair, the bundle's effective policy-valid horizon must extend beyond the request deadline. That horizon is the earliest point at which expiry, maximum evidence age, or minimum remaining-validity requirements would cease to hold.

## Consensus

Leader and validators independently:

1. fetch every registered source URL;
2. require HTTP status `200`;
3. bound the response body size;
4. SHA-256 the exact fetched bytes;
5. require the digest to match the registered digest;
6. evaluate only those verified bytes under the sealed policy criteria; and
7. return a bounded structured result.

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

The resolved request is terminal, making the historical attestation immutable for that request. Consequential consumers must additionally call `is_attestation_current(request_id)`: a later evidence-lineage version or any freshness/validity failure makes the historical attestation non-current even though the record remains queryable.

## v1 bounds

The implementation must cap authority count, outcome count, evidence count, question bytes, criteria bytes, each fetched source body, the aggregate fetched source bundle, evidence age, and request lifetime.

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
