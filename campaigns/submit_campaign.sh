#!/bin/sh
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -euo pipefail
repo="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo"
export ANALYSIS_PATH="$repo"
if [ "$#" -eq 0 ]; then
    echo 'Usage: submit_campaign.sh CONFIG.sh [ACTION] [OPTIONS...]' >&2
    exit 2
fi
config="$1"
shift
case "$config" in
    *.sh)
        # Per-campaign workflow defaults precede command-line overrides.
        CAMPAIGN_OPTIONS=()
        source "$config"
        exec python3 -u campaigns/workflow.py generic --config "$config" "${CAMPAIGN_OPTIONS[@]}" "$@"
        ;;
    *) exec python3 -u campaigns/workflow.py "$config" "$@" ;;
esac
