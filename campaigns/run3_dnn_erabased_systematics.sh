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

Con Condor, sia run sia monitor attendono la fine dei cluster e verificano gli
output. plan/check preparano soltanto il report dei job mancanti.

Options:
  -e, --eras ERAS              comma-separated eras
  -s, --systematics SYSTS      comma-separated systematic groups
  --local                      run locally
  --condor                     submit to HTCondor (default)
  --missing-only               skip completed outputs (default)
  --no-missing-only            also rerun completed outputs
  --interval SECONDS           polling Condor interno (default: 300)
  --input-dir PATH             skim input base
  --manifests PATH             validation-manifest base
  -o, --output-base PATH       output base
  --central-output PATH        direct output directory for Central
  -h, --help                   show this help

Example:
  ... run -e 2023 -s JERC --local --missing-only
  ... run -e 2022,2023 -s JERC,Muon --condor --interval 300
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
    DATASETS="mc"
fi

case "${MODE}" in
    plan|run|check|monitor) ;;
    *)
        usage >&2
        exit 2
        ;;
esac

if [[ "${EXECUTION}" == "condor" ]]; then
    IFS=',' read -r -a era_parts <<< "${ERAS}"
    condor_eras=()
    for era_part in "${era_parts[@]}"; do
        if [[ "${era_part}" == Run3_* ]]; then
            condor_eras+=("${era_part}")
        else
            condor_eras+=("Run3_${era_part}")
        fi
    done
    condor_eras_csv="$(IFS=,; echo "${condor_eras[*]}")"

    if [[ "${SYSTEMATICS,,}" == "central" ]]; then
        histogram_output="${CENTRAL_OUTPUT}"
        condor_label="DNN_Central"
    else
        histogram_output="${OUTPUT_BASE}"
        condor_label="DNN_${SYSTEMATICS//,/_}"
    fi

    command=(
        python3 htcondor/condorsubmit.py histograms
        --eras "${condor_eras_csv}"
        --systematics "${SYSTEMATICS}"
        --datasets "${DATASETS}"
        --root-input-folder "${INPUT_DIR}"
        --json-input-folder "${INPUT_DIR}"
        --manifest-input-folder "${MANIFESTS}"
        --output-dir "${histogram_output}"
        --condor-label "${condor_label}"
        --chunk-size 1
        --poll-interval "${INTERVAL}"
    )
    [[ ${MISSING_ONLY} -eq 1 ]] && command+=(--missing-only)
    [[ ${MISSING_ONLY} -eq 0 ]] && command+=(--force)
    case "${MODE}" in
        plan|check) command+=(--no-submit) ;;
        run|monitor) ;;
    esac
    command+=(
        --
        --variables DNN_NNOutput
        --mass-regions Signal_Fit
        --categories VBF
    )
    "${command[@]}"
else
    [[ "${MODE}" != "monitor" ]] || {
        echo "monitor mode requires --condor" >&2
        exit 2
    }
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
        --local
    )
    if [[ "${SYSTEMATICS,,}" == "central" ]]; then
        command+=(--output-dir "${CENTRAL_OUTPUT}")
    else
        command+=(--output-base "${OUTPUT_BASE}")
    fi
    [[ ${MISSING_ONLY} -eq 1 ]] && command+=(--missing-only)
    [[ ${MISSING_ONLY} -eq 0 ]] && command+=(--no-missing-only)
    [[ "${MODE}" == "run" ]] && command+=(--run)
    [[ "${MODE}" == "check" ]] && command+=(--check)
    "${command[@]}"
fi
