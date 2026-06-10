import pytest
import json
import os
from unittest.mock import patch

# MOCK ENV VARS BEFORE IMPORTING APP
os.environ["OPENAI_API_KEY"] = "fake-test-key-do-not-use"
os.environ["GOOGLE_API_KEY"] = "fake-test-key-do-not-use"

from fastapi.testclient import TestClient
from gateway import app 

client = TestClient(app)

async def mock_llm_stream(*args, **kwargs):
    """Fake async generator that yields tokens."""
    tokens = ["Here ", "is ", "the ", "solution."]
    for token in tokens:
        yield token

# IMPORTANT: Patch the exact location where your app calls the LangChain streaming function
@patch("gateway.generate_instruction_stream", side_effect=mock_llm_stream) 
def test_websocket_llm_streaming(mock_generate_stream):
    with client.websocket_connect("/ws/student/test_user_stream") as websocket:
        payload = {
            "type": "student_answer",
            "concept_id": "ALG-8-LINEAR",
            "answer_text": "I don't know.",
            "response_time_seconds": 20,
            "cognitive_state": "focused"
        }
        websocket.send_json(payload)

        # 1. Skip the initial 'instruction_response' (empty start message)
        initial_msg = websocket.receive_json()
        assert initial_msg["type"] == "instruction_response"

        expected_tokens = ["Here ", "is ", "the ", "solution."]
        
        for expected_token in expected_tokens:
            response = websocket.receive_json()
            assert response["type"] == "stream_chunk"
            assert response["content"] == expected_token

        final_response = websocket.receive_json()
        assert final_response["type"] == "stream_complete"
