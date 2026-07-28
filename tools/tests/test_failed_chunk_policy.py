import tempfile
import unittest
from pathlib import Path


class FailedChunkPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from common.failed_chunk_policy import (
            metadata_for_root_files,
            resolve_skip_failed_chunks,
            validate_skip_failed_chunks,
        )

        cls.metadata_for_root_files = staticmethod(metadata_for_root_files)
        cls.resolve_policy = staticmethod(resolve_skip_failed_chunks)
        cls.validate_policy = staticmethod(validate_skip_failed_chunks)

    def test_automatic_default_skips_only_serial_mc(self):
        self.assertTrue(self.resolve_policy(None, False, 1))
        self.assertFalse(self.resolve_policy(None, True, 1))
        self.assertFalse(self.resolve_policy(None, False, 4))

    def test_data_cannot_skip_failed_chunks(self):
        with self.assertRaisesRegex(ValueError, "forbidden for data"):
            self.validate_policy(True, True, 1, False)

    def test_skip_requires_serial_fresh_processing(self):
        with self.assertRaisesRegex(ValueError, "requires --n-cores 1"):
            self.validate_policy(True, False, 2, False)
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            self.validate_policy(True, False, 1, True)

    def test_metadata_is_filtered_with_surviving_root_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root_a = root / "a_skim.root"
            root_b = root / "b_skim.root"
            json_a = root / "a_skim_report.json"
            json_b = root / "b_skim_report.json"
            for path in (root_a, root_b, json_a, json_b):
                path.touch()
            selected = self.metadata_for_root_files(
                [str(json_a), str(json_b)],
                [str(root_b)],
            )
            self.assertEqual(selected, [str(json_b)])

    def test_indexed_skim_and_report_names_are_paired(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skim = root / "skim_7.root"
            report = root / "report_7.json"
            skim.touch()
            report.touch()
            selected = self.metadata_for_root_files(
                [str(report)],
                [str(skim)],
            )
            self.assertEqual(selected, [str(report)])


if __name__ == "__main__":
    unittest.main()
