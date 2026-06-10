import pytest
from pydantic import ValidationError
from shared.models.curriculum import CurriculumNode
from instructor.main import app, MOCK_CURRICULUM_DB, construct_system_prompt
from fastapi.testclient import TestClient

client = TestClient(app)

# --- 1. Pydantic DAG Node Validation ---

def test_curriculum_node_validation_success():
    """Test A (Success): Valid JSON payload."""
    data = {
        "concept_id": "ALG-8-LINEAR",
        "title": "Solving Linear Equations",
        "prerequisite_concept_ids": ["MATH-7-PRE-ALG"],
        "mastery_threshold": 0.95,
        "verified_content_references": ["ref://123"]
    }
    node = CurriculumNode(**data)
    assert node.concept_id == "ALG-8-LINEAR"
    assert node.mastery_threshold == 0.95

def test_curriculum_node_validation_failure():
    """Test B (Failure Validation): Malformed data."""
    # Invalid mastery_threshold (string instead of float)
    with pytest.raises(ValidationError):
        CurriculumNode(
            concept_id="ALG-8-LINEAR",
            title="Solving Linear Equations",
            mastery_threshold="very high" 
        )

# --- 2. State-Dependent Instructional Generation ---

def test_generate_instruction_focused():
    """Test A (The 'Focused' State): Technical and detailed."""
    response = client.post("/generate_instruction", json={
        "student_id": "s1",
        "concept_id": "alg-8-lin-eq-vars-both-sides",
        "current_cognitive_state": "focused"
    })
    assert response.status_code == 200
    data = response.json()
    assert "Today we are mastering" in data["instruction_text"]
    assert "STUDENT STATE: The student is focused." in data["metadata"]["system_prompt_used"]

def test_generate_instruction_fatigued():
    """Test B (The 'Fatigued' State): Brief and encouraging."""
    response = client.post("/generate_instruction", json={
        "student_id": "s1",
        "concept_id": "alg-8-lin-eq-vars-both-sides",
        "current_cognitive_state": "fatigued"
    })
    assert response.status_code == 200
    data = response.json()
    # Check if mock response reflects fatigued logic
    assert "take it easy" in data["instruction_text"] or "brief" in data["instruction_text"].lower()
    assert "STUDENT STATE: The student is fatigued." in data["metadata"]["system_prompt_used"]

# --- 3. Curriculum Data Injection (RAG Grounding Check) ---

def test_rag_grounding_injection():
    """Objective: Ensure the zero-hallucination policy is working."""
    # 1. Inject a fictional method into the mock DB
    fictional_method = "The Gauss-Turing Equation Method"
    concept_id = "test-grounding-concept"
    MOCK_CURRICULUM_DB[concept_id] = {
        "concept_id": concept_id,
        "title": "Grounding Test",
        "content": f"Use {fictional_method} to solve all problems."
    }

    # 2. Call the endpoint
    response = client.post("/generate_instruction", json={
        "student_id": "s1",
        "concept_id": concept_id,
        "current_cognitive_state": "neutral"
    })
    
    assert response.status_code == 200
    # In the real system, the LLM would generate this. 
    # In our MVP, we check if the system prompt passed to the LLM (in metadata) contains the term.
    system_prompt = response.json()["metadata"]["system_prompt_used"]
    assert fictional_method in system_prompt
    
    # Clean up mock DB
    del MOCK_CURRICULUM_DB[concept_id]
