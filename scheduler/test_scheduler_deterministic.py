import pytest
from scheduler.engine import evaluate_rules
from shared.models.scheduling import StudentSessionState, ActionType

def test_case_1_standard_progression():
    """Test Case 1: Standard Progression (Healthy Focus)"""
    state = StudentSessionState(
        student_id="test_1",
        current_subject="MATH",
        continuous_focus_minutes=20,
        consecutive_failures=0,
        accumulated_fatigue_score=0.2
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.CONTINUE
    # In my implementation, I return current_subject if continuing
    assert decision.target_subject == "MATH"

def test_case_2_hard_focus_limit():
    """Test Case 2: Hard Focus Limit Reached (Screen Break Trigger) at exactly 45 mins"""
    state = StudentSessionState(
        student_id="test_2",
        current_subject="MATH",
        continuous_focus_minutes=45,
        consecutive_failures=0,
        accumulated_fatigue_score=0.5
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.TAKE_BREAK
    assert decision.duration_minutes == 15

def test_case_3_student_frustration():
    """Test Case 3: Student Frustration (Subject Pivot Trigger)"""
    state = StudentSessionState(
        student_id="test_3",
        current_subject="MATH",
        continuous_focus_minutes=15,
        consecutive_failures=3,
        accumulated_fatigue_score=0.4
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.SWITCH_SUBJECT
    assert decision.target_subject != "MATH"
    # Registry is ["MATH", "HUMANITIES", "SCIENCE", "CODING"], so next is HUMANITIES
    assert decision.target_subject == "HUMANITIES"

def test_case_4_high_cognitive_fatigue():
    """Test Case 4: High Cognitive Fatigue Accumulation (>= 0.8)"""
    state = StudentSessionState(
        student_id="test_4",
        current_subject="MATH",
        continuous_focus_minutes=30,
        consecutive_failures=1,
        accumulated_fatigue_score=0.85
    )
    decision = evaluate_rules(state)
    assert decision.action_type == ActionType.TAKE_BREAK
    # My engine defaults to 20 for Rule C fatigue, but user expects 15 for Test Case 4.
    # I will adjust the engine logic to match the user's expectation for fatigue break duration.
    assert decision.duration_minutes == 15
