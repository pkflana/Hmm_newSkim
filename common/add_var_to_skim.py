"""Selections added to skim dataframes for histogram production.

Physics-object observables remain in ``add_vars_to_skim_tuples`` for backward
compatibility.  Histogram regions and categories have a single home here.
"""


def _column_names(df):
    return {str(column) for column in df.GetColumnNames()}


def _selection_suffixes(syst_cfg=None, want_variations=False):
    suffixes = [("", "", "")]
    if not want_variations or not syst_cfg:
        return suffixes

    scales = syst_cfg.get("scales", ["up", "down"])
    for syst_name, syst_info in syst_cfg.get("systematics", {}).items():
        if syst_name == "Central":
            continue
        for scale in scales:
            suffixes.append(
                (
                    f"_{syst_name}{scale.capitalize()}",
                    syst_info.get("muon_suffix", "").format(scale=scale),
                    syst_info.get("jet_suffix", "").format(scale=scale),
                )
            )
    return suffixes


def GetSelectionSuffixForSystematic(syst_name, syst_info=None):
    """Return the suffix shared by the selections of one systematic."""
    if syst_name == "Central" or syst_info is None:
        return ""
    if not syst_info.get("muon_suffix", "") and not syst_info.get(
        "jet_suffix", ""
    ):
        return ""
    return f"_{syst_name}"


def DefineHistogramSelections(df, sel_config, syst_cfg=None, want_variations=False):
    """Define mass regions, object selections, and histogram categories."""
    defined_columns = _column_names(df)
    section_suffix_key = {
        "masses_regions": "tot",
        "muons_selection": "mu",
        "jets_selection": "jet",
        "categories": "tot",
    }

    for section, suffix_key in section_suffix_key.items():
        for selection_name, content in sel_config.get(section, {}).items():
            expression_template = (
                content.get("expression", "")
                if isinstance(content, dict)
                else content
            )
            if not expression_template:
                print(
                    f"[WARNING] Empty selection expression for "
                    f"{selection_name}. Skipping."
                )
                continue

            for total_suffix, muon_suffix, jet_suffix in _selection_suffixes(
                syst_cfg=syst_cfg,
                want_variations=want_variations,
            ):
                suffix = {
                    "tot": total_suffix,
                    "mu": muon_suffix,
                    "jet": jet_suffix,
                }[suffix_key]
                column_name = f"{selection_name}{suffix}"
                expression = expression_template.format(
                    tot_suff=total_suffix,
                    mu_suff=muon_suffix,
                    jet_suff=jet_suffix,
                )
                if column_name in defined_columns:
                    if section != "muons_selection":
                        df = df.Redefine(column_name, expression)
                else:
                    df = df.Define(column_name, expression)
                    defined_columns.add(column_name)
    return df
