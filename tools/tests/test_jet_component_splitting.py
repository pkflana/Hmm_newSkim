import unittest

from common.jet_component_splitting import (
    DY_JET_COMPONENTS,
    GGF_COMPONENT_VARIABLES,
    add_jet_component_categories,
    variable_for_component,
)


class JetComponentSplittingTest(unittest.TestCase):
    def test_component_categories_are_complete_and_exclusive_by_name(self):
        config = add_jet_component_categories({"categories": {}})
        self.assertEqual(set(config["categories"]), set(DY_JET_COMPONENTS))
        self.assertIn(
            "N_PU_FirstTwoJets{jet_suff} == 2",
            config["categories"]["ggF_2J_PU2"]["expression"],
        )
        self.assertIn(
            "N_PU_VBFJets{jet_suff} == 0",
            config["categories"]["VBF_Hard"]["expression"],
        )

    def test_ggf_components_select_the_prescribed_observable(self):
        for category, variable in GGF_COMPONENT_VARIABLES.items():
            self.assertEqual(
                variable_for_component(category, ["unused"]),
                (variable,),
            )

    def test_vbf_components_keep_requested_observables(self):
        self.assertEqual(
            variable_for_component("VBF_PU1", ["m_mumu", "DNN_NNOutput"]),
            ("m_mumu", "DNN_NNOutput"),
        )


if __name__ == "__main__":
    unittest.main()
