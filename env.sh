#!/usr/bin/env bash

# --- 1. Core Framework Paths ---
local_file="$( [ -n "$ZSH_VERSION" ] && echo "${(%):-%x}" || echo "${BASH_SOURCE[0]}" )"
export ANALYSIS_PATH="$( cd "$( dirname "$local_file" )" && pwd )"
export ANALYSIS_DATA_PATH="$ANALYSIS_PATH/data"

mkdir -p "$ANALYSIS_DATA_PATH"
export PYTHONPATH="$ANALYSIS_PATH:$PYTHONPATH"

# --- 2. Persistent VOMS Proxy Settings ---
export X509_USER_PROXY="$ANALYSIS_DATA_PATH/voms.proxy"

# --- 3. Light LCG Environment (For Correctionlib, ROOT, & Python) ---
# Sourced by default to give you immediate access to your analysis tools
if [ -z "$CMSSW_BASE" ]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc13-opt/setup.sh
    source /cvmfs/cms.cern.ch/rucio/setup-py3.sh &> /dev/null
    echo ">>> Loaded analysis environment (ROOT, correctionlib, Python3)"
fi

# --- 4. Optional HiggsAnalysis Combine Function ---
# This function is defined but won't run or modify your paths unless triggered.
setup_combine() {
    export COMBINE_RELEASES="$ANALYSIS_PATH/soft"
    local cmssw_ver="CMSSW_14_1_0"
    local arch="el9_amd64_gcc13"

    if [ ! -d "$COMBINE_RELEASES/$cmssw_ver" ]; then
        echo ">>> Installing a clean Combine area in $COMBINE_RELEASES..."
        mkdir -p "$COMBINE_RELEASES" && cd "$COMBINE_RELEASES"
        source /cvmfs/cms.cern.ch/cmsset_default.sh
        export SCRAM_ARCH=$arch
        scramv1 project CMSSW $cmssw_ver
        cd $cmssw_ver/src && eval `scramv1 runtime -sh`

        echo ">>> Cloning Combine & CombineHarvester..."
        git clone https://github.com/cms-analysis/HiggsAnalysis-CombinedLimit.git HiggsAnalysis/CombinedLimit
        git clone https://github.com/cms-analysis/CombineHarvester.git CombineHarvester
        scram b -j8
    else
        source /cvmfs/cms.cern.ch/cmsset_default.sh
        cd "$COMBINE_RELEASES/$cmssw_ver/src"
        export SCRAM_ARCH=$arch
        eval `scramv1 runtime -sh`
        echo ">>> Environment switched to $cmssw_ver for Combine."
    fi
    cd "$ANALYSIS_PATH"
}

# --- 5. Parse Command Line Arguments ---
# Allows you to explicitly enable combine on startup if you want to
LOAD_COMBINE=false
for arg in "$@"; do
    if [[ "$arg" == "--combine" || "$arg" == "-c" ]]; then
        LOAD_COMBINE=true
    fi
done

if [ "$LOAD_COMBINE" = true ]; then
    setup_combine
else
    # Register an alias so you can still type 'cmsCombineEnv' later in the session if needed
    alias cmsCombineEnv=setup_combine
    echo ">>> Combine is currently DISABLED. (Type 'cmsCombineEnv' or source with '--combine' to enable)"
fi

ulimit -n 4096