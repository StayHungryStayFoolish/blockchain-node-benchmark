#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source monitoring/lib/cloud_provider_resolver.sh

get_provider_name() {
    echo "gcp"
}

export CLOUD_PROVIDER="aws"
out="$(resolve_cloud_provider_value)"
[[ "$out" == "gcp" ]] || {
    echo "Getter should win over CLOUD_PROVIDER: $out"
    exit 1
}

unset -f get_provider_name
out="$(resolve_cloud_provider_value)"
[[ "$out" == "aws" ]] || {
    echo "CLOUD_PROVIDER fallback mismatch: $out"
    exit 1
}

unset CLOUD_PROVIDER
out="$(resolve_cloud_provider_value)"
[[ "$out" == "unknown" ]] || {
    echo "unknown fallback mismatch: $out"
    exit 1
}

echo "✅ cloud_provider_resolver resolves provider value"
