from pathlib import Path
import os
import ROOT
from .general import pog_folder_names,period_names


##### ID + trigger ####
muIDEff_JsonPath = (
    "/cvmfs/cms-griddata.cern.ch/cat/metadata/MUO/{}/latest/muon_Z.json.gz"
)
MediumMu_SF_Sources_dict = {
    # reco SF
    "NUM_TrackerMuons_DEN_genTracks": "Reco",  # --> used in Run 2 - NOT FOR RUN 3!! https://muon-wiki.docs.cern.ch/guidelines/corrections/#medium-pt-30-gev-pt-200-gev "No correction is recommended for Run 3 data. Data/MC scale factors are expected to be 1 and therefore no correction is needed/provided."
    # ID SF - with tracker muons - RECOMMENDED
    "NUM_LooseID_DEN_TrackerMuons": "LooseID_Trk",
    "NUM_MediumID_DEN_genTracks": "MediumID_genTrk",
    "NUM_MediumPromptID_DEN_TrackerMuons": "MediumPromptID_Trk",
    "NUM_MediumID_DEN_TrackerMuons": "MediumID_Trk",
    "NUM_TightID_DEN_TrackerMuons": "TightID_Trk",
    "NUM_SoftID_DEN_TrackerMuons": "SoftID_Trk",
    "NUM_HighPtID_DEN_TrackerMuons": "HighPtID_Trk",
    "NUM_TrkHighPtID_DEN_TrackerMuons": "TrkHighPtID_Trk",
    # Iso SF
    "NUM_LoosePFIso_DEN_LooseID": "LoosePFIso_LooseID",  # loose ID, loose iso
    "NUM_LoosePFIso_DEN_MediumID": "LoosePFIso_MediumID",  # medium ID, loose  iso
    "NUM_LoosePFIso_DEN_MediumPromptID": "LoosePFIso_MediumPromptID",  # medium prompt ID, loose iso
    "NUM_LoosePFIso_DEN_TightID": "LoosePFIso_TightID",  # tight ID, tight PF Iso
    "NUM_LooseRelTkIso_DEN_HighPtID": "LooseRelTkIso_HighPtID",  # highPtID, loose tkRelIso
    "NUM_LooseRelTkIso_DEN_TrkHighPtID": "LooseRelTkIso_TrkHighPtID",  # trkHighPtID, loose tkRelIso
    "NUM_LooseRelIso_DEN_MediumID": "LooseRelIso_MediumID",
    "NUM_TightPFIso_DEN_MediumID": "TightPFIso_MediumID",  # medium ID, tight PF Iso
    "NUM_TightPFIso_DEN_MediumPromptID": "TightPFIso_MediumPromptID",  # medium prompt ID, tight PF Iso
    "NUM_TightRelTkIso_DEN_HighPtID": "TightRelIso_HighPtID",  # highPtID, tight tkRelIso
    "NUM_TightRelTkIso_DEN_TrkHighPtID": "TightRelIso_TrkHighPtID",  # trkHighPtID, tight tkRelIso
    "NUM_TightPFIso_DEN_TightID": "TightPFIso_TightID",  # tight ID, tight PF Iso
    "NUM_LooseMiniIso_DEN_LooseID": "LooseMiniIso_LooseID",
    "NUM_LooseMiniIso_DEN_MediumID": "LooseMiniIso_MediumID",
    "NUM_MediumMiniIso_DEN_MediumID": "MediumMiniIso_MediumID",
    "NUM_TightMiniIso_DEN_MediumID": "TightMiniIso_MediumID",
    "NUM_TightRelIso_DEN_MediumPromptID": "MediumRelIso",  # medium ID, tight iso --> old, Run 2 only
    "NUM_TightRelIso_DEN_TightIDandIPCut": "TightRelIso",  # tight ID, tight iso --> old, Run 2 only
    "NUM_TightRelTkIso_DEN_TrkHighPtIDandIPCut": "HighPtIdRelTkIso",  # highPtID, tight tkRelIso --> old, Run 2 only
    # Trigger
    # "NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight": "TightIso24",  # trg --> FOR ALL PT RANGE!!
    # "NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium": "MediumIso24",  # trg for medium muons
    "NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight": "TightIso27",  # trg --> FOR ALL PT RANGE!!  --> old, Run 2 only
    "NUM_Mu50_or_OldMu100_or_TkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose": "Mu50",  # trg --> FOR ALL PT RANGE!! --> old, Run 2 only
    "NUM_Mu50_or_TkMu50_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose": "Mu50_tkMu50",  # trg --> FOR ALL PT RANGE!! --> old, Run 2 only
    "NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight": "TightIso24OrTightIsoTk24",  # trg --> FOR ALL PT RANGE!! --> old, Run 2 only
    "NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium": "IsoMu24_CutBasedIdMedium_and_PFIsoMedium",
    "NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight": "IsoMu24_CutBasedIdTight_and_PFIsoTight",
    "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose": "IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_CutBasedIdGlobalHighPt_and_TkIsoLoose",
    "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdMedium_and_PFIsoMedium": "IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_CutBasedIdMedium_and_PFIsoMedium",
    "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTight_and_PFIsoTight": "IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_CutBasedIdTight_and_PFIsoTight",
    "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose": "IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_CutBasedIdTrkHighPt_and_TkIsoLoose",
    "NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose": "Mu50_or_CascadeMu100_or_HighPtTkMu100_CutBasedIdGlobalHighPt_and_TkIsoLoose",
    "NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose": "Mu50_or_CascadeMu100_or_HighPtTkMu100_CutBasedIdTrkHighPt_and_TkIsoLoose",
}

MediumMuReco_SF_sources = {
    "2016preVFP_UL": ["NUM_TrackerMuons_DEN_genTracks"],
    "2016postVFP_UL": ["NUM_TrackerMuons_DEN_genTracks"],
    "2017_UL": ["NUM_TrackerMuons_DEN_genTracks"],
    "2018_UL": ["NUM_TrackerMuons_DEN_genTracks"],
    "2022_Summer22": [],  # 2022 has no genTrack to TrackerMuons key
    "2022_Summer22EE": [],
    "2023_Summer23": [],
    "2023_Summer23BPix": [],
    "2024_Winter24": [],
    "2024_Summer24": [],
    "2025_Summer24": [],
    "2025_Winter25": [],
}
MediumMuIDIso_SF_Sources = {
    "2016preVFP_UL": [
        "NUM_TightID_DEN_TrackerMuons",
        "NUM_TightRelIso_DEN_TightIDandIPCut",
    ],
    "2016postVFP_UL": [
        "NUM_TightID_DEN_TrackerMuons",
        "NUM_TightRelIso_DEN_TightIDandIPCut",
    ],
    "2017_UL": [
        "NUM_TightID_DEN_TrackerMuons",
        "NUM_TightRelIso_DEN_TightIDandIPCut",
    ],
    "2018_UL": [
        "NUM_TightID_DEN_TrackerMuons",
        "NUM_TightRelIso_DEN_TightIDandIPCut",
    ],
    "2022_Summer22": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2022_Summer22EE": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2023_Summer23": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2023_Summer23BPix": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2024_Summer24": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2024_Winter24": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2025_Summer24": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
    "2025_Winter25": [
        "NUM_LooseID_DEN_TrackerMuons",
        # "NUM_MediumID_DEN_genTracks",
        # "NUM_MediumPromptID_DEN_TrackerMuons",
        "NUM_MediumID_DEN_TrackerMuons",
        "NUM_TightID_DEN_TrackerMuons",
        # "NUM_SoftID_DEN_TrackerMuons",
        # "NUM_HighPtID_DEN_TrackerMuons",
        # "NUM_TrkHighPtID_DEN_TrackerMuons",
        "NUM_LoosePFIso_DEN_LooseID",
        "NUM_LoosePFIso_DEN_MediumID",
        # "NUM_LoosePFIso_DEN_MediumPromptID",
        "NUM_LoosePFIso_DEN_TightID",
        # "NUM_LooseRelTkIso_DEN_HighPtID",
        # "NUM_LooseRelTkIso_DEN_TrkHighPtID",
        # "NUM_LooseRelIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumID",
        # "NUM_TightPFIso_DEN_MediumPromptID",
        # "NUM_TightRelTkIso_DEN_HighPtID",
        # "NUM_TightRelTkIso_DEN_TrkHighPtID",
        "NUM_TightPFIso_DEN_TightID",
        "NUM_LooseMiniIso_DEN_LooseID",
        "NUM_LooseMiniIso_DEN_MediumID",
        # "NUM_MediumMiniIso_DEN_MediumID",
        # "NUM_TightMiniIso_DEN_MediumID",
    ],
}

def apply_muIDIso_weights(df,config,return_variations=True):
    era = config.get("era")
    period_unc = period_names[era]
    period = period_names[era]
    jsonFile_eff = os.path.join(
        os.environ["ANALYSIS_PATH"],
        MuCorrProducer.muIDEff_JsonPath.format(pog_folder_names["MUO"][period_unc]),
    )
    headers_dir = os.path.dirname(os.path.abspath(__file__))
    header_path = os.path.join(headers_dir, "mu.h")
    ROOT.gInterpreter.Declare(f'#include "{header_path}"')
    ROOT.gInterpreter.ProcessLine(
        f'::correction::MuCorrProvider::Initialize("{jsonFile_eff}", "{era}")'
    )
    sf_sources = (
        MuCorrProducer.MediumMuIDIso_SF_Sources[MuCorrProducer.period]
        + MuCorrProducer.MediumMuReco_SF_sources[MuCorrProducer.period]
    )
    sf_scales = ["Central", "Up", "Down"] if return_variations else [central]
    for source in sf_sources:
        for scale in sf_scales:
            source_name = MuCorrProducer.MediumMu_SF_Sources_dict[source]
            syst_name = source_name + scale

                branch_name = f"weight_MuonID_SF_{syst_name}"
                gen_kind = f"{leg_name}_{self.columns['gen_kind']}"
                legType = f'{leg_name}_{self.columns["legType"]}'
                p4 = f'{leg_name}_{self.columns["p4"]}'
                # print(f"p4 is {p4}. Computing medium SF: 30 < pT < 200 GeV")
                pfRelIso04_all = f'{leg_name}_{self.columns["pfRelIso04_all"]}'
                tightId = f'{leg_name}_{self.columns["tightId"]}'
                tkRelIso = f'{leg_name}_{self.columns["tkRelIso"]}'
                highPtId = f'{leg_name}_{self.columns["highPtId"]}'
                mediumId = f'{leg_name}_{self.columns["mediumId"]}'
                looseId = f'{leg_name}_{self.columns["looseId"]}'

                genMatch_bool = f"{gen_kind} == 2 || {gen_kind} == 4"
                legType = getLegTypeString(df, legType)

                df = df.Define(
                    f"{branch_name}_double",
                    f"""{legType} == Leg::mu && ({genMatch_bool})
                        ? ::correction::MuCorrProvider::getGlobal().getMuonSF(
                            {p4}, {pfRelIso04_all}, {tightId}, {tkRelIso}, {highPtId}, {mediumId},{looseId},
                            ::correction::MuCorrProvider::UncSource::{source},
                            ::correction::UncScale::{scale})
                        : 1.""",
                )

                # Change to this format
                # df = df.Define(pair_name, vector<val1,val2>)
                # df = df.Define(SF_value, pair_name[0]) #Add these to the branch list
                # df = df.Define(SF_validitiy, pair_name[1]) #Add these to the branch list -- Maybe -1 underflow, 0 within, +1 overflow, -2 notGenMuon

                # print(f"{branch_name}_double")
                # if scale==central:
                #    df.Filter(f"{branch_name}_double!=1.").Display({f"{branch_name}_double"}).Print()
                if scale != central:
                    branch_name_final = branch_name + "_rel"
                    df = df.Define(
                        branch_name_final,
                        f"static_cast<float>({branch_name}_double/{branch_central})",
                    )
                else:
                    if source == central:
                        branch_name_final = (
                            f"""weight_{leg_name}_MuonID_SF_{central}"""
                        )
                    else:
                        branch_name_final = branch_name
                    df = df.Define(
                        branch_name_final,
                        f"static_cast<float>({branch_name}_double)",
                    )
                SF_branches.append(branch_name_final)
    return df, SF_branches

########################################################################################################
# saving high and low pT SFs for development
def getHighPtMuonIDSF(self, df, lepton_legs, isCentral, return_variations):
    highPtMuSF_branches = []
    sf_sources = (
        MuCorrProducer.highPtmuReco_SF_sources
        + MuCorrProducer.highPtmuID_SF_Sources
        + MuCorrProducer.highPtmuIso_SF_Sources
    )
    sf_scales = [up, down] if return_variations else []
    for source in sf_sources:
        for scale in [central] + sf_scales:
            if source == central and scale != central:
                continue
            if not isCentral and scale != central:
                continue
            source_name = (
                MuCorrProducer.highPtMu_SF_Sources_dict[source]
                if source != central
                else central
            )
            syst_name = source_name + scale if source != central else "Central"
            for leg_idx, leg_name in enumerate(lepton_legs):
                branch_name = f"weight_{leg_name}_HighPt_MuonID_SF_{syst_name}"
                branch_central = (
                    f"""weight_{leg_name}_HighPt_MuonID_SF_{source_name+central}"""
                )

                gen_kind = f"{leg_name}_{self.columns['gen_kind']}"
                legType = f'{leg_name}_{self.columns["legType"]}'
                p4 = f'{leg_name}_{self.columns["p4"]}'
                # print(f"p4 is {p4}. Computing High Pt SF: pT > 200 GeV")
                pfRelIso04_all = f'{leg_name}_{self.columns["pfRelIso04_all"]}'
                tightId = f'{leg_name}_{self.columns["tightId"]}'
                tkRelIso = f'{leg_name}_{self.columns["tkRelIso"]}'
                highPtId = f'{leg_name}_{self.columns["highPtId"]}'
                mediumId = f'{leg_name}_{self.columns["mediumId"]}'

                genMatch_bool = f"{gen_kind} == 2 || {gen_kind} == 4"
                legType = getLegTypeString(df, legType)

                df = df.Define(
                    f"{branch_name}_double",
                    f"""{legType} == Leg::mu && ({genMatch_bool})
                        ? ::correction::HighPtMuCorrProvider::getGlobal().getHighPtMuonSF(
                            {p4}, {pfRelIso04_all}, {tightId}, {highPtId}, {tkRelIso}, {mediumId},
                            ::correction::HighPtMuCorrProvider::UncSource::{source},
                            ::correction::UncScale::{scale})
                        : 1.""",
                )

                if scale != central:
                    branch_name_final = branch_name + "_rel"
                    df = df.Define(
                        branch_name_final,
                        f"static_cast<float>({branch_name}_double/{branch_central})",
                    )
                else:
                    if source == central:
                        branch_name_final = (
                            f"""weight_{leg_name}_HighPt_MuonID_SF_{central}"""
                        )
                    else:
                        branch_name_final = branch_name
                    df = df.Define(
                        branch_name_final,
                        f"static_cast<float>({branch_name}_double)",
                    )
                highPtMuSF_branches.append(branch_name_final)
    return df, highPtMuSF_branches

########################################################################################################
def getLowPtMuonIDSF(self, df, lepton_legs, isCentral, return_variations):
    lowPtMuSF_branches = []
    sf_sources = (
        MuCorrProducer.lowPtmuReco_SF_sources
        + MuCorrProducer.lowPtmuID_SF_Sources
        + MuCorrProducer.lowPtmuIso_SF_Sources
    )
    sf_scales = [up, down] if return_variations else []
    for source in sf_sources:
        for scale in [central] + sf_scales:
            if source == central and scale != central:
                continue
            if not isCentral and scale != central:
                continue
            source_name = (
                MuCorrProducer.lowPtMu_SF_Sources_dict[source]
                if source != central
                else central
            )
            syst_name = source_name + scale if source != central else "Central"
            for leg_idx, leg_name in enumerate(lepton_legs):
                branch_name = f"weight_{leg_name}_LowPt_MuonID_SF_{syst_name}"
                branch_central = (
                    f"""weight_{leg_name}_LowPt_MuonID_SF_{source_name+central}"""
                )

                gen_kind = f"{leg_name}_{self.columns['gen_kind']}"
                legType = f'{leg_name}_{self.columns["legType"]}'
                p4 = f'{leg_name}_{self.columns["p4"]}'
                # print(f"p4 is {p4}. Computing low pT SF:  pT < 30 GeV")
                pfRelIso04_all = f'{leg_name}_{self.columns["pfRelIso04_all"]}'
                tightId = f'{leg_name}_{self.columns["tightId"]}'
                tkRelIso = f'{leg_name}_{self.columns["tkRelIso"]}'
                highPtId = f'{leg_name}_{self.columns["highPtId"]}'
                mediumId = f'{leg_name}_{self.columns["mediumId"]}'

                genMatch_bool = f"{gen_kind} == 2 || {gen_kind} == 4"
                legType = getLegTypeString(df, legType)

                df = df.Define(
                    f"{branch_name}_double",
                    f"""{legType} == Leg::mu && ({genMatch_bool})
                        ? ::correction::LowPtMuCorrProvider::getGlobal().getLowPtMuonSF(
                            {p4}, {pfRelIso04_all}, {tightId}, {tkRelIso}, {highPtId}, {mediumId},
                            ::correction::LowPtMuCorrProvider::UncSource::{source},
                            ::correction::UncScale::{scale})
                        : 1.""",
                )

                if scale != central:
                    branch_name_final = branch_name + "_rel"
                    df = df.Define(
                        branch_name_final,
                        f"static_cast<float>({branch_name}_double/{branch_central})",
                    )
                else:
                    if source == central:
                        branch_name_final = (
                            f"""weight_{leg_name}_LowPt_MuonID_SF_{central}"""
                        )
                    else:
                        branch_name_final = branch_name
                    df = df.Define(
                        branch_name_final,
                        f"static_cast<float>({branch_name}_double)",
                    )
                lowPtMuSF_branches.append(branch_name_final)
    return df, lowPtMuSF_branches
