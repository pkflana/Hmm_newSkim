"""Reco-jet and gen-matching components used by DY control fits."""

from __future__ import annotations

from copy import deepcopy


GGF_COMPONENT_VARIABLES = {
    "ggF_0J_Hard": "m_mumu",
    "ggF_1J_Hard": "eta_vs_pt_leadingjet",
    "ggF_1J_PU": "eta_vs_pt_leadingjet",
    "ggF_2J_Hard": "eta_vs_pt_subleadingjet",
    "ggF_2J_PU1": "eta_vs_pt_subleadingjet",
    "ggF_2J_PU2": "eta_vs_pt_subleadingjet",
}

VBF_COMPONENTS = ("VBF_Hard", "VBF_PU1", "VBF_PU2")
DY_JET_COMPONENTS = (*GGF_COMPONENT_VARIABLES, *VBF_COMPONENTS)
DY_COMPONENT_FILE_LABELS = {
    "ggF_0J_Hard": "DY_0J",
    "ggF_1J_Hard": "DY_1J_Hard",
    "ggF_1J_PU": "DY_1J_PU",
    "ggF_2J_Hard": "DY_2J_Hard",
    "ggF_2J_PU1": "DY_2J_PU1",
    "ggF_2J_PU2": "DY_2J_PU2",
    "VBF_Hard": "DY_VBF_Hard",
    "VBF_PU1": "DY_VBF_PU1",
    "VBF_PU2": "DY_VBF_PU2",
}
VBF_ETA_REGIONS = ("incl", "CC", "CF", "FF")


def vbf_eta_region_expressions(base_expression):
    """Split a VBF selection at |eta|=2.5 using the selected VBF pair."""
    eta1 = "abs(SelectedJet_eta{jet_suff}[VBFJetIdx_1{jet_suff}])"
    eta2 = "abs(SelectedJet_eta{jet_suff}[VBFJetIdx_2{jet_suff}])"
    central1 = f"{eta1} < 2.5"
    central2 = f"{eta2} < 2.5"
    return {
        "incl": base_expression,
        "CC": f"({base_expression}) && {central1} && {central2}",
        "CF": (
            f"({base_expression}) && (({central1} && !({central2})) || "
            f"(!({central1}) && {central2}))"
        ),
        "FF": f"({base_expression}) && !({central1}) && !({central2})",
    }


def expanded_jet_component_categories():
    """Internal staging categories needed for split component ROOT files."""
    categories = ["DY_inclusive_ggF"]
    categories.extend(f"DY_inclusive_VBF_{region}" for region in VBF_ETA_REGIONS)
    for component in GGF_COMPONENT_VARIABLES:
        categories.append(component)
    for component in VBF_COMPONENTS:
        categories.extend(f"{component}_{region}" for region in VBF_ETA_REGIONS)
    return tuple(categories)


def add_vbf_eta_region_categories(selection_config):
    """Add inclusive/CC/CF/FF VBF categories independently of DY splitting."""
    config = deepcopy(selection_config)
    categories = config.setdefault("categories", {})
    for region, expression in vbf_eta_region_expressions(
        "VBF{tot_suff}"
    ).items():
        categories[f"VBF_eta_{region}"] = {
            "expression": expression,
            "store": True,
        }
    return config


def add_jet_component_categories(selection_config):
    """Return a config with mutually exclusive reco/gen-matching categories."""
    config = deepcopy(selection_config)
    categories = config.setdefault("categories", {})
    components = {
        "ggF_0J_Hard": "ggF{tot_suff} && N_SelectedJets{jet_suff} == 0",
        "ggF_1J_Hard": (
            "ggF{tot_suff} && N_SelectedJets{jet_suff} == 1 "
            "&& N_PU_FirstTwoJets{jet_suff} == 0"
        ),
        "ggF_1J_PU": (
            "ggF{tot_suff} && N_SelectedJets{jet_suff} == 1 "
            "&& N_PU_FirstTwoJets{jet_suff} == 1"
        ),
        "ggF_2J_Hard": (
            "ggF{tot_suff} && N_SelectedJets{jet_suff} >= 2 "
            "&& N_PU_FirstTwoJets{jet_suff} == 0"
        ),
        "ggF_2J_PU1": (
            "ggF{tot_suff} && N_SelectedJets{jet_suff} >= 2 "
            "&& N_PU_FirstTwoJets{jet_suff} == 1"
        ),
        "ggF_2J_PU2": (
            "ggF{tot_suff} && N_SelectedJets{jet_suff} >= 2 "
            "&& N_PU_FirstTwoJets{jet_suff} == 2"
        ),
        "VBF_Hard": "VBF{tot_suff} && N_PU_VBFJets{jet_suff} == 0",
        "VBF_PU1": "VBF{tot_suff} && N_PU_VBFJets{jet_suff} == 1",
        "VBF_PU2": "VBF{tot_suff} && N_PU_VBFJets{jet_suff} == 2",
    }
    staging = {
        "DY_inclusive_ggF": "ggF{tot_suff}",
        **{
            f"DY_inclusive_VBF_{region}": expression
            for region, expression in vbf_eta_region_expressions(
                "VBF{tot_suff}"
            ).items()
        },
    }
    for name, expression in components.items():
        if name in VBF_COMPONENTS:
            staging.update(
                {
                    f"{name}_{region}": region_expression
                    for region, region_expression in vbf_eta_region_expressions(
                        expression
                    ).items()
                }
            )
        else:
            staging[name] = expression
    for name, expression in staging.items():
        categories[name] = {"expression": expression, "store": True}
    return config


def define_jet_gen_matching(df, selection_suffixes):
    """Define PU-jet counts for the first two reco jets and the VBF pair.

    A reconstructed jet is classified as hard when ``Jet_genJetIdx >= 0`` and
    as PU when no generator-level jet is matched (index < 0).
    """
    columns = {str(column) for column in df.GetColumnNames()}
    for suffix in selection_suffixes:
        selected_index = f"SelectedJet_idx{suffix}"
        selected_gen_index = f"SelectedJet_genJetIdx{suffix}"
        n_selected = f"N_SelectedJets{suffix}"
        if selected_index not in columns:
            raise RuntimeError(
                f"Jet component splitting requires column {selected_index}"
            )
        if selected_gen_index not in columns:
            if "Jet_genJetIdx" not in columns:
                raise RuntimeError(
                    "Jet component splitting requires SelectedJet_genJetIdx "
                    "or the raw MC column Jet_genJetIdx. Regenerate this DY "
                    "skim with the current analysis/jets.py."
                )
            df = df.Define(
                selected_gen_index,
                f"ROOT::VecOps::Take(Jet_genJetIdx, {selected_index})",
            )
            columns.add(selected_gen_index)

        first_two_count = f"N_PU_FirstTwoJets{suffix}"
        if first_two_count not in columns:
            df = df.Define(
                first_two_count,
                (
                    f"int(({n_selected} > 0 && {selected_gen_index}[0] < 0) + "
                    f"({n_selected} > 1 && {selected_gen_index}[1] < 0))"
                ),
            )
            columns.add(first_two_count)

        # Generic, process-independent 0/1/2J flags. Here J denotes the
        # number of the first two selected reco jets without a GenJet match.
        for count in (0, 1, 2):
            flag = f"RecoGenJetMatch_{count}J{suffix}"
            if flag not in columns:
                df = df.Define(flag, f"{first_two_count} == {count}")
                columns.add(flag)

        vbf_count = f"N_PU_VBFJets{suffix}"
        if vbf_count not in columns:
            df = df.Define(
                vbf_count,
                (
                    f"HasVBF{suffix} ? int("
                    f"({selected_gen_index}[VBFJetIdx_1{suffix}] < 0) + "
                    f"({selected_gen_index}[VBFJetIdx_2{suffix}] < 0)) : -1"
                ),
            )
            columns.add(vbf_count)
    return df


def variable_for_component(category, requested_variables):
    """Choose the prescribed ggF fit observable; leave VBF configurable."""
    if category in GGF_COMPONENT_VARIABLES:
        return (GGF_COMPONENT_VARIABLES[category],)
    for component, variable in GGF_COMPONENT_VARIABLES.items():
        if category.startswith(f"{component}_"):
            return (variable,)
    return tuple(requested_variables)
