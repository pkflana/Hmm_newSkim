"""Run a legacy tool while public entry points migrate into this package."""

from pathlib import Path
import runpy


def run_tool(filename):
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "tools" / filename),
        run_name="__main__",
    )
