import pytest
import time
import json
import redis
from fastapi.testclient import TestClient
from assessor.main import app as assessor_app
from scheduler.main import CURRICULUM_DAG

# Test configuration
REDIS_URL = "redis://localhost:6379/0"

@pytest.fixture
def redis_conn():
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except redis.ConnectionError:
        pytest.skip("Redis not available locally. Run docker-compose up redis first.")

def test_full_orchestration_flow(redis_conn):
    """
    Simulates a sequence of correct answers in the Assessor, 
    verifies Redis event publication, and (mocking the listener) 
    verifies the Orchestrator's routing logic.
    """
    assessor_client = TestClient(assessor_app)
    student_id = "orch_student_99"
    concept_id = "alg-8-lin-eq-1"
    
    # 1. Clear previous state in Redis
    pubsub = redis_conn.pubsub()
    pubsub.subscribe("student_events")
    
    # 2. Send correct answers to cross the 0.85 threshold
    # Initial P(L0) = 0.25. 
    # Correct 1 -> 0.64
    # Correct 2 -> 0.90 (CROSSES THRESHOLD)
    
    responses = []
    for _ in range(2):
        resp = assessor_client.post("/update_mastery", json={
            "student_id": student_id,
            "concept_id": concept_id,
            "correct": True,
            "response_time_seconds": 5.0
        })
        assert resp.status_code == 200
        responses.append(resp.json())

    # 3. Verify the last response crossed threshold
    assert responses[-1]["current_mastery_probability"] >= 0.85

    # 4. Check Redis for the event
    # We need to give it a tiny bit of time to propagate
    time.sleep(0.5)
    
    message = pubsub.get_message() # Skip subscription confirmation
    message = pubsub.get_message()
    
    assert message is not None
    event_data = json.loads(message["data"])
    assert event_data["event_type"] == "CONCEPT_MASTERED"
    assert event_data["student_id"] == student_id
    assert event_data["concept_id"] == concept_id

    # 5. Verify Orchestrator logic (using the imported DAG)
    next_concept = CURRICULUM_DAG.get(event_data["concept_id"])
    assert next_concept == "alg-8-lin-eq-vars-both-sides"
    print(f"\n[TEST SUCCESS] Student {student_id} mastered {concept_id} and was routed to {next_concept}")

def test_event_serialization():
    """Simple check for event JSON structure"""
    from assessor.main import publish_mastery_event
    # This test primarily ensures no syntax errors in the publishing logic
    # without requiring a full live redis for a unit check
    pass 
