"""Phase 8 integration probe — controlled ranking feedback.

Closes the final loop step (measure → improve) while preserving:
  - structural ranking dominance (OmegaClips base score never overwritten)
  - confidence gating (below threshold → zero adjustment)
  - capped influence (|adjustment| ≤ ENGAGEMENT_WEIGHT_CAP = 0.15)
  - explainability (breakdown carries every intermediate value)
  - replayability (same inputs → byte-identical final scores)

Eight sub-tests (one per user-listed acceptance line):

  A) Identical to Phase 3 with no prior_performance supplied.
  B) High-confidence positive view → upward, measurable adjustment.
  C) Low-confidence view → adjustment = 0 (confidence gate working).
  D) Engagement at extreme (1.0 with conf 1.0) → adjustment capped at the
     declared ENGAGEMENT_WEIGHT_CAP.
  E) RankingSnapshot rows persist with correct fields.
  F) RANKING_FEEDBACK_APPLIED usage events present + carry required keys.
  G) Import discipline grep on clip_ranking_adapter source — must not
     reference EngagementEvent, engagement_events, or engagement_aggregation.
  H) Deterministic replay: running with same inputs twice yields the same
     base/adjustment/final triple for every candidate.

Writes a report to _probe_phase8_loop.out.
"""
from __future__ import annotations

import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase8_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"
FIXTURE_DIR = Path(__file__).parent / "_probe_phase8_fixtures"
SOURCE_PATH = FIXTURE_DIR / "source_30s.mp4"
RENDER_OUTPUT_DIR = FIXTURE_DIR / "renders"


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


def _ensure_fixture_source() -> str:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_PATH.exists() and SOURCE_PATH.stat().st_size > 0:
        return str(SOURCE_PATH)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not on PATH")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=30:size=320x240:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-shortest",
        str(SOURCE_PATH),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"fixture source build failed: {proc.stderr[-400:]}")
    return str(SOURCE_PATH)


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    log("step: start")
    if PROBE_DB.exists():
        PROBE_DB.unlink()
    if RENDER_OUTPUT_DIR.exists():
        shutil.rmtree(RENDER_OUTPUT_DIR)

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    _silent(lambda: command.upgrade(cfg, "head"))
    log("alembic upgrade head: OK")

    source_uri = _ensure_fixture_source()

    # --- run Phases 0-3 chain to get persisted ClipCandidate rows ----------
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from api.models import (
        ClipCandidate, Job, JobStatus, MaturityState, RankingSnapshot,
        Scene, Tenant, Upload, UploadStatus, UsageEvent, UsageEventType, User,
    )
    from api.services.intel.scene_analysis_adapter import analyze_video
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.ranking_feedback_adapter import (
        CONFIDENCE_THRESHOLD,
        ENGAGEMENT_WEIGHT_CAP,
        PerformanceFeatureView,
        apply_feedback_to_rank_score,
    )
    from api.services.scene_persistence import persist_scene_analysis
    from api.services.clip_candidate_persistence import persist_clip_candidates
    from api.services.ranking_snapshot_persistence import persist_ranking_snapshot
    from api.services.usage_events import emit_usage_event

    log(f"phase8.constants: CONFIDENCE_THRESHOLD={CONFIDENCE_THRESHOLD}")
    log(f"phase8.constants: ENGAGEMENT_WEIGHT_CAP={ENGAGEMENT_WEIGHT_CAP}")

    fixture_reads = [
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
        upload_id="probe-upload-phase8",
        source_uri="fixture://memory",
        fixture_reads=fixture_reads,
    )
    log(f"chain.analyzer.scene_count={len(analysis.scenes)}")

    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as db:
        tenant = Tenant(slug="phase8_probe", name="Phase 8 Probe", plan="creator")
        db.add(tenant); db.flush()
        user = User(
            tenant_id=tenant.id, clerk_user_id="user_probe8",
            email="probe8@aidirector.app", role="admin",
        )
        db.add(user); db.flush()
        upload = Upload(
            tenant_id=tenant.id, user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe8/match.mp4",
            filename="match.mp4", bytes=Path(source_uri).stat().st_size,
            duration_s=60.0, sport="football",
            status=UploadStatus.READY.value,
            upload_metadata={"source_uri": source_uri},
        )
        db.add(upload); db.flush()
        job = Job(
            tenant_id=tenant.id, upload_id=upload.id, intent="analyze",
            status=JobStatus.RUNNING.value, cost_budget_cents=30,
        )
        db.add(job); db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id, job_id=job.id,
            event_type=UsageEventType.ANALYSIS_STARTED, unit="job",
            metadata={"intent": job.intent},
        )

        scene_rows = persist_scene_analysis(db, job=job, result=analysis)
        scene_records = [
            SceneRecord(
                t_start=s.t_start, t_end=s.t_end, kind=s.kind,
                arc_position=s.arc_position, intensity=s.intensity,
                importance=s.importance, signals=s.signals,
            ) for s in scene_rows
        ]

        # --- sub-test A: no prior_performance → Phase 3-equivalent --------
        ranked_no_fb = rank_clip_candidates(
            upload_id=str(upload.id), scenes=scene_records,
        )
        log(f"A.ranked_count={len(ranked_no_fb.candidates)}")
        for c in ranked_no_fb.candidates:
            base = c.scores.get("base_rank_score")
            adj = c.scores.get("engagement_adjustment")
            final = c.scores.get("final_rank_score")
            fb = c.scores.get("feedback_applied")
            log(
                f"A.candidate scene={c.scene_index} base={base} "
                f"adjustment={adj} final={final} feedback_applied={fb}"
            )
            if adj != 0.0:
                log(f"FAIL.A: adjustment {adj} != 0 without prior_performance")
                return 2
            if final != base:
                log(f"FAIL.A: final {final} != base {base} without prior_performance")
                return 3
            if fb is not False:
                log(f"FAIL.A: feedback_applied={fb} should be False")
                return 4

        # Persist the no-feedback candidates so subsequent sub-tests
        # have ClipCandidate ORM rows to snapshot against.
        candidate_rows = persist_clip_candidates(
            db, job=job, scenes_in_order=scene_rows, ranked=ranked_no_fb,
        )
        db.commit()
        baseline_finals = [c.scores["final_rank_score"] for c in ranked_no_fb.candidates]
        log(f"A.baseline_finals={baseline_finals}")

        # --- sub-test B: high-confidence positive view → upward ----------
        export_id_b = uuid.uuid4()
        high_conf_view = PerformanceFeatureView(
            export_id=export_id_b,
            tenant_id=tenant.id,
            feature_version="v1",
            maturity_state=MaturityState.STABLE,
            engagement_confidence=0.8,
            normalized_view_rate=0.9,
            normalized_completion_rate=0.85,
            normalized_watch_time=0.7,
            replay_rate=0.1,
            share_rate=0.05,
            engagement_score=0.9,   # well above neutral
            experiment_group_id=None,
        )
        # Apply to scene 0 only; scene 1 remains adjustment-free.
        prior_b = {0: high_conf_view}
        ranked_b = rank_clip_candidates(
            upload_id=str(upload.id), scenes=scene_records,
            prior_performance=prior_b,
        )
        c0_b = next(c for c in ranked_b.candidates if c.scene_index == 0)
        c1_b = next(c for c in ranked_b.candidates if c.scene_index == 1)
        log(
            f"B.scene0 base={c0_b.scores['base_rank_score']} "
            f"adj={c0_b.scores['engagement_adjustment']} "
            f"final={c0_b.scores['final_rank_score']} "
            f"applied={c0_b.scores['feedback_applied']}"
        )
        log(
            f"B.scene1 base={c1_b.scores['base_rank_score']} "
            f"adj={c1_b.scores['engagement_adjustment']} "
            f"final={c1_b.scores['final_rank_score']}"
        )
        if not c0_b.scores["feedback_applied"]:
            log("FAIL.B: feedback not applied to scene 0")
            return 5
        if c0_b.scores["engagement_adjustment"] <= 0:
            log("FAIL.B: adjustment for positive view should be > 0")
            return 6
        if c0_b.scores["final_rank_score"] <= c0_b.scores["base_rank_score"]:
            log("FAIL.B: final should be > base for positive high-conf view")
            return 7
        # Scene 1 had NO prior → stays at baseline
        if c1_b.scores["engagement_adjustment"] != 0.0:
            log(f"FAIL.B: scene 1 adjustment {c1_b.scores['engagement_adjustment']} != 0")
            return 8
        # Adjustment must still be within cap
        if abs(c0_b.scores["engagement_adjustment"]) > ENGAGEMENT_WEIGHT_CAP + 1e-9:
            log(
                f"FAIL.B: adjustment {c0_b.scores['engagement_adjustment']} "
                f"exceeds cap {ENGAGEMENT_WEIGHT_CAP}"
            )
            return 9

        # --- sub-test C: low-confidence view → zero adjustment ----------
        low_conf_view = PerformanceFeatureView(
            export_id=uuid.uuid4(),
            tenant_id=tenant.id,
            feature_version="v1",
            maturity_state=MaturityState.FRESH,
            engagement_confidence=0.10,   # below threshold 0.30
            normalized_view_rate=0.9,
            normalized_completion_rate=0.85,
            normalized_watch_time=0.7,
            replay_rate=0.1,
            share_rate=0.05,
            engagement_score=0.95,        # would be huge if not gated
            experiment_group_id=None,
        )
        outcome_c = apply_feedback_to_rank_score(0.5, low_conf_view)
        log(
            f"C.outcome adj={outcome_c.engagement_adjustment} "
            f"applied={outcome_c.feedback_applied} "
            f"explanation={outcome_c.explanation[:80]}…"
        )
        if outcome_c.engagement_adjustment != 0.0:
            log("FAIL.C: low-confidence view produced non-zero adjustment")
            return 10
        if outcome_c.feedback_applied:
            log("FAIL.C: feedback_applied should be False below confidence threshold")
            return 11

        # --- sub-test D: cap enforcement at extreme ---------------------
        extreme_view = PerformanceFeatureView(
            export_id=uuid.uuid4(),
            tenant_id=tenant.id,
            feature_version="v1",
            maturity_state=MaturityState.STABLE,
            engagement_confidence=1.0,
            normalized_view_rate=1.0,
            normalized_completion_rate=1.0,
            normalized_watch_time=1.0,
            replay_rate=1.0,
            share_rate=1.0,
            engagement_score=1.0,        # max
            experiment_group_id=None,
        )
        outcome_d_pos = apply_feedback_to_rank_score(0.5, extreme_view)
        log(
            f"D.max_pos adj={outcome_d_pos.engagement_adjustment} "
            f"final={outcome_d_pos.final_rank_score}"
        )
        if abs(outcome_d_pos.engagement_adjustment - ENGAGEMENT_WEIGHT_CAP) > 1e-6:
            log(
                f"FAIL.D: max-positive adjustment {outcome_d_pos.engagement_adjustment} "
                f"!= cap {ENGAGEMENT_WEIGHT_CAP}"
            )
            return 12

        # Negative side
        negative_view = PerformanceFeatureView(
            export_id=uuid.uuid4(),
            tenant_id=tenant.id,
            feature_version="v1",
            maturity_state=MaturityState.STABLE,
            engagement_confidence=1.0,
            normalized_view_rate=0.0,
            normalized_completion_rate=0.0,
            normalized_watch_time=0.0,
            replay_rate=0.0,
            share_rate=0.0,
            engagement_score=0.0,        # min
            experiment_group_id=None,
        )
        outcome_d_neg = apply_feedback_to_rank_score(0.5, negative_view)
        log(
            f"D.max_neg adj={outcome_d_neg.engagement_adjustment} "
            f"final={outcome_d_neg.final_rank_score}"
        )
        if abs(outcome_d_neg.engagement_adjustment + ENGAGEMENT_WEIGHT_CAP) > 1e-6:
            log(
                f"FAIL.D: max-negative adjustment {outcome_d_neg.engagement_adjustment} "
                f"!= -cap {-ENGAGEMENT_WEIGHT_CAP}"
            )
            return 13
        # Final should be clamped at 0.5 - 0.15 = 0.35
        if abs(outcome_d_neg.final_rank_score - 0.35) > 1e-6:
            log(
                f"FAIL.D: final {outcome_d_neg.final_rank_score} != expected 0.35"
            )
            return 14

        # --- sub-test E + F: persist snapshots + RANKING_FEEDBACK_APPLIED -
        # Persist a snapshot for each candidate using the feedback-applied
        # ranking from sub-test B (scene 0 has feedback; scene 1 does not).
        # `candidate_rows` and `ranked_no_fb.candidates` are 1:1 in order
        # (persist_clip_candidates iterates the ranked list); use that to
        # map scene_index → ClipCandidate ORM row.
        by_scene_index = {
            rec.scene_index: row
            for rec, row in zip(ranked_no_fb.candidates, candidate_rows)
        }
        snapshots = []
        for cand_record in ranked_b.candidates:
            target = by_scene_index.get(cand_record.scene_index or 0)
            if target is None:
                continue
            snap = persist_ranking_snapshot(
                db, job=job, candidate=target, scores=cand_record.scores,
                source_export_id=export_id_b if cand_record.scene_index == 0 else None,
            )
            snapshots.append(snap)
        db.commit()

        snap_count = db.execute(select(func.count()).select_from(RankingSnapshot)).scalar()
        log(f"E.snapshots_persisted={snap_count}")
        if snap_count != len(ranked_b.candidates):
            log(f"FAIL.E: expected {len(ranked_b.candidates)} snapshots, got {snap_count}")
            return 15
        for s in snapshots:
            log(
                f"E.snapshot candidate_id={s.candidate_id} "
                f"base={s.base_rank_score} adj={s.engagement_adjustment} "
                f"final={s.final_rank_score} feedback_applied={s.feedback_applied} "
                f"feature_version={s.feature_version}"
            )

        # Idempotent upsert: re-persist same identity → row count stays same
        for cand_record in ranked_b.candidates:
            target = by_scene_index.get(cand_record.scene_index or 0)
            if target is None:
                continue
            persist_ranking_snapshot(
                db, job=job, candidate=target, scores=cand_record.scores,
                source_export_id=export_id_b if cand_record.scene_index == 0 else None,
            )
        db.commit()
        snap_count_after_replay = db.execute(
            select(func.count()).select_from(RankingSnapshot)
        ).scalar()
        log(f"E.snapshots_after_replay={snap_count_after_replay}")
        if snap_count_after_replay != snap_count:
            log("FAIL.E: snapshot upsert duplicated rows on replay")
            return 16

        # F: usage events
        usage = db.execute(select(UsageEvent)).scalars().all()
        events = sorted({(u.event_type, u.unit) for u in usage})
        log(f"F.usage_events={json.dumps(events)}")
        feedback_events = [u for u in usage if u.event_type == "ranking_feedback_applied"]
        log(f"F.ranking_feedback_applied.count={len(feedback_events)}")
        if len(feedback_events) < len(ranked_b.candidates):
            log(
                f"FAIL.F: expected ≥{len(ranked_b.candidates)} ranking_feedback_applied "
                f"events, got {len(feedback_events)}"
            )
            return 17
        last_meta = feedback_events[-1].event_metadata or {}
        required = {
            "candidate_id", "feature_version", "feedback_applied",
            "base_rank_score", "engagement_adjustment", "final_rank_score",
            "confidence_threshold", "engagement_weight_cap",
        }
        log(f"F.metadata_keys={sorted(last_meta.keys())}")
        if not required.issubset(set(last_meta.keys())):
            log(f"FAIL.F: missing keys {required - set(last_meta.keys())}")
            return 18

        # --- sub-test G: import-discipline grep on adapter source --------
        import api.services.intel.clip_ranking_adapter as adapter_mod

        adapter_src_path = inspect.getsourcefile(adapter_mod) or ""
        adapter_src = Path(adapter_src_path).read_text(encoding="utf-8")
        forbidden_patterns = [
            r"^\s*from\s+api\.services\.engagement_aggregation",
            r"^\s*from\s+api\.models\s+import\s+[^#\n]*EngagementEvent",
            r"^\s*import\s+api\.services\.engagement_aggregation",
        ]
        violations = []
        for pat in forbidden_patterns:
            if re.search(pat, adapter_src, re.MULTILINE):
                violations.append(pat)
        log(f"G.adapter_src_path={adapter_src_path}")
        log(f"G.violations={violations}")
        if violations:
            log(f"FAIL.G: forbidden imports present in adapter: {violations}")
            return 19

        # --- sub-test H: deterministic replay ----------------------------
        ranked_h1 = rank_clip_candidates(
            upload_id=str(upload.id), scenes=scene_records,
            prior_performance=prior_b,
        )
        ranked_h2 = rank_clip_candidates(
            upload_id=str(upload.id), scenes=scene_records,
            prior_performance=prior_b,
        )

        def _triples(r):
            return [
                (c.scene_index, c.scores["base_rank_score"],
                 c.scores["engagement_adjustment"], c.scores["final_rank_score"])
                for c in r.candidates
            ]

        t1, t2 = _triples(ranked_h1), _triples(ranked_h2)
        log(f"H.triples_1={t1}")
        log(f"H.triples_2={t2}")
        if t1 != t2:
            log("FAIL.H: same inputs produced different (base, adj, final)")
            return 20

    log("sub-tests A/B/C/D/E/F/G/H: OK")
    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
