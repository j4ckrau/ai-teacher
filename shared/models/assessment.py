from pydantic import BaseModel, Field
from typing import Optional

class InteractionPayload(BaseModel):
    """
    Payload representing a single student interaction with a learning item.
    """
    student_id: str = Field(..., description="Unique identifier for the student")
    concept_id: str = Field(..., description="The concept being assessed")
    correct: bool = Field(..., description="Whether the response was correct")
    response_time_seconds: float = Field(..., ge=0.0, description="Time taken to respond")

class MasteryState(BaseModel):
    """
    The current calculated mastery state for a student on a specific concept.
    """
    student_id: str
    concept_id: str
    current_mastery_probability: float = Field(..., ge=0.0, le=1.0)
    confidence_interval: float = Field(0.05, description="Statistical confidence in the mastery estimate")
