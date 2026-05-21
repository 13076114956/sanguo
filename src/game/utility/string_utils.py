from __future__ import annotations

import re
from typing import Iterable


class StringUtils:
    """字符串处理工具。"""

    @staticmethod
    def snake_to_title(value: str) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def normalize_whitespace(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def join_non_empty(values: Iterable[str], separator: str = ", ") -> str:
        return separator.join(item for item in values if item)

