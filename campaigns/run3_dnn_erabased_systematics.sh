#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPOSITORY}"

ERAS="${ERAS:-2022,2022EE,2023,2023BPix,2024,2025}"
SYSTEMATICS="${SYSTEMATICS:-JERC,ScaRe,Muon,PU,QCDScale,PDF}"
INPUT_DIR="${INPUT_DIR:-/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3}"
MANIFESTS="${MANIFESTS:-/eos/user/v/vdamante/H_mumu/manifests_skim_v3}"
OUTPUT_BASE="${OUTPUT_BASE:-/eos/user/v/vdamante/H_mumu/Hists_DNN_erabased_systematics}"
CENTRAL_OUTPUT="${CENTRAL_OUTPUT:-/eos/user/v/vdamante/H_mumu/Hists_DNN_erabased}"
EXECUTION="${EXECUTION:-condor}"
MISSING_ONLY=1
INTERVAL="${INTERVAL:-300}"

usage() {
    cat <<'EOF'
Usage:
  campaigns/run3_dnn_erabased_systematics.sh [plan|run|check|monitor] [options]

Options:
  -e, --eras ERAS              comma-separated eras
  -s, --systematics SYSTS      comma-separated systematic groups
  --local                      run locally
  --condor                     submit to HTCondor (default)
  --missing-only               skip completed outputs (default)
  --no-missing-only            also rerun completed outputs
  --interval SECONDS           monitor interval (default: 300)
  --input-dir PATH             skim input base
  --manifests PATH             validation-manifest base
  -o, --output-base PATH       output base
  --central-output PATH        direct output directory for Central
  -h, --help                   show this help

Example:
  ... run -e 2023 -s JERC --local --missing-only
  ... monitor -e 2022,2023 -s JERC,Muon --condor --interval 300
EOF
}

MODE="plan"
if [[ $# -gt 0 && "$1" != -* ]]; then
    MODE="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--eras)
            ERAS="$2"
            shift 2
            ;;
        -s|--systematics)
            SYSTEMATICS="$2"
            shift 2
            ;;
        --local)
            EXECUTION="local"
            shift
            ;;
        --condor)
            EXECUTION="condor"
            shift
            ;;
        --missing-only)
            MISSING_ONLY=1
            shift
            ;;
        --no-missing-only)
            MISSING_ONLY=0
            shift
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --input-dir)
            INPUT_DIR="$2"
            shift 2
            ;;
        --manifests)
            MANIFESTS="$2"
            shift 2
            ;;
        -o|--output-base)
            OUTPUT_BASE="$2"
            shift 2
            ;;
        --central-output)
            CENTRAL_OUTPUT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "${EXECUTION}" in
    condor|local) ;;
    *)
        echo "EXECUTION must be 'condor' or 'local'" >&2
        exit 2
        ;;
esac

if ! [[ "${INTERVAL}" =~ ^[1-9][0-9]*$ ]]; then
    echo "--interval must be a positive integer" >&2
    exit 2
fi

if [[ "${SYSTEMATICS,,}" == "central" ]]; then
    DATASETS="skim_cfg"
elif [[ ",${SYSTEMATICS,,}," == *,central,* ]]; then
    echo "Run Central separately from shifted systematics: Central includes data, shifted systematics do not." >&2
    exit 2
else
    DATASETS="DiTriBoson,DY_amcatnlo,DY_amcatnlo_105_160,EWK,signals,SingleH,SingleTop,TTX,TT,W"
fi

case "${MODE}" in
    plan|run|check|monitor) ;;
    *)
        usage >&2
        exit 2
        ;;
esac

command=(
    python3 tools/hmumu.py hist
    -e "${ERAS}"
    -s "${SYSTEMATICS}"
    --input-dir "${INPUT_DIR}"
    --manifests "${MANIFESTS}"
    --datasets "${DATASETS}"
    -v DNN_NNOutput
    -r Signal_Fit
    -c VBF
    --chunk-size 1
    --${EXECUTION}
)

if [[ "${SYSTEMATICS,,}" == "central" ]]; then
    command+=(--output-dir "${CENTRAL_OUTPUT}")
else
    command+=(--output-base "${OUTPUT_BASE}")
fi

if [[ ${MISSING_ONLY} -eq 1 ]]; then
    command+=(--missing-only)
else
    command+=(--no-missing-only)
fi

case "${MODE}" in
    run) command+=(--run) ;;
    check) command+=(--check) ;;
    monitor) command+=(--run) ;;
esac

if [[ "${MODE}" == "monitor" ]]; then
    if [[ "${EXECUTION}" != "condor" ]]; then
        echo "monitor mode requires --condor" >&2
        exit 2
    fi
    echo "[MONITOR] Continuous missing-output resubmission every ${INTERVAL}s"
    echo "[MONITOR] Stop with Ctrl-C"
    while true; do
        echo
        echo "[MONITOR] Pass started at $(date --iso-8601=seconds)"
        "${command[@]}"
        echo "[MONITOR] Next pass in ${INTERVAL}s"
        sleep "${INTERVAL}"
    done
else
    "${command[@]}"
fi
