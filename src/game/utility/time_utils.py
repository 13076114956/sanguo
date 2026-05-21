from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(slots=True)
class DurationBreakdown:
    hours: int
    minutes: int
    seconds: int


class TimeUtils:
    """时间转换工具。"""

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def format_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")

    @staticmethod
    def to_isoformat(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def seconds_to_breakdown(seconds: int) -> DurationBreakdown:
        normalized = max(0, int(seconds))
        hours, remainder = divmod(normalized, 3600)
        minutes, seconds = divmod(remainder, 60)
        return DurationBreakdown(hours=hours, minutes=minutes, seconds=seconds)

    @staticmethod
    def add_minutes(base: datetime, minutes: int) -> datetime:
        return base + timedelta(minutes=minutes)

