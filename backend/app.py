# Flask app for Smart Agent (Claude + OpenAI)
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os

app = Flask(__name__)
CORS(app)

CONFIG = {
    "provider": "claude",
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    "claude_api_key": os.getenv("CLAUDE_API_KEY", "")
}

INSTRUCTION_PROMPT = """
You are an intelligent assistant that extracts structured actions from user input.
Only return valid JSON. Do not include any extra commentary.

Supported action: "create_task"

Your response format must match:
{
  "action": "create_task",
  "title": "...",
  "due_date": "YYYY-MM-DDTHH:MM:SS"
}

If the date/time is vague, set due_date to null.
"""

def call_openai(prompt):
    return {"response": "OpenAI not yet wired in this version."}

def call_claude(prompt):
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        full_prompt = f"{INSTRUCTION_PROMPT}\n\nUser: {prompt}"
        body = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": full_prompt}]
        }

        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, data=json.dumps(body))
        response_json = res.json()
        if "content" in response_json:
            raw_text = response_json["content"][0]["text"]
            parsed_json = json.loads(raw_text)
            return parsed_json
        else:
            print("Claude API error:", json.dumps(response_json, indent=2))
            return {"error": response_json.get("error", "Unknown error")}
    except Exception as e:
        print("Exception in call_claude:", str(e))
        return {"error": f"Server error: {str(e)}"}

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        if CONFIG["provider"] == "claude":
            result = call_claude(prompt)
        else:
            result = call_openai(prompt)
        return jsonify({"response": result})
    except Exception as e:
        print("Top-level error:", str(e))
        return jsonify({"response": f"Unexpected error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
