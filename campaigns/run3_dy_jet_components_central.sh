#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

eras=(2022 2022EE 2023 2023BPix 2024 2025)
run_args=()
if [[ "${1:-}" == "--run" ]]; then
  run_args=(--run)
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--run]" >&2
  exit 2
fi

if [[ ${#run_args[@]} -gt 0 ]]; then
  # ROOT is needed only for the preflight performed before real submission.
  # shellcheck disable=SC1091
  source "${repo_dir}/env.sh"
  python3 tools/check_dy_jet_component_inputs.py \
    --manifests /eos/user/v/vdamante/H_mumu/manifests \
    --eras "${eras[@]/#/Run3_}"
fi

exec ./hmumu hist \
  --era "$(IFS=,; echo "${eras[*]}")" \
  --systematics Central \
  --datasets DY_amcatnlo,DY_amcatnlo_105_160 \
  --region Signal_Fit,H_sideband,Z_sideband \
  --dy-jet-components \
  --condor \
  --chunk-size 1 \
  --cores 1 \
  --output-dir /eos/user/v/vdamante/H_mumu/Hists_DYJetComponents_Central \
  "${run_args[@]}"
