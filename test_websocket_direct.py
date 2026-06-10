import asyncio
import websockets
import json
import sys

async def test_websocket():
    uri = "ws://localhost:8040/ws/student/test_student"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")

            # 1. Start Lesson
            start_lesson_msg = {
                "type": "start_lesson",
                "concept_id": "math-8-alg"
            }
            print(f"Sending: {start_lesson_msg}")
            await websocket.send(json.dumps(start_lesson_msg))

            # Wait for instruction response
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Received: {json.dumps(data, indent=2)}")
                if data.get("type") == "stream_complete":
                    break

            # 2. Student Answer
            student_answer_msg = {
                "type": "student_answer",
                "concept_id": "math-8-alg",
                "answer_text": "I think we should add 5 to both sides.",
                "correct": True
            }
            print(f"\nSending student answer: {student_answer_msg}")
            await websocket.send(json.dumps(student_answer_msg))

            # Wait for response
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Received: {json.dumps(data, indent=2)}")
                if data.get("type") == "stream_complete":
                    break
            
            print("\nTest completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_websocket())
