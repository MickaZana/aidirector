"""End-to-end smoke probe.

Exercises the full FK chain: tenant -> user -> upload -> job -> scene ->
clip_candidate -> director_plan -> render_job -> render_output, plus emits
usage_events at each step. Also validates the Pydantic DirectorPlan contract
round-trips through JSON storage.

Then runs `alembic downgrade base` + `upgrade head` to prove migration
reversibility.

Writes a report to _probe_loop.out.
"""
import io
import json
import os
import sys
import traceback
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "_probe_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    if PROBE_DB.exists():
        PROBE_DB.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        log("alembic import failed:")
        log(traceback.format_exc())
        return 2

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    # 1) upgrade head
    _silent(lambda: command.upgrade(cfg, "head"))
    log("step 1: upgrade head OK")

    # 2) downgrade base
    _silent(lambda: command.downgrade(cfg, "base"))
    log("step 2: downgrade base OK")

    # 3) upgrade head again
    _silent(lambda: command.upgrade(cfg, "head"))
    log("step 3: re-upgrade head OK")

    # 4) sample insert chain
    from sqlalchemy import create_engine, inspect, select
    from sqlalchemy.orm import Session

    from api.models import (
        ClipCandidate,
        DirectorPlan as DirectorPlanRow,
        Job,
        RenderJob,
        RenderOutput,
        Scene,
        Tenant,
        Upload,
        UsageEvent,
        User,
    )
    from api.schemas.director_plan import (
        DirectorPlan,
        SelectedCandidate,
        Variant,
    )

    engine = create_engine(os.environ["DATABASE_URL"])

    with Session(engine) as db:
        tenant = Tenant(slug="user_demo", name="Demo Tenant", plan="creator")
        db.add(tenant)
        db.flush()

        user = User(
            tenant_id=tenant.id,
            clerk_user_id="user_demo_clerk",
            email="demo@aidirector.app",
            role="admin",
        )
        db.add(user)
        db.flush()

        upload = Upload(
            tenant_id=tenant.id,
            user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe/match.mp4",
            filename="match.mp4",
            bytes=104857600,
            duration_s=1800.0,
            sport="football",
            status="ready",
            upload_metadata={"content_type": "video/mp4"},
        )
        db.add(upload)
        db.flush()

        job = Job(
            tenant_id=tenant.id,
            upload_id=upload.id,
            intent="analyze",
            status="succeeded",
            intel_submodule_sha="78fcd57",
            cost_budget_cents=30,
            cost_actual_cents=12,
        )
        db.add(job)
        db.flush()

        scene = Scene(
            job_id=job.id,
            tenant_id=tenant.id,
            t_start=120.5,
            t_end=132.0,
            kind="goal",
            arc_position="climax",
            intensity=0.92,
            importance=0.95,
            signals={
                "scoreboard_delta": {"home": 1, "away": 0},
                "audio_intensity": 0.88,
                "rationale": "scoreboard increment + crowd peak + replay confirm",
            },
        )
        db.add(scene)
        db.flush()

        candidate = ClipCandidate(
            job_id=job.id,
            tenant_id=tenant.id,
            scene_id=scene.id,
            t_start=118.0,
            t_end=134.0,
            confidence_score=0.91,
            quality_score=0.87,
            platform_score=0.80,
            rationale="goal + crowd payoff + clear scoreboard",
            scores={"replay_density": 0.62, "commentator_spike": 0.81},
        )
        db.add(candidate)
        db.flush()

        plan = DirectorPlan(
            upload_id=str(upload.id),
            job_id=str(job.id),
            model="claude-sonnet-4-6",
            prompt_version="v1",
            platform_targets=["youtube_shorts", "tiktok", "instagram_reels"],
            selected_candidates=[
                SelectedCandidate(
                    candidate_id=str(candidate.id),
                    reason_selected="goal + crowd payoff + clear scoreboard",
                    confidence_score=0.91,
                    quality_score=0.87,
                    platform_score=0.80,
                    clip_start=118.0,
                    clip_end=134.0,
                    duration=16.0,
                    pacing="fast",
                    caption_style="sports_hype",
                    crop_strategy="action",
                    render_style="sports_hype",
                    hook_options=["OFF THE BENCH AND IT'S IN", "70 SECONDS AFTER COMING ON"],
                    variants=[
                        Variant(
                            variant_id="v1",
                            platform="youtube_shorts",
                            aspect_ratio="9:16",
                            duration_cap=60,
                        ),
                        Variant(
                            variant_id="v2",
                            platform="tiktok",
                            aspect_ratio="9:16",
                            duration_cap=60,
                        ),
                        Variant(
                            variant_id="v3",
                            platform="instagram_reels",
                            aspect_ratio="9:16",
                            duration_cap=90,
                        ),
                    ],
                )
            ],
            cost_estimate_cents=24,
        )
        plan_row = DirectorPlanRow(
            job_id=job.id,
            tenant_id=tenant.id,
            model=plan.model,
            prompt_version=plan.prompt_version,
            plan_json=plan.model_dump(mode="json"),
        )
        db.add(plan_row)
        db.flush()

        rj = RenderJob(
            job_id=job.id,
            tenant_id=tenant.id,
            candidate_id=candidate.id,
            pipeline="ffmpeg_finisher",
            platform="youtube_shorts",
            status="succeeded",
            settings={"aspect_ratio": "9:16", "duration_cap": 60, "watermark": True},
            cost_cents=6,
        )
        db.add(rj)
        db.flush()

        ro = RenderOutput(
            render_job_id=rj.id,
            tenant_id=tenant.id,
            r2_key=f"tenant/{tenant.id}/render/{rj.id}/yt_shorts.mp4",
            aspect_ratio="9:16",
            duration_s=16.0,
            bytes=2400000,
            output_metadata={"crf": 21, "bitrate_kbps": 8000},
        )
        db.add(ro)
        db.flush()

        for event_type, qty, unit, meta in (
            ("upload_created", 1.0, "upload", {"size_bytes": upload.bytes}),
            ("analysis_started", 1.0, "job", {}),
            ("analysis_completed", 1800.0, "video_seconds", {"scene_count": 1}),
            ("candidate_created", 1.0, "candidate", {}),
            ("director_plan_created", 1.0, "plan", {"variants": 3}),
            ("render_started", 1.0, "render", {}),
            ("render_completed", 16.0, "clip_seconds", {"platform": "youtube_shorts"}),
            ("export_created", 1.0, "export", {}),
        ):
            db.add(
                UsageEvent(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    upload_id=upload.id,
                    job_id=job.id,
                    event_type=event_type,
                    quantity=qty,
                    unit=unit,
                    event_metadata=meta,
                )
            )

        db.commit()

    # 5) verify counts
    with Session(engine) as db:
        from sqlalchemy import func

        counts = {}
        for cls in (Tenant, User, Upload, Job, Scene, ClipCandidate,
                    DirectorPlanRow, RenderJob, RenderOutput, UsageEvent):
            counts[cls.__tablename__] = db.execute(
                select(func.count()).select_from(cls)
            ).scalar()
        log("row_counts=" + json.dumps(counts))

        # 6) round-trip plan
        plan_row = db.execute(select(DirectorPlanRow)).scalar_one()
        recovered = DirectorPlan.model_validate(plan_row.plan_json)
        log(f"recovered_plan.job_id={recovered.job_id}")
        log(f"recovered_plan.candidates={len(recovered.selected_candidates)}")
        log(f"recovered_plan.variants={sum(len(c.variants) for c in recovered.selected_candidates)}")
        log(f"recovered_plan.first_render_style={recovered.selected_candidates[0].render_style}")

    log("OK")
    return 0


def _silent(fn) -> None:
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        fn()
    finally:
        sys.stdout = saved_out
        sys.stderr = saved_err


if __name__ == "__main__":
    sys.exit(main())
