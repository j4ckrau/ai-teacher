import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Adjust imports to match project structure
from assessor.main import app as assessor_app
from scheduler.main import handle_event, CURRICULUM_DAG

client = TestClient(assessor_app)

@patch("assessor.main.redis_client")
def test_no_event_published_below_threshold(mock_redis):
    """
    Test that an interaction resulting in mastery below the threshold 
    DOES NOT trigger a Redis publish event.
    """
    # Initial P(L0) = 0.25. One incorrect answer will drop it significantly.
    payload = {
        "student_id": "test_user_1",
        "concept_id": "alg-8-lin-eq-1",
        "correct": False,
        "response_time_seconds": 10.0
    }
    
    response = client.post("/update_mastery", json=payload)
    assert response.status_code == 200
    
    # Assert Redis publish was NEVER called
    mock_redis.publish.assert_not_called()

@patch("assessor.main.redis_client")
def test_event_published_above_threshold(mock_redis):
    """
    Test that an interaction resulting in mastery above the threshold 
    DOES trigger a Redis publish event with the correct payload.
    """
    # Mastery threshold is 0.85. 
    # With P(L0)=0.25:
    # 1st Correct -> 0.64
    # 2nd Correct -> 0.90 (CROSSES THRESHOLD)
    
    student_id = "test_user_2"
    concept_id = "alg-8-lin-eq-1"

    for _ in range(2):
        payload = {
            "student_id": student_id,
            "concept_id": concept_id,
            "correct": True,
            "response_time_seconds": 5.0
        }
        client.post("/update_mastery", json=payload)
    
    # Assert Redis publish WAS called
    assert mock_redis.publish.called
    
    # Extract the arguments passed to publish
    args, kwargs = mock_redis.publish.call_args
    channel = args[0]
    message_json = args[1]
    
    assert channel == "student_events"
    
    message_data = json.loads(message_json)
    assert message_data["event_type"] == "CONCEPT_MASTERED"
    assert message_data["student_id"] == student_id
    assert message_data["concept_id"] == concept_id
    assert "final_probability" in message_data

@pytest.mark.asyncio
@patch("scheduler.main.logger")
async def test_orchestrator_routing_logic(mock_logger):
    """
    Test the isolated Orchestrator worker function to ensure it 
    parses the Redis message and fetches the next concept.
    """
    student_id = "test_user_3"
    concept_id = "alg-8-lin-eq-1"
    
    mock_event_payload = {
        "event_type": "CONCEPT_MASTERED",
        "student_id": student_id,
        "concept_id": concept_id,
        "final_probability": 0.95
    }
    
    # Call the actual orchestrator handler
    await handle_event(json.dumps(mock_event_payload))
    
    # Verify the next concept was correctly identified from the DAG
    expected_next = CURRICULUM_DAG[concept_id]
    
    # Check if logger was called with the correct routing message
    # scheduler/main.py logs: f"[ORCHESTRATOR] Student {student_id} mastered {concept_id}. Routing to Next Concept: {next_concept}"
    expected_log = f"[ORCHESTRATOR] Student {student_id} mastered {concept_id}. Routing to Next Concept: {expected_next}"
    
    # Find the call to logger.info that contains our expected message
    info_calls = [call.args[0] for call in mock_logger.info.call_args_list]
    assert expected_log in info_calls
