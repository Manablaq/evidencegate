# EvidenceGate v1 Bradbury live proof

Status: **canonical fixed source deployed and end-to-end live-network verified on GenLayer Bradbury; every canonical transaction listed below reached `Finalized|7`, and the final request resolved to exact `YES` with five-validator exact agreement.**

## Bound release

```text
repository branch: build/evidencegate-v1
release commit before live-proof documentation update:
4f04ee6bfa65965d12b7437c72b26c914a4fd125

contract:
contracts/evidence_gate.py

contract SHA-256:
6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1

contract bytes:
16181

Bradbury chain ID:
4221

canonical contract:
0xbd403771f876F72540319480EC2453d01de27a2b
```

The deployment transaction created that canonical contract from the exact fixed source above. The later documentation update does not modify the contract source.

## Canonical finalized transaction chain

Every transaction below was independently rechecked as `Finalized|7` in R22-R50R.

```text
deployment:
0xa3849f47e9f2e97b7957544407000a996398772dd716ba36bf5f6f1544122a1e

create_policy:
0x226036045b1be46aab5883bac9ef3c47691410e1a094698c6215a9223b55186c

authority-a register_evidence:
0x3fa2a6caaba96374e67f90bdcd6abb418370202e71e3bb178bc89009d8abf23b

authority-b register_evidence:
0x611d1e7aebaf1f58debd301085d508762facedcf2d9c65f4e8dc9978797fccbb

create_request:
0x14041dfeac8d17579e70be9a0f8f5a3711ef4966a2f01bce857856dd763f3125

resolve_request:
0xd04538ea1d0cbb6ea037691a7c4de60fe02f2c0d52bb29b71d31c673e99d773b
```

No live write was automatically retried or resubmitted after a transaction hash was observed. Finality tracking used the original transaction hashes. No manual finalization was used for this live proof.

## Finalized policy

```text
policy id:
c6dcb70bcf8f024972ddca6c9ea498844f896c8f845a692655e69d9f35fc5122

policy fingerprint:
4123169fde60475e1e6b831d8c1d6aed1f505597662360d121e9453e719c9bc8

allowed outcomes:
NO,YES

minimum evidence records:
2

minimum distinct authorities:
2

minimum distinct publisher origins:
2

maximum evidence age:
604800 seconds

minimum remaining validity:
3600 seconds

maximum request lifetime:
86400 seconds
```

The policy binds two authority identities to two authority addresses and two publisher origins. Exact consequential outcomes are limited to the policy outcome set.

## Immutable evidence records

### Authority A

```text
evidence id:
817ce084efdd402ec3894d7fe18c1ac7a40f6dcee85c2e95ed6c03cd3e7f1c9d

authority id:
authority-a

stable record id:
evidencegate-fixed-finalized-2026-09-17-primary

version:
1

publisher origin:
https://raw.githubusercontent.com

immutable URL:
https://raw.githubusercontent.com/Manablaq/genlayer-evidence-primary/e496cdbf64678afe8fa2e54877df8f5b6f048a76/records/evidencegate-fixed-finalized-2026-09-17.txt

SHA-256:
3f76a70ac784f931d7eaf4fe723a5e476555acdb0d7c799195e470d92ff1aa17

bytes:
1114

published_at:
1789628180

expires_at:
1790232980
```

### Authority B

```text
evidence id:
c81c043b6fd0eabe597c8ddbcaa2df4a1b84571390192f000130848b450e6a75

authority id:
authority-b

stable record id:
evidencegate-fixed-finalized-2026-09-17-corroboration

version:
1

publisher origin:
https://cdn.jsdelivr.net

immutable URL:
https://cdn.jsdelivr.net/gh/Manablaq/genlayer-evidence-corroboration@c9f8383c49d511d0ff9e526f0c0dc0ffd379cadc/records/evidencegate-fixed-finalized-2026-09-17.txt

SHA-256:
b3ceccfe79670fb78cc7ec31b95b0163d84441072c6b0afaf237767f3edfefd5

bytes:
1103

published_at:
1789628180

expires_at:
1790232980
```

R22-R50R refetched both immutable URLs and reproduced both registered SHA-256 values and byte counts.

## Canonical request and final attestation

```text
request id:
eece9ba052a5a794d4904777f54a9a31d6c9736e0be6587ec5d7fa5c6f79ecf1

claim digest:
017353226c04b05672fd2a3c2499af5d4ea7cb271d406dfa75ab1377ad02d43b

evidence-bundle digest:
18b392e491446e4b1b5991bbcb3383d7c5922f4fa9b39256f411b70d34f3f2a2

request status:
RESOLVED

final outcome:
YES

failure code:
(empty)

attestation resolved_at:
1789641006

attestation valid_until:
1790229381
```

The finalized attestation records:

```text
evidence_count = 2
distinct_authority_count = 2
distinct_origin_count = 2
```

At R22-R50R chain timestamp `1789663471`, `is_attestation_current(request_id)` was `true` and `565910` seconds remained until `valid_until`. That observation is time-bound; consumers must re-check currentness when using the attestation later.

## Finalized validator consensus

R22-R50D and R22-R50R read Bradbury consensus data directly from the chain-defined consensus data contract:

```text
consensus data contract:
0x85D7bf947A512Fc640C75327A780c90847267697

resolve transaction:
0xd04538ea1d0cbb6ea037691a7c4de60fe02f2c0d52bb29b71d31c673e99d773b

final transaction status:
7 (Finalized)

round count:
1

round:
0

validators:
5

votes committed:
5

votes revealed:
5

validator votes:
1,1,1,1,1

result hash:
0x8627ec61ad8c347cd2e86d5a3e4cf36699b3832a44dc69b71497f9f213dcad3f
```

All five validator result hashes exactly matched the transaction result hash. This is the live exact-consensus-to-consequence proof for the canonical `YES` resolution.

`Accepted|5` was never treated as final. The final reviewer-facing claim is based on network-side `Finalized|7` plus `LATEST_FINAL` application state.

## Relationship to reproducible supported-runtime verification

The Bradbury proof is separate from the isolated supported-runtime harness.

The supported-runtime layer proves reproducible five-validator execution for exact positive and negative outcomes, repair/re-resolution, expiry, raw-response preservation, and finalized reads in the pinned local runtime.

The Bradbury layer proves that the exact fixed source was separately deployed and that one canonical real-network policy/evidence/request/resolve path reached network finality with the exact expected attestation bindings.

Neither layer substitutes for the other.

## Reviewer hard-gate coverage

The combined verification evidence covers:

- policy-bound authority identities and addresses;
- immutable/versioned evidence references;
- two distinct registered authorities;
- two distinct registered publisher origins;
- exact source SHA-256 binding;
- evidence freshness, expiry, and minimum remaining-validity checks;
- exact allowed consequential outcomes;
- repairable source/evidence failure states;
- request deadline/expiry behavior;
- exact validator comparison of consequential resolution output;
- five-validator finalized consensus on the live resolution;
- `LATEST_FINAL` attestation exactness;
- no escrow, token, or value-custody path.

## Trust-boundary limitations

EvidenceGate can prove that the configured authority addresses, origins, immutable records, hashes, freshness rules, and consensus outputs match the governing policy.

EvidenceGate does **not** cryptographically prove that a policy-approved authority is truthful, or that two distinct addresses/origins are controlled by independent real-world organizations. Those remain explicit policy/governance trust assumptions.

Historical Bradbury activity for predecessor source versions is not used as deployment, finality, or attestation evidence for this fixed source.
