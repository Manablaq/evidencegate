#!/bin/bash
set -euo pipefail

REPO="${EVIDENCEGATE_REPO:-${HOME}/Downloads/evidencegate}"

EXPECTED_CONTRACT_SHA="6b5c31c786f3b8af0df559ae831b93083dbbe4ee23552a40c268edf633f80ad1"
EXPECTED_TEST_SHA="71a34d8c258292d30f445a303d77a37d6f5aeeeb01ed0d6c6b63a5e17b98cda0"
EXPECTED_CONFIG_SHA="2b643303f18082b3ecdd9c71ad1d029421b352ae8f0ea6c5db442b6cc99956c1"
EXPECTED_REQUIREMENTS_SHA="42bacbcf02387c98c551220ecaedd5e61e3534b67f0e84f7b3b2e3d3f57ddb30"
EXPECTED_LOCK_SHA="3b9981d8a29a1c1f8894549f4d77f9d6ccbd55c67533f5603c9c7f8d09ad4c38"

NETWORK="${EVIDENCEGATE_SUPPORTED_RUNTIME_NETWORK:-localnet}"
AUTH="${EVIDENCEGATE_SUPPORTED_RUNTIME_WRITE_AUTHORIZATION:-}"

GLSIM_PORT="${EVIDENCEGATE_GLSIM_PORT:-4011}"
GLSIM_CHAIN_ID="61999"
GLSIM_VALIDATORS="5"
GLSIM_MAX_ROTATIONS="3"

die() {
  echo "STOP: $*" >&2
  exit 1
}

sha_file() {
  shasum -a 256 "$1" |
    awk '{print $1}'
}

cleanup() {
  set +e

  if [ -n "${GLSIM_PID:-}" ]; then
    kill "$GLSIM_PID" >/dev/null 2>&1 || true

    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$GLSIM_PID" >/dev/null 2>&1 || break
      sleep 0.2
    done

    kill -9 "$GLSIM_PID" >/dev/null 2>&1 || true
  fi

  if [ -n "${TMPROOT:-}" ] && [ -d "$TMPROOT" ]; then
    rm -rf "$TMPROOT"
  fi
}

trap cleanup EXIT INT TERM

cd "$REPO" || die "repository not found"

if [ "$AUTH" != "I_EXPLICITLY_AUTHORIZE_LOCALNET_WRITES" ]; then
  echo "STOP: explicit EvidenceGate supported-runtime localnet-write authorization is required."
  echo "Set:"
  echo "  EVIDENCEGATE_SUPPORTED_RUNTIME_WRITE_AUTHORIZATION=I_EXPLICITLY_AUTHORIZE_LOCALNET_WRITES"
  echo "No GenLayer transaction was submitted."
  exit 2
fi

test "$NETWORK" = "localnet" || {
  echo "STOP: supported-runtime runner is intentionally restricted to isolated localnet."
  echo "Bradbury writes require a separate explicit authorization."
  exit 2
}

test "$(git branch --show-current)" = "build/evidencegate-v1" \
  || die "wrong branch"

test -z "$(git status --porcelain=v1 --untracked-files=all)" \
  || die "worktree must be clean before supported-runtime execution"

test "$(sha_file contracts/evidence_gate.py)" = "$EXPECTED_CONTRACT_SHA" \
  || die "canonical contract source changed"

test "$(sha_file tests/integration/test_evidencegate_supported_runtime.py)" = "$EXPECTED_TEST_SHA" \
  || die "supported-runtime integration test changed"

test "$(sha_file gltest.config.yaml)" = "$EXPECTED_CONFIG_SHA" \
  || die "canonical gltest config changed"

test "$(sha_file requirements-supported-runtime.txt)" = "$EXPECTED_REQUIREMENTS_SHA" \
  || die "supported-runtime requirements changed"

test "$(sha_file requirements-supported-runtime-lock.txt)" = "$EXPECTED_LOCK_SHA" \
  || die "supported-runtime lock changed"

for required_tool in \
  python3.12 \
  curl \
  rsync \
  lsof \
  git \
  shasum
do
  command -v "$required_tool" >/dev/null 2>&1 \
    || die "$required_tool is required"
done

if lsof -nP -iTCP:"$GLSIM_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "STOP: isolated GLSim port $GLSIM_PORT is already in use."
  lsof -nP -iTCP:"$GLSIM_PORT" -sTCP:LISTEN || true
  exit 2
fi

RUN_ID="${EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

FINAL_ARTIFACT_DIR="$REPO/artifacts/evidencegate-supported-runtime/$RUN_ID"

test ! -e "$FINAL_ARTIFACT_DIR" \
  || die "run artifact directory already exists: $FINAL_ARTIFACT_DIR"

TMPROOT="$(mktemp -d)"
VENV="$TMPROOT/venv"
MIRROR="$TMPROOT/evidencegate"
COMPAT="$TMPROOT/compat"
GLSIM_LOG="$TMPROOT/glsim.log"
GLSIM_PID=""

mkdir -p "$MIRROR" "$COMPAT"

echo "============================================================"
echo "EVIDENCEGATE SUPPORTED-RUNTIME EXECUTION"
echo "NETWORK=$NETWORK"
echo "RUN_ID=$RUN_ID"
echo "ISOLATED_GLSIM_PORT=$GLSIM_PORT"
echo "CHAIN_ID=$GLSIM_CHAIN_ID"
echo "EXPECTED_VALIDATORS=$GLSIM_VALIDATORS"
echo "MAX_ROTATIONS=$GLSIM_MAX_ROTATIONS"
echo "CONTRACT_SHA256=$EXPECTED_CONTRACT_SHA"
echo "INTEGRATION_TEST_SHA256=$EXPECTED_TEST_SHA"
echo "REQUIREMENTS_SHA256=$EXPECTED_REQUIREMENTS_SHA"
echo "LOCK_SHA256=$EXPECTED_LOCK_SHA"
echo "FINALITY_REQUIRED=YES"
echo "LATEST_FINAL_READS_REQUIRED=YES"
echo "AUTO_RESUBMISSION=NO"
echo "BRADBURY_WRITE=NO"
echo "============================================================"

python3.12 \
  -m venv \
  "$VENV"

"$VENV/bin/python" \
  -m pip install \
  --disable-pip-version-check \
  --no-input \
  --no-deps \
  -r "$REPO/requirements-supported-runtime-lock.txt"

"$VENV/bin/python" \
  -m pip check

"$VENV/bin/python" - <<'PY'
from importlib import metadata
import importlib.util

expected = {
    "genlayer-test": "0.29.2",
    "genlayer-py": "0.16.3",
    "pytest": "9.1.1",
    "eth-utils": "6.0.0",
    "numpy": "2.3.3",
}

for package, wanted in expected.items():
    actual = metadata.version(package)
    print(f"TOOLCHAIN::{package}={actual}")

    if actual != wanted:
        raise SystemExit(
            f"STOP: {package} version mismatch: {actual} != {wanted}"
        )

for module in (
    "glsim",
    "glsim.server",
    "fastapi",
    "uvicorn",
    "httpx",
    "numpy",
):
    if importlib.util.find_spec(module) is None:
        raise SystemExit(
            f"STOP: required runtime module missing: {module}"
        )

print("SUPPORTED_RUNTIME_TOOLCHAIN_GATE=PASS")
PY

cat >"$COMPAT/sitecustomize.py" <<'PY'
from dataclasses import fields, is_dataclass

import glsim.tx_decoder as tx_decoder


def _normalize_runtime_result(value):
    value_type = type(value)

    if (
        value_type.__module__ == "genlayer.py.types"
        and value_type.__name__ == "Address"
    ):
        address_hex = value.as_hex

        if callable(address_hex):
            address_hex = address_hex()

        return str(address_hex)

    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _normalize_runtime_result(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(value, dict):
        return {
            key: _normalize_runtime_result(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _normalize_runtime_result(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _normalize_runtime_result(item)
            for item in value
        )

    return value


def _encode_calldata_result(value):
    return tx_decoder.calldata.encode(
        _normalize_runtime_result(value)
    )


def _encode_result_bytes(value):
    return bytes([0]) + tx_decoder.calldata.encode(
        _normalize_runtime_result(value)
    )


tx_decoder.encode_calldata_result = _encode_calldata_result
tx_decoder.encode_result_bytes = _encode_result_bytes
PY

COMPAT_SHA="$(
  shasum -a 256 "$COMPAT/sitecustomize.py" |
    awk '{print $1}'
)"

echo "GLSIM_COMPAT_SHIM_SHA256=$COMPAT_SHA"

PYTHONPATH="$COMPAT" \
"$VENV/bin/python" - <<'PY'
from dataclasses import dataclass

from genlayer_py.abi import calldata
from glsim.tx_decoder import (
    encode_calldata_result,
    encode_result_bytes,
)


class Address:
    __module__ = "genlayer.py.types"

    def __init__(self, value):
        self.as_hex = value


@dataclass
class Sample:
    owner: object
    version: int


address = "0x1111111111111111111111111111111111111111"

value = Sample(
    owner=Address(address),
    version=7,
)

read_value = calldata.decode(
    encode_calldata_result(value)
)

write_raw = encode_result_bytes(value)

if write_raw[:1] != b"\x00":
    raise SystemExit(
        "STOP: compatibility write prefix mismatch"
    )

write_value = calldata.decode(
    write_raw[1:]
)

expected = {
    "owner": address,
    "version": 7,
}

if read_value != expected:
    raise SystemExit(
        f"STOP: compatibility read result mismatch: {read_value!r}"
    )

if write_value != expected:
    raise SystemExit(
        f"STOP: compatibility write result mismatch: {write_value!r}"
    )

print("GLSIM_COMPATIBILITY_SHIM_GATE=PASS")
PY

rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'artifacts' \
  --exclude '.gltest-artifacts' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  "$REPO/" \
  "$MIRROR/"

cat >"$MIRROR/gltest.config.yaml" <<EOF
networks:
  default: localnet
  localnet:
    url: "http://127.0.0.1:${GLSIM_PORT}/api"
    leader_only: false

paths:
  contracts: contracts
  artifacts: .gltest-artifacts

environment: .env
EOF

PYTHONPATH="$COMPAT" \
"$VENV/bin/glsim" \
  --host 127.0.0.1 \
  --port "$GLSIM_PORT" \
  --validators "$GLSIM_VALIDATORS" \
  --max-rotations "$GLSIM_MAX_ROTATIONS" \
  --chain-id "$GLSIM_CHAIN_ID" \
  --no-browser \
  >"$GLSIM_LOG" 2>&1 &

GLSIM_PID=$!

GLSIM_READY="NO"

for _ in $(seq 1 80); do
  if ! kill -0 "$GLSIM_PID" >/dev/null 2>&1; then
    echo "===== GLSIM LOG BEGIN ====="
    cat "$GLSIM_LOG" || true
    echo "===== GLSIM LOG END ====="
    die "GLSim exited before ready"
  fi

  if curl \
    --silent \
    --fail \
    --max-time 2 \
    "http://127.0.0.1:${GLSIM_PORT}/health" \
    >/dev/null 2>&1
  then
    GLSIM_READY="YES"
    break
  fi

  sleep 0.5
done

test "$GLSIM_READY" = "YES" || {
  echo "===== GLSIM LOG BEGIN ====="
  cat "$GLSIM_LOG" || true
  echo "===== GLSIM LOG END ====="
  die "GLSim health check failed"
}

RPC_URL="http://127.0.0.1:${GLSIM_PORT}/api"

CHAIN_RESPONSE="$(
  curl \
    --silent \
    --show-error \
    --fail \
    -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' \
    "$RPC_URL"
)"

CHAIN_DECIMAL="$(
  "$VENV/bin/python" - "$CHAIN_RESPONSE" <<'PY'
import json
import sys

value = json.loads(
    sys.argv[1]
)["result"]

print(
    int(value, 16)
    if isinstance(value, str)
    else int(value)
)
PY
)"

echo "RPC_CHAIN_ID=$CHAIN_DECIMAL"

test "$CHAIN_DECIMAL" = "$GLSIM_CHAIN_ID" \
  || die "isolated GLSim chain id mismatch"

cd "$MIRROR"

export EVIDENCEGATE_SUPPORTED_RUNTIME_RUN_ID="$RUN_ID"
export EVIDENCEGATE_SUPPORTED_RUNTIME_NETWORK="$NETWORK"
export EVIDENCEGATE_WAIT_INTERVAL_MS="${EVIDENCEGATE_WAIT_INTERVAL_MS:-100}"
export EVIDENCEGATE_WAIT_RETRIES="${EVIDENCEGATE_WAIT_RETRIES:-600}"

set +e

"$VENV/bin/python" \
  -m pytest \
  -vv \
  -s \
  tests/integration/test_evidencegate_supported_runtime.py

TEST_RC=$?

set -e

if [ "$TEST_RC" -ne 0 ]; then
  echo "===== GLSIM LOG TAIL BEGIN ====="
  tail -800 "$GLSIM_LOG" || true
  echo "===== GLSIM LOG TAIL END ====="
  exit "$TEST_RC"
fi

SOURCE_ARTIFACT_DIR="$MIRROR/artifacts/evidencegate-supported-runtime/$RUN_ID"

test -d "$SOURCE_ARTIFACT_DIR" \
  || die "supported-runtime artifact directory missing"

test -f "$SOURCE_ARTIFACT_DIR/manifest.json" \
  || die "supported-runtime manifest missing"

mkdir -p \
  "$REPO/artifacts/evidencegate-supported-runtime"

cp -R \
  "$SOURCE_ARTIFACT_DIR" \
  "$FINAL_ARTIFACT_DIR"

cp \
  "$GLSIM_LOG" \
  "$FINAL_ARTIFACT_DIR/glsim.log"

cat >"$FINAL_ARTIFACT_DIR/runner-runtime.json" <<EOF
{
  "run_id": "$RUN_ID",
  "network": "$NETWORK",
  "chain_id": $GLSIM_CHAIN_ID,
  "validator_count": $GLSIM_VALIDATORS,
  "max_rotations": $GLSIM_MAX_ROTATIONS,
  "contract_sha256": "$EXPECTED_CONTRACT_SHA",
  "integration_test_sha256": "$EXPECTED_TEST_SHA",
  "canonical_gltest_config_sha256": "$EXPECTED_CONFIG_SHA",
  "requirements_sha256": "$EXPECTED_REQUIREMENTS_SHA",
  "lock_sha256": "$EXPECTED_LOCK_SHA",
  "glsim_compatibility_shim_sha256": "$COMPAT_SHA",
  "bradbury_write": false,
  "auto_resubmission": false
}
EOF

MANIFEST_SHA="$(
  shasum -a 256 \
    "$FINAL_ARTIFACT_DIR/manifest.json" |
    awk '{print $1}'
)"

RUNNER_RUNTIME_SHA="$(
  shasum -a 256 \
    "$FINAL_ARTIFACT_DIR/runner-runtime.json" |
    awk '{print $1}'
)"

echo
echo "EVIDENCEGATE_SUPPORTED_RUNTIME_EXECUTION=PASS"
echo "ARTIFACT_DIR=$FINAL_ARTIFACT_DIR"
echo "MANIFEST_SHA256=$MANIFEST_SHA"
echo "RUNNER_RUNTIME_SHA256=$RUNNER_RUNTIME_SHA"
echo "BRADBURY_TRANSACTION_SUBMITTED=NO"
