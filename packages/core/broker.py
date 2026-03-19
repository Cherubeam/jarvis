"""
Message broker protocol and implementations.

Abstracts message passing for multi-agent communication.
InProcessBroker for local/dev, RedisBroker for homelab (Scenario B).
"""

import queue
import threading
from collections import defaultdict
from collections.abc import Iterator
from typing import Protocol


class MessageBroker(Protocol):
    """Protocol for message brokers used in multi-agent communication."""

    def publish(self, topic: str, message: dict) -> None:
        """Publish a message to a topic."""
        ...

    def subscribe(self, topic: str, group: str = "") -> Iterator[dict]:
        """Subscribe to a topic and iterate over messages."""
        ...

    def ack(self, topic: str, group: str, message_id: str) -> None:
        """Acknowledge a message as processed."""
        ...


class InProcessBroker:
    """In-process message broker using threading queues.

    Suitable for Scenario A (local parallel agents) and development.
    Messages are not persisted — they exist only in memory.
    """

    def __init__(self):
        self._queues: dict[str, dict[str, queue.Queue]] = defaultdict(dict)
        self._lock = threading.Lock()

    def publish(self, topic: str, message: dict) -> None:
        """Publish a message to all subscribers of a topic."""
        with self._lock:
            subscribers = dict(self._queues.get(topic, {}))

        for q in subscribers.values():
            q.put(message)

    def subscribe(self, topic: str, group: str = "default") -> Iterator[dict]:
        """Subscribe to a topic. Blocks until messages arrive.

        Yields messages indefinitely. Use in a thread or with a timeout.
        """
        with self._lock:
            if topic not in self._queues or group not in self._queues[topic]:
                self._queues[topic][group] = queue.Queue()
            q = self._queues[topic][group]

        while True:
            try:
                msg = q.get(timeout=1.0)
                yield msg
            except queue.Empty:
                continue

    def ack(self, topic: str, group: str, message_id: str) -> None:
        """No-op for in-process broker (messages are consumed immediately)."""
        pass

    def close(self) -> None:
        """Clear all queues."""
        with self._lock:
            self._queues.clear()
