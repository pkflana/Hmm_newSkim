import ROOT
import sys

def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}

def _define_if_missing(df, name, expression):
    if name in _column_names(df):
        return df
    return df.Define(name, expression)

# =============================================================================
# 1. JET PT & P4 VARIATION CONFIGURATIONS (Initial Jet Cols)
# =============================================================================
def GetJetPtConfigurations(is_data, want_variations):
    """Mappatura esplicita dei suffissi e dei rami di pT da NanoAOD."""
    configs = [("", "Jet_pt_corr")] # Suffix nominale

    if not is_data and want_variations:
        configs.extend([
            ("_JERUp",       "Jet_pt_JERUp"),
            ("_JERDown",     "Jet_pt_JERDown"),
            ("_TotalUp",     "Jet_pt_TotalUp"),
            ("_TotalDown",   "Jet_pt_TotalDown"),
            ("_unCorr",      "Jet_pt")
        ])
    return configs


def DefineJetInitialVectors(df, is_data, want_variations=False):
    """Inizializzazione dei vettori p4 per tutte le variazioni attive."""
    available_cols = _column_names(df)
    pt_configs = GetJetPtConfigurations(is_data, want_variations)

    df = _define_if_missing(df, "Jet_idx", "CreateIndexes(Jet_pt.size())")

    for suff, branch_pt in pt_configs:
        if branch_pt not in available_cols:
            continue
        df = _define_if_missing(df, f"Jet_p4{suff}", f"GetP4({branch_pt}, Jet_eta, Jet_phi, Jet_mass, Jet_idx)")

    return df


# =============================================================================
# 2. NTUPLIZER CORE PROCESSING (WITH INPUT VARIABLES DYNAMIC MAPPING)
# =============================================================================
def ProcessAllJetVariables(df, is_data, jet_columns, config, bTagAlgo, bTagDict, want_variations=False, mu_suff="ScaRe_FSR"):
    """
    Seleziona i jet applicando cross-cleaning e Horn Veto. Salva la collezione
    dei SelectedJets includendo tutte le variabili passate in 'jet_columns' filtrate.
    Estrae inoltre gli indici nativi delle gambe VBF.
    """
    new_jet_cols = []
    available_cols = _column_names(df)

    # Parametri di taglio da dizionario config
    pt_min = config.get("jet_pt_min", 25.0)
    eta_max = config.get("jet_eta_max", 4.7)
    horn_veto_base_expr = config.get("jet_horn_veto_expr", "false")

    loose_wp = bTagDict.get("loose", 0.0)
    medium_wp = bTagDict.get("medium", 0.0)

    # Inizializzazione p4 dei jet
    df = DefineJetInitialVectors(df, is_data, want_variations)
    pt_configs = GetJetPtConfigurations(is_data, want_variations)

    # Mappatura delle altre variabili dei jet fornite in input (escludendo pT/eta/phi/mass gestiti esplicitamente)
    jet_extra_branches = {}
    for col in jet_columns:
        col_lower = col.lower()
        if any(k in col_lower for k in ["_pt", "_eta", "_phi", "_mass", "jet_idx"]):
            continue
        # Estrae il suffisso pulito (es: da 'Jet_jetId' prende 'jetId')
        suffix_clean = col.split("Jet_")[-1]
        jet_extra_branches[suffix_clean] = col

    def define_and_track(dataframe, name, expr):
        if name in _column_names(dataframe): return dataframe
        new_jet_cols.append(name)
        return dataframe.Define(name, expr)

    # --- Loop delle Variazioni Sistematiche ---
    for suff, branch_pt in pt_configs:
        if branch_pt not in available_cols: continue

        # Pre-selezione cinematica e applicazione Veto Map
        df = df.Define(f"Jet_preSel{suff}", f"v_ops::pt(Jet_p4{suff}) > {pt_min} && abs(v_ops::eta(Jet_p4{suff})) < {eta_max} && Jet_passJetIdTight")
        df = df.Define(f"Jet_NotInDeadZome{suff}", f"Jet_preSel{suff} && !Jet_vetoMap")

        # Cross-cleaning geometrico dai muoni del segnale (dR > 0.4)
        overlap_expr = f"""
        ROOT::VecOps::RVec<bool> clean_vec;
        clean_vec.reserve(Jet_p4{suff}.size());
        for (size_t i = 0; i < Jet_p4{suff}.size(); ++i) {{
            bool pass = Jet_NotInDeadZome{suff}[i] &&
                        ROOT::Math::VectorUtil::DeltaR(Jet_p4{suff}[i], mu1_p4{mu_suff}) > 0.4 &&
                        ROOT::Math::VectorUtil::DeltaR(Jet_p4{suff}[i], mu2_p4{mu_suff}) > 0.4;
            clean_vec.push_back(pass);
        }}
        return clean_vec;
        """
        df = df.Define(f"Jet_NoOverlapWithMuons{suff}", overlap_expr)

        # Applicazione dinamica della stringa di veto Horn passata da config
        current_horn_expr = horn_veto_base_expr.replace("Jet_p4", f"Jet_p4{suff}")
        df = df.Define(f"Jet_IsInsideHorn{suff}", current_horn_expr)

        # Maschera finale dei jet selezionati (goodJet)
        df = df.Define(f"goodJet{suff}", f"Jet_NoOverlapWithMuons{suff} && !Jet_IsInsideHorn{suff}")

        # ---------------------------------------------------------------------
        # SALVATAGGIO COLLEZIONE "SelectedJets" (VARIABILI FONDAMENTALI)
        # ---------------------------------------------------------------------
        df = define_and_track(df, f"SelectedJet_idx{suff}", f"Jet_idx[goodJet{suff}]")
        df = define_and_track(df, f"SelectedJet_pt{suff}", f"{branch_pt}[goodJet{suff}]")
        df = define_and_track(df, f"SelectedJet_eta{suff}", f"Jet_eta[goodJet{suff}]")
        df = define_and_track(df, f"SelectedJet_phi{suff}", f"Jet_phi[goodJet{suff}]")
        df = define_and_track(df, f"SelectedJet_mass{suff}", f"Jet_mass[goodJet{suff}]")
        df = define_and_track(df, f"N_SelectedJets{suff}", f"(int)SelectedJet_idx{suff}.size()")

        # ---------------------------------------------------------------------
        # SALVATAGGIO DINAMICO DELLE VARIABILI DI INPUT PASSATE (jet_columns)
        # ---------------------------------------------------------------------
        for branch_suff, original_branch in jet_extra_branches.items():
            if original_branch in available_cols:
                df = define_and_track(df, f"SelectedJet_{branch_suff}{suff}", f"{original_branch}[goodJet{suff}]")

        # Informazione b-tagging passata a livello di evento (JetTagSel)
        df = df.Define(f"Jet_btag_Veto_loose{suff}", f"Jet_btag{bTagAlgo}B >= {loose_wp} && abs(v_ops::eta(Jet_p4{suff})) < 2.5")
        df = df.Define(f"Jet_btag_Veto_medium{suff}", f"Jet_btag{bTagAlgo}B >= {medium_wp} && abs(v_ops::eta(Jet_p4{suff})) < 2.5")
        df = define_and_track(df, f"JetTagSel{suff}", f"Jet_p4{suff}[goodJet{suff} && Jet_btag_Veto_medium{suff}].size() < 1 && Jet_p4{suff}[goodJet{suff} && Jet_btag_Veto_loose{suff}].size() < 2")

        # ---------------------------------------------------------------------
        # ESTRAZIONE INDICI DELLE GAMBE VBF (VBFJetIdx_1, VBFJetIdx_2)
        # ---------------------------------------------------------------------
        df = df.Define(f"VBFJetCand{suff}", f"FindVBFJets(Jet_p4{suff}, goodJet{suff})")
        df = define_and_track(df, f"HasVBF{suff}", f"static_cast<bool>(VBFJetCand{suff}.isVBF)")

        df = define_and_track(df, f"VBFJetIdx_1{suff}", f"HasVBF{suff} ? static_cast<int>(VBFJetCand{suff}.leg_index[0]) : -1000")
        df = define_and_track(df, f"VBFJetIdx_2{suff}", f"HasVBF{suff} ? static_cast<int>(VBFJetCand{suff}.leg_index[1]) : -1000")

    return df, new_jet_cols