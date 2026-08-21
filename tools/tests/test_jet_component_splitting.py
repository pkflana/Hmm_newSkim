import unittest

from common.jet_component_splitting import (
    DY_COMPONENT_FILE_LABELS,
    DY_JET_COMPONENTS,
    GGF_COMPONENT_VARIABLES,
    VBF_ETA_REGIONS,
    add_jet_component_categories,
    add_vbf_eta_region_categories,
    component_output_directory,
    define_jet_gen_matching,
    expanded_jet_component_categories,
    jet_components_enabled_for_dataset,
    pu_hard_component_style,
    variable_for_component,
    vbf_eta_region_expressions,
)
from test.rew_patch import dy_component_scale


class JetComponentSplittingTest(unittest.TestCase):
    def test_temporary_dy_component_plot_scales(self):
        self.assertEqual(
            dy_component_scale("DY_2J_Hard", "Run3_2022"), 0.845
        )
        self.assertEqual(
            dy_component_scale("DY_VBF_Hard", "Run3_2025"), 1.04
        )
        self.assertEqual(
            dy_component_scale("DY_1J_PU", "Run3_2023BPix"), 1.637
        )
        self.assertEqual(
            dy_component_scale("DY_2J_PU1", "Run3_2024"), 0.706
        )
        self.assertEqual(
            dy_component_scale("DY_VBF_PU2", "Run3_2025"), 0.354
        )
        self.assertEqual(
            dy_component_scale("DY_1J_Hard", "Run3_2024"), 1.0
        )
        self.assertEqual(
            dy_component_scale("DY_0J", "Run3_2024"), 1.0
        )
        self.assertEqual(
            dy_component_scale("EWK_VBF_Hard", "Run3_2024"), 1.0
        )
        self.assertEqual(
            dy_component_scale("DY_VBF_Hard", "Run3_2022_23"), 1.0
        )

    def test_dy_and_ewk_components_have_plot_styles(self):
        styles = {
            "DY": {"1J PU": "dy-blue"},
            "EWK": {"1J PU": "ewk-orange", "VBF Hard": "ewk-dark"},
        }
        dy_style = pu_hard_component_style(
            "DYto2Mu_MLL105To160_1J_PU", styles
        )
        ewk_style = pu_hard_component_style(
            "EWK_2Mu2J_MLL_105to160_herwig_1J_PU", styles
        )
        self.assertEqual(
            dy_style[:2],
            ("DY", "1J PU"),
        )
        self.assertEqual(
            pu_hard_component_style(
                "EWK_2Mu2J_MLL_105to160_herwig_VBF_Hard", styles
            )[:2],
            ("EWK", "VBF Hard"),
        )
        self.assertEqual(ewk_style[:2], ("EWK", "1J PU"))
        self.assertNotEqual(dy_style[2], ewk_style[2])
        self.assertIsNone(pu_hard_component_style("TT"))

    def test_pu_hard_component_layout_is_flat_without_eta_components(self):
        self.assertEqual(
            component_output_directory("Signal_Fit", "ggF"),
            "Signal_Fit_ggF",
        )
        self.assertEqual(
            component_output_directory("Signal_Fit", "VBF"),
            "Signal_Fit_VBF",
        )

    def test_eta_component_layout_is_nested_only_for_vbf(self):
        self.assertEqual(
            component_output_directory("Signal_Fit", "VBF", "CC"),
            "Signal_Fit_VBF/CC",
        )
        self.assertEqual(
            component_output_directory("Signal_Fit", "VBF", "incl"),
            "Signal_Fit_VBF/incl",
        )

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
        self.assertNotIn("VBF_Hard_CC", config["categories"])

    def test_vbf_component_eta_subregions_can_be_requested(self):
        config = add_jet_component_categories(
            {"categories": {}}, include_vbf_eta_regions=True
        )
        self.assertEqual(
            set(config["categories"]),
            set(expanded_jet_component_categories(include_vbf_eta_regions=True)),
        )
        self.assertIn("VBF_Hard_CC", config["categories"])
        self.assertIn("VBF_PU2_FF", config["categories"])

    def test_vbf_only_request_does_not_add_ggf_components(self):
        config = add_jet_component_categories(
            {"categories": {}}, requested_categories=["VBF"]
        )
        self.assertEqual(
            set(config["categories"]),
            set(expanded_jet_component_categories(requested_categories=["VBF"])),
        )
        self.assertEqual(
            set(config["categories"]),
            {"DY_inclusive_VBF_incl", "VBF_Hard_incl", "VBF_PU1_incl", "VBF_PU2_incl"},
        )

    def test_unrelated_requested_categories_are_kept_inclusive(self):
        expanded = expanded_jet_component_categories(
            requested_categories=["baseline", "ggF", "VBF"]
        )
        self.assertIn("baseline", expanded)
        self.assertIn("DY_inclusive_ggF", expanded)
        self.assertIn("DY_inclusive_VBF_incl", expanded)

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
        self.assertEqual(DY_COMPONENT_FILE_LABELS["VBF_Hard"], "DY_2J_Hard")
        self.assertEqual(DY_COMPONENT_FILE_LABELS["VBF_PU1"], "DY_2J_PU1")
        self.assertEqual(DY_COMPONENT_FILE_LABELS["VBF_PU2"], "DY_2J_PU2")

    def test_ggf_components_keep_all_requested_observables(self):
        for category, variable in GGF_COMPONENT_VARIABLES.items():
            self.assertEqual(
                variable_for_component(category, ["feature_a", "feature_b"]),
                ("feature_a", "feature_b", variable),
            )

    def test_vbf_components_keep_requested_observables(self):
        self.assertEqual(
            variable_for_component("VBF_PU1_CC", ["m_mumu", "DNN_NNOutput"]),
            ("m_mumu", "DNN_NNOutput"),
        )

    def test_generic_reco_gen_flags_are_declared(self):
        class FakeDataFrame:
            def __init__(self):
                self.columns = {
                    "SelectedJet_idx",
                    "SelectedJet_genJetIdx",
                    "N_SelectedJets",
                    "HasVBF",
                    "VBFJetIdx_1",
                    "VBFJetIdx_2",
                }

            def GetColumnNames(self):
                return self.columns

            def Define(self, name, expression):
                self.columns.add(name)
                return self

        dataframe = define_jet_gen_matching(FakeDataFrame(), {""})
        for count in (0, 1, 2):
            self.assertIn(f"RecoGenJetMatch_{count}J", dataframe.columns)

    def test_campaign_group_aliases_select_the_expected_datasets(self):
        allowed = [
            "DY_amcatnlo",
            "DY_amcatnlo_105_160",
            "EWK",
            "EWK_105_160",
            "signals",
        ]
        cases = [
            ("DYto2L_M_50_amcatnloFXFX", "DY", False),
            (
                "DYto2Mu_MLL_105to160_amcatnloFXFX",
                "DYto2Mu_MLL105To160",
                False,
            ),
            ("EWK_2L2J_madgraph_herwig", "EWK", False),
            (
                "EWK_2Mu2J_MLL_105to160_herwig",
                "EWK_2Mu2J_MLL_105to160_herwig",
                False,
            ),
            ("GluGluHto2Mu", "GluGluHto2Mu", True),
        ]
        for dataset, process, is_signal in cases:
            self.assertTrue(
                jet_components_enabled_for_dataset(
                    allowed, dataset, process, is_signal=is_signal
                )
            )

    def test_unlisted_background_is_not_split(self):
        self.assertFalse(
            jet_components_enabled_for_dataset(
                ["DY_amcatnlo", "signals"],
                "TTto2L2Nu",
                "TT",
                is_signal=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
