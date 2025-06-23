import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, ROOT)

import vjlooper


def test_double_register(monkeypatch):
    """Registering multiple times should never raise ValueError."""
    monkeypatch.setattr(vjlooper.tunnelfx, "register", lambda: None)
    monkeypatch.setattr(vjlooper.tunnelfx, "unregister", lambda: None)

    vjlooper.register()
    vjlooper.unregister()
    vjlooper.register()
    vjlooper.unregister()



