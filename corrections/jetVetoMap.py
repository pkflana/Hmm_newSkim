#!/usr/bin/env python3
import os
import ROOT
import correctionlib

from .general import pog_folder_names, period_names

correctionlib.register_pyroot_binding()

def GetJetVetoMap(df, config):
    JME_vetoMap_JsonPath = (
        "/cvmfs/cms-griddata.cern.ch/cat/metadata/JME/{}/latest/jetvetomaps.json.gz"
    )
    era = config.get("era")
    period_unc = period_names[era]

    jetvetomap_names = {
        "2022_Summer22": "Summer22_23Sep2023_RunCD_V1",  # period: , entryname
        "2022_Summer22EE": "Summer22EE_23Sep2023_RunEFG_V1",
        "2023_Summer23BPix": "Summer23BPixPrompt23_RunD_V1",
        "2023_Summer23": "Summer23Prompt23_RunC_V1",
        "2024_Summer24": "Summer24Prompt24_RunBCDEFGHI_V1",
        "2025_Winter25": "Winter25Prompt25_RunCDEFG_V1",
        "2025_Summer24": "Winter25Prompt25_RunCDEFG_V1",
    }
    entry_name = jetvetomap_names[period_unc]
    JME_vetoMap_JsonFile =JME_vetoMap_JsonPath.format(pog_folder_names["JERC"][period_unc])

    headers_dir = os.path.dirname(os.path.abspath(__file__))
    header_path = os.path.join(headers_dir, "jetVetoMap.h")
    ROOT.gInterpreter.Declare(f'#include "{header_path}"')
    ROOT.gInterpreter.ProcessLine(
        f'::correction::JetVetoMapProvider::Initialize("{JME_vetoMap_JsonFile}", "{entry_name}")'
    )
    # jet pT > 15 GeV, tight jet ID, PU jet ID for CHS jets with pT < 50 GeV,  jet EM fraction (charged + neutral) < 0.9
    df = df.Define(
        f"Jet_isInsideVetoRegion",
        f"""::correction::JetVetoMapProvider::getGlobal().GetJetVetoMapValues(Jet_p4)""",
    )
    return df



def ApplyJetVetoMap(df, config, apply_filter=True, defineElectronCleaning=False, isV12=False):
    df = GetJetVetoMap(df, config)
    function_for_jetId = (
        "JetIdNewDef::RedefineJet_passJetIdTight_v12(Jet_p4, Jet_neHEF, Jet_neEmEF, Jet_jetId)"
        if isV12
        else "JetIdNewDef::RedefineJet_passJetIdTight_v13(Jet_p4, Jet_neHEF, Jet_neEmEF, Jet_chHEF, Jet_chMultiplicity, Jet_neMultiplicity )"
    )
    df = df.Define(f"Jet_passJetIdTight", function_for_jetId)
    df = df.Define(
        f"Jet_passJetIdTightLepVeto",
        "JetIdNewDef::Redefine_Jet_passJetIdTightLepVeto(Jet_p4, Jet_passJetIdTight, Jet_muEF, Jet_chEmEF)",
    )
    df = df.Define(
        f"Jet_vetoMapLooseRegion_presel",
        "Jet_pt > 15 && ( Jet_passJetIdTightLepVeto ) && (Jet_chEmEF + Jet_neEmEF < 0.9) && Jet_isInsideVetoRegion",  # here goes the new Jet ID
    )  #  (Jet_puId > 0 || Jet_pt >50) &&  for CHS jets


    df = df.Define(
        f"Jet_vetoMap",
        " RemoveOverlaps(Jet_p4, Jet_vetoMapLooseRegion_presel, Muon_p4_ScaRe_FSR[Muon_isPFcand], 0.2)",
    )
    jet_veto_map_string = "Jet_vetoMap"

    if defineElectronCleaning:
        df = df.Define(
            f"Jet_vetoMapEle",
            " RemoveOverlaps(Jet_p4, Jet_vetoMap, Electron_p4[Electron_isPFcand], 0.2)",
        )
        jet_veto_map_string+="Ele"

    if apply_filter:
        return df.Filter(f"Jet_p4[{jet_veto_map_string}].size()==0", "Jet Veto Map filter")
    return df
