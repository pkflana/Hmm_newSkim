#!/usr/bin/env bash
set -euo pipefail

analysis_path="$1"
jobs_file="$2"
proc_id="$3"
era="$4"
input_folder="$5"
output_dir="$6"
extra_opts_file="${7:-}"

cd "${analysis_path}"
_saved_args=("$@")
set --
source "${analysis_path}/env.sh"
set -- "${_saved_args[@]}"
unset _saved_args

line_number=$((proc_id + 1))
job_line="$(sed -n "${line_number}p" "${jobs_file}")"
if [[ -z "${job_line}" ]]; then
  echo "[ERROR] No job entry for ProcId=${proc_id} in ${jobs_file}" >&2
  exit 1
fi

IFS=$'\t' read -r dataset_name chunk_size file_suffix specific_opts_string <<< "${job_line}"

input_path="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/"
output_file="${output_dir}/${dataset_name}${file_suffix}.root"

mkdir -p "${output_dir}"

specific_opts=()
if [[ -n "${specific_opts_string}" ]]; then
  # shellcheck disable=SC2206
  specific_opts=(${specific_opts_string})
fi

extra_opts=()
if [[ -n "${extra_opts_file}" && -s "${extra_opts_file}" ]]; then
  extra_opts_string="$(<"${extra_opts_file}")"
  # shellcheck disable=SC2206
  extra_opts=(${extra_opts_string})
fi

command=(
  python3 histograms/hist_maker.py
  --era "${era}"
  --dataset-name "${dataset_name}"
  --input "${input_path}"
  --output-file "${output_file}"
  --chunk-size "${chunk_size}"
)
command+=("${specific_opts[@]}")
command+=("${extra_opts[@]}")

echo "============================================================"
echo "[INFO] ProcId  : ${proc_id}"
echo "[INFO] Era     : ${era}"
echo "[INFO] Dataset : ${dataset_name}"
echo "[INFO] Input   : ${input_path}"
echo "[INFO] Output  : ${output_file}"
echo "[INFO] Command : ${command[*]}"
echo "============================================================"

if [[ ! -d "${input_path}" ]]; then
  echo "[ERROR] Input directory does not exist: ${input_path}" >&2
  exit 2
fi

"${command[@]}"
