#!/bin/bash
set -euo pipefail

REPO="${HOME}/Downloads/evidencegate"
EXPECTED_CONTRACT_SHA="776dcd2ce4b0e6844d184831efe4b3e2b9b46eab2116d975bcf2f670b57562e5"
EXPECTED_TEST_SHA="37fc4ae99c2f02943311ceb785154f154f162615da5fd335ef7d94921ea8dcda"
EXPECTED_CONFIG_SHA="2b643303f18082b3ecdd9c71ad1d029421b352ae8f0ea6c5db442b6cc99956c1"
EXPECTED_REQUIREMENTS_SHA="e3cf2b74588825b277d2f563eb159419450e907bf63b9017303ff3d25565d649"
EXPECTED_LOCK_SHA="600dfc9a0e5ec0eb0adeab9b0eb751be03cce5ea95a44105fdfaf4e3c6eb4cfb"
NETWORK="${EVIDENCEGATE_SUPPORTED_RUNTIME_NETWORK:-localnet}"
AUTH="${EVIDENCEGATE_SUPPORTED_RUNTIME_WRITE_AUTHORIZATION:-}"

die() {
  echo "STOP: $*" >&2
  exit 1
}

cd "$REPO" || die "repository not found"

if [ "$AUTH" != "I_EXPLICITLY_AUTHORIZE_LOCALNET_WRITES" ]; then
  echo "STOP: explicit EvidenceGate supported-runtime localnet-write authorization is required."
  echo "No GenLayer network read, deployment, or transaction was submitted."
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

sha_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

test "$(sha_file contracts/evidence_gate.py)" = "$EXPECTED_CONTRACT_SHA" \
  || die "canonical contract source changed"
test "$(sha_file tests/integration/test_evidencegate_supported_runtime.py)" = "$EXPECTED_TEST_SHA" \
  || die "supported-runtime integration test changed"
test "$(sha_file gltest.config.yaml)" = "$EXPECTED_CONFIG_SHA" \
  || die "gltest config changed"
test "$(sha_file requirements-supported-runtime.txt)" = "$EXPECTED_REQUIREMENTS_SHA" \
  || die "supported-runtime requirements changed"
test "$(sha_file requirements-supported-runtime-lock.txt)" = "$EXPECTED_LOCK_SHA" \
  || die "supported-runtime lock changed"

PY="${EVIDENCEGATE_PYTHON:-$REPO/.venv/bin/python}"
test -x "$PY" || {
  echo "STOP: EvidenceGate repo-local Python environment not found."
  echo "Create it with:"
  echo "  python3.12 -m venv .venv"
  echo "  .venv/bin/python -m pip install -r requirements-supported-runtime-lock.txt"
  exit 2
}

"$PY" - <<'PY'
import importlib.metadata as md
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(
        f"STOP: Python 3.12 required, found {sys.version.split()[0]}"
    )

expected = {
    "genlayer-test": "0.29.2",
    "genlayer-py": "0.16.3",
    "pytest": "9.1.1",
    "eth-utils": "6.0.0",
}

for package, wanted in expected.items():
    actual = md.version(package)
    print(f"TOOLCHAIN::{package}={actual}")
    if actual != wanted:
        raise SystemExit(
            f"STOP: {package} version mismatch: {actual} != {wanted}"
        )

print("SUPPORTED_RUNTIME_TOOLCHAIN_GATE=PASS")
PY

RUN_ID="${EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID="$RUN_ID"
export EVIDENCEGATE_SUPPORTED_RUNTIME_NETWORK="$NETWORK"

ARTIFACT_DIR="artifacts/evidencegate-supported-runtime/$RUN_ID"
test ! -e "$ARTIFACT_DIR" \
  || die "run artifact directory already exists: $ARTIFACT_DIR"

RPC_URL="$(
  "$PY" - <<'PY'
from genlayer_py.chains import localnet
print(localnet.rpc_urls["default"]["http"][0])
PY
)"

echo "============================================================"
echo "EVIDENCEGATE SUPPORTED-RUNTIME EXECUTION"
echo "NETWORK=$NETWORK"
echo "RUN_ID=$RUN_ID"
echo "RPC_URL=$RPC_URL"
echo "CONTRACT_SHA256=$EXPECTED_CONTRACT_SHA"
echo "INTEGRATION_TEST_SHA256=$EXPECTED_TEST_SHA"
echo "FINALITY_REQUIRED=YES"
echo "LATEST_FINAL_READS_REQUIRED=YES"
echo "EXPECTED_VALIDATORS=5"
echo "AUTO_RESUBMISSION=NO"
echo "============================================================"

RPC_RESPONSE="$(
  curl --fail --silent --show-error \
    -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
    "$RPC_URL"
)" || die "local GenLayer RPC preflight failed"

CHAIN_ID="$(
  printf '%s' "$RPC_RESPONSE" |
  "$PY" -c '
import json, sys
value = json.load(sys.stdin)
if "error" in value:
    raise SystemExit("RPC returned error: " + repr(value["error"]))
print(value.get("result", ""))
'
)"

EXPECTED_CHAIN_ID="$(
  "$PY" - <<'PY'
from genlayer_py.chains import localnet

print(hex(localnet.id))

if localnet.default_number_of_initial_validators != 5:
    raise SystemExit(
        "STOP: pinned localnet default validator count is not 5"
    )
PY
)"

echo "RPC_CHAIN_ID=$CHAIN_ID"
echo "PINNED_SDK_LOCALNET_CHAIN_ID=$EXPECTED_CHAIN_ID"

test "$CHAIN_ID" = "$EXPECTED_CHAIN_ID" \
  || die "RPC chain id does not match pinned SDK localnet definition"

echo "GENLAYER_PREFLIGHT_READ=PASS"

"$PY" -m pytest \
  tests/integration/test_evidencegate_supported_runtime.py \
  -vv \
  -s \
  --network "$NETWORK"

MANIFEST="$ARTIFACT_DIR/manifest.json"
test -f "$MANIFEST" || die "supported-runtime manifest missing"

MANIFEST_SHA="$(
  shasum -a 256 "$MANIFEST" |
  awk '{print $1}'
)"

echo
echo "EVIDENCEGATE_SUPPORTED_RUNTIME_EXECUTION=PASS"
echo "ARTIFACT_DIR=$ARTIFACT_DIR"
echo "MANIFEST_SHA256=$MANIFEST_SHA"
