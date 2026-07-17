"""Resolve a validation manifest, creating it once when inputs are raw files."""

import os
import subprocess
import sys
from pathlib import Path

from common.manifests import read_manifest


def ensure_validation_manifest(
    manifest_path,
    *,
    era,
    dataset,
    root_input=None,
    json_input=None,
    fallback_path,
    workers=8,
    retries=3,
    retry_delay=2.0,
):
    candidate = Path(manifest_path) if manifest_path else Path(fallback_path)
    if candidate.is_file():
        manifest = read_manifest(candidate, "validation")
    else:
        if not root_input:
            raise ValueError(
                "No validation manifest found: --input is required for automatic validation"
            )
        json_input = json_input or root_input
        analysis_path = Path(os.environ["ANALYSIS_PATH"])
        command = [
            sys.executable,
            str(analysis_path / "analysis/validate_dataset.py"),
            "--era",
            era,
            "--dataset-name",
            dataset,
            "--root-input",
            root_input,
            "--json-input",
            json_input,
            "--output-manifest",
            str(candidate),
            "--workers",
            str(workers),
            "--retries",
            str(retries),
            "--retry-delay",
            str(retry_delay),
        ]
        print("[MANIFEST] Not found; running automatic validation", flush=True)
        print("[MANIFEST] " + " ".join(command), flush=True)
        subprocess.run(command, check=True, cwd=analysis_path)
        manifest = read_manifest(candidate, "validation")
    if manifest.get("status", "passed") != "passed":
        raise RuntimeError(f"Refusing failed validation manifest: {candidate}")
    if manifest["era"] != era or manifest["dataset"] != dataset:
        raise ValueError(f"Manifest era/dataset mismatch: {candidate}")
    return str(candidate.resolve()), manifest
