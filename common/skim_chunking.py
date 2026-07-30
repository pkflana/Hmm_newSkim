"""Deterministic grouping of NanoAOD inputs for skim production."""


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
        exceeds_size = current and current_size + entry_size > target_bytes
        exceeds_count = len(current) >= max_files
        if exceeds_size or exceeds_count:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(entry)
        current_size += entry_size
    if current:
        chunks.append(current)
    return chunks
