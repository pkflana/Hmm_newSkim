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


def DefineMuonPtAndP4(df, is_data, only_default=True, want_variations=False):
    """Definisce nel dataframe i pT e p4 corretti per tutte le variazioni richieste"""
    _declare_muon_helpers()


    pt_configurations = [
        ("Muon_pt_noCorr",     "Muon_pt",                      "Muon_bsConstrainedPt"),
        ("Muon_pt_ScaRe",      "Muon_pt_corr",                 "Muon_bsc_pt_corr"),
        ("Muon_pt_ScaRe_FSR",  "Muon_pt_nano_scare_FSR",       "Muon_bsc_pt_nano_scare_FSR")
    ]

    if not only_default:
        pt_configurations.extend([
            ("Muon_pt_scale",      "Muon_pt_scale_corr",           "Muon_bsc_pt_scale_corr"),
            ("Muon_pt_noCorr_FSR", "Muon_pt_nano_FSR",             "Muon_pt_bsc_FSR"),
            ("Muon_pt_scale_FSR",  "Muon_pt_nano_scale_corr_FSR",  "Muon_bsc_pt_nano_scale_corr_FSR")
        ])

    if not is_data and want_variations:
        pt_configurations.extend([
            ("Muon_pt_scale_FSR_up",   "Muon_pt_nano_scale_corr_FSR_up",   "Muon_bsc_pt_nano_scale_corr_FSR_up"),
            ("Muon_pt_scale_FSR_down", "Muon_pt_nano_scale_corr_FSR_down", "Muon_bsc_pt_nano_scale_corr_FSR_down"),
            ("Muon_pt_resol_FSR_up",   "Muon_pt_nano_corr_resol_FSR_up",   "Muon_bsc_pt_nano_corr_resol_FSR_up"),
            ("Muon_pt_resol_FSR_down", "Muon_pt_nano_corr_resol_FSR_down", "Muon_bsc_pt_nano_corr_resol_FSR_down")
        ])
        if not only_default:
            pt_configurations.extend([
                ("Muon_pt_scale_up",   "Muon_pt_scale_corr_up",   "Muon_bsc_pt_scale_corr_up"),
                ("Muon_pt_scale_down", "Muon_pt_scale_corr_down", "Muon_bsc_pt_scale_corr_down"),
                ("Muon_pt_resol_up",   "Muon_pt_corr_resol_up",   "Muon_bsc_pt_corr_resol_up"),
                ("Muon_pt_resol_down", "Muon_pt_corr_resol_down", "Muon_bsc_pt_corr_resol_down")
            ])

    # Applica le definizioni dei vettori pT e p4 nel DataFrame
    available_cols = _column_names(df)
    for name_pt, branch_nano, branch_bsc in pt_configurations:
        if branch_nano not in available_cols or branch_bsc not in available_cols:
            continue
        df = _define_if_missing(df, name_pt, f"Muon_pt_sel({branch_nano}, {branch_bsc}, Muon_bsConstrainedChi2)")
        df = _define_if_missing(df, name_pt.replace("pt", "p4"), f"GetP4({name_pt}, Muon_eta, Muon_phi, Muon_mass)")

    return df


def ApplyMuonTriggerMatching(df, trigger_config, apply_filter=True):
    """Calcola il trigger matching globale a livello di evento e array"""
    matching_bool_vars = []
    available_cols = _column_names(df)

    # Inizializza TrigObj_p4 se presente
    if "TrigObj_pt" in available_cols:
        df = _define_if_missing(df, "TrigObj_idx", "CreateIndexes(TrigObj_pt.size())")
        if "TrigObj_mass" not in available_cols:
            df = _define_if_missing(df, "TrigObj_mass", "RVecF(TrigObj_pt.size(), 0.f)")
        df = _define_if_missing(df, "TrigObj_p4", "GetP4(TrigObj_pt, TrigObj_eta, TrigObj_phi, TrigObj_mass, TrigObj_idx)")

    for path in trigger_config.keys():
        path_name = trigger_config[path]["path"][0]
        leg_config = trigger_config[path]["legs"][0]

        offline_cut_expr = leg_config["offline_obj"]["cut"].format(obj="Muon", pt="pt_noCorr")
        online_cut_expr = leg_config["online_obj"]["cut"]

        df = _define_if_missing(df, f"Muon_passOfflineCut_{path}", offline_cut_expr)
        df = _define_if_missing(df, f"TrigObj_passOnlineCut_{path}", online_cut_expr)

        df = _define_if_missing(
            df, f"Muon_TriggerMatchingIdx_{path}",
            f"FindMatching(Muon_passOfflineCut_{path}, TrigObj_passOnlineCut_{path}, Muon_p4_noCorr, TrigObj_p4, 0.4)"
        )

        matching_branch_bool = f"Event_HasTriggerMatching_{path}"
        df = df.Define(matching_branch_bool, f"{path_name} && Any(Muon_TriggerMatchingIdx_{path} > -1)")
        matching_bool_vars.append(matching_branch_bool)

    if apply_filter and matching_bool_vars:
        total_or_string = " || ".join(matching_bool_vars)
        df = df.Filter(total_or_string, "Trigger application filter")

    return df, matching_bool_vars


def ProcessMuonVariables(df, is_data, muon_columns, default_suffix, trigger_config, only_default=True, want_variations=False, pt_min=15.0, mass_cut=50.0):
    """Seleziona la coppia di muoni di segnale ed estrae tutte le variabili tracciandole"""
    new_muon_cols = []

    # Seleziona quali pT processare indice per indice per l'output finale
    pt_configurations = [f"Muon_pt{default_suffix}"] # Default standard richiesto

    if not only_default:
        pt_configurations.extend(["Muon_pt_noCorr", "Muon_pt_ScaRe", "Muon_pt_scale", "Muon_pt_noCorr_FSR", "Muon_pt_scale_FSR"])

    if not is_data and want_variations:
        pt_configurations.extend(["Muon_pt_scale_FSR_up", "Muon_pt_scale_FSR_down", "Muon_pt_resol_FSR_up", "Muon_pt_resol_FSR_down"])
        if not only_default:
            pt_configurations.extend(["Muon_pt_scale_up", "Muon_pt_scale_down", "Muon_pt_resol_up", "Muon_pt_resol_down"])

    # Parsing rami scalari esterni
    muon_scalar_branches = {
        "pt_noCorr":"Muon_pt_noCorr",
    }
    for muon_col in muon_columns:
        if "pt" in muon_col.lower(): continue
        col_suffix = "_".join(s for s in muon_col.split("_")[1:])
        muon_scalar_branches[col_suffix] = muon_col

    def define_and_track(dataframe, col_name, expression):
        if col_name in _column_names(dataframe):
            return dataframe
        if "p4" not in col_name:
            new_muon_cols.append(col_name)
        return dataframe.Define(col_name, expression)

    available_cols = _column_names(df)
    event_filters = []

    for name_pt in pt_configurations:
        if name_pt not in available_cols:
            continue

        suffix = "_" + name_pt.replace("Muon_pt_", "")
        if suffix == default_suffix:
            suffix = ""

        # Selezione cinematica e ordinamento basato sul pT specifico della variazione
        df = define_and_track(df, f"good_muons{suffix}", f"{name_pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_mediumId && Muon_pfIsoId >= 2")
        df = define_and_track(df, f"good_idx{suffix}", f"ROOT::VecOps::Nonzero(good_muons{suffix})")
        df = define_and_track(df, f"sorted_idx{suffix}", f"Reverse(Take(good_idx{suffix}, Argsort(Take({name_pt}, good_idx{suffix}))))")

        # Estrazione indici mu1 e mu2 di segnale
        df = define_and_track(df, f"mu1_idx{suffix}", f"sorted_idx{suffix}.size() > 0 ? (int)sorted_idx{suffix}[0] : -1")
        df = define_and_track(df, f"mu2_idx{suffix}", f"sorted_idx{suffix}.size() > 1 ? (int)sorted_idx{suffix}[1] : -1")
        event_filters.append(f"sorted_idx{suffix}.size() > 1")

        # Estrazione variabili scalari per mu1 e mu2
        for num in [1, 2]:
            idx = f"mu{num}_idx{suffix}"
            df = define_and_track(df, f"mu{num}_pt{suffix}", f"{idx} >= 0 ? {name_pt}[{idx}] : -999.f")

            for branch_suff, original_branch in muon_scalar_branches.items():
                df = define_and_track(df, f"mu{num}_{branch_suff}{suffix}", f"{idx} >= 0 ? {original_branch}[{idx}] : -999.f")

            df = define_and_track(
                df, f"mu{num}_p4{suffix}",
                f"{idx} >= 0 ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({name_pt}[{idx}], Muon_eta[{idx}], Muon_phi[{idx}], Muon_mass[{idx}]) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0,0,0,0)"
            )

            # Estrazione trigger matching per mu1 e mu2 (Indice per Indice)
            for path in trigger_config.keys():
                df = define_and_track(
                    df, f"mu{num}_HasTriggerMatching_{path}{suffix}",
                    f"{idx} >= 0 ? (Muon_TriggerMatchingIdx_{path}[{idx}] >= 0) : false"
                )

        # Osservabili Dimuone
        p4_mumu = f"(mu1_p4{suffix} + mu2_p4{suffix})"
        df = define_and_track(df, f"m_mumu{suffix}", f"{p4_mumu}.M()")
        df = define_and_track(df, f"pt_mumu{suffix}", f"{p4_mumu}.Pt()")
        df = define_and_track(df, f"eta_mumu{suffix}", f"{p4_mumu}.Eta()")
        df = define_and_track(df, f"phi_mumu{suffix}", f"{p4_mumu}.Phi()")
        df = define_and_track(df, f"dR_mumu{suffix}", f"ROOT::Math::VectorUtil::DeltaR(mu1_p4{suffix}, mu2_p4{suffix})")

    # Filtri di selezione finali sulla coppia
    operator = " && " if (not is_data and want_variations) else " || "
    df = df.Filter(operator.join(event_filters), "Dimuon selection")

    updated_cols = _column_names(df)
    mass_filters = [f"m_mumu_{n.replace('Muon_pt_', '')} > {mass_cut}" for n in pt_configurations if f"m_mumu_{n.replace('Muon_pt_', '')}" in updated_cols]
    if mass_filters:
        df = df.Filter(operator.join(mass_filters), f"Mass cut > {mass_cut} GeV")

    return df, new_muon_cols

def ApplyElectronVeto(df):
    df = df.Define("Electron_p4", "GetP4(Electron_pt, Electron_eta, Electron_phi, Electron_mass)")
    df = _define_if_missing(df, "veto_electrons", "Electron_pt > 20 && abs(Electron_eta) < 2.5 && Electron_mvaIso_WP90")
    return df.Filter("ROOT::VecOps::Nonzero(veto_electrons).size() == 0", "Electron veto")

def DefineMuonSelection(df,sel_config, only_default, is_data, want_variations=False):
    sel_dict = sel_config.get("muons_selection", {})
    vars_to_store = []
    for sel_name,sel_str in sel_dict.items():
        sel_str_complete = sel_str.format(suff="") # default suffix is ""
        sel_name_complete= sel_name
        df = df.Define(sel_name_complete, sel_str_complete)
        vars_to_store.append(sel_name_complete)

    additional_suffix = []
    if not only_default:
        additional_suffix.extend(["_noCorr", "_ScaRe", "_scale", "_noCorr_FSR", "_scale_FSR"])
    if not is_data and want_variations:
        additional_suffix.extend(["_scale_FSR_up", "_scale_FSR_down", "_resol_FSR_up", "_resol_FSR_down"])
        if not only_default:
            additional_suffix.extend(["_scale_up", "_scale_down", "_resol_up", "_resol_down"])

    for additional_suff in additional_suffix:
        for sel_name,sel_str in sel_dict.items():
            sel_str_complete = sel_str.format(suff=additional_suff)
            sel_name_complete=f"{sel_name}_{additional_suff}"
            df = df.Define(sel_name_complete, sel_str_complete)
            vars_to_store.append(sel_name_complete)
    return df,vars_to_store


def ProcessExtraMuonVariables(df, is_data, muon_columns, default_suffix, trigger_config, only_default=True, want_variations=False, pt_min=15.0):
    """
    Seleziona e salva l'array di indici di tutti gli extra muons che passano il LooseId
    anziché il MediumId, escludendo i due muoni principali di segnale (Veto).
    """
    new_extra_muon_cols = []

    pt_configurations = [f"Muon_pt{default_suffix}"]
    if not only_default:
        pt_configurations.extend([
            "Muon_pt_noCorr", "Muon_pt_ScaRe", "Muon_pt_scale", "Muon_pt_noCorr_FSR", "Muon_pt_scale_FSR"
        ])

    if not is_data and want_variations:
        pt_configurations.extend([
            "Muon_pt_scale_FSR_up", "Muon_pt_scale_FSR_down", "Muon_pt_resol_FSR_up", "Muon_pt_resol_FSR_down"
        ])

    def define_and_track_extra(dataframe, col_name, expression):
        if col_name in _column_names(dataframe):
            return dataframe
        new_extra_muon_cols.append(col_name)
        return dataframe.Define(col_name, expression)

    available_cols = _column_names(df)

    for name_pt in pt_configurations:
        if name_pt not in available_cols:
            continue

        suffix = "_" + name_pt.replace("Muon_pt_", "")
        if suffix == default_suffix:
            suffix = ""

        # 1. Selezione Loose ID + Kinematics + Isolation
        df = define_and_track_extra(
            df, f"extra_good_muons{suffix}",
            f"{name_pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_looseId && Muon_pfIsoId >= 2"
        )
        df = define_and_track_extra(df, f"extra_good_idx{suffix}", f"ROOT::VecOps::Nonzero(extra_good_muons{suffix})")

        # Ordinamento per pT decrescente degli indici loose trovati
        df = define_and_track_extra(
            df, f"extra_sorted_idx{suffix}",
            f"Reverse(Take(extra_good_idx{suffix}, Argsort(Take({name_pt}, extra_good_idx{suffix}))))"
        )

        # 2. Applicazione del VETO (rimuoviamo mu1_idx e mu2_idx se presenti nell'array)
        m1 = f"mu1_idx{suffix}"
        m2 = f"mu2_idx{suffix}"

        # Salviamo DIRETTAMENTE il vettore finale filtrato degli indici extra
        # Questo sarà un ROOT::VecOps::RVec<int> salvato nel TTree
        df = define_and_track_extra(
            df, f"extraMuon_idx{suffix}",
            f"extra_sorted_idx{suffix}[extra_sorted_idx{suffix} != {m1} && extra_sorted_idx{suffix} != {m2}]"
        )

        # 3. Numero di muoni extra nell'evento (utile per tagli veloci)
        df = define_and_track_extra(df, f"n_extraMuon{suffix}", f"(int)extraMuon_idx{suffix}.size()")

        # 4. Salvataggio delle proprietà fondamentali come vettori (RVec) usando la shortcut Take()
        df = define_and_track_extra(df, f"extraMuon_pt{suffix}", f"Take({name_pt}, extraMuon_idx{suffix})")
        df = define_and_track_extra(df, f"extraMuon_eta{suffix}", f"Take(Muon_eta, extraMuon_idx{suffix})")
        df = define_and_track_extra(df, f"extraMuon_phi{suffix}", f"Take(Muon_phi, extraMuon_idx{suffix})")
        df = define_and_track_extra(df, f"extraMuon_charge{suffix}", f"Take(Muon_charge, extraMuon_idx{suffix})")

        if "Muon_pfRelIso04_all" in available_cols:
            df = define_and_track_extra(df, f"extraMuon_pfRelIso04{suffix}", f"Take(Muon_pfRelIso04_all, extraMuon_idx{suffix})")

    return df, new_extra_muon_cols