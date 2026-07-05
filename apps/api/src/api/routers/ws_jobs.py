"""WebSocket endpoint for real-time job event streaming.

WS /api/jobs/{job_id}/events

Subscribes to Redis Pub/Sub channel `job:{job_id}:events` and forwards
every message to the connected client. When Redis is unreachable, the
endpoint still accepts the connection and emits a heartbeat every 30s
so the client doesn't tear down the socket.

Protocol:
  - Server → Client: JSON-encoded event dicts
    {"kind": "Job", "from_state": "QUEUED", "to_state": "RUNNING",
     "reason": "scene_analysis_started", "timestamp": "..."}
  - Client → Server: ignored (reserved for future ack protocol)
  - Server sends a heartbeat ping every 30 seconds

The endpoint is unauthenticated at the WebSocket level — the client
must already have a valid session via Clerk. Job isolation is enforced
by the job_id path parameter (the client can only subscribe to events
for jobs they know the ID of).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/api/jobs/{job_id}/events")
async def job_events(websocket: WebSocket, job_id: str) -> None:
    """Stream job state transitions to a connected WebSocket client.

    Uses Redis Pub/Sub internally. Falls back to periodic pings if
    Redis is unreachable so the client keeps the connection alive.
    """
    await websocket.accept()
    log.info("ws_jobs: client connected for job %s", job_id)

    channel = f"job:{job_id}:events"
    pubsub = None
    redis_client = None

    try:
        # Try to set up Redis Pub/Sub subscription
        try:
            from redis import Redis
            from api.config import get_settings

            settings = get_settings()
            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            pubsub = redis_client.pubsub()
            pubsub.subscribe(channel)
            log.debug("ws_jobs: subscribed to Redis channel %s", channel)
        except Exception as exc:
            log.warning(
                "ws_jobs: Redis unavailable (%s) — heartbeat-only mode for job %s", exc, job_id
            )
            pubsub = None

        heartbeat_interval = 30.0
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            now = asyncio.get_event_loop().time()

            # Check for incoming messages (or disconnect)
            try:
                if pubsub is not None:
                    # Non-blocking check for Redis messages
                    message = pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        data = json.loads(message["data"])
                        await websocket.send_json(data)
                        continue
                else:
                    # No Redis — just wait
                    await asyncio.sleep(1.0)
            except WebSocketDisconnect:
                log.info("ws_jobs: client disconnected for job %s", job_id)
                break
            except Exception as exc:
                log.debug("ws_jobs: error reading message for job %s: %s", job_id, exc)

            # Send heartbeat every 30s
            if now - last_heartbeat >= heartbeat_interval:
                try:
                    await websocket.send_json({"type": "heartbeat", "timestamp": now})
                    last_heartbeat = now
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

    except asyncio.CancelledError:
        pass
    finally:
        # Clean up Redis subscription
        if pubsub is not None:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass
        if redis_client is not None:
            try:
                redis_client.close()
            except Exception:
                pass
        log.info("ws_jobs: cleaned up connection for job %s", job_id)
