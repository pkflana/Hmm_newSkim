
def SelectedJetObservablesDef(df):
    columns = {str(col) for col in df.GetColumnNames()}
    jet_names = {
        0: "leading",
        1: "subleading",
        2: "third",
        3: "fourth",
    }
    sel_jet_cols = ["SelectedJet_area","SelectedJet_btagDeepFlavQG","SelectedJet_btagPNetB","SelectedJet_btagPNetQvG","SelectedJet_btagUParTAK4QvG","SelectedJet_eta","SelectedJet_idx","SelectedJet_mass","SelectedJet_phi","SelectedJet_pt"]
    for jet_idx, jet_type in jet_names.items():
        for jet_obs in sel_jet_cols:
            if jet_obs not in columns:
                continue
            jet_obs_suff = "_".join(jet_obs.split("_")[1:])
            df = df.Define(
                f"{jet_type}jet_{jet_obs_suff}",
                f"(SelectedJet_idx.size()>{jet_idx} && !SelectedJet_IsInsideHorn[{jet_idx}]) ? {jet_obs}.at({jet_idx}): -1000.f;",
            )
        df = df.Define(
            f"{jet_type}jet_p4",
            f"(SelectedJet_idx.size()>{jet_idx} && !SelectedJet_IsInsideHorn[{jet_idx}]) ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(SelectedJet_pt.at({jet_idx}), SelectedJet_eta.at({jet_idx}),SelectedJet_phi.at({jet_idx}), SelectedJet_mass.at({jet_idx})) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(-10000.,-10000.,-10000.,-10000.);",
        )
    df = df.Define(f"delta_eta_jj_ls", "std::abs(leadingjet_eta - subleadingjet_eta)")
    df = df.Define(f"m_jj_ls", "(leadingjet_p4+subleadingjet_p4).M()")

    return df


def VBFJetObservablesDef(df):
    columns = {str(col) for col in df.GetColumnNames()}
    sel_jet_cols = ["SelectedJet_area","SelectedJet_btagDeepFlavQG","SelectedJet_btagPNetB","SelectedJet_btagPNetQvG","SelectedJet_btagUParTAK4QvG","SelectedJet_eta","SelectedJet_idx","SelectedJet_mass","SelectedJet_phi","SelectedJet_pt"]
    for vbfj_idx in [1,2]:
        df = df.Define(
            f"vbfjet{vbfj_idx}_p4",
            f"(HasVBF) ? ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(SelectedJet_pt.at(VBFJetIdx_{vbfj_idx}), SelectedJet_eta.at(VBFJetIdx_{vbfj_idx}),SelectedJet_phi.at(VBFJetIdx_{vbfj_idx}), SelectedJet_mass.at(VBFJetIdx_{vbfj_idx})) : ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(-10000.,-10000.,-10000.,-10000.);",
        )
        for jet_obs in sel_jet_cols:
            if jet_obs not in columns:
                continue
            jet_obs_suff = "_".join(jet_obs.split("_")[1:])
            df = df.Define(
                f"vbfjet{vbfj_idx}_{jet_obs_suff}",
                f"(HasVBF) ? {jet_obs}.at(VBFJetIdx_{vbfj_idx}): -1000.f;",
            )

    df = df.Define(
        "m_jj",
        "if (HasVBF) return static_cast<float>((vbfjet1_p4+vbfjet2_p4).M()); return -1000.f",
    )

    df = df.Define(
        "delta_eta_jj",
        "if (HasVBF) return static_cast<float>(abs(vbfjet1_p4.Eta()-vbfjet2_p4.Eta())); return -1000.f",
    )
    df = df.Define(
        "vbfjet1_y",
        "if (HasVBF) return static_cast<float>(vbfjet1_p4.Rapidity()); return -1000.f; ",
    )
    df = df.Define(
        "vbfjet2_y",
        "if (HasVBF) return static_cast<float>(vbfjet2_p4.Rapidity()); return -1000.f; ",
    )
    df = df.Define(
        "delta_phi_jj",
        "if (HasVBF) return static_cast<float>(ROOT::Math::VectorUtil::DeltaPhi( vbfjet1_p4,vbfjet2_p4 ) ); return -1000.f;",
    )

    df = df.Define(f"pt_vbfj1j2", "(vbfjet1_p4+vbfjet2_p4).Pt()")

    return df


def VBFJetMuonsObservablesDef(df):
    mu_suff = "ScaRe_FSR" if "mu1_p4_ScaRe_FSR" in df.GetColumnNames() else ""
    mu_suffix = f"_{mu_suff}" if mu_suff else ""
    mu1_p4 = f"mu1_p4{mu_suffix}"
    mu2_p4 = f"mu2_p4{mu_suffix}"
    pt_mumu_name = f"pt_mumu{mu_suffix}"
    eta_mumu_name = f"eta_mumu{mu_suffix}"
    y_mumu_name = f"y_mumu{mu_suffix}"

    for mu_idx in [1,2]:
        if f"mu{mu_idx}_p4" not in df.GetColumnNames():
            df = df.Define(f"mu{mu_idx}_p4", f"ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>(mu{mu_idx}_pt, mu{mu_idx}_eta, mu{mu_idx}_phi, mu{mu_idx}_mass)")
    if "y_mumu" not in df.GetColumnNames():
        df = df.Define("y_mumu", "return (mu1_p4.Rapidity()+mu2_p4.Rapidity())/2.;")
    df = df.Define(
        "Zeppenfeld_Var",
        f"if (HasVBF) return static_cast<float>(({y_mumu_name} - 0.5*(vbfjet1_y+vbfjet2_y))/std::abs(vbfjet1_y - vbfjet2_y)); return -10000.f;",
    )
    df = df.Define(
        "pT_all_sum",
        f"if(HasVBF) return static_cast<float>(({mu1_p4}+{mu2_p4}+vbfjet1_p4+vbfjet2_p4).Pt()); return -10000.f;",
    )
    df = df.Define(
        "pT_single_sum",
        f"if(HasVBF) return static_cast<float>({mu1_p4}.Pt()+{mu2_p4}.Pt()+vbfjet1_p4.Pt()+vbfjet2_p4.Pt()); return -10000.f;",
    )
    df = df.Define(
        "R_pt",
        f"if(HasVBF) return static_cast<float>(pT_all_sum/pT_single_sum); return -10000.f;",
    )
    df = df.Define(
        "pT_jj_sum",
        f"if(HasVBF) return static_cast<float>((vbfjet1_p4+vbfjet2_p4).Pt()); return -10000.f;",
    )
    df = df.Define(
        "pT_jj_diff",
        f"if(HasVBF) return static_cast<float>((vbfjet1_p4-vbfjet2_p4).Pt()); return -10000.f;",
    )
    df = df.Define(
        "pT_mumu_sum",
        f"return static_cast<float>(({mu1_p4}+{mu2_p4}).Pt());",
    )
    df = df.Define(
        "pt_centrality",
        f"if(HasVBF) return static_cast<float>(( (pT_mumu_sum-0.5*(pT_jj_sum)) / pT_jj_diff)); return -10000.f;",
    )

    df = df.Define(
        "minDeltaPhi",
        f"if(HasVBF) return static_cast<float>(std::min(ROOT::Math::VectorUtil::DeltaPhi( ({mu1_p4}+{mu2_p4}), vbfjet1_p4), ROOT::Math::VectorUtil::DeltaPhi(({mu1_p4}+{mu2_p4}), vbfjet2_p4) ) )  ; return -10000.f;",
    )
    df = df.Define(
        "minDeltaEta",
        f"if(HasVBF) return static_cast<float>(std::min(std::abs({eta_mumu_name} - vbfjet1_eta),std::abs({eta_mumu_name} - vbfjet2_eta))) ; return -10000.f;",
    )
    df = df.Define(
        "minDeltaEtaSigned",
        f"if(HasVBF) return static_cast<float>(std::min(({eta_mumu_name} - vbfjet1_eta),({eta_mumu_name} - vbfjet2_eta))) ; return -10000.f;",
    )

    return df


def SoftJetCollectionCleaningInVBF(df):
    if "SoftActivityJet_idx" not in df.GetColumnNames():
        # print("SoftActivityJet_idx not in df.GetColumnNames")
        df = df.Define(
            f"SoftActivityJet_idx", f"CreateIndexes(SoftActivityJet_pt.size())"
        )
    if f"SoftActivityJet_mass" not in df.GetColumnNames():
        df = df.Define(
            f"SoftActivityJet_mass",
            "RVecF SoftActivityJet_mass(SoftActivityJet_idx.size(),0.); return SoftActivityJet_mass;",
        )
    df = df.Define(
        f"SoftActivityJet_p4",
        f"GetP4(SoftActivityJet_pt, SoftActivityJet_eta, SoftActivityJet_phi, SoftActivityJet_mass, SoftActivityJet_idx)",
    )
    df = df.Define(
        f"SoftActivityJet_pt_gt0",
        f"SoftActivityJet_pt>0",
    )

    df = df.Define(
        "SoftJetActivity_NoOverlapWithMuonsAndVBFJets",
        f"""
        ROOT::VecOps::RVec<bool> out;
        out.reserve(SoftActivityJet_p4.size());

        for (size_t i = 0; i < SoftActivityJet_p4.size(); ++i)
        {{
            bool pass = ROOT::Math::VectorUtil::DeltaR(SoftActivityJet_p4[i], mu1_p4) > 0.4 &&
                    ROOT::Math::VectorUtil::DeltaR(SoftActivityJet_p4[i], mu2_p4) > 0.4 &&
                    ROOT::Math::VectorUtil::DeltaR(SoftActivityJet_p4[i], vbfjet1_p4) > 0.4 &&
                    ROOT::Math::VectorUtil::DeltaR(SoftActivityJet_p4[i], vbfjet2_p4) > 0.4;

            out.push_back(pass);
        }}

        return out;
        """,
    )

    df = df.Define(
        f"SoftJetCleanedActivity_pt",
        "v_ops::pt(SoftActivityJet_p4[SoftJetActivity_NoOverlapWithMuonsAndVBFJets])",
    )
    df = df.Define(
        f"SoftJetCleanedActivity_eta",
        "v_ops::eta(SoftActivityJet_p4[SoftJetActivity_NoOverlapWithMuonsAndVBFJets])",
    )
    df = df.Define(
        f"SoftJetCleanedActivity_N",
        "SoftActivityJet_p4[SoftJetActivity_NoOverlapWithMuonsAndVBFJets].size()",
    )
    df = df.Define(
        f"SoftJetCleanedActivity_ptSum",
        "float sum=0.; for(size_t sj_idx=0; sj_idx<SoftJetCleanedActivity_pt.size();sj_idx++){{sum+=SoftJetCleanedActivity_pt[sj_idx];}} return sum;",
    )

    df = df.Define(
        "SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning",
        f"""
        ROOT::VecOps::RVec<bool> out;
        out.reserve(SoftJetCleanedActivity_eta.size());

        for (size_t i = 0; i < SoftJetCleanedActivity_eta.size(); ++i)
        {{
            bool pass = SoftJetCleanedActivity_eta[i] < std::max(vbfjet1_eta, vbfjet2_eta) && SoftJetCleanedActivity_eta[i] > std::min(vbfjet1_eta, vbfjet2_eta);

            out.push_back(pass);
        }}

        return out;
        """,
    )

    df = df.Define(
        f"SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning_pt",
        "SoftJetCleanedActivity_pt[SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning]",
    )
    df = df.Define(
        f"SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning_eta",
        "SoftJetCleanedActivity_eta[SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning]",
    )
    df = df.Define(
        f"SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning_N",
        "SoftJetCleanedActivity_eta[SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning].size()",
    )
    df = df.Define(
        f"SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning_ptSum",
        "float sum=0.; for(size_t sj_idx=0; sj_idx<SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning_pt.size();sj_idx++){{sum+=SoftJetActivity_NoOverlapWithMuonsAndEtaCleaning_pt[sj_idx];}} return sum;",
    )
    return df




def GetAllMuonsObservablesNew(df):
    df = df.Define("Ebeam", "13600.0/2")

    dimu_obs = {
        "pt_mumu": "{dimu}.Pt()",
        "m_mumu": "{dimu}.M()",
        "y_mumu": "{dimu}.Rapidity()",
        "eta_mumu": "{dimu}.Eta()",
        "phi_mumu": "{dimu}.Phi()",
        "dR_mumu": "ROOT::Math::VectorUtil::DeltaR({mu1p4}, {mu2p4})",
        "cosTheta_Phi_CS": "ComputeCosThetaPhiCS({mu1p4}, {mu2p4}, Ebeam)",
        "cosTheta_CS": "static_cast<float>(std::get<0>(cosTheta_Phi_CS{suff}))",
        "phi_CS": "static_cast<float>(std::get<1>(cosTheta_Phi_CS{suff}))",
    }
    for pt_suffix in ["", "_FSR_scale"
        # "_nano",
        # "_bsConstrainedPt",
        # "",  # should be same than bsc_scare
        # "_bsc_scare",
        # "_nano_scare",
        # "_FSR_nano_scare",
        # "_FSR_bsc_scare",
    ]:
        for mu_idx in [1, 2]:
            mu_pt_name = (
                f"mu{mu_idx}_pt{pt_suffix}"
                if pt_suffix != "_bsConstrainedPt"
                else f"mu{mu_idx}{pt_suffix}"
            )
            if (
                mu_pt_name in df.GetColumnNames()
                and f"mu{mu_idx}_p4{pt_suffix}" not in df.GetColumnNames()
            ):
                df = df.Define(
                    f"mu{mu_idx}_p4{pt_suffix}",
                    f"ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({mu_pt_name},mu{mu_idx}_eta,mu{mu_idx}_phi,mu{mu_idx}_mass)",
                )
        p4_dimu = f"(mu1_p4{pt_suffix}+mu2_p4{pt_suffix})"
        p4_dimu_list = [f"mu1_p4{pt_suffix}", f"mu2_p4{pt_suffix}"]
        for obs, expr in dimu_obs.items():
            # if pt_suffix == "":
            #     continue
            if f"{obs}{pt_suffix}" in df.GetColumnNames():
                continue
            df = df.Define(
                f"{obs}{pt_suffix}",
                expr.format(
                    dimu=p4_dimu,
                    mu1p4=p4_dimu_list[0],
                    mu2p4=p4_dimu_list[1],
                    suff=pt_suffix,
                ),
            )
    # for mu_idx in [1, 2]:
    #     df = df.Define(
    #         f"mu{mu_idx}_p4_noCorr",
    #         f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_bsConstrainedPt : mu{mu_idx}_p4_nano",
    #     )
    #     df = df.Define(
    #         f"mu{mu_idx}_p4_ScaRe",
    #         f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_bsc_scare : mu{mu_idx}_p4_nano_scare",
    #     )
    #     df = df.Define(
    #         f"mu{mu_idx}_p4_ScaRe_FSR",
    #         f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_FSR_bsc_scare : mu{mu_idx}_p4_FSR_nano_scare",
    #     )
    # for newsuff in ["noCorr", "ScaRe", "ScaRe_FSR"]:
    #     df = df.Define(f"mu1_pt_{newsuff}", f"mu1_p4_{newsuff}.pt()")
    #     df = df.Define(f"mu2_pt_{newsuff}", f"mu2_p4_{newsuff}.pt()")
    #     p4_dimu_system = f"(mu1_p4_{newsuff}+mu2_p4_{newsuff})"
    #     p4_dimu_system_list = [f"mu1_p4_{newsuff}", f"mu2_p4_{newsuff}"]
    #     for obs, expr in dimu_obs.items():
    #         df = df.Define(
    #             f"{obs}_{newsuff}",
    #             expr.format(
    #                 dimu=p4_dimu_system,
    #                 mu1p4=p4_dimu_system_list[0],
    #                 mu2p4=p4_dimu_system_list[1],
    #                 suff=f"_{newsuff}",
    #             ),
    #         )
    #     df = df.Define(
    #         f"mu1_pt_rel_{newsuff}", f"mu1_p4_{newsuff}.pt()/m_mumu_{newsuff}"
    #     )
    #     df = df.Define(
    #         f"mu2_pt_rel_{newsuff}", f"mu2_p4_{newsuff}.pt()/m_mumu_{newsuff}"
    #     )

    # pt_variants = {
    #     "_nano": {
    #         "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
    #         "pt_name_template": "mu{0}_pt_nano",
    #         "has_scare": False,
    #     },
    #     "_nano_scare": {
    #         "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
    #         "pt_name_template": "mu{0}_pt_nano_scare",
    #         "has_scare": True,
    #         "base_p4_suffix": "_nano",
    #     },
    #     "_nano_scare_FSR": {
    #         "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
    #         "pt_name_template": "mu{0}_pt_nano_scare_FSR",
    #         "has_scare": True,
    #         "base_p4_suffix": "_FSR_nano",
    #     },
    #     "_bsConstrainedPt": {
    #         "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
    #         "pt_name_template": "mu{0}_bsConstrainedPt",
    #         "has_scare": False,
    #     },
    #     "_bsc_scare": {
    #         "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
    #         "pt_name_template": "mu{0}_pt_bsc_scare",
    #         "has_scare": True,
    #         "base_p4_suffix": "_bsConstrainedPt",
    #     },
    #     "": {
    #         "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
    #         "pt_name_template": "mu{0}_pt_bsc_scare",
    #         "has_scare": True,
    #         "base_p4_suffix": "_bsConstrainedPt",
    #     },
    #     "_bsc_scare_FSR": {
    #         "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
    #         "pt_name_template": "mu{0}_pt_bsc_scare_FSR",
    #         "has_scare": True,
    #         "base_p4_suffix": "_FSR_bsConstrainedPt",
    #     },
    # }

    # for pt_suffix, pt_info in pt_variants.items():
    #     # Check if both muons have the required pT columns
    #     mu1_pt_name = pt_info["pt_name_template"].format(1)
    #     mu2_pt_name = pt_info["pt_name_template"].format(2)

    #     if (
    #         mu1_pt_name not in df.GetColumnNames()
    #         or mu2_pt_name not in df.GetColumnNames()
    #     ):
    #         continue

    #     # Calculate relative pT errors for each muon
    #     for mu_idx in [1, 2]:
    #         sigma_expr = pt_info["pt_err_template"].format(mu_idx)
    #         df = df.Define(f"sigma_mu{mu_idx}_pt_rel{pt_suffix}", sigma_expr)

    #     # Calculate m_mumu_resolution including ScaRe uncertainties
    #     # Base resolution from pT errors: Δm_μμ^rel = sqrt(1/2 * ((Δpt(u1)/pt(u1))^2 + (Δpt(u2)/pt(u2))^2))
    #     resolution_expr = f"sqrt(0.5*(pow(sigma_mu1_pt_rel{pt_suffix},2) + pow(sigma_mu2_pt_rel{pt_suffix},2)))"

    #     # Handle ScaRe uncertainties if present
    #     if pt_info.get("has_scare", False):
    #         base_p4_suffix = pt_info.get("base_p4_suffix", "")
    #         # Check if ScaRe delta columns exist from friend trees
    #         deltas_up_exist = all(
    #             f"mu{mu_idx}_p4{base_p4_suffix}_ScaReUp_delta" in df.GetColumnNames()
    #             for mu_idx in [1, 2]
    #         )
    #         deltas_down_exist = all(
    #             f"mu{mu_idx}_p4{base_p4_suffix}_ScaReDown_delta" in df.GetColumnNames()
    #             for mu_idx in [1, 2]
    #         )

    #         if deltas_up_exist and deltas_down_exist:
    #             # Use deltas from friend trees
    #             for mu_idx in [1, 2]:
    #                 mu_pt_name = pt_info["pt_name_template"].format(mu_idx)
    #                 scare_unc_name = f"sigma_mu{mu_idx}_pt_scare_rel{pt_suffix}"
    #                 delta_up = f"mu{mu_idx}_p4{base_p4_suffix}_ScaReUp_delta"
    #                 delta_down = f"mu{mu_idx}_p4{base_p4_suffix}_ScaReDown_delta"
    #                 # Average of absolute deltas, relative to nominal pT
    #                 df = df.Define(
    #                     scare_unc_name,
    #                     f"(abs({delta_up}) + abs({delta_down})) / 2.0 / {mu_pt_name}",
    #                 )

    #             # Add ScaRe uncertainties in quadrature to base resolution
    #             resolution_expr = f"sqrt(0.5*(pow(sigma_mu1_pt_rel{pt_suffix},2) + pow(sigma_mu2_pt_rel{pt_suffix},2)) + 0.5*(pow(sigma_mu1_pt_scare_rel{pt_suffix},2) + pow(sigma_mu2_pt_scare_rel{pt_suffix},2)))"

    #     resolution_name = (
    #         f"m_mumu_resolution{pt_suffix}" if pt_suffix != "" else "m_mumu_resolution"
    #     )
    #     df = df.Define(resolution_name, resolution_expr)

    return df
