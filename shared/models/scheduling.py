from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class ActionType(str, Enum):
    CONTINUE = "CONTINUE"
    SWITCH_SUBJECT = "SWITCH_SUBJECT"
    TAKE_BREAK = "TAKE_BREAK"

from shared.models.curriculum import LessonPhase

class StudentSessionState(BaseModel):
    """
    Represents the current session state of a student for scheduling decisions.
    """
    student_id: str
    current_subject: str
    current_lesson_id: Optional[str] = None
    current_phase: LessonPhase = LessonPhase.INTRODUCTION
    continuous_focus_minutes: int = Field(0, ge=0)
    consecutive_failures: int = Field(0, ge=0)
    accumulated_fatigue_score: float = Field(0.0, ge=0.0, le=1.0)

class ScheduleAction(BaseModel):
    """
    The decision made by the scheduling engine.
    """
    action_type: ActionType
    target_subject: Optional[str] = None
    duration_minutes: int = Field(0, ge=0)
    reason: str
