# Flask app for Smart Agent (Claude + OpenAI)
from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

CONFIG = {
    "provider": "claude",
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    "claude_api_key": os.getenv("CLAUDE_API_KEY", "")
}

def call_openai(prompt):
    return {"response": "OpenAI not yet wired in this version."}

def call_claude(prompt):
    headers = {
        "x-api-key": CONFIG["claude_api_key"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    body = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 1000,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}]
    }

    res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, data=json.dumps(body))
    return res.json()["content"][0]["text"]

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    prompt = data.get("text", "")
    if CONFIG["provider"] == "claude":
        result = call_claude(prompt)
    else:
        result = call_openai(prompt)
    return jsonify({"response": result})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
