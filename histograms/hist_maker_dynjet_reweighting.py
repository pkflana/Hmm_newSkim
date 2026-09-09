#!/usr/bin/env python3
"""Produce the Z-sideband inputs for the dynjet reweight derivation.

Uses hist_maker's input/output CLI. Stage variables, categories and weight
switches are fixed here so later corrections cannot contaminate the fit.
"""
import os
import sys

sys.path.append(os.environ["ANALYSIS_PATH"])
from histograms.hist_maker import main

STAGE_SETTINGS = {'variables': ['N_SelectedJets'],
 'categories': ['ggF', 'VBF'],
 'custom_weights': True,
 'dy_jet_component_reweight': True,
 'dy_ptll_reweight': True,
 'dy_njets_reweight': False,
 'dy_jet_components': False,
 'mass_regions': ['Z_sideband'],
 'systematics': ['Central'],
 'derive_jet_component_weights': False,
 'vbf_eta_regions': False}

if __name__ == "__main__":
    main(stage_settings=STAGE_SETTINGS)
