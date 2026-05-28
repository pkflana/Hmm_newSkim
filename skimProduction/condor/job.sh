#!/bin/bash

set -euo pipefail
set -x

exec > debug.log 2>&1

echo "Starting job"

# unpack
tar -xzf framework.tar.gz

ls -R .

# environment
source env.sh

# inputs
ERA=$1
DATASET=$2
INPUTS=$3
OUTPUT=$4

INPUTS=$(echo $INPUTS | tr ',' ' ')

mkdir -p $(dirname $OUTPUT)

python3 skimProduction/analysis/skim.py \
    --era $ERA \
    --dataset-name $DATASET \
    --input-files $INPUTS \
    --output-file $OUTPUT