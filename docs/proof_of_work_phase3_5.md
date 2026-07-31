# Phase 3.5 — Podcast / Conversation Intelligence

## Final status

PASS WITH LIMITATIONS — the backend Podcast intelligence architecture and automated verification are implemented. Real-media and browser E2E remain pending because no authorized Podcast video was available and the browser backend was unavailable.

## Architecture before

Podcast was present in the UI and upload schema, but processing entered the shared worker path with football-oriented assumptions. Director prompts, scene analysis fallbacks, candidate metadata, sports-hype captions, and action framing could therefore be applied to Podcast uploads.

## Architecture after

Shared infrastructure remains unchanged: upload, validation, queue lifecycle, storage, render manifests, platform variants, captions, analytics, and error handling remain common.

Content-aware intelligence now provides:

- A shared `ContentType` contract: football, basketball, podcast.
- Explicit normalization of the existing UI `sport` field.
- A content router that preserves the Football adapter and routes Podcast to conversation analysis.
- Deterministic Podcast transcript/diarization analysis with speaker metadata.
- Conversation moment types including questions, strong statements, hooks, and general moments.
- Traceable conversation scoring with rationale and signals.
- Podcast Director defaults: documentary captions, conversation renderer, face framing, and speech-preserving audio behavior.
- Podcast-specific vertical rendering capability through the `conversation` renderer contract.
- Podcast 9:16 variants now request the explicit `smart` crop strategy; the shared renderer uses the fill-crop path and preserves the strategy in the executable contract for future face-track coordinates.
- Content type preserved in the DirectorPlan and RenderManifest execution metadata.
- Worker prompts that select conversation language for Podcast rather than sports language.
- Explicit failure when Podcast media lacks a transcription/diarization adapter; Podcast no longer silently falls into football analysis.

## Files created

- `apps/api/src/api/content_types.py`
- `apps/api/src/api/services/intel/podcast_intelligence.py`
- `apps/api/src/api/services/intel/content_router.py`
- `apps/api/tests/unit/test_podcast_intelligence.py`
- `apps/api/tests/integration/test_podcast_pipeline.py`
- `docs/proof_of_work_phase3_5.md`

## Files modified

- `apps/api/src/api/schemas/director_plan.py`
- `apps/api/src/api/schemas/render_manifest.py`
- `apps/api/src/api/services/director_plan_builder.py`
- `apps/api/src/api/services/render_manifest_builder.py`
- `apps/api/src/api/services/intel/director_agent_adapter.py`
- `apps/api/src/api/services/intel/renderer_registry.py`
- `apps/api/workers/scene_analysis_worker.py`
- `workers/src/workers/director.py`

## Tests and verification

- Podcast unit and integration tests: 5 passed.
- API unit suite: 186 passed, 3 existing deprecation warnings.
- Crop/render regression coverage: included in the passing unit suite.
- TypeScript and frontend tests were not changed by this backend phase and should be rerun in the final release gate.

## Automated coverage

Covered:

- Podcast content-type routing.
- Explicit missing-diarization failure behavior.
- Speaker extraction and preservation.
- Conversation moment classification.
- Deterministic scoring and rationale.
- Podcast Director defaults.
- Vertical platform variant generation.
- Conversation caption mode.
- Face framing contract.
- Render manifest content metadata.
- Existing renderer regression behavior.

## Real-media and browser verification

No real Podcast media was tested. No Podcast clips were generated from a real video, so captions, speaker tracking quality, audio quality, thumbnails, previews, downloads, analytics events, and platform outputs remain unverified on actual media.

The browser backend was unavailable. No browser E2E claim is made.

## Remaining limitations

- A production transcription/diarization provider still needs to supply transcript segments and speaker identities to `analyze_content`.
- The current deterministic adapter is provider-agnostic and test-fixture driven.
- Real speaker tracking requires video-face/audio diarization integration.
- Real Podcast E2E must be completed before final Beta approval.

## Conclusion

Podcast is no longer only a UI selection: it has a dedicated, content-aware backend contract, deterministic conversation intelligence, Podcast-specific planning and rendering configuration, explicit failure boundaries, and automated coverage. It must not be marked fully verified until real Podcast media and browser infrastructure are available for the required upload-to-download test.
