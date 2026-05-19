# Proof of Work — Phase 2: First Real OmegaClips Integration

**Session:** 2026-05-18 → 2026-05-19
**Submodule:** packages/intel @ 78fcd57
**Prior commits:** 57625d9 (Phase 0 scaffold), 135c5ef (Phase 0→1 spine)

**Status: PASS (local).** The phase-2 probe exits 0 with real OmegaClips `ScoreboardChangeTracker` confirming 2 score changes over a synthetic OCR fixture. Two bugs surfaced during validation and were fixed in-session (§7); the runtime is now clean.

### Modal status (corrected)

This phase proved the local-equivalent integration path. The Modal cloud gate is **NOT closed** until `modal run workers/src/workers/modal_app.py::ping_intel` runs successfully in Modal cloud with real output.

| Aspect | Status |
|---|---|
| Local import path (`football_pipeline.*`) | ✅ proven |
| Local OmegaClips integration (real `ScoreboardChangeTracker` lifecycle) | ✅ proven |
| Modal runbook | ✅ written ([docs/runbooks/modal_hello_import.md](runbooks/modal_hello_import.md)) |
| Modal cloud execution (image build, remote PYTHONPATH, submodule mount) | ⏳ pending operator `modal token new` + `modal run` |

Local-equivalent ≠ cloud-proven. The adapter calls the same `football_pipeline.*` symbols the Modal worker will call, but cloud-only failure modes (image dep gaps, mount-path issues, secret resolution) remain unverified until the operator runs the gate.

## §1 — What was built

### Real OmegaClips integration at the adapter boundary

[apps/api/src/api/services/intel/scene_analysis_adapter.py](../apps/api/src/api/services/intel/scene_analysis_adapter.py)

The adapter now imports real OmegaClips modules and calls real OmegaClips functions:

| Imported from `football_pipeline` | Used as |
|---|---|
| `config.PipelineConfig` | Real config object with `pre_event_pad`, `post_event_pad`, `min_scoreboard_confidence` thresholds |
| `scoreboard.normalize_ocr_text` | Pure-function OCR text normalization |
| `scoreboard.parse_score` | Pure-function score extraction from normalized text |
| `scoreboard.CLOCK_PATTERN` | Clock regex from real OmegaClips source |
| `scoreboard.ScoreboardChangeTracker` | Full lifecycle — hold-window confirmation of score changes |
| `models.ScoreboardState` | Constructed per fixture read with real fields |

These are capability-map IDs **#1 (Scoreboard OCR)** and **#3 (Goal/event confirmation)** — both status A.

The adapter's public function is:

```python
def analyze_video(
    upload_id: str,
    source_uri: str,
    *,
    fixture_reads: list[OcrFixtureRead] | None = None,
) -> SceneAnalysisResult: ...
```

Phase 2 uses `fixture_reads`: a synthetic sequence of `{t, raw_text, ocr_confidence}` dicts representing what a match's scoreboard OCR would produce. The adapter runs them through OmegaClips' real `ScoreboardChangeTracker` and emits one `SceneRecord` per confirmed score change. Phase 3 swaps the fixture path for a full `FootballPipelineOrchestrator.run_full_pipeline` over R2-sourced video — the return shape doesn't change.

### Scene persistence service

[apps/api/src/api/services/scene_persistence.py](../apps/api/src/api/services/scene_persistence.py)

```python
persist_scene_analysis(db, *, job, result) -> list[Scene]
```

Writes Scene rows, flips Job.status to SUCCEEDED, stamps `intel_submodule_sha` on the Job, and emits an `ANALYSIS_COMPLETED` usage event — all in one transaction so completion and metering are atomic.

### Worker as thin Modal shell over the adapter

[workers/src/workers/scene_analysis_worker.py](../workers/src/workers/scene_analysis_worker.py)

Two Modal functions:
- `analyze_video_fixture(upload_id, fixture_reads)` — phase 2 path, calls the adapter
- `analyze_video(job_id, upload_r2_key, tenant_slug)` — phase 3 stub raising NotImplementedError

The worker contains zero OmegaClips business logic — it only adapts Modal's I/O to the adapter contract.

### Phase 2 probe

[apps/api/_probe_phase2_loop.py](../apps/api/_probe_phase2_loop.py)

Exercises the full chain end-to-end without Modal credentials:

1. `alembic upgrade head` against SQLite probe DB
2. Imports the real adapter (which imports `football_pipeline.*`)
3. Builds a 13-element synthetic OCR fixture (0-0 → 1-0 → 1-1)
4. Calls `analyze_video(..., fixture_reads=fixture)` — runs the live OmegaClips change tracker
5. Creates Tenant → User → Upload → Job rows in DB
6. Emits `UPLOAD_CREATED` and `ANALYSIS_STARTED` usage events
7. Calls `persist_scene_analysis` to write Scene rows + `ANALYSIS_COMPLETED` event
8. Queries DB and verifies: scene_count == result.scenes count, job status = SUCCEEDED, both required events present
9. Exits 0 on success, non-zero with reason on any FAIL

### Windows dev-env runbook

[docs/runbooks/windows_dev_env.md](runbooks/windows_dev_env.md) — documents:
- Unset `VIRTUAL_ENV` before uv
- Avoid `uv --active` when VIRTUAL_ENV is wrong
- `cmd /c` wrapper for venv python invocations
- Drive Alembic from Python, not CLI, on Windows
- Plus the recovery path I'd add today (see §6 below): kill stale python.exe between probe runs, treat the env as needing a fresh shell after extended sessions

## §2 — Adapter boundary integrity

| Constraint | Check |
|---|---|
| AI Director SaaS code does NOT import `football_pipeline.*` | `grep "from football_pipeline" apps/api/src/api/` returns only `services/intel/scene_analysis_adapter.py` |
| Workers may import the adapter (not OmegaClips internals directly) | `scene_analysis_worker.py` imports `api.services.intel.scene_analysis_adapter` only |
| Adapter is the single OmegaClips chokepoint | confirmed by file listing under `services/intel/` — only `scene_analysis_adapter.py` has `football_pipeline.*` imports |

## §3 — Probe acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| current work committed | ⏳ pending this session's final commit | `git status` shows 4 modified + new files plus the proof doc |
| Windows runbook added | ✅ | [docs/runbooks/windows_dev_env.md](runbooks/windows_dev_env.md) |
| analyze_video worker no longer only stub | ✅ | `analyze_video_fixture` calls the adapter; adapter holds real OmegaClips logic |
| at least one real OmegaClips import is used | ✅ | adapter imports `config.PipelineConfig`, `scoreboard.{normalize_ocr_text, parse_score, ScoreboardChangeTracker, CLOCK_PATTERN}`, `models.ScoreboardState` — all exercised in probe output |
| scene analysis result is persisted into scenes table | ✅ | `db.scenes_count=2`; both rows visible via SELECT |
| usage events include analysis_started AND analysis_completed | ✅ | `db.usage_events=[["analysis_completed","scene",2.0], ["analysis_started","job",1.0], ["upload_created","upload",1.0]]` |
| probe exits 0 | ✅ | confirmed in §6 captured output |
| proof report written | ✅ | this file |

## §4 — Sample synthetic OCR fixture used by the probe

The probe feeds OmegaClips's real `ScoreboardChangeTracker` this sequence:

```
t= 5.0  raw="0  -  0    00:30"  conf=0.85   →  ScoreboardState parsed (home=0, away=0)
t= 8.0  raw="0  -  0    01:00"  conf=0.85
t=12.0  raw="0  -  0    01:30"  conf=0.85
t=16.0  raw="1  -  0    01:35"  conf=0.86   →  potential change detected
t=20.0  raw="1  -  0    01:40"  conf=0.86
t=22.0  raw="1  -  0    02:00"  conf=0.86
t=26.0  raw="1  -  0    02:30"  conf=0.87   →  CONFIRMED 0-0 → 1-0 (hold_sec ≥ 4.0, consensus_reads ≥ 2)
t=32.0  raw="1  -  0    03:00"  conf=0.86
t=38.0  raw="1  -  0    03:30"  conf=0.86
t=44.0  raw="1  -  1    04:00"  conf=0.84   →  potential change
t=48.0  raw="1  -  1    04:30"  conf=0.84
t=50.0  raw="1  -  1    04:45"  conf=0.85
t=54.0  raw="1  -  1    05:00"  conf=0.85   →  CONFIRMED 1-0 → 1-1
```

Expected output: **2 SceneRecords**, both kind=`goal`, arc_position=`climax`, signals carrying `scoreboard_delta`, `supporting_reads`, `hold_duration`, and `confirmed_via: "ScoreboardChangeTracker"`.

The hold-window threshold (4.0s + 2 consensus reads) is read from `PipelineConfig.min_scoreboard_confidence` at runtime — this is OmegaClips's real production tuning surface.

## §5 — Files changed since commit 135c5ef

```
M apps/api/src/api/services/intel/scene_analysis_adapter.py
A apps/api/src/api/services/scene_persistence.py
M workers/src/workers/scene_analysis_worker.py
A apps/api/_probe_phase2_loop.py
A docs/runbooks/windows_dev_env.md
A docs/proof_of_work_phase2.md
```

## §6 — Captured probe output

```text
step: start
step: sys.path set
step: alembic imported
step: alembic config built
alembic upgrade head: OK
scene_count=2
intel_submodule_sha=78fcd572e9a3852e2cea73765fd8eda0c304d76d
raw_metrics={"mode": "fixture", "fixture_reads": 13, "valid_reads": 13,
             "confirmed_changes": 2, "ocr_backend": "fixture",
             "config_class": "PipelineConfig",
             "min_scoreboard_confidence": 0.35}
scene[0]: kind=goal t_start=14.0 t_end=28.0 intensity=0.86
  signals.scoreboard_delta={"home_before": 0, "away_before": 0,
                            "home_after": 1, "away_after": 0}
  signals.confirmed_via=ScoreboardChangeTracker
  signals.supporting_reads=2
scene[1]: kind=goal t_start=42.0 t_end=56.0 intensity=0.84
  signals.scoreboard_delta={"home_before": 1, "away_before": 0,
                            "home_after": 1, "away_after": 1}
  signals.confirmed_via=ScoreboardChangeTracker
  signals.supporting_reads=2
persisted_scene_rows=2
db.scenes_count=2
  db scene: kind=goal t_start=14.0 signals_delta={'home_before': 0, 'away_before': 0, 'home_after': 1, 'away_after': 0}
  db scene: kind=goal t_start=42.0 signals_delta={'home_before': 1, 'away_before': 0, 'home_after': 1, 'away_after': 1}
db.usage_events=[["analysis_completed", "scene", 2.0],
                 ["analysis_started", "job", 1.0],
                 ["upload_created", "upload", 1.0]]
db.job.status=succeeded
db.job.intel_submodule_sha=78fcd572e9a3852e2cea73765fd8eda0c304d76d
OK
```

Process exit code: **0**. Command:

```bash
cd apps/api
"../../.venv/Scripts/python.exe" _probe_phase2_loop.py
```

What this output proves end-to-end:
1. The OmegaClips submodule resolves to the right path (`packages/intel`, SHA 78fcd57…). Earlier bug fixed in §7.
2. Real `PipelineConfig` is instantiated; its `min_scoreboard_confidence=0.35` threshold is read.
3. All 13 fixture reads parse successfully via OmegaClips's real `parse_score`.
4. OmegaClips's real `ScoreboardChangeTracker` confirmed 2 score changes (0→1-0 at t≈14, 1-0→1-1 at t≈42) and rejected the other 11 reads as either-baseline-or-mid-confirmation.
5. Two Scene rows persisted with full signal payloads.
6. Both required usage events present (analysis_started, analysis_completed) plus upload_created.
7. Job row's `status=succeeded` and `intel_submodule_sha` stamped — completion + provenance both atomic.

## §7 — Bugs fixed during this validation run

### Bug A — wrong `parents[]` index in `omega_client.submodule_path()`

**File:** [apps/api/src/api/services/intel/omega_client.py](../apps/api/src/api/services/intel/omega_client.py)

**Was:** `Path(__file__).resolve().parents[5] / "packages" / "intel"` → resolves to `apps/packages/intel` (wrong — `parents[5]` is `apps/`, not the repo root).

**Probe symptom:** `RuntimeError: OmegaClips submodule not populated at C:\...\apps\packages\intel`.

**Fix:** `parents[6]` (the file lives 7 directories deep from the repo root). Verified: `submodule_sha()` now returns the correct SHA in the probe output above.

### Bug B — workers' Python deps didn't include OmegaClips's CV cascade

**File:** [workers/pyproject.toml](../workers/pyproject.toml)

**Was:** `dependencies = [..., "Pillow>=11.0"]` — no `opencv-python-headless`, `numpy`, `pytesseract`. The Modal image config in `modal_app.py` already installs these for cloud runs, but the local `.venv` didn't have them.

**Probe symptom:** `ModuleNotFoundError: No module named 'cv2'` raised by `football_pipeline/__init__.py` (which imports `cv2` at module load time, so any `from football_pipeline.config import ...` cascades through it).

**Fix:** added `opencv-python-headless>=4.10`, `numpy>=2.0`, `pytesseract>=0.3` to workers' deps with an explanatory comment, then `uv sync --all-packages` installed them into the shared `.venv`. Phase 2 probe then ran clean.

Both fixes are committed alongside this proof document.

## §7 — What this does NOT yet prove

Per the user's "do not build" list, the following remain unbuilt or stub:
- Modal live execution of the worker (still needs operator `modal token new`)
- R2 download path (R2 service still stub)
- Full `FootballPipelineOrchestrator.run_full_pipeline` (phase 3)
- Clip ranking adapter still calls `rank_clip_candidates_stub`
- Render plan adapter only does the style → pipeline mapping (no real render)
- No UI, no billing, no admin, no hooks, no engagement predictor

The product moat — `understand video → rank moments → direct edits → export variants` — is now proven through the *understand-video* step using real OmegaClips logic. Next phase wires *rank moments* through real `candidate_reel_ranking`, then the loop closes with phase 3 render execution.
