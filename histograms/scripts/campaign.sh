#!/usr/bin/env bash
# Compatibility interface: workflow implementation lives in submit_campaign.sh.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"
[[ $# -ge 2 ]] || { echo 'Usage: campaign.sh CONFIG ACTION [ERA] [OPTIONS...]' >&2; exit 2; }
config="$1"
action="$2"
shift 2
source "$config"
options=()
if [[ $# -gt 0 && "$1" != --* ]]; then options+=(--eras "$1"); shift; fi
case "$action" in
  resubmit) action=submit; options+=(--force) ;;
  rehadd) action=hadd ;;
  plan-hadd) action=hadd; options+=(--dry-run) ;;
  fit)
    declare -F campaign_fit >/dev/null || { echo 'Config does not define campaign_fit' >&2; exit 2; }
    campaign_fit "${options[1]:-}"
    exit
    ;;
esac
mode=syst
for family in "${SYSTEMATICS[@]}"; do
  if [[ "$family" == Central ]]; then
    mode=both
    [[ ${#SYSTEMATICS[@]} -gt 1 ]] || mode=central
  fi
done
if [[ -n "${CAMPAIGN_DATASETS_OVERRIDE:-}" ]]; then options+=(--datasets "$CAMPAIGN_DATASETS_OVERRIDE"); fi
if [[ -n "${CAMPAIGN_SYSTEMATICS_OVERRIDE:-}" ]]; then
  if [[ "$CAMPAIGN_SYSTEMATICS_OVERRIDE" == Central ]]; then mode=central
  else mode=syst; options+=(--families "$CAMPAIGN_SYSTEMATICS_OVERRIDE"); fi
fi
exec sh campaigns/submit_campaign.sh "$config" "$action" --mode "$mode" --jes total "${options[@]}" "$@"
