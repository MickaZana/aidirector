"""Unit tests for services/clip_format.py"""
import pytest

from api.services.clip_format import (
    LONG_FORM_DEFAULT_DURATION_S,
    LONG_FORM_DURATION_RANGE_S,
    SHORT_FORM_DEFAULT_DURATION_S,
    SHORT_FORM_DURATION_RANGE_S,
    _interpolate,
    pick_long_form_duration,
    pick_short_form_duration,
)


class TestInterpolate:
    def test_single_clip_returns_midpoint(self):
        assert _interpolate(1, 1, 0.0, 10.0) == 5.0

    def test_first_of_two_returns_lo(self):
        assert _interpolate(1, 2, 0.0, 10.0) == 0.0

    def test_last_of_two_returns_hi(self):
        assert _interpolate(2, 2, 0.0, 10.0) == 10.0

    def test_midpoint_of_three(self):
        assert _interpolate(2, 3, 0.0, 10.0) == pytest.approx(5.0)

    def test_invalid_total_raises(self):
        with pytest.raises(ValueError):
            _interpolate(1, 0, 0.0, 10.0)

    def test_index_out_of_range_raises(self):
        with pytest.raises(ValueError):
            _interpolate(5, 3, 0.0, 10.0)

    def test_index_zero_raises(self):
        with pytest.raises(ValueError):
            _interpolate(0, 3, 0.0, 10.0)


class TestPickShortFormDuration:
    lo, hi = SHORT_FORM_DURATION_RANGE_S

    def test_pack_of_one_is_midpoint(self):
        d = pick_short_form_duration(1, 1)
        assert d == pytest.approx((self.lo + self.hi) / 2.0)

    def test_stays_within_band(self):
        for total in range(1, 6):
            for idx in range(1, total + 1):
                d = pick_short_form_duration(idx, total)
                assert self.lo <= d <= self.hi, f"idx={idx} total={total} d={d}"

    def test_pack_of_four_varies(self):
        durations = [pick_short_form_duration(i, 4) for i in range(1, 5)]
        assert len(set(durations)) == 4, "all four durations should be distinct"

    def test_first_clip_is_shortest_in_pack(self):
        assert pick_short_form_duration(1, 4) < pick_short_form_duration(4, 4)

    def test_default_constant_is_midpoint(self):
        assert SHORT_FORM_DEFAULT_DURATION_S == pytest.approx((self.lo + self.hi) / 2.0)


class TestPickLongFormDuration:
    lo, hi = LONG_FORM_DURATION_RANGE_S

    def test_stays_within_band(self):
        for total in range(1, 4):
            for idx in range(1, total + 1):
                d = pick_long_form_duration(idx, total)
                assert self.lo <= d <= self.hi

    def test_default_constant_is_midpoint(self):
        assert LONG_FORM_DEFAULT_DURATION_S == pytest.approx((self.lo + self.hi) / 2.0)
