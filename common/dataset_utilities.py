"""Dataset selection and region-routing helpers for campaigns."""

from collections import OrderedDict
from pathlib import Path

import yaml


def _load_yaml(path):
    with open(path) as handle:
        return yaml.safe_load(handle) or {}


def resolve_dataset_selection(analysis_path, era):
    """Resolve the canonical dataset/process selection from skim_cfg.yaml."""
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
    datasets = list(whitelist)
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


def load_routing(path):
    with Path(path).open() as handle:
        return yaml.safe_load(handle)


def era_policy(config, era):
    for policy in config["mass_region_routing"].values():
        if era in policy.get("eras", []):
            return policy
    raise ValueError(f"No mass-region sample routing configured for {era}")


def groups_for_region(config, era, mass_region):
    policy = era_policy(config, era)
    key = mass_region if mass_region in ("Signal_Fit", "H_sideband") else "sidebands"
    return tuple(policy[key])


def separate_groups(config, era):
    return tuple(era_policy(config, era).get("separate", []))


def jet_gen_component_processes(config):
    return tuple(config["jet_gen_components"]["enabled_processes"])


def dataset_region_allowed(dataset, region):
    """Use the matching generated mass window for DY/EWK, including FlashSim."""
    name = dataset.lower().replace("_", "")
    if not name.startswith(("dy", "ewk")):
        return True
    restricted = "105to160" in name
    return restricted == (region in ("Signal_Fit", "H_sideband"))


def production_samples(analysis_path, era, group):
    """Canonical nominal samples and configured FlashSim counterparts."""
    if group == 'FlashSim':
        return sorted({name for subset in ('signals', 'region_higgs', 'region_inclusive', 'flash_backgrounds')
                       for name in production_samples(analysis_path, era, subset) if 'flashsim' in name.lower()})
    folder = Path(analysis_path) / 'config' / era
    samples = _load_yaml(folder / 'samples.yaml')
    processes = _load_yaml(folder / 'process_names.yaml')
    skim = _load_yaml(folder / 'skim_cfg.yaml')
    excluded = set(skim.get('datasets_exclude', []) or [])
    selected = []
    for process, entry in processes.items():
        names = [*(entry.get('datasets', []) or []), *(entry.get('sub_processes', []) or [])]
        for name in names:
            lower = name.lower()
            signal = lower.startswith(('glugluh', 'vbfh')) and 'to2mu' in lower
            if group == 'signals':
                keep = signal and not any(x in lower for x in ('120', '130', 'tune', 'minnlo'))
            elif group in ('region_higgs', 'region_inclusive'):
                nominal = process in ('DY', 'DYto2Mu_MLL105To160', 'EWK',
                    'EWK_2Mu2J_MLL_105to160_herwig', 'EWK_2Mu2J_MLL_105to160_pythia')
                keep = name.lower().startswith(('dy', 'ewk')) and (nominal or 'flashsim' in lower)
                keep = keep and dataset_region_allowed(name, 'H_sideband' if group == 'region_higgs' else 'Z_sideband')
            elif group == 'flash_backgrounds':
                keep = 'flashsim' in lower and not signal and not lower.startswith(('dy', 'ewk'))
            else:
                raise ValueError(group)
            if keep and name in samples and name not in excluded:
                selected.append(name)
    return sorted(set(selected))
