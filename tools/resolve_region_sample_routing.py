#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from common.region_sample_routing import (
    groups_for_region,
    jet_gen_component_processes,
    load_routing,
    separate_groups,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--region", choices=["Signal_Fit", "sidebands", "separate"])
    parser.add_argument(
        "--field",
        choices=["groups", "processes"],
        default="groups",
    )
    args = parser.parse_args()
    analysis_path = Path(os.environ.get("ANALYSIS_PATH", Path(__file__).parents[1]))
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
