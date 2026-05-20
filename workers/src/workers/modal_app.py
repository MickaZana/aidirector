"""Modal application — images, secrets, and the function registry.

Phase 10 promotion: this file is the **real** entrypoint for the cloud
worker fleet. Operators run:

    modal token new
    modal secret create aidirector \
        DATABASE_URL=... \
        R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET=...
    modal run workers/src/workers/modal_app.py::ping_intel
    modal run workers/src/workers/modal_app.py::analyze_scene_fixture
    modal run workers/src/workers/modal_app.py::rank_clip_candidates_fixture
    modal run workers/src/workers/modal_app.py::render_one_fixture

Each entrypoint is the cloud-side equivalent of a probe that's already
been proven locally. The local probes use the adapters directly; these
do the same work inside the Modal image so the operator can attest to
distributed execution.

Image surface:
  - packages/intel mounted at /intel and on PYTHONPATH
  - apps/api/src mounted at /api_src and on PYTHONPATH so the API
    services (adapters, schemas, state_transitions, idempotency, r2)
    are importable cloud-side
  - boto3 + opencv + tesseract + pillow + anthropic + pydantic + sqlalchemy
    are in the image; alembic isn't (workers don't migrate)
"""
from __future__ import annotations

from pathlib import Path

import modal

# Resolve paths from this file's location, not CWD, so `modal run` works
# from any directory. workers/src/workers/modal_app.py → parents[3] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_INTEL_DIR = _REPO_ROOT / "packages" / "intel"
_API_SRC = _REPO_ROOT / "apps" / "api" / "src"

# Heavy deps: OmegaClips + FFmpeg + DB driver + S3 client. Trimmed to
# what's actually imported by the adapters.
intel_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "tesseract-ocr", "libgl1", "libglib2.0-0")
    .pip_install(
        "opencv-python-headless>=4.10",
        "numpy>=2.0",
        "pytesseract>=0.3",
        "pillow>=11.0",
        "anthropic>=0.42",
        "boto3>=1.35",
        "pydantic>=2.9",
        "pydantic-settings>=2.5",
        "sqlalchemy>=2.0",
        "psycopg[binary]>=3.2",
        "fastapi>=0.115",
    )
    .add_local_dir(_INTEL_DIR, remote_path="/intel")
    .add_local_dir(_API_SRC, remote_path="/api_src")
    .add_local_python_source("workers")
    .env({"PYTHONPATH": "/intel:/api_src"})
)

app = modal.App("aidirector")

# Secrets bundle — populate via:
#   modal secret create aidirector DATABASE_URL=... R2_*=... ANTHROPIC_API_KEY=...
# When absent, ping_intel still works (no DB/R2 needed). The other
# entrypoints will pick up creds from the secret automatically.
secrets = [modal.Secret.from_name("aidirector", required_keys=[])]


# --- Phase 0 gate: prove OmegaClips imports inside Modal -------------------


@app.function(image=intel_image, timeout=60)
def ping_intel() -> dict[str, str]:
    """Phase 0 ship gate (#2): confirm OmegaClips + AI Director adapters
    import cleanly inside the Modal container."""
    import sys

    sys.path.insert(0, "/intel")
    sys.path.insert(0, "/api_src")

    from football_pipeline.config import PipelineConfig
    from api.services.intel.scene_analysis_adapter import analyze_video  # noqa: F401
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates  # noqa: F401
    from api.services.state_transitions import JOB_TRANSITIONS

    cfg = PipelineConfig()
    return {
        "ok": "true",
        "python": sys.version.split()[0],
        "intel_config_class": type(cfg).__name__,
        "transition_states": ",".join(sorted(JOB_TRANSITIONS.keys())),
    }


# --- Phase 2 equivalent: scene analysis over a fixture, cloud-side --------


@app.function(image=intel_image, secrets=secrets, timeout=120, memory=2048)
def analyze_scene_fixture() -> dict:
    """Cloud-side equivalent of `_probe_phase2_loop.py`.

    Runs the real OmegaClips `ScoreboardChangeTracker` over a synthetic
    OCR sequence — exactly the same code path the local probe drives,
    but executed inside the Modal container. Operators run this to flip
    the "LOCAL-EQUIVALENT PROVEN → CLOUD PROVEN" gate.
    """
    import sys

    sys.path.insert(0, "/intel")
    sys.path.insert(0, "/api_src")

    from api.services.intel.scene_analysis_adapter import analyze_video

    fixture_reads = [
        {"t": 0.0, "home": 0, "away": 0, "clock": "00:00"},
        {"t": 12.5, "home": 1, "away": 0, "clock": "12:30"},
        {"t": 47.2, "home": 1, "away": 1, "clock": "47:12"},
        {"t": 72.8, "home": 2, "away": 1, "clock": "72:48"},
    ]
    result = analyze_video(
        upload_id="cloud-probe-upload",
        source_uri="fixture://memory",
        fixture_reads=fixture_reads,
    )
    return result.model_dump(mode="json")


# --- Phase 3 equivalent: ranking, cloud-side ------------------------------


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def rank_clip_candidates_fixture() -> dict:
    """Cloud-side equivalent of the Phase 3 ranking probe.

    Builds a small list of synthetic scenes and runs the real OmegaClips
    ranker through `clip_ranking_adapter.rank_clip_candidates`. No DB
    write — returns the ranked output so the operator can eyeball it.
    """
    import sys

    sys.path.insert(0, "/intel")
    sys.path.insert(0, "/api_src")

    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates

    scenes = [
        SceneRecord(
            t_start=0.0,
            t_end=18.0,
            kind="goal",
            arc_position="climax",
            intensity=0.91,
            importance=0.87,
            signals={"scoreboard_change": True},
        ),
        SceneRecord(
            t_start=18.0,
            t_end=42.0,
            kind="build_up",
            arc_position="rising",
            intensity=0.62,
            importance=0.55,
            signals={"pass_chain": 9},
        ),
    ]
    ranked = rank_clip_candidates("cloud-probe-upload", scenes)
    return ranked.model_dump(mode="json")


# --- Phase 5 equivalent: render, cloud-side ------------------------------


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=4096)
def render_one_fixture(manifest_dict: dict | None = None) -> dict:
    """Cloud-side equivalent of `_probe_phase5_loop.py`.

    If `manifest_dict` is None, builds a minimal in-memory RenderManifest
    pointing at FFmpeg's bundled testsrc filter (no R2 source needed)
    and runs the FFmpeg-basic renderer. Returns the execution result.

    For the full cloud chain (R2 source → FFmpeg → R2 upload), drive
    this with a real manifest from a probe on the API side.
    """
    import sys

    sys.path.insert(0, "/intel")
    sys.path.insert(0, "/api_src")

    from pathlib import Path
    from api.schemas.render_manifest import RenderManifest
    from api.services.intel.render_plan_adapter import render_clip

    if manifest_dict is None:
        manifest_dict = _synthetic_manifest_dict()
    manifest = RenderManifest.model_validate(manifest_dict)
    out_dir = Path("/tmp/aidirector_renders")
    out_dir.mkdir(parents=True, exist_ok=True)
    result = render_clip(manifest, output_dir=out_dir)
    return result.model_dump(mode="json")


def _synthetic_manifest_dict() -> dict:
    """Smallest manifest the FFmpeg-basic renderer will accept, using
    ffmpeg's built-in testsrc input. Kept inline so the cloud function
    doesn't need any additional source mounting."""
    import uuid

    rj = str(uuid.uuid4())
    return {
        "version": "1",
        "render_job_id": rj,
        "candidate_id": str(uuid.uuid4()),
        "upload_id": str(uuid.uuid4()),
        "job_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "source_uri": "ffmpeg-testsrc://lavfi",
        "clip_start": 0.0,
        "clip_end": 5.0,
        "duration": 5.0,
        "platform": "youtube_shorts",
        "aspect_ratio": "9:16",
        "output_width": 540,
        "output_height": 960,
        "fps": 30,
        "output_container": "mp4",
        "bitrate_preset": "low",
        "bitrate_kbps": 800,
        "crf": 28,
        "renderer": "ffmpeg_basic",
        "render_style": "ffmpeg_basic",
        "caption_mode": "off",
        "crop_mode": "center",
        "watermark": False,
        "normalize_audio": False,
        "filename_template": f"cloud_probe_{rj}.mp4",
        "output_filename": f"cloud_probe_{rj}.mp4",
        "execution_metadata": {"source": "cloud-probe"},
    }


# --- Existing thin-shell registrations ----------------------------------
# Imported at the bottom so Modal sees a single app graph. These files
# carry the workers used by the persistence path (not the operator
# cloud-proof entrypoints above).
from workers.analyzer import analyze_scene  # noqa: E402, F401
from workers.director import direct_render_plan  # noqa: E402, F401
from workers.renderers.ffmpeg_finisher import finish_with_ffmpeg  # noqa: E402, F401
from workers.renderers.caption_engine import render_captions  # noqa: E402, F401
from workers.renderers.auto_crop import auto_crop  # noqa: E402, F401
from workers.renderers.static_generator import render_static  # noqa: E402, F401
from workers.renderers.hyperframes import render_hyperframes  # noqa: E402, F401
from workers.renderers.remotion import render_remotion  # noqa: E402, F401
