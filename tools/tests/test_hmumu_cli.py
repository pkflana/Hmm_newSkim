import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "hmumu.py"
SPEC = importlib.util.spec_from_file_location("hmumu_cli", MODULE_PATH)
hmumu = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = hmumu
SPEC.loader.exec_module(hmumu)


class HmumuCliTest(unittest.TestCase):
    def request(self, **overrides):
        values = dict(
            eras=["2025"],
            systematics=["Central"],
            datasets=None,
            dataset_name="DYto2Mu_MLL_105to160_amcatnloFXFX",
            variables=["m_mumu"],
            regions=["Signal_Fit"],
            categories=["VBF"],
            input_dir="/input",
            manifests="/manifests",
            output_base="/output",
            output_dir=None,
            chunk_size=5,
            cores=1,
            retries=3,
            retry_delay=2,
            condor=False,
            missing_only=True,
            dry_run=True,
            execute=False,
            dy_jet_components=False,
            jet_component_processes=[],
            vbf_eta_regions=False,
            max_files=None,
            extra=[],
        )
        values.update(overrides)
        return hmumu.HistRequest(**values)

    def test_central_single_histogram_command(self):
        command = hmumu.histogram_command(self.request(), "2025", "Central")
        self.assertIn("histograms/scripts/hists.sh", command[1])
        self.assertEqual(command[command.index("--era") + 1], "Run3_2025")
        self.assertEqual(command[command.index("--dataset-name") + 1],
                         "DYto2Mu_MLL_105to160_amcatnloFXFX")
        self.assertEqual(command[command.index("--output-dir") + 1],
                         "/output/Hists_Central")
        separator = command.index("--")
        self.assertLess(command.index("--systematics"), separator)
        self.assertGreater(command.index("--variables"), separator)

    def test_shifted_uses_systematics_entry_point(self):
        request = self.request(systematics=["ScaRe"], condor=True)
        command = hmumu.histogram_command(request, "Run3_2024", "ScaRe")
        self.assertIn("histograms/scripts/systematics.sh", command[1])
        self.assertIn("--condor", command)

    def test_shifted_removes_explicit_data_group(self):
        request = self.request(
            systematics=["JERC"],
            dataset_name=None,
            datasets="data,signals,EWK",
        )
        command = hmumu.histogram_command(request, "2023", "JERC")
        self.assertEqual(command[command.index("--datasets") + 1], "signals,EWK")

    def test_shifted_rejects_explicit_data_dataset(self):
        request = self.request(
            systematics=["Muon"],
            dataset_name="Muon1_Run2023C_v1",
        )
        with self.assertRaisesRegex(ValueError, "cannot be run"):
            hmumu.histogram_command(request, "2023", "Muon")

    def test_central_keeps_explicit_data_group(self):
        request = self.request(
            dataset_name=None,
            datasets="data,signals",
        )
        command = hmumu.histogram_command(request, "2023", "Central")
        self.assertEqual(command[command.index("--datasets") + 1], "data,signals")

    def test_output_override_rejects_multiple_systematics(self):
        request = self.request(
            systematics=["Central", "Muon"],
            output_dir="/one-output",
        )
        with self.assertRaises(ValueError):
            hmumu.output_dir_for(request, "Central")

    def test_variable_finder_prioritizes_definition(self):
        matches = hmumu.variable_matches("FullEventId")
        self.assertTrue(matches)
        self.assertEqual(matches[0].kind, "definition")

    def test_ast_catalog_finds_multiline_and_dynamic_definitions(self):
        definitions = hmumu.discover_definitions(hmumu.REPO)
        producers = hmumu.definitions_for(definitions, "m_mumu")
        self.assertTrue(producers)
        self.assertTrue(
            any(item.producer == "GetAllMuonsObservablesNew" for item in producers)
        )

    def test_dy_jet_components_is_forwarded_to_hist_maker(self):
        request = self.request(dy_jet_components=True)
        command = hmumu.histogram_command(request, "2025", "Central")
        separator = command.index("--")
        self.assertGreater(command.index("--pu-hard-jet-components"), separator)

    def test_selected_pu_hard_processes_are_forwarded(self):
        request = self.request(
            dy_jet_components=True,
            jet_component_processes=["DY_amcatnlo_105_160", "EWK_105_160"],
        )
        command = hmumu.histogram_command(request, "2025", "Central")
        option = command.index("--pu-hard-processes")
        self.assertEqual(
            command[option + 1 : option + 3],
            ["DY_amcatnlo_105_160", "EWK_105_160"],
        )

    def test_vbf_eta_regions_is_forwarded_to_hist_maker(self):
        request = self.request(vbf_eta_regions=True)
        command = hmumu.histogram_command(request, "2025", "Central")
        separator = command.index("--")
        self.assertGreater(command.index("--eta-components"), separator)

    def test_one_file_limit_is_forwarded_after_separator(self):
        request = self.request(
            max_files=1,
            output_base=hmumu.DEFAULT_OUTPUT_BASE,
        )
        command = hmumu.histogram_command(request, "2025", "Central")
        separator = command.index("--")
        option = command.index("--max-files")
        self.assertGreater(option, separator)
        self.assertEqual(command[option + 1], "1")
        self.assertEqual(
            command[command.index("--output-dir") + 1],
            "/tmp/vdamante/hmumu_tests/Hists_Central",
        )

    def test_overwrite_is_forwarded_before_separator(self):
        command = hmumu.histogram_command(
            self.request(overwrite=True), "2025", "Central"
        )
        separator = command.index("--")
        self.assertIn("--erase-existing", command[:separator])
        self.assertNotIn("--erase-existing", command[separator:])

    def test_merge_eras_matches_files_by_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for era in ("Run3_2022", "Run3_2022EE"):
                directory = base / era
                directory.mkdir()
                (directory / "DY.root").write_bytes(b"ROOT")
            args = type("Args", (), {
                "input_dir": str(base),
                "eras": ["2022,2022EE"],
                "output_era": "2022_23",
                "execute": False,
                "force": True,
            })()
            with patch("builtins.print") as printer:
                self.assertEqual(hmumu.run_merge_eras(args), 0)
            output = "\n".join(str(call) for call in printer.call_args_list)
            self.assertIn("Run3_2022_23/DY.root", output)
            self.assertIn("Run3_2022/DY.root", output)
            self.assertIn("Run3_2022EE/DY.root", output)

    def test_systematic_directories_are_inferred_from_central(self):
        central = Path("/analysis/Hists_Central")
        self.assertEqual(
            hmumu.systematic_directory(central, "JERC"),
            Path("/analysis/Hists_JERC"),
        )

    def test_hadded_systematic_directories_are_inferred_from_central(self):
        central = Path("/analysis/Hists_Central_hadded")
        self.assertEqual(
            hmumu.systematic_directory(central, "JERC"),
            Path("/analysis/Hists_JERC_hadded"),
        )
        self.assertEqual(
            hmumu.systematic_directory(central, "Central"),
            central,
        )

    def test_root_discovery_ignores_temporary_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "Run3_2024").mkdir()
            (base / "Run3_2024" / "DY.root").write_bytes(b"ROOT")
            (base / "Run3_2024" / "DY_tmp").mkdir()
            (base / "Run3_2024" / "DY_tmp" / "chunk_1.root").write_bytes(b"ROOT")
            files = hmumu.root_files_by_relative_path(base)
            self.assertEqual(list(files), [Path("Run3_2024/DY.root")])

    def test_merge_systematics_can_filter_one_era(self):
        with tempfile.TemporaryDirectory() as tmp:
            central = Path(tmp) / "Hists_Central"
            for era in ("Run3_2022", "Run3_2023"):
                directory = central / era
                directory.mkdir(parents=True)
                (directory / "DY.root").write_bytes(b"ROOT")
            args = type("Args", (), {
                "central_dir": str(central),
                "systematics": ["Central"],
                "eras": ["2022"],
                "output_dir": None,
                "execute": False,
                "force": True,
            })()
            with patch("builtins.print") as printer:
                self.assertEqual(hmumu.run_merge_systematics(args), 0)
            output = "\n".join(str(call) for call in printer.call_args_list)
            self.assertIn("Run3_2022/DY.root", output)
            self.assertNotIn("Run3_2023/DY.root", output)

    def test_hadd_processes_infers_hadded_output(self):
        args = type("Args", (), {
            "input_dir": "/analysis/Hists_Central",
            "output_dir": None,
            "eras": ["2023BPix"],
            "add_derived_systs": False,
            "execute": False,
        })()
        with patch("builtins.print") as printer:
            self.assertEqual(hmumu.run_hadd_processes(args), 0)
        output = "\n".join(str(call) for call in printer.call_args_list)
        self.assertIn("/analysis/Hists_Central/Run3_2023BPix", output)
        self.assertIn("/analysis/Hists_Central_hadded/Run3_2023BPix", output)

    def test_plot_builds_one_command_per_region(self):
        args = type("Args", (), {
            "era": "2022",
            "input_dir": "/analysis/Hists_merged_hadded/Run3_2022",
            "output_dir": "plots",
            "regions": ["Signal_Fit_VBF,Z_sideband_VBF"],
            "samples": ["Data_Muon", "DY_amcatnlo"],
            "variables": ["DNN_NNOutput"],
            "systematics": True,
            "want_data": True,
            "log_y": True,
            "rebin": True,
            "normalize_dy_to_data": True,
            "normalize_mc_to_data": False,
            "dy_normalization_sample": "DY_amcatnlo",
            "execute": False,
        })()
        with patch("builtins.print") as printer:
            self.assertEqual(hmumu.run_plot(args), 0)
        output = "\n".join(str(call) for call in printer.call_args_list)
        self.assertIn("Signal_Fit_VBF", output)
        self.assertIn("Z_sideband_VBF", output)
        self.assertIn("--systematics", output)
        self.assertIn("DNN_NNOutput", output)

    def test_temporary_histogram_report_lists_missing_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            era_dir = Path(tmp) / "Run3_2023" / "DY_tmp"
            era_dir.mkdir(parents=True)
            (era_dir / "chunk_1.root").write_bytes(b"ROOT")
            with patch("builtins.print") as printer:
                hmumu.report_temporary_histograms(tmp, "2023")
            output = "\n".join(str(call) for call in printer.call_args_list)
            self.assertIn("DY: 1 chunk(s), final-missing", output)


if __name__ == "__main__":
    unittest.main()
