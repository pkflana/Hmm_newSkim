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

def ProcessMuons(df, is_data, muon_columns, only_fsr=True, want_variations=False, pt_min=15.0, mass_cut=50.0):
    _declare_muon_helpers()

    new_muon_cols = []  # List to keep track of all newly created columns

    # 1. Define target branches to process (Name, NanoAOD_Branch, BSC_Branch)
    pt_configurations = [
        ("Muon_pt_ScaRe_FSR", "Muon_pt_nano_scare_FSR", "Muon_bsc_pt_nano_scare_FSR")
    ]

    if not only_fsr:
        pt_configurations.extend([
            ("Muon_pt_noCorr",     "Muon_pt",                      "Muon_bsConstrainedPt"),
            ("Muon_pt_scale",      "Muon_pt_scale_corr",           "Muon_bsc_pt_scale_corr"),
            ("Muon_pt_ScaRe",      "Muon_pt_corr",                 "Muon_bsc_pt_corr"),
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
        if not only_fsr:
            pt_configurations.extend([
                ("Muon_pt_scale_up",   "Muon_pt_scale_corr_up",   "Muon_bsc_pt_scale_corr_up"),
                ("Muon_pt_scale_down", "Muon_pt_scale_corr_down", "Muon_bsc_pt_scale_corr_down"),
                ("Muon_pt_resol_up",   "Muon_pt_corr_resol_up",   "Muon_bsc_pt_corr_resol_up"),
                ("Muon_pt_resol_down", "Muon_pt_corr_resol_down", "Muon_bsc_pt_corr_resol_down")
            ])

    # Dynamic parsing of input muon columns (e.g., mapping 'Muon_eta' to 'eta')
    muon_scalar_branches = {}
    for muon_col in muon_columns:
        # Avoid duplicating pt if it's already in muon_columns
        if "pt" in muon_col.lower():
            continue
        # Extract suffix (e.g., 'Muon_mediumId' -> 'mediumId')
        col_suffix = "_".join(s for s in muon_col.split("_")[1:])
        muon_scalar_branches[col_suffix] = muon_col

    # Helper inner function to define columns and automatically add them to our tracking list
    def define_and_track(dataframe, col_name, expression):
        if col_name in _column_names(dataframe):
            return dataframe
        if "p4" not in col_name:
            new_muon_cols.append(col_name)
        return dataframe.Define(col_name, expression)

    # 2. Loop over configurations to define observables
    available_cols = _column_names(df)
    event_filters = []

    for name_pt, branch_nano, branch_bsc in pt_configurations:
        if branch_nano not in available_cols or branch_bsc not in available_cols:
            continue

        suffix = "_" + name_pt.replace("Muon_pt_", "")

        # Compute selected pT and p4 vector
        df = define_and_track(df, name_pt, f"Muon_pt_sel({branch_nano}, {branch_bsc}, Muon_bsConstrainedChi2)")
        df = define_and_track(df, name_pt.replace("pt", "p4"), f"GetP4({name_pt}, Muon_eta, Muon_phi, Muon_mass)")

        # Select and sort good muons
        df = define_and_track(df, f"good_muons{suffix}", f"{name_pt} > {pt_min} && abs(Muon_eta) < 2.4 && Muon_mediumId && Muon_pfIsoId >= 2")
        df = define_and_track(df, f"good_idx{suffix}", f"ROOT::VecOps::Nonzero(good_muons{suffix})")
        df = define_and_track(df, f"sorted_idx{suffix}", f"Reverse(Take(good_idx{suffix}, Argsort(Take({name_pt}, good_idx{suffix}))))")

        # Extract leading and subleading indices
        df = define_and_track(df, f"mu1_idx{suffix}", f"sorted_idx{suffix}.size() > 0 ? (int)sorted_idx{suffix}[0] : -1")
        df = define_and_track(df, f"mu2_idx{suffix}", f"sorted_idx{suffix}.size() > 1 ? (int)sorted_idx{suffix}[1] : -1")
        event_filters.append(f"sorted_idx{suffix}.size() > 1")

        # Single muon observables
        for num in [1, 2]:
            idx = f"mu{num}_idx{suffix}"

            # 1. Define the specific pT variation for this muon
            df = define_and_track(df, f"mu{num}_pt{suffix}", f"{idx} >= 0 ? {name_pt}[{idx}] : -999.f")

            # 2. Dynamically define all external scalar branches passed into the function
            for branch_suff, original_branch in muon_scalar_branches.items():
                df = define_and_track(df, f"mu{num}_{branch_suff}{suffix}", f"{idx} >= 0 ? {original_branch}[{idx}] : -999.f")

            df = define_and_track(
                df, f"mu{num}_p4{suffix}",
                f"{idx} >= 0 ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({name_pt}[{idx}], Muon_eta[{idx}], Muon_phi[{idx}], Muon_mass[{idx}]) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0,0,0,0)"
            )

        # Dimuon observables
        p4_mumu = f"(mu1_p4{suffix} + mu2_p4{suffix})"
        df = define_and_track(df, f"m_mumu{suffix}", f"{p4_mumu}.M()")
        df = define_and_track(df, f"pt_mumu{suffix}", f"{p4_mumu}.Pt()")
        df = define_and_track(df, f"eta_mumu{suffix}", f"{p4_mumu}.Eta()")
        df = define_and_track(df, f"phi_mumu{suffix}", f"{p4_mumu}.Phi()")
        df = define_and_track(df, f"dR_mumu{suffix}", f"ROOT::Math::VectorUtil::DeltaR(mu1_p4{suffix}, mu2_p4{suffix})")

    # 3. Apply Filters
    operator = " && " if (not is_data and want_variations) else " || "

    df = df.Filter(operator.join(event_filters), "Dimuon selection")

    updated_cols = _column_names(df)
    mass_filters = [f"m_mumu_{n.replace('Muon_pt_', '')} > {mass_cut}" for n, _, _ in pt_configurations if f"m_mumu_{n.replace('Muon_pt_', '')}" in updated_cols]
    if mass_filters:
        df = df.Filter(operator.join(mass_filters), f"Mass cut > {mass_cut} GeV")

    return df, new_muon_cols

def ApplyElectronVeto(df):
    df = df.Define("Electron_p4", "GetP4(Electron_pt, Electron_eta, Electron_phi, Electron_mass)")
    df = _define_if_missing(df, "veto_electrons", "Electron_pt > 20 && abs(Electron_eta) < 2.5 && Electron_mvaIso_WP90")
    return df.Filter("ROOT::VecOps::Nonzero(veto_electrons).size() == 0", "Electron veto")


# def GetMuonP4Observables(df):
#     for pt_suffix in [
#         "",
#         "_bsc_scare",
#         "_nano_scare",
#         "_nano",
#         "_bsConstrainedPt",
#     ]:
#         for mu_idx in [1, 2]:
#             mu_pt_name = (
#                 f"mu{mu_idx}_pt{pt_suffix}"
#                 if pt_suffix != "_bsConstrainedPt"
#                 else f"mu{mu_idx}{pt_suffix}"
#             )
#             if f"mu{mu_idx}_p4{pt_suffix}" in df.GetColumnNames():
#                 continue
#             if mu_pt_name not in df.GetColumnNames():
#                 continue
#             df = df.Define(
#                 f"mu{mu_idx}_p4{pt_suffix}",
#                 f"ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({mu_pt_name},mu{mu_idx}_eta,mu{mu_idx}_phi,mu{mu_idx}_mass)",
#             )
#     return df


# def GetAllMuonsObservablesNew(df):
#     df = df.Define("Ebeam", "13600.0/2")

#     dimu_obs = {
#         "pt_mumu": "{dimu}.Pt()",
#         "m_mumu": "{dimu}.M()",
#         "y_mumu": "{dimu}.Rapidity()",
#         "eta_mumu": "{dimu}.Eta()",
#         "phi_mumu": "{dimu}.Phi()",
#         "dR_mumu": "ROOT::Math::VectorUtil::DeltaR({mu1p4}, {mu2p4})",
#         "cosTheta_Phi_CS": "ComputeCosThetaPhiCS({mu1p4}, {mu2p4}, Ebeam)",
#         "cosTheta_CS": "static_cast<float>(std::get<0>(cosTheta_Phi_CS{suff}))",
#         "phi_CS": "static_cast<float>(std::get<1>(cosTheta_Phi_CS{suff}))",
#     }
#     for pt_suffix in [
#         "_nano",
#         "_bsConstrainedPt",
#         "",  # should be same than bsc_scare
#         "_bsc_scare",
#         "_nano_scare",
#         "_FSR_nano_scare",
#         "_FSR_bsc_scare",
#     ]:
#         for mu_idx in [1, 2]:
#             mu_pt_name = (
#                 f"mu{mu_idx}_pt{pt_suffix}"
#                 if pt_suffix != "_bsConstrainedPt"
#                 else f"mu{mu_idx}{pt_suffix}"
#             )
#             if (
#                 mu_pt_name in df.GetColumnNames()
#                 and f"mu{mu_idx}_p4{pt_suffix}" not in df.GetColumnNames()
#             ):
#                 df = df.Define(
#                     f"mu{mu_idx}_p4{pt_suffix}",
#                     f"ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({mu_pt_name},mu{mu_idx}_eta,mu{mu_idx}_phi,mu{mu_idx}_mass)",
#                 )
#         p4_dimu = f"(mu1_p4{pt_suffix}+mu2_p4{pt_suffix})"
#         p4_dimu_list = [f"mu1_p4{pt_suffix}", f"mu2_p4{pt_suffix}"]
#         for obs, expr in dimu_obs.items():
#             if pt_suffix == "":
#                 continue
#             df = df.Define(
#                 f"{obs}{pt_suffix}",
#                 expr.format(
#                     dimu=p4_dimu,
#                     mu1p4=p4_dimu_list[0],
#                     mu2p4=p4_dimu_list[1],
#                     suff=pt_suffix,
#                 ),
#             )
#     for mu_idx in [1, 2]:
#         df = df.Define(
#             f"mu{mu_idx}_p4_noCorr",
#             f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_bsConstrainedPt : mu{mu_idx}_p4_nano",
#         )
#         df = df.Define(
#             f"mu{mu_idx}_p4_ScaRe",
#             f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_bsc_scare : mu{mu_idx}_p4_nano_scare",
#         )
#         df = df.Define(
#             f"mu{mu_idx}_p4_ScaRe_FSR",
#             f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_FSR_bsc_scare : mu{mu_idx}_p4_FSR_nano_scare",
#         )
#     for newsuff in ["noCorr", "ScaRe", "ScaRe_FSR"]:
#         df = df.Define(f"mu1_pt_{newsuff}", f"mu1_p4_{newsuff}.pt()")
#         df = df.Define(f"mu2_pt_{newsuff}", f"mu2_p4_{newsuff}.pt()")
#         p4_dimu_system = f"(mu1_p4_{newsuff}+mu2_p4_{newsuff})"
#         p4_dimu_system_list = [f"mu1_p4_{newsuff}", f"mu2_p4_{newsuff}"]
#         for obs, expr in dimu_obs.items():
#             df = df.Define(
#                 f"{obs}_{newsuff}",
#                 expr.format(
#                     dimu=p4_dimu_system,
#                     mu1p4=p4_dimu_system_list[0],
#                     mu2p4=p4_dimu_system_list[1],
#                     suff=f"_{newsuff}",
#                 ),
#             )
#         df = df.Define(
#             f"mu1_pt_rel_{newsuff}", f"mu1_p4_{newsuff}.pt()/m_mumu_{newsuff}"
#         )
#         df = df.Define(
#             f"mu2_pt_rel_{newsuff}", f"mu2_p4_{newsuff}.pt()/m_mumu_{newsuff}"
#         )

#     pt_variants = {
#         "_nano": {
#             "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
#             "pt_name_template": "mu{0}_pt_nano",
#             "has_scare": False,
#         },
#         "_nano_scare": {
#             "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
#             "pt_name_template": "mu{0}_pt_nano_scare",
#             "has_scare": True,
#             "base_p4_suffix": "_nano",
#         },
#         "_nano_scare_FSR": {
#             "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
#             "pt_name_template": "mu{0}_pt_nano_scare_FSR",
#             "has_scare": True,
#             "base_p4_suffix": "_FSR_nano",
#         },
#         "_bsConstrainedPt": {
#             "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
#             "pt_name_template": "mu{0}_bsConstrainedPt",
#             "has_scare": False,
#         },
#         "_bsc_scare": {
#             "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
#             "pt_name_template": "mu{0}_pt_bsc_scare",
#             "has_scare": True,
#             "base_p4_suffix": "_bsConstrainedPt",
#         },
#         "": {
#             "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
#             "pt_name_template": "mu{0}_pt_bsc_scare",
#             "has_scare": True,
#             "base_p4_suffix": "_bsConstrainedPt",
#         },
#         "_bsc_scare_FSR": {
#             "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
#             "pt_name_template": "mu{0}_pt_bsc_scare_FSR",
#             "has_scare": True,
#             "base_p4_suffix": "_FSR_bsConstrainedPt",
#         },
#     }

#     for pt_suffix, pt_info in pt_variants.items():
#         # Check if both muons have the required pT columns
#         mu1_pt_name = pt_info["pt_name_template"].format(1)
#         mu2_pt_name = pt_info["pt_name_template"].format(2)

#         if (
#             mu1_pt_name not in df.GetColumnNames()
#             or mu2_pt_name not in df.GetColumnNames()
#         ):
#             continue

#         # Calculate relative pT errors for each muon
#         for mu_idx in [1, 2]:
#             sigma_expr = pt_info["pt_err_template"].format(mu_idx)
#             df = df.Define(f"sigma_mu{mu_idx}_pt_rel{pt_suffix}", sigma_expr)

#         # Calculate m_mumu_resolution including ScaRe uncertainties
#         # Base resolution from pT errors: Δm_μμ^rel = sqrt(1/2 * ((Δpt(u1)/pt(u1))^2 + (Δpt(u2)/pt(u2))^2))
#         resolution_expr = f"sqrt(0.5*(pow(sigma_mu1_pt_rel{pt_suffix},2) + pow(sigma_mu2_pt_rel{pt_suffix},2)))"

#         # Handle ScaRe uncertainties if present
#         if pt_info.get("has_scare", False):
#             base_p4_suffix = pt_info.get("base_p4_suffix", "")
#             # Check if ScaRe delta columns exist from friend trees
#             deltas_up_exist = all(
#                 f"mu{mu_idx}_p4{base_p4_suffix}_ScaReUp_delta" in df.GetColumnNames()
#                 for mu_idx in [1, 2]
#             )
#             deltas_down_exist = all(
#                 f"mu{mu_idx}_p4{base_p4_suffix}_ScaReDown_delta" in df.GetColumnNames()
#                 for mu_idx in [1, 2]
#             )

#             if deltas_up_exist and deltas_down_exist:
#                 # Use deltas from friend trees
#                 for mu_idx in [1, 2]:
#                     mu_pt_name = pt_info["pt_name_template"].format(mu_idx)
#                     scare_unc_name = f"sigma_mu{mu_idx}_pt_scare_rel{pt_suffix}"
#                     delta_up = f"mu{mu_idx}_p4{base_p4_suffix}_ScaReUp_delta"
#                     delta_down = f"mu{mu_idx}_p4{base_p4_suffix}_ScaReDown_delta"
#                     # Average of absolute deltas, relative to nominal pT
#                     df = df.Define(
#                         scare_unc_name,
#                         f"(abs({delta_up}) + abs({delta_down})) / 2.0 / {mu_pt_name}",
#                     )

#                 # Add ScaRe uncertainties in quadrature to base resolution
#                 resolution_expr = f"sqrt(0.5*(pow(sigma_mu1_pt_rel{pt_suffix},2) + pow(sigma_mu2_pt_rel{pt_suffix},2)) + 0.5*(pow(sigma_mu1_pt_scare_rel{pt_suffix},2) + pow(sigma_mu2_pt_scare_rel{pt_suffix},2)))"

#         resolution_name = (
#             f"m_mumu_resolution{pt_suffix}" if pt_suffix != "" else "m_mumu_resolution"
#         )
#         df = df.Define(resolution_name, resolution_expr)

#     return df


# def LeptonsSelection(df, is_data=False):
#     df = DefineMuonPairObservables(df, is_data)
#     df = ApplyElectronVeto(df)
#     return df


# def DiMuonMassCut(df, p4_cols=None, cut_value=50, is_data=False):
#     if p4_cols is None:
#         return ApplyDimuonMassCut(df, is_data, cut_value)

#     for p4_col in p4_cols:
#         df = _define_if_missing(
#             df,
#             f"m_mumu_{p4_col}",
#             f"(mu1_{p4_col} + mu2_{p4_col}).M()",
#         )
#     masses_cut = " || ".join([f"m_mumu_{p4_col} > {cut_value}" for p4_col in p4_cols])
#     return df.Filter(masses_cut, masses_cut)
