#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS_PATH="${ANALYSIS_PATH:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
export ANALYSIS_PATH
cd "${ANALYSIS_PATH}"

MODE="${1:---dry-run}"
VARIABLE="${VARIABLE:-m_jj}"
N_CORES="${N_CORES:-4}"
OUTPUT_DIR="${OUTPUT_DIR:-/eos/user/v/vdamante/H_mumu/newHists_Run3_2024_${VARIABLE}_fullSyst_ptllNJetsRW}"
INPUT_FOLDER="${INPUT_FOLDER:-skim_v2_noUnc}"

PTLL_REWEIGHT="reweights/dy_ptll_reweight/Run3_2024/dy_ptll_reweight_smart.json"
NJETS_REWEIGHT="reweights/dy_njets_reweight/Run3_2024/dy_njets_reweight.json"

MASS_REGIONS=(
  Z_sideband
  Signal_Fit
  H_sideband
  Signal_ext
  mass_inclusive
)

CATEGORIES=(
  base_sel
  baseline
  baseline_chi2
  VBF_def
  VBF
  ggF
  ggF_0J
  ggF_1J
  ggF_ge2J
  VBF_ge2J
)

[[ -r "${PTLL_REWEIGHT}" ]] || {
  echo "[ERROR] Missing pt(ll) reweight payload: ${PTLL_REWEIGHT}" >&2
  exit 1
}
[[ -r "${NJETS_REWEIGHT}" ]] || {
  echo "[ERROR] Missing NJets reweight payload: ${NJETS_REWEIGHT}" >&2
  exit 1
}

set --
source "${ANALYSIS_PATH}/env.sh"

REFERENCE_INPUT_DIR="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/${INPUT_FOLDER}/Run3_2024/VBFHto2Mu_M125_powheg"
REFERENCE_FILE="$(find "${REFERENCE_INPUT_DIR}" -maxdepth 1 -name '*.root' 2>/dev/null | sort | head -1 || true)"

preflight_status=0
if [[ -z "${REFERENCE_FILE}" ]]; then
  echo "[ERROR] No reference ROOT file found under ${REFERENCE_INPUT_DIR}" >&2
  preflight_status=1
else
  if ! python3 - "${REFERENCE_FILE}" <<'PY'
import sys
import uproot

required = {
    "SelectedJet_pt_JERup",
    "SelectedJet_pt_JERdown",
    "SelectedJet_pt_JESTotalup",
    "SelectedJet_pt_JESTotaldown",
    "weight_pu_up",
    "weight_pu_down",
    "weight_mu1_MediumID_Trk_up",
    "weight_mu1_MediumID_Trk_down",
}

with uproot.open(sys.argv[1]) as root_file:
    columns = set(root_file["Events"].keys())

missing = sorted(required - columns)
if missing:
    print("[ERROR] Input skim production does not contain required variations:")
    for column in missing:
        print(f"  - {column}")
    raise SystemExit(1)

print(f"[INFO] Variation preflight passed with: {sys.argv[1]}")
PY
  then
    preflight_status=1
  fi
fi

if [[ ${preflight_status} -ne 0 ]]; then
  if [[ "${MODE}" == "--dry-run" ]]; then
    echo "[WARNING] Dry-run continues, but --pilot/--run will require a variation-enabled INPUT_FOLDER."
  else
    echo "[ERROR] Refusing to start an invalid systematic campaign." >&2
    echo "[ERROR] Set INPUT_FOLDER to the Run3_2024 skim production made with want_variations=true." >&2
    exit 1
  fi
fi

campaign_args=(
  --era Run3_2024
  --input-folder "${INPUT_FOLDER}"
  --output-dir "${OUTPUT_DIR}"
  --missing-only
)

case "${MODE}" in
  --dry-run)
    campaign_args+=(--dry-run --datasets all)
    ;;
  --pilot)
    campaign_args+=(--dataset-name VBFHto2Mu_M125_powheg)
    ;;
  --run)
    campaign_args+=(--datasets all)
    ;;
  *)
    echo "Usage: $0 [--dry-run|--pilot|--run]" >&2
    exit 2
    ;;
esac

hist_maker_args=(
  --variables "${VARIABLE}"
  --systematics all
  --mass-regions "${MASS_REGIONS[@]}"
  --categories "${CATEGORIES[@]}"
  --dy-ptll-njets-reweight-json "${PTLL_REWEIGHT}"
  --dy-njets-reweight-json "${NJETS_REWEIGHT}"
  --n-cores "${N_CORES}"
  --skip-file-validation
)

echo "[INFO] Run3_2024 local histogram campaign"
echo "[INFO] Mode       : ${MODE}"
echo "[INFO] Variable   : ${VARIABLE}"
echo "[INFO] Input      : ${INPUT_FOLDER}"
echo "[INFO] Output     : ${OUTPUT_DIR}"
echo "[INFO] Systematics: all"
echo "[INFO] pt(ll) RW  : ${PTLL_REWEIGHT}"
echo "[INFO] NJets RW   : ${NJETS_REWEIGHT}"

exec histograms/scripts/hists.sh \
  "${campaign_args[@]}" \
  -- \
  "${hist_maker_args[@]}"
