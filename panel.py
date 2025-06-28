"""Aggregates registration of VjLooper modules."""

from . import signals, operators, ui, tunnelfx
from .signals import *
from .operators import *
from .ui import *
from .tunnelfx import *


def register():
    signals.register()
    operators.register()
    tunnelfx.register()
    ui.register()


def unregister():
    ui.unregister()
    tunnelfx.unregister()
    operators.unregister()
    signals.unregister()
