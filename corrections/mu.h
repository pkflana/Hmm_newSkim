#pragma once

#include "correction.h"
#include "corrections.h"

namespace correction {

    class MuCorrProvider : public CorrectionsBase<MuCorrProvider> {
      public:
        enum class UncSource : int {
            Central = -1,
            NUM_GlobalMuons_DEN_genTracks = 0,
            NUM_HighPtID_DEN_genTracks = 1,
            NUM_HighPtID_DEN_TrackerMuons = 2,
            NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight = 3,
            NUM_LooseID_DEN_genTracks = 4,
            NUM_LooseID_DEN_TrackerMuons = 5,
            NUM_LooseRelIso_DEN_LooseID = 6,
            NUM_LooseRelIso_DEN_MediumID = 7,
            NUM_LooseRelIso_DEN_MediumPromptID = 8,
            NUM_LooseRelIso_DEN_TightIDandIPCut = 9,
            NUM_LooseRelTkIso_DEN_HighPtIDandIPCut = 10,
            NUM_LooseRelTkIso_DEN_TrkHighPtIDandIPCut = 11,
            NUM_MediumID_DEN_genTracks = 12,
            NUM_MediumID_DEN_TrackerMuons = 13,
            NUM_MediumPromptID_DEN_genTracks = 14,
            NUM_MediumPromptID_DEN_TrackerMuons = 15,
            NUM_Mu50_or_OldMu100_or_TkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose = 16,
            NUM_SoftID_DEN_genTracks = 17,
            NUM_SoftID_DEN_TrackerMuons = 18,
            NUM_TightID_DEN_genTracks = 19,
            NUM_TightID_DEN_TrackerMuons = 20,
            NUM_TightRelIso_DEN_MediumID = 21,
            NUM_TightRelIso_DEN_MediumPromptID = 22,
            NUM_TightRelIso_DEN_TightIDandIPCut = 23,
            NUM_TightRelTkIso_DEN_HighPtIDandIPCut = 24,
            NUM_TightRelTkIso_DEN_TrkHighPtIDandIPCut = 25,
            NUM_TrackerMuons_DEN_genTracks = 26,
            NUM_TrkHighPtID_DEN_genTracks = 27,
            NUM_TrkHighPtID_DEN_TrackerMuons = 28,
            NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight = 29,
            NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight = 30,
            NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium = 31,
            NUM_LoosePFIso_DEN_TightID = 32,
            NUM_LoosePFIso_DEN_MediumID = 33,
            NUM_LoosePFIso_DEN_LooseID = 34,
            NUM_LoosePFIso_DEN_MediumPromptID = 35,
            NUM_LooseRelTkIso_DEN_HighPtID = 36,
            NUM_LooseRelTkIso_DEN_TrkHighPtID = 37,
            NUM_TightPFIso_DEN_MediumID = 38,
            NUM_TightPFIso_DEN_MediumPromptID = 39,
            NUM_TightPFIso_DEN_TightID = 40,
            NUM_LooseMiniIso_DEN_LooseID = 41,
            NUM_LooseMiniIso_DEN_MediumID = 42,
            NUM_MediumMiniIso_DEN_MediumID = 43,
            NUM_TightMiniIso_DEN_MediumID = 44,
            NUM_Mu50_or_TkMu50_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose = 45,
            NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose = 46,
            NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdMedium_and_PFIsoMedium = 47,
            NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTight_and_PFIsoTight = 48,
            NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose = 49,
            NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose = 50,
            NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose = 51,
            NUM_TightRelTkIso_DEN_HighPtID = 52,
            NUM_TightRelTkIso_DEN_TrkHighPtID = 53,
        };

        static const std::map<WorkingPointsMuonID, std::string>& getWPID() {
            static const std::map<WorkingPointsMuonID, std::string> names = {
                {WorkingPointsMuonID::HighPtID, "HighPtID"},
                {WorkingPointsMuonID::LooseID, "LooseID"},
                {WorkingPointsMuonID::MediumID, "MediumID"},
                {WorkingPointsMuonID::MediumPromptID, "MediumPromptID"},
                {WorkingPointsMuonID::SoftID, "SoftID"},
                {WorkingPointsMuonID::TightID, "TightID"},
                {WorkingPointsMuonID::TrkHighPtID, "TrkHighPtID"},
            };
            return names;
        };

        static const std::string& getScaleStr(UncScale scale) {
            static const std::map<UncScale, std::string> names = {
                {UncScale::Down, "systdown"},
                {UncScale::Central, "nominal"},
                {UncScale::Up, "systup"},
            };
            return names.at(scale);
        }

        static bool sourceApplies(UncSource source,
                          const float Muon_pfRelIso04_all,
                          const bool  Muon_TightId,
                          const float muon_Pt,
                          const float Muon_tkRelIso,
                          const bool  Muon_highPtId,
                          const bool  Muon_MediumId,
                          const bool  Muon_LooseId) {

            const bool Muon_LooseIso = (Muon_pfRelIso04_all < 0.25);
            const bool Muon_MediumIso = (Muon_pfRelIso04_all < 0.2);
            const bool Muon_TightIso = (Muon_pfRelIso04_all < 0.15);
            const bool Muon_LooseRelTrkIso = (Muon_tkRelIso < 0.25);
            const bool Muon_MediumRelTrkIso = (Muon_tkRelIso < 0.2);
            const bool Muon_TightRelTrkIso = (Muon_tkRelIso < 0.15);
            // ======================
            // RECO
            // ======================
            if (source == UncSource::NUM_TrackerMuons_DEN_genTracks)
                return true;

            if (source == UncSource::NUM_GlobalMuons_DEN_genTracks)
                return true;

            // ======================
            // ID (genTracks / TrackerMuons)
            // ======================
            if (source == UncSource::NUM_LooseID_DEN_genTracks && Muon_LooseId)
                return true;
            if (source == UncSource::NUM_LooseID_DEN_TrackerMuons && Muon_LooseId)
                return true;

            if (source == UncSource::NUM_MediumID_DEN_genTracks && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_MediumID_DEN_TrackerMuons && Muon_MediumId)
                return true;

            if (source == UncSource::NUM_MediumPromptID_DEN_genTracks && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_MediumPromptID_DEN_TrackerMuons && Muon_MediumId)
                return true;

            if (source == UncSource::NUM_TightID_DEN_genTracks && Muon_TightId)
                return true;
            if (source == UncSource::NUM_TightID_DEN_TrackerMuons && Muon_TightId)
                return true;

            if (source == UncSource::NUM_SoftID_DEN_genTracks)
                return true;
            if (source == UncSource::NUM_SoftID_DEN_TrackerMuons)
                return true;

            if (source == UncSource::NUM_HighPtID_DEN_genTracks && Muon_highPtId)
                return true;
            if (source == UncSource::NUM_HighPtID_DEN_TrackerMuons && Muon_highPtId)
                return true;

            if (source == UncSource::NUM_TrkHighPtID_DEN_genTracks && Muon_highPtId)
                return true;
            if (source == UncSource::NUM_TrkHighPtID_DEN_TrackerMuons && Muon_highPtId)
                return true;

            // ======================
            // ISO – PF
            // ======================
            if (source == UncSource::NUM_LoosePFIso_DEN_LooseID && Muon_LooseIso && Muon_LooseId)
                return true;
            if (source == UncSource::NUM_LoosePFIso_DEN_MediumID && Muon_LooseIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_LoosePFIso_DEN_MediumPromptID && Muon_LooseIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_LoosePFIso_DEN_TightID && Muon_LooseIso && Muon_TightId)
                return true;

            if (source == UncSource::NUM_TightPFIso_DEN_MediumID && Muon_TightIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_TightPFIso_DEN_MediumPromptID && Muon_TightIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_TightPFIso_DEN_TightID && Muon_TightIso && Muon_TightId)
                return true;

            // ======================
            // ISO – MiniIso --> to change the Iso
            // ======================
            if (source == UncSource::NUM_LooseMiniIso_DEN_LooseID && Muon_LooseId)
                return true;
            if (source == UncSource::NUM_LooseMiniIso_DEN_MediumID && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_MediumMiniIso_DEN_MediumID && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_TightMiniIso_DEN_MediumID && Muon_MediumId)
                return true;

            // ======================
            // ISO – RelIso (PF + tk)
            // ======================

            if (source == UncSource::NUM_LooseRelIso_DEN_LooseID && Muon_LooseIso && Muon_LooseId)
                return true;
            if (source == UncSource::NUM_LooseRelIso_DEN_MediumID && Muon_LooseIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_LooseRelIso_DEN_MediumPromptID && Muon_LooseIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_LooseRelIso_DEN_TightIDandIPCut && Muon_LooseIso && Muon_TightId)
                return true;

            if (source == UncSource::NUM_TightRelIso_DEN_MediumID && Muon_TightIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_TightRelIso_DEN_MediumPromptID && Muon_TightIso && Muon_MediumId)
                return true;
            if (source == UncSource::NUM_TightRelIso_DEN_TightIDandIPCut && Muon_TightIso && Muon_TightId)
                return true;

            if (source == UncSource::NUM_LooseRelTkIso_DEN_HighPtID && Muon_LooseRelTrkIso && Muon_highPtId)
                return true;
            if (source == UncSource::NUM_LooseRelTkIso_DEN_TrkHighPtID && Muon_LooseRelTrkIso && Muon_highPtId)
                return true;

            if (source == UncSource::NUM_TightRelTkIso_DEN_HighPtID && Muon_TightRelTrkIso && Muon_highPtId)
                return true;
            if (source == UncSource::NUM_TightRelTkIso_DEN_HighPtIDandIPCut && Muon_TightRelTrkIso && Muon_highPtId)
                return true;
            if (source == UncSource::NUM_TightRelTkIso_DEN_TrkHighPtIDandIPCut && Muon_TightRelTrkIso && Muon_highPtId)
                return true;

            // ======================
            // TRIGGER
            // ======================
            return false;
        }
        // NOTE: Maintenance considerations (tracked externally in the issue tracker):
        // 1. Consider adding miniIso to the infos.
        // 2. Consider cleaning up or splitting Run2-specific parts.
        // 3. Consider propagating any changes also to the soft and high-pT muons.
        // 4. Review the map between corrections_ and the actual evaluation to clarify its purpose.

        MuCorrProvider(const std::string& fileName, const std::string& era)
            : corrections_(CorrectionSet::from_file(fileName)) {
            /*
        Eventually we want to switch this interface with a map and a loop
        map < era -> set<string>
        dict = {
            era: [list of silly names]
        }

        for sillyname in dict[era]:
            muIDCorr[sillyname] = corrections_->at[sillyname]
        */

            if (era == "Run2_2016" || era == "Run2_2016_HIPM" || era == "Run2_2017" || era == "Run2_2018") {
                muIDCorrections["NUM_TrackerMuons_DEN_genTracks"] = corrections_->at("NUM_TrackerMuons_DEN_genTracks");
                muIDCorrections["NUM_TightID_DEN_TrackerMuons"] = corrections_->at("NUM_TightID_DEN_TrackerMuons");
                muIDCorrections["NUM_TightID_DEN_genTracks"] = corrections_->at("NUM_TightID_DEN_genTracks");
                muIDCorrections["NUM_HighPtID_DEN_TrackerMuons"] = corrections_->at("NUM_HighPtID_DEN_TrackerMuons");
                muIDCorrections["NUM_HighPtID_DEN_genTracks"] = corrections_->at("NUM_HighPtID_DEN_genTracks");
                muIDCorrections["NUM_TightRelIso_DEN_TightIDandIPCut"] =
                    corrections_->at("NUM_TightRelIso_DEN_TightIDandIPCut");
                muIDCorrections["NUM_TightRelTkIso_DEN_TrkHighPtIDandIPCut"] =
                    corrections_->at("NUM_TightRelTkIso_DEN_TrkHighPtIDandIPCut");
            }
            if (era == "Run2_2018") {
                muIDCorrections["NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight"] =
                    corrections_->at("NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight");
            }
            if (era == "Run2_2017") {
                muIDCorrections["NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight"] =
                    corrections_->at("NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight");
            }
            if ((era == "Run2_2016_HIPM") || (era == "Run2_2016")) {
                muIDCorrections["NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight"] =
                    corrections_->at("NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight");
            }
            if (era == "Run3_2022" || era == "Run3_2022EE" || era == "Run3_2023" || era == "Run3_2023BPix") {
                muIDCorrections["NUM_TightID_DEN_TrackerMuons"] = corrections_->at("NUM_TightID_DEN_TrackerMuons");
                muIDCorrections["NUM_LoosePFIso_DEN_TightID"] = corrections_->at("NUM_LoosePFIso_DEN_TightID");
                muIDCorrections["NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight"] =
                    corrections_->at("NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight");

                muIDCorrections["NUM_MediumID_DEN_TrackerMuons"] = corrections_->at("NUM_MediumID_DEN_TrackerMuons");
                muIDCorrections["NUM_LoosePFIso_DEN_MediumID"] = corrections_->at("NUM_LoosePFIso_DEN_MediumID");
                muIDCorrections["NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium"] =
                    corrections_->at("NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium");
            }
        }
        // float getMuonSFMedium(const LorentzVectorM & muon_p4, const float Muon_pfRelIso04_all, const bool Muon_MediumId, UncSource source, UncScale scale) const {
        //     const UncScale muID_scale = sourceAppliesMedium(source, Muon_pfRelIso04_all,  muon_p4.Pt(), Muon_MediumId) ? scale : UncScale::Central;
        //     const std::string& scale_str = getScaleStr(muID_scale);
        //     return source == UncSource::Central ? 1. : muIDCorrections.at(getUncSourceName(source))->evaluate({abs(muon_p4.Eta()),muon_p4.Pt(), scale_str}) ;
        // }

        float getMuonSF(const LorentzVectorM& muon_p4,
                        const float Muon_pfRelIso04_all,
                        const bool Muon_TightId,
                        const float Muon_tkRelIso,
                        const bool Muon_highPtId,
                        const bool Muon_MediumId,
                        const bool Muon_LooseId,
                        UncSource source,
                        UncScale scale) const {
            const UncScale muID_scale =
                sourceApplies(
                    source, Muon_pfRelIso04_all, Muon_TightId, muon_p4.Pt(), Muon_tkRelIso, Muon_highPtId, Muon_MediumId, Muon_LooseId)
                    ? scale
                    : UncScale::Central;
            const std::string& scale_str = getScaleStr(muID_scale);
            if (source == UncSource::NUM_TrackerMuons_DEN_genTracks) {
                //const std::string& reco_scale_str = scale==UncScale::Central ? "nominal" : scale_str;
                return (muon_p4.Pt() >= 10 && muon_p4.Pt() < 200)
                           ? muIDCorrections.at(getUncSourceName(source))->evaluate({abs(muon_p4.Eta()), 50., scale_str})
                           : 1.;
            }
            static const double pt_low = 15.0;
            const double muon_pt = std::max(pt_low, muon_p4.pt());
            const float corr_SF =
                corrections_->at(getUncSourceName(source))->evaluate({abs(muon_p4.Eta()), muon_pt, scale_str});
            return source == UncSource::Central ? 1. : corr_SF;
        }
        //Check range, but if it is out of range it is still valid and return 1.
        //Read json for bounds, min/max to be within, use that value
        //If its out of range return a bool as well
      private:
        static const std::map<float, std::set<std::pair<float, float>>>& getRecoSFMap() {
            static const std::map<float, std::set<std::pair<float, float>>> RecoSFMap = {
                {50., {std::pair<float, float>(1.6, 0.9943), std::pair<float, float>(2.4, 1.0)}},
                {100., {std::pair<float, float>(1.6, 0.9948), std::pair<float, float>(2.4, 0.993)}},
                {150., {std::pair<float, float>(1.6, 0.9950), std::pair<float, float>(2.4, 0.990)}},
                {200., {std::pair<float, float>(1.6, 0.994), std::pair<float, float>(2.4, 0.988)}},
                {300., {std::pair<float, float>(1.6, 0.9914), std::pair<float, float>(2.4, 0.981)}},
                {400., {std::pair<float, float>(1.6, 0.993), std::pair<float, float>(2.4, 0.983)}},
                {600., {std::pair<float, float>(1.6, 0.991), std::pair<float, float>(2.4, 0.978)}},
                {1500., {std::pair<float, float>(1.6, 1.0), std::pair<float, float>(2.4, 0.98)}},
            };
            return RecoSFMap;
        }
        static std::string& getUncSourceName(UncSource source) {
            static std::string k = "Central";

            if (source == UncSource::NUM_GlobalMuons_DEN_genTracks)
                k = "NUM_GlobalMuons_DEN_genTracks";
            if (source == UncSource::NUM_HighPtID_DEN_genTracks)
                k = "NUM_HighPtID_DEN_genTracks";
            if (source == UncSource::NUM_HighPtID_DEN_TrackerMuons)
                k = "NUM_HighPtID_DEN_TrackerMuons";

            if (source == UncSource::NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight)
                k = "NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight";
            if (source == UncSource::NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium)
                k = "NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium";
            if (source == UncSource::NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight)
                k = "NUM_IsoMu27_DEN_CutBasedIdTight_and_PFIsoTight";
            if (source == UncSource::NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight)
                k = "NUM_IsoMu24_or_IsoTkMu24_DEN_CutBasedIdTight_and_PFIsoTight";

            if (source == UncSource::NUM_LooseID_DEN_genTracks)
                k = "NUM_LooseID_DEN_genTracks";
            if (source == UncSource::NUM_LooseID_DEN_TrackerMuons)
                k = "NUM_LooseID_DEN_TrackerMuons";

            if (source == UncSource::NUM_MediumID_DEN_genTracks)
                k = "NUM_MediumID_DEN_genTracks";
            if (source == UncSource::NUM_MediumID_DEN_TrackerMuons)
                k = "NUM_MediumID_DEN_TrackerMuons";
            if (source == UncSource::NUM_MediumPromptID_DEN_genTracks)
                k = "NUM_MediumPromptID_DEN_genTracks";
            if (source == UncSource::NUM_MediumPromptID_DEN_TrackerMuons)
                k = "NUM_MediumPromptID_DEN_TrackerMuons";

            if (source == UncSource::NUM_SoftID_DEN_genTracks)
                k = "NUM_SoftID_DEN_genTracks";
            if (source == UncSource::NUM_SoftID_DEN_TrackerMuons)
                k = "NUM_SoftID_DEN_TrackerMuons";

            if (source == UncSource::NUM_TightID_DEN_genTracks)
                k = "NUM_TightID_DEN_genTracks";
            if (source == UncSource::NUM_TightID_DEN_TrackerMuons)
                k = "NUM_TightID_DEN_TrackerMuons";

            if (source == UncSource::NUM_HighPtID_DEN_TrackerMuons)
                k = "NUM_HighPtID_DEN_TrackerMuons";
            if (source == UncSource::NUM_TrkHighPtID_DEN_genTracks)
                k = "NUM_TrkHighPtID_DEN_genTracks";
            if (source == UncSource::NUM_TrkHighPtID_DEN_TrackerMuons)
                k = "NUM_TrkHighPtID_DEN_TrackerMuons";

            if (source == UncSource::NUM_TrackerMuons_DEN_genTracks)
                k = "NUM_TrackerMuons_DEN_genTracks";

            // ===== Isolation =====
            if (source == UncSource::NUM_LooseRelIso_DEN_LooseID)
                k = "NUM_LooseRelIso_DEN_LooseID";
            if (source == UncSource::NUM_LooseRelIso_DEN_MediumID)
                k = "NUM_LooseRelIso_DEN_MediumID";
            if (source == UncSource::NUM_LooseRelIso_DEN_MediumPromptID)
                k = "NUM_LooseRelIso_DEN_MediumPromptID";
            if (source == UncSource::NUM_LooseRelIso_DEN_TightIDandIPCut)
                k = "NUM_LooseRelIso_DEN_TightIDandIPCut";

            if (source == UncSource::NUM_LooseRelTkIso_DEN_HighPtID)
                k = "NUM_LooseRelTkIso_DEN_HighPtID";
            if (source == UncSource::NUM_LooseRelTkIso_DEN_TrkHighPtID)
                k = "NUM_LooseRelTkIso_DEN_TrkHighPtID";
            if (source == UncSource::NUM_LooseRelTkIso_DEN_HighPtIDandIPCut)
                k = "NUM_LooseRelTkIso_DEN_HighPtIDandIPCut";
            if (source == UncSource::NUM_LooseRelTkIso_DEN_TrkHighPtIDandIPCut)
                k = "NUM_LooseRelTkIso_DEN_TrkHighPtIDandIPCut";

            if (source == UncSource::NUM_LoosePFIso_DEN_LooseID)
                k = "NUM_LoosePFIso_DEN_LooseID";
            if (source == UncSource::NUM_LoosePFIso_DEN_MediumID)
                k = "NUM_LoosePFIso_DEN_MediumID";
            if (source == UncSource::NUM_LoosePFIso_DEN_MediumPromptID)
                k = "NUM_LoosePFIso_DEN_MediumPromptID";
            if (source == UncSource::NUM_LoosePFIso_DEN_TightID)
                k = "NUM_LoosePFIso_DEN_TightID";

            if (source == UncSource::NUM_TightPFIso_DEN_MediumID)
                k = "NUM_TightPFIso_DEN_MediumID";
            if (source == UncSource::NUM_TightPFIso_DEN_MediumPromptID)
                k = "NUM_TightPFIso_DEN_MediumPromptID";
            if (source == UncSource::NUM_TightPFIso_DEN_TightID)
                k = "NUM_TightPFIso_DEN_TightID";

            if (source == UncSource::NUM_LooseMiniIso_DEN_LooseID)
                k = "NUM_LooseMiniIso_DEN_LooseID";
            if (source == UncSource::NUM_LooseMiniIso_DEN_MediumID)
                k = "NUM_LooseMiniIso_DEN_MediumID";
            if (source == UncSource::NUM_MediumMiniIso_DEN_MediumID)
                k = "NUM_MediumMiniIso_DEN_MediumID";
            if (source == UncSource::NUM_TightMiniIso_DEN_MediumID)
                k = "NUM_TightMiniIso_DEN_MediumID";

            // ===== Triggers high-pT =====
            if (source == UncSource::NUM_Mu50_or_OldMu100_or_TkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose)
                k = "NUM_Mu50_or_OldMu100_or_TkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose";
            if (source == UncSource::NUM_Mu50_or_TkMu50_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose)
                k = "NUM_Mu50_or_TkMu50_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose";

            if (source == UncSource::NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose)
                k = "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose";
            if (source == UncSource::NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdMedium_and_PFIsoMedium)
                k = "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdMedium_and_PFIsoMedium";
            if (source == UncSource::NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTight_and_PFIsoTight)
                k = "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTight_and_PFIsoTight";
            if (source == UncSource::NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose)
                k = "NUM_IsoMu24_or_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose";

            if (source == UncSource::NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose)
                k = "NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdGlobalHighPt_and_TkIsoLoose";
            if (source == UncSource::NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose)
                k = "NUM_Mu50_or_CascadeMu100_or_HighPtTkMu100_DEN_CutBasedIdTrkHighPt_and_TkIsoLoose";

            if (source == UncSource::NUM_TightRelIso_DEN_MediumID)
                k = "NUM_TightRelIso_DEN_MediumID";
            if (source == UncSource::NUM_TightRelIso_DEN_MediumPromptID)
                k = "NUM_TightRelIso_DEN_MediumPromptID";
            if (source == UncSource::NUM_TightRelIso_DEN_TightIDandIPCut)
                k = "NUM_TightRelIso_DEN_TightIDandIPCut";
            return k;
        }


      private:
        std::unique_ptr<CorrectionSet> corrections_;
        std::map<std::string, Correction::Ref> muIDCorrections;
    };
}