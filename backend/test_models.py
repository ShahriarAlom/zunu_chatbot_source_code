import os
import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print([m.name for m in genai.list_models() if 'embedContent' in m.supported_generation_methods])
