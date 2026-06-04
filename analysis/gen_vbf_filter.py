import os
import sys
import ROOT

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities


_INCLUSIVE_SAMPLES = {
    "DYto2Mu_MLL105To160",
    "DYto2Mu_MLL_105to160_amcatnloFXFX",
}

_VBF_FILTERED_SAMPLES = {
    "DYto2Mu_MLL105To160_VBFFiltered",
    "DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF",
}


def _declare_gen_vbf_filter():
    header_path = os.path.join(os.environ["ANALYSIS_PATH"], "common", "GenVBFFilter.cpp")
    utilities.DeclareHeader(header_path)


def ApplyGenVBFFilter(df, era, dataset_name, process_name=None):
    if era != "Run3_2024":
        return df

    sample_names = {dataset_name}
    if process_name:
        sample_names.add(process_name)

    if sample_names & _INCLUSIVE_SAMPLES:
        filter_expr = "!GenVBFFilter"
        filter_label = "DY MLL105To160 inclusive: remove GenVBFFilter phase space"
    elif sample_names & _VBF_FILTERED_SAMPLES:
        filter_expr = "GenVBFFilter"
        filter_label = "DY MLL105To160 VBF filtered: keep GenVBFFilter phase space"
    else:
        return df

    _declare_gen_vbf_filter()
    df = df.Define(
        "GenVBFFilter",
        "genVBFFilter_func(GenJet_pt, GenJet_eta, GenJet_phi, GenJet_mass, "
        "GenPart_pt, GenPart_eta, GenPart_phi, GenPart_mass, "
        "GenPart_pdgId, GenPart_statusFlags)"
    )
    return df.Filter(filter_expr, filter_label)
