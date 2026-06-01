import ROOT
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from .utilities import *


def _column_names(df): return {str(col) for col in df.GetColumnNames()}


def _define_if_missing(df, name, expression):
    if name in _column_names(df): return df
    return df.Define(name, expression)


def _declare_muon_helpers():
    ROOT.gInterpreter.Declare(
        """
        #ifndef NEW_SKIM_MUON_ANALYSIS_HELPERS
        #define NEW_SKIM_MUON_ANALYSIS_HELPERS
        using RVecF = ROOT::VecOps::RVec<float>;

        RVecF Muon_pt_err_sel(const RVecF& Muon_nano_pt_err, const RVecF& Muon_bsc_pt_err, const RVecF& Muon_bsc_chi2) {
            RVecF out(Muon_nano_pt_err.size());
            for (size_t i = 0; i < out.size(); ++i) {
                out[i] = (Muon_bsc_chi2[i] < 30) ? Muon_bsc_pt_err[i] : Muon_nano_pt_err[i];
            }
            return out;
        }

        RVecF Muon_pt_sel(const RVecF& Muon_nano_pt, const RVecF& Muon_bsc_pt, const RVecF& Muon_bsc_chi2) {
            RVecF out(Muon_nano_pt.size());
            for (size_t i = 0; i < out.size(); ++i) {
                out[i] = (Muon_bsc_chi2[i] < 30) ? Muon_bsc_pt[i] : Muon_nano_pt[i];
            }
            return out;
        }
        #endif
        """
    )

def GetPtConfigurations(only_default, want_variations):
    configs = {
        "Muon_pt_noCorr": ["Muon_pt", "Muon_bsConstrainedPt"],
        "Muon_pt_corr": ["Muon_pt_nano_corr", "Muon_pt_bsc_corr"],
        "Muon_pt_corr_FSR": ["Muon_pt_nano_corr_FSR", "Muon_pt_bsc_corr_FSR"],
        "Muon_pt_FSR_scale": ["Muon_pt_nano_scale_FSR", "Muon_pt_bsc_scale_FSR"],
        "Muon_pt_scale": ["Muon_pt_nano_scale", "Muon_pt_bsc_scale"],
    }
    if not only_default:
        configs.update({
            "Muon_pt_noCorr_FSR": ["Muon_pt_nano_FSR", "Muon_bsConstrainedPt"],
        })
    if want_variations:
        configs.update({
            "Muon_pt_FSR_scale_up": ["Muon_pt_nano_FSR_scale_up", "Muon_pt_bsc_FSR_scale_up"],
            "Muon_pt_FSR_scale_down": ["Muon_pt_nano_FSR_scale_down", "Muon_pt_bsc_FSR_scale_down"],
            "Muon_pt_FSR_res_up": ["Muon_pt_nano_FSR_res_up", "Muon_pt_bsc_FSR_res_up"],
            "Muon_pt_FSR_res_down": ["Muon_pt_nano_FSR_res_down", "Muon_pt_bsc_FSR_res_down"],
        })
    err_configs = {
        "Muon_pt_err": ["Muon_ptErr", "Muon_bsConstrainedPtErr"],
    }
    return configs,err_configs

def DefineMuonPtAndP4(df, only_default=True, want_variations=False):
    _declare_muon_helpers()
    configs,err_configs = GetPtConfigurations(only_default, want_variations)
    cols = _column_names(df)
    for name_pt, (nano, bsc) in configs.items():
        df = _define_if_missing(df,name_pt,f"Muon_pt_sel({nano}, {bsc}, Muon_bsConstrainedChi2)")
        df = _define_if_missing(df,name_pt.replace("pt", "p4"),f"GetP4({name_pt}, Muon_eta, Muon_phi, Muon_mass)")
    for name_err, (nano_err, bsc_err) in err_configs.items():
         df = _define_if_missing(df,name_err,f"Muon_pt_err_sel({nano_err}, {bsc_err}, Muon_bsConstrainedChi2)")
    return df

def ApplyMuonTriggerMatching(df, trigger_config, apply_filter=True):
    cols = _column_names(df)
    if "TrigObj_pt" in cols:
        df = _define_if_missing(df, "TrigObj_idx", "CreateIndexes(TrigObj_pt.size())")
        df = _define_if_missing(df, "TrigObj_mass", "RVecF(TrigObj_pt.size(), 0.f)")
        df = _define_if_missing(df, "TrigObj_p4","GetP4(TrigObj_pt, TrigObj_eta, TrigObj_phi, TrigObj_mass, TrigObj_idx)")
    filters = []
    for path, config in trigger_config.items():
        path_name = config["path"][0]
        leg = config["legs"][0]
        offline = leg["offline_obj"]["cut"].format(obj="Muon", pt="pt_corr_FSR")
        online = leg["online_obj"]["cut"]
        df = _define_if_missing(df, f"Muon_passOfflineCut_{path}", offline)
        df = _define_if_missing(df, f"TrigObj_passOnlineCut_{path}", online)
        df = _define_if_missing(df,f"Muon_TriggerMatchingIdx_{path}",f"FindMatching(Muon_passOfflineCut_{path}, TrigObj_passOnlineCut_{path}, Muon_p4_corr_FSR, TrigObj_p4, 0.4)")
        evt = f"Event_HasTriggerMatching_{path}"
        df = df.Define(evt, f"{path_name} && Any(Muon_TriggerMatchingIdx_{path} > -1)")
        filters.append(evt)
    if apply_filter:
        df = df.Filter(" || ".join(filters), "Trigger matching for " + "__".join(trigger_config.keys()))
    return df, filters

def ProcessMuonVariables(df,muon_columns,default_suffix,trigger_config,only_default=True,want_variations=False,pt_min=15.0,lower_mass_cut=50.0,upper_mass_cut=200.0,syst_cfg=None,):
    cols = _column_names(df)
    selection_pt = [f"Muon_pt_{default_suffix}"]
    syst_suffixes = [""]
    if want_variations:
        scales = syst_cfg.get('scales',['up','down'])
        syst_suffixes.extend([syst_cfg['systematics']['MuonScale']['muon_suffix'].format(scale=scale) for scale in scales])
        syst_suffixes.extend([syst_cfg['systematics']['MuonRes']['muon_suffix'].format(scale=scale) for scale in scales])
        selection_pt += ["Muon_pt{syst}" for syst in syst_suffixes]
    new_cols = []

    def track(df, name, expr):
        if name in _column_names(df): return df
        if "p4" not in name: new_cols.append(name)
        return df.Define(name, expr)

    event_filters = []
    mass_filters = []

    for suff in syst_suffixes:
        is_nominal = (suff == "")
        pt=f"Muon_pt{suff}"
        if is_nominal: pt = "Muon_pt_"+default_suffix
        df = df.Define(f"good_muons{suff}",f"{pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_mediumId && Muon_pfIsoId >= 2")
        df = df.Define(f"good_idx{suff}",f"ROOT::VecOps::Nonzero(good_muons{suff})")
        df = df.Define(f"sorted_idx{suff}",f"Reverse(Take(good_idx{suff}, Argsort(Take({pt}, good_idx{suff}))))")
        df = track(df, f"mu1_idx{suff}", f"sorted_idx{suff}.size()>0 ? (int)sorted_idx{suff}[0] : -1")
        df = track(df, f"mu2_idx{suff}", f"sorted_idx{suff}.size()>1 ? (int)sorted_idx{suff}[1] : -1")
        event_filters.append(f"sorted_idx{suff}.size() == 2")
        for i in [1, 2]:
            idx = f"mu{i}_idx{suff}"
            df = track(df, f"mu{i}_pt{suff}", f"{idx}>=0 ? {pt}[{idx}] : -999.f")
            df = track(df,f"mu{i}_p4{suff}",f"{idx}>=0 ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({pt}[{idx}], Muon_eta[{idx}], Muon_phi[{idx}], Muon_mass[{idx}]) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0,0,0,0)")
            for muon_col in muon_columns+['Muon_pt_corr','Muon_pt_err', 'Muon_pt_scale', 'Muon_pt_FSR_scale']:
                suffix_clean = "_".join(c for c in muon_col.split("_")[1:])
                df = track(df, f"mu{i}_{suffix_clean}{suff}", f"{idx}>=0 ? {muon_col}[{idx}] : -999.f")
            for path in trigger_config.keys():
                df = track(df, f"mu{i}_HasTriggerMatching_{path}{suff}", f"{idx} >= 0 ? (Muon_TriggerMatchingIdx_{path}[{idx}] >= 0) : false")

        p4 = f"(mu1_p4{suff} + mu2_p4{suff})"
        df = track(df, f"m_mumu{suff}", f"{p4}.M()")
        mass_filters.append(f"m_mumu{suff} > {lower_mass_cut} && m_mumu{suff} < {upper_mass_cut}")

    df = df.Filter(" && ".join(event_filters), "Exactly 2 muons")
    df = df.Filter(" && ".join(mass_filters), "dimuon mass cut")

    onlyCentral_branches = ["Muon_pt_noCorr"]
    idx1 = "mu1_idx"
    idx2 = "mu2_idx"
    for centr_br in onlyCentral_branches:
        suffix_br = "_".join(c for c in centr_br.split("_")[1:])
        df = track(df, f"mu1_{suffix_br}", f"{idx1}>=0 ? {centr_br}[{idx1}] : -999.f")
        df = track(df, f"mu2_{suffix_br}", f"{idx2}>=0 ? {centr_br}[{idx2}] : -999.f")
    return df, new_cols


def ProcessExtraMuonVariables(df,muon_columns,default_suffix,trigger_config,only_default=True,want_variations=False,pt_min=15.0):

    cols = _column_names(df)
    new_cols = []
    pt_list = [f"Muon_pt_{default_suffix}"]
    def track(df, name, expr):
        if name in _column_names(df): return df
        new_cols.append(name)
        return df.Define(name, expr)
    for pt in pt_list:
        if pt not in cols:
            print(f"pt column {pt} not found, skipping extra muon variables")
            continue
        df = _define_if_missing(df, "Muon_idx", f"CreateIndexes({pt}.size())")
        df = df.Define( "extra_good_muons", f"{pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_looseId && Muon_pfIsoId >= 2 && " f"Muon_idx != mu1_idx && " f"Muon_idx != mu2_idx")
        df = df.Define("extra_good_idx", "ROOT::VecOps::Nonzero(extra_good_muons)")
        df = df.Define("extra_sorted_idx", f"Reverse(Take(extra_good_idx, Argsort(Take({pt}, extra_good_idx))))")
        df = track(df, "extraMuon_idx", "extra_sorted_idx")
        df = track(df, "n_extraMuon", "int(extraMuon_idx.size())")
        df = track(df, "extraMuon_pt", f"Take({pt}, extraMuon_idx)")
        df = track(df, "extraMuon_eta", "Take(Muon_eta, extraMuon_idx)")
        df = track(df, "extraMuon_phi", "Take(Muon_phi, extraMuon_idx)")
        df = track(df, "extraMuon_charge", "Take(Muon_charge, extraMuon_idx)")
        for col in muon_columns + ['Muon_pt_corr','Muon_pt_err']:
            suffix_clean = "_".join(c for c in col.split("_")[1:])
            if f"extraMuon_{suffix_clean}" not in _column_names(df):
                df = track(df, f"extraMuon_{suffix_clean}", f"Take({col}, extraMuon_idx)")
    return df, new_cols

def ApplyElectronVeto(df):
    df = df.Define("Electron_p4", "GetP4(Electron_pt, Electron_eta, Electron_phi, Electron_mass)")
    df = _define_if_missing(df, "veto_electrons","Electron_pt > 20 && abs(Electron_eta) < 2.5 && Electron_mvaIso_WP90")
    return df.Filter("ROOT::VecOps::Nonzero(veto_electrons).size() == 0", "No extra electrons")

def DefineMuonSelection(df,sel_config,only_default,want_variations=False,syst_cfg=None):
    sel_dict = sel_config.get("muons_selection", {})
    vars_to_store = []
    syst_suffixes = [""]
    if want_variations:
        scales = syst_cfg.get('scales',['up','down'])
        syst_suffixes.extend([syst_cfg['systematics']['MuonScale']['muon_suffix'].format(scale=scale) for scale in scales])
        syst_suffixes.extend([syst_cfg['systematics']['MuonRes']['muon_suffix'].format(scale=scale) for scale in scales])
    for suff in syst_suffixes:
        for sel_name, sel_subdict in sel_dict.items():
            sel_str = sel_subdict["expression"]
            full_name = f"{sel_name}{suff}"
            df = df.Define(full_name,sel_str.format(mu_suff=suff))
            if sel_subdict.get("store", False):
                vars_to_store.append(full_name)
    return df, vars_to_store

