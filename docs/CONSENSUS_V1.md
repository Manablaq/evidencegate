# EvidenceGate v1 consensus model

## Objective

GenLayer consensus is used to derive one exact policy-allowed outcome from a fixed, policy-valid evidence bundle.

## Nondeterministic boundary

Web requests and LLM calls occur only inside the nondeterministic execution function. Persistent state is mutated only after the nondeterministic result has been accepted by consensus.

## Leader

The leader independently fetches and verifies every source body, evaluates the bounded question under the sealed criteria, and returns structured decision fields.

## Validator

Each validator independently reruns the same fetch/hash/evaluation path. It does not merely validate the leader's JSON shape.

The validator must exactly compare the decision-bearing fields. Reasoning prose is neither required nor persisted as a consequential field.

## Exact consequence

Different outcome codes are never equivalent. A validator may not use a tolerance that can bridge two distinct policy outcomes.

## Repair result

If evidence is unavailable, altered, conflicting, insufficient, stale, expired, or otherwise correctable, the contract uses a repairable result rather than manufacturing a negative answer.

## Error handling

Malformed LLM output or a leader-only transient failure should cause validator disagreement/rotation rather than acceptance of an unsafe result.

The implementation must classify only a small bounded set of repair codes and must not persist arbitrary model-generated failure text.
