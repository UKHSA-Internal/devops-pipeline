"""Shared helpers for the tests."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIONS = REPO_ROOT / "packages" / "shared-workflows" / "actions"


def load_script(path: Path, name: str):
    """Import a script that isn't on the import path, such as a composite action's Python file."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
