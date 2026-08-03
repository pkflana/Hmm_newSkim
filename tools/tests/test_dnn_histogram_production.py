import unittest

from histograms.dnn_histogram_production import (
    needs_sideband_mass_shift,
    shifted_output_column,
    sideband_mass_expression,
)


class DNNHistogramProductionTest(unittest.TestCase):
    def test_only_dnn_output_is_shifted_in_supported_sidebands(self):
        self.assertTrue(needs_sideband_mass_shift("Z_sideband", "DNN_NNOutput"))
        self.assertTrue(needs_sideband_mass_shift("H_sideband", "DNN_NNOutput"))
        self.assertFalse(needs_sideband_mass_shift("H_peak", "DNN_NNOutput"))
        self.assertFalse(needs_sideband_mass_shift("Z_sideband", "m_mumu"))

    def test_shifted_columns_match_payload_names(self):
        self.assertEqual(
            shifted_output_column("Z_sideband"),
            "DNNZSidebandMassShift_NNOutput",
        )
        self.assertEqual(
            shifted_output_column("H_sideband"),
            "DNNHSidebandMassShift_NNOutput",
        )

    def test_unknown_region_is_rejected(self):
        with self.assertRaises(ValueError):
            sideband_mass_expression("unknown")


if __name__ == "__main__":
    unittest.main()
