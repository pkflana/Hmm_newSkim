#!/usr/bin/env bash
#
# Raccolta di esempi per la produzione e il merge degli istogrammi.
#
# Uso:
#   bash examples/run_histograms.sh plan-all
#   bash examples/run_histograms.sh run-all
#
# Le azioni "plan-*" stampano soltanto i comandi. Usare "run-*" solo dopo
# avere controllato il piano.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

# ============================================================================
# CONFIGURAZIONE DA MODIFICARE
# ============================================================================

# Si possono specificare una o più ere.
ERAS=(2023)
# Esempio per tutto Run 3:
# ERAS=(2022 2022EE 2023 2023BPix 2024 2025)

# Una o più variabili. Lasciare l'array vuoto per usare quelle del maincfg.
VARIABLES=(DNN_NNOutput)
# Esempio:
# VARIABLES=(DNN_NNOutput m_mumu)

REGIONS=(Signal_Fit H_sideband Z_sideband)
CATEGORIES=(VBF)
# Esempio:
# CATEGORIES=(baseline ggF VBF)

SHIFTED_SYSTEMATICS=(JERC ScaRe Muon PU QCDScale PDF)

# Gli output saranno OUTPUT_BASE/Hists_Central, OUTPUT_BASE/Hists_JERC, ...
OUTPUT_BASE="/eos/user/v/vdamante/H_mumu/DNN"

# I default di hmumu corrispondono già a questi path. Tenerli qui rende
# evidente quale produzione viene letta.
INPUT_DIR="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v2"
MANIFESTS="/eos/user/v/vdamante/H_mumu/manifests"

CHUNK_SIZE=5
CORES=1

# Le shifted vengono normalmente sottomesse a Condor. Per Central il comando
# originale era locale: cambiare in true se si vuole sottomettere anche quello.
CENTRAL_CONDOR=false
SHIFTED_CONDOR=true

# Usata dall'azione merge-eras. Cambiarla, per esempio, in Hists_JERC per
# combinare quella specifica sistematica.
MERGE_ERAS_INPUT="${OUTPUT_BASE}/Hists_Central"
MERGED_ERA_NAME="Run3_2022_23"

# Input del passaggio dataset -> processi. L'output predefinito aggiunge
# automaticamente il suffisso "_hadded".
HADD_PROCESSES_INPUT="${OUTPUT_BASE}/Hists_Central"

# ============================================================================
# FINE CONFIGURAZIONE
# ============================================================================

join_csv() {
    local IFS=,
    printf '%s' "$*"
}

usage() {
    cat <<'EOF'
Uso:
  bash examples/run_histograms.sh AZIONE

Produzione:
  plan-central          mostra il comando Central
  run-central           produce Central
  plan-systematics      mostra i comandi delle shifted
  run-systematics       sottomette/produce le shifted
  plan-all              mostra Central e shifted
  run-all               produce Central e shifted

Merge:
  plan-hadd-processes    mostra il merge dataset -> processi
  run-hadd-processes     esegue il merge dataset -> processi
  plan-merge-eras       mostra hadd 2022+2022EE+2023+2023BPix
  run-merge-eras        esegue hadd delle ere
  plan-merge-systs      mostra hadd Central+shifted
  run-merge-systs       esegue hadd Central+shifted

Prima di lanciare, modificare il blocco CONFIGURAZIONE all'inizio del file.
EOF
}

common_hist_arguments() {
    HIST_ARGS=(
        -e "$(join_csv "${ERAS[@]}")"
        -r "$(join_csv "${REGIONS[@]}")"
        -c "$(join_csv "${CATEGORIES[@]}")"
        --input-dir "${INPUT_DIR}"
        --manifests "${MANIFESTS}"
        --output-base "${OUTPUT_BASE}"
        --chunk-size "${CHUNK_SIZE}"
        --cores "${CORES}"
    )

    local variable
    for variable in "${VARIABLES[@]}"; do
        HIST_ARGS+=(-v "${variable}")
    done
}

run_central() {
    local execute="$1"
    common_hist_arguments

    local command=(
        ./hmumu hist
        "${HIST_ARGS[@]}"
        -s Central
    )
    if [[ "${CENTRAL_CONDOR}" == true ]]; then
        command+=(--condor)
    fi
    if [[ "${execute}" == true ]]; then
        command+=(--run)
    fi
    command+=(-- --skip-failed-chunks)

    "${command[@]}"
}

run_systematics() {
    local execute="$1"
    common_hist_arguments

    local command=(
        ./hmumu hist
        "${HIST_ARGS[@]}"
        -s "$(join_csv "${SHIFTED_SYSTEMATICS[@]}")"
    )
    if [[ "${SHIFTED_CONDOR}" == true ]]; then
        command+=(--condor)
    fi
    if [[ "${execute}" == true ]]; then
        command+=(--run)
    fi
    command+=(-- --skip-failed-chunks)

    "${command[@]}"
}

merge_eras() {
    local execute="$1"
    local command=(
        ./hmumu merge-eras
        "${MERGE_ERAS_INPUT}"
        --output-era "${MERGED_ERA_NAME}"
    )
    if [[ "${execute}" == true ]]; then
        command+=(--run)
    fi
    "${command[@]}"
}

hadd_processes() {
    local execute="$1"
    local command=(
        ./hmumu hadd-processes
        "${HADD_PROCESSES_INPUT}"
        -e "$(join_csv "${ERAS[@]}")"
    )
    if [[ "${execute}" == true ]]; then
        command+=(--run)
    fi
    "${command[@]}"
}

merge_systematics() {
    local execute="$1"
    local command=(
        ./hmumu merge-systematics
        "${OUTPUT_BASE}/Hists_Central"
        --systematics "Central,$(join_csv "${SHIFTED_SYSTEMATICS[@]}")"
    )
    if [[ "${execute}" == true ]]; then
        command+=(--run)
    fi
    "${command[@]}"
}

ACTION="${1:-}"
case "${ACTION}" in
    plan-central)       run_central false ;;
    run-central)        run_central true ;;
    plan-systematics)   run_systematics false ;;
    run-systematics)    run_systematics true ;;
    plan-all)
        run_central false
        run_systematics false
        ;;
    run-all)
        run_central true
        run_systematics true
        ;;
    plan-hadd-processes) hadd_processes false ;;
    run-hadd-processes)  hadd_processes true ;;
    plan-merge-eras)    merge_eras false ;;
    run-merge-eras)     merge_eras true ;;
    plan-merge-systs)   merge_systematics false ;;
    run-merge-systs)    merge_systematics true ;;
    *)
        usage
        [[ -z "${ACTION}" ]] || printf '\nERRORE: azione sconosciuta: %s\n' "${ACTION}" >&2
        exit 2
        ;;
esac
