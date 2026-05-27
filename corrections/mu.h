#pragma once

#include <string>
#include <iostream>

namespace correction {

    // A simple, clean stateless evaluator function
    inline double getMuonSF_simple(
        const std::string& cset_key,
        const std::string& systematic, // "nominal", "systup", or "systdown"
        float pt,
        float eta,
        float pfRelIso04_all,
        bool tightId,
        float tkRelIso,
        // bool highPtId,
        bool mediumId,
        bool looseId,
        bool trg_matching,
        bool trg_path
    ) {

        auto correction_worker = cset->at(cset_key);

        // 3. Keep your custom object selection gating if needed.
        // This ensures you only apply corrections where the object passes the selection.
        const bool LooseIso = (pfRelIso04_all < 0.25);
        const bool MediumIso = (pfRelIso04_all < 0.2);
        const bool TightIso = (pfRelIso04_all < 0.15);
        const bool LooseRelTrkIso = (tkRelIso < 0.25);
        const bool MediumRelTrkIso = (tkRelIso < 0.2);
        const bool TightRelTrkIso = (tkRelIso < 0.15);


        // ======================
        // RECO
        // ======================
        if (cset_key=="NUM_TrackerMuons_DEN_genTracks")
            return 1.0;

        if (cset_key=="NUM_GlobalMuons_DEN_genTracks")
            return 1.0;

        // ======================
        // ID (genTracks / TrackerMuons)
        // ======================
        if (cset_key=="NUM_LooseID_DEN_genTracks" && looseId)
            return 1.0;
        if (cset_key=="NUM_LooseID_DEN_TrackerMuons" && looseId)
            return 1.0;

        if (cset_key=="NUM_MediumID_DEN_genTracks" && mediumId)
            return 1.0;
        if (cset_key=="NUM_MediumID_DEN_TrackerMuons" && mediumId)
            return 1.0;

        if (cset_key=="NUM_MediumPromptID_DEN_genTracks" && mediumId)
            return 1.0;
        if (cset_key=="NUM_MediumPromptID_DEN_TrackerMuons" && mediumId)
            return 1.0;

        if (cset_key=="NUM_TightID_DEN_genTracks" && tightId)
            return 1.0;
        if (cset_key=="NUM_TightID_DEN_TrackerMuons" && tightId)
            return 1.0;

        if (cset_key=="NUM_SoftID_DEN_genTracks")
            return 1.0;
        if (cset_key=="NUM_SoftID_DEN_TrackerMuons")
            return 1.0;

        // if (cset_key=="NUM_HighPtID_DEN_genTracks" && highPtId)
        //     return 1.0;
        // if (cset_key=="NUM_HighPtID_DEN_TrackerMuons" && highPtId)
        //     return 1.0;

        // if (cset_key=="NUM_TrkHighPtID_DEN_genTracks" && highPtId)
        //     return 1.0;
        // if (cset_key=="NUM_TrkHighPtID_DEN_TrackerMuons" && highPtId)
        //     return 1.0;

        // ======================
        // ISO – PF
        // ======================
        if (cset_key=="NUM_LoosePFIso_DEN_LooseID" && LooseIso && looseId)
            return 1.0;
        if (cset_key=="NUM_LoosePFIso_DEN_MediumID" && LooseIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_LoosePFIso_DEN_MediumPromptID" && LooseIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_LoosePFIso_DEN_TightID" && LooseIso && tightId)
            return 1.0;

        if (cset_key=="NUM_TightPFIso_DEN_MediumID" && TightIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_TightPFIso_DEN_MediumPromptID" && TightIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_TightPFIso_DEN_TightID" && TightIso && tightId)
            return 1.0;

        // ======================
        // ISO – MiniIso --> to change the Iso
        // ======================
        if (cset_key=="NUM_LooseMiniIso_DEN_LooseID" && looseId)
            return 1.0;
        if (cset_key=="NUM_LooseMiniIso_DEN_MediumID" && mediumId)
            return 1.0;
        if (cset_key=="NUM_MediumMiniIso_DEN_MediumID" && mediumId)
            return 1.0;
        if (cset_key=="NUM_TightMiniIso_DEN_MediumID" && mediumId)
            return 1.0;

        // ======================
        // ISO – RelIso (PF + tk)
        // ======================

        if (cset_key=="NUM_LooseRelIso_DEN_LooseID" && LooseIso && looseId)
            return 1.0;
        if (cset_key=="NUM_LooseRelIso_DEN_MediumID" && LooseIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_LooseRelIso_DEN_MediumPromptID" && LooseIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_LooseRelIso_DEN_TightIDandIPCut" && LooseIso && tightId)
            return 1.0;

        if (cset_key=="NUM_TightRelIso_DEN_MediumID" && TightIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_TightRelIso_DEN_MediumPromptID" && TightIso && mediumId)
            return 1.0;
        if (cset_key=="NUM_TightRelIso_DEN_TightIDandIPCut" && TightIso && tightId)
            return 1.0;

        if (cset_key =="NUM_IsoMu24_DEN_CutBasedIdMedium_and_PFIsoMedium" && (mediumId || looseId) && (LooseIso || MediumIso) && trg_matching && trg_path)
            return 1.0;
        if (cset_key =="NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight" && tightId && TightIso && trg_matching && trg_path)
            return 1.0;

        // if (cset_key=="NUM_LooseRelTkIso_DEN_HighPtID" && LooseRelTrkIso && highPtId)
        //     return 1.0;
        // if (cset_key=="NUM_LooseRelTkIso_DEN_TrkHighPtID" && LooseRelTrkIso && highPtId)
        //     return 1.0;

        // if (cset_key=="NUM_TightRelTkIso_DEN_HighPtID" && TightRelTrkIso && highPtId)
        //     return 1.0;
        // if (cset_key=="NUM_TightRelTkIso_DEN_HighPtIDandIPCut" && TightRelTrkIso && highPtId)
        //     return 1.0;
        // if (cset_key=="NUM_TightRelTkIso_DEN_TrkHighPtIDandIPCut" && TightRelTrkIso && highPtId)
        //     return 1.0;

        try {
            return correction_worker->evaluate({systematic, eta, pt});
        }
        catch (const std::exception& e) {
            // Gracefully catch out-of-bounds kinematics (e.g., pT under/overflow limits)
            return 1.0;
        }
    }
}