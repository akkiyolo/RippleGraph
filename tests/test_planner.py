"""Unit tests for the query planner."""

from ripplegraph.retrieval.planner import plan_query, _detect_temporal_mode
from ripplegraph.models.query import TemporalMode


class TestTemporalDetection:
    def test_current(self):
        assert _detect_temporal_mode("what database are we using now?") == TemporalMode.CURRENT
        assert _detect_temporal_mode("what is our current framework?") == TemporalMode.CURRENT

    def test_historical(self):
        assert _detect_temporal_mode("what database were we using before?") == TemporalMode.HISTORICAL
        assert _detect_temporal_mode("what did we use previously?") == TemporalMode.HISTORICAL

    def test_transition(self):
        assert _detect_temporal_mode("when did we switch databases?") == TemporalMode.TRANSITION
        assert _detect_temporal_mode("when did we change to postgresql?") == TemporalMode.TRANSITION

    def test_timeline(self):
        assert _detect_temporal_mode("what databases have we considered over time?") == TemporalMode.TIMELINE

    def test_none(self):
        assert _detect_temporal_mode("what is the weather?") == TemporalMode.NONE


class TestPlanQuery:
    def test_basic_plan(self):
        plan = plan_query("What database are we using now?")
        assert plan.temporal_mode == TemporalMode.CURRENT
        assert plan.original_query == "What database are we using now?"
