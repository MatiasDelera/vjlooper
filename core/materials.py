"""Material preset definitions."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MaterialPreset:
    name: str
    base_color: tuple
    emission: float
    roughness: float
    texture_path: Optional[str] = None
