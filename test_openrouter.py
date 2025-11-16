import requests

API_KEY = "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"

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": "http://localhost",
        "X-Title": "FH-Aachen-Tarifberater"
    },
    json={
        "model": "tngtech/deepseek-r1t2-chimera:free",
        "messages": [
            {"role": "user", "content": "Hallo, was kannst du tun?"}
        ]
    }
)

print(response.json())
