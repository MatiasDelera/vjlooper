import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, ROOT)

import vjlooper.signals as signals

class Item:
    pass

class PresetCollection(list):
    def add(self):
        it = Item()
        self.append(it)
        return it
    def clear(self):
        super().clear()

def test_load_default_presets(tmp_path, monkeypatch):
    scene = types.SimpleNamespace(signal_presets=PresetCollection())
    monkeypatch.setattr(signals, "_scene", lambda: scene)
    monkeypatch.setattr(signals, "get_preset_file", lambda: tmp_path / "presets.json")
    signals.load_presets_from_disk()
    assert len(scene.signal_presets) > 0
