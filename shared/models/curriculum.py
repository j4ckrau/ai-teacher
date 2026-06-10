from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum

class LessonPhase(str, Enum):
    INTRODUCTION = "INTRODUCTION"     # Hook, objectives, connection to prior knowledge
    INSTRUCTION = "INSTRUCTION"       # Direct teaching of the concept
    GUIDED_PRACTICE = "PRACTICE"      # Interactive problem solving with hints
    SUMMATIVE_ASSESSMENT = "TEST"     # Final check for mastery (updates BKT)

class Concept(BaseModel):
    """
    The smallest atomic unit of learning.
    """
    concept_id: str
    title: str
    description: str
    prerequisite_ids: List[str] = Field(default_factory=list)
    mastery_threshold: float = 0.85
    content_rag_uri: Optional[str] = None

class Lesson(BaseModel):
    """
    A structured teaching sequence for one or more concepts.
    """
    lesson_id: str
    title: str
    concepts: List[Concept]
    estimated_duration_minutes: int = 30

class Unit(BaseModel):
    """
    A collection of related lessons.
    """
    unit_id: str
    title: str
    lessons: List[Lesson]

class Subject(BaseModel):
    """
    A high-level academic subject (e.g., Algebra 1, Biology, US History).
    """
    subject_id: str
    title: str
    grade_level: int = Field(..., ge=1, le=12)
    units: List[Unit]

class CurriculumNode(BaseModel):
    # Keeping for backward compatibility if needed, but we'll prefer the hierarchy
    concept_id: str
    title: str
    prerequisite_concept_ids: List[str] = Field(default_factory=list)
    mastery_threshold: float = 0.85
    verified_content_references: List[str] = Field(default_factory=list)
