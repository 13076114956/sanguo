from __future__ import annotations

import random
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


class RandomService:
    """可注入随机数服务，便于测试和重现。"""

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def roll(self) -> float:
        return self._random.random()

    def randint(self, minimum: int, maximum: int) -> int:
        return self._random.randint(minimum, maximum)

    def choice(self, values: Sequence[T]) -> T:
        return self._random.choice(values)

    def weighted_choice(self, values: Iterable[tuple[T, float]]) -> T:
        items = list(values)
        total = sum(weight for _, weight in items)
        if total <= 0:
            raise ValueError("总权重必须大于 0")
        cursor = self.roll() * total
        current = 0.0
        for value, weight in items:
            current += weight
            if cursor <= current:
                return value
        return items[-1][0]

