import ROOT
import os

def applyMETFlags(df, config, is_data):
    MET_flags = config.get("MET_flags", [])
    badMET_flag_runs = config.get("badMET_flag_runs", [])
    if badMET_flag_runs:
        df = applyBadMETfilter(df, badMET_flag_runs, is_data)
    MET_flags_string = " && ".join(MET_flags)
    return df.Filter(MET_flags_string, "MET filters")

def applyBadMETfilter(df, badMET_flag_runs, is_data):
    if not is_data:
        return df
    else:
        # https://twiki.cern.ch/twiki/bin/view/CMS/MissingETOptionalFiltersRun2#ECal_BadCalibration_Filter_Flag
        df = df.Define(
            f"Flag_badMET_calib",
            f""" !( PuppiMET_p4.pt()>100 &&
                                                Any(v_ops::pt(Jet_p4) > 50
                                                && v_ops::eta(Jet_p4) >= -0.5 && v_ops::eta(Jet_p4) <= -0.1
                                                && v_ops::phi(Jet_p4) >= -2.1 && v_ops::phi(Jet_p4) <= -1.8
                                                && abs(PuppiMET_p4.phi() - v_ops::phi(Jet_p4)) > 2.9
                                                && (Jet_neEmEF > 0.9 || Jet_chEmEF > 0.9)
                                                ) )""",
        )

        df = df.Redefine(
            f"Flag_ecalBadCalibFilter",
            f" ( run >= {badMET_flag_runs[0]} && run <= {badMET_flag_runs[1]} ) ? Flag_badMET_calib : Flag_ecalBadCalibFilter",
        )
        return df


import ROOT

def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}

def DefineCategoryBooleans(df, sel_config, is_data, want_variations=False):
    """
    Parses the flat 'categories' section from the YAML config.
    Applies systematic suffix replacements purely using python's .format()
    and configuration keys, with zero hardcoded physics objects.
    """
    categories_dict = sel_config.get("categories", {})
    categories_dict.update(sel_config.get("masses_regions", {}))
    # print(categories_dict)
    vars_to_store = []

    # Lista delle variazioni attive su cui ciclare
    suffixes = [""]  # Nominal

    # if not is_data and want_variations:
    #     suffixes.extend([
    #         "_JERUp", "_JERDown", "_TotalUp", "_TotalDown",
    #         "_scale_FSR_up", "_scale_FSR_down", "_resol_FSR_up", "_resol_FSR_down"
    #     ])
    # print(suffixes)
    for suff in suffixes:
        for cat_name, cat_content in categories_dict.items():

            # 1. Estrazione del contenuto dal dizionario dello YAML
            if isinstance(cat_content, dict):
                base_expression = cat_content.get("expression", "")
                should_store = cat_content.get("store", True)
            else:
                base_expression = cat_content
                should_store = True

            if not base_expression:
                continue

            # 2. Sostituzione dei token delle macro-categorie dipendenti
            # (es: "baseline" diventa "baseline_JERUp" se siamo nel loop JERUp)
            formatted_expr = base_expression
            for defined_cat in categories_dict.keys():
                # print(f"Processing category '{cat_name}' with base expression: {base_expression}and defined cat {defined_cat}")
                formatted_expr = formatted_expr.replace(f"{defined_cat} ", f"{defined_cat}{suff} ")
                formatted_expr = formatted_expr.replace(f"({defined_cat})", f"({defined_cat}{suff})")
                if formatted_expr.endswith(defined_cat):
                    formatted_expr = formatted_expr + suff

            # 3. Risoluzione dei placeholder {suff} scritti esplicitamente nello YAML
            # Questo sostituisce simultaneamente muoni, jet, b-tag senza avere liste hardcoded nel codice!
            formatted_expr = formatted_expr.format(suff=suff)

            # 4. Generazione della colonna nell'RDataFrame
            final_column_name = f"{cat_name}{suff}" if suff != "" else cat_name

            if final_column_name not in _column_names(df):
                df = df.Define(final_column_name, formatted_expr)

                if should_store:
                    vars_to_store.append(final_column_name)

    return df, vars_to_store