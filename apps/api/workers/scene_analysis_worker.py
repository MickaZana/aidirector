"""RQ scene-analysis worker — local-dev equivalent of modal_app.py:run_scene_analysis.

Called by RQ when a job is dequeued from q:cv. The function is registered
by name so the `rq worker` process resolves it the same way as the Modal
cron bridge.

Payload contract (dict):
    job_id  str  — UUID of the Job row to analyse

Returns a summary dict (stored in rq Job.result for polling).

Pipeline:
  1. Load Job + Upload from DB
  2. Download source file from R2 → /tmp/
  3. Run OmegaClips intelligence (or stub fallback) → Scene + ClipCandidate rows
  4. Call Director Agent LLM (or deterministic fallback) → DirectorPlan
  5. Persist Scene, ClipCandidate, and DirectorPlan rows
  6. Transition Job RUNNING → SUCCEEDED
  7. Enqueue render jobs to q:render-cpu for each selected clip
"""

from __future__ import annotations

import logging
import uuid as _uuid
from pathlib import Path

import sentry_sdk
from sqlalchemy import select

from api.config import get_settings
from api.db import SessionLocal
from api.models import DirectorPlan as DirectorPlanModel
from api.models import Job, JobStatus, Upload
from api.services.queue import queue_for
from api.services.state_transitions import transition

log = logging.getLogger(__name__)


def run_analysis(payload: dict) -> dict:
    """Entry point for RQ. `payload` matches the contract in the module docstring."""
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env)

    job_id: str = payload["job_id"]
    log.info("scene_analysis: job=%s starting", job_id)

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

            client = boto3.client(
                "s3",
                endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
            )
            client.download_file(settings.r2_bucket, source_key, str(source_path))
        else:
            log.warning("scene_analysis: R2 not configured — using stub source")
            source_path = None

        # Run OmegaClips FI-1→FI-13 intelligence (or stub fallback)
        candidates = _run_omega_clips(job_id, source_path, log, content_type=upload.sport)

        # Run Director Agent LLM (or deterministic fallback)
        director_plan = _run_director_agent(job_id, candidates, log, content_type=upload.sport)

        # Persist Scene, ClipCandidate, and DirectorPlan rows + transition
        with SessionLocal() as db:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()

            # 1. Persist scenes + clip candidates
            _persist_analysis_result(db, job=job, candidates=candidates, log=log)

            # 2. Persist a DirectorPlan row so the render worker can read it
            selected = director_plan.get("selected_clips", candidates[:6])
            plan_entry = DirectorPlanModel(
                id=_uuid.uuid4(),
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
                "scene_analysis: job=%s complete; %d clips queued for render",
                job_id,
                len(selected),
            )

        return {"job_id": job_id, "status": "complete", "clips_queued": len(selected)}

    except Exception as exc:
        log.exception("scene_analysis: job=%s failed", job_id)
        with SessionLocal() as db:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
            if job:
                transition(
                    db,
                    job,
                    JobStatus.FAILED.value,
                    reason=f"scene_analysis_error: {exc}",
                )
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

    This function mirrors modal_app.py:_persist_analysis_result. Any
    persistence failure in the analysis path should not block the pipeline
    — we log and continue.
    """
    import uuid as _uuid

    from api.models import ClipCandidate, Scene

    scenes_written = 0
    candidates_written = 0
    for i, c in enumerate(candidates):
        try:
            scene = Scene(
                id=_uuid.uuid4(),
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
                id=_uuid.uuid4(),
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


def _run_omega_clips(job_id: str, source_path, log, content_type: str = "football") -> list[dict]:
    """Run OmegaClips FI-1→FI-13 on the source file, falling back to stubs."""
    if content_type == "podcast":
        raise RuntimeError("Podcast analysis requires a diarization/transcription adapter")
    try:
        intel_path = Path(__file__).resolve().parents[3] / "packages" / "intel"
        if intel_path.exists() and str(intel_path) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(intel_path))
        from omega_clips import analyze  # type: ignore[import]

        results = analyze(str(source_path)) if source_path else []
        log.info(
            "scene_analysis: OmegaClips returned %d candidates for job=%s",
            len(results),
            job_id,
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


def _run_director_agent(job_id: str, candidates: list[dict], log, content_type: str = "football") -> dict:
    """Call Anthropic to build a DirectorPlan from ranked candidates.

    Falls back to deterministic top-6 by score when the LLM is unavailable.
    """
    try:
        import json

        import anthropic

        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt_subject = "conversation video director" if content_type == "podcast" else "sports video director"
        prompt = (
            f"You are an expert {prompt_subject}. "
            f"Select the best 6 clips from these {len(candidates)} candidates "
            f"for a cinematic highlight reel. Return a JSON object with key "
            f"'selected_clips' containing the top candidates by fi_score. "
            f"Candidates: {candidates[:24]}"
        )
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        # Iterate over content blocks to handle both TextBlock and ThinkingBlock
        _text = ""
        for _block in message.content:
            if hasattr(_block, "text"):
                _text = _block.text
                break
        if not _text:
            _text = message.content[0].text
        start = _text.find("{")
        end = _text.rfind("}") + 1
        plan = json.loads(_text[start:end]) if start >= 0 else {}
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
