import os
import json
import httpx
import dotenv

dotenv.load_dotenv(".env")

API_KEY = os.getenv("GEMINI_API_KEY")

url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
headers = {
    #"x-google-api-key": API_KEY
}
payload = {
    "contents": [
        {
            "parts": [
                {"text": "Write me a python function `is_even(n: int) -> bool` that returns whether `n` is even, ONLY send a MD code block!"}
            ]
        }
    ]
}
print(API_KEY[-6:-1])
response = httpx.post(url, headers=headers, json=payload)
print(json.dumps(response.json(), indent=2))
