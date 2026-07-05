"""Unit tests for services/viral_title.py"""
import textwrap
from pathlib import Path

import pytest

from api.services.viral_title import (
    TitleHints,
    _category,
    _pick_deterministic,
    _position_bucket,
    build_title,
    read_srt_text,
)


class TestCategory:
    def test_goal_keyword(self):
        assert _category("and he scores a goal!") == "goal"

    def test_save_keyword(self):
        assert _category("the keeper made a brilliant save") == "save"

    def test_setup_keyword(self):
        assert _category("great through ball into space") == "setup"

    def test_skill_keyword(self):
        assert _category("outrageous skill from the winger") == "skill"

    def test_fail_keyword(self):
        assert _category("how did he miss that open net") == "fail"

    def test_empty_transcript_returns_none(self):
        assert _category("") is None

    def test_whitespace_only_returns_none(self):
        assert _category("   ") is None

    def test_goal_takes_priority_over_skill(self):
        # "goal" pattern listed before "skill" — should win
        assert _category("brilliant goal in the net") == "goal"


class TestPositionBucket:
    def test_opener(self):
        assert _position_bucket(0.0, 100.0) == "opener"

    def test_buildup(self):
        assert _position_bucket(30.0, 100.0) == "buildup"

    def test_climax(self):
        assert _position_bucket(65.0, 100.0) == "climax"

    def test_outro(self):
        assert _position_bucket(90.0, 100.0) == "outro"

    def test_zero_duration_defaults_to_climax(self):
        assert _position_bucket(0.0, 0.0) == "climax"


class TestPickDeterministic:
    pool = ("alpha", "beta", "gamma", "delta", "epsilon")

    def test_same_seed_same_result(self):
        a = _pick_deterministic(self.pool, "seed-abc")
        b = _pick_deterministic(self.pool, "seed-abc")
        assert a == b

    def test_different_seeds_can_differ(self):
        results = {_pick_deterministic(self.pool, f"seed-{i}") for i in range(20)}
        assert len(results) > 1

    def test_result_is_in_pool(self):
        r = _pick_deterministic(self.pool, "whatever")
        assert r in self.pool


class TestBuildTitle:
    def _hints(self, transcript="", index=1, total=1, start=0.0, source_dur=120.0):
        return TitleHints(
            transcript=transcript,
            index=index,
            total=total,
            clip_start_s=start,
            source_duration_s=source_dur,
        )

    def test_returns_string(self):
        assert isinstance(build_title(self._hints()), str)

    def test_not_empty(self):
        assert build_title(self._hints()).strip()

    def test_stable_for_same_inputs(self):
        h = self._hints("great goal in the net", index=2, total=4, start=30.0)
        assert build_title(h) == build_title(h)

    def test_goal_transcript_picks_goal_pool(self):
        h = self._hints("and goal! back of the net")
        title = build_title(h)
        from api.services.viral_title import _GOAL_TITLES
        assert title in _GOAL_TITLES

    def test_idx_substituted_in_template(self):
        # _CLIMAX_TITLES contains "Peak chaos — clip {idx}"
        # Force a climax position with no keyword so that template is reachable.
        # We can't guarantee which template is picked, but {idx} must not appear raw.
        h = self._hints("", index=3, total=4, start=65.0, source_dur=100.0)
        title = build_title(h)
        assert "{idx}" not in title

    def test_varies_across_pack(self):
        titles = {
            build_title(self._hints("", index=i, total=4, start=i * 20.0))
            for i in range(1, 5)
        }
        assert len(titles) > 1


class TestReadSrtText:
    def test_empty_file_returns_empty_string(self, tmp_path: Path):
        srt = tmp_path / "empty.srt"
        srt.write_text("", encoding="utf-8")
        assert read_srt_text(srt) == ""

    def test_missing_file_returns_empty_string(self, tmp_path: Path):
        assert read_srt_text(tmp_path / "nonexistent.srt") == ""

    def test_strips_index_and_timecode_lines(self, tmp_path: Path):
        srt = tmp_path / "clip.srt"
        srt.write_text(
            textwrap.dedent("""\
                1
                00:00:00,000 --> 00:00:02,000
                Great goal today

                2
                00:00:03,000 --> 00:00:05,000
                Back of the net
            """),
            encoding="utf-8",
        )
        text = read_srt_text(srt)
        assert "Great goal today" in text
        assert "Back of the net" in text
        assert "-->" not in text
        # index lines stripped
        assert text.strip() not in ("1", "2")

    def test_accepts_string_path(self, tmp_path: Path):
        srt = tmp_path / "clip.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        assert read_srt_text(str(srt)) == "Hello"
