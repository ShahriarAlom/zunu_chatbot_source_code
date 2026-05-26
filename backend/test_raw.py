import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model='gemini-3.1-flash-lite', temperature=0.2, google_api_key=os.getenv('GEMINI_API_KEY'))

async def run():
    prompt = """You are an intent router for a car rental company.
Analyze the user's message and determine if they want to:
1. "BOOKING": Find a car, rent a vehicle, check availability/prices.
2. "GREETING": Say hello, hi, how are you, thanks, goodbye.
3. "RAG": Ask a general question, policy, fee, or FAQ.

Respond ONLY with a JSON object in this exact format:
{"intent": "BOOKING" or "GREETING" or "RAG", "city": "strictly city name ONLY (e.g. 'Germantown', NO state) if BOOKING else null", "vehicle_type": "type if BOOKING else null"}

User Message: "I need a car in Germantown MD"
"""
    res = await llm.ainvoke(prompt)
    print(res.content)

if __name__ == '__main__':
    asyncio.run(run())
