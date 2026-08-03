"""Read, write, and resolve validation manifests."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def read_manifest(path, expected_stage=None):
    with open(path) as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported manifest schema in {path}")
    if expected_stage and manifest.get("stage") != expected_stage:
        raise ValueError(
            f"Expected a {expected_stage!r} manifest, got "
            f"{manifest.get('stage')!r}: {path}"
        )
    return manifest


def write_manifest(path, stage, **payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, output)
    return document


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
    """Return a valid manifest, creating it from raw inputs when necessary."""
    candidate = Path(manifest_path) if manifest_path else Path(fallback_path)
    if candidate.is_file():
        manifest = read_manifest(candidate, "validation")
    else:
        if not root_input:
            raise ValueError(
                "No validation manifest found: --input is required for "
                "automatic validation"
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
