"""Prepare skim RDFs for histograms, snapshots or other analyses.

Call once on each raw skim graph: nominal and custom weights are multiplied
once. The returned mapping contains ``inclusive`` first, followed by optional
reco/gen components. No histograms are booked here.
"""
from common.rdf_utilities import GetRdfForDataset, build_rdf
from common.histogram_rdf import (
    normalize_systematic_direction_columns, define_shifted_jet_observables,
    finalize_histogram_dataframe,
)
from common.jet_component_splitting import (
    add_jet_component_categories, expanded_jet_component_categories,
    define_jet_gen_matching,
)
from histograms.jer_split import define_split_jer_collections
from common.add_vars import GetSelectionSuffixForSystematic
from common.dnn_histogram_production import (
    apply_sideband_mass_shifted_dnn, needs_sideband_mass_shift,
)


def prepare_rdf(
    rdf=None, *, dataset_name, era, selections_cfg, systematics_cfg,
    is_data=False, input_dir=None, input_files=None, seg_dict=None,
    systs_to_run=None, want_variations=False, dnn_payloads=None,
    btag_algo="PNet", dnn_model_set="updated", additional_cuts=None,
    qcd_scale_seg_dicts=None, skip_validation=False,
    enable_dy012j=True, enable_dyptll=True, enable_dynjets=True,
    enable_custom_weights=True, reweight_jsons=None,
    split_jet_multiplicity=False, include_vbf_eta_regions=False,
    component_categories=("ggF", "VBF"),
):
    """Return an ordered dict of prepared RDFs (empty if no input files).

    Supply either a raw skim ``rdf`` or ``input_dir``/``input_files``.
    ``seg_dict`` must contain the full dataset normalization, also for batches.
    Three independent switches control DY012J, DYptll and DYNJets; nominal
    normalization remains applied when custom weights are disabled.
    Splitting returns inclusive plus ggF 0J/1J/>=2J hard/PU and VBF hard/PU
    nodes; data returns inclusive only. Component nodes use central selections;
    the inclusive node also carries shifted category columns for systematics.
    The caller owns ROOT runtime initialization and DNN registry cleanup.
    """
    systs_to_run = systs_to_run or {"Central": {"weight": "weight__Central"}}
    build_options = dict(
        is_data=is_data, weight_dict=systematics_cfg["weights"],
        store_shifted_weights=want_variations, seg_dict=seg_dict,
        dnn_payloads=dnn_payloads, btag_algo=btag_algo, era=era,
        dnn_model_set=dnn_model_set,
        qcd_scale_config=systematics_cfg.get("qcd_scale"),
        qcd_scale_seg_dicts=qcd_scale_seg_dicts,
        pdf_config=systematics_cfg.get("pdf"),
    )
    if rdf is None:
        rdf = GetRdfForDataset(
            input_dir=input_dir, explicit_files=input_files,
            additional_cuts=additional_cuts, skip_validation=skip_validation,
            **build_options,
        )
    else:
        if additional_cuts:
            rdf = rdf.Filter(additional_cuts)
        rdf = build_rdf(rdf, **build_options)
    if rdf is None:
        return {}
    rdf = normalize_systematic_direction_columns(rdf, systs_to_run)
    rdf = define_split_jer_collections(rdf, systs_to_run)
    rdf = define_shifted_jet_observables(rdf, systs_to_run)
    columns = {str(column) for column in rdf.GetColumnNames()}
    split = split_jet_multiplicity and not is_data
    can_match = bool({"Jet_genJetIdx", "SelectedJet_genJetIdx"} & columns)
    if split and not can_match:
        raise RuntimeError("Jet component splitting requires reco/gen matching indices")
    if not is_data and can_match:
        rdf = define_jet_gen_matching(
            rdf, {""} | {info.get("jet_suffix", "") for info in systs_to_run.values()}
        )
    if split:
        selections_cfg = add_jet_component_categories(
            selections_cfg, include_vbf_eta_regions=include_vbf_eta_regions,
            requested_categories=component_categories,
        )
    weight_columns = sorted({info["weight"] for info in systs_to_run.values() if "weight" in info})
    rdf = finalize_histogram_dataframe(
        rdf, dataset_name, selections_cfg, systematics_cfg, weight_columns, era,
        want_variations=want_variations,
        apply_jet_component_weight=enable_dy012j,
        apply_dy_ptll_weight=enable_dyptll,
        apply_dy_njets_weight=enable_dynjets,
        apply_custom_weight_corrections=enable_custom_weights,
        reweight_jsons=reweight_jsons,
    )
    result = {"inclusive": rdf}
    if split:
        for category in expanded_jet_component_categories(
            include_vbf_eta_regions=include_vbf_eta_regions,
            requested_categories=component_categories,
        ):
            result[category] = rdf.Filter(category)
    return result


def prepare_region_dataframes(
    rdf, *, mass_regions, categories, systs_to_run, variables=(),
    btag_algo="PNet", era=None, dnn_model_set="updated",
):
    """Build cached region/category nodes, including sideband DNN inputs.

    Keys are (mass region, category, selection suffix); values are
    (RDF, available columns). This performs no histogram booking.
    """
    base_columns = {str(column) for column in rdf.GetColumnNames()} if rdf is not None else set()
    selection_suffixes = {
        GetSelectionSuffixForSystematic(name, info)
        for name, info in systs_to_run.items()
    }
    required_selection_columns = {
        f"{selection}{suffix}"
        for suffix in selection_suffixes
        for selection in (*mass_regions, *categories)
    }
    missing_selection_columns = sorted(required_selection_columns - base_columns)
    if rdf is not None and missing_selection_columns:
        raise RuntimeError(
            "Missing histogram selection column(s): "
            + ", ".join(missing_selection_columns)
        )
    # Apply each sideband DNN once per distinct selection suffix, before any
    # histograms are booked. ApplyDNN materializes its inputs; doing this in
    # the booking loop would otherwise trigger repeated RDF event loops.
    shifted_rdfs = {}
    if rdf is not None and "DNN_NNOutput" in variables:
        for mass_region in mass_regions:
            if not needs_sideband_mass_shift(
                mass_region, "DNN_NNOutput"
            ):
                continue
            for selection_suffix in selection_suffixes:
                mass_column = f"{mass_region}{selection_suffix}"
                region_rdf = rdf.Filter(
                    mass_column,
                    f"{mass_region}_{selection_suffix or 'central'}_dnn_input",
                )
                shifted_rdf = apply_sideband_mass_shifted_dnn(
                    region_rdf,
                    mass_region,
                    btag_algo=btag_algo,
                    era=era,
                    model_set=dnn_model_set,
                )
                shifted_rdfs[(mass_region, selection_suffix)] = (
                    shifted_rdf,
                    {str(column) for column in shifted_rdf.GetColumnNames()},
                )
    # Weight-only systematics share their selection suffix. Cache each
    # region/category filter so its predicate is evaluated once per event,
    # rather than once for every weight variation.
    filtered_rdfs = {}
    if rdf is not None:
        for selection_suffix in selection_suffixes:
            for mass_region in mass_regions:
                mass_column = f"{mass_region}{selection_suffix}"
                shifted_entry = shifted_rdfs.get(
                    (mass_region, selection_suffix)
                )
                region_rdf = (
                    shifted_entry[0]
                    if shifted_entry is not None
                    else rdf.Filter(mass_column)
                )
                for category in categories:
                    category_column = f"{category}{selection_suffix}"
                    cache_key = (
                        mass_region,
                        category,
                        selection_suffix,
                    )
                    if shifted_entry is not None:
                        _, available_columns = shifted_entry
                    else:
                        available_columns = base_columns
                    filtered_rdf = region_rdf.Filter(category_column)
                    filtered_rdfs[cache_key] = (
                        filtered_rdf,
                        available_columns,
                    )
    return filtered_rdfs
