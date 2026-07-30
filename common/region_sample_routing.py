"""Resolve histogram dataset groups from era and mass-region policy."""

from pathlib import Path

import yaml


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
    key = "Signal_Fit" if mass_region == "Signal_Fit" else "sidebands"
    return tuple(policy[key])


def separate_groups(config, era):
    return tuple(era_policy(config, era).get("separate", []))


def jet_gen_component_processes(config):
    return tuple(config["jet_gen_components"]["enabled_processes"])
