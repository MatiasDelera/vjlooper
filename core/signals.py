"""Pure signal computation utilities for VjLooper."""

from dataclasses import dataclass
import math
from typing import Optional

from . import noise


@dataclass
class SignalParams:
    signal_type: str
    amplitude: float = 1.0
    frequency: float = 1.0
    duration: int = 24
    offset: int = 0
    start_frame: int = 0
    phase_offset: float = 0.0
    noise_seed: int = 0
    smoothing: float = 0.0
    base_value: float = 0.0
    loop_count: int = 0
    use_clamp: bool = False
    clamp_min: float = -1.0
    clamp_max: float = 1.0
    blend_frames: int = 0


smoothing_cache = {}


def _wave(signal_type: str, t: float, seed: int, frame: int) -> float:
    if signal_type == "SINE":
        return math.sin(2 * math.pi * t)
    if signal_type == "COSINE":
        return math.cos(2 * math.pi * t)
    if signal_type == "SQUARE":
        return 1.0 if math.sin(2 * math.pi * t) >= 0 else -1.0
    if signal_type == "TRIANGLE":
        p = t % 1.0
        return 4 * p - 1 if p < 0.5 else 3 - 4 * p
    if signal_type == "SAWTOOTH":
        return 2 * (t % 1.0) - 1
    if signal_type == "NOISE":
        return noise.noise_value(seed + frame)
    return 0.0


def calc_signal(
    params: SignalParams,
    frame: int,
    *,
    loop_lock: bool = False,
    cache_key: Optional[object] = None,
) -> float:
    """Calculate signal value for given frame using pure parameters."""
    sf = params.start_frame + params.offset
    if frame < sf:
        return params.base_value

    rel = frame - sf
    duration = max(1, int(params.duration))
    amplitude = params.amplitude
    frequency = params.frequency

    if loop_lock:
        frequency = round(frequency * duration) / duration

    if params.loop_count and rel >= duration * params.loop_count:
        return params.base_value

    cycle = rel % duration
    t = (cycle / duration) * frequency + params.phase_offset / 360.0
    seed_frame = cycle if loop_lock else frame
    wave = _wave(params.signal_type, t, params.noise_seed, seed_frame)

    key = id(params) if cache_key is None else cache_key
    last = smoothing_cache.get(key, wave)
    val = (
        last * params.smoothing + wave * (1 - params.smoothing)
        if params.smoothing
        else wave
    )
    smoothing_cache[key] = val

    if (
        loop_lock
        and params.blend_frames > 0
        and cycle >= duration - params.blend_frames
    ):
        factor = (cycle - (duration - params.blend_frames)) / params.blend_frames
        t0 = params.phase_offset / 360.0
        start_w = _wave(params.signal_type, t0, params.noise_seed, seed_frame)
        val = val * (1 - factor) + start_w * factor

    out = params.base_value + amplitude * val

    if params.use_clamp:
        out = max(params.clamp_min, min(params.clamp_max, out))

    return out
