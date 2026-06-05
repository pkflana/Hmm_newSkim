#pragma once

#include "correction.h"
#include "corrections.h"

namespace correction {
    class JetCorrectionProvider : public CorrectionsBase<JetCorrectionProvider> {
      public:
        enum class UncSource : int {
            Central = -1,
            JER = 0,
            Total = 1,
            RelativeBal = 2,
            HF = 3,
            BBEC1 = 4,
            EC2 = 5,
            Absolute = 6,
            FlavorQCD = 7,
            BBEC1_year = 8,
            Absolute_year = 9,
            EC2_year = 10,
            HF_year = 11,
            RelativeSample_year = 12
        };

        // json_file_name - path to json file with corrections
        // e.g. /cvmfs/cms-griddata.cern.ch/cat/metadata/JME/2022_Summer2022/jet_jerc.json.gz

        // jecTag_corrName_algoType

        // jec_tag - a string describing when sample was produced and type of sample
        // e.g. Summer22_22Sep2023_V2_MC

        // algo - type of jet algorithm
        // e.g. AK4PFPuppi
        JetCorrectionProvider(std::string const& json_file_name,
                              std::string const& jetsmear_file_name,
                              std::string const& jec_tag,
                              std::string const& other_jec_tag,
                              std::string const& jer_tag,
                              std::string const& algo,
                              std::string const& year,
                              bool is_data,
                              bool use_regrouped,
                              bool use_cmpd_jec)
            : corrset_(CorrectionSet::from_file(json_file_name)),
              jersmear_corr_(CorrectionSet::from_file(jetsmear_file_name)->at("JERSmear")),
              corr_jer_sf_(corrset_->at(jer_tag + "_ScaleFactor_" + algo)),
              corr_jer_sf_shifted_(corrset_->at(jer_tag + "_SFUncertainty_" + algo)),
              corr_jer_res_(corrset_->at(jer_tag + "_PtResolution_" + algo)),
              cmpd_corr_(corrset_->compound().at(other_jec_tag + "_L1L2L3Res_" + algo)),
              corr_l1_(corrset_->at(other_jec_tag + "_L1FastJet_" + algo)),
              corr_l2_(corrset_->at(other_jec_tag + "_L2Relative_" + algo)),
              corr_l2l3res_(corrset_->at(other_jec_tag + "_L2L3Residual_" + algo)),
              is_data_(is_data),
              year_(year),
              use_cmpd_jec_(use_cmpd_jec) {
            // map with uncertainty sources should only be filled for MC
            std::cout << "JetCorrectionProvider: init" << std::endl;
            if (!is_data_) {
                auto const& unc_map_ref = use_regrouped ? unc_map_regrouped : unc_map_total;
                for (auto const& [unc_source, unc_name] : unc_map_ref) {
                    std::string full_name = jec_tag;
                    full_name += '_';
                    full_name += unc_name;
                    full_name += '_';
                    if (year_dep_map.at(unc_source)) {
                        full_name += year;
                        full_name += '_';
                    }
                    full_name += algo;
                    unc_map_[unc_source] = full_name;
                }
            }
        }

        float evaluateJECCompound(float pt_raw,
                       float eta,
                       float phi,
                       float area,
                       float rho,
                       unsigned int run,
                       bool require_run_number,
                       bool wantPhi) const {
            float sf = 1.0;

            if (require_run_number) {
                if (wantPhi) {
                    sf = cmpd_corr_->evaluate({area, eta, pt_raw, rho, phi, (float)run});
                } else {
                    sf = cmpd_corr_->evaluate({area, eta, pt_raw, rho, (float)run});
                }
            } else {
                if (wantPhi) {
                    sf = cmpd_corr_->evaluate({area, eta, pt_raw, rho, phi});
                } else {
                    sf = cmpd_corr_->evaluate({area, eta, pt_raw, rho});
                }
            }

            return sf;
        }

        float evaluateJECSeparately(float pt_raw,
                                         float eta,
                                         float phi,
                                         float area,
                                         float rho,
                                         unsigned int run,
                                         bool require_run_number,
                                         bool wantPhi,
                                         bool isdata_,
                                        bool is2024Eta2To2p5) const {

            if (pt_raw <= 0.0) return 1.0;

            float pt_after = pt_raw;

            // 2) L1FastJet
            float c1 = corr_l1_->evaluate({area, eta, pt_after, rho});
            pt_after *= c1;

            // 3) L2Relative
            float c2 = 1.0;
            if (wantPhi) {
                c2 = corr_l2_->evaluate({eta, phi, pt_after});
            } else {
                c2 = corr_l2_->evaluate({eta, pt_after});
            }
            pt_after *= c2;

            // add L3 --> it's always 1

            // 4) Residual (solo data)
            // For MC-truth corrected pT < 30 GeV use L2L3Residual correction factor of MC-truth corrected pT = 30 GeV in 2.0 < |eta| < 2.5

            float cRes = 1.0;
            float pt_for_corr = pt_after;
            if (isdata_){
                if(is2024Eta2To2p5 and pt_after < 30. ){
                    pt_for_corr = 30.;
                }
                if (require_run_number) {
                    cRes = corr_l2l3res_->evaluate({float(run),eta,pt_for_corr});
                } else {
                    cRes = corr_l2l3res_->evaluate({eta,pt_for_corr});
                }
            }

            pt_after *= cRes;


            return pt_after / pt_raw ;
        }



        std::size_t findGenMatch(
        const double pt, const float eta, const float phi,
        const std::size_t genJetIdx, const ROOT::VecOps::RVec<float>& gen_pt,
        const ROOT::VecOps::RVec<float>& gen_eta, const ROOT::VecOps::RVec<float>& gen_phi,
        const double resolution, const bool isAK4=true ) const
        {
            const float m_genMatch_dR2max = isAK4 ? 0.2*0.2 : 0.4*0.4; // half cone squared
            const float m_genMatch_dPtmax = 3; // 3 times the resolution
            auto get_dr2 = [](float phi, float eta, float gen_phi, float gen_eta) -> float {
                const auto dphi = ROOT::Math::VectorUtil::Phi_mpi_pi(gen_phi - phi);
                const auto deta = gen_eta - eta;
                return dphi*dphi + deta*deta;
            };
            auto check_resolution = [resolution, m_genMatch_dPtmax](float pt, float gen_pt) -> bool {
                return std::abs(gen_pt - pt) < m_genMatch_dPtmax*resolution;
            };

            // First check if matched genJet from NanoAOD is acceptable
            if (genJetIdx >= 0) {
                const float dr2 = get_dr2(phi, eta, gen_phi[genJetIdx], gen_eta[genJetIdx]);
                if ((dr2 < m_genMatch_dR2max) && check_resolution(pt, gen_pt[genJetIdx])) {
                    return genJetIdx;
                }
            }

            std::size_t igBest{gen_pt.size()};
            auto dr2Min = std::numeric_limits<float>::max();
            for ( std::size_t ig{0}; ig != gen_pt.size(); ++ig ) {
                const auto dr2 = get_dr2(phi, eta, gen_phi[ig], gen_eta[ig]);
                if ( ( dr2 < dr2Min ) && ( dr2 < m_genMatch_dR2max ) ) {
                    if (check_resolution(pt, gen_pt[ig])) {
                        dr2Min = dr2;
                        igBest = ig;
                    }
                }
            }
            return igBest;
        }



    std::map<std::pair<UncSource, UncScale>, RVecLV> getShiftedP4(
        const RVecF& Jet_pt,
        const RVecF& Jet_eta,
        const RVecF& Jet_phi,
        const RVecF& Jet_mass,
        const RVecF& Jet_rawFactor,
        const RVecF& Jet_area,
        const float rho,
        int event,
        bool apply_jer,
        bool reapply_jec,
        bool require_run_number,
        const unsigned int run,
        bool wantPhi,
        bool apply_forward_jet_horns_fix,
        const RVecF& GenJet_pt = {},
        const RVecF& GenJet_eta = {},
        const RVecF& GenJet_phi = {},
        const RVecI& Jet_genJetIdx = {}
    ) const
    {
        std::map<std::pair<UncSource, UncScale>, RVecLV> all_shifted_p4;

        const size_t sz = Jet_pt.size();

        std::vector<std::pair<UncSource, UncScale>> variations;

        variations.emplace_back(
            UncSource::Central,
            UncScale::Central
        );

        if (!is_data_) {

            for (const auto& unc_scale : {UncScale::up, UncScale::down}) {

                for (const auto& [unc_source, unc_name] : unc_map_) {

                    variations.emplace_back(
                        unc_source,
                        unc_scale
                    );
                }
            }
        }
        for (const auto& [unc_source, unc_scale] : variations) {

            RVecLV shifted_p4(sz);

            for (size_t i = 0; i < sz; ++i) {

                const float eta = Jet_eta[i];
                const float phi = Jet_phi[i];
                const float abs_eta = std::abs(eta);


                float corrected_pt = Jet_pt[i];
                float corrected_mass = Jet_mass[i];

                if (reapply_jec) {

                    const float raw_sf = 1.f - Jet_rawFactor[i];

                    const float pt_raw = Jet_pt[i] * raw_sf;
                    const float mass_raw = Jet_mass[i] * raw_sf;

                    const bool is2024Eta2To2p5 =
                        (year_ == "2024" &&
                        abs_eta > 2.f &&
                        abs_eta < 2.5f);

                    float jec_sf = 1.f;

                    if (use_cmpd_jec_ && !is2024Eta2To2p5) {

                        jec_sf = evaluateJECCompound(
                            pt_raw,
                            eta,
                            phi,
                            Jet_area[i],
                            rho,
                            run,
                            require_run_number,
                            wantPhi
                        );

                    } else {

                        jec_sf = evaluateJECSeparately(
                            pt_raw,
                            eta,
                            phi,
                            Jet_area[i],
                            rho,
                            run,
                            require_run_number,
                            wantPhi,
                            is_data_,
                            is2024Eta2To2p5
                        );
                    }

                    corrected_pt = pt_raw * jec_sf;
                    corrected_mass = mass_raw * jec_sf;
                }


                float jersmear_factor = 1.f;

                if (apply_jer && !is_data_) {


                    const float jer_pt_res =
                        corr_jer_res_->evaluate({
                            eta,
                            corrected_pt,
                            rho
                        });


                    float genjet_pt = -1.f;

                    if (!GenJet_pt.empty()) {
                        const size_t genJetIdx_nano_size = Jet_genJetIdx.size();
                        const size_t genJet_pt_size = GenJet_pt.size();
                        const size_t GenJet_size =(i < genJetIdx_nano_size && Jet_genJetIdx[i] >= 0) ? static_cast<size_t>(Jet_genJetIdx[i]) : genJet_pt_size;
                        const auto matched_idx = findGenMatch(
                            corrected_pt,
                            eta,
                            phi,
                            GenJet_size,
                            GenJet_pt,
                            GenJet_eta,
                            GenJet_phi,
                            jer_pt_res * corrected_pt
                        );

                        if (matched_idx < GenJet_pt.size()) {
                            genjet_pt = GenJet_pt[matched_idx];
                        }
                    }


                    // nominal
                    float jer_sf =
                        corr_jer_sf_->evaluate({
                            eta,
                            corrected_pt,
                        });

                    if (unc_source == UncSource::JER) {
                        float SF_unc = corr_jer_sf_->evaluate({
                            eta,
                            corrected_pt,
                        });
                        if (unc_scale == UncScale::up) {
                            // jer_tag = "up";
                            jer_sf *=(1+SF_unc);
                        }
                        else if (unc_scale == UncScale::down) {
                            // jer_tag = "down";
                            jer_sf *=(1-SF_unc);
                        }
                    }

                    jersmear_factor =
                        jersmear_corr_->evaluate({
                            corrected_pt,
                            eta,
                            genjet_pt,
                            rho,
                            event,
                            jer_pt_res,
                            jer_sf
                        });


                    const bool is_jet_in_horn =
                        (abs_eta > 2.5f &&
                        abs_eta < 3.f);

                    const bool has_gen_match =
                        (genjet_pt > 0.f);

                    if (
                        apply_forward_jet_horns_fix &&
                        is_jet_in_horn &&
                        !has_gen_match &&
                        year_ != "2025"
                    ) {
                        jersmear_factor = 1.f;
                    }

                    corrected_pt *= jersmear_factor;
                    corrected_mass *= jersmear_factor;
                }

                if (
                    unc_source != UncSource::Central &&
                    unc_source != UncSource::JER
                ) {

                    const auto corr =
                        corrset_->at(
                            unc_map_.at(unc_source)
                        );

                    const float unc =
                        corr->evaluate({
                            eta,
                            corrected_pt
                        });

                    const float sf =
                        1.f +
                        static_cast<int>(unc_scale) * unc;

                    corrected_pt *= sf;
                    corrected_mass *= sf;
                }

                shifted_p4[i] = LorentzVectorM(
                    corrected_pt,
                    eta,
                    phi,
                    corrected_mass
                );
            }

            all_shifted_p4.insert({
                {unc_source, unc_scale},
                shifted_p4
            });
        }

        return all_shifted_p4;
    }

      private:
        std::map<UncSource, std::string> unc_map_;
        std::unique_ptr<CorrectionSet> corrset_;
        Correction::Ref jersmear_corr_;  // aka shared_ptr<Correction const>, sizeof = 8
        Correction::Ref corr_l1_;
        Correction::Ref corr_l2_;
        Correction::Ref corr_l2l3res_;
        Correction::Ref corr_jer_sf_;
        Correction::Ref corr_jer_sf_shifted_;
        Correction::Ref corr_jer_res_;
        CompoundCorrection::Ref cmpd_corr_;
        bool is_data_;
        std::string year_;
        bool use_cmpd_jec_;

        inline static const std::map<UncSource, std::string> unc_map_total = {{UncSource::Total, "Total"},
                                                                              {UncSource::JER, "JER"}};

        inline static const std::map<UncSource, bool> year_dep_map = {{UncSource::Central, false},
                                                                      {UncSource::JER, false},
                                                                      {UncSource::Total, false},
                                                                      {UncSource::RelativeBal, false},
                                                                      {UncSource::HF, false},
                                                                      {UncSource::BBEC1, false},
                                                                      {UncSource::EC2, false},
                                                                      {UncSource::Absolute, false},
                                                                      {UncSource::FlavorQCD, false},
                                                                      {UncSource::BBEC1_year, true},
                                                                      {UncSource::Absolute_year, true},
                                                                      {UncSource::EC2_year, true},
                                                                      {UncSource::HF_year, true},
                                                                      {UncSource::RelativeSample_year, true}};

        inline static const std::map<UncSource, std::string> unc_map_regrouped = {
            {UncSource::JER, "JER"},
            {UncSource::RelativeBal, "Regrouped_RelativeBal"},
            {UncSource::HF, "Regrouped_HF"},
            {UncSource::BBEC1, "Regrouped_BBEC1"},
            {UncSource::EC2, "Regrouped_EC2"},
            {UncSource::Absolute, "Regrouped_Absolute"},
            {UncSource::FlavorQCD, "Regrouped_FlavorQCD"},
            {UncSource::BBEC1_year, "Regrouped_BBEC1"},
            {UncSource::Absolute_year, "Regrouped_Absolute"},
            {UncSource::EC2_year, "Regrouped_EC2"},
            {UncSource::HF_year, "Regrouped_RelativeStatHF"},
            {UncSource::RelativeSample_year, "Regrouped_RelativeSample"}};
    };

}  // namespace correction
