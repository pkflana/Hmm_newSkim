#pragma once

#include "correction.h"
#include "corrections.h"

namespace correction {
    class JetVetoMapProvider : public CorrectionsBase<JetVetoMapProvider> {
      public:
        JetVetoMapProvider(std::string const& fileName, std::string const& entry_name)
            : corrections_(CorrectionSet::from_file(fileName)) {
            std::cout << "JetVetoMapProvider: init" << std::endl;
            JetVetoMap_value = corrections_->at(entry_name);
        }
        RVecB GetJetVetoMapValues(const RVecLV& Jet_p4) const {
            // Non-zero value for (eta, phi) indicates that the region is vetoed. --> initialization with 0.
            RVecB veto_values(Jet_p4.size(), false);  // Default value is false (NO veto)
            for (int jet_idx = 0; jet_idx < Jet_p4.size(); jet_idx++) {
                float jvm_factor =
                    JetVetoMap_value->evaluate({"jetvetomap", Jet_p4[jet_idx].Eta(), Jet_p4[jet_idx].Phi()});
                veto_values[jet_idx] = static_cast<bool>(jvm_factor);  // Apply the correction factor
            }
            return veto_values;
        }

      private:
        std::unique_ptr<CorrectionSet> corrections_;
        Correction::Ref JetVetoMap_value;
    };

}  // namespace correction
