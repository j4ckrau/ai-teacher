from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os

# Import shared models (using local path for this MVP)
from shared.models.curriculum import CurriculumNode

app = FastAPI(title="TuringEd Instructional Engine (Vertical Slice)")

# --- Request Models ---

class InstructionRequest(BaseModel):
    student_id: str
    concept_id: str
    current_cognitive_state: str  # e.g., "fatigued", "focused", "curious"

class InstructionResponse(BaseModel):
    instruction_text: str
    modality: str = "text"
    metadata: dict

# --- Mock RAG Database ---

MOCK_CURRICULUM_DB = {
    "alg-8-lin-eq-vars-both-sides": {
        "concept_id": "alg-8-lin-eq-vars-both-sides",
        "title": "Solving Linear Equations with Variables on Both Sides",
        "content": """
        Verified Curriculum Data:
        - Goal: Isolate the variable on one side of the equation.
        - Core Steps:
          1. Use Addition/Subtraction Property of Equality to move all variable terms to one side.
          2. Use Addition/Subtraction Property of Equality to move all constant terms to the other side.
          3. Use Multiplication/Division Property of Equality to solve for the variable.
        - Example: 3x + 5 = x - 7 -> 2x + 5 = -7 -> 2x = -12 -> x = -6.
        - Common Error: Forgetting to apply the operation to both sides of the equation.
        """
    }
}

# --- Internal Logic ---

def retrieve_verified_content(concept_id: str) -> str:
    """
    Simulates RAG retrieval from the verified curriculum dataset.
    """
    content = MOCK_CURRICULUM_DB.get(concept_id)
    if not content:
        raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found in verified curriculum.")
    return content["content"]

def construct_system_prompt(content: str, cognitive_state: str) -> str:
    """
    Dynamically generates the system prompt based on verified content and student state.
    """
    base_prompt = f"""
    You are the TuringEd AI Instructor, an expert 8th-grade math teacher.
    Your goal is to explain the following concept using ONLY the verified data provided.
    
    VERIFIED CURRICULUM DATA:
    {content}
    
    CONSTRAINTS:
    1. STRICT ADHERENCE: Do not introduce external mathematical concepts or methods not mentioned in the verified data.
    2. TONE: Encouraging, clear, and age-appropriate for an 8th grader.
    3. NO HALLUCINATION: If the verified data is insufficient, state that you are focusing on the core principles provided.
    """
    
    # Adjust delivery based on cognitive state
    if cognitive_state == "fatigued":
        base_prompt += "\nSTUDENT STATE: The student is fatigued. Keep the explanation very brief, use bullet points, and focus on one simple step at a time. Use high encouragement."
    elif cognitive_state == "focused":
        base_prompt += "\nSTUDENT STATE: The student is focused. Provide a thorough explanation with a step-by-step walkthrough and a check-for-understanding question."
    else:
        base_prompt += "\nSTUDENT STATE: Neutral. Provide a standard, clear explanation."

    return base_prompt

# --- Endpoints ---

@app.post("/generate_instruction", response_model=InstructionResponse)
async def generate_instruction(request: InstructionRequest):
    # 1. Retrieve verified content (RAG)
    verified_content = retrieve_verified_content(request.concept_id)
    
    # 2. Construct dynamic prompt
    system_prompt = construct_system_prompt(verified_content, request.current_cognitive_state)
    
    # 3. Simulate LLM Call (In a real scenario, this would call OpenAI/Gemini/etc.)
    # For this vertical slice, we'll return the prompt itself to demonstrate the logic, 
    # or a mock response if we want it to look "real".
    
    mock_llm_response = f"[LLM GENERATED RESPONSE BASED ON SYSTEM PROMPT]\n\n"
    if request.current_cognitive_state == "fatigued":
        mock_llm_response += "Hey there! Let's take it easy. To solve these, just move the 'x's to one side. Example: 3x = x + 4 becomes 2x = 4. You got this!"
    else:
        mock_llm_response += f"Today we are mastering {request.concept_id}. Here is the verified approach..."

    return InstructionResponse(
        instruction_text=mock_llm_response,
        metadata={
            "system_prompt_used": system_prompt,
            "cognitive_state_applied": request.current_cognitive_state
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
