from . import signals, operators, ui
from .signals import *
from .operators import *
from .ui import *


def register():
    signals.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    signals.unregister()
