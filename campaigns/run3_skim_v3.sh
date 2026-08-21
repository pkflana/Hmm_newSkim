#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: campaigns/run3_skim_v3.sh {status|dry-run|submit|check} [options]

Modes:
  status   Compare configured datasets with manifests, submission logs and outputs.
  dry-run  Resolve inputs and show missing jobs without submitting.
  submit   Submit missing skim_v3 chunks to HTCondor, era by era.
  check    Run the detailed ROOT/report output checker.

Options:
  --era ERA              Run one era (repeatable; accepts 2025 or Run3_2025).
  --max-submit-jobs N    Limit submitted jobs per era.
  --max-parallel-jobs N  Limit concurrently active jobs.
  --proxy PATH            Override the VOMS proxy.
  --output-dir PATH       Override the skim output directory.
  -d, --dataset NAME      Process one exact dataset (repeatable).

Default eras: 2022 2022EE 2023 2023BPix 2024 2025 2026
EOF
}

mode="${1:-status}"
[[ $# -gt 0 ]] && shift
case "$mode" in status|dry-run|submit|check) ;; *) usage >&2; exit 2;; esac

default_eras=(2022 2022EE 2023 2023BPix 2024 2025 2026)
eras=(); datasets=(); common=(); max_submit=""; max_parallel=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --era) eras+=("$2"); shift 2;;
    -d|--dataset) datasets+=("$2"); shift 2;;
    --max-submit-jobs) max_submit="$2"; shift 2;;
    --max-parallel-jobs) max_parallel="$2"; shift 2;;
    --proxy|--output-dir) common+=("$1" "$2"); shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "[ERROR] Unknown option: $1" >&2; usage >&2; exit 2;;
  esac
done
[[ ${#eras[@]} -gt 0 ]] || eras=("${default_eras[@]}")

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
for dataset in "${datasets[@]}"; do common+=(--dataset "$dataset"); done

for requested_era in "${eras[@]}"; do
  [[ $requested_era == Run3_* ]] && era="$requested_era" || era="Run3_$requested_era"
  echo "[CAMPAIGN] mode=$mode era=$era"
  case "$mode" in
    status)
      python3 tools/check_skim_campaign_status.py --era "$era"
      ;;
    dry-run)
      python3 htcondor/condorsubmit.py skim --era "$era" --no-submit "${common[@]}"
      ;;
    submit)
      opts=()
      [[ -n $max_submit ]] && opts+=(--max-submit-jobs "$max_submit")
      [[ -n $max_parallel ]] && opts+=(--max-parallel-jobs "$max_parallel")
      python3 htcondor/condorsubmit.py skim --era "$era" --submit "${common[@]}" "${opts[@]}"
      ;;
    check)
      python3 htcondor/check_missing_files.py --era "$era" --only-missing
      ;;
  esac
done
