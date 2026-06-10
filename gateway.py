import json
import asyncio
import logging
import os
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import redis.asyncio as redis
import httpx
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TuringEd API Gateway")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ASSESSOR_URL = os.getenv("ASSESSOR_URL", "http://assessor:8001")
INSTRUCTOR_URL = os.getenv("INSTRUCTOR_URL", "http://instructor:8000")

from shared.models.curriculum import LessonPhase

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # Track student lesson state (for MVP)
        self.student_states: Dict[str, Dict] = {}

    async def connect(self, student_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[student_id] = websocket
        if student_id not in self.student_states:
            self.student_states[student_id] = {
                "current_phase": LessonPhase.INTRODUCTION,
                "current_concept": None,
                "history": []
            }
        logger.info(f"Student {student_id} connected.")

    def disconnect(self, student_id: str):
        if student_id in self.active_connections:
            del self.active_connections[student_id]
            logger.info(f"Student {student_id} disconnected.")

    async def update_phase(self, student_id: str, next_phase: LessonPhase):
        if student_id in self.student_states:
            self.student_states[student_id]["current_phase"] = next_phase
            logger.info(f"Student {student_id} advanced to {next_phase}")

    async def add_to_history(self, student_id: str, role: str, content: str):
        if student_id in self.student_states:
            self.student_states[student_id]["history"].append({"role": role, "content": content})
            # Keep history manageable
            if len(self.student_states[student_id]["history"]) > 20:
                self.student_states[student_id]["history"] = self.student_states[student_id]["history"][-20:]

    async def send_personal_message(self, message: dict, student_id: str):
        if student_id in self.active_connections:
            await self.active_connections[student_id].send_json(message)

manager = ConnectionManager()
app.state.manager = manager

from instructor.llm_service import generate_instruction, generate_lesson_plan, generate_instruction_stream

async def update_mastery_service(payload: dict):
    """Actual call to Assessor Engine"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{ASSESSOR_URL}/update_mastery", json=payload)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to connect to Assessor: {e}")
            return {"status": "error", "message": str(e)}

# --- Redis Background Listener ---

async def listen_to_redis():
    """Listens for Scheduler events and pushes them to active WebSockets"""
    logger.info(f"Connecting to Redis for Gateway events at {REDIS_URL}...")
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe("student_events")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                event_type = data.get("event_type")
                student_id = data.get("student_id")
                
                # Check for interventions: TAKE_BREAK, SWITCH_SUBJECT, or SCHEDULE_UPDATE
                if event_type in ["TAKE_BREAK", "SWITCH_SUBJECT", "SCHEDULE_UPDATE"]:
                    logger.info(f"Intervention detected for {student_id}: {event_type}")
                    # Map SCHEDULE_UPDATE to the expected action key if present
                    action = data.get("action", event_type)
                    payload = {
                        "type": "system_intervention",
                        "action": action,
                        "reason": data.get("reason", "Scheduler intervention"),
                        "duration_minutes": data.get("duration_minutes", 15)
                    }
                    await manager.send_personal_message(payload, student_id)
                    
    except Exception as e:
        logger.error(f"Redis listener error: {e}")
    finally:
        await r.aclose()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(listen_to_redis())

# --- WebSocket Endpoint ---

@app.websocket("/ws/student/{student_id}")
async def websocket_endpoint(websocket: WebSocket, student_id: str):
    await manager.connect(student_id, websocket)
    try:
        while True:
            # Receive message from student
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "start_lesson":
                concept_id = message.get("concept_id")
                
                # 1. Generate Lesson Plan
                logger.info(f"Generating lesson plan for {student_id} on {concept_id}")
                lesson_plan = await generate_lesson_plan(concept_id)
                
                manager.student_states[student_id]["current_concept"] = concept_id
                manager.student_states[student_id]["current_phase"] = LessonPhase.INTRODUCTION
                manager.student_states[student_id]["lesson_plan"] = lesson_plan
                manager.student_states[student_id]["history"] = [] # Reset history for new lesson
                
                # 2. Generate Initial Instruction
                instruction = await generate_instruction(
                    student_answer="I am ready to start!",
                    concept_id=concept_id,
                    cognitive_state="focused",
                    phase=LessonPhase.INTRODUCTION,
                    lesson_plan=lesson_plan,
                    history=[]
                )

                # Append to history
                await manager.add_to_history(student_id, "student", "I am ready to start!")
                await manager.add_to_history(student_id, "teacher", instruction)

                # Send combined response (Plan + Intro)
                await manager.send_personal_message({
                    "type": "instruction_response",
                    "concept_id": concept_id,
                    "message": f"**Lesson Plan Initiated**\n\n{lesson_plan}\n\n---\n\n{instruction}" 
                }, student_id)
                await manager.send_personal_message({"type": "stream_complete"}, student_id)

            elif message.get("type") == "student_answer":
                concept_id = message.get("concept_id")
                student_answer = message.get("answer_text", "")
                current_state = manager.student_states.get(student_id, {})
                current_phase = current_state.get("current_phase", LessonPhase.INTRODUCTION)
                lesson_plan = current_state.get("lesson_plan", "")
                history = current_state.get("history", [])
                
                # 1. Update Mastery
                correct = message.get("correct", True)
                assessor_payload = {
                    "student_id": student_id,
                    "concept_id": concept_id,
                    "correct": correct,
                    "response_time_seconds": message.get("response_time_seconds", 0)
                }
                await update_mastery_service(assessor_payload)
                
                # 2. Logic to advance phase
                next_phase = current_phase
                if correct:
                    if current_phase == LessonPhase.INTRODUCTION: next_phase = LessonPhase.INSTRUCTION
                    elif current_phase == LessonPhase.INSTRUCTION: next_phase = LessonPhase.GUIDED_PRACTICE
                    elif current_phase == LessonPhase.GUIDED_PRACTICE: next_phase = LessonPhase.SUMMATIVE_ASSESSMENT
                
                await manager.update_phase(student_id, next_phase)
                
                # 3. Generate Instruction
                logger.info(f"Generating full LLM response for {student_id} on {concept_id} (Phase: {next_phase})")
                cognitive_state = message.get("cognitive_state", "focused")
                
                instruction = await generate_instruction(
                    student_answer=student_answer,
                    concept_id=concept_id,
                    cognitive_state=cognitive_state,
                    phase=next_phase,
                    lesson_plan=lesson_plan,
                    history=history
                )

                # Update history
                await manager.add_to_history(student_id, "student", student_answer)
                await manager.add_to_history(student_id, "teacher", instruction)

                await manager.send_personal_message({
                    "type": "instruction_response",
                    "concept_id": concept_id,
                    "message": instruction 
                }, student_id)
                
                await manager.send_personal_message({
                    "type": "stream_complete",
                    "new_phase": next_phase
                }, student_id)
                
    except WebSocketDisconnect:
        manager.disconnect(student_id)
    except Exception as e:
        logger.error(f"WebSocket error for {student_id}: {e}")
        manager.disconnect(student_id)

@app.get("/")
async def get():
    return HTMLResponse("TuringEd Gateway Active")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8040)
