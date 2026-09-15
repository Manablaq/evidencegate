# EvidenceGate v1 security model

## Authority model

A URL or digest is not authority. A sealed policy binds approved publisher identities to exact HTTPS origins. Evidence is accepted only under those bindings.

EvidenceGate cannot guarantee that an approved authority is honest; choosing authorities is a policy-author responsibility.

## Immutability/versioning

Evidence uses stable record IDs with monotonically increasing versions. Requests must use the latest registered version.

## Freshness

Maximum evidence age, minimum remaining validity, expiry, and request lifetime are explicit deterministic policy rules.

## Corroboration

At least two evidence records, two distinct authorities, and two distinct origins are required.

## Exact consensus-to-consequence binding

Validators independently derive the substantive outcome and exactly compare consequential fields. Schema-only validation is forbidden.

## Correctable failures

Correctable evidence failures must enter `REPAIR_REQUIRED`. They must not be collapsed into a substantive rejection outcome.

## Liveness

Deadlines are immutable and repair cannot extend them. Unresolved requests can expire.

## Prompt injection

Fetched content is untrusted data. The evaluation prompt must explicitly instruct the model to ignore instructions embedded in evidence and to answer only the bounded question under the sealed criteria.

Digest binding proves the exact bytes evaluated; it does not prove those bytes are truthful.

## DoS bounds

All collections and text/body sizes used in consensus are bounded.

## Hidden mutation/value-transfer review

v1 must contain no payable surface, balance accounting, transfer, message emission, external contract call, or code-upgrade path.

## Release rule

Any change to the canonical contract after certification invalidates the previous source hash and requires a new review/deployment/finality record.
