#!/usr/bin/env bash
set -euo pipefail

era="${1:?Usage: ./run_wjets_hists.sh ERA [input_folder]}"
input_folder="${2:-skim_v1_noUnc}"

declare -a datasets

case "${era}" in
  Run3_2024|Run3_2025|Run3_2026)
    datasets=(
      WtoENu_amcatnloFXFX
      WtoLNu_1J_madgraphMLM
      WtoLNu_2J_madgraphMLM
      WtoLNu_3J_madgraphMLM
      WtoLNu_4J_madgraphMLM
      WtoMuNu_amcatnloFXFX
      WtoTauNu_amcatnloFXFX
    )
    ;;

  Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix)
    datasets=(
      WtoLNu_0J_amcatnloFXFX
      WtoLNu_1J_amcatnloFXFX
      WtoLNu_2J_amcatnloFXFX
    )
    ;;

  *)
    echo "[ERROR] Unknown era: ${era}"
    echo "Allowed eras:"
    echo "  Run3_2022"
    echo "  Run3_2022EE"
    echo "  Run3_2023"
    echo "  Run3_2023BPix"
    echo "  Run3_2024"
    echo "  Run3_2025"
    echo "  Run3_2026"
    exit 1
    ;;
esac

output_dir="/eos/user/v/vdamante/H_mumu/newHists_${era}"
mkdir -p "${output_dir}"

for dataset_name in "${datasets[@]}"; do

  input_path="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/"
  output_file="${output_dir}/${dataset_name}.root"

  echo
  echo "============================================================"
  echo "[INFO] Era     : ${era}"
  echo "[INFO] Dataset : ${dataset_name}"
  echo "[INFO] Input   : ${input_path}"
  echo "[INFO] Output  : ${output_file}"
  echo "============================================================"

  if [[ ! -d "${input_path}" ]]; then
    echo "[WARNING] Input directory does not exist, skipping:"
    echo "          ${input_path}"
    continue
  fi

  python3 histograms/hist_maker.py \
    --era "${era}" \
    --dataset WJets \
    --dataset-name "${dataset_name}" \
    --input "${input_path}" \
    --output-file "${output_file}"

done