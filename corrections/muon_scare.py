#!/usr/bin/env python3
import os
import ROOT
from .general import pog_folder_names,period_names
import correctionlib

correctionlib.register_pyroot_binding()

def apply_muon_scare(
    df,
    config,
    dataset_cfg,
    return_variations=True,
):
    era = config.get("era")
    period_unc = period_names[era]
    folder_name = pog_folder_names["MUO"][period_unc]
    jsonFile_path = f"corrections/data/MUO/MuonScaRe/{folder_name}/muon_scalesmearing.json"
    jsonFile_path_VXBS = f"corrections/data/MUO/MuonScaRe/{folder_name}/muon_scalesmearing_VXBS.json"

    ## first on raw nano pT

    ROOT.gROOT.ProcessLine(
        f'auto cset = correction::CorrectionSet::from_file("{jsonFile_path}");'
    )
    ROOT.gROOT.ProcessLine(
        f'auto cset_vxbs = correction::CorrectionSet::from_file("{jsonFile_path_VXBS}");'
    )

    headers_dir = os.path.dirname(os.path.abspath(__file__))
    header_path = os.path.join(headers_dir, "MuonScaRe.cc")
    ROOT.gInterpreter.Declare(f'#include "{header_path}"')

    # CENTRAL - Scale (both data and MC)
    df = df.Define(
        'Muon_pt_scale_corr',
        f'''
        ROOT::VecOps::RVec<float> Muon_pt_scale_corr(Muon_pt.size());
        for(size_t Muon_pt_idx = 0 ; Muon_pt_idx < Muon_pt.size(); Muon_pt_idx ++ ){{
            Muon_pt_scale_corr[Muon_pt_idx] = pt_scale(is_data_int, Muon_pt[Muon_pt_idx], Muon_eta[Muon_pt_idx], Muon_phi[Muon_pt_idx], Muon_charge[Muon_pt_idx], false);
        }}
        return Muon_pt_scale_corr;

        '''
    )


    # CENTRAL - Resol (only MC) on top of Scale

    if not dataset_cfg.get("is_data", False):
        df = df.Define(
            'Muon_pt_corr',
            f'''
            ROOT::VecOps::RVec<float> Muon_pt_corr(Muon_pt.size());
            for(size_t Muon_pt_idx = 0 ; Muon_pt_idx < Muon_pt.size(); Muon_pt_idx ++ ){{
                Muon_pt_corr[Muon_pt_idx] = pt_resol(Muon_pt_scale_corr[Muon_pt_idx], Muon_eta[Muon_pt_idx], Muon_phi[Muon_pt_idx], float(Muon_nTrackerLayers[Muon_pt_idx]), event, luminosityBlock, false);
            }}
            return Muon_pt_corr;

            '''
        )
    else:
        df = df.Define('Muon_pt_corr',"Muon_pt_scale_corr")

    # UP/DOWN - Scale, then Resol (only MC)
    if not dataset_cfg.get("is_data", False) and return_variations:
        df = df.Define(
            'Muon_pt_scale_corr_up',
            f'''
            ROOT::VecOps::RVec<float> Muon_pt_scale_corr_up(Muon_pt.size());
            for(size_t Muon_pt_idx = 0 ; Muon_pt_idx < Muon_pt.size(); Muon_pt_idx ++ ){{
                Muon_pt_scale_corr_up[Muon_pt_idx] = pt_scale_var(Muon_pt_corr[Muon_pt_idx], Muon_eta[Muon_pt_idx], Muon_phi[Muon_pt_idx], Muon_charge[Muon_pt_idx], "up", false);
            }}
            return Muon_pt_scale_corr_up;
            '''
        )
        df = df.Define(
            'Muon_pt_scale_corr_down',
            f'''
            ROOT::VecOps::RVec<float> Muon_pt_scale_corr_down(Muon_pt.size());
            for(size_t Muon_pt_idx = 0 ; Muon_pt_idx < Muon_pt.size(); Muon_pt_idx ++ ){{
                Muon_pt_scale_corr_down[Muon_pt_idx] = pt_scale_var(Muon_pt_corr[Muon_pt_idx], Muon_eta[Muon_pt_idx], Muon_phi[Muon_pt_idx], Muon_charge[Muon_pt_idx], "down", false);
            }}
            return Muon_pt_scale_corr_down;
            '''
        )

        df = df.Define(
                "Muon_pt_corr_resol_up",
                f'''
                    ROOT::VecOps::RVec<float> Muon_pt_corr_resol_up(Muon_pt.size());
                    for(size_t Muon_pt_idx = 0 ; Muon_pt_idx < Muon_pt.size(); Muon_pt_idx ++ ){{
                        Muon_pt_corr_resol_up[Muon_pt_idx] = pt_resol_var(Muon_pt_scale_corr[Muon_pt_idx], Muon_pt_corr[Muon_pt_idx], Muon_eta[Muon_pt_idx], "up", false);
                    }}
                    return Muon_pt_corr_resol_up;
                '''
        )

        df = df.Define(
                "Muon_pt_corr_resol_down",
                f'''
                    ROOT::VecOps::RVec<float> Muon_pt_corr_resol_down(Muon_pt.size());
                    for(size_t Muon_pt_idx = 0 ; Muon_pt_idx < Muon_pt.size(); Muon_pt_idx ++ ){{
                        Muon_pt_corr_resol_down[Muon_pt_idx] =  pt_resol_var(Muon_pt_scale_corr[Muon_pt_idx], Muon_pt_corr[Muon_pt_idx], Muon_eta[Muon_pt_idx], "dn", false);
                    }}
                    return Muon_pt_corr_resol_down;
                '''
        )

    ## then on bsc pT

    # CENTRAL - Scale (both data and MC)
    df = df.Define(
        'Muon_bsc_pt_scale_corr',
        f'''
        ROOT::VecOps::RVec<float> Muon_bsc_pt_scale_corr(Muon_bsConstrainedPt.size());
        for(size_t Muon_bsc_pt_idx = 0 ; Muon_bsc_pt_idx < Muon_bsConstrainedPt.size(); Muon_bsc_pt_idx ++ ){{
            Muon_bsc_pt_scale_corr[Muon_bsc_pt_idx] = pt_scale(is_data_int, Muon_bsConstrainedPt[Muon_bsc_pt_idx], Muon_eta[Muon_bsc_pt_idx], Muon_phi[Muon_bsc_pt_idx], Muon_charge[Muon_bsc_pt_idx], true);
        }}
        return Muon_bsc_pt_scale_corr;

        '''
    )

    # CENTRAL - Resol (only MC) on top of Scale

    if not dataset_cfg.get("is_data", False):
        df = df.Define(
            'Muon_bsc_pt_corr',
            f'''
            ROOT::VecOps::RVec<float> Muon_bsc_pt_corr(Muon_bsConstrainedPt.size());
            for(size_t Muon_bsc_pt_idx = 0 ; Muon_bsc_pt_idx < Muon_bsConstrainedPt.size(); Muon_bsc_pt_idx ++ ){{
                Muon_bsc_pt_corr[Muon_bsc_pt_idx] = pt_resol(Muon_bsc_pt_scale_corr[Muon_bsc_pt_idx], Muon_eta[Muon_bsc_pt_idx], Muon_phi[Muon_bsc_pt_idx], float(Muon_nTrackerLayers[Muon_bsc_pt_idx]), event, luminosityBlock, true);
            }}
            return Muon_bsc_pt_corr;

            '''
        )
    else:
        df = df.Define('Muon_bsc_pt_corr',"Muon_bsc_pt_scale_corr")

    # UP/DOWN - Scale, then Resol (only MC)
    if not dataset_cfg.get("is_data", False):
        df = df.Define(
            'Muon_bsc_pt_scale_corr_up',
            f'''
            ROOT::VecOps::RVec<float> Muon_bsc_pt_scale_corr_up(Muon_bsConstrainedPt.size());
            for(size_t Muon_bsc_pt_idx = 0 ; Muon_bsc_pt_idx < Muon_bsConstrainedPt.size(); Muon_bsc_pt_idx ++ ){{
                Muon_bsc_pt_scale_corr_up[Muon_bsc_pt_idx] = pt_scale_var(Muon_bsc_pt_corr[Muon_bsc_pt_idx], Muon_eta[Muon_bsc_pt_idx], Muon_phi[Muon_bsc_pt_idx], Muon_charge[Muon_bsc_pt_idx], "up", true);
            }}
            return Muon_bsc_pt_scale_corr_up;
            '''
        )
        df = df.Define(
            'Muon_bsc_pt_scale_corr_down',
            f'''
            ROOT::VecOps::RVec<float> Muon_bsc_pt_scale_corr_down(Muon_bsConstrainedPt.size());
            for(size_t Muon_bsc_pt_idx = 0 ; Muon_bsc_pt_idx < Muon_bsConstrainedPt.size(); Muon_bsc_pt_idx ++ ){{
                Muon_bsc_pt_scale_corr_down[Muon_bsc_pt_idx] = pt_scale_var(Muon_bsc_pt_corr[Muon_bsc_pt_idx], Muon_eta[Muon_bsc_pt_idx], Muon_phi[Muon_bsc_pt_idx], Muon_charge[Muon_bsc_pt_idx], "down", true);
            }}
            return Muon_bsc_pt_scale_corr_down;
            '''
        )

        df = df.Define(
                "Muon_bsc_pt_corr_resol_up",
                f'''
                    ROOT::VecOps::RVec<float> Muon_bsc_pt_corr_resol_up(Muon_bsConstrainedPt.size());
                    for(size_t Muon_bsc_pt_idx = 0 ; Muon_bsc_pt_idx < Muon_bsConstrainedPt.size(); Muon_bsc_pt_idx ++ ){{
                        Muon_bsc_pt_corr_resol_up[Muon_bsc_pt_idx] = pt_resol_var(Muon_bsc_pt_scale_corr[Muon_bsc_pt_idx], Muon_bsc_pt_corr[Muon_bsc_pt_idx], Muon_eta[Muon_bsc_pt_idx], "up", true);
                    }}
                    return Muon_bsc_pt_corr_resol_up;
                '''
        )

        df = df.Define(
                "Muon_bsc_pt_corr_resol_down",
                f'''
                    ROOT::VecOps::RVec<float> Muon_bsc_pt_corr_resol_down(Muon_bsConstrainedPt.size());
                    for(size_t Muon_bsc_pt_idx = 0 ; Muon_bsc_pt_idx < Muon_bsConstrainedPt.size(); Muon_bsc_pt_idx ++ ){{
                        Muon_bsc_pt_corr_resol_down[Muon_bsc_pt_idx] = pt_resol_var(Muon_bsc_pt_scale_corr[Muon_bsc_pt_idx], Muon_bsc_pt_corr[Muon_bsc_pt_idx], Muon_eta[Muon_bsc_pt_idx], "dn", true);
                    }}
                    return Muon_bsc_pt_corr_resol_down;
                '''
        )
    return df