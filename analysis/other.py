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

