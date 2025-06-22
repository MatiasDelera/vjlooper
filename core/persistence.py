"""Persistence helpers used by the add-on."""

import json
import shutil
from pathlib import Path
from typing import Any, List


def save_presets(data: List[Any], path: Path, version: int = 1) -> None:
    """Save presets to disk with backup and version metadata."""
    if path.exists():
        shutil.copy(path, path.with_suffix('.bak'))
    payload = {"__version__": version, "presets": data}
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)


def load_presets(path: Path) -> List[Any]:
    """Load presets from file handling version migrations."""
    if not path.exists():
        return []
    data = json.load(open(path))
    if isinstance(data, list):
        # legacy version without metadata
        return data
    version = data.get("__version__", 0)
    presets = data.get("presets", [])
    # future migration logic could be added here based on version
    return presets
