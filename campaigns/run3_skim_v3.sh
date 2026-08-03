#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  campaigns/run3_skim_v3.sh [dry-run|submit|check] [options]

Modes:
  dry-run  Resolve DAS inputs, create chunk manifests, and print jobs (default).
  submit   Submit all missing skim_v3 chunks to HTCondor, era by era.
  check    Check ROOT/report pairs using the saved chunk manifests.

Options:
  --era ERA              Run only one era (repeatable).
  --max-submit-jobs N    Limit submitted jobs per era (submit only).
  --proxy PATH            Use this user's VOMS proxy.
  --output-dir PATH       Override the configured skim_v3 output directory.
  -h, --help             Show this help.

Default eras:
  Run3_2022 Run3_2022EE Run3_2023 Run3_2023BPix
  Run3_2024 Run3_2025 Run3_2026
EOF
}

mode="dry-run"
if [[ $# -gt 0 && "$1" != -* ]]; then
  mode="$1"
  shift
fi

case "$mode" in
  dry-run|submit|check) ;;
  *)
    echo "[ERROR] Unknown mode: $mode" >&2
    usage >&2
    exit 2
    ;;
esac

default_eras=(
  Run3_2022
  Run3_2022EE
  Run3_2023
  Run3_2023BPix
  Run3_2024
  Run3_2025
  Run3_2026
)
eras=()
max_submit_jobs=""
proxy_path=""
output_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --era)
      eras+=("$2")
      shift 2
      ;;
    --max-submit-jobs)
      max_submit_jobs="$2"
      shift 2
      ;;
    --proxy)
      proxy_path="$2"
      shift 2
      ;;
    --output-dir)
      output_dir="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${#eras[@]} -eq 0 ]]; then
  eras=("${default_eras[@]}")
fi


analysis_path="${ANALYSIS_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$analysis_path"

echo "[CAMPAIGN] mode=$mode"
echo "[CAMPAIGN] eras=${eras[*]}"
echo "[CAMPAIGN] output=skim_v3"
echo "[CAMPAIGN] chunking=5 GiB, at most 5 NanoAOD files"

common_opts=()
if [[ -n "$proxy_path" ]]; then
  common_opts+=(--proxy "$proxy_path")
fi
if [[ -n "$output_dir" ]]; then
  common_opts+=(--output-dir "$output_dir")
fi

for era in "${eras[@]}"; do
  echo
  echo "[ERA] $era"

  case "$mode" in
    dry-run)
      python3 htcondor/condorsubmit.py \
        --era "$era" \
        --no-submit \
        "${common_opts[@]}"
      ;;
    submit)
      submit_opts=()
      if [[ -n "$max_submit_jobs" ]]; then
        submit_opts+=(--max-submit-jobs "$max_submit_jobs")
      fi
      python3 htcondor/condorsubmit.py \
        --era "$era" \
        --submit \
        "${common_opts[@]}" \
        "${submit_opts[@]}"
      ;;
    check)
      python3 htcondor/check_missing_files.py \
        --era "$era" \
        --only-missing
      ;;
  esac
done
