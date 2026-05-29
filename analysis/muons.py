import ROOT
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from .utilities import *

def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}

def _define_if_missing(df, name, expression):
    if name in _column_names(df):
        return df
    return df.Define(name, expression)

def _declare_muon_helpers():
    ROOT.gInterpreter.Declare(
        """
        #ifndef NEW_SKIM_MUON_ANALYSIS_HELPERS
        #define NEW_SKIM_MUON_ANALYSIS_HELPERS
        using RVecF = ROOT::VecOps::RVec<float>;

        RVecF Muon_pt_sel(const RVecF& Muon_nano_pt, const RVecF& Muon_bsc_pt, const RVecF& Muon_bsc_chi2) {
            RVecF Muon_pt_sel(Muon_nano_pt.size());
            for (size_t i = 0; i < Muon_pt_sel.size(); ++i) {
                Muon_pt_sel[i] = (Muon_bsc_chi2[i] < 30) ? Muon_bsc_pt[i] : Muon_nano_pt[i];
            }
            return Muon_pt_sel;
        }
        #endif
        """
    )

# =============================================================================
# 1. PT & P4 VARIATION CONFIGURATIONS
# =============================================================================
def GetPtConfigurations(is_data, only_default, want_variations):
    """Returns the explicit mapping of (OutputColumn, NanoBranch, BscBranch)"""
    configs = [
        ("Muon_pt_noCorr",     "Muon_pt",                "Muon_bsConstrainedPt"),
        ("Muon_pt_ScaRe",      "Muon_pt_corr",           "Muon_bsc_pt_corr"),
        ("Muon_pt_ScaRe_FSR",  "Muon_pt_nano_scare_FSR", "Muon_bsc_pt_nano_scare_FSR")
    ]
    if not only_default:
        configs.extend([
            ("Muon_pt_scale",      "Muon_pt_scale_corr",          "Muon_bsc_pt_scale_corr"),
            ("Muon_pt_noCorr_FSR", "Muon_pt_nano_FSR",            "Muon_pt_bsc_FSR"),
            ("Muon_pt_scale_FSR",  "Muon_pt_nano_scale_corr_FSR", "Muon_bsc_pt_nano_scale_corr_FSR")
        ])
    if not is_data and want_variations:
        configs.extend([
            ("Muon_pt_scale_FSR_up",   "Muon_pt_nano_scale_corr_FSR_up",   "Muon_bsc_pt_nano_scale_corr_FSR_up"),
            ("Muon_pt_scale_FSR_down", "Muon_pt_nano_scale_corr_FSR_down", "Muon_bsc_pt_nano_scale_corr_FSR_down"),
            ("Muon_pt_resol_FSR_up",   "Muon_pt_nano_corr_resol_FSR_up",   "Muon_bsc_pt_nano_corr_resol_FSR_up"),
            ("Muon_pt_resol_FSR_down", "Muon_pt_nano_corr_resol_FSR_down", "Muon_bsc_pt_nano_corr_resol_FSR_down")
        ])
        if not only_default:
            configs.extend([
                ("Muon_pt_scale_up",   "Muon_pt_scale_corr_up",   "Muon_bsc_pt_scale_corr_up"),
                ("Muon_pt_scale_down", "Muon_pt_scale_corr_down", "Muon_bsc_pt_scale_corr_down"),
                ("Muon_pt_resol_up",   "Muon_pt_corr_resol_up",   "Muon_bsc_pt_corr_resol_up"),
                ("Muon_pt_resol_down", "Muon_pt_corr_resol_down", "Muon_bsc_pt_corr_resol_down")
            ])
    return configs


def DefineMuonPtAndP4(df, is_data, only_default=True, want_variations=False):
    """Sets up primary pT vectors and Lorentz Vectors inside the RDataFrame"""
    _declare_muon_helpers()
    pt_configurations = GetPtConfigurations(is_data, only_default, want_variations)
    available_cols = _column_names(df)

    for name_pt, branch_nano, branch_bsc in pt_configurations:
        if branch_nano not in available_cols or branch_bsc not in available_cols:
            continue
        df = _define_if_missing(df, name_pt, f"Muon_pt_sel({branch_nano}, {branch_bsc}, Muon_bsConstrainedChi2)")
        df = _define_if_missing(df, name_pt.replace("pt", "p4"), f"GetP4({name_pt}, Muon_eta, Muon_phi, Muon_mass)")
    return df


# =============================================================================
# 2. GLOBAL TRIGGER EVENT FILTER
# =============================================================================
def ApplyMuonTriggerMatching(df, trigger_config, apply_filter=True):
    """Applies strict event filtering based on Trigger Object matching"""
    matching_bool_vars = []
    available_cols = _column_names(df)

    if "TrigObj_pt" in available_cols:
        df = _define_if_missing(df, "TrigObj_idx", "CreateIndexes(TrigObj_pt.size())")
        if "TrigObj_mass" not in available_cols:
            df = _define_if_missing(df, "TrigObj_mass", "RVecF(TrigObj_pt.size(), 0.f)")
        df = _define_if_missing(df, "TrigObj_p4", "GetP4(TrigObj_pt, TrigObj_eta, TrigObj_phi, TrigObj_mass, TrigObj_idx)")

    for path, config in trigger_config.items():
        path_name = config["path"][0]
        matching_bool_vars.append(path_name)
        leg_config = config["legs"][0]

        offline_cut_expr = leg_config["offline_obj"]["cut"].format(obj="Muon", pt="pt_ScaRe_FSR")
        online_cut_expr = leg_config["online_obj"]["cut"]
        df = _define_if_missing(df, f"Muon_passOfflineCut_{path}", offline_cut_expr)
        df = _define_if_missing(df, f"TrigObj_passOnlineCut_{path}", online_cut_expr)
        df = _define_if_missing(df, f"Muon_TriggerMatchingIdx_{path}",
                                f"FindMatching(Muon_passOfflineCut_{path}, TrigObj_passOnlineCut_{path}, Muon_p4_ScaRe_FSR, TrigObj_p4, 0.4)")
        matching_branch_bool = f"Event_HasTriggerMatching_{path}"
        df = df.Define(matching_branch_bool, f"{path_name} && Any(Muon_TriggerMatchingIdx_{path} > -1)")
        matching_bool_vars.append(matching_branch_bool)

    if apply_filter and matching_bool_vars:
        df = df.Filter(" || ".join(matching_bool_vars), "Trigger application filter")
    return df, matching_bool_vars


# =============================================================================
# 3. CORE PROCESSING & KINEMATIC FILTERS
# =============================================================================
def ProcessMuonVariables(df, is_data, muon_columns, default_suffix, trigger_config, only_default=True, want_variations=False, pt_min=15.0, mass_cut=50.0):
    """Processes signal dimuons using main/shifted configurations. noCorr and ScaRe are computed passively."""
    new_muon_cols = []
    available_cols = _column_names(df)

    # 3a. Active configurations guiding the event filters (Excluding noCorr & ScaRe)
    nominal_pt_branch = f"Muon_pt{default_suffix}"
    filtering_pt_configs = [nominal_pt_branch]
    if not only_default:
        filtering_pt_configs.extend(["Muon_pt_scale", "Muon_pt_scale_FSR"])
    if not is_data and want_variations:
        filtering_pt_configs.extend([
            "Muon_pt_scale_FSR_up", "Muon_pt_scale_FSR_down",
            "Muon_pt_resol_FSR_up", "Muon_pt_resol_FSR_down"
        ])
        if not only_default:
            filtering_pt_configs.extend([
                "Muon_pt_scale_up", "Muon_pt_scale_down",
                "Muon_pt_resol_up", "Muon_pt_resol_down"
            ])

    # 3b. Map additional scalar branches
    muon_scalar_branches = {}
    for col in muon_columns:
        if "pt" in col.lower(): continue
        suffix_clean = "_".join(col.split("_")[1:])
        muon_scalar_branches[suffix_clean] = col

    def define_and_track(dataframe, name, expr):
        if name in _column_names(dataframe): return dataframe
        if "p4" not in name: new_muon_cols.append(name)
        return dataframe.Define(name, expr)

    event_filters = []
    mass_filters = []

    # 3c. Main loop over active filtering configurations
    for name_pt in filtering_pt_configs:
        if name_pt not in available_cols: continue

        is_nominal = (name_pt == nominal_pt_branch)
        suff = "" if is_nominal else "_" + name_pt.replace("Muon_pt_", "")

        # Object selection
        df = df.Define(f"good_muons{suff}", f"{name_pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_mediumId && Muon_pfIsoId >= 2")
        df = df.Define(f"good_idx{suff}", f"ROOT::VecOps::Nonzero(good_muons{suff})")
        df = df.Define(f"sorted_idx{suff}", f"Reverse(Take(good_idx{suff}, Argsort(Take({name_pt}, good_idx{suff}))))")

        # Pick leading & subleading
        df = define_and_track(df, f"mu1_idx{suff}", f"sorted_idx{suff}.size() > 0 ? (int)sorted_idx{suff}[0] : -1")
        df = define_and_track(df, f"mu2_idx{suff}", f"sorted_idx{suff}.size() > 1 ? (int)sorted_idx{suff}[1] : -1")

        # CRITICO: Enforce exactly 2 muons for the default configuration, but allow >= 2 for systematic loops
        if is_nominal:
            event_filters.append(f"sorted_idx{suff}.size() == 2")
        else:
            event_filters.append(f"sorted_idx{suff}.size() == 2")

        # Save specific single muon variables
        for num in [1, 2]:
            idx = f"mu{num}_idx{suff}"
            df = define_and_track(df, f"mu{num}_pt{suff}", f"{idx} >= 0 ? {name_pt}[{idx}] : -999.f")

            for branch_suff, original_branch in muon_scalar_branches.items():
                df = define_and_track(df, f"mu{num}_{branch_suff}{suff}", f"{idx} >= 0 ? {original_branch}[{idx}] : -999.f")

            df = define_and_track(df, f"mu{num}_p4{suff}",
                                  f"{idx} >= 0 ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({name_pt}[{idx}], Muon_eta[{idx}], Muon_phi[{idx}], Muon_mass[{idx}]) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0,0,0,0)")

            for path in trigger_config.keys():

                df = define_and_track(df, f"mu{num}_HasTriggerMatching_{path}{suff}", f"{idx} >= 0 ? (Muon_TriggerMatchingIdx_{path}[{idx}] >= 0) : false")

        # Compute pair metrics
        p4_mumu = f"(mu1_p4{suff} + mu2_p4{suff})"
        df = define_and_track(df, f"m_mumu{suff}", f"{p4_mumu}.M()")
        df = define_and_track(df, f"pt_mumu{suff}", f"{p4_mumu}.Pt()")
        df = define_and_track(df, f"eta_mumu{suff}", f"{p4_mumu}.Eta()")
        df = define_and_track(df, f"phi_mumu{suff}", f"{p4_mumu}.Phi()")
        df = define_and_track(df, f"dR_mumu{suff}", f"ROOT::Math::VectorUtil::DeltaR(mu1_p4{suff}, mu2_p4{suff})")

        mass_filters.append(f"m_mumu{suff} > {mass_cut}")

    # 3d. Apply active filters to the data stream
    operator = " || " if (not is_data and want_variations) else " && "
    # print(operator.join(event_filters))
    df = df.Filter(operator.join(event_filters), "DiMuon Filter")
    # print(operator.join(mass_filters))
    df = df.Filter(operator.join(mass_filters), f"M_mumu gt {int(mass_cut)} GeV")

    # 3e. Passive evaluation of noCorr and ScaRe variables anchored to the nominal selection indices
    nominal_suff = ""
    idx_mu1 = f"mu1_idx{nominal_suff}"
    idx_mu2 = f"mu2_idx{nominal_suff}"

    passive_pt_variables = {
        "_noCorr": "Muon_pt_noCorr",
        "_ScaRe":  "Muon_pt_ScaRe"
    }

    for label, branch_pt in passive_pt_variables.items():
        if branch_pt not in available_cols: continue

        df = define_and_track(df, f"mu1_pt{label}", f"{idx_mu1} >= 0 ? {branch_pt}[{idx_mu1}] : -999.f")
        df = define_and_track(df, f"mu2_pt{label}", f"{idx_mu2} >= 0 ? {branch_pt}[{idx_mu2}] : -999.f")

        df = define_and_track(df, f"mu1_p4{label}", f"{idx_mu1} >= 0 ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({branch_pt}[{idx_mu1}], Muon_eta[{idx_mu1}], Muon_phi[{idx_mu1}], Muon_mass[{idx_mu1}]) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0,0,0,0)")
        df = define_and_track(df, f"mu2_p4{label}", f"{idx_mu2} >= 0 ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({branch_pt}[{idx_mu2}], Muon_eta[{idx_mu2}], Muon_phi[{idx_mu2}], Muon_mass[{idx_mu2}]) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0,0,0,0)")

        p4_mumu_passive = f"(mu1_p4{label} + mu2_p4{label})"
        df = define_and_track(df, f"m_mumu{label}", f"{p4_mumu_passive}.M()")
        df = define_and_track(df, f"pt_mumu{label}", f"{p4_mumu_passive}.Pt()")

    return df, new_muon_cols


# =============================================================================
# 4. OBJECT VETOS & ADDITIONAL SYSTEMATICS DEFINITIONS
# =============================================================================
def ApplyElectronVeto(df):
    df = df.Define("Electron_p4", "GetP4(Electron_pt, Electron_eta, Electron_phi, Electron_mass)")
    df = _define_if_missing(df, "veto_electrons", "Electron_pt > 20 && abs(Electron_eta) < 2.5 && Electron_mvaIso_WP90")
    return df.Filter("ROOT::VecOps::Nonzero(veto_electrons).size() == 0", "Electron veto")


def DefineMuonSelection(df, sel_config, only_default, is_data, want_variations=False):
    """Maps configured external selections to their nominal and systematic variations"""
    sel_dict = sel_config.get("muons_selection", {})
    vars_to_store = []

    for sel_name, sel_subdict in sel_dict.items():
        sel_str = sel_subdict['expression']
        df = df.Define(sel_name, sel_str.format(suff=""))
        if sel_subdict['store'] == True: vars_to_store.append(sel_name)

    suffixes = []
    if not only_default:
        suffixes.extend(["_noCorr", "_ScaRe", "_scale", "_noCorr_FSR", "_scale_FSR"])
    if not is_data and want_variations:
        suffixes.extend(["_scale_FSR_up", "_scale_FSR_down", "_resol_FSR_up", "_resol_FSR_down"])
        if not only_default:
            suffixes.extend(["_scale_up", "_scale_down", "_resol_up", "_resol_down"])

    for suff in suffixes:
        for sel_name, sel_subdict in sel_dict.items():
            sel_str = sel_subdict['expression']
            full_name = f"{sel_name}_{suff}"
            df = df.Define(full_name, sel_str.format(suff=suff))
            if sel_subdict['store'] == True: vars_to_store.append(full_name)
    return df, vars_to_store


def ProcessExtraMuonVariables(df, is_data, muon_columns, default_suffix, trigger_config, only_default=True, want_variations=False, pt_min=15.0):
    """Saves vector properties of remaining Loose-ID extra muons bypassing signal roles"""
    new_extra_muon_cols = []
    available_cols = _column_names(df)

    pt_configs = [f"Muon_pt{default_suffix}"]
    if not only_default:
        pt_configs.extend(["Muon_pt_noCorr", "Muon_pt_ScaRe", "Muon_pt_scale", "Muon_pt_noCorr_FSR", "Muon_pt_scale_FSR"])
    if not is_data and want_variations:
        pt_configs.extend(["Muon_pt_scale_FSR_up", "Muon_pt_scale_FSR_down", "Muon_pt_resol_FSR_up", "Muon_pt_resol_FSR_down"])

    def define_and_track_extra(dataframe, name, expr):
        if name in _column_names(dataframe): return dataframe
        new_extra_muon_cols.append(name)
        return dataframe.Define(name, expr)

    for name_pt in pt_configs:
        if name_pt not in available_cols: continue
        suff = "" if f"Muon_pt{default_suffix}" == name_pt else "_" + name_pt.replace("Muon_pt_", "")

        df = df.Define(f"extra_good_muons{suff}", f"{name_pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_looseId && Muon_pfIsoId >= 2")
        df = df.Define(f"extra_good_idx{suff}", f"ROOT::VecOps::Nonzero(extra_good_muons{suff})")
        df = df.Define(f"extra_sorted_idx{suff}", f"Reverse(Take(extra_good_idx{suff}, Argsort(Take({name_pt}, extra_good_idx{suff}))))")

        m1, m2 = f"mu1_idx{suff}", f"mu2_idx{suff}"
        df = define_and_track_extra(df, f"extraMuon_idx{suff}", f"extra_sorted_idx{suff}[extra_sorted_idx{suff} != {m1} && extra_sorted_idx{suff} != {m2}]")
        df = define_and_track_extra(df, f"n_extraMuon{suff}", f"(int)extraMuon_idx{suff}.size()")

        df = define_and_track_extra(df, f"extraMuon_pt{suff}", f"Take({name_pt}, extraMuon_idx{suff})")
        df = define_and_track_extra(df, f"extraMuon_eta{suff}", f"Take(Muon_eta, extraMuon_idx{suff})")
        df = define_and_track_extra(df, f"extraMuon_phi{suff}", f"Take(Muon_phi, extraMuon_idx{suff})")
        df = define_and_track_extra(df, f"extraMuon_charge{suff}", f"Take(Muon_charge, extraMuon_idx{suff})")
        if "Muon_pfRelIso04_all" in available_cols:
            df = define_and_track_extra(df, f"extraMuon_pfRelIso04{suff}", f"Take(Muon_pfRelIso04_all, extraMuon_idx{suff})")

    return df, new_extra_muon_cols