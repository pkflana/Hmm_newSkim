import unittest

from common.add_vars_to_skim_tuples import DefineDimuonMassResolution


class FakeDataFrame:
    def __init__(self, columns):
        self.columns = set(columns)
        self.expressions = {}

    def GetColumnNames(self):
        return sorted(self.columns)

    def Define(self, name, expression):
        self.columns.add(name)
        self.expressions[name] = expression
        return self


class DimuonMassResolutionTest(unittest.TestCase):
    def test_detector_resolution_uses_selected_uncorrected_pt(self):
        dataframe = FakeDataFrame(
            {
                "mu1_pt_err",
                "mu2_pt_err",
                "mu1_pt",
                "mu2_pt",
                "mu1_pt_noCorr",
                "mu2_pt_noCorr",
                "m_mumu",
            }
        )

        result = DefineDimuonMassResolution(dataframe)

        self.assertIn("mu1_pt_noCorr", result.expressions["mu1_pt_resolution_rel"])
        self.assertIn("mu2_pt_noCorr", result.expressions["mu2_pt_resolution_rel"])
        self.assertIn("0.5", result.expressions["m_mumu_resolution"])
        self.assertIn("m_mumu_resolution_detector", result.columns)
        self.assertIn("m_mumu_resolution_abs", result.columns)

    def test_scale_and_resolution_systematics_stay_separate(self):
        dataframe = FakeDataFrame(
            {
                "m_mumu",
                "m_mumu_FSR_scale_up",
                "m_mumu_FSR_scale_down",
                "m_mumu_FSR_res_up",
                "m_mumu_FSR_res_down",
            }
        )

        result = DefineDimuonMassResolution(dataframe)

        self.assertIn("m_mumu_resolution_scale", result.columns)
        self.assertIn("m_mumu_resolution_res", result.columns)
        self.assertNotIn("m_mumu_resolution_total", result.columns)
        self.assertNotIn("m_mumu_resolution_detector", result.columns)

    def test_total_requires_and_combines_all_three_components(self):
        dataframe = FakeDataFrame(
            {
                "mu1_pt_err",
                "mu2_pt_err",
                "mu1_pt",
                "mu2_pt",
                "m_mumu",
                "m_mumu_FSR_scale_up",
                "m_mumu_FSR_scale_down",
                "m_mumu_FSR_res_up",
                "m_mumu_FSR_res_down",
            }
        )

        result = DefineDimuonMassResolution(dataframe)

        expression = result.expressions["m_mumu_resolution_total"]
        self.assertIn("m_mumu_resolution_detector", expression)
        self.assertIn("m_mumu_resolution_scale", expression)
        self.assertIn("m_mumu_resolution_res", expression)
        self.assertIn("m_mumu_resolution_total_abs", result.columns)

    def test_missing_inputs_are_skipped(self):
        dataframe = FakeDataFrame({"m_mumu"})

        result = DefineDimuonMassResolution(dataframe)

        self.assertEqual(result.expressions, {})


if __name__ == "__main__":
    unittest.main()
