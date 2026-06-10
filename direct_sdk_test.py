import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_key():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"Testing key starting with: {api_key[:10]}...")
    
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello, say 'API Key is working' if you receive this."
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Direct SDK Error: {e}")

if __name__ == "__main__":
    test_key()
