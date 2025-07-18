# Flask CMP Server with PWA capabilities, Voice Input, and Twilio MCP integration
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import asyncio
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional

app = Flask(__name__)
CORS(app)

CONFIG = {
    "provider": "claude",
    "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
    "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
    "mcp_server_path": os.getenv("MCP_SERVER_PATH", "mcp-server-twilio")
}

INSTRUCTION_PROMPT = """
You are an intelligent assistant. Respond ONLY with valid JSON using one of the supported actions.

Supported actions:
- create_task
- create_appointment
- send_message (now supports SMS via Twilio)
- log_conversation

Each response must use this structure:
{
  "action": "create_task" | "create_appointment" | "send_message" | "log_conversation",
  "title": "...",               // for tasks or appointments
  "due_date": "YYYY-MM-DDTHH:MM:SS", // or null
  "recipient": "Name or phone number",    // for send_message (can be phone number like +1234567890)
  "message": "Body of the message",  // for send_message or log
  "notes": "Optional details or transcript" // for CRM logs
}

For send_message action:
- If recipient looks like a phone number (starts with + or contains only digits), it will be sent as SMS
- Otherwise it will be logged as a regular message
- Phone numbers should be in E.164 format (e.g., +1234567890)

Only include fields relevant to the action.
Do not add extra commentary.
"""

class TwilioMCPClient:
    """Client for interacting with Twilio MCP server"""
    
    def __init__(self):
        self.process = None
        self.connected = False
    
    async def connect(self):
        """Start the MCP server process"""
        try:
            # Start MCP server as subprocess
            self.process = await asyncio.create_subprocess_exec(
                CONFIG["mcp_server_path"],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **os.environ,
                    "TWILIO_ACCOUNT_SID": CONFIG["twilio_account_sid"],
                    "TWILIO_AUTH_TOKEN": CONFIG["twilio_auth_token"],
                    "TWILIO_PHONE_NUMBER": CONFIG["twilio_phone_number"]
                }
            )
            
            # Initialize MCP connection
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "flask-twilio-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            await self._send_message(init_message)
            response = await self._receive_message()
            
            if response and "result" in response:
                self.connected = True
                return True
            
            return False
            
        except Exception as e:
            print(f"Failed to connect to MCP server: {e}")
            return False
    
    async def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio MCP server"""
        if not self.connected:
            await self.connect()
        
        if not self.connected:
            return {"error": "Failed to connect to Twilio MCP server"}
        
        try:
            # Call the send_sms tool via MCP
            tool_call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "send_sms",
                    "arguments": {
                        "to": to,
                        "body": message
                    }
                }
            }
            
            await self._send_message(tool_call)
            response = await self._receive_message()
            
            if response and "result" in response:
                return response["result"]
            else:
                return {"error": "Failed to send SMS", "details": response}
                
        except Exception as e:
            return {"error": f"SMS sending failed: {str(e)}"}
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send message to MCP server"""
        if self.process and self.process.stdin:
            message_str = json.dumps(message) + "\n"
            self.process.stdin.write(message_str.encode())
            await self.process.stdin.drain()
    
    async def _receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive message from MCP server"""
        if self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if line:
                    return json.loads(line.decode().strip())
            except Exception as e:
                print(f"Error receiving MCP message: {e}")
        return None
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.connected = False

# Global MCP client instance
twilio_client = TwilioMCPClient()

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

def is_phone_number(recipient: str) -> bool:
    """Check if recipient looks like a phone number"""
    # Remove spaces and common formatting
    clean = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Check if it starts with + or is all digits
    if clean.startswith("+") and clean[1:].isdigit():
        return True
    if clean.isdigit() and len(clean) >= 10:
        return True
    
    return False

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    # Remove all non-digit characters except +
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # If it doesn't start with +, assume US number
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    
    return clean

# ----- CMP Action Handlers -----

def handle_create_task(data):
    print("[CMP] Creating task:", data.get("title"), data.get("due_date"))
    return f"Task '{data.get('title')}' scheduled for {data.get('due_date')}."

def handle_create_appointment(data):
    print("[CMP] Creating appointment:", data.get("title"), data.get("due_date"))
    return f"Appointment '{data.get('title')}' booked for {data.get('due_date')}."

def handle_send_message(data):
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    
    print(f"[CMP] Sending message to {recipient}")
    print(f"Message: {message}")
    
    # Check if recipient is a phone number
    if is_phone_number(recipient):
        # Format phone number and send SMS via Twilio MCP
        formatted_phone = format_phone_number(recipient)
        print(f"[CMP] Detected phone number, sending SMS to {formatted_phone}")
        
        # Run async SMS sending in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(twilio_client.send_sms(formatted_phone, message))
            
            if "error" in result:
                return f"Failed to send SMS to {recipient}: {result['error']}"
            else:
                return f"SMS sent successfully to {recipient}. Message ID: {result.get('content', {}).get('sid', 'N/A')}"
                
        except Exception as e:
            return f"Error sending SMS to {recipient}: {str(e)}"
        finally:
            loop.close()
    else:
        # Regular message (not SMS)
        return f"Message logged for {recipient}: {message}"

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

# ----- PWA Manifest -----
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Smart AI Agent",
        "short_name": "AI Agent",
        "description": "AI-powered task and appointment manager with voice input and SMS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f4f6f8",
        "theme_color": "#007bff",
        "icons": [
            {
                "src": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTkyIiBoZWlnaHQ9IjE5MiIgdmlld0JveD0iMCAwIDE5MiAxOTIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxOTIiIGhlaWdodD0iMTkyIiByeD0iMjQiIGZpbGw9IiMwMDdiZmYiLz4KPHN2ZyB4PSI0OCIgeT0iNDgiIHdpZHRoPSI5NiIgaGVpZ2h0PSI5NiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CjxwYXRoIGQ9Im0xMiAzLTEuOTEyIDUuODEzYTIgMiAwIDAgMS0xLjI5NSAxLjI5NUwzIDEyIDguODEzIDEzLjkxMmEyIDIgMCAwIDEgMS4yOTUgMS4yOTVMMTIgMjEgMTMuOTEyIDE1LjE4N2EyIDIgMCAwIDEgMS4yOTUtMS4yOTVMMjEgMTIgMTUuMTg3IDEwLjA4OGEyIDIgMCAwIDEtMS4yOTUtMS4yOTVMMTIgMyIvPgo8L3N2Zz4KPC9zdmc+",
                "sizes": "192x192",
                "type": "image/svg+xml",
                "purpose": "any maskable"
            }
        ],
        "categories": ["productivity", "utilities"],
        "orientation": "portrait"
    })

# ----- Service Worker -----
@app.route('/sw.js')
def service_worker():
    return '''
const CACHE_NAME = 'ai-agent-v1';
const urlsToCache = [
  '/',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});
''', {'Content-Type': 'application/javascript'}

# ----- Mobile-Optimized HTML Template with Voice Input -----
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>Smart AI Agent</title>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#007bff">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="AI Agent">
  <link rel="apple-touch-icon" href="data:image/svg+xml;base64,...">
  <style>
    * {
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f4f6f8;
      margin: 0;
      padding: 2rem;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      color: #222;
    }

    .container {
      width: 100%;
      max-width: 600px;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    h1 {
      font-size: 2rem;
      margin: 0;
      text-align: center;
      font-weight: 700;
      color: #111;
    }

    .subtitle {
      font-size: 0.95rem;
      color: #666;
      text-align: center;
      margin-top: -1rem;
    }

    .input-container {
      background: #fff;
      border-radius: 12px;
      padding: 1rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
      border: 1px solid #e0e0e0;
    }

    .input-group {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }

    input {
      flex: 1;
      padding: 12px 16px;
      font-size: 16px;
      border: 1px solid #ccc;
      border-radius: 8px;
      background: #fff;
      outline: none;
      color: #333;
    }

    input::placeholder {
      color: #aaa;
    }

    button {
      padding: 12px 20px;
      font-size: 16px;
      border: none;
      border-radius: 8px;
      background: #007bff;
      color: white;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.2s;
    }

    button:hover {
      background: #0069d9;
    }

    .response-container {
      background: #fff;
      border-radius: 12px;
      padding: 1rem;
      border: 1px solid #e0e0e0;
      min-height: 200px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    }

    .response-text {
      font-size: 14px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-wrap: break-word;
      color: #222;
      font-family: 'Courier New', Courier, monospace;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Smart AI Agent UI</h1>
    <div class="subtitle">Tech Stack: HTML + JS → Flask API → Claude (Anthropic) → CMP Logic</div>

    <div class="input-container">
      <div class="input-group">
        <input type="text" id="command" placeholder="What would you like the agent to do?" />
        <button onclick="sendCommand()">Send</button>
      </div>
    </div>

    <div class="response-container">
      <div class="response-text" id="response">Claude API response will appear here...</div>
    </div>
  </div>
</body>
</html>

    // PWA Install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      document.getElementById('installPrompt').style.display = 'flex';
    });

    function installApp() {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
          if (choiceResult.outcome === 'accepted') {
            console.log('User accepted the install prompt');
          }
          deferredPrompt = null;
          hideInstallPrompt();
        });
      }
    }

    function hideInstallPrompt() {
      document.getElementById('installPrompt').style.display = 'none';
    }

    // Register service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js');
    }

    function sendCommand() {
      const input = document.getElementById('command');
      const output = document.getElementById('response');
      const userText = input.value.trim();

      if (!userText) {
        output.textContent = "⚠️ Please enter a command or use voice input.";
        return;
      }

      output.textContent = "🤔 Processing...";

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        output.textContent = "✅ " + (data.response || "Done!") + "\\n\\n📋 Details:\\n" + JSON.stringify(data.claude_output, null, 2);
        input.value = "";
        document.getElementById('voiceStatus').textContent = voiceSupported ? 'Tap microphone to speak' : '';
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

    // Handle keyboard on mobile
    document.getElementById('command').addEventListener('focus', function() {
      setTimeout(() => {
        this.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 300);
    });

    // Initialize speech recognition when page loads
    window.addEventListener('load', initSpeechRecognition);
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "twilio_configured": bool(CONFIG["twilio_account_sid"] and CONFIG["twilio_auth_token"]),
        "claude_configured": bool(CONFIG["claude_api_key"])
    })

# Cleanup on app shutdown
import atexit

def cleanup():
    """Clean up MCP connection on shutdown"""
    if twilio_client.connected:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(twilio_client.disconnect())
        loop.close()

atexit.register(cleanup)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
