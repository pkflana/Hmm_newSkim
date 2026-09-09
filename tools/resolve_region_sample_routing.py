#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from common.dataset_utilities import (
    groups_for_region,
    production_samples,
    jet_gen_component_processes,
    load_routing,
    separate_groups,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--region", choices=["Signal_Fit", "H_sideband", "Z_sideband", "mass_inclusive", "sidebands", "separate"])
    parser.add_argument(
        "--field",
        choices=["groups", "processes"],
        default="groups",
    )
    parser.add_argument("--selection", choices=["signals", "region_higgs", "region_inclusive", "flash_backgrounds", "FlashSim"])
    args = parser.parse_args()
    analysis_path = Path(os.environ.get("ANALYSIS_PATH", Path(__file__).parents[1]))
    if args.selection:
        print("\n".join(production_samples(analysis_path, args.era, args.selection)))
        return
    config = load_routing(analysis_path / "config/histogram_sample_routing.yaml")
    if args.field == "processes":
        values = jet_gen_component_processes(config)
    elif args.region == "separate":
        values = separate_groups(config, args.era)
    else:
        values = groups_for_region(config, args.era, args.region)
    print(",".join(values))


if __name__ == "__main__":
    main()
