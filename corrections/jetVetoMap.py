#!/usr/bin/env python3
import gzip
import json
import re

import ROOT
import correctionlib

from .general import pog_folder_names, period_names

correctionlib.register_pyroot_binding()

JME_vetoMap_JsonPath = (
    "/cvmfs/cms-griddata.cern.ch/cat/metadata/JME/{}/latest/jetvetomaps.json.gz"
)
JME_jetId_JsonPath = (
    "/cvmfs/cms-griddata.cern.ch/cat/metadata/JME/{}/latest/jetid.json.gz"
)

jetvetomap_names = {
    "2022_Summer22": "Summer22_23Sep2023_RunCD_V1",
    "2022_Summer22EE": "Summer22EE_23Sep2023_RunEFG_V1",
    "2023_Summer23BPix": "Summer23BPixPrompt23_RunD_V1",
    "2023_Summer23": "Summer23Prompt23_RunC_V1",
    "2024_Summer24": "Summer24Prompt24_RunBCDEFGHI_V1",
    "2025_Winter25": "Winter25Prompt25_RunCDEFG_V1",
    "2025_Summer24": "Winter25Prompt25_RunCDEFG_V1",
}

_initialized = set()


def _get_jet_id_correction_names(jet_id_file, jet_algorithm="AK4PUPPI"):
    with gzip.open(jet_id_file, "rt") as f:
        payload = json.load(f)

    correction_names = {corr["name"] for corr in payload["corrections"]}
    tight_name = f"{jet_algorithm}_Tight"
    tight_lep_veto_name = f"{jet_algorithm}_TightLeptonVeto"

    missing_names = [
        name
        for name in [tight_name, tight_lep_veto_name]
        if name not in correction_names
    ]
    if missing_names:
        raise RuntimeError(
            f"Missing JetID correction(s) {missing_names} in {jet_id_file}. "
            f"Available corrections: {sorted(correction_names)}"
        )

    return tight_name, tight_lep_veto_name


def _sanitize_cpp_name(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _declare_correction_helpers(
    period,
    veto_map_file,
    jet_id_file,
    veto_map_name,
    tight_jet_id_name,
    tight_lep_veto_jet_id_name,
):
    suffix = _sanitize_cpp_name(period)
    if suffix in _initialized:
        return suffix

    ROOT.gROOT.ProcessLine(
        f'auto HMM_jetveto_cset_{suffix} = correction::CorrectionSet::from_file("{veto_map_file}");'
    )
    ROOT.gROOT.ProcessLine(
        f'auto HMM_jetid_cset_{suffix} = correction::CorrectionSet::from_file("{jet_id_file}");'
    )
    ROOT.gROOT.ProcessLine(
        f'auto HMM_jetveto_corr_{suffix} = HMM_jetveto_cset_{suffix}->at("{veto_map_name}");'
    )
    ROOT.gROOT.ProcessLine(
        f'auto HMM_jetid_tight_corr_{suffix} = HMM_jetid_cset_{suffix}->at("{tight_jet_id_name}");'
    )
    ROOT.gROOT.ProcessLine(
        f'auto HMM_jetid_tight_lep_veto_corr_{suffix} = HMM_jetid_cset_{suffix}->at("{tight_lep_veto_jet_id_name}");'
    )

    ROOT.gInterpreter.Declare(
        f"""
        #ifndef HMM_JET_VETO_MAP_HELPERS_{suffix}
        #define HMM_JET_VETO_MAP_HELPERS_{suffix}

        ROOT::VecOps::RVec<bool> HMM_Jet_isInsideVetoRegion_{suffix}(
            const ROOT::VecOps::RVec<float>& Jet_eta,
            const ROOT::VecOps::RVec<float>& Jet_phi
        ) {{
            ROOT::VecOps::RVec<bool> result(Jet_eta.size(), false);
            for (size_t i = 0; i < Jet_eta.size(); ++i) {{
                const float veto_value =
                    HMM_jetveto_corr_{suffix}->evaluate({{"jetvetomap", Jet_eta[i], Jet_phi[i]}});
                result[i] = veto_value != 0.f;
            }}
            return result;
        }}

        template <typename ChMultiplicityT, typename NeMultiplicityT, typename MultiplicityT>
        ROOT::VecOps::RVec<bool> HMM_Jet_passJetIdFromCorrection_{suffix}(
            const ROOT::VecOps::RVec<float>& Jet_eta,
            const ROOT::VecOps::RVec<float>& Jet_chHEF,
            const ROOT::VecOps::RVec<float>& Jet_neHEF,
            const ROOT::VecOps::RVec<float>& Jet_chEmEF,
            const ROOT::VecOps::RVec<float>& Jet_neEmEF,
            const ROOT::VecOps::RVec<float>& Jet_muEF,
            const ChMultiplicityT& Jet_chMultiplicity,
            const NeMultiplicityT& Jet_neMultiplicity,
            const MultiplicityT& Jet_nConstituents,
            const bool tight_lepton_veto
        ) {{
            ROOT::VecOps::RVec<bool> result(Jet_eta.size(), false);
            const auto& corr =
                tight_lepton_veto ? HMM_jetid_tight_lep_veto_corr_{suffix}
                                  : HMM_jetid_tight_corr_{suffix};

            for (size_t i = 0; i < Jet_eta.size(); ++i) {{
                const float jet_id =
                    corr->evaluate({{
                        Jet_eta[i],
                        Jet_chHEF[i],
                        Jet_neHEF[i],
                        Jet_chEmEF[i],
                        Jet_neEmEF[i],
                        Jet_muEF[i],
                        static_cast<int>(Jet_chMultiplicity[i]),
                        static_cast<int>(Jet_neMultiplicity[i]),
                        static_cast<int>(Jet_nConstituents[i])
                    }});
                result[i] = jet_id != 0.f;
            }}
            return result;
        }}

        #endif
        """
    )

    _initialized.add(suffix)
    return suffix


def apply_jet_veto_map(
    df,
    config,
    apply_filter=True,
    define_electron_cleaning=False,
):
    era = config.get("era")
    period = period_names[era]
    folder_name = pog_folder_names["JERC"][period]
    veto_map_file = JME_vetoMap_JsonPath.format(folder_name)
    jet_id_file = JME_jetId_JsonPath.format(folder_name)
    veto_map_name = jetvetomap_names[period]
    tight_jet_id_name, tight_lep_veto_jet_id_name = _get_jet_id_correction_names(
        jet_id_file
    )

    suffix = _declare_correction_helpers(
        period,
        veto_map_file,
        jet_id_file,
        veto_map_name,
        tight_jet_id_name,
        tight_lep_veto_jet_id_name,
    )
    available_columns = {str(column) for column in df.GetColumnNames()}
    jet_pt_column = "Jet_pt_corr" if "Jet_pt_corr" in available_columns else "Jet_pt"

    df = df.Define(
        "Jet_isInsideVetoRegion",
        f"HMM_Jet_isInsideVetoRegion_{suffix}(Jet_eta, Jet_phi)",
    )
    df = df.Define(
        "Jet_passJetIdTight",
        f"HMM_Jet_passJetIdFromCorrection_{suffix}(Jet_eta, Jet_chHEF, Jet_neHEF, Jet_chEmEF, Jet_neEmEF, Jet_muEF, Jet_chMultiplicity, Jet_neMultiplicity, Jet_nConstituents, false)",
    )
    df = df.Define(
        "Jet_passJetIdTightLepVeto",
        f"HMM_Jet_passJetIdFromCorrection_{suffix}(Jet_eta, Jet_chHEF, Jet_neHEF, Jet_chEmEF, Jet_neEmEF, Jet_muEF, Jet_chMultiplicity, Jet_neMultiplicity, Jet_nConstituents, true)",
    )
    df = df.Define(
        "Jet_vetoMapLooseRegion_presel",
        f"{jet_pt_column} > 15 && Jet_passJetIdTightLepVeto && (Jet_chEmEF + Jet_neEmEF < 0.9) && Jet_isInsideVetoRegion",
    )
    if (
        "Muon_p4_ScaRe_FSR" not in available_columns
        and "Muon_p4_nano_scare_FSR" in available_columns
        and "Muon_bsc_p4_nano_scare_FSR" in available_columns
    ):
        df = df.Define(
            "Muon_p4_ScaRe_FSR",
            """
            RVecLV muon_p4(Muon_p4_nano_scare_FSR.size());
            for (size_t i = 0; i < muon_p4.size(); ++i) {
                muon_p4[i] = Muon_bsConstrainedChi2[i] < 30 ?
                    Muon_bsc_p4_nano_scare_FSR[i] :
                    Muon_p4_nano_scare_FSR[i];
            }
            return muon_p4;
            """,
        )
        available_columns.add("Muon_p4_ScaRe_FSR")

    if "Jet_p4" in available_columns and "Muon_p4_ScaRe_FSR" in available_columns:
        df = df.Define(
            "Jet_vetoMap",
            "RemoveOverlaps(Jet_p4, Jet_vetoMapLooseRegion_presel, Muon_p4_ScaRe_FSR[Muon_isPFcand], 0.2)",
        )
    else:
        df = df.Define("Jet_vetoMap", "Jet_vetoMapLooseRegion_presel")

    available_columns = {str(column) for column in df.GetColumnNames()}
    if (
        define_electron_cleaning
        and "Jet_p4" in available_columns
        and "Electron_p4" in available_columns
    ):
        df = df.Define(
            "Jet_vetoMapEle",
            "RemoveOverlaps(Jet_p4, Jet_vetoMap, Electron_p4[Electron_isPFcand], 0.2)",
        )

    if apply_filter:
        return df.Filter("ROOT::VecOps::Nonzero(Jet_vetoMap).size() == 0", "Jet Veto Map filter")
    return df


def GetJetVetoMap(df, config):
    return apply_jet_veto_map(df, config, apply_filter=False)


def ApplyJetVetoMap(
    df,
    config,
    apply_filter=True,
    defineElectronCleaning=False,
    isV12=False,
):
    return apply_jet_veto_map(
        df,
        config,
        apply_filter=apply_filter,
        define_electron_cleaning=defineElectronCleaning,
    )


__all__ = [
    "apply_jet_veto_map",
    "GetJetVetoMap",
    "ApplyJetVetoMap",
]
