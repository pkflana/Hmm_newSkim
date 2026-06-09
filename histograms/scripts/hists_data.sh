#!/usr/bin/env bash
set -euo pipefail

era="${1:?Usage: ./run_data_hists.sh ERA [input_folder]}"
input_folder="${2:-skim_v1_noUnc}"

declare -a datasets

case "${era}" in
  Run3_2022)
    datasets=(
      Muon_Run2022C
      Muon_Run2022D
      SingleMuon_Run2022C
    )
    ;;

  Run3_2022EE)
    datasets=(
      Muon_Run2022E
      Muon_Run2022F
      Muon_Run2022G
    )
    ;;

  Run3_2023)
    datasets=(
      Muon0_Run2023C_v1
      Muon0_Run2023C_v2
      Muon0_Run2023C_v3
      Muon0_Run2023C_v4
      Muon1_Run2023C_v1
      Muon1_Run2023C_v2
      Muon1_Run2023C_v3
      Muon1_Run2023C_v4
    )
    ;;

  Run3_2023BPix)
    datasets=(
      Muon0_Run2023D_v1
      Muon0_Run2023D_v2
      Muon1_Run2023D_v1
      Muon1_Run2023D_v2
    )
    ;;

  Run3_2024)
    datasets=(
      Muon0_Run2024C
      Muon0_Run2024D
      Muon0_Run2024E
      Muon0_Run2024F
      Muon0_Run2024G
      Muon0_Run2024H
      Muon0_Run2024I_v1
      Muon0_Run2024I_v2
      Muon1_Run2024C
      Muon1_Run2024D
      Muon1_Run2024E
      Muon1_Run2024F
      Muon1_Run2024G
      Muon1_Run2024H
      Muon1_Run2024I_v1
      Muon1_Run2024I_v2
    )
    ;;

  Run3_2025)
    datasets=(
      Muon0_Run2025C_v1
      Muon0_Run2025C_v2
      Muon0_Run2025D_v1
      Muon0_Run2025E_v1
      Muon0_Run2025F_v1
      Muon0_Run2025F_v2
      Muon0_Run2025G_v1
      Muon1_Run2025C_v1
      Muon1_Run2025C_v2
      Muon1_Run2025D_v1
      Muon1_Run2025E_v1
      Muon1_Run2025F_v1
      Muon1_Run2025F_v2
      Muon1_Run2025G_v1
    )
    ;;

  Run3_2026)
    datasets=(
      # TODO: aggiungi qui i dataset 2026 quando li hai
      # Muon0_Run2026...
      # Muon1_Run2026...
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

if [[ ${#datasets[@]} -eq 0 ]]; then
  echo "[ERROR] No datasets configured for era ${era}"
  exit 1
fi

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

  python3 histograms/hist_maker.py \
    --era "${era}" \
    --dataset data \
    --dataset-name "${dataset_name}" \
    --input "${input_path}" \
    --output-file "${output_file}" \
    --resume

done