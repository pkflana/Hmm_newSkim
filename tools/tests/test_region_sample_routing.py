import unittest
from pathlib import Path

from common.dataset_utilities import (
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


def test_h_sideband_routes_like_signal():
    config = load_routing(Path(__file__).parents[2] / 'config/histogram_sample_routing.yaml')
    for era in ('Run3_2022', 'Run3_2024', 'Run3_2026'):
        assert groups_for_region(config, era, 'H_sideband') == groups_for_region(config, era, 'Signal_Fit')


def test_fullsim_and_flashsim_mass_windows():
    from common.dataset_utilities import dataset_region_allowed
    for prefix in ('DYto2Mu_', 'EWK_2Mu2J_'):
        for suffix in ('', '_Flashsim_New'):
            restricted = prefix + 'MLL_105to160' + suffix
            inclusive = prefix + 'MLL50' + suffix
            for region in ('Signal_Fit', 'H_sideband'):
                assert dataset_region_allowed(restricted, region)
                assert not dataset_region_allowed(inclusive, region)
            for region in ('Z_sideband', 'mass_inclusive'):
                assert not dataset_region_allowed(restricted, region)
                assert dataset_region_allowed(inclusive, region)


def test_signals_only_nominal_125_and_flashsim():
    from common.dataset_utilities import production_samples
    root = Path(__file__).parents[2]
    for era in ('Run3_2022', 'Run3_2024', 'Run3_2025'):
        samples = production_samples(root, era, 'signals')
        assert 'GluGluHto2Mu' in samples
        assert 'GluGluHto2Mu_amcatnlo' in samples
        assert any('VBF' in s and 'powheg' in s for s in samples)
        assert not any(any(x in s.lower() for x in ('120','130','tune','minnlo')) for s in samples)
    assert 'VBFHto2Mu_m125_Flashsim' in production_samples(root, 'Run3_2024', 'signals')
