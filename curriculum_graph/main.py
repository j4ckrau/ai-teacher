import os
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("curriculum-graph")

app = FastAPI(title="TuringEd Curriculum Graph Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Neo4j Configuration ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- Endpoints ---

@app.get("/")
async def root():
    return {"message": "Curriculum Graph Service Active"}

@app.get("/subjects")
async def get_subjects():
    """Returns all subjects in the curriculum."""
    query = "MATCH (s:Subject) RETURN s"
    with driver.session() as session:
        result = session.run(query)
        subjects = [record["s"]._properties for record in result]
    return subjects

@app.get("/map/{student_id}")
async def get_learning_map(student_id: str):
    """
    Returns the full curriculum DAG with mastery status for a student.
    For MVP, we'll return the nodes and their prerequisites.
    """
    # This query fetches all nodes and their relationships
    # We will expand this to include student-specific mastery later
    query = """
    MATCH (n)
    OPTIONAL MATCH (n)-[r:REQUIRES_MASTERY_OF]->(m)
    OPTIONAL MATCH (n)-[p:BELONGS_TO]->(parent)
    RETURN n, r, m, p, parent
    """
    with driver.session() as session:
        result = session.run(query)
        # Parse result into a graph structure suitable for React Flow
        # For now, let's just return raw nodes and links
        nodes = []
        links = []
        processed_ids = set()
        
        for record in result:
            node = record["n"]
            if node.id not in processed_ids:
                nodes.append({
                    "id": node.element_id,
                    "labels": list(node.labels),
                    "properties": dict(node)
                })
                processed_ids.add(node.id)
            
            if record["m"]:
                links.append({
                    "source": node.element_id,
                    "target": record["m"].element_id,
                    "type": "PREREQUISITE"
                })
            
            if record["parent"]:
                links.append({
                    "source": node.element_id,
                    "target": record["parent"].element_id,
                    "type": "PARENT"
                })
                
    return {"nodes": nodes, "links": links}

@app.on_event("shutdown")
def shutdown_event():
    driver.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
