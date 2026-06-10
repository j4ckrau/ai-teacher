# TuringEd Vertical Slice MVP: Curriculum & Instruction

This is the initial "Vertical Slice" for Project TuringEd, focusing on the integration between the **Curriculum Graph** and the **Instructional Engine**.

## Features
- **Curriculum Model**: Pydantic-based DAG nodes.
- **RAG Instructional Service**: FastAPI endpoint that generates instructions grounded in verified curriculum data.
- **Dynamic Personas**: Adjusts teaching style based on student cognitive state (e.g., "fatigued" vs. "focused").
- **Containerized**: Ready to run with Docker and PostgreSQL.

## Prerequisites
- Docker and Docker Compose installed.

## How to Run

1. **Spin up the services:**
   ```bash
   docker compose up --build
   ```

2. **Access the API Documentation:**
   Open your browser and navigate to `http://localhost:8000/docs`.

3. **Test the Endpoint:**
   You can use the Swagger UI at `/docs` or `curl`:

   ```bash
   curl -X 'POST' \
     'http://localhost:8000/generate_instruction' \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
     "student_id": "student_123",
     "concept_id": "alg-8-lin-eq-vars-both-sides",
     "current_cognitive_state": "fatigued"
   }'
   ```

## Project Structure
- `instructor/`: The Instructional Engine microservice.
- `shared/models/`: Shared data models (Curriculum Graph nodes).
- `docker-compose.yml`: Orchestration for the service and PostgreSQL.

## Zero-Hallucination Policy
The service retrieves content from a mock "Verified Curriculum Database". The LLM system prompt is strictly constrained to use only this data, ensuring mathematical accuracy and consistency.
