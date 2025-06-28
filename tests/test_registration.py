import importlib
import os
import sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, ROOT)

import vjlooper


def test_modules_imported():
    assert hasattr(vjlooper, "ui")
    assert hasattr(vjlooper, "operators")


def test_register_rollback(monkeypatch):
    called = {}

    def fail_register():
        called["fail"] = True
        raise RuntimeError("boom")

    monkeypatch.setattr(vjlooper.operators, "register", fail_register)
    with pytest.raises(RuntimeError):
        vjlooper.register()

    # replace with no-op for successful registration
    monkeypatch.setattr(vjlooper.operators, "register", lambda: called.setdefault("ok", True))
    monkeypatch.setattr(vjlooper.tunnelfx, "register", lambda: None)
    monkeypatch.setattr(vjlooper.tunnelfx, "unregister", lambda: None)
    vjlooper.register()
    vjlooper.unregister()


def test_unregister_props_no_error():
    # ensure calling without prior registration doesn't raise
    importlib.reload(vjlooper.ui)
    vjlooper.ui.unregister_props()

