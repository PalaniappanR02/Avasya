from __future__ import annotations

from enum import Enum


class DataOrigin(str, Enum):
    REAL = "REAL"
    MIXED = "MIXED"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"
