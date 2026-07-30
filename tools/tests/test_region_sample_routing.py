import unittest
from pathlib import Path

from common.region_sample_routing import (
    groups_for_region,
    jet_gen_component_processes,
    load_routing,
    separate_groups,
)


class RegionSampleRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_routing(
            Path(__file__).parents[2] / "config/histogram_sample_routing.yaml"
        )

    def test_signal_uses_mass_binned_groups(self):
        for era in ("Run3_2022", "Run3_2024", "Run3_2026"):
            self.assertEqual(
                groups_for_region(self.config, era, "Signal_Fit"),
                ("DY_amcatnlo_105_160", "EWK_105_160"),
            )

    def test_sidebands_use_generic_groups(self):
        self.assertEqual(
            groups_for_region(self.config, "Run3_2025", "Z_sideband"),
            ("DY_amcatnlo", "EWK"),
        )

    def test_dy_012j_is_always_separate(self):
        self.assertEqual(
            separate_groups(self.config, "Run3_2023"),
            ("DY_012J",),
        )

    def test_default_component_processes_include_dy_and_ewk(self):
        processes = jet_gen_component_processes(self.config)
        self.assertIn("DY", processes)
        self.assertIn("EWK", processes)


if __name__ == "__main__":
    unittest.main()
