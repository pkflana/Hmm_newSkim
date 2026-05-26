import ROOT
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from .utilities import *



def _column_names(df):
    return {str(col) for col in df.GetColumnNames()}

def _has_column(df, column):
    return column in _column_names(df)

def _define_if_missing(df, name, expression):
    if _has_column(df, name):
        return df
    return df.Define(name, expression)
    
MUON_PT_VARIATIONS = {
    "Muon_pt_noCorr": ("Muon_pt", "Muon_bsConstrainedPt"),
    "Muon_pt_scale": ("Muon_pt_scale_corr", "Muon_bsc_pt_scale_corr"),
    "Muon_pt_ScaRe": ("Muon_pt_corr", "Muon_bsc_pt_corr"),
    "Muon_pt_noCorr_FSR": ("Muon_pt_nano_FSR", "Muon_pt_bsc_FSR"),
    "Muon_pt_scale_FSR": (
        "Muon_pt_nano_scale_corr_FSR",
        "Muon_bsc_pt_nano_scale_corr_FSR",
    ),
    "Muon_pt_ScaRe_FSR": (
        "Muon_pt_nano_scare_FSR",
        "Muon_bsc_pt_nano_scare_FSR",
    ),
}

MUON_PT_VARIATIONS_SHIFTED = {
    "Muon_pt_scale_up": ("Muon_pt_scale_corr_up", "Muon_bsc_pt_scale_corr_up"),
    "Muon_pt_scale_down": (
        "Muon_pt_scale_corr_down",
        "Muon_bsc_pt_scale_corr_down",
    ),
    "Muon_pt_resol_up": ("Muon_pt_corr_resol_up", "Muon_bsc_pt_corr_resol_up"),
    "Muon_pt_resol_down": (
        "Muon_pt_corr_resol_down",
        "Muon_bsc_pt_corr_resol_down",
    ),
    "Muon_pt_scale_FSR_up": (
        "Muon_pt_nano_scale_corr_FSR_up",
        "Muon_bsc_pt_nano_scale_corr_FSR_up",
    ),
    "Muon_pt_scale_FSR_down": (
        "Muon_pt_nano_scale_corr_FSR_down",
        "Muon_bsc_pt_nano_scale_corr_FSR_down",
    ),
    "Muon_pt_resol_FSR_up": (
        "Muon_pt_nano_corr_resol_FSR_up",
        "Muon_bsc_pt_nano_corr_resol_FSR_up",
    ),
    "Muon_pt_resol_FSR_down": (
        "Muon_pt_nano_corr_resol_FSR_down",
        "Muon_bsc_pt_nano_corr_resol_FSR_down",
    ),
}


def _muon_variation_suffix(muon_pt_name): # "" if muon_pt_name == "Muon_pt_ScaRe_FSR" else
    return "_" + muon_pt_name.replace("Muon_pt_", "")


def _get_muon_pt_variations(is_data, want_variations):
    variations = dict(MUON_PT_VARIATIONS)
    if not is_data and want_variations:
        variations.update(MUON_PT_VARIATIONS_SHIFTED)
    return variations


def _declare_muon_helpers():
    ROOT.gInterpreter.Declare(
        """
        #ifndef NEW_SKIM_MUON_ANALYSIS_HELPERS
        #define NEW_SKIM_MUON_ANALYSIS_HELPERS

        using RVecF = ROOT::VecOps::RVec<float>;

        RVecF Muon_pt_sel(
            const RVecF& Muon_nano_pt,
            const RVecF& Muon_bsc_pt,
            const RVecF& Muon_bsc_chi2
        ) {
            RVecF Muon_pt_sel(Muon_nano_pt.size());
            for (size_t muon_idx = 0; muon_idx < Muon_pt_sel.size(); ++muon_idx) {
                Muon_pt_sel[muon_idx] =
                    Muon_bsc_chi2[muon_idx] < 30 ? Muon_bsc_pt[muon_idx] : Muon_nano_pt[muon_idx];
            }
            return Muon_pt_sel;
        }

        #endif
        """
    )


def DefineMuonPtVariations(df, is_data, want_variations):
    _declare_muon_helpers()
    available_columns = _column_names(df)
    for mu_pt_final_name, muons_pt_orig in _get_muon_pt_variations(is_data,want_variations).items():
        if mu_pt_final_name in available_columns:
            continue
        if not all(branch in available_columns for branch in muons_pt_orig):
            continue
        df = df.Define(
            mu_pt_final_name,
            f"Muon_pt_sel({muons_pt_orig[0]}, {muons_pt_orig[1]}, Muon_bsConstrainedChi2)",
        )
        available_columns.add(mu_pt_final_name)
        df = df.Define(mu_pt_final_name.replace("pt","p4"), f"GetP4({mu_pt_final_name}, Muon_eta, Muon_phi, Muon_mass) ")
    return df


def SelectMuonsForVariations(df, is_data, want_variations, pt_min=15.0):
    df = DefineMuonPtVariations(df, is_data, want_variations)
    available_columns = _column_names(df)

    for mu_pt in _get_muon_pt_variations(is_data, want_variations):
        if mu_pt not in available_columns:
            continue

        suffix = _muon_variation_suffix(mu_pt)
        df = _define_if_missing(
            df,
            f"good_muons{suffix}",
            (
                f"{mu_pt} > {pt_min}"
                " && abs(Muon_eta) < 2.4"
                " && Muon_mediumId"
                " && Muon_pfIsoId >= 2"
            ),
        )
        df = _define_if_missing(
            df,
            f"good_muon_idx{suffix}",
            f"ROOT::VecOps::Nonzero(good_muons{suffix})",
        )
        df = _define_if_missing(
            df,
            f"sorted_good_muon_idx{suffix}",
            f"""
            Reverse(
                Take(
                    good_muon_idx{suffix},
                    Argsort(Take({mu_pt}, good_muon_idx{suffix}))
                )
            )
            """,
        )
        df = _define_if_missing(
            df,
            f"mu1_idx{suffix}",
            f"sorted_good_muon_idx{suffix}.size() > 0 ? static_cast<int>(sorted_good_muon_idx{suffix}[0]) : -1",
        )
        df = _define_if_missing(
            df,
            f"mu2_idx{suffix}",
            f"sorted_good_muon_idx{suffix}.size() > 1 ? static_cast<int>(sorted_good_muon_idx{suffix}[1]) : -1",
        )
    return df


def DefineMuonPairObservables(df, is_data, want_variations):
    df = SelectMuonsForVariations(df, is_data, want_variations)
    available_columns = _column_names(df)

    muon_scalar_branches = {
        "pt": "{mu_pt}[{idx}]",
        "eta": "Muon_eta[{idx}]",
        "phi": "Muon_phi[{idx}]",
        "mass": "Muon_mass[{idx}]",
        "charge": "Muon_charge[{idx}]",
        "bsConstrainedChi2": "Muon_bsConstrainedChi2[{idx}]",
        "dxy": "Muon_dxy[{idx}]",
        "dz": "Muon_dz[{idx}]",
        "pfIsoId": "Muon_pfIsoId[{idx}]",
        "mediumId": "Muon_mediumId[{idx}]",
    }

    for mu_pt in _get_muon_pt_variations(is_data, want_variations):
        suffix = _muon_variation_suffix(mu_pt)
        # print(f"suffix is {suffix}")
        if (
            mu_pt not in available_columns
            or f"mu1_idx{suffix}" not in available_columns
            or f"mu2_idx{suffix}" not in available_columns
        ):
            # print(f"{mu_pt} in availabel columns? {mu_pt in available_columns}")
            # print(f"mu1_idx{suffix} in availabel columns?", f"mu1_idx{suffix}" not in available_columns)
            # print(f"mu2_idx{suffix} in availabel columns?", f"mu2_idx{suffix}" not in available_columns)
            continue

        for mu_num in [1, 2]:
            idx_name = f"mu{mu_num}_idx{suffix}"
            for obs_name, obs_expr in muon_scalar_branches.items():
                df = _define_if_missing(
                    df,
                    f"mu{mu_num}_{obs_name}{suffix}",
                    f"{idx_name} >= 0 ? {obs_expr.format(mu_pt=mu_pt, idx=idx_name)} : -999.f",
                )

            df = _define_if_missing(
                df,
                f"mu{mu_num}_p4{suffix}",
                (
                    f"{idx_name} >= 0 ? "
                    f"ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({mu_pt}[{idx_name}], Muon_eta[{idx_name}], Muon_phi[{idx_name}], Muon_mass[{idx_name}]) : "
                    "ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(0., 0., 0., 0.)"
                ),
            )

        p4_dimu = f"(mu1_p4{suffix} + mu2_p4{suffix})"
        df = _define_if_missing(df, f"m_mumu{suffix}", f"{p4_dimu}.M()")
        df = _define_if_missing(df, f"pt_mumu{suffix}", f"{p4_dimu}.Pt()")
        df = _define_if_missing(df, f"eta_mumu{suffix}", f"{p4_dimu}.Eta()")
        df = _define_if_missing(df, f"phi_mumu{suffix}", f"{p4_dimu}.Phi()")
        df = _define_if_missing(df, f"y_mumu{suffix}", f"{p4_dimu}.Rapidity()")
        df = _define_if_missing(
            df,
            f"dR_mumu{suffix}",
            f"ROOT::Math::VectorUtil::DeltaR(mu1_p4{suffix}, mu2_p4{suffix})",
        )

        available_columns = _column_names(df)

    return df


def ApplyDimuonMassCut(df, is_data, want_variations, cut_value=50.0, require_all_variations=False):
    df = DefineMuonPairObservables(df, is_data, want_variations)
    available_columns = _column_names(df)

    mass_columns = []
    for mu_pt in _get_muon_pt_variations(is_data, want_variations):
        suffix = _muon_variation_suffix(mu_pt)
        mass_column = f"m_mumu{suffix}"
        if mass_column in available_columns:
            mass_columns.append(mass_column)

    if not mass_columns:
        raise RuntimeError("No dimuon mass columns available for dimuon invariant mass cut")

    mass_operator = " && " if require_all_variations else " || "
    mass_cut = mass_operator.join([f"{mass_column} > {cut_value}" for mass_column in mass_columns])
    return df.Filter(mass_cut, f"m_mumu>{cut_value:g}")


def ApplyElectronVeto(df):
    df = df.Define(f"Electron_p4", f"GetP4(Electron_pt, Electron_eta, Electron_phi, Electron_mass) ")
    df = _define_if_missing(
        df,
        "Electron_veto",
        "Electron_pt > 20 && abs(Electron_eta) < 2.5 && Electron_mvaIso_WP90",
    )
    return df.Filter("ROOT::VecOps::Nonzero(Electron_veto).size() == 0", "No extra electrons")


def ApplyMuonSelection(df, is_data,want_variations, dimuon_mass_cut=50.0):
    df = DefineMuonPairObservables(df, is_data, want_variations)
    df = ApplyElectronVeto(df)
    df = ApplyDimuonMassCut(df, is_data, want_variations, dimuon_mass_cut)
    return df


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
