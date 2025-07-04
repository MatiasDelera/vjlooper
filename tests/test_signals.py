import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
from core import signals as core_signals


def test_sine_wave():
    params = core_signals.SignalParams(signal_type="SINE", duration=10)
    # start frame should return base value
    assert core_signals.calc_signal(params, 0) == 0.0
    # value at frame 2 for duration 10
    val = core_signals.calc_signal(params, 2)
    assert math.isclose(val, 0.9510565, abs_tol=1e-4)


def test_sine_loop():
    params = core_signals.SignalParams(signal_type="SINE", duration=24, frequency=1)
    val0 = core_signals.calc_signal(params, 0)
    val24 = core_signals.calc_signal(params, 24)
    assert math.isclose(val0, val24, abs_tol=1e-6)


def test_triangle_wave():
    params = core_signals.SignalParams(signal_type="TRIANGLE", duration=4)
    val0 = core_signals.calc_signal(params, 0)
    val2 = core_signals.calc_signal(params, 2)
    assert math.isclose(val0, -1.0, abs_tol=1e-4)
    assert math.isclose(val2, 1.0, abs_tol=1e-4)


def test_loop_lock_quantization():
    params = core_signals.SignalParams(signal_type="SINE", duration=8, frequency=1.3)
    val_unlocked = core_signals.calc_signal(params, 4, loop_lock=False)
    val_locked = core_signals.calc_signal(params, 4, loop_lock=True)
    # frequencies differ when loop lock active
    assert not math.isclose(val_unlocked, val_locked)


def test_loop_lock():
    params = core_signals.SignalParams(signal_type="SINE", duration=24, frequency=1.3)
    locked = core_signals.calc_signal(params, 5, loop_lock=True)
    qfreq = round(params.frequency * params.duration) / params.duration
    expected = core_signals.calc_signal(
        core_signals.SignalParams(signal_type="SINE", duration=24, frequency=qfreq), 5
    )
    assert math.isclose(locked, expected, abs_tol=1e-6)


def test_smoothing_persistent():
    core_signals.smoothing_cache.clear()
    raw0 = core_signals.calc_signal(
        core_signals.SignalParams(signal_type="SINE", duration=10), 0
    )
    raw1 = core_signals.calc_signal(
        core_signals.SignalParams(signal_type="SINE", duration=10), 1
    )
    core_signals.smoothing_cache.clear()
    params = core_signals.SignalParams(signal_type="SINE", duration=10, smoothing=0.5)
    smooth0 = core_signals.calc_signal(params, 0, cache_key="x")
    smooth1 = core_signals.calc_signal(params, 1, cache_key="x")
    assert math.isclose(raw0, smooth0, abs_tol=1e-6)
    assert not math.isclose(raw1, smooth1, abs_tol=1e-6)
