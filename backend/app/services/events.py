from __future__ import annotations

import asyncio
import datetime as dt
from collections import deque
from typing import Any


class EventHub:
    def __init__(self, history_size: int = 500):
        self._sequence = 0
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._subscribers: set[asyncio.Queue] = set()

    async def publish(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._sequence += 1
        event = {
            "sequence": self._sequence,
            "topic": topic,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "payload": payload,
        }
        self._history.append(event)
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)
        return event

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=250)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def history(self, after: int = 0) -> list[dict[str, Any]]:
        return [item for item in self._history if item["sequence"] > after]

