import pytest
from scheduler.engine import evaluate_rules
from shared.models.scheduling import StudentSessionState, ActionType

def test_rule_a_time_limit():
    """Rule A: If focus >= 45 mins, force break."""
    state = StudentSessionState(
        student_id="s1",
        current_subject="MATH",
        continuous_focus_minutes=45,
        consecutive_failures=0,
        accumulated_fatigue_score=0.2
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.TAKE_BREAK
    assert decision.duration_minutes == 15
    assert "Rule A" in decision.reason

def test_rule_b_frustration_pivot():
    """Rule B: If failures >= 3, switch subject."""
    state = StudentSessionState(
        student_id="s2",
        current_subject="MATH",
        continuous_focus_minutes=20,
        consecutive_failures=3,
        accumulated_fatigue_score=0.4
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.SWITCH_SUBJECT
    assert decision.target_subject != "MATH"
    assert "Rule B" in decision.reason

def test_rule_c_fatigue_threshold():
    """Rule C: If fatigue >= 0.8, force break."""
    state = StudentSessionState(
        student_id="s3",
        current_subject="MATH",
        continuous_focus_minutes=10,
        consecutive_failures=0,
        accumulated_fatigue_score=0.8
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.TAKE_BREAK
    assert decision.duration_minutes == 15
    assert "Rule C" in decision.reason

def test_default_continue():
    """Verify default behavior when no limits are reached."""
    state = StudentSessionState(
        student_id="s4",
        current_subject="MATH",
        continuous_focus_minutes=30,
        consecutive_failures=1,
        accumulated_fatigue_score=0.5
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.CONTINUE
    assert decision.target_subject == "MATH"
