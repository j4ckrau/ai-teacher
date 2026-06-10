from fastapi import FastAPI, HTTPException
import logging
import json
import os
import redis.asyncio as redis
import asyncio
from typing import Dict, List

# Import shared models
from shared.models.scheduling import StudentSessionState, ScheduleAction, ActionType

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler-engine")

app = FastAPI(title="TuringEd Scheduling & Cognitive Load Engine")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Mock Subject Registry ---
SUBJECTS = ["MATH", "HUMANITIES", "SCIENCE", "CODING"]

# --- In-Memory Session Store (For MVP) ---
SESSION_STORE: Dict[str, StudentSessionState] = {}

# --- Scheduling Logic ---

def evaluate_rules(state: StudentSessionState) -> ScheduleAction:
    """
    Deterministic rule engine for scheduling decisions.
    """
    # Rule A: Time Limit (45 mins)
    if state.continuous_focus_minutes >= 45:
        return ScheduleAction(
            action_type=ActionType.TAKE_BREAK,
            duration_minutes=15,
            reason="Continuous focus limit reached (Rule A)"
        )

    # Rule B: Frustration Pivot (3 consecutive failures)
    if state.consecutive_failures >= 3:
        # Simple pivot logic: find first subject that isn't the current one
        next_subject = next((s for s in SUBJECTS if s != state.current_subject), "HUMANITIES")
        return ScheduleAction(
            action_type=ActionType.SWITCH_SUBJECT,
            target_subject=next_subject,
            duration_minutes=30,
            reason="Frustration threshold reached (Rule B)"
        )

    # Rule C: Fatigue Threshold (>= 0.8)
    if state.accumulated_fatigue_score >= 0.8:
        return ScheduleAction(
            action_type=ActionType.TAKE_BREAK,
            duration_minutes=15,
            reason="High fatigue score detected (Rule C)"
        )

    # Default: Continue
    return ScheduleAction(
        action_type=ActionType.CONTINUE,
        target_subject=state.current_subject,
        duration_minutes=15,
        reason="Proceeding with current session"
    )

# --- Endpoints ---

@app.post("/evaluate_schedule", response_model=ScheduleAction)
async def evaluate_schedule(state: StudentSessionState):
    """
    Direct endpoint for evaluating schedule based on state.
    """
    decision = evaluate_rules(state)
    logger.info(f"Scheduling decision for {state.student_id}: {decision.action_type} ({decision.reason})")
    return decision

# --- Redis Event Integration ---

async def handle_performance_event(msg_data: str):
    """
    Updates internal state based on performance events (e.g., struggles).
    """
    try:
        event = json.loads(msg_data)
        student_id = event.get("student_id")
        
        if not student_id:
            return

        # Initialize if new
        if student_id not in SESSION_STORE:
            SESSION_STORE[student_id] = StudentSessionState(
                student_id=student_id, 
                current_subject="MATH" # Default
            )
        
        state = SESSION_STORE[student_id]

        # Process event types
        event_type = event.get("event_type")
        if event_type == "CONCEPT_STRUGGLE":
            state.consecutive_failures += 1
            state.accumulated_fatigue_score = min(1.0, state.accumulated_fatigue_score + 0.15)
            logger.warning(f"Student {student_id} is struggling. Consecutive failures: {state.consecutive_failures}")
        elif event_type == "CONCEPT_MASTERED":
            state.consecutive_failures = 0
            state.accumulated_fatigue_score = max(0.0, state.accumulated_fatigue_score - 0.05)
            logger.info(f"Student {student_id} mastered a concept. Resetting failure count.")

        # Re-evaluate and act if necessary
        decision = evaluate_rules(state)
        if decision.action_type != ActionType.CONTINUE:
            logger.info(f"[SCHEDULER] Intervention required for {student_id}: {decision.action_type}")
            # In production, we'd publish this back to the UI/Instructor

    except Exception as e:
        logger.error(f"Error processing performance event: {e}")

async def redis_performance_listener():
    logger.info(f"Connecting to Redis for performance events at {REDIS_URL}...")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe("student_performance")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await handle_performance_event(message["data"])
    finally:
        await client.close()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_performance_listener())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
