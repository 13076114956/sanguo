from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class JsonUtils:
    """JSON 序列化与落盘工具。"""

    @staticmethod
    def dumps(data: Any, *, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(JsonUtils._normalize(data), ensure_ascii=ensure_ascii, indent=indent)

    @staticmethod
    def dump_to_file(path: Path, data: Any, *, ensure_ascii: bool = False, indent: int = 2) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(JsonUtils.dumps(data, ensure_ascii=ensure_ascii, indent=indent), encoding="utf-8")

    @staticmethod
    def loads(text: str) -> Any:
        return json.loads(text)

    @staticmethod
    def load_from_file(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _normalize(data: Any) -> Any:
        if is_dataclass(data):
            return {key: JsonUtils._normalize(value) for key, value in asdict(data).items()}
        if isinstance(data, dict):
            return {key: JsonUtils._normalize(value) for key, value in data.items()}
        if isinstance(data, (list, tuple, set)):
            return [JsonUtils._normalize(item) for item in data]
        if hasattr(data, "value"):
            return getattr(data, "value")
        return data

