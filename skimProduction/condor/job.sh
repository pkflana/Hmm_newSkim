#!/bin/bash

set -euo pipefail
set -x

exec > debug.log 2>&1

echo "Starting job in Condor sandbox"

echo "PWD = $PWD"
ls -R .

# --------------------------------------
# environment (LOCAL COPY)
# --------------------------------------

source env.sh


# --------------------------------------
# inputs
# --------------------------------------

ERA=$1
DATASET=$2
INPUTS=$3
OUTPUT=$4

INPUTS=$(echo $INPUTS | tr ',' ' ')

mkdir -p $(dirname $OUTPUT)

# --------------------------------------
# run from local copy
# --------------------------------------

python3 analysis/skim.py \
    --era $ERA \
    --dataset-name $DATASET \
    --input-files $INPUTS \
    --output-file $OUTPUT
