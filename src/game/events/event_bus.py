from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict

EventHandler = Callable[["GameEvent"], None]


@dataclass(slots=True)
class GameEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """基于委托/回调的事件总线。"""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler not in self._subscribers[event_name]:
            self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_name)
        if not handlers:
            return
        self._subscribers[event_name] = [registered for registered in handlers if registered != handler]
        if not self._subscribers[event_name]:
            self._subscribers.pop(event_name, None)

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> GameEvent:
        event = GameEvent(name=event_name, payload=payload or {})
        for handler in list(self._subscribers.get(event_name, [])):
            handler(event)
        return event

    def clear(self) -> None:
        self._subscribers.clear()

