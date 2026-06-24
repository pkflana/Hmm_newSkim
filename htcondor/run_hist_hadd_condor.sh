#!/usr/bin/env bash
set -euo pipefail

analysis_path="$1"
output_file="$2"
chunk_list="$3"

cd "${analysis_path}"
_saved_args=("$@")
set --
source "${analysis_path}/env.sh"
set -- "${_saved_args[@]}"
unset _saved_args

chunk_files=()
while IFS= read -r chunk_file; do
  [[ -z "${chunk_file}" ]] && continue
  if [[ ! -s "${chunk_file}" ]]; then
    echo "[ERROR] Missing or empty chunk output: ${chunk_file}" >&2
    exit 4
  fi
  chunk_files+=("${chunk_file}")
done < "${chunk_list}"

if [[ ${#chunk_files[@]} -eq 0 ]]; then
  echo "[ERROR] No chunk outputs listed in ${chunk_list}" >&2
  exit 5
fi

mkdir -p "$(dirname "${output_file}")"
temporary_output="${output_file}.merging.$$"
trap 'rm -f "${temporary_output}"' EXIT

echo "[INFO] Merging ${#chunk_files[@]} chunks into ${output_file}"
hadd -f "${temporary_output}" "${chunk_files[@]}"
mv -f "${temporary_output}" "${output_file}"
trap - EXIT

echo "[INFO] Merge completed: ${output_file}"
