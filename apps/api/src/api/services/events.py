"""Real-time event publishing — Redis Pub/Sub bridge for WebSocket streams.

Every job state transition publishes a JSON message to a Redis channel
named `job:{job_id}:events`. WebSocket endpoints subscribe to these
channels and forward messages to connected clients.

Architecture:
  transition() in state_transitions.py  →  publish_job_event()  →  Redis PUBLISH
  WebSocket handler                     →  Redis SUBSCRIBE      →  client

This is decoupled by design: the WebSocket server doesn't care about
the transition logic, and the transition logic doesn't care about
connected clients.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)


def publish_job_event(job_id: str, event: dict[str, Any]) -> None:
    """Publish a job state transition event to Redis Pub/Sub.

    Callers (currently state_transitions.transition()) invoke this
    after every accepted or forced transition. The WebSocket handler
    subscribes to `job:{job_id}:events` and forwards to clients.

    If Redis is unreachable, the event is silently dropped — the
    WebSocket client will eventually catch up via polling.
    """
    try:
        from redis import Redis
        from api.config import get_settings

        settings = get_settings()
        r = Redis.from_url(settings.redis_url, decode_responses=True)
        channel = f"job:{job_id}:events"
        payload = json.dumps(event, default=str)
        r.publish(channel, payload)
    except Exception as exc:
        log.debug(
            "publish_job_event: Redis unavailable (%s) — event dropped for job %s", exc, job_id
        )
