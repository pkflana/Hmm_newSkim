"""Shared dataframe transformations for histogram production."""

from common.add_vars import (
    DefineHistogramSelections,
    SelectedJetObservablesDef,
    VBFJetObservablesDef,
)
from common.apply_custom_weights import apply_custom_weights


def normalize_systematic_direction_columns(rdf, systs_to_run):
    """Alias systematic columns across the historical direction spellings."""
    available_columns = {str(column) for column in rdf.GetColumnNames()}
    for syst_info in systs_to_run.values():
        requested_suffixes = {
            syst_info.get(key, "") for key in ("jet_suffix", "muon_suffix")
        }
        for requested_suffix in requested_suffixes - {""}:
            alternate_suffix = None
            for ending, alternate in (
                ("Up", "up"), ("up", "Up"),
                ("Down", "down"), ("down", "Down"),
            ):
                if requested_suffix.endswith(ending):
                    alternate_suffix = (
                        f"{requested_suffix[:-len(ending)]}{alternate}"
                    )
                    break
            if not alternate_suffix:
                continue
            for source in tuple(available_columns):
                if not source.endswith(alternate_suffix):
                    continue
                target = f"{source[:-len(alternate_suffix)]}{requested_suffix}"
                if target not in available_columns:
                    rdf = rdf.Alias(target, source)
                    available_columns.add(target)
    return rdf


def define_shifted_jet_observables(rdf, systs_to_run):
    """Define derived selected-jet and VBF observables for shifted jets."""
    defined_suffixes = set()
    available_columns = {str(column) for column in rdf.GetColumnNames()}
    for syst_info in systs_to_run.values():
        jet_suffix = syst_info.get("jet_suffix", "")
        if not jet_suffix or jet_suffix in defined_suffixes:
            continue
        required = {
            f"SelectedJet_idx{jet_suffix}",
            f"SelectedJet_pt{jet_suffix}",
            f"SelectedJet_eta{jet_suffix}",
            f"SelectedJet_phi{jet_suffix}",
            f"SelectedJet_mass{jet_suffix}",
            f"SelectedJet_IsInsideHorn{jet_suffix}",
            f"HasVBF{jet_suffix}",
            f"VBFJetIdx_1{jet_suffix}",
            f"VBFJetIdx_2{jet_suffix}",
        }
        missing = sorted(required - available_columns)
        if missing:
            raise RuntimeError(
                f"Cannot build jet variation '{jet_suffix}'; missing columns: "
                + ", ".join(missing)
            )
        rdf = SelectedJetObservablesDef(rdf, suffix=jet_suffix)
        rdf = VBFJetObservablesDef(rdf, suffix=jet_suffix)
        defined_suffixes.add(jet_suffix)
        available_columns = {str(column) for column in rdf.GetColumnNames()}
    return rdf


def finalize_histogram_dataframe(
    rdf,
    dataset_name,
    selections_cfg,
    systematics_cfg,
    weight_columns,
    era,
    want_variations=False,
    multiply_corrections=True,
    apply_jet_component_weight=True,
    apply_dy_ptll_weight=True,
    apply_dy_njets_weight=True,
    reweight_jsons=None,
):
    """Apply selections and final weight corrections exactly once."""
    rdf = DefineHistogramSelections(
        rdf,
        selections_cfg,
        syst_cfg=systematics_cfg,
        want_variations=want_variations,
    )
    columns = {str(column) for column in rdf.GetColumnNames()}
    for source in ("leadingjet_eta", "subleadingjet_eta", "vbfjet1_eta"):
        target = f"abs_{source}"
        if source in columns and target not in columns:
            rdf = rdf.Define(target, f"std::abs({source})")
            columns.add(target)
    target_weights = weight_columns if multiply_corrections else []
    return apply_custom_weights(
        rdf,
        dataset_name,
        era,
        target_weights,
        apply_jet_component=apply_jet_component_weight,
        apply_dy_ptll=apply_dy_ptll_weight,
        apply_dy_njets=apply_dy_njets_weight,
        reweight_jsons=reweight_jsons,
    )
