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
def apply_universal_readline_patch():
    patched_classes = set()
    async def patched_readline(self, *args, **kwargs):
        kwargs.pop('max_line_length', None)
        return await self._original_readline(*args, **kwargs)
    import asyncio.streams
    targets = [asyncio.streams.StreamReader]
    try:
        import anyio._backends._asyncio
        targets.append(anyio._backends._asyncio.StreamReader)
    except (ImportError, AttributeError): pass
    for cls in targets:
        if hasattr(cls, 'readline') and not hasattr(cls, '_original_readline'):
            cls._original_readline = cls.readline
            cls.readline = patched_readline
            patched_classes.add(cls.__name__)
    if patched_classes:
        logging.getLogger("patch").info(f"Applied readline patch to: {', '.join(patched_classes)}")

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
    }
}

def get_google_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key: return None
    return genai.Client(api_key=api_key)

from shared.models.curriculum import LessonPhase

async def generate_lesson_plan(concept_id: str) -> str:
    client = get_google_client()
    model_name = "gemini-3.5-flash"
    system_instruction = f"You are a master curriculum designer. Create a succinct lesson plan for: {concept_id}."
    if client:
        try:
            response = await client.aio.models.generate_content(
                model=model_name, contents=f"Lesson plan for {concept_id}",
                config=genai.types.GenerateContentConfig(system_instruction=system_instruction)
            )
            return response.text
        except Exception: pass
    return f"Standard lesson plan for {concept_id}: Intro -> Instruction -> Practice -> Assessment."

# --- Smart Fallback Logic ---
def get_simulated_instruction(student_answer: str, concept_id: str, phase: LessonPhase, history: list) -> str:
    answer = student_answer.lower()
    if any(w in answer for w in ["don't know", "dont know", "help", "not sure", "confused"]):
        if concept_id == "math-8-alg":
            return "No worries! Think of it like a puzzle. If a scale has 10lbs total on one side, and the other has a box plus 5lbs... what number added to 5 gives us 10?"
        return "It's okay to be unsure! Let's break it down together. What's the trickiest part for you right now?"
    if any(w in answer for w in ["ready", "start", "hello", "hi"]):
        if concept_id == "math-8-alg":
            return "Welcome to Algebra! Imagine a balance scale... if you have a mystery box on one side and a 5lb weight, and it balances with a 10lb weight, how much does the box weigh?"
        return f"Welcome! I'm excited to dive into {concept_id} with you. What do you already know about this?"
    if phase == LessonPhase.INSTRUCTION:
        if concept_id == "math-8-alg" and "5" in answer:
             return "Exactly! $x$ must be 5. In algebra, we write $x + 5 = 10$. To solve it, we subtract 5 from both sides. Does that make sense?"
        return "Great progress! We keep the scale balanced by doing the same thing to both sides. Ready for the next step?"
    
    if phase == LessonPhase.GUIDED_PRACTICE:
        if concept_id == "math-8-alg":
            return "You're doing great. Let's try one together. If we have $x + 12 = 20$, and we want to get $x$ by itself, what number should we subtract from both sides?"
        return "You're doing great. Let's try another example together to make sure we've got the hang of it. Ready?"
        
    if phase == LessonPhase.SUMMATIVE_ASSESSMENT:
        if concept_id == "math-8-alg":
            return "Final challenge! Solve this one on your own: $x - 15 = 30$. What is the value of $x$?"
        return "You've worked hard today! For our final check, how would you explain the core concept we learned to a friend?"

    return "That's an interesting point! Let's think about how we can use our current tools to solve this. What's our next step?"

async def generate_instruction(student_answer: str, concept_id: str, cognitive_state: str, phase: LessonPhase, lesson_plan: str = "", history: list = None) -> str:
    context_data = CURRICULUM_CONTEXT.get(concept_id, {"content": "Standard principles apply."})
    system_instruction = f"You are an elite teacher. Topic: {concept_id}. Phase: {phase}. Context: {context_data.get('content')}. Use the EDGE framework (Explain, Demonstrate, Guide, Enable)."
    
    client = get_google_client()
    for model_name in ["gemini-3.5-flash", "gemini-2.0-flash-lite"]:
        if not client: break
        try:
            contents = []
            if history:
                for msg in history:
                    contents.append(genai.types.Content(role="user" if msg["role"] == "student" else "model", parts=[genai.types.Part(text=msg["content"])]))
            contents.append(genai.types.Content(role="user", parts=[genai.types.Part(text=student_answer)]))
            response = await client.aio.models.generate_content(
                model=model_name, contents=contents,
                config=genai.types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.7)
            )
            if response.text: return response.text
        except Exception as e:
            logger.warning(f"Error with {model_name}: {e}")
    
    logger.error("All LLM attempts failed. Using Smart Fallback.")
    return get_simulated_instruction(student_answer, concept_id, phase, history or [])

async def generate_instruction_stream(student_answer: str, concept_id: str, cognitive_state: str, phase: LessonPhase, lesson_plan: str = "", history: list = None) -> AsyncGenerator[str, None]:
    # Stream version using same logic but yielding chunks
    client = get_google_client()
    if client:
        try:
            async for chunk in await client.aio.models.generate_content_stream(model="gemini-3.5-flash", contents=student_answer):
                if chunk.text: yield chunk.text
            return
        except Exception: pass
    fallback = get_simulated_instruction(student_answer, concept_id, phase, history or [])
    for word in fallback.split():
        yield word + " "
        await asyncio.sleep(0.05)

if __name__ == "__main__":
    async def test():
        print(await generate_instruction("What is a variable?", "math-8-alg", "focused", LessonPhase.INTRODUCTION))
    asyncio.run(test())
