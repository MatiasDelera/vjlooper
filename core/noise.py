import random


def noise_value(seed: int) -> float:
    """Return deterministic noise between -1 and 1 for given seed."""
    random.seed(seed)
    return random.uniform(-1.0, 1.0)
