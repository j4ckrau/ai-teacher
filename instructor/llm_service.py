import os
import json
import asyncio
import logging
import sys
from typing import AsyncGenerator
from dotenv import load_dotenv, find_dotenv

# Load environment variables - search upwards to find .env if not in CWD
load_dotenv(find_dotenv(), override=True)

# Override problematic model version if set
if os.getenv("GEMINI_MODEL_VERSION") == "gemini-2.0-flash":
    os.environ["GEMINI_MODEL_VERSION"] = "gemini-flash-latest"

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
    "math-8-alg": {
        "content": "Algebra involves using variables (letters like x, y) to represent unknown numbers in equations.",
        "misconceptions": "Students often think variables can only be x; they may also think adding a weight to both sides is helpful for isolation.",
        "analogy": "A balance scale where mystery boxes are variables and weights are constants."
    },
    "alg-8-lin-eq": {
        "content": "Linear equations are algebraic equations where each term is either a constant or the product of a constant and a single variable.",
        "steps": "1. Isolate variable terms. 2. Isolate constant terms. 3. Divide by coefficient.",
        "common_error": "Forgetting to perform the same operation on BOTH sides."
    },
    "alg-8-lin-eq-vars-both-sides": {
        "content": "Goal is to collect all variable terms on one side and constant terms on the other.",
        "strategy": "Subtract the smaller variable term from both sides to keep the coefficient positive.",
        "tips": "Always check your work by substituting the answer back into the original equation."
    },
    "sci-8-phy-1": {
        "content": "Newton's Laws of Motion describe the relationship between a body and the forces acting upon it.",
        "first_law": "Inertia - objects resist changes in motion.",
        "second_law": "F=ma.",
        "third_law": "Action/Reaction pairs."
    }
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
    model_name = "gemini-3.5-flash"
    
    system_instruction = f"""You are a master curriculum designer. 
    Create a succinct lesson plan for the concept: {concept_id}.
    Include:
    1. Lesson Goals
    2. Specific Learning Outcomes
    3. Brief Roadmap (Introduction -> Instruction -> Practice -> Assessment)
    Keep it under 150 words."""

    if client:
        for attempt in range(2):
            try:
                logger.info(f"Generating Lesson Plan for {concept_id} using {model_name} - Attempt {attempt+1}")
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
                logger.warning(f"Lesson Plan Generation Error with {model_name} (Attempt {attempt+1}): {e}")
                if "503" in str(e) or "overloaded" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                break
                    
    return f"Standard lesson plan for {concept_id}: 1. Introduction to concepts. 2. Direct Instruction. 3. Guided Practice with examples. 4. Summative Assessment."

# --- Fallback Canned Responses ---
SIMULATED_RESPONSES = {
    "math-8-alg": {
        LessonPhase.INTRODUCTION: "Welcome to Algebra! Today we're going to explore how we can use letters to represent mystery numbers. Imagine a balance scale... if you have a mystery box on one side and a 5lb weight, and it balances with a 10lb weight on the other, how much does the box weigh?",
        LessonPhase.INSTRUCTION: "Exactly! That mystery box ($x$) must be 5. In algebra, we'd write that as $x + 5 = 10$. To solve it, we subtract 5 from both sides to keep the scale balanced. Does that make sense?",
    },
    "alg-8-lin-eq-1": {
        LessonPhase.INTRODUCTION: "Hi there! Let's look at the **Addition Property of Equality**. It sounds fancy, but it just means that if you add the same thing to both sides of an equation, they stay equal. Ready to try a quick example?",
        LessonPhase.INSTRUCTION: "Great! Let's look at $x - 7 = 12$. To get $x$ by itself, we need to undo that 'minus 7'. What do you think is the opposite of subtracting 7?",
    }
}

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
    context_data = CURRICULUM_CONTEXT.get(concept_id, {"content": "Standard 8th grade principles apply."})
    if isinstance(context_data, str):
        context_data = {"content": context_data}
    
    # 2. Define System Instruction (Elite Teacher Persona)
    system_instruction = f"""# ROLE AND PERSONA
    You are an elite, empathetic, and highly structured classroom teacher. Your goal is to guide the student to true mastery of a concept using the EDGE framework. 

    # THE EDGE FRAMEWORK (Conceptual Roadmap)
    1. EXPLAIN (Conceptual Anchor): Use a relatable analogy (e.g., {context_data.get('analogy', 'a seesaw for balance')}).
    2. DEMONSTRATE (I Do): Walk through a complete, solved example yourself with LaTeX.
    3. GUIDE (We Do): Provide a new problem and ask the student for JUST the first step.
    4. ENABLE (You Do): Give the student a final problem to solve independently.

    # CONSTRAINTS & BEHAVIOR
    - ADAPTIVITY: If the student asks a question or makes a mistake, address it directly and warmly. 
    - PEDAGOGY: Be aware of these common misconceptions: {context_data.get('misconceptions', 'None specified')}.
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
    Curriculum Truth: {context_data.get('content')}
    Pedagogical Tips: {context_data.get('tips', context_data.get('steps', ''))}

    # INSTRUCTION
    Based on the student's input and the conversation history, provide the next piece of instruction or feedback. 
    If they are right, move forward. If they are wrong, provide a gentle hint or a different way to look at it."""

    # Pin model to gemini-3.5-flash as requested
    client = get_google_client()
    model_name = "gemini-3.5-flash"

    if client:
        for attempt in range(2):
            try:
                logger.info(f"Generating Elite Teacher response for {concept_id} (Phase: {phase}) using {model_name} - Attempt {attempt+1}")
                
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
                if response.text:
                    return response.text
                
            except Exception as e:
                logger.warning(f"Gemini SDK Error with {model_name} (Attempt {attempt+1}): {e}")
                if "503" in str(e) or "overloaded" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                break

    # 4. High-Fidelity Fallback
    logger.error(f"All LLM attempts failed for {concept_id}. Using simulated response.")
    concept_fallbacks = SIMULATED_RESPONSES.get(concept_id, SIMULATED_RESPONSES["math-8-alg"])
    return concept_fallbacks.get(phase, "That's an interesting point! Let's think about how we can use our current tools to solve this. What do you think our first step should be?")


async def generate_instruction_stream(
    student_answer: str,
    concept_id: str,
    cognitive_state: str,
    phase: LessonPhase = LessonPhase.INTRODUCTION,
    lesson_plan: str = "",
    history: list = None
) -> AsyncGenerator[str, None]:
    """
    Streaming version of generate_instruction.
    """
    client = get_google_client()
    model_name = "gemini-3.5-flash"

    context_data = CURRICULUM_CONTEXT.get(concept_id, {"content": "Standard 8th grade principles apply."})
    if isinstance(context_data, str):
        context_data = {"content": context_data}
    
    system_instruction = f"""# ROLE AND PERSONA
    You are an elite, empathetic, and highly structured classroom teacher. Your goal is to guide the student to true mastery of a concept using the EDGE framework. 

    # THE EDGE FRAMEWORK (Conceptual Roadmap)
    1. EXPLAIN (Conceptual Anchor): Use a relatable analogy (e.g., {context_data.get('analogy', 'a seesaw for balance')}).
    2. DEMONSTRATE (I Do): Walk through a complete, solved example yourself with LaTeX.
    3. GUIDE (We Do): Provide a new problem and ask the student for JUST the first step.
    4. ENABLE (You Do): Give the student a final problem to solve independently.

    # CONSTRAINTS & BEHAVIOR
    - MICRO-CHUNKING: Teach only ONE core idea or step per message. Limit text to 150 words.
    - PULSE CHECK: Every message must end with a targeted question.
    - MATH: Use LaTeX ($$ or $) for ALL mathematical expressions.
    - CURRENT CONTEXT: Topic: {concept_id}, State: {cognitive_state}, Phase: {phase.value if hasattr(phase, 'value') else phase}
    """

    if client:
        try:
            contents = []
            if history:
                for msg in history:
                    role = "user" if msg["role"] == "student" else "model"
                    contents.append(genai.types.Content(
                        role=role,
                        parts=[genai.types.Part(text=msg["content"])]
                    ))
            
            contents.append(genai.types.Content(
                role="user",
                parts=[genai.types.Part(text=student_answer)]
            ))

            async for chunk in await client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7
                )
            ):
                if chunk.text:
                    yield chunk.text
            return # Successfully streamed
                        
        except Exception as e:
            logger.warning(f"Gemini Streaming Error (Model: {model_name}): {e}")

    # Final Fallback for streaming
    logger.error(f"All LLM streaming attempts failed for {concept_id}. Using simulated response.")
    concept_fallbacks = SIMULATED_RESPONSES.get(concept_id, SIMULATED_RESPONSES["math-8-alg"])
    fallback_text = concept_fallbacks.get(phase, "I'm having a little trouble connecting to my brain! Let's try again in a moment.")
    for word in fallback_text.split():
        yield word + " "
        await asyncio.sleep(0.05)

# For standalone testing
if __name__ == "__main__":
    async def test():
        response = await generate_instruction("What is a variable?", "math-8-alg", "focused")
        print(response)
    asyncio.run(test())
