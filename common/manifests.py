"""Versioned, atomic manifests shared by validation and histograms."""

import json
import os
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
            f"Expected a {expected_stage!r} manifest, got {manifest.get('stage')!r}: {path}"
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
