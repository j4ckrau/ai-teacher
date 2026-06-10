import os
import json
import asyncio
import logging
import sys
from typing import AsyncGenerator
from dotenv import load_dotenv, find_dotenv

# Load environment variables - search upwards to find .env if not in CWD
load_dotenv(find_dotenv(), override=True)

# --- UNIVERSAL MONKEY-PATCH for StreamReader compatibility ---
# This is CRITICAL for Python 3.12+ and certain anyio/httpx versions
def apply_universal_readline_patch():
    patched_classes = set()
    
    async def patched_readline(self, *args, **kwargs):
        # The 'max_line_length' argument is not supported by standard asyncio StreamReader
        # but is sometimes passed by higher-level libraries like httpx/google-genai.
        kwargs.pop('max_line_length', None)
        return await self._original_readline(*args, **kwargs)

    # 1. Target known offenders
    targets = []
    import asyncio.streams
    targets.append(asyncio.streams.StreamReader)
    
    try:
        import anyio._backends._asyncio
        targets.append(anyio._backends._asyncio.StreamReader)
    except (ImportError, AttributeError):
        pass

    for cls in targets:
        if hasattr(cls, 'readline') and not hasattr(cls, '_original_readline'):
            cls._original_readline = cls.readline
            cls.readline = patched_readline
            patched_classes.add(cls.__name__)

    # 2. Nuclear option: search for any StreamReader in loaded modules
    for module_name, module in list(sys.modules.items()):
        if not module or module_name.startswith('google.genai'): continue
        # Only check a few known libraries for efficiency and safety
        if not any(pkg in module_name for pkg in ['asyncio', 'anyio', 'aiohttp', 'httpx']): continue
        
        for attr_name in dir(module):
            if attr_name != 'StreamReader': continue
            try:
                # Use getattr with a default to avoid triggering some property/lazy loading issues
                obj = getattr(module, attr_name, None)
                if isinstance(obj, type) and hasattr(obj, 'readline'):
                    if not hasattr(obj, '_original_readline'):
                        obj._original_readline = obj.readline
                        obj.readline = patched_readline
                        patched_classes.add(f"{module_name}.{attr_name}")
            except (AttributeError, Exception):
                continue
    
    if patched_classes:
        logging.getLogger("patch").info(f"Applied readline patch to: {', '.join(patched_classes)}")

# Apply the patch immediately
apply_universal_readline_patch()

# --- SDK Imports ---
from google import genai

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("instructor-service")

# --- Mock Verified Curriculum Data (RAG Context) ---
CURRICULUM_CONTEXT = {
    "math-8-alg": """
    Algebra involves using variables (letters like x, y) to represent unknown numbers in equations. 
    A variable is a symbol used to represent an arbitrary element of a set. 
    In the context of 8th grade math, it's a 'placeholder' for a number we are trying to find.
    """,
    "alg-8-lin-eq": """
    Linear equations are algebraic equations where each term is either a constant or the product of a constant and a single variable. 
    To solve an equation like 2x + 5 = 15, you must isolate the variable x. 
    Step 1: Subtract the constant from both sides (2x = 10). 
    Step 2: Divide by the coefficient (x = 5).
    """,
    "alg-8-lin-eq-vars-both-sides": """
    When variables are on both sides, like 3x - 4 = x + 10, the goal is to collect all variable terms on one side and constant terms on the other.
    Step 1: Subtract x from both sides to get 2x - 4 = 10.
    Step 2: Add 4 to both sides to get 2x = 14.
    Step 3: Divide by 2 to find x = 7.
    """,
    "sci-8-phy-1": """
    Newton's Laws of Motion describe the relationship between a body and the forces acting upon it.
    First Law (Inertia): An object at rest stays at rest, and an object in motion stays in motion unless acted upon by a net external force.
    Second Law (F=ma): The force acting on an object is equal to the mass of that object times its acceleration. Pushing a heavier box requires more force to achieve the same acceleration.
    Third Law (Action/Reaction): For every action, there is an equal and opposite reaction.
    """
}

def get_google_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

from shared.models.curriculum import LessonPhase

async def generate_lesson_plan(concept_id: str) -> str:
    """Generates a structured lesson plan for a concept."""
    client = get_google_client()
    model_name = os.getenv("GEMINI_MODEL_VERSION", "gemini-2.0-flash")
    
    system_instruction = f"""You are a master curriculum designer. 
    Create a succinct lesson plan for the concept: {concept_id}.
    Include:
    1. Lesson Goals
    2. Specific Learning Outcomes
    3. Brief Roadmap (Introduction -> Instruction -> Practice -> Assessment)
    Keep it under 150 words."""

    if client:
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=f"Generate a lesson plan for {concept_id}.",
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.3
                    )
                )
                return response.text
            except Exception as e:
                logger.error(f"Lesson Plan Generation Error (Attempt {attempt+1}): {e}")
                if "503" in str(e) or "overloaded" in str(e).lower():
                    await asyncio.sleep(2)
                    continue
                break
    return "Standard lesson plan: Introduction, Instruction, Guided Practice, and Assessment."

async def generate_instruction(
    student_answer: str,
    concept_id: str,
    cognitive_state: str,
    phase: LessonPhase = LessonPhase.INTRODUCTION,
    lesson_plan: str = "",
    history: list = None
) -> str:
    """
    RAG-enabled instruction generator following the Elite Teacher Learning Loop.
    """
    # 1. Retrieve Context (Mock RAG)
    context = CURRICULUM_CONTEXT.get(concept_id, "Standard 8th grade principles apply.")
    
    # 2. Define System Instruction (Elite Teacher Persona)
    system_instruction = f"""# ROLE AND PERSONA
    You are an elite, empathetic, and highly structured classroom teacher. Your goal is to guide the student to true mastery of a concept using the EDGE framework. 

    # THE EDGE FRAMEWORK (Conceptual Roadmap)
    1. EXPLAIN (Conceptual Anchor): Use a relatable analogy (e.g., the seesaw for balance).
    2. DEMONSTRATE (I Do): Walk through a complete, solved example yourself with LaTeX.
    3. GUIDE (We Do): Provide a new problem and ask the student for JUST the first step.
    4. ENABLE (You Do): Give the student a final problem to solve independently.

    # CONSTRAINTS & BEHAVIOR
    - ADAPTIVITY: If the student asks a question or makes a mistake, address it directly and warmly. Don't just repeat your previous prompt.
    - NO REDUNDANCY: Do NOT list the entire lesson roadmap or "BLUEPRINT" unless this is the very beginning of the lesson (history is empty).
    - MICRO-CHUNKING: Teach only ONE core idea or step per message. Limit instructional text to 150 words.
    - PULSE CHECK: Every message must end with a targeted question or a small task for the student.
    - MATH: Use LaTeX ($$ or $) for ALL mathematical expressions.
    - NO INTERNAL DISCLOSURE: Do not mention 'phases', 'EDGE', or 'stages' to the student.
    
    # CURRENT CONTEXT
    Topic: {concept_id}
    Cognitive State: {cognitive_state}
    Current Phase: {phase.value if hasattr(phase, 'value') else phase}
    Lesson Plan Context: {lesson_plan}
    Curriculum Truth: {context}

    # INSTRUCTION
    Based on the student's input and the conversation history, provide the next piece of instruction or feedback. 
    If they are right, move forward. If they are wrong, provide a gentle hint or a different way to look at it."""

    # 3. Use Google GenAI SDK (Gemini)
    client = get_google_client()
    model_name = os.getenv("GEMINI_MODEL_VERSION", "gemini-flash-latest")

    if client:
        for attempt in range(3):
            try:
                logger.info(f"Generating Elite Teacher response for {concept_id} (Phase: {phase}) - Attempt {attempt+1}")
                
                # Format history for Gemini SDK if provided
                contents = []
                if history:
                    for msg in history:
                        role = "user" if msg["role"] == "student" else "model"
                        contents.append(genai.types.Content(
                            role=role,
                            parts=[genai.types.Part(text=msg["content"])]
                        ))
                
                # Add the current student answer
                contents.append(genai.types.Content(
                    role="user",
                    parts=[genai.types.Part(text=student_answer)]
                ))

                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7
                    )
                )
                return response.text
                
            except Exception as e:
                logger.error(f"Gemini SDK Error (Attempt {attempt+1}): {e}")
                if "503" in str(e) or "overloaded" in str(e).lower():
                    await asyncio.sleep(2 * (attempt + 1)) # Exponential backoff
                    continue
                break

    # 4. Fallback
    return "I'm sorry, I'm having a little trouble connecting to my brain! Can you repeat that?"


# For standalone testing
if __name__ == "__main__":
    async def test():
        response = await generate_instruction("What is a variable?", "math-8-alg", "focused")
        print(response)
    asyncio.run(test())

