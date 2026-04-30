import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OPENAI_API_KEY is not set")
    exit(1)

client = OpenAI(api_key=api_key)

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello in one word."}],
        max_tokens=10,
    )
    print("API key is valid")
    print("Response:", response.choices[0].message.content)
except Exception as e:
    print(f"Request failed: {e}")
