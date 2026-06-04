import math
import ROOT

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])


ROOT.gInterpreter.Declare("""
    float getCorrectSingleLepWeight(const float& lep1_pt, const float& lep1_eta, const bool& lep1_matching, const float& lep1_weight,const float& lep2_pt, const float& lep2_eta, const bool& lep2_matching, const float& lep2_weight){
        if(lep1_pt > lep2_pt){
            return lep1_matching? lep1_weight : 1.f;
        }
        else if(lep1_pt == lep2_pt){
            if(abs(lep1_eta) < abs(lep2_eta)){
                return lep1_matching? lep1_weight : 1.f;
            }
            else if(abs(lep1_eta) > abs(lep2_eta)){
                return lep2_matching? lep2_weight : 1.f;
            }
        }
        else{
            return lep2_matching? lep2_weight : 1.f;
        }
    throw std::invalid_argument("ERROR: no suitable single lepton candidate");

    }
    """)


def defineTriggerWeights(df, pt_to_use="pt"):  # needs application region def
    # print(f"using pt = {pt_to_use} for trigger SFs")
    if f"weight_TrgSF_singleMu_IsoMu24Central" in df.GetColumnNames():
        print(
            "Warning, weight_TrgSF_singleMu_IsoMu24Central already in col names, passing"
        )
    else:
        df = df.Define(
            f"weight_TrgSF_singleMu_IsoMu24Central",
            f"if (Event_HasTriggerMatching_singleMu) {{return getCorrectSingleLepWeight(mu1_{pt_to_use}, mu1_eta, mu1_HasTriggerMatching_singleMu, weight_mu1_IsoMu24_CutBasedIdMedium_and_PFIsoMedium_Central,mu2_{pt_to_use}, mu2_eta, mu2_HasTriggerMatching_singleMu, weight_mu2_IsoMu24_CutBasedIdMedium_and_PFIsoMedium_Central) ;}}return 1.f;",
        )
    return df


def defineTriggerWeightsErrors(df, pt_to_use="pt"):
    for scale in ["up", "down"]:
        # weight_mu2_TrgSF_singleMu_IsoMu24
        trg_name = "singleMu_IsoMu24"  # "singleMu_IsoMu24"
        df = df.Define(
            f"weight_TrgSF_{trg_name}{scale}",
            f"""if (Event_HasTriggerMatching_singleMu) {{return getCorrectSingleLepWeight(mu1_{pt_to_use}, mu1_eta, mu1_HasTriggerMatching_singleMu, weight_mu1_IsoMu24_CutBasedIdMedium_and_PFIsoMedium_{scale},mu2_{pt_to_use}, mu2_eta, mu2_HasTriggerMatching_singleMu, weight_mu2_IsoMu24_CutBasedIdMedium_and_PFIsoMedium_{scale}) ;}} return 1.f;""",
        )
    return df


def AddTriggerWeightsAndErrors(df, WantErrors):
    df = defineTriggerWeights(df)
    if WantErrors:
        df = defineTriggerWeightsErrors(df)
    return df