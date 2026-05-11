import os, asyncio, json
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def test():
    try:
        r = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents="Say OK",
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        print("SUCCESS:", r.text)
    except Exception:
        import traceback; traceback.print_exc()

asyncio.run(test())
