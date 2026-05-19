"""Phase 4 integration probe — deterministic DirectorPlan + sandboxed enrichment.

Proves the analyze → rank → direct chain:

  upload → analysis job → scenes persisted (Phase 2) → candidates persisted
   (Phase 3) → deterministic build_director_plan → optional enrichment
   → validated DirectorPlan → director_plans row → usage_events written

Three sub-tests inside one probe (each must pass):

  A) Deterministic-only build → persist → DB round-trip.
     enricher disabled. Plan must validate, have ≥1 candidate, variants
     for YT Shorts / TikTok / Reels, and emit DIRECTOR_PLAN_CREATED.

  B) Sandboxed enrichment with a valid enricher_fn.
     Returns whitelisted suggestions (rewrite reason, suggest pacing,
     supply hook_options). Plan must validate; the enriched fields must
     show in the output.

  C) Sandboxed enrichment with a HALLUCINATED enricher_fn.
     Returns invalid enums, oversized strings, AND attempts to override
     protected fields (timestamps, candidate_id). Plan must equal the
     deterministic baseline (or accept only the whitelisted-and-valid
     subset). Protected fields must be unchanged.

Writes a report to _probe_phase4_loop.out.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase4_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def _silent(fn) -> None:
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        fn()
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    log("step: start")
    if PROBE_DB.exists():
        PROBE_DB.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    _silent(lambda: command.upgrade(cfg, "head"))
    log("alembic upgrade head: OK")

    # --- common setup: analyzer + ranker + persistence -------------------
    from api.services.intel.scene_analysis_adapter import analyze_video
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.intel.capability_registry import SceneRecord

    fixture = [
        {"t":  5.0, "raw_text": "0  -  0    00:30", "ocr_confidence": 0.85},
        {"t":  8.0, "raw_text": "0  -  0    01:00", "ocr_confidence": 0.85},
        {"t": 12.0, "raw_text": "0  -  0    01:30", "ocr_confidence": 0.85},
        {"t": 16.0, "raw_text": "1  -  0    01:35", "ocr_confidence": 0.86},
        {"t": 20.0, "raw_text": "1  -  0    01:40", "ocr_confidence": 0.86},
        {"t": 22.0, "raw_text": "1  -  0    02:00", "ocr_confidence": 0.86},
        {"t": 26.0, "raw_text": "1  -  0    02:30", "ocr_confidence": 0.87},
        {"t": 32.0, "raw_text": "1  -  0    03:00", "ocr_confidence": 0.86},
        {"t": 38.0, "raw_text": "1  -  0    03:30", "ocr_confidence": 0.86},
        {"t": 44.0, "raw_text": "1  -  1    04:00", "ocr_confidence": 0.84},
        {"t": 48.0, "raw_text": "1  -  1    04:30", "ocr_confidence": 0.84},
        {"t": 50.0, "raw_text": "1  -  1    04:45", "ocr_confidence": 0.85},
        {"t": 54.0, "raw_text": "1  -  1    05:00", "ocr_confidence": 0.85},
    ]
    analysis = analyze_video(
        upload_id="probe-upload-phase4",
        source_uri="fixture://memory",
        fixture_reads=fixture,
    )
    log(f"analyzer.scene_count={len(analysis.scenes)}")
    if len(analysis.scenes) < 2:
        log("FAIL: need ≥2 scenes from fixture analyzer")
        return 2

    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session
    from api.models import (
        ClipCandidate,
        DirectorPlan as DirectorPlanRow,
        Job,
        JobStatus,
        Tenant,
        Upload,
        UploadStatus,
        UsageEvent,
        UsageEventType,
        User,
    )
    from api.services.clip_candidate_persistence import persist_clip_candidates
    from api.services.scene_persistence import persist_scene_analysis
    from api.services.usage_events import emit_usage_event
    from api.services.director_plan_builder import (
        build_director_plan,
        DEFAULT_DIRECTOR_MODEL,
    )
    from api.services.director_plan_persistence import persist_director_plan
    from api.services.intel.director_agent_adapter import enrich_director_plan
    from api.schemas.director_plan import DirectorPlan

    engine = create_engine(os.environ["DATABASE_URL"])
    PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels"]

    with Session(engine) as db:
        tenant = Tenant(slug="phase4_probe", name="Phase 4 Probe", plan="creator")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            clerk_user_id="user_probe4_clerk",
            email="probe4@aidirector.app",
            role="admin",
        )
        db.add(user)
        db.flush()
        upload = Upload(
            tenant_id=tenant.id,
            user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe4/match.mp4",
            filename="match.mp4",
            bytes=104857600,
            duration_s=60.0,
            sport="football",
            status=UploadStatus.READY.value,
            upload_metadata={"content_type": "video/mp4"},
        )
        db.add(upload)
        db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id,
            event_type=UsageEventType.UPLOAD_CREATED, unit="upload",
            metadata={"size_bytes": upload.bytes},
        )

        job = Job(
            tenant_id=tenant.id,
            upload_id=upload.id,
            intent="analyze",
            status=JobStatus.RUNNING.value,
            cost_budget_cents=30,
        )
        db.add(job)
        db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id, job_id=job.id,
            event_type=UsageEventType.ANALYSIS_STARTED, unit="job",
            metadata={"intent": job.intent},
        )

        scene_rows = persist_scene_analysis(db, job=job, result=analysis)
        log(f"persisted_scene_rows={len(scene_rows)}")

        ranked = rank_clip_candidates(
            upload_id=str(upload.id),
            scenes=[
                SceneRecord(
                    t_start=s.t_start, t_end=s.t_end, kind=s.kind,
                    arc_position=s.arc_position, intensity=s.intensity,
                    importance=s.importance, signals=s.signals,
                )
                for s in scene_rows
            ],
        )
        candidate_rows = persist_clip_candidates(
            db, job=job, scenes_in_order=scene_rows, ranked=ranked
        )
        log(f"persisted_candidate_rows={len(candidate_rows)}")

        # --- sub-test A: deterministic-only build ------------------------
        plan_a = build_director_plan(
            upload_id=str(upload.id),
            job_id=str(job.id),
            candidates=candidate_rows,
            platform_targets=PLATFORMS,
        )
        log(f"A.plan.model={plan_a.model}")
        log(f"A.plan.selected_candidates={len(plan_a.selected_candidates)}")
        log(f"A.plan.platform_targets={plan_a.platform_targets}")
        log(f"A.plan.cost_estimate_cents={plan_a.cost_estimate_cents}")
        for i, c in enumerate(plan_a.selected_candidates):
            variants = [(v.platform, v.aspect_ratio, v.duration_cap) for v in c.variants]
            log(
                f"A.candidate[{i}]: id={c.candidate_id} "
                f"clip={c.clip_start}->{c.clip_end} dur={c.duration} "
                f"pacing={c.pacing} caption={c.caption_style} "
                f"crop={c.crop_strategy} render={c.render_style} variants={variants}"
            )

        if plan_a.model != DEFAULT_DIRECTOR_MODEL:
            log(f"FAIL.A: deterministic plan.model='{plan_a.model}', expected '{DEFAULT_DIRECTOR_MODEL}'")
            return 3
        if len(plan_a.selected_candidates) < 1:
            log("FAIL.A: deterministic plan has zero selected candidates")
            return 4
        platforms_seen = {
            v.platform for c in plan_a.selected_candidates for v in c.variants
        }
        required = {"youtube_shorts", "tiktok", "instagram_reels"}
        if not required.issubset(platforms_seen):
            log(f"FAIL.A: missing variants for {required - platforms_seen}")
            return 5

        # Identity enrichment (disabled) — must return the same plan
        plan_a_ident = enrich_director_plan(plan_a, enabled=False, enricher_fn=None)
        if plan_a_ident.model_dump(mode="python") != plan_a.model_dump(mode="python"):
            log("FAIL.A: disabled enrichment changed the plan (it should be identity)")
            return 6

        persist_director_plan(db, job=job, plan=plan_a_ident)
        db.commit()

        # --- sub-test B: valid sandboxed enrichment ----------------------
        def valid_enricher(req: dict) -> dict:
            return {
                "candidates": {
                    c["candidate_id"]: {
                        "reason_selected": "rewritten by valid enricher",
                        "pacing": "medium",
                        "caption_style": "documentary",
                        "render_style": "sports_hype",
                        "hook_options": ["FIRST HOOK", "SECOND HOOK"],
                    }
                    for c in req["candidates"]
                }
            }

        plan_b = build_director_plan(
            upload_id=str(upload.id),
            job_id=str(job.id),
            candidates=candidate_rows,
            platform_targets=PLATFORMS,
        )
        plan_b_enriched = enrich_director_plan(
            plan_b, enabled=True, enricher_fn=valid_enricher, model="claude-test-fake"
        )
        log(f"B.enriched.model={plan_b_enriched.model}")
        for i, c in enumerate(plan_b_enriched.selected_candidates):
            log(
                f"B.candidate[{i}]: pacing={c.pacing} caption={c.caption_style} "
                f"render={c.render_style} reason='{c.reason_selected}' "
                f"hooks={c.hook_options}"
            )

        # Check enrichment landed for every candidate
        for c in plan_b_enriched.selected_candidates:
            if c.reason_selected != "rewritten by valid enricher":
                log("FAIL.B: reason_selected not enriched")
                return 7
            if c.pacing != "medium":
                log("FAIL.B: pacing not enriched")
                return 8
            if c.render_style != "sports_hype":
                log("FAIL.B: render_style not enriched")
                return 9
            if c.hook_options != ["FIRST HOOK", "SECOND HOOK"]:
                log("FAIL.B: hook_options not enriched")
                return 10
        if plan_b_enriched.model != "claude-test-fake":
            log("FAIL.B: enriched plan model field not updated")
            return 11

        # Protected fields must be unchanged from deterministic baseline.
        for det, enr in zip(plan_b.selected_candidates, plan_b_enriched.selected_candidates):
            if (det.candidate_id, det.clip_start, det.clip_end, det.duration) != (
                enr.candidate_id, enr.clip_start, enr.clip_end, enr.duration,
            ):
                log("FAIL.B: protected timestamp/id fields drifted under valid enrichment")
                return 12

        # --- sub-test C: hallucinated enrichment must be rejected --------
        def evil_enricher(req: dict) -> dict:
            return {
                "candidates": {
                    c["candidate_id"]: {
                        "reason_selected": "x" * 9999,            # too long
                        "pacing": "ultra_warp_speed",              # not in enum
                        "caption_style": "neon_skyboard",          # not in enum
                        "render_style": "ai_god_mode",             # not in enum
                        "hook_options": ["ok hook", "x" * 9999],  # one valid, one too long
                        # Attempts to override protected fields:
                        "clip_start": 0.0,
                        "clip_end": 999.0,
                        "candidate_id": "ATTACKER_OVERRIDE",
                        "confidence_score": 1.0,
                    }
                    for c in req["candidates"]
                },
                # Top-level shape pollution:
                "evil_extra_field": "should be ignored",
                "selected_candidates": "should be ignored",
            }

        plan_c = build_director_plan(
            upload_id=str(upload.id),
            job_id=str(job.id),
            candidates=candidate_rows,
            platform_targets=PLATFORMS,
        )
        plan_c_enriched = enrich_director_plan(
            plan_c, enabled=True, enricher_fn=evil_enricher, model="claude-evil-fake"
        )
        for i, c in enumerate(plan_c_enriched.selected_candidates):
            log(
                f"C.candidate[{i}]: pacing={c.pacing} caption={c.caption_style} "
                f"render={c.render_style} hook_count={len(c.hook_options)} "
                f"reason_len={len(c.reason_selected)}"
            )

        for det, enr in zip(plan_c.selected_candidates, plan_c_enriched.selected_candidates):
            # Invalid enums must be silently rejected → values stay deterministic.
            if enr.pacing != det.pacing:
                log("FAIL.C: invalid pacing accepted")
                return 20
            if enr.caption_style != det.caption_style:
                log("FAIL.C: invalid caption_style accepted")
                return 21
            if enr.render_style != det.render_style:
                log("FAIL.C: invalid render_style accepted")
                return 22
            # Oversized reason rejected → stays deterministic
            if enr.reason_selected != det.reason_selected:
                log("FAIL.C: oversized reason accepted")
                return 23
            # Oversized hooks dropped, one valid kept
            if enr.hook_options != ["ok hook"]:
                log(f"FAIL.C: hook_options not sanitized: {enr.hook_options}")
                return 24
            # Protected fields must be untouched
            if (enr.candidate_id, enr.clip_start, enr.clip_end, enr.confidence_score) != (
                det.candidate_id, det.clip_start, det.clip_end, det.confidence_score,
            ):
                log("FAIL.C: protected field mutated by evil enricher")
                return 25

        # Top-level shape pollution must not appear on the validated plan
        if len(plan_c_enriched.selected_candidates) != len(plan_c.selected_candidates):
            log("FAIL.C: enricher injected/removed candidates")
            return 26

        log("sub-tests A/B/C: OK")

    # --- DB verification --------------------------------------------------
    with Session(engine) as db:
        plan_count = db.execute(select(func.count()).select_from(DirectorPlanRow)).scalar()
        log(f"db.director_plans_count={plan_count}")
        if plan_count != 1:
            log(f"FAIL: expected 1 persisted plan, got {plan_count}")
            return 30

        plan_row = db.execute(select(DirectorPlanRow)).scalar_one()
        log(f"db.plan.model={plan_row.model}")
        log(f"db.plan.candidate_count={len(plan_row.plan_json.get('selected_candidates', []))}")
        log(
            f"db.plan.variant_count={sum(len(c.get('variants', [])) for c in plan_row.plan_json.get('selected_candidates', []))}"
        )

        # Round-trip through the contract
        recovered = DirectorPlan.model_validate(plan_row.plan_json)
        log(f"recovered.upload_id={recovered.upload_id}")
        log(f"recovered.job_id={recovered.job_id}")
        log(f"recovered.platform_targets={recovered.platform_targets}")

        usage_rows = db.execute(select(UsageEvent)).scalars().all()
        events = sorted({(u.event_type, u.unit, float(u.quantity)) for u in usage_rows})
        log(f"db.usage_events={json.dumps(events)}")
        if not any(e[0] == "director_plan_created" for e in events):
            log("FAIL: director_plan_created usage event missing")
            return 31

        # Tenant + job linkage
        if plan_row.tenant_id is None or plan_row.job_id is None:
            log("FAIL: persisted plan missing tenant/job linkage")
            return 32

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
