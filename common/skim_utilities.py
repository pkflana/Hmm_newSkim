"""Chunking helpers shared by skim workflows."""

from pathlib import Path
import re


def chunk_files_by_size(file_entries, target_bytes, max_files):
    """Create stable sequential chunks bounded by input bytes and file count."""
    if target_bytes <= 0:
        raise ValueError("target_bytes must be greater than zero")
    if max_files <= 0:
        raise ValueError("max_files must be greater than zero")

    chunks = []
    current = []
    current_size = 0
    for raw_entry in file_entries:
        entry = (
            {"path": raw_entry, "size": 0}
            if isinstance(raw_entry, str)
            else dict(raw_entry)
        )
        if "path" not in entry:
            raise ValueError(f"file entry has no path: {raw_entry!r}")
        entry_size = max(0, int(entry.get("size", 0)))
        if current and (
            current_size + entry_size > target_bytes or len(current) >= max_files
        ):
            chunks.append(current)
            current = []
            current_size = 0
        current.append(entry)
        current_size += entry_size
    if current:
        chunks.append(current)
    return chunks


def input_file_id(path):
    stem = Path(path).stem
    match = re.fullmatch(r"(?:skim|report)_(\d+)", stem)
    return match.group(1) if match else stem.removesuffix("_report")


def metadata_excluding_root_files(metadata_inputs, excluded_root_files):
    """Return JSON inputs excluding reports paired to rejected MC ROOT files."""
    excluded_ids = {input_file_id(path) for path in excluded_root_files}
    selected = []
    seen = set()
    for raw_path in metadata_inputs:
        path = Path(raw_path)
        candidates = path.rglob("*.json") if path.is_dir() else (path,)
        for candidate in candidates:
            normalized = str(candidate.resolve())
            if (
                candidate.suffix == ".json"
                and normalized not in seen
                and input_file_id(candidate) not in excluded_ids
            ):
                selected.append(normalized)
                seen.add(normalized)
    return selected
