#!/usr/bin/env bash
set -euo pipefail

era="${1:?Usage: ./run_wjets_hists.sh ERA [input_folder]}"
input_folder="${2:-skim_v1_noUnc}"

declare -a datasets

case "${era}" in
  Run3_2024|Run3_2025|Run3_2026)
    datasets=(
      DYto2Mu_MLL_105to160_amcatnloFXFX
      # DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF
    )
    ;;

  *)
    echo "[ERROR] Unknown era: ${era}"
    echo "Allowed eras:"
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
  output_file="${output_dir}/${dataset_name}_stitched.root"

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
    --output-file "${output_file}"\
    --additional-cuts "GenVBFFilter==0"\
    --chunk-size 20
done