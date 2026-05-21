from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


class IGameData(ABC):
    """统一游戏数据接口。"""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(slots=True)
class BaseData(IGameData):
    id: str
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

