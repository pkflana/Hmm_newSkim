"""ROOT-file validation and workflow-output completeness helpers."""

import json
import os
import time
from pathlib import Path


def discover_root_files(path):
    if path.endswith(".root"):
        return [os.path.abspath(path)]
    files = []
    for root, _, names in os.walk(path):
        files.extend(
            os.path.abspath(os.path.join(root, name))
            for name in names
            if name.endswith(".root")
        )
    return sorted(files)


def validate_file(task):
    """Validate one ROOT tree; suitable for multiprocessing workers."""
    path, tree_name, *retry_options = task
    retries = int(retry_options[0]) if retry_options else 1
    retry_delay = float(retry_options[1]) if len(retry_options) > 1 else 0.0
    import ROOT

    last_reason = "unknown validation error"
    for attempt in range(1, retries + 1):
        root_file = None
        try:
            root_file = ROOT.TFile.Open(path, "READ")
            if not root_file or root_file.IsZombie():
                last_reason = "cannot open file or zombie"
            else:
                tree = root_file.Get(tree_name)
                if not tree:
                    last_reason = f"missing tree '{tree_name}'"
                elif tree.GetEntries() == 0:
                    last_reason = f"empty tree '{tree_name}' (0 entries)"
                elif tree.GetListOfBranches().GetEntries() == 0:
                    last_reason = f"tree '{tree_name}' has no branches"
                else:
                    return path, True, ""
        except Exception as error:
            last_reason = repr(error)
        finally:
            if root_file:
                root_file.Close()
        if attempt < retries and retry_delay:
            time.sleep(retry_delay)
    return path, False, f"{last_reason} (failed after {retries} attempts)"


def atomic_write_lines(path, lines):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w") as handle:
        for line in lines:
            handle.write(f"{line}\n")
    os.replace(temporary, output)


def nonempty(path):
    candidate = Path(path)
    return candidate.is_file() and candidate.stat().st_size > 0


def validation_complete(path):
    if not nonempty(path):
        return False
    try:
        with open(path) as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        manifest.get("stage") == "validation"
        and manifest.get("status") == "passed"
        and isinstance(manifest.get("valid_root_files"), list)
        and (
            bool(manifest["valid_root_files"])
            or bool(manifest.get("ignored_empty_root_files", []))
        )
    )


def histogram_complete(path):
    """Return true only for a readable ROOT file containing output objects."""
    if not nonempty(path):
        return False
    root_file = None
    try:
        import ROOT

        root_file = ROOT.TFile.Open(str(path), "READ")
        return bool(
            root_file
            and not root_file.IsZombie()
            and root_file.GetNkeys() > 0
        )
    except Exception:
        return False
    finally:
        if root_file:
            root_file.Close()


def stage_output_complete(stage, path):
    if stage not in {"validation", "histograms", "systematics"}:
        raise ValueError(f"Unknown workflow stage: {stage}")
    return (
        validation_complete(path)
        if stage == "validation"
        else histogram_complete(path)
    )
