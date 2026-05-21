from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from game.events.event_bus import EventBus
from game.utility.time_utils import TimeUtils


class SingletonMeta(type):
    _instances: dict[type, object] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> object:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class EventManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.bus = EventBus()

    def subscribe(self, event_name: str, handler: Callable[..., None]) -> None:
        self.bus.subscribe(event_name, handler)

    def unsubscribe(self, event_name: str, handler: Callable[..., None]) -> None:
        self.bus.unsubscribe(event_name, handler)

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        self.bus.publish(event_name, payload)


@dataclass(slots=True)
class ScheduledTask:
    name: str
    interval_seconds: int
    callback: Callable[[], None]
    last_run_at: float = 0.0


class TimeManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.now_provider = TimeUtils.utcnow
        self._elapsed_seconds = 0.0
        self._tasks: dict[str, ScheduledTask] = {}

    @property
    def elapsed_seconds(self) -> float:
        return self._elapsed_seconds

    def register_repeating_task(self, name: str, interval_seconds: int, callback: Callable[[], None]) -> None:
        self._tasks[name] = ScheduledTask(name=name, interval_seconds=interval_seconds, callback=callback)

    def tick(self, delta_seconds: float) -> None:
        self._elapsed_seconds += max(0.0, delta_seconds)
        for task in self._tasks.values():
            if self._elapsed_seconds - task.last_run_at >= task.interval_seconds:
                task.callback()
                task.last_run_at = self._elapsed_seconds


class UIManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._messages: list[str] = []

    def show_message(self, message: str) -> None:
        self._messages.append(message)

    def flush_messages(self) -> list[str]:
        messages = list(self._messages)
        self._messages.clear()
        return messages


class ResourceManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._resources: dict[str, Any] = {}

    def register(self, key: str, value: Any) -> None:
        self._resources[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._resources.get(key, default)


@dataclass(slots=True)
class SaveSlotInfo:
    slot: int
    path: Path
    exists: bool
    summary: dict[str, Any] = field(default_factory=dict)


class SaveManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.repository: Any | None = None

    def bind_repository(self, repository: Any) -> None:
        self.repository = repository


class GameManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.is_initialized = False
        self.services: dict[str, Any] = {}

    def register_service(self, key: str, service: Any) -> None:
        self.services[key] = service

    def get_service(self, key: str) -> Any:
        return self.services[key]

    def initialize(self) -> None:
        self.is_initialized = True

