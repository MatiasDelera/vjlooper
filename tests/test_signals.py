import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
from core import signals as core_signals


def test_sine_wave():
    params = core_signals.SignalParams(signal_type='SINE', duration=10)
    # start frame should return base value
    assert core_signals.calc_signal(params, 0) == 0.0
    # value at frame 2 for duration 10
    val = core_signals.calc_signal(params, 2)
    assert math.isclose(val, 0.9510565, abs_tol=1e-4)


def test_triangle_wave():
    params = core_signals.SignalParams(signal_type='TRIANGLE', duration=4)
    val0 = core_signals.calc_signal(params, 0)
    val2 = core_signals.calc_signal(params, 2)
    assert math.isclose(val0, -1.0, abs_tol=1e-4)
    assert math.isclose(val2, 1.0, abs_tol=1e-4)


def test_loop_lock_quantization():
    params = core_signals.SignalParams(signal_type='SINE', duration=8, frequency=1.3)
    val_unlocked = core_signals.calc_signal(params, 4, loop_lock=False)
    val_locked = core_signals.calc_signal(params, 4, loop_lock=True)
    # frequencies differ when loop lock active
    assert not math.isclose(val_unlocked, val_locked)
