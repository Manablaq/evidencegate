# EvidenceGate v1 security model

## Authority model

A URL or digest is not authority. A sealed policy binds approved publisher identities to exact HTTPS origins. Evidence is accepted only under those bindings.

EvidenceGate cannot guarantee that an approved authority is honest; choosing authorities is a policy-author responsibility.

## Immutability/versioning

Evidence uses stable record IDs with monotonically increasing versions. Requests must use the latest registered version.

## Freshness

Maximum evidence age, minimum remaining validity, expiry, and request lifetime are explicit deterministic policy rules.

## Corroboration

At least two evidence records, two distinct authority IDs bound to distinct authority addresses, and two distinct origins are required. This prevents one signing key from satisfying multiple authority slots under different labels.

## Exact consensus-to-consequence binding

Validators independently derive the substantive outcome and exactly compare consequential fields. Schema-only validation is forbidden.

## Correctable failures

Correctable evidence failures must enter `REPAIR_REQUIRED`. They must not be collapsed into a substantive rejection outcome.

## Liveness

Deadlines are immutable and repair cannot extend them. Unresolved requests can expire.

## Authority-origin network boundary

Authority origins must be canonical HTTPS DNS hostnames. Literal IPv4
origins are rejected, as are malformed DNS labels. This reduces obvious
internal-address/SSRF-style configuration mistakes, but DNS rebinding and
network-layer policy remain runtime/environment trust boundaries.

## Evidence validity horizon and attestation reuse

The effective validity horizon is the earliest bound implied by source
expiry, maximum evidence age, and minimum remaining validity. Requests
cannot be created or repaired with a deadline at or beyond that horizon.

A resolved attestation is immutable historical evidence, not an eternal
"currently valid" flag. `is_attestation_current()` rechecks the exact
bound evidence bundle against latest registered lineage versions and
current policy freshness before downstream consequential reuse.

## HTTP transport result

Only HTTP status `200` is eligible for evidence evaluation. Non-200 responses are repairable failures and cannot create attestations.

## Prompt injection

Fetched content is untrusted data. The evaluation prompt must explicitly instruct the model to ignore instructions embedded in evidence and to answer only the bounded question under the sealed criteria.

Digest binding proves the exact bytes evaluated; it does not prove those bytes are truthful.

## DoS bounds

All collections and text/body sizes used in consensus are bounded.

## Hidden mutation/value-transfer review

v1 must contain no payable surface, balance accounting, transfer, message emission, external contract call, or code-upgrade path.

## Release rule

Any change to the canonical contract after certification invalidates the previous source hash and requires a new review/deployment/finality record.
