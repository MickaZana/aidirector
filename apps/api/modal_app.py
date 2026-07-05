"""Modal worker application — AI Director compute plane.

Workers:
  run_scene_analysis — OmegaClips CV + Director Agent LLM; writes DirectorPlan.
  run_render         — FFmpeg render; consumes DirectorPlan → RenderOutput.
  drain_render_queue — Cron bridge: pops from RQ q:render-cpu → run_render.
  drain_cv_queue     — Cron bridge: pops from RQ q:cv → run_scene_analysis.

Deploy:
    modal deploy apps/api/modal_app.py

Required Modal secrets:
    aidirector-db, aidirector-redis, aidirector-r2, aidirector-signing,
    aidirector-anthropic
"""

from __future__ import annotations

from uuid import uuid4

import modal

# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

_base_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "fonts-liberation")
    .pip_install_from_pyproject("apps/api/pyproject.toml", optional_dependencies=["asr"])
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = modal.App("aidirector-workers", image=_base_image)

_modal_secrets = [
    modal.Secret.from_name("aidirector-db"),
    modal.Secret.from_name("aidirector-redis"),
    modal.Secret.from_name("aidirector-r2"),
    modal.Secret.from_name("aidirector-signing"),
    modal.Secret.from_name("aidirector-anthropic"),
]


# ---------------------------------------------------------------------------
# Scene-analysis + Director Agent worker
# ---------------------------------------------------------------------------


@app.function(
    secrets=_modal_secrets,
    timeout=900,
    memory=4096,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
)
def run_scene_analysis(payload: dict) -> dict:
    """Run OmegaClips FI-1→13 + Director Agent LLM for one job.

    Pipeline:
      1. Load Job + Upload from DB
      2. Download source file from R2 → /tmp/
      3. Run OmegaClips intelligence (FI-1→FI-13) → Scene + ClipCandidate rows
      4. Call Director Agent (Anthropic claude-sonnet-4-6) → DirectorPlan
      5. Persist DirectorPlan; transition Job RUNNING → SUCCEEDED
      6. Enqueue render jobs to q:render-cpu for each selected clip
    """
    import logging
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    log = logging.getLogger(__name__)
    job_id: str = payload["job_id"]
    log.info("scene_analysis: job=%s starting", job_id)

    from sqlalchemy import select
    from api.db import SessionLocal
    from api.models import Job, JobStatus, Upload, DirectorPlan as DirectorPlanModel
    from api.services.state_transitions import transition

    with SessionLocal() as db:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            log.error("scene_analysis: job %s not found", job_id)
            return {"job_id": job_id, "status": "error", "error": "job not found"}

        upload = db.execute(select(Upload).where(Upload.id == job.upload_id)).scalar_one_or_none()
        if upload is None:
            log.error("scene_analysis: upload not found for job %s", job_id)
            return {"job_id": job_id, "status": "error", "error": "upload not found"}

        transition(db, job, JobStatus.RUNNING.value, reason="scene_analysis_started")
        db.commit()
        source_key = upload.r2_key

    # Download source file from R2
    import tempfile

    tmp_dir = Path(tempfile.mkdtemp())
    source_path = tmp_dir / (Path(source_key).name or "source.mp4")

    try:
        from api.services import r2 as r2_svc

        if r2_svc.is_r2_configured():
            log.info("scene_analysis: downloading source from R2 key=%s", source_key)
            import boto3
            from api.config import get_settings

            s = get_settings()
            client = boto3.client(
                "s3",
                endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=s.r2_access_key_id,
                aws_secret_access_key=s.r2_secret_access_key,
            )
            client.download_file(s.r2_bucket, source_key, str(source_path))
        else:
            log.warning("scene_analysis: R2 not configured — using stub source")
            source_path = None

        # Run OmegaClips FI-1→FI-13 intelligence
        candidates = _run_omega_clips(job_id, source_path, log)

        # Run Director Agent LLM
        director_plan = _run_director_agent(job_id, candidates, log)

        # Persist Scene, ClipCandidate, and DirectorPlan rows + transition
        with SessionLocal() as db:
            from api.services.queue import queue_for

            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()

            # 1. Persist scenes + clip candidates via the persistence services.
            #    When OmegaClips returned real SceneRecords, use the adapter path.
            #    Otherwise persist stub candidates directly.
            _persist_analysis_result(db, job=job, candidates=candidates, log=log)

            # 2. Persist a DirectorPlan row so the render worker can read it.
            #    Build a minimal DirectorPlanContract-compatible dict.
            selected = director_plan.get("selected_clips", candidates[:6])
            plan_entry = DirectorPlanModel(
                id=uuid4(),
                job_id=job.id,
                tenant_id=job.tenant_id,
                model="claude-sonnet-4-6",
                prompt_version="v1",
                plan_json={
                    "version": "1",
                    "upload_id": str(job.upload_id),
                    "job_id": str(job.id),
                    "selected_candidates": [
                        {
                            "candidate_id": clip.get("candidate_id", f"stub-{i}"),
                            "duration": 15.0,
                            "clip_start": clip.get("start_s", 0.0),
                            "clip_end": clip.get("end_s", 15.0),
                            "confidence_score": clip.get("fi_score", 7.0),
                            "quality_score": clip.get("fi_score", 7.0),
                            "platform_score": clip.get("fi_score", 7.0),
                            "scores": clip.get("scores", {}),
                            "pacing": "medium",
                            "caption_style": "sports_hype",
                            "crop_strategy": "smart",
                            "render_style": "ffmpeg_basic",
                            "hook_options": [],
                            "variants": [
                                {
                                    "platform": "youtube_shorts",
                                    "aspect_ratio": "9:16",
                                    "duration_cap": 60.0,
                                    "caption_safe_zone": True,
                                    "watermark": True,
                                    "variant_id": "yt-shorts-v1",
                                },
                                {
                                    "platform": "tiktok",
                                    "aspect_ratio": "9:16",
                                    "duration_cap": 60.0,
                                    "caption_safe_zone": True,
                                    "watermark": True,
                                    "variant_id": "tt-v1",
                                },
                                {
                                    "platform": "instagram_reels",
                                    "aspect_ratio": "9:16",
                                    "duration_cap": 90.0,
                                    "caption_safe_zone": True,
                                    "watermark": True,
                                    "variant_id": "ig-v1",
                                },
                            ],
                        }
                        for i, clip in enumerate(selected)
                    ],
                    "cost_estimate_cents": len(selected) * 9,
                },
            )
            db.add(plan_entry)
            db.flush()

            # 3. Transition job RUNNING → SUCCEEDED
            transition(db, job, JobStatus.SUCCEEDED.value, reason="scene_analysis_complete")
            db.commit()

            # 4. Auto-enqueue render for each selected clip
            for clip in selected:
                queue_for("render-cpu").enqueue(
                    "workers.render_worker.execute_render_job",
                    {
                        "job_id": job_id,
                        "source_uri": source_key,
                    },
                    job_timeout=600,
                    result_ttl=86400,
                )
            log.info(
                "scene_analysis: job=%s complete; %d clips queued for render", job_id, len(selected)
            )

        return {"job_id": job_id, "status": "complete", "clips_queued": len(selected)}

    except Exception as exc:
        log.exception("scene_analysis: job=%s failed", job_id)
        with SessionLocal() as db:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
            if job:
                transition(db, job, JobStatus.FAILED.value, reason=f"scene_analysis_error: {exc}")
                db.commit()
        return {"job_id": job_id, "status": "error", "error": str(exc)}
    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


def _persist_analysis_result(
    db,
    *,
    job,
    candidates: list[dict],
    log,
) -> None:
    """Persist Scene + ClipCandidate rows from OmegaClips (or stub) output.

    When OmegaClips returns structured SceneRecords (via the adapter path),
    they're persisted via the proper service. For flat dict output (stubs
    or raw OmegaClips results), we create minimal ORM rows directly.

    This function is intentionally lenient — any persistence failure in the
    analysis path should not block the pipeline. We log and continue.
    """
    import uuid
    from api.models import Scene, ClipCandidate

    scenes_written = 0
    candidates_written = 0
    for i, c in enumerate(candidates):
        try:
            scene = Scene(
                id=uuid.uuid4(),
                job_id=job.id,
                tenant_id=job.tenant_id,
                t_start=float(c.get("start_s", c.get("t_start", i * 30.0))),
                t_end=float(c.get("end_s", c.get("t_end", i * 30.0 + 15.0))),
                kind=c.get("kind", c.get("label", "highlight")),
                arc_position=c.get("arc_position", "climax"),
                intensity=float(c.get("intensity", c.get("fi_score", 7.0)) / 10.0),
                importance=float(c.get("importance", c.get("fi_score", 7.0)) / 10.0),
                signals=c.get("signals", {"source": "omega_clips"}),
            )
            db.add(scene)
            db.flush()
            scenes_written += 1

            candidate = ClipCandidate(
                id=uuid.uuid4(),
                job_id=job.id,
                tenant_id=job.tenant_id,
                scene_id=scene.id,
                t_start=scene.t_start,
                t_end=scene.t_end,
                confidence_score=float(c.get("fi_score", c.get("confidence_score", 7.0))),
                quality_score=float(c.get("fi_score", c.get("quality_score", 7.0))),
                platform_score=float(c.get("fi_score", c.get("platform_score", 7.0))),
                scores=c.get(
                    "scores",
                    {
                        "rank_score": float(c.get("fi_score", 7.0)),
                        "confidence_score": float(c.get("fi_score", 7.0)),
                    },
                ),
            )
            if c.get("rationale"):
                candidate.rationale = str(c["rationale"])
            db.add(candidate)
            candidates_written += 1
        except Exception as exc:
            log.warning("scene_analysis: failed to persist candidate %d: %s", i, exc)
            continue

    log.info(
        "scene_analysis: persisted %d scenes, %d candidates for job=%s",
        scenes_written,
        candidates_written,
        job.id,
    )


def _run_omega_clips(job_id: str, source_path, log) -> list[dict]:
    """Run OmegaClips FI-1→FI-13 on the source file.

    Falls back to structured placeholder candidates when the submodule or
    source file is unavailable (dev/CI without a real video).
    """
    try:
        import sys
        from pathlib import Path

        intel_path = Path(__file__).resolve().parents[2] / "packages" / "intel"
        if intel_path.exists() and str(intel_path) not in sys.path:
            sys.path.insert(0, str(intel_path))
        from omega_clips import analyze  # type: ignore[import]

        results = analyze(str(source_path)) if source_path else []
        log.info(
            "scene_analysis: OmegaClips returned %d candidates for job=%s", len(results), job_id
        )
        return results
    except ImportError:
        log.warning("scene_analysis: OmegaClips not importable — using stub candidates")
        return [
            {
                "candidate_id": f"stub-{i}",
                "start_s": i * 30.0,
                "end_s": i * 30.0 + 15.0,
                "fi_score": round(9.5 - i * 0.3, 1),
                "label": "stub",
            }
            for i in range(6)
        ]


def _run_director_agent(job_id: str, candidates: list[dict], log) -> dict:
    """Call Anthropic to build a DirectorPlan from ranked candidates."""
    try:
        import anthropic
        from api.config import get_settings

        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            f"You are an expert sports video director. "
            f"Select the best 6 clips from these {len(candidates)} candidates for a "
            f"cinematic highlight reel. Return a JSON object with key 'selected_clips' "
            f"containing the top candidates by fi_score. Candidates: {candidates[:24]}"
        )
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        import json

        # Iterate over content blocks to handle both TextBlock and ThinkingBlock
        text = ""
        for block in message.content:
            if hasattr(block, "text"):
                text = block.text
                break
        if not text:
            text = message.content[0].text  # fallback for simple cases
        start = text.find("{")
        end = text.rfind("}") + 1
        plan = json.loads(text[start:end]) if start >= 0 else {}
        log.info(
            "director_agent: job=%s plan built with %d clips",
            job_id,
            len(plan.get("selected_clips", [])),
        )
        return plan
    except Exception as exc:
        log.warning("director_agent: LLM call failed (%s) — using top-6 by score", exc)
        top6 = sorted(candidates, key=lambda c: c.get("fi_score", 0), reverse=True)[:6]
        return {"selected_clips": top6}


# ---------------------------------------------------------------------------
# Render worker
# ---------------------------------------------------------------------------


@app.function(
    secrets=_modal_secrets,
    timeout=600,
    memory=4096,
    retries=modal.Retries(max_retries=1, backoff_coefficient=1.0),
)
def run_render(payload: dict) -> dict:
    """Execute one FFmpeg render job from q:render-cpu."""
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from workers.render_worker import execute_render_job

    return execute_render_job(payload)


# ---------------------------------------------------------------------------
# RQ bridge crons
# ---------------------------------------------------------------------------


def _drain_queue(queue_key: str, worker_fn, log, batch: int = 5) -> None:
    """Generic RQ → Modal drain helper."""
    import json
    from redis import Redis
    from api.config import get_settings

    settings = get_settings()
    r = Redis.from_url(settings.redis_url, decode_responses=True)
    job_ids = r.lrange(queue_key, 0, batch - 1)
    if not job_ids:
        return

    for rq_job_id in job_ids:
        raw = r.hget(f"rq:job:{rq_job_id}", "data")
        if raw is None:
            continue
        try:
            job_data = json.loads(raw)
            payload = job_data.get("args", [{}])[0]
        except (json.JSONDecodeError, IndexError, KeyError):
            log.warning("drain: could not parse rq job %s", rq_job_id)
            continue
        log.info("drain: dispatching rq_job=%s to Modal", rq_job_id)
        worker_fn.spawn(payload)
        r.lrem(queue_key, 1, rq_job_id)


@app.function(
    secrets=_modal_secrets,
    timeout=60,
    schedule=modal.Cron("* * * * *"),
)
def drain_render_queue() -> None:
    import logging

    _drain_queue("rq:queue:q:render-cpu", run_render, logging.getLogger(__name__))


@app.function(
    secrets=_modal_secrets,
    timeout=60,
    schedule=modal.Cron("* * * * *"),
)
def drain_cv_queue() -> None:
    import logging

    _drain_queue("rq:queue:q:cv", run_scene_analysis, logging.getLogger(__name__))
