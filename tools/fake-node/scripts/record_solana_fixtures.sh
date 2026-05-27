#!/bin/bash
# record_solana_fixtures.sh — fetch Solana mainnet response samples for fake-node fixtures.
#
# Reuses tools/proxy/poc-min/scripts/record_fixtures.sh logic.
# Writes to tools/fake-node/fixtures/ by default.
#
# Run once after clone; fixtures are .gitignored and recorded on demand.

set -euo pipefail

OUT_DIR="${1:-$(dirname "$0")/../fixtures}"
exec bash "$(dirname "$0")/../../proxy/poc-min/scripts/record_fixtures.sh" "$OUT_DIR"
