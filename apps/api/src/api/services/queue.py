"""Job queue — Redis + RQ, with a bridge to OmegaClips' JobStore.

Per plan §5 Option B: RQ is the SaaS-facing queue. Workers pop jobs off RQ
and use OmegaClips' DurableJobRunner internally, so OmegaClips' job state
machine stays intact and the SaaS layer doesn't reach into engine internals.
"""
from __future__ import annotations

from redis import Redis
from rq import Queue

from api.config import get_settings


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def queue_for(pipeline_class: str) -> Queue:
    """pipeline_class is one of: cv, llm, render-cpu, render-gpu, export."""
    return Queue(f"q:{pipeline_class}", connection=_redis())
