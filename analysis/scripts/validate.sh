#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS_PATH="${ANALYSIS_PATH:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
export ANALYSIS_PATH
exec "${ANALYSIS_PATH}/common/scripts/dataset_campaign.sh" \
  --campaign-mode validation "$@"
