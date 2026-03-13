import os
from groq import Groq

# Manually read .env
with open(".env", "r") as f:
    for line in f:
        if line.startswith("GROQ_API_KEY="):
            os.environ["GROQ_API_KEY"] = line.split("=")[1].strip()

api_key = os.environ.get("GROQ_API_KEY")
print(f"Key found: {api_key[:10]}...")

try:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "test"}],
        max_tokens=10,
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Failed: {e}")
