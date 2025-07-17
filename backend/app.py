# Flask CMP Server with Claude structured output and embedded HTML frontend
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

CONFIG = {
    "provider": "claude",
    "claude_api_key": os.getenv("CLAUDE_API_KEY", "")
}

INSTRUCTION_PROMPT = """
You are an intelligent assistant. Respond ONLY with valid JSON using one of the supported actions.

Supported actions:
- create_task
- create_appointment
- send_message
- log_conversation

Each response must use this structure:
{
  "action": "create_task" | "create_appointment" | "send_message" | "log_conversation",
  "title": "...",               // for tasks or appointments
  "due_date": "YYYY-MM-DDTHH:MM:SS", // or null
  "recipient": "Name or contact",    // for send_message
  "message": "Body of the message",  // for send_message or log
  "notes": "Optional details or transcript" // for CRM logs
}
Only include fields relevant to the action.
Do not add extra commentary.
"""

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
            parsed = json.loads(raw_text)
            return parsed
        else:
            return {"error": "Claude response missing content."}
    except Exception as e:
        return {"error": str(e)}

# ----- CMP Action Handlers -----

def handle_create_task(data):
    print("[CMP] Creating task:", data.get("title"), data.get("due_date"))
    return f"Task '{data.get('title')}' scheduled for {data.get('due_date')}."

def handle_create_appointment(data):
    print("[CMP] Creating appointment:", data.get("title"), data.get("due_date"))
    return f"Appointment '{data.get('title')}' booked for {data.get('due_date')}."

def handle_send_message(data):
    print("[CMP] Sending message to", data.get("recipient"))
    print("Message:", data.get("message"))
    return f"Message sent to {data.get('recipient')}."

def handle_log_conversation(data):
    print("[CMP] Logging conversation:", data.get("notes"))
    return "Conversation log saved."

def dispatch_action(parsed):
    action = parsed.get("action")
    if action == "create_task":
        return handle_create_task(parsed)
    elif action == "create_appointment":
        return handle_create_appointment(parsed)
    elif action == "send_message":
        return handle_send_message(parsed)
    elif action == "log_conversation":
        return handle_log_conversation(parsed)
    else:
        return f"Unknown action: {action}"

# ----- Embedded HTML Template -----
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Smart AI Agent</title>
  <style>
    body {
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      background-color: #f4f6f8;
      margin: 0;
      padding: 2rem;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    h1 {
      font-size: 2rem;
      margin-bottom: 0.3rem;
    }

    h2 {
      font-size: 0.95rem;
      font-weight: normal;
      color: #777;
      margin-bottom: 2rem;
    }

    .input-group {
      display: flex;
      width: 100%;
      max-width: 720px;
      gap: 8px;
    }

    input {
      flex: 1;
      padding: 14px;
      font-size: 16px;
      border: 1px solid #ccc;
      border-radius: 8px;
    }

    button {
      padding: 14px 20px;
      font-size: 16px;
      border: none;
      border-radius: 8px;
      background-color: #007bff;
      color: white;
      cursor: pointer;
    }

    button:hover {
      background-color: #0056b3;
    }

    pre {
      margin-top: 2rem;
      width: 100%;
      max-width: 720px;
      background-color: #fff;
      border: 1px solid #ccc;
      border-radius: 8px;
      padding: 1.5rem;
      font-size: 14px;
      white-space: pre-wrap;
      min-height: 220px;
      line-height: 1.6;
      overflow-x: auto;
    }

    .label {
      font-weight: bold;
      margin-bottom: 0.5rem;
    }

    @media (max-width: 768px) {
      .input-group {
        flex-direction: column;
      }

      button {
        width: 100%;
      }

      pre {
        font-size: 13px;
      }
    }
  </style>
</head>
<body>
  <h1>Smart AI Agent UI</h1>
  <h2>Tech Stack: Single Flask App → Claude (Anthropic) → CMP Logic</h2>

  <div class="input-group">
    <input type="text" id="command" placeholder="What would you like the agent to do?" />
    <button onclick="sendCommand()">Send</button>
  </div>

  <pre id="response">Claude API response will appear here...</pre>

  <script>
    function sendCommand() {
      const input = document.getElementById('command');
      const output = document.getElementById('response');
      const userText = input.value.trim();

      if (!userText) {
        output.textContent = "⚠️ Please enter a command.";
        return;
      }

      output.textContent = "Sending...";

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        output.textContent = "Claude API response:\\n" + JSON.stringify(data.claude_output || data.response, null, 2);
        output.scrollIntoView({ behavior: "smooth" });
      })
      .catch(err => {
        output.textContent = "❌ Error: " + err.message;
      });
    }

    // Allow Enter key to submit
    document.getElementById('command').addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        sendCommand();
      }
    });
  </script>
</body>
</html>
"""

# ----- Routes -----

@app.route("/")
def root():
    return HTML_TEMPLATE

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        result = call_claude(prompt)

        if "error" in result:
            return jsonify({"response": result["error"]}), 500

        dispatch_result = dispatch_action(result)
        return jsonify({
            "response": dispatch_result,
            "claude_output": result
        })

    except Exception as e:
        return jsonify({"response": f"Unexpected error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
