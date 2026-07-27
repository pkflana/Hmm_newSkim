"""Resolve one campaign dataset/process selection from skim_cfg.yaml."""

from collections import OrderedDict
from pathlib import Path

import yaml


def _load_yaml(path):
    with open(path) as handle:
        return yaml.safe_load(handle) or {}


def resolve_dataset_selection(analysis_path, era):
    config_dir = Path(analysis_path) / "config" / era
    skim_cfg = _load_yaml(config_dir / "skim_cfg.yaml")
    processes_cfg = _load_yaml(config_dir / "process_names.yaml")
    samples_cfg = _load_yaml(config_dir / "samples.yaml")
    samples_with_files = _load_yaml(config_dir / "samples_withfiles.yaml")

    selected_processes = skim_cfg.get("process_to_select", []) or []
    whitelist = skim_cfg.get("datasets_whitelist", []) or []
    excluded = set(skim_cfg.get("datasets_exclude", []) or [])
    if not isinstance(selected_processes, list) or not isinstance(whitelist, list):
        raise ValueError(
            "skim_cfg.yaml process_to_select and datasets_whitelist must be lists"
        )

    process_datasets = OrderedDict()
    datasets = []
    datasets.extend(whitelist)
    for process in selected_processes:
        if process not in processes_cfg:
            raise KeyError(
                f"Process {process!r} from skim_cfg.yaml is missing from "
                f"config/{era}/process_names.yaml"
            )
        process_info = processes_cfg[process] or {}
        members = [
            *(process_info.get("datasets", []) or []),
            *(process_info.get("sub_processes", []) or []),
        ]
        members = list(dict.fromkeys(name for name in members if name not in excluded))
        process_datasets[process] = members
        datasets.extend(members)

    datasets = list(dict.fromkeys(name for name in datasets if name not in excluded))
    missing_samples = [name for name in datasets if name not in samples_cfg]
    if missing_samples:
        raise KeyError(
            f"Selected dataset(s) missing from config/{era}/samples.yaml: "
            + ", ".join(missing_samples)
        )

    return {
        "era": era,
        "datasets": datasets,
        "processes": list(process_datasets),
        "process_datasets": process_datasets,
        "datasets_whitelist": whitelist,
        "datasets_exclude": sorted(excluded),
        "datasets_missing_filelist": [
            name
            for name in datasets
            if not isinstance(samples_with_files.get(name), dict)
            or not isinstance(samples_with_files[name].get("filelist"), list)
        ],
    }
