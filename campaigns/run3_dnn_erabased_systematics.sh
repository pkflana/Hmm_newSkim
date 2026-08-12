#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPOSITORY}"

ERAS="${ERAS:-2022,2022EE,2023,2023BPix,2024,2025}"
SYSTEMATICS="${SYSTEMATICS:-JERC,ScaRe,Muon,PU,QCDScale,PDF}"
INPUT_DIR="${INPUT_DIR:-/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3}"
MANIFESTS="${MANIFESTS:-/eos/user/gtv/vdamante/H_mumu/manifests_skim_v3}"
OUTPUT_BASE="${OUTPUT_BASE:-/eos/user/v/vdamante/H_mumu/Hists_DNN_erabased_systematics}"

MODE="${1:-plan}"
case "${MODE}" in
    plan|run|check) ;;
    *)
        echo "Usage: $0 [plan|run|check]" >&2
        exit 2
        ;;
esac

command=(
    python3 tools/hmumu.py hist
    -e "${ERAS}"
    -s "${SYSTEMATICS}"
    --input-dir "${INPUT_DIR}"
    --manifests "${MANIFESTS}"
    --output-base "${OUTPUT_BASE}"
    --datasets DiTriBoson,DY_amcatnlo,DY_amcatnlo_105_160,EWK,signals,SingleH,SingleTop,TTX,TT,W
    -v DNN_NNOutput
    -r Signal_Fit
    -c VBF
    --chunk-size 1
    --condor
    --missing-only
)

case "${MODE}" in
    run) command+=(--run) ;;
    check) command+=(--check) ;;
esac

"${command[@]}"
