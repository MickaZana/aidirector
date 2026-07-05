"""Watermarking services — visible + invisible forensic watermarking.

Package components:
  - forensic:   Invisible luminance-based forensic watermark (embed + detect)
  - config:     Watermark configuration helpers

Usage:
    from api.services.watermarking.forensic import ForensicWatermarker
    watermarker = ForensicWatermarker()
    watermarker.embed("input.mp4", "output.mp4", tenant_id="...", clip_id="...")
    payload = watermarker.detect("output.mp4")
"""

from __future__ import annotations

from api.services.watermarking.forensic import ForensicWatermarker

__all__ = ["ForensicWatermarker"]
