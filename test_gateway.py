import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

# Adjust import to match your Gateway file
from gateway import app 

client = TestClient(app)

def test_websocket_connection_and_answer_routing():
    """
    Test that a client can connect, send an answer, and receive an instructional response.
    """
    with client.websocket_connect("/ws/student/test_user_1") as websocket:
        # Simulate the student sending an answer
        student_payload = {
            "type": "student_answer",
            "concept_id": "ALG-8-LINEAR",
            "answer_text": "x = 4",
            "response_time_seconds": 12
        }
        websocket.send_json(student_payload)
        
        # Await the Gateway's response (mocking the Instruction Engine)
        response = websocket.receive_json()
        
        assert response["type"] == "instruction_response"
        assert "message" in response
        assert response["concept_id"] == "ALG-8-LINEAR"


@patch("gateway.listen_to_redis") # Adjust to your actual background task function name
def test_websocket_receives_redis_push_event(mock_redis_listener):
    """
    Test that the Gateway successfully routes background events (like breaks) 
    to the correct active WebSocket connection.
    """
    with client.websocket_connect("/ws/student/test_user_2") as websocket:
        
        # Simulate a Redis event triggering within the Gateway
        # Note to CLI: You will need to expose a method on your ConnectionManager 
        # to manually broadcast this for the sake of the test.
        scheduler_event = {
            "type": "system_intervention",
            "action": "TAKE_BREAK",
            "reason": "Fatigue limit",
            "duration_minutes": 15
        }
        
        # Trigger the internal broadcast using the manager exposed via app.state
        # We need to run this in an async way if the test is sync, or use the loop.
        # TestClient.websocket_connect is sync-looking but runs its own loop.
        
        # To make this work with the sync TestClient, we can use the manager directly
        # since it's in the same process.
        from gateway import manager
        
        # We need to run the async send_personal_message in the background or use a sync wrapper
        # However, TestClient's websocket connection is already active.
        
        async def trigger_event():
            await manager.send_personal_message(scheduler_event, "test_user_2")
        
        asyncio.run(trigger_event())
        
        # Assert the client receives the push notification
        response = websocket.receive_json()
        assert response["type"] == "system_intervention"
        assert response["action"] == "TAKE_BREAK"
        assert response["duration_minutes"] == 15

def test_gateway_root():
    """Verify the root endpoint is alive."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Gateway Active" in response.text
