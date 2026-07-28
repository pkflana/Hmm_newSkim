"""Validation and per-file metadata selection for failed histogram chunks."""

from pathlib import Path
import re


def resolve_skip_failed_chunks(requested, is_data, n_cores):
    """Apply the automatic default without ever skipping data."""
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
    """Return the shared identifier of a skim ROOT file and report JSON."""
    stem = Path(path).stem
    indexed_match = re.fullmatch(r"(?:skim|report)_(\d+)", stem)
    if indexed_match:
        return indexed_match.group(1)
    if stem.endswith("_report"):
        stem = stem[: -len("_report")]
    return stem


def metadata_for_root_files(metadata_inputs, root_files):
    """Select only per-file JSON reports belonging to supplied ROOT files."""
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
        str(path)
        for path in candidates
        if input_file_id(path) in wanted_ids
    ]
    selected_ids = {input_file_id(path) for path in selected}
    missing_ids = sorted(wanted_ids - selected_ids)
    if missing_ids:
        preview = ", ".join(missing_ids[:5])
        raise RuntimeError(
            "Cannot recalculate normalization after failed chunks: no "
            f"per-file metadata JSON found for {len(missing_ids)} successful "
            f"ROOT file(s), including {preview}"
        )
    return selected
