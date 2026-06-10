from fastapi import FastAPI, HTTPException
import logging
import json
import os
from typing import Dict
import redis
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# Import shared models
from shared.models.assessment import InteractionPayload, MasteryState

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("assessor-service")

app = FastAPI(title="TuringEd Continuous Assessment Engine")

from neo4j import GraphDatabase

# --- Redis Configuration ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# --- Neo4j Configuration ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- In-Memory State (For MVP simulation) ---
STUDENT_MASTERY_STORE: Dict[str, Dict[str, float]] = {}

# --- BKT Default Parameters ---
BKT_PARAMS = {
    "p_initial": 0.25,   # P(L0)
    "p_transition": 0.10, # P(T)
    "p_guess": 0.20,      # P(G)
    "p_slip": 0.10        # P(S)
}

MASTERY_THRESHOLD = 0.85

# --- Helper Logic ---

def update_graph_mastery(student_id: str, concept_id: str, mastery: float):
    """
    Creates a MASTERED relationship in Neo4j if threshold is met.
    """
    if mastery >= MASTERY_THRESHOLD:
        query = """
        MERGE (s:Student {id: $student_id})
        WITH s
        MATCH (c {id: $concept_id})
        MERGE (s)-[r:MASTERED]->(c)
        SET r.probability = $mastery, r.updated_at = timestamp()
        """
        with driver.session() as session:
            session.run(query, student_id=student_id, concept_id=concept_id, mastery=mastery)
            logger.info(f"Updated Neo4j: Student {student_id} MASTERED {concept_id}")

def publish_mastery_event(student_id: str, concept_id: str, mastery: float):
    """
    Publishes a CONCEPT_MASTERED event to Redis if threshold is met.
    """
    if mastery >= MASTERY_THRESHOLD:
        event_payload = {
            "event_type": "CONCEPT_MASTERED",
            "student_id": student_id,
            "concept_id": concept_id,
            "final_probability": mastery
        }
        try:
            redis_client.publish("student_events", json.dumps(event_payload))
            logger.info(f"Published CONCEPT_MASTERED event for student {student_id} on {concept_id}")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

def calculate_bkt_update(p_known_prev: float, correct: bool) -> float:
    pg = BKT_PARAMS["p_guess"]
    ps = BKT_PARAMS["p_slip"]
    pt = BKT_PARAMS["p_transition"]

    if correct:
        numerator = p_known_prev * (1 - ps)
        denominator = (p_known_prev * (1 - ps)) + ((1 - p_known_prev) * pg)
    else:
        numerator = p_known_prev * ps
        denominator = (p_known_prev * ps) + ((1 - p_known_prev) * (1 - pg))

    if denominator == 0:
        p_known_given_obs = p_known_prev
    else:
        p_known_given_obs = numerator / denominator

    p_known_new = p_known_given_obs + (1 - p_known_given_obs) * pt
    return max(0.0, min(1.0, p_known_new))

# --- Endpoints ---

@app.post("/update_mastery", response_model=MasteryState)
async def update_mastery(payload: InteractionPayload):
    student_id = payload.student_id
    concept_id = payload.concept_id

    if student_id not in STUDENT_MASTERY_STORE:
        STUDENT_MASTERY_STORE[student_id] = {}
    
    p_known_prev = STUDENT_MASTERY_STORE[student_id].get(concept_id, BKT_PARAMS["p_initial"])
    p_known_new = calculate_bkt_update(p_known_prev, payload.correct)
    STUDENT_MASTERY_STORE[student_id][concept_id] = p_known_new

    update_graph_mastery(student_id, concept_id, p_known_new)
    publish_mastery_event(student_id, concept_id, p_known_new)

    return MasteryState(
        student_id=student_id,
        concept_id=concept_id,
        current_mastery_probability=p_known_new,
        confidence_interval=0.05
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
