"""One-time ROOT runtime initialization shared by analysis applications."""

import os
from pathlib import Path

import ROOT

from common import utilities

_INITIALIZED = False


def initialize_root_runtime(batch=True, thread_safe=True):
    global _INITIALIZED
    if _INITIALIZED:
        return
    analysis_path = os.environ.setdefault(
        "ANALYSIS_PATH", str(Path(__file__).resolve().parents[1])
    )
    if batch:
        ROOT.gROOT.SetBatch(True)
    if thread_safe:
        ROOT.EnableThreadSafety()
    utilities.DeclareHeader(f"{analysis_path}/analysis/AnalysisTools.h")
    _INITIALIZED = True
