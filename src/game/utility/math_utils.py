from __future__ import annotations

from typing import Iterable


class MathUtils:
    """通用数学工具。"""

    @staticmethod
    def clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def percent(value: float) -> float:
        return MathUtils.clamp(value, 0.0, 1.0)

    @staticmethod
    def sum_safe(values: Iterable[float]) -> float:
        return sum(values, 0.0)

    @staticmethod
    def non_negative(value: float) -> float:
        return max(0.0, value)

