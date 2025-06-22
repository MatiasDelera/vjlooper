from pathlib import Path
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
from core import persistence


def test_save_and_load(tmp_path):
    data = [{"name": "P", "data": [], "preview_icon": "", "category": "General"}]
    path = tmp_path / "presets.json"
    persistence.save_presets(data, path)
    assert path.with_suffix('.bak').exists() is False
    # second save should create backup
    persistence.save_presets(data, path)
    assert path.with_suffix('.bak').exists()
    loaded = persistence.load_presets(path)
    assert loaded == data
