#!/usr/bin/env python3
"""Print unweighted event counts and weighted yields for histogram selections."""

import argparse
import os
import re
import sys
from pathlib import Path

import ROOT

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("ANALYSIS_PATH", str(REPO))

import common.utilities as utilities
from common.prepare_rdf import finalize_histogram_dataframe
from common.jet_component_splitting import define_jet_gen_matching
from common.utilities import (
    read_manifest,
    list_root_files,
    get_segmentation_dict,
    initialize_root_runtime,
    validate_file,
)
from common.prepare_rdf import GetRdfForDataset

ROOT.gROOT.SetBatch(True)
initialize_root_runtime()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era", required=True)
    parser.add_argument("--sample-name", "--dataset-name", "--dataset", dest="dataset_name", required=True)
    parser.add_argument("--input-manifest")
    parser.add_argument("--root-input", "--input")
    parser.add_argument("--json-input", "--metadata-input")
    parser.add_argument("--additional-cuts")
    parser.add_argument("--mass-regions", nargs="+")
    parser.add_argument("--categories", nargs="+")
    return parser.parse_args()


def resolve_inputs(args):
    if args.input_manifest:
        manifest = read_manifest(args.input_manifest)
        if manifest.get("stage") != "validation" or manifest.get("status", "passed") != "passed":
            raise RuntimeError(f"Manifest is not a passed validation manifest: {args.input_manifest}")
        if manifest.get("era") != args.era or manifest.get("dataset") != args.dataset_name:
            raise ValueError("Manifest era/dataset does not match the requested cutflow")
        return manifest["valid_root_files"], manifest["valid_json_files"]
    if not args.root_input or not args.json_input:
        raise ValueError("Pass --input-manifest or both --root-input and --json-input")
    root_files = list_root_files(args.root_input)
    results = [validate_file((path, "Events")) for path in root_files]
    invalid = [(path, reason) for path, valid, reason in results if not valid]
    if invalid:
        raise RuntimeError("Invalid ROOT input(s):\n" + "\n".join(f"  {p}: {r}" for p, r in invalid))
    return [path for path, _, _ in results], [args.json_input]


def selected_names(config, section, requested=None):
    names = [name for name, info in config.get(section, {}).items() if info.get("store", False)]
    return [name for name in names if requested is None or name in requested]


def normalize_expression(expression):
    for suffix in ("{mu_suff}", "{jet_suff}", "{tot_suff}"):
        expression = expression.replace(suffix, "")
    return expression.strip()


def expanded_selection_expressions(config):
    definitions = {
        name: normalize_expression(info["expression"])
        for section in ("muons_selection", "jets_selection", "masses_regions", "categories")
        for name, info in config.get(section, {}).items()
        if "expression" in info
    }
    resolved = {}

    def resolve(name, active=()):
        if name in resolved:
            return resolved[name]
        expression = definitions[name]
        for dependency in definitions:
            if dependency != name and dependency not in active and re.search(rf"\b{re.escape(dependency)}\b", expression):
                expression = re.sub(rf"\b{re.escape(dependency)}\b", f"({resolve(dependency, active + (name,))})", expression)
        resolved[name] = expression
        return expression

    return {name: resolve(name) for name in definitions}


def main():
    args = parse_args()
    root_files, metadata_inputs = resolve_inputs(args)
    cfg_dir = REPO / "config" / args.era
    main_cfg = utilities.get_config(cfg_dir / "maincfg.yaml")
    samples_cfg = utilities.get_config(cfg_dir / "samples.yaml")
    selections_cfg = utilities.get_config(cfg_dir / "selections.yaml")
    selection_cuts = expanded_selection_expressions(selections_cfg)
    systematics_cfg = utilities.get_config(cfg_dir / "systematics.yaml")
    is_data = samples_cfg.get(args.dataset_name, {}).get("is_data", False) or "data" in args.dataset_name.lower()
    weight = systematics_cfg["systematics"]["Central"]["weight"]
    seg_dict = None if is_data else get_segmentation_dict(metadata_inputs, node="gen", fallback_to_initial=True)
    rdf = GetRdfForDataset(
        input_dir=args.root_input, is_data=is_data, weight_dict=systematics_cfg["weights"],
        store_shifted_weights=False, treeName="Events", explicit_files=root_files, seg_dict=seg_dict,
        skip_validation=True, dnn_payloads=[], btag_algo=main_cfg.get("bTagAlgo", "PNet"),
        additional_cuts=None, era=args.era, dnn_model_set="updated",
        qcd_scale_config=systematics_cfg.get("qcd_scale"), qcd_scale_seg_dicts={},
        pdf_config=systematics_cfg.get("pdf"),
    )
    columns = {str(column) for column in rdf.GetColumnNames()}
    if not is_data and ({"Jet_genJetIdx", "SelectedJet_genJetIdx"} & columns):
        rdf = define_jet_gen_matching(rdf, {""})
    rdf = finalize_histogram_dataframe(
        rdf, args.dataset_name, selections_cfg, systematics_cfg, [weight], args.era
    )
    base = rdf
    rows = [("input", "all", "true", rdf)]
    if args.additional_cuts:
        base = rdf.Filter(args.additional_cuts, "additional_cuts")
        rows.append(("additional_cut", "additional_cuts", args.additional_cuts, base))
    for section in ("muons_selection", "jets_selection"):
        rows.extend(
            (section, name, selection_cuts[name], base.Filter(name))
            for name in selected_names(selections_cfg, section)
        )
    regions = selected_names(selections_cfg, "masses_regions", args.mass_regions)
    categories = selected_names(selections_cfg, "categories", args.categories)
    region_cuts = {name: selection_cuts[name] for name in regions}
    category_cuts = {name: selection_cuts[name] for name in categories}
    rows.extend(("mass_region", region, region_cuts[region], base.Filter(region)) for region in regions)
    rows.extend(("category", category, category_cuts[category], base.Filter(category)) for category in categories)
    rows.extend(
        ("histogram", f"{region}/{category}", f"({region_cuts[region]}) && ({category_cuts[category]})", base.Filter(region).Filter(category))
        for region in regions for category in categories
    )
    actions = [(section, name, cut, node.Count(), node.Sum(weight)) for section, name, cut, node in rows]
    ROOT.RDF.RunGraphs([action for _, _, _, count, total in actions for action in (count, total)])
    print(f"{'section':<18} {'selection':<42} {'NEntries':>14} {'Yield':>20} {'Efficiency':>14}")
    print("-" * 114)
    previous_count = None
    for section, name, cut, count, total in actions:
        entries = int(count.GetValue())
        if previous_count is None:
            efficiency = "100.0000%"
        elif previous_count == 0:
            efficiency = "n/a"
        else:
            efficiency = f"{100.0 * entries / previous_count:.4f}%"
        print(f"{section:<18} {name:<42} {entries:>14d} {float(total.GetValue()):>20.8g} {efficiency:>14}")
        previous_count = entries


if __name__ == "__main__":
    main()
