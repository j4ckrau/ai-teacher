import pytest
from fastapi.testclient import TestClient
from assessor.main import app, STUDENT_MASTERY_STORE

client = TestClient(app)

def reset_student(student_id):
    if student_id in STUDENT_MASTERY_STORE:
        del STUDENT_MASTERY_STORE[student_id]

def test_case_1_first_attempt_correct():
    """Test Case 1: Cold Start (0.25) + Correct -> 0.6400"""
    sid = "test_1"
    reset_student(sid)
    response = client.post("/update_mastery", json={
        "student_id": sid,
        "concept_id": "c1",
        "correct": True,
        "response_time_seconds": 1.0
    })
    assert response.status_code == 200
    assert response.json()["current_mastery_probability"] == pytest.approx(0.6400, abs=1e-4)

def test_case_2_first_attempt_incorrect():
    """Test Case 2: Cold Start (0.25) + Incorrect -> 0.1360"""
    sid = "test_2"
    reset_student(sid)
    response = client.post("/update_mastery", json={
        "student_id": sid,
        "concept_id": "c1",
        "correct": False,
        "response_time_seconds": 1.0
    })
    assert response.status_code == 200
    assert response.json()["current_mastery_probability"] == pytest.approx(0.1360, abs=1e-4)

def test_case_3_two_consecutive_corrects():
    """Test Case 3: Post-Correct (0.64) + Correct -> 0.9000"""
    sid = "test_3"
    reset_student(sid)
    
    # First correct
    client.post("/update_mastery", json={
        "student_id": sid, "concept_id": "c1", "correct": True, "response_time_seconds": 1.0
    })
    
    # Second correct
    response = client.post("/update_mastery", json={
        "student_id": sid, "concept_id": "c1", "correct": True, "response_time_seconds": 1.0
    })
    assert response.status_code == 200
    assert response.json()["current_mastery_probability"] == pytest.approx(0.9000, abs=1e-4)

def test_case_4_recovery_sequence():
    """Test Case 4: Post-Incorrect (0.136) + Correct -> 0.4731"""
    sid = "test_4"
    reset_student(sid)
    
    # First incorrect
    client.post("/update_mastery", json={
        "student_id": sid, "concept_id": "c1", "correct": False, "response_time_seconds": 1.0
    })
    
    # Second correct
    response = client.post("/update_mastery", json={
        "student_id": sid, "concept_id": "c1", "correct": True, "response_time_seconds": 1.0
    })
    assert response.status_code == 200
    assert response.json()["current_mastery_probability"] == pytest.approx(0.4731, abs=1e-4)
