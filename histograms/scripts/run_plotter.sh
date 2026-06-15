#!/bin/bash

set -e
# Usage examples:
# ./run_plotter.sh
# ./run_plotter.sh --eras "Run3_2022 Run3_2022EE" --output plots_test/
# ./run_plotter.sh --eras "Run3_2024" --mode 2024_all
# ./run_plotter.sh --eras "Run3_2024" --input-tag-template newHists_ERA_newCats_hadded
# ./run_plotter.sh --dryrun
# ./run_plotter.sh --web
# ./run_plotter.sh --combined

ERAS="Run3_2022 Run3_2022EE Run3_2023 Run3_2023BPix"
INPUT_BASE="/eos/user/v/vdamante/H_mumu"
INPUT_TAG_TEMPLATE="newHists_ERA_hadded"
OUTPUT_BASE="plots"
WEB_OUTPUT_BASE="/eos/user/v/vdamante/www/H_mumu"
REGIONS_Z="Z_sideband_ggF Z_sideband_VBF"
REGIONS_SIGNAL="Signal_Fit_ggF Signal_Fit_VBF"
MODE="default"
DRYRUN=0
WEB=0
COMBINED=0
EXTRA_OPTS=""

PYTHON=python3
PLOTTER="histograms/hist_plotter.py"

# ==========================================================
# Argument parsing
# ==========================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --eras)
            ERAS="$2"
            shift 2
            ;;
        --input-base)
            INPUT_BASE="$2"
            shift 2
            ;;
        --input-tag-template)
            INPUT_TAG_TEMPLATE="$2"
            shift 2
            ;;
        --output)
            OUTPUT_BASE="$2"
            shift 2
            ;;
        --web)
            WEB=1
            shift
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --combined)
            COMBINED=1
            shift
            ;;
        --dryrun)
            DRYRUN=1
            shift
            ;;
        --extra-opts)
            EXTRA_OPTS="$2"
            shift 2
            ;;
        --plotter)
            PLOTTER="$2"
            shift 2
            ;;
        *)
            echo "[ERROR] Unknown option: $1"
            exit 1
            ;;
    esac
done

# ==========================================================
# Output base
# ==========================================================

if [[ "${WEB}" -eq 1 ]]; then
    FINAL_OUTPUT_BASE="${WEB_OUTPUT_BASE}"
else
    FINAL_OUTPUT_BASE="${OUTPUT_BASE}"
fi

echo "=========================================================="
echo "[INFO] Plot runner"
echo "[INFO] Eras:        ${ERAS}"
echo "[INFO] Mode:        ${MODE}"
echo "[INFO] Combined:    ${COMBINED}"
echo "[INFO] Input base:  ${INPUT_BASE}"
echo "[INFO] Input tag:   ${INPUT_TAG_TEMPLATE}"
echo "[INFO] Output base: ${FINAL_OUTPUT_BASE}"
echo "[INFO] Dryrun:      ${DRYRUN}"
echo "=========================================================="

# ==========================================================
# Helpers
# ==========================================================

run_cmd() {
    echo ""
    echo "[CMD] $*"
    if [[ "${DRYRUN}" -eq 0 ]]; then
        "$@"
    fi
}

get_input_dir() {
    local era=$1
    local input_tag=${INPUT_TAG_TEMPLATE/ERA/${era}}
    echo "${INPUT_BASE}/${input_tag}/"
}
copy_index_if_web() {
    local outdir=$1

    if [[ "${WEB}" -eq 1 ]]; then
        cp /eos/user/v/vdamante/www/H_mumu/index.php "${outdir}/index.php"
    fi
}
run_plot() {
    local era=$1
    local output_dir=$2
    local region=$3
    shift 3
    local samples=("$@")

    local input_dir
    input_dir=$(get_input_dir "${era}")

    mkdir -p "${output_dir}"
    copy_index_if_web "${output_dir}"

    run_cmd ${PYTHON} ${PLOTTER} \
        --era "${era}" \
        --input "${input_dir}" \
        --output "${output_dir}" \
        --region "${region}" \
        --samples "${samples[@]}" \
        --wantLogY \
        --wantData \
        --rebin \
        ${EXTRA_OPTS}
}

# ==========================================================
# Sample definitions
# ==========================================================

SAMPLES_Z=( Data_Muon DY W_NJets TT EWK VV VVV VBFHto2Mu_M125_powheg GluGluHto2Mu)
SAMPLES_SIGNAL_LEGACY=( Data_Muon DYto2Mu_MLL105To160 W_NJets TT EWK_2Mu2J_MLL_105to160_herwig VV VVV VBFHto2Mu_M125_powheg GluGluHto2Mu)
SAMPLES_SIGNAL_LEGACY_2024=( Data_Muon DYto2Mu_MLL105To160_nonStitched DYto2Mu_MLL105To160_FlashSim W_NJets TT EWK_2Mu2J_MLL_105to160_herwig VV VVV VBFHto2Mu_M125_powheg GluGluHto2Mu)
SAMPLES_2024_FLASHSIM=( Data_Muon DYto2Mu_MLL105To160_FlashSim W_NJets TT EWK_2Mu2J_MLL_105to160_pythia_Flashsim VV VVV VBFHto2Mu_M125_powheg GluGluHto2Mu)
SAMPLES_2024_STITCHED_EWK_PYTHIA=( Data_Muon DYto2Mu_MLL105To160 DYto2Mu_MLL105To160_VBFFiltered W_NJets TT EWK_2Mu2J_MLL_105to160_pythia VV VVV VBFHto2Mu_M125_powheg GluGluHto2Mu)
SAMPLES_2024_STITCHED_EWK_HERWIG=( Data_Muon DYto2Mu_MLL105To160 DYto2Mu_MLL105To160_VBFFiltered W_NJets TT EWK_2Mu2J_MLL_105to160_herwig VV VVV VBFHto2Mu_M125_powheg GluGluHto2Mu)

# ==========================================================
# Combined placeholder
# ==========================================================

if [[ "${COMBINED}" -eq 1 ]]; then
    echo "[WARNING] Combined 2022-2024 mode requested."
    echo "[WARNING] This is a placeholder: define input/output convention for combined hists first."
    exit 0
fi

for era in ${ERAS}; do

    echo ""
    echo "=========================================================="
    echo "[INFO] Processing era: ${era}"
    echo "=========================================================="

    if [[ "${era}" == "Run3_2024" ]]; then

        # --------------------------------------------------
        # 2024 dedicated modes
        # --------------------------------------------------

        if [[ "${MODE}" == "default" || "${MODE}" == "2024_all" || "${MODE}" == "flashsim" ]]; then
            for region in ${REGIONS_SIGNAL}; do
                run_plot \
                    "${era}" \
                    "${FINAL_OUTPUT_BASE}/plots_FlashSim/" \
                    "${region}" \
                    "${SAMPLES_2024_FLASHSIM[@]}"
            done
        fi

        if [[ "${MODE}" == "default" || "${MODE}" == "2024_all" || "${MODE}" == "stitched_pythia" ]]; then
            for region in ${REGIONS_SIGNAL}; do
                run_plot \
                    "${era}" \
                    "${FINAL_OUTPUT_BASE}/plots_stitchedVBFFiltered_EWKPythia/" \
                    "${region}" \
                    "${SAMPLES_2024_STITCHED_EWK_PYTHIA[@]}"
            done
        fi

        if [[ "${MODE}" == "default" || "${MODE}" == "2024_all" || "${MODE}" == "stitched_herwig" ]]; then
            for region in ${REGIONS_SIGNAL}; do
                run_plot \
                    "${era}" \
                    "${FINAL_OUTPUT_BASE}/plots_stitchedVBFFiltered_EWKHerwig/" \
                    "${region}" \
                    "${SAMPLES_2024_STITCHED_EWK_HERWIG[@]}"
            done
        fi


        if [[ "${MODE}" == "default" || "${MODE}" == "2024_all" || "${MODE}" == "nonStitched" ]]; then
            for region in ${REGIONS_SIGNAL}; do
                run_plot \
                    "${era}" \
                    "${FINAL_OUTPUT_BASE}/plots_nonStitched_wrong/" \
                    "${region}" \
                    "${SAMPLES_SIGNAL_LEGACY_2024[@]}"
            done
        fi

    else

        # --------------------------------------------------
        # 2022 / 2022EE / 2023 / 2023BPix
        # --------------------------------------------------

        if [[ "${MODE}" == "default" || "${MODE}" == "z" || "${MODE}" == "all" ]]; then
            for region in ${REGIONS_Z}; do
                run_plot \
                    "${era}" \
                    "${FINAL_OUTPUT_BASE}/plots/" \
                    "${region}" \
                    "${SAMPLES_Z[@]}"
            done
        fi

        if [[ "${MODE}" == "default" || "${MODE}" == "signal" || "${MODE}" == "all" ]]; then
            for region in ${REGIONS_SIGNAL}; do
                run_plot \
                    "${era}" \
                    "${FINAL_OUTPUT_BASE}/plots/" \
                    "${region}" \
                    "${SAMPLES_SIGNAL_LEGACY[@]}"
            done
        fi

    fi

done

echo ""
echo "=========================================================="
echo "[INFO] All plotting jobs completed."
echo "=========================================================="
