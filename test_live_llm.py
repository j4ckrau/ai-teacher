import asyncio
import os
from instructor.llm_service import generate_instruction_stream

async def main():
    concept_id = "alg-8-lin-eq-vars-both-sides"
    student_answer = "I added x to both sides of 3x - 4 = x + 10 and got 4x - 4 = 10. Is that right?"
    cognitive_state = "focused"

    print(f"--- TEST INPUT ---")
    print(f"Concept: {concept_id}")
    print(f"Student Answer: {student_answer}")
    print(f"Cognitive State: {cognitive_state}")
    print(f"\n--- LLM RESPONSE ---")
    
    full_response = ""
    try:
        async for chunk in generate_instruction_stream(
            student_answer=student_answer,
            concept_id=concept_id,
            cognitive_state=cognitive_state
        ):
            print(chunk, end="", flush=True)
            full_response += chunk
    except Exception as e:
        import traceback
        print(f"\nError during test: {e}")
        traceback.print_exc()

    print(f"\n\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(main())
