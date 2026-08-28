#!/usr/bin/env bash

set -euo pipefail

# Configurazione della campagna
year="2022_23"
enable_component_composition=true
multipage_pdf_name="all_plots.pdf"

while (($#)); do
    case "$1" in
        --era|--year)
            (($# >= 2)) || { echo "Missing value after $1" >&2; exit 2; }
            year="$2"
            shift 2
            ;;
        --component-composition)
            enable_component_composition=true
            shift
            ;;
        --no-component-composition)
            enable_component_composition=false
            shift
            ;;
        --pdf-name)
            (($# >= 2)) || { echo "Missing value after --pdf-name" >&2; exit 2; }
            multipage_pdf_name="$2"
            shift 2
            ;;
        Run3_*|2022|2022EE|2023|2023BPix|2024|2025|2022_23|2022_25)
            year="$1"
            shift
            ;;
        *)
            echo "Unexpected argument: $1" >&2
            exit 2
            ;;
    esac
done

year="${year#Run3_}"
era="Run3_${year}"
input_dir="/eos/user/v/vdamante/H_mumu/Aug25/AllVars_AllRegions/WithDY012JWeights/Hists_Central_hadded/${era}"
output_dir="prova_plots_26Aug"
generated_pdfs=()

regions=(
    Signal_Fit
    Z_sideband
    H_sideband
    mass_inclusive
)

categories=(
    VBF
    ggF
    baseline
)

other_samples=(
    Data_Muon
    SingleH
    SingleTop
    TTX
    DiTriBoson
    W_NJets
    W
    TT
)

signal_samples=(
    GluGluHto2Mu
    VBFHto2Mu_M125_powheg
)

component_suffixes=(
    0J
    1J_Hard
    1J_PU
    2J_Hard
    2J_PU1
    2J_PU2
)

append_components() {
    local -n destination="$1"
    local process="$2"
    local suffix

    for suffix in "${component_suffixes[@]}"; do
        destination+=("${process}_${suffix}")
    done
}

for region in "${regions[@]}"; do
    # Signal_Fit usa le produzioni ristrette a 105 < m_mumu < 160 GeV.
    if [[ "$region" == "Signal_Fit" ]]; then
        dy_sample="DYto2Mu_MLL105To160"
        if [[ "$year" == "2024" || "$year" == "2025" \
              || "$year" == "2022_25" ]]; then
            dy_sample+="_combined"
        fi
        ewk_sample="EWK_2Mu2J_MLL_105to160_herwig"
    else
        dy_sample="DY"
        ewk_sample="EWK"
    fi

    samples=(
        "$dy_sample"
        "$ewk_sample"
        "${signal_samples[@]}"
        "${other_samples[@]}"
    )
    composition_args=()

    if "$enable_component_composition"; then
        append_components samples "$dy_sample"
        append_components samples "$ewk_sample"

        for signal_sample in "${signal_samples[@]}"; do
            append_components samples "$signal_sample"
        done

        composition_args=(--component-composition)
    fi

    for category in "${categories[@]}"; do
        region_category="${region}_${category}"

        echo "Producing ${era}/${region_category}"

        python3 plotting_tools/hist_plotter.py \
            --era "$era" \
            --input "$input_dir" \
            --output "$output_dir" \
            --region "$region_category" \
            --samples "${samples[@]}" \
            --wantLogY \
            --wantData \
            --rebin \
            --multipage-pdf "$multipage_pdf_name" \
            --normalize-dy-to-data \
            "${composition_args[@]}" \
            --dy-normalization-sample "$dy_sample"

        region_pdf="$output_dir/$era/$region_category/$multipage_pdf_name"
        if [[ -s "$region_pdf" ]]; then
            generated_pdfs+=("$region_pdf")
        fi

    done
done

if ((${#generated_pdfs[@]})); then
    combined_pdf="$output_dir/$era/$multipage_pdf_name"
    temporary_pdf="$(mktemp --suffix=.pdf)"
    trap 'rm -f "$temporary_pdf"' EXIT
    pdfunite "${generated_pdfs[@]}" "$temporary_pdf"
    mkdir -p "$(dirname "$combined_pdf")"
    mv -f "$temporary_pdf" "$combined_pdf"
    trap - EXIT
    echo "Combined multipage PDF: $combined_pdf"
fi
