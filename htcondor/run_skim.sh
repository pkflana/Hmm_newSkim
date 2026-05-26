#!/bin/bash
export X509_USER_PROXY=/afs/cern.ch/user/p/pflanaga/x509up_u148441
export XRD_NETWORKSTACK=IPv4
cd /afs/cern.ch/user/p/pflanaga/Hmm_newSkim/analysis
source /cvmfs/sft.cern.ch/lcg/views/LCG_105a_swan/x86_64-el9-gcc13-opt/setup.sh
source /cvmfs/cms.cern.ch/cmsset_default.sh
python3 skim.py $1 $2 $3 $4