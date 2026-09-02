import os
import json
import gemini_evaluator
from dotenv import load_dotenv

load_dotenv()
print("Starting diagnostic Pydantic article generation...")
res = gemini_evaluator.generate_new_article("B1+", "Hydrogel patch")
if res:
    print("SUCCESS! Keys in res:", list(res.keys()))
    print("Full result JSON:")
    print(json.dumps(res, indent=2))
else:
    print("FAILED! returned None.")
