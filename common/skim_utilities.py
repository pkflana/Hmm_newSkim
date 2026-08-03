"""Chunking and failed-chunk policies shared by skim workflows."""

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


def resolve_skip_failed_chunks(requested, is_data, n_cores):
    if requested is None:
        return not is_data and n_cores == 1
    return bool(requested)


def validate_skip_failed_chunks(skip_failed_chunks, is_data, n_cores, resume):
    if not skip_failed_chunks:
        return
    if is_data:
        raise ValueError(
            "--skip-failed-chunks is forbidden for data: every data chunk "
            "must be processed successfully."
        )
    if n_cores != 1:
        raise ValueError(
            "--skip-failed-chunks requires --n-cores 1 so failed chunks can "
            "be identified and the surviving chunks renormalized safely."
        )
    if resume:
        raise ValueError(
            "--skip-failed-chunks cannot be combined with --resume because "
            "the normalization stored in existing temporary files is unknown."
        )


def input_file_id(path):
    stem = Path(path).stem
    indexed_match = re.fullmatch(r"(?:skim|report)_(\d+)", stem)
    if indexed_match:
        return indexed_match.group(1)
    return stem.removesuffix("_report")


def metadata_for_root_files(metadata_inputs, root_files):
    wanted_ids = {input_file_id(path) for path in root_files}
    candidates = []
    seen = set()
    for metadata_input in metadata_inputs:
        path = Path(metadata_input)
        paths = path.rglob("*.json") if path.is_dir() else (path,)
        for candidate in paths:
            normalized = str(candidate.resolve())
            if candidate.suffix == ".json" and normalized not in seen:
                seen.add(normalized)
                candidates.append(candidate)

    selected = [
        str(path) for path in candidates if input_file_id(path) in wanted_ids
    ]
    missing_ids = sorted(wanted_ids - {input_file_id(path) for path in selected})
    if missing_ids:
        preview = ", ".join(missing_ids[:5])
        raise RuntimeError(
            "Cannot recalculate normalization after failed chunks: no "
            f"per-file metadata JSON found for {len(missing_ids)} successful "
            f"ROOT file(s), including {preview}"
        )
    return selected
