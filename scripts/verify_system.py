import os
import asyncio
import json
import redis.asyncio as redis
from dotenv import load_dotenv
from instructor.llm_service import generate_instruction_stream

# Load environment variables
load_dotenv()

async def test_redis():
    print("--- [1/3] Testing Redis Connection ---")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        await r.ping()
        print("✅ Redis is UP and responding.")
        await r.aclose()
        return True
    except Exception as e:
        print(f"❌ Redis is DOWN or unreachable at {REDIS_URL}")
        print(f"   Error: {e}")
        return False

async def test_llm_api():
    print("\n--- [2/3] Testing LLM API & Streaming ---")
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not google_key and not openai_key:
        print("❌ No API Keys found. Please set GOOGLE_API_KEY or OPENAI_API_KEY.")
        return False

    provider = "Google Gemini" if google_key else "OpenAI"
    print(f"Testing {provider} integration...")
    
    try:
        # We'll try to generate a tiny stream
        found_tokens = False
        async for token in generate_instruction_stream("Hello", "alg-8-lin-eq", "focused"):
            if "[SIMULATED TUTOR]" in token:
                print("\n⚠️  Warning: API call failed (Quota/Auth), system is using SIMULATED fallback.")
                return False
            if "[System Error:" in token:
                print(f"\n❌ {token}")
                return False
            if token:
                found_tokens = True
                print(token, end="", flush=True)
        
        if found_tokens:
            print("\n✅ LLM Streaming is working perfectly.")
            return True
        else:
            print("\n❌ LLM returned no tokens.")
            return False
    except Exception as e:
        print(f"\n❌ LLM API Error: {e}")
        return False

async def test_gateway_readiness():
    print("\n--- [3/3] Checking Port 8004 (Gateway) ---")
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8004))
    if result == 0:
        print("✅ Gateway is already running on port 8004.")
    else:
        print("ℹ️  Gateway is not running yet (this is okay if you haven't started it).")
    sock.close()
    return True

async def main():
    print("==========================================")
    print("   TuringEd System Verification Tool")
    print("==========================================\n")
    
    r_ok = await test_redis()
    l_ok = await test_llm_api()
    g_ok = await test_gateway_readiness()
    
    print("\n==========================================")
    if r_ok and l_ok:
        print("🚀 SYSTEM READY: All core systems are green.")
    else:
        print("🚧 ACTION REQUIRED: Please check the failures above.")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(main())
