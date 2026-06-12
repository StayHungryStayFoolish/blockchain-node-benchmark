#!/usr/bin/env bash
# tests/test_cloud_provider_detect.sh
# Mock-based unit test for config/cloud_provider.sh : detect_platform()
#
# Verifies GCP / AWS / other detection, including proxy or metadata poisoning.
# Usage: bash tests/test_cloud_provider_detect.sh
# Exit code: 0 when all cases pass, non-zero on failure.

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CP_SH="${PROJECT_ROOT}/config/cloud_provider.sh"

if [[ ! -f "$CP_SH" ]]; then
    echo "FATAL: cannot locate $CP_SH" >&2
    exit 2
fi

PASS=0
FAIL=0
declare -a FAILURES=()

# ---------------------------------------------------------------------------
# Each case runs in a subshell with a curl dispatcher selected by MOCK_MODE.
# ---------------------------------------------------------------------------

curl() {
    local args="$*"
    case "$MOCK_MODE" in
      gcp_happy)
          if [[ "$args" == *metadata.google.internal* ]]; then
              echo "7583017767800978370"; return 0
          fi
          return 7
          ;;
      aws_happy)
          if [[ "$args" == *metadata.google.internal* ]]; then return 7; fi
          if [[ "$args" == *169.254.169.254/latest/api/token* ]]; then
              echo "AQAEAFakeToken1234567890=="; return 0
          fi
          if [[ "$args" == *169.254.169.254/latest/meta-data/instance-id* ]]; then
              echo "i-0abc123def4567890"; return 0
          fi
          return 7
          ;;
      aws_bare_metadata_rejected)
          if [[ "$args" == *metadata.google.internal* ]]; then return 7; fi
          if [[ "$args" == *169.254.169.254/latest/api/token* ]]; then return 7; fi
          if [[ "$args" == *169.254.169.254/latest/meta-data/instance-id* ]]; then
              echo "i-0abc123def4567890"; return 0
          fi
          return 7
          ;;
      other_none)
          return 7
          ;;
      gcp_priority_over_poisoned_aws)
          if [[ "$args" == *metadata.google.internal* ]]; then
              echo "7583017767800978370"; return 0
          fi
          if [[ "$args" == *169.254.169.254* ]]; then
              echo "<html><body>Proxy error</body></html>"; return 0
          fi
          return 7
          ;;
      other_html_poisoned_all)
          if [[ "$args" == *metadata.google.internal* ]]; then
              echo "<html>blocked</html>"; return 0
          fi
          if [[ "$args" == *169.254.169.254* ]]; then
              echo "<html>blocked</html>"; return 0
          fi
          return 7
          ;;
      gcp_empty_body)
          if [[ "$args" == *metadata.google.internal* ]]; then
              echo -n ""; return 0
          fi
          return 7
          ;;
      *)
          echo "MOCK_MODE not set" >&2
          return 99
          ;;
    esac
}

ip() { echo "default via 10.0.0.1 dev eth0"; }
ethtool() { echo "driver: virtio_net"; }
export -f curl ip ethtool

run_case() {
    local case_name="$1"
    local mock_mode="$2"     # matches dispatch_curl case labels
    local expected="$3"

    local actual
    actual=$(
        export MOCK_MODE="$mock_mode"

        # --- Clean env to avoid short-circuiting detection. ---
        unset CLOUD_PROVIDER NIC_DRIVER CLOUD_PROVIDER_VARIANT NETWORK_INTERFACE

        # Sourcing runs detect_cloud_provider once; detect_platform is called below.
        # shellcheck disable=SC1090
        source "$CP_SH" >/dev/null 2>&1
        detect_platform
    )

    if [[ "$actual" == "$expected" ]]; then
        echo "  ✅ PASS  [$case_name]  detect_platform → '$actual'"
        PASS=$((PASS+1))
    else
        echo "  ❌ FAIL  [$case_name]  expected='$expected'  actual='$actual'"
        FAIL=$((FAIL+1))
        FAILURES+=("$case_name")
    fi
}

echo "============================================================"
echo "  cloud_provider.sh :: detect_platform() unit tests"
echo "============================================================"

run_case "GCP-happy-path"                       "gcp_happy"                       "gcp"
run_case "AWS-IMDSv2-happy-path"                "aws_happy"                       "aws"
run_case "AWS-bare-metadata-request-rejected"   "aws_bare_metadata_rejected"      "other"
run_case "Other-no-metadata"                    "other_none"                      "other"
run_case "GCP-priority-over-poisoned-AWS"       "gcp_priority_over_poisoned_aws"  "gcp"
run_case "Other-rejects-HTML-poisoned-AWS-meta" "other_html_poisoned_all"         "other"
run_case "GCP-empty-body-falls-through"         "gcp_empty_body"                  "other"

echo "============================================================"
echo "  Result: PASS=$PASS  FAIL=$FAIL"
if [[ $FAIL -gt 0 ]]; then
    echo "  Failed cases:"
    for f in "${FAILURES[@]}"; do echo "    - $f"; done
    exit 1
fi
echo "  ALL TESTS PASSED ✅"
exit 0
