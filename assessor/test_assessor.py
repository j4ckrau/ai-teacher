import pytest
from fastapi.testclient import TestClient
from assessor.main import app, STUDENT_MASTERY_STORE

client = TestClient(app)

def test_mastery_progression_sequence():
    """
    Simulates a sequence of 5 interactions: [Incorrect, Incorrect, Correct, Correct, Correct]
    Asserts that the mastery probability increases after correct responses.
    """
    student_id = "test_student_456"
    concept_id = "alg-8-lin-eq-1"
    
    # Clear store for clean test
    if student_id in STUDENT_MASTERY_STORE:
        del STUDENT_MASTERY_STORE[student_id]

    interactions = [False, False, True, True, True]
    mastery_history = []

    for was_correct in interactions:
        response = client.post("/update_mastery", json={
            "student_id": student_id,
            "concept_id": concept_id,
            "correct": was_correct,
            "response_time_seconds": 15.0
        })
        assert response.status_code == 200
        new_mastery = response.json()["current_mastery_probability"]
        mastery_history.append(new_mastery)

    # Validations:
    # 1. After two incorrects, mastery should be lower than initial (0.3) or at least not higher.
    # Note: BKT with p_slip=0.1 means an incorrect response significantly drops p_known.
    assert mastery_history[1] < 0.3
    
    # 2. Mastery should increase monotonically during the correct streak
    assert mastery_history[2] > mastery_history[1]
    assert mastery_history[3] > mastery_history[2]
    assert mastery_history[4] > mastery_history[3]

    # 3. Final mastery should be high (likely above threshold 0.85 with 3 corrects)
    # Let's verify if it actually crossed the threshold based on parameters.
    # If it did, the logs would have shown the event.
    print(f"Final Mastery History: {mastery_history}")
    assert mastery_history[-1] > 0.80

def test_pydantic_validation():
    """
    Ensures invalid payloads are rejected.
    """
    # Negative response time
    response = client.post("/update_mastery", json={
        "student_id": "s1",
        "concept_id": "c1",
        "correct": True,
        "response_time_seconds": -1.0
    })
    assert response.status_code == 422
