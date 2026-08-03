"""Shared dataframe transformations for histogram production."""

from common.add_var_to_skim import DefineHistogramSelections
from common.dy_ptll_reweight import (
    ApplyDYAmcatnloNormalization,
    ApplyDYNJetsReweight,
    ApplyDYPtLLReweight,
)


def finalize_histogram_dataframe(
    rdf,
    dataset_name,
    selections_cfg,
    systematics_cfg,
    weight_columns,
    want_variations=False,
    dy_ptll_reweight_json=None,
    dy_njets_reweight_json=None,
    multiply_corrections=True,
):
    """Apply selections and final weight corrections exactly once."""
    rdf = DefineHistogramSelections(
        rdf,
        selections_cfg,
        syst_cfg=systematics_cfg,
        want_variations=want_variations,
    )
    target_weights = weight_columns if multiply_corrections else []
    rdf = ApplyDYAmcatnloNormalization(rdf, dataset_name, target_weights)
    if dy_ptll_reweight_json:
        rdf = ApplyDYPtLLReweight(
            rdf, dataset_name, dy_ptll_reweight_json, target_weights
        )
    if dy_njets_reweight_json:
        rdf = ApplyDYNJetsReweight(
            rdf, dataset_name, dy_njets_reweight_json, target_weights
        )
    return rdf
