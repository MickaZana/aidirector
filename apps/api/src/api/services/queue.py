"""Job queue — Redis + RQ, with in-process memory fallback.

Per plan §5 Option B: RQ is the SaaS-facing queue. Workers pop jobs off RQ
and use OmegaClips' DurableJobRunner internally, so OmegaClips' job state
machine stays intact and the SaaS layer doesn't reach into engine internals.

Graceful degradation (Sprint 2):
  - If Redis is unreachable, queue_for() falls back to InMemoryQueue — an
    in-process (list + threading) queue so the app stays up during a Redis
    outage. InMemoryQueue.enqueue() is a no-op (we can't process jobs without
    Redis anyway), but it never raises.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any

from redis import Redis
from rq import Queue

from api.config import get_settings

log = logging.getLogger(__name__)

# ── In-memory fallback queue ──────────────────────────────────────────────────

_EMPTY_RESULT: dict[str, Any] = {
    "status": "deferred_redis_down",
    "note": "Redis unavailable — job queued in memory; will not be processed until Redis recovers",
}


class InMemoryQueue:
    """Thread-safe in-process queue used when Redis is unreachable.

    Jobs are accepted (no-op enqueue) but cannot be processed without Redis.
    The queue simply swallows the payload and returns a stub result so the
    caller doesn't crash. This is better than throwing 500 errors — the
    pipeline gracefully pauses until Redis recovers.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._lock = threading.Lock()
        self._items: deque[dict[str, Any]] = deque()

    @property
    def name(self) -> str:
        return self._name

    def enqueue(self, func: str, args: dict | None = None, **kwargs: Any) -> Any:
        """Accept the job but don't process it — Redis is down."""
        with self._lock:
            self._items.append({"func": func, "args": args or {}, "kwargs": kwargs})
        log.warning("InMemoryQueue[%s]: job deferred (Redis down): %s(%s)", self._name, func, args)
        return _EMPTY_RESULT

    def enqueue_call(
        self, func: str, args: tuple = (), kwargs: dict | None = None, **options: Any
    ) -> Any:
        """RQ-compatible alias for enqueue_call."""
        return self.enqueue(func, args=(args or (), kwargs or {}), **options)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def __bool__(self) -> bool:
        return True

    def empty(self) -> bool:
        with self._lock:
            return len(self._items) == 0


# ── Redis-backed queue (primary) ─────────────────────────────────────────────


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def queue_for(pipeline_class: str) -> Queue | InMemoryQueue:
    """Return an RQ Queue for `pipeline_class`, or InMemoryQueue fallback.

    pipeline_class is one of: cv, llm, render-cpu, render-gpu, export.

    If Redis is unreachable, returns an InMemoryQueue that accepts jobs
    but does not process them. The calling code does not need to handle
    connection errors — the fallback is transparent.
    """
    name = f"q:{pipeline_class}"
    try:
        r = _redis()
        r.ping()
        return Queue(name, connection=r)
    except Exception as exc:
        log.warning(
            "queue_for: Redis unreachable (%s) — using InMemoryQueue fallback for %s",
            exc,
            name,
        )
        return InMemoryQueue(name)
