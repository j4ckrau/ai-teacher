import asyncio
import json
import os
import logging
import redis.asyncio as redis # Standard redis-py async support
from fastapi import FastAPI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler-service")

app = FastAPI(title="TuringEd Orchestrator / Scheduler")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Mock Curriculum Graph Service ---
CURRICULUM_DAG = {
    "alg-8-lin-eq-1": "alg-8-lin-eq-vars-both-sides",
    "alg-8-lin-eq-vars-both-sides": "alg-8-lin-eq-complex",
    "alg-8-lin-eq-complex": "mastered"
}

async def get_next_concept(concept_id: str) -> str:
    return CURRICULUM_DAG.get(concept_id, "unknown-concept")

# --- Event Handler ---

async def handle_event(msg_data: str):
    try:
        event = json.loads(msg_data)
        if event.get("event_type") == "CONCEPT_MASTERED":
            student_id = event["student_id"]
            concept_id = event["concept_id"]
            
            next_concept = await get_next_concept(concept_id)
            logger.info(f"[ORCHESTRATOR] Student {student_id} mastered {concept_id}. "
                        f"Routing to Next Concept: {next_concept}")
    except Exception as e:
        logger.error(f"Error handling event: {e}")

# --- Background Worker ---

async def redis_listener():
    logger.info(f"Connecting to Redis at {REDIS_URL}...")
    # Use redis.asyncio
    client = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe("student_events")
    
    logger.info("Scheduler listening for student_events...")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await handle_event(message["data"])
    except Exception as e:
        logger.error(f"Redis listener error: {e}")
    finally:
        await client.close()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
