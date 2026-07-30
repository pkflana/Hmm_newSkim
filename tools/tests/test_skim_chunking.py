import unittest

from common.skim_chunking import chunk_files_by_size


class SkimChunkingTest(unittest.TestCase):
    def test_chunks_are_bounded_by_size_and_count(self):
        files = [
            {"path": "a.root", "size": 4},
            {"path": "b.root", "size": 3},
            {"path": "c.root", "size": 2},
            {"path": "d.root", "size": 1},
        ]
        chunks = chunk_files_by_size(files, target_bytes=5, max_files=2)
        self.assertEqual(
            [[entry["path"] for entry in chunk] for chunk in chunks],
            [["a.root"], ["b.root", "c.root"], ["d.root"]],
        )

    def test_oversized_file_is_kept_as_one_chunk(self):
        files = [{"path": "large.root", "size": 10}]
        self.assertEqual(
            chunk_files_by_size(files, target_bytes=5, max_files=5),
            [files],
        )

    def test_legacy_string_entries_are_supported(self):
        chunks = chunk_files_by_size(
            ["a.root", "b.root", "c.root"],
            target_bytes=5,
            max_files=2,
        )
        self.assertEqual(
            [[entry["path"] for entry in chunk] for chunk in chunks],
            [["a.root", "b.root"], ["c.root"]],
        )


if __name__ == "__main__":
    unittest.main()
