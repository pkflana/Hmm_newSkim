import unittest

from common.jet_component_splitting import (
    DY_COMPONENT_FILE_LABELS,
    DY_JET_COMPONENTS,
    GGF_COMPONENT_VARIABLES,
    VBF_ETA_REGIONS,
    add_jet_component_categories,
    add_vbf_eta_region_categories,
    expanded_jet_component_categories,
    variable_for_component,
    vbf_eta_region_expressions,
)


class JetComponentSplittingTest(unittest.TestCase):
    def test_component_categories_are_complete_and_exclusive_by_name(self):
        config = add_jet_component_categories({"categories": {}})
        self.assertEqual(
            set(config["categories"]),
            set(expanded_jet_component_categories()),
        )
        self.assertIn(
            "N_PU_FirstTwoJets{jet_suff} == 2",
            config["categories"]["ggF_2J_PU2"]["expression"],
        )
        self.assertIn(
            "N_PU_VBFJets{jet_suff} == 0",
            config["categories"]["VBF_Hard_incl"]["expression"],
        )

    def test_vbf_eta_regions_use_the_requested_boundary(self):
        regions = vbf_eta_region_expressions("VBF{tot_suff}")
        self.assertEqual(set(regions), set(VBF_ETA_REGIONS))
        self.assertIn("< 2.5", regions["CC"])
        self.assertIn("!(", regions["CF"])
        self.assertIn("!(", regions["FF"])

    def test_vbf_eta_categories_are_independent_of_dy_components(self):
        config = add_vbf_eta_region_categories({"categories": {"VBF": {}}})
        self.assertIn("VBF", config["categories"])
        self.assertEqual(
            {
                name
                for name in config["categories"]
                if name.startswith("VBF_eta_")
            },
            {f"VBF_eta_{region}" for region in VBF_ETA_REGIONS},
        )

    def test_every_component_has_a_separate_file_label(self):
        self.assertEqual(set(DY_COMPONENT_FILE_LABELS), set(DY_JET_COMPONENTS))
        self.assertEqual(DY_COMPONENT_FILE_LABELS["ggF_0J_Hard"], "DY_0J")

    def test_ggf_components_select_the_prescribed_observable(self):
        for category, variable in GGF_COMPONENT_VARIABLES.items():
            self.assertEqual(
                variable_for_component(category, ["unused"]),
                (variable,),
            )

    def test_vbf_components_keep_requested_observables(self):
        self.assertEqual(
            variable_for_component("VBF_PU1_CC", ["m_mumu", "DNN_NNOutput"]),
            ("m_mumu", "DNN_NNOutput"),
        )


if __name__ == "__main__":
    unittest.main()
