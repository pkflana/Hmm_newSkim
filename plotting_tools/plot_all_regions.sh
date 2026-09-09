#!/usr/bin/env bash

set -euo pipefail

# Configurazione della campagna
year="2022_23"
enable_component_composition=true
multipage_pdf_name="all_plots.pdf"
output_dir="prova_plots_26Aug"
input_root="/eos/user/v/vdamante/H_mumu/Aug25/AllVars_AllRegions/WithDY012JWeights/Hists_Central_hadded"
extra_plot_args=()
regions_override=""
categories_override=""
variables_override=""

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
        --output)
            (($# >= 2)) || { echo "Missing value after --output" >&2; exit 2; }
            output_dir="$2"
            shift 2
            ;;
        --input-root)
            (($# >= 2)) || { echo "Missing value after --input-root" >&2; exit 2; }
            input_root="$2"
            shift 2
            ;;
        --regions)
            (($# >= 2)) || { echo "Missing value after --regions" >&2; exit 2; }
            regions_override="$2"
            shift 2
            ;;
        --categories)
            (($# >= 2)) || { echo "Missing value after --categories" >&2; exit 2; }
            categories_override="$2"
            shift 2
            ;;
        --variables)
            (($# >= 2)) || { echo "Missing value after --variables" >&2; exit 2; }
            variables_override="$2"
            shift 2
            ;;
        --plot-option)
            (($# >= 2)) || { echo "Missing value after --plot-option" >&2; exit 2; }
            extra_plot_args+=("$2")
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
input_dir="${input_root}/${era}"
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

if [[ -n "$regions_override" ]]; then
    IFS=',' read -r -a regions <<< "$regions_override"
fi
if [[ -n "$categories_override" ]]; then
    IFS=',' read -r -a categories <<< "$categories_override"
fi
if [[ -n "$variables_override" ]]; then
    IFS=',' read -r -a requested_variables <<< "$variables_override"
    # hist_plotter accepts one comma-separated value for --variables.
    extra_plot_args+=(--variables "$variables_override")
fi

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
    # Signal_Fit e H_sideband usano le produzioni ristrette a 105 < m_mumu < 160 GeV.
    if [[ "$region" == "Signal_Fit" || "$region" == "H_sideband" ]]; then
        dy_process="DYto2Mu_MLL105To160"
        # Some older campaigns used the _combined filename, whereas the
        # current merge stage writes the canonical name without that suffix.
        # Select the actual file instead of inferring the convention by era.
        if [[ -f "$input_dir/${dy_process}_combined.root" ]]; then
            dy_process+="_combined"
        fi
        # Plotting folds the physical process into this configured macro-group;
        # normalization must target the post-grouping name.
        dy_sample="DYto2Mu_MLL105_160"
        ewk_sample="EWK_2Mu2J_MLL_105to160_herwig"
    else
        dy_process="DY"
        dy_sample="DY_amcatnlo"
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
        append_components samples "$dy_process"
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
            "${composition_args[@]}" \
            "${extra_plot_args[@]}"

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
