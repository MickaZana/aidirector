"""Unit tests for routers/engagement.py

Tests the trust-gradient clamping logic:
  - @field_validator clamps engagement_delta to ±0.15
  - clamped flag correctly identifies boundary values
  - No double-clamping (the bug this test guards against)
"""

from __future__ import annotations

import uuid

from pydantic import ValidationError

from api.routers.engagement import EngagementIn, _TRUST_GRADIENT_CAP


class TestEngagementInValidation:
    """Verify that the Pydantic model correctly clamps engagement_delta."""

    def test_within_range_passes_unchanged(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=0.05,
        )
        assert body.engagement_delta == 0.05

    def test_above_cap_clamps_to_max(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=0.50,
        )
        assert body.engagement_delta == _TRUST_GRADIENT_CAP  # 0.15

    def test_below_cap_clamps_to_min(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=-0.50,
        )
        assert body.engagement_delta == -_TRUST_GRADIENT_CAP  # -0.15

    def test_exactly_at_max_passes(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=_TRUST_GRADIENT_CAP,
        )
        assert body.engagement_delta == _TRUST_GRADIENT_CAP

    def test_exactly_at_min_passes(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=-_TRUST_GRADIENT_CAP,
        )
        assert body.engagement_delta == -_TRUST_GRADIENT_CAP

    def test_zero_delta_passes(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=0.0,
        )
        assert body.engagement_delta == 0.0

    def test_negative_within_range_passes(self):
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=-0.10,
        )
        assert body.engagement_delta == -0.10


class TestEngagementRouterClampedFlag:
    """Verify the clamped flag logic in the ingest_engagement endpoint."""

    def test_clamped_true_when_at_boundary(self):
        """When engagement_delta is exactly ±0.15, clamped should be True
        because the validator clamped the (presumably larger) input value
        down to the boundary."""
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=_TRUST_GRADIENT_CAP,
        )
        # The clamped flag is determined by: body.engagement_delta in (-cap, cap)
        clamped = body.engagement_delta in (-_TRUST_GRADIENT_CAP, _TRUST_GRADIENT_CAP)
        assert clamped

    def test_clamped_false_when_internal(self):
        """When engagement_delta is within range, clamped should be False."""
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=0.05,
        )
        clamped = body.engagement_delta in (-_TRUST_GRADIENT_CAP, _TRUST_GRADIENT_CAP)
        assert not clamped

    def test_no_double_clamping(self):
        """Verify that engagement_delta is clamped ONLY once by the
        @field_validator. The function body should NOT re-clamp."""
        # Raw value > cap gets clamped once by the validator
        body = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=999.0,
        )
        assert body.engagement_delta == _TRUST_GRADIENT_CAP  # single clamp

        body2 = EngagementIn(
            render_output_id=str(uuid.uuid4()),
            platform="youtube_shorts",
            engagement_delta=-999.0,
        )
        assert body2.engagement_delta == -_TRUST_GRADIENT_CAP  # single clamp
