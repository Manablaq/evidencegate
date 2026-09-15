#!/bin/bash
set -euo pipefail

REPO="${HOME}/Downloads/evidencegate"
EXPECTED_CONTRACT_SHA="719e83531ba38b87cce825d68788d64a0f2971336626201ce1ea2f0726b0f1b2"
NETWORK="${EVIDENCEGATE_SUPPORTED_RUNTIME_NETWORK:-localnet}"
AUTH="${EVIDENCEGATE_SUPPORTED_RUNTIME_WRITE_AUTHORIZATION:-}"

die() {
  echo "STOP: $*" >&2
  exit 1
}

cd "$REPO" || die "repository not found"

if [ "$AUTH" != "I_EXPLICITLY_AUTHORIZE_LOCALNET_WRITES" ]; then
  echo "STOP: explicit EvidenceGate supported-runtime network-write authorization is required."
  echo "No deployment or transaction was submitted."
  exit 2
fi

test "$NETWORK" = "localnet" || {
  echo "STOP: v1 supported-runtime harness is intentionally restricted to localnet."
  echo "Bradbury and Studionet writes require a separate explicit authorization and certification stage."
  exit 2
}

test "$(git branch --show-current)" = "build/evidencegate-v1" \
  || die "wrong branch"

test -z "$(git status --porcelain=v1 --untracked-files=all)" \
  || die "worktree must be clean before supported-runtime execution"

ACTUAL_CONTRACT_SHA="$(
  shasum -a 256 contracts/evidence_gate.py |
  awk '{print $1}'
)"

echo "EXPECTED_CONTRACT_SHA256=$EXPECTED_CONTRACT_SHA"
echo "ACTUAL_CONTRACT_SHA256=$ACTUAL_CONTRACT_SHA"

test "$ACTUAL_CONTRACT_SHA" = "$EXPECTED_CONTRACT_SHA" \
  || die "canonical contract source changed"

PY="$HOME/Downloads/memoryseal/.venv/bin/python"
test -x "$PY" || die "known GenLayer test Python unavailable"

RUN_ID="${EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID="$RUN_ID"
export EVIDENCEGATE_SUPPORTED_RUNTIME_NETWORK="$NETWORK"

ARTIFACT_DIR="artifacts/evidencegate-supported-runtime/$RUN_ID"
test ! -e "$ARTIFACT_DIR" \
  || die "run artifact directory already exists: $ARTIFACT_DIR"

echo "============================================================"
echo "EVIDENCEGATE SUPPORTED-RUNTIME EXECUTION"
echo "NETWORK=$NETWORK"
echo "RUN_ID=$RUN_ID"
echo "CONTRACT_SHA256=$ACTUAL_CONTRACT_SHA"
echo "FINALITY_REQUIRED=YES"
echo "LATEST_FINAL_READS_REQUIRED=YES"
echo "AUTO_RESUBMISSION=NO"
echo "============================================================"

"$PY" -m pytest \
  tests/integration/test_evidencegate_supported_runtime.py \
  -vv \
  -s \
  --network "$NETWORK"

echo
echo "EVIDENCEGATE_SUPPORTED_RUNTIME_EXECUTION=PASS"
echo "ARTIFACT_DIR=$ARTIFACT_DIR"
