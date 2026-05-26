import ROOT 
def GetMuonP4Observables(df):
    for pt_suffix in [
        "",
        "_bsc_scare",
        "_nano_scare",
        "_nano",
        "_bsConstrainedPt",
    ]:
        for mu_idx in [1, 2]:
            mu_pt_name = (
                f"mu{mu_idx}_pt{pt_suffix}"
                if pt_suffix != "_bsConstrainedPt"
                else f"mu{mu_idx}{pt_suffix}"
            )
            if f"mu{mu_idx}_p4{pt_suffix}" in df.GetColumnNames():
                continue
            if mu_pt_name not in df.GetColumnNames():
                continue
            df = df.Define(
                f"mu{mu_idx}_p4{pt_suffix}",
                f"ROOT::Math::LorentzVector<ROOT::Math::PtEtaPhiM4D<double>>({mu_pt_name},mu{mu_idx}_eta,mu{mu_idx}_phi,mu{mu_idx}_mass)",
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
    for pt_suffix in [
        "_nano",
        "_bsConstrainedPt",
        "",  # should be same than bsc_scare
        "_bsc_scare",
        "_nano_scare",
        "_FSR_nano_scare",
        "_FSR_bsc_scare",
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
            if pt_suffix == "":
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
    for mu_idx in [1, 2]:
        df = df.Define(
            f"mu{mu_idx}_p4_noCorr",
            f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_bsConstrainedPt : mu{mu_idx}_p4_nano",
        )
        df = df.Define(
            f"mu{mu_idx}_p4_ScaRe",
            f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_bsc_scare : mu{mu_idx}_p4_nano_scare",
        )
        df = df.Define(
            f"mu{mu_idx}_p4_ScaRe_FSR",
            f"mu{mu_idx}_bsConstrainedChi2 < 30 ? mu{mu_idx}_p4_FSR_bsc_scare : mu{mu_idx}_p4_FSR_nano_scare",
        )
    for newsuff in ["noCorr", "ScaRe", "ScaRe_FSR"]:
        df = df.Define(f"mu1_pt_{newsuff}", f"mu1_p4_{newsuff}.pt()")
        df = df.Define(f"mu2_pt_{newsuff}", f"mu2_p4_{newsuff}.pt()")
        p4_dimu_system = f"(mu1_p4_{newsuff}+mu2_p4_{newsuff})"
        p4_dimu_system_list = [f"mu1_p4_{newsuff}", f"mu2_p4_{newsuff}"]
        for obs, expr in dimu_obs.items():
            df = df.Define(
                f"{obs}_{newsuff}",
                expr.format(
                    dimu=p4_dimu_system,
                    mu1p4=p4_dimu_system_list[0],
                    mu2p4=p4_dimu_system_list[1],
                    suff=f"_{newsuff}",
                ),
            )
        df = df.Define(
            f"mu1_pt_rel_{newsuff}", f"mu1_p4_{newsuff}.pt()/m_mumu_{newsuff}"
        )
        df = df.Define(
            f"mu2_pt_rel_{newsuff}", f"mu2_p4_{newsuff}.pt()/m_mumu_{newsuff}"
        )

    pt_variants = {
        "_nano": {
            "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
            "pt_name_template": "mu{0}_pt_nano",
            "has_scare": False,
        },
        "_nano_scare": {
            "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
            "pt_name_template": "mu{0}_pt_nano_scare",
            "has_scare": True,
            "base_p4_suffix": "_nano",
        },
        "_nano_scare_FSR": {
            "pt_err_template": "mu{0}_ptErr/mu{0}_pt",
            "pt_name_template": "mu{0}_pt_nano_scare_FSR",
            "has_scare": True,
            "base_p4_suffix": "_FSR_nano",
        },
        "_bsConstrainedPt": {
            "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
            "pt_name_template": "mu{0}_bsConstrainedPt",
            "has_scare": False,
        },
        "_bsc_scare": {
            "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
            "pt_name_template": "mu{0}_pt_bsc_scare",
            "has_scare": True,
            "base_p4_suffix": "_bsConstrainedPt",
        },
        "": {
            "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
            "pt_name_template": "mu{0}_pt_bsc_scare",
            "has_scare": True,
            "base_p4_suffix": "_bsConstrainedPt",
        },
        "_bsc_scare_FSR": {
            "pt_err_template": "mu{0}_bsConstrainedPtErr/mu{0}_bsConstrainedPt",
            "pt_name_template": "mu{0}_pt_bsc_scare_FSR",
            "has_scare": True,
            "base_p4_suffix": "_FSR_bsConstrainedPt",
        },
    }

    for pt_suffix, pt_info in pt_variants.items():
        # Check if both muons have the required pT columns
        mu1_pt_name = pt_info["pt_name_template"].format(1)
        mu2_pt_name = pt_info["pt_name_template"].format(2)

        if (
            mu1_pt_name not in df.GetColumnNames()
            or mu2_pt_name not in df.GetColumnNames()
        ):
            continue

        # Calculate relative pT errors for each muon
        for mu_idx in [1, 2]:
            sigma_expr = pt_info["pt_err_template"].format(mu_idx)
            df = df.Define(f"sigma_mu{mu_idx}_pt_rel{pt_suffix}", sigma_expr)

        # Calculate m_mumu_resolution including ScaRe uncertainties
        # Base resolution from pT errors: Δm_μμ^rel = sqrt(1/2 * ((Δpt(u1)/pt(u1))^2 + (Δpt(u2)/pt(u2))^2))
        resolution_expr = f"sqrt(0.5*(pow(sigma_mu1_pt_rel{pt_suffix},2) + pow(sigma_mu2_pt_rel{pt_suffix},2)))"

        # Handle ScaRe uncertainties if present
        if pt_info.get("has_scare", False):
            base_p4_suffix = pt_info.get("base_p4_suffix", "")
            # Check if ScaRe delta columns exist from friend trees
            deltas_up_exist = all(
                f"mu{mu_idx}_p4{base_p4_suffix}_ScaReUp_delta" in df.GetColumnNames()
                for mu_idx in [1, 2]
            )
            deltas_down_exist = all(
                f"mu{mu_idx}_p4{base_p4_suffix}_ScaReDown_delta" in df.GetColumnNames()
                for mu_idx in [1, 2]
            )

            if deltas_up_exist and deltas_down_exist:
                # Use deltas from friend trees
                for mu_idx in [1, 2]:
                    mu_pt_name = pt_info["pt_name_template"].format(mu_idx)
                    scare_unc_name = f"sigma_mu{mu_idx}_pt_scare_rel{pt_suffix}"
                    delta_up = f"mu{mu_idx}_p4{base_p4_suffix}_ScaReUp_delta"
                    delta_down = f"mu{mu_idx}_p4{base_p4_suffix}_ScaReDown_delta"
                    # Average of absolute deltas, relative to nominal pT
                    df = df.Define(
                        scare_unc_name,
                        f"(abs({delta_up}) + abs({delta_down})) / 2.0 / {mu_pt_name}",
                    )

                # Add ScaRe uncertainties in quadrature to base resolution
                resolution_expr = f"sqrt(0.5*(pow(sigma_mu1_pt_rel{pt_suffix},2) + pow(sigma_mu2_pt_rel{pt_suffix},2)) + 0.5*(pow(sigma_mu1_pt_scare_rel{pt_suffix},2) + pow(sigma_mu2_pt_scare_rel{pt_suffix},2)))"

        resolution_name = (
            f"m_mumu_resolution{pt_suffix}" if pt_suffix != "" else "m_mumu_resolution"
        )
        df = df.Define(resolution_name, resolution_expr)

    return df


def LeptonsSelection(df):
    ### muon selection: pt > 15 GeV, abs(eta) < 2.4, medium ID, loose PF Iso ###
    df = df.Define(
        "Muon_acceptanceSel",
        "Muon_pt_corr > 15 && abs(Muon_eta) < 2.4",
    )
    df = df.Define(
        "Muon_idIsoSel",
        "Muon_mediumId && Muon_pfIsoId >= 2",
    )
    df = df.Define("Muon_selectedIdx", "Muon_idx[Muon_acceptanceSel && Muon_idIsoSel]")
    df = df.Filter("Muon_selectedIdx.size()==2", "n_muons=2")
    df = df.Define(
        "Muon_selectedIdxSorted",
        """
                    auto indices = Muon_selectedIdx;
                    if(Muon_pt_corr[indices[1]].pt() > Muon_pt_corr[indices[0]].pt())
                        std::swap(indices[0], indices[1]);
                    return indices; """,
    )
    df = df.Define("mu1_idx", "Muon_selectedIdxSorted[0]")
    df = df.Define("mu2_idx", "Muon_selectedIdxSorted[1]")

    # df = df.Filter("Muon_charge[mu1_idx]*Muon_charge[mu2_idx]<0", "OS muons") # this filter can be applied later too.

    ### electron veto ###
    df = df.Define(
        "Electron_B0_veto",
        "Electron_pt > 20 && abs(Electron_eta) < 2.5  && Electron_mvaIso_WP90",
    )
    # && abs(Electron_dz) < 0.2 && abs(Electron_dxy) < 0.024 --> to add?
    df = df.Filter("Electron_idx[Electron_B0_veto].size() == 0", "No extra electrons")
    return df


def DiMuonMassCut(df, p4_cols=["p4"], cut_value=50):
    for p4_col in p4_cols:
        df = df.Define(f"m_mumu_{p4_col}", f"(mu1_{p4_col}+mu2_{p4_col}).M()")
    masses_cut = ""
    if len(p4_cols) > 1:
        masses_cut = " || ".join(
            [f"m_mumu_{p4_col} > {cut_value}" for p4_col in p4_cols]
        )
    elif len(p4_cols) == 1:
        masses_cut = f"m_mumu_{p4_cols[0]} > {cut_value}"
    df = df.Filter(masses_cut, masses_cut)
    return df
