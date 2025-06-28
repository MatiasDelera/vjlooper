"""Aggregates registration of VjLooper modules."""

from . import signals, operators, ui, tunnelfx, type_animator
from .signals import *
from .operators import *
from .ui import *
from .tunnelfx import *


def register():
    signals.register()
    operators.register()
    tunnelfx.register()
    type_animator.register()
    ui.register()


def unregister():
    ui.unregister()
    tunnelfx.unregister()
    type_animator.unregister()
    operators.unregister()
    signals.unregister()
