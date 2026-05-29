#!/bin/bash

export XRD_NETWORKSTACK=IPv4
cd $2
source /cvmfs/sft.cern.ch/lcg/views/LCG_105a_swan/x86_64-el9-gcc13-opt/setup.sh
source /cvmfs/cms.cern.ch/cmsset_default.sh
source env.sh
export X509_USER_PROXY=$1

IFS=',' read -r -a INPUT_FILES <<< "$4"
IFS=',' read -r -a OUTPUT_FILES <<< "$6"

for i in "${!INPUT_FILES[@]}"; do
    python3 analysis/skim.py --era "$3" --input-file "${INPUT_FILES[$i]}" --dataset-name "$5" --output-file "${OUTPUT_FILES[$i]}"
done