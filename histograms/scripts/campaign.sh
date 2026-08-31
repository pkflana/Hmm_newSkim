#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo}"
export ANALYSIS_PATH="${ANALYSIS_PATH:-${repo}}"

usage() {
  cat <<'EOF'
Usage: campaign.sh CONFIG ACTION [ERA]

Actions:
  submit       submit configured histogram jobs to Condor
  resubmit     force Condor submission even when output ROOT files exist
  local        run configured histogram jobs locally
  hadd         hadd datasets into physics-process ROOT files
  plan-hadd    inspect available/missing hadd inputs without writing files
  rehadd       rebuild physics-process ROOT files even when they exist
  merge-syst   merge Central and configured systematic outputs
  merge-eras   merge the configured eras into MERGED_ERA
  fit          run the optional campaign_fit function from CONFIG
  paths        print resolved campaign paths

ERA is optional for submit, local and hadd (example: 2022 or Run3_2022).
EOF
}

[[ $# -ge 2 ]] || { usage >&2; exit 2; }
config="$1"
action="$2"
only_era="${3:-}"
[[ -f "${config}" ]] || { echo "[ERROR] Config not found: ${config}" >&2; exit 2; }

# shellcheck source=/dev/null
source "${config}"

# Optional one-shot restriction without editing the campaign configuration.
# Example: CAMPAIGN_DATASETS_OVERRIDE=DY_amcatnlo campaign.sh ... resubmit 2022EE
DATASETS="${CAMPAIGN_DATASETS_OVERRIDE:-${DATASETS:-}}"

: "${CAMPAIGN_ROOT:?CONFIG must define CAMPAIGN_ROOT}"
: "${CAMPAIGN_LABEL:?CONFIG must define CAMPAIGN_LABEL}"
: "${DATASETS:?CONFIG must define DATASETS}"

ERAS=("${ERAS[@]:-2022 2022EE 2023 2023BPix 2024 2025}")
SYSTEMATICS=("${SYSTEMATICS[@]:-Central}")
HIST_ARGS=("${HIST_ARGS[@]:-}")
REQUEST_CPUS="${REQUEST_CPUS:-4}"
REQUEST_MEMORY="${REQUEST_MEMORY:-20GB}"
RDF_THREADS="${RDF_THREADS:-${REQUEST_CPUS}}"
VARIABLE_BATCH_SIZE="${VARIABLE_BATCH_SIZE:-64}"
CHUNK_SIZE="${CHUNK_SIZE:-1}"
MANIFEST_INPUT="${MANIFEST_INPUT:-/eos/user/v/vdamante/H_mumu/manifests_skim_v3}"
ROOT_INPUT="${ROOT_INPUT:-/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3}"
JSON_INPUT="${JSON_INPUT:-${ROOT_INPUT}}"
HIST_DIR_PREFIX="${HIST_DIR_PREFIX-Hists_}"

has_hist_arg() {
  local wanted="$1" arg
  for arg in "${HIST_ARGS[@]}"; do
    [[ "${arg}" == "${wanted}" || "${arg}" == "${wanted}="* ]] && return 0
  done
  return 1
}

# Shared performance policy. Campaigns can override the variables above or
# provide either hist_maker option explicitly in HIST_ARGS.
has_hist_arg --rdf-threads || HIST_ARGS+=(--rdf-threads "${RDF_THREADS}")
has_hist_arg --variable-batch-size || HIST_ARGS+=(--variable-batch-size "${VARIABLE_BATCH_SIZE}")

normalize_era() {
  local era="$1"
  [[ "${era}" == Run3_* ]] && printf '%s' "${era}" || printf 'Run3_%s' "${era}"
}

selected_eras() {
  local era
  if [[ -n "${only_era}" ]]; then
    normalize_era "${only_era}"
    echo
    return
  fi
  for era in "${ERAS[@]}"; do normalize_era "${era}"; echo; done
}

hist_dir() { printf '%s/%s%s' "${CAMPAIGN_ROOT}" "${HIST_DIR_PREFIX}" "$1"; }
hadded_dir() { printf '%s/%s%s_hadded' "${CAMPAIGN_ROOT}" "${HIST_DIR_PREFIX}" "$1"; }

produce() {
  local mode="$1" systematic era wrapper
  while IFS= read -r era; do
    [[ -n "${era}" ]] || continue
    for systematic in "${SYSTEMATICS[@]}"; do
      wrapper="histograms/scripts/hists.sh"
      [[ "${systematic}" == Central ]] || wrapper="histograms/scripts/systematics.sh"
      cmd=(bash "${wrapper}"
        --era "${era}"
        --datasets "${DATASETS}"
        --manifest-input-folder "${MANIFEST_INPUT}"
        --root-input-folder "${ROOT_INPUT}"
        --json-input-folder "${JSON_INPUT}"
        --output-dir "$(hist_dir "${systematic}")"
        --systematics "${systematic}"
        --chunk-size "${CHUNK_SIZE}"
        --missing-only
        --condor-label "${CAMPAIGN_LABEL}_${systematic}"
        --request-cpus "${REQUEST_CPUS}"
        --request-memory "${REQUEST_MEMORY}")
      if [[ "${mode}" == submit || "${mode}" == resubmit ]]; then
        cmd+=(--condor)
      fi
      [[ "${mode}" == resubmit ]] && cmd+=(--force)
      cmd+=(-- "${HIST_ARGS[@]}")
      echo "[${mode^^}] ${era} ${systematic}"
      "${cmd[@]}"
    done
  done < <(selected_eras)
}

hadd_outputs() {
  local mode="$1" systematic eras_csv era
  if [[ "${mode}" == plan ]]; then
    while IFS= read -r era; do
      [[ -n "${era}" ]] || continue
      for systematic in "${SYSTEMATICS[@]}"; do
        python3 histograms/hadd_hists_to_processes.py \
          --input-dir "$(hist_dir "${systematic}")/${era}" \
          --output-dir "$(hadded_dir "${systematic}")/${era}" \
          --era "${era}" --dryRun
      done
    done < <(selected_eras)
    return
  fi
  eras_csv="$(selected_eras | paste -sd, -)"
  for systematic in "${SYSTEMATICS[@]}"; do
    cmd=(python3 tools/hmumu.py hadd-processes "$(hist_dir "${systematic}")"
      --era "${eras_csv}" --output-dir "$(hadded_dir "${systematic}")")
    [[ "${mode}" == missing ]] && cmd+=(--missing-only)
    cmd+=(--run)
    "${cmd[@]}"
  done
}

merge_systematics() {
  local eras_csv sources=() systematic
  eras_csv="$(selected_eras | paste -sd, -)"
  for systematic in "${SYSTEMATICS[@]}"; do
    [[ "${systematic}" == Central ]] && continue
    sources+=(--source-dir "$(hadded_dir "${systematic}")")
  done
  ((${#sources[@]})) || { echo "[ERROR] No non-Central SYSTEMATICS configured" >&2; exit 2; }
  python3 tools/hmumu.py merge-systematics "$(hadded_dir Central)" \
    --era "${eras_csv}" "${sources[@]}" \
    --output-dir "${CAMPAIGN_ROOT}/Hists_systMerged" --run
}

merge_eras() {
  : "${MERGED_ERA:?CONFIG must define MERGED_ERA for merge-eras}"
  local systematic eras_csv
  eras_csv="$(selected_eras | paste -sd, -)"
  for systematic in "${SYSTEMATICS[@]}"; do
    python3 tools/hmumu.py merge-eras "$(hadded_dir "${systematic}")" \
      --eras "${eras_csv}" --output-era "${MERGED_ERA}" --run
  done
}

case "${action}" in
  submit) produce submit ;;
  resubmit) produce resubmit ;;
  local) produce local ;;
  hadd) hadd_outputs missing ;;
  plan-hadd) hadd_outputs plan ;;
  rehadd) hadd_outputs rebuild ;;
  merge-syst) merge_systematics ;;
  merge-eras) merge_eras ;;
  fit)
    declare -F campaign_fit >/dev/null || {
      echo "[ERROR] CONFIG does not define campaign_fit" >&2; exit 2;
    }
    campaign_fit "${only_era}"
    ;;
  paths)
    echo "CAMPAIGN_ROOT=${CAMPAIGN_ROOT}"
    echo "REQUEST_CPUS=${REQUEST_CPUS}"
    echo "REQUEST_MEMORY=${REQUEST_MEMORY}"
    echo "RDF_THREADS=${RDF_THREADS}"
    echo "VARIABLE_BATCH_SIZE=${VARIABLE_BATCH_SIZE}"
    for systematic in "${SYSTEMATICS[@]}"; do
      echo "${systematic}: $(hist_dir "${systematic}") -> $(hadded_dir "${systematic}")"
    done
    ;;
  *) usage >&2; exit 2 ;;
esac
