#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  campaigns/run3_region_routed_backgrounds.sh \
    [plan|submit|local|hadd-plan|hadd] [--era ERA]

Environment overrides:
  SKIM_BASE       Skim base (default: shared skim_v3)
  MANIFEST_BASE   Validation-manifest base
  OUTPUT_BASE     Histogram output base
  SYSTEMATICS     Comma-separated systematics (default: Central)
  EXTRA_HIST_OPTS Additional hist_maker.py options, e.g. variables/categories

The campaign automatically uses:
  Signal_Fit       mass-binned DY and EWK
  Z/H sidebands    generic DY and EWK
  DY012J           generator-binned DY 0J, 1J, and 2J in separate outputs
EOF
}

mode="${1:-plan}"
[[ $# -eq 0 ]] || shift
case "$mode" in
  plan|submit|local|hadd-plan|hadd) ;;
  -h|--help) usage; exit 0 ;;
  *) echo "[ERROR] Invalid mode: $mode" >&2; usage >&2; exit 2 ;;
esac

eras=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --era) eras+=("$2"); shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ ${#eras[@]} -eq 0 ]]; then
  eras=(
    Run3_2022 Run3_2022EE Run3_2023 Run3_2023BPix
    Run3_2024 Run3_2025 Run3_2026
  )
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
export ANALYSIS_PATH="${ANALYSIS_PATH:-$repo_dir}"

skim_base="${SKIM_BASE:-/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3}"
manifest_base="${MANIFEST_BASE:-/eos/user/v/vdamante/H_mumu/manifests_skim_v3}"
output_base="${OUTPUT_BASE:-/eos/user/v/vdamante/H_mumu/campaigns/RegionRouted}"
systematics="${SYSTEMATICS:-Central}"
extra_hist_opts="${EXTRA_HIST_OPTS:-}"
component_processes="$(
  python3 tools/resolve_region_sample_routing.py \
    --era "${eras[0]}" --field processes
)"
component_processes="${component_processes//,/ }"

run_stage() {
  local era="$1"
  local label="$2"
  local groups="$3"
  local regions="$4"
  local stage_opts="--jet-gen-components --jet-gen-component-processes $component_processes --mass-regions $regions"
  if [[ -n "$extra_hist_opts" ]]; then
    stage_opts+=" $extra_hist_opts"
  fi
  local command=(
    bash histograms/scripts/hists.sh
    --era "$era"
    --datasets "$groups"
    --root-input-folder "$skim_base"
    --json-input-folder "$skim_base"
    --manifest-input-folder "$manifest_base"
    --output-dir "$output_base/$label"
    --systematics "$systematics"
    --chunk-size 1
    --extra-opts
    "$stage_opts"
  )
  case "$mode" in
    plan) command+=(--condor --dry-run) ;;
    submit) command+=(--condor) ;;
    local) ;;
  esac
  echo "[ROUTING] era=$era output=$label groups=$groups regions=$regions"
  "${command[@]}"
}

hadd_stage() {
  local era="$1"
  local label="$2"
  local command=(
    ./hmumu hadd-processes
    "$output_base/$label"
    --era "$era"
    --output-dir "$output_base/${label}_hadded"
  )
  [[ "$mode" == "hadd" ]] && command+=(--run)
  echo "[HADD] era=$era input=$label output=${label}_hadded"
  "${command[@]}"
}

for era in "${eras[@]}"; do
  if [[ "$mode" == "hadd-plan" || "$mode" == "hadd" ]]; then
    hadd_stage "$era" Signal_Fit
    hadd_stage "$era" Sidebands
    # hadd_stage "$era" DY012J
    continue
  fi
  signal_groups="$(
    python3 tools/resolve_region_sample_routing.py \
      --era "$era" --region Signal_Fit
  )"
  sideband_groups="$(
    python3 tools/resolve_region_sample_routing.py \
      --era "$era" --region sidebands
  )"
  separate_groups="$(
    python3 tools/resolve_region_sample_routing.py \
      --era "$era" --region separate
  )"

  # run_stage "$era" Signal_Fit "$signal_groups" "Signal_Fit"
  run_stage "$era" Sidebands "$sideband_groups" "Z_sideband H_sideband"
  # run_stage "$era" DY012J "$separate_groups" "Signal_Fit Z_sideband H_sideband"
done
