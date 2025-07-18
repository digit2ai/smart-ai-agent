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
HTML_TEMPLATE = """
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
  <link rel="apple-touch-icon" href="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTkyIiBoZWlnaHQ9IjE5MiIgdmlld0JveD0iMCAwIDE5MiAxOTIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxOTIiIGhlaWdodD0iMTkyIiByeD0iMjQiIGZpbGw9IiMwMDdiZmYiLz4KPHN2ZyB4PSI0OCIgeT0iNDgiIHdpZHRoPSI5NiIgaGVpZ2h0PSI5NiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CjxwYXRoIGQ9Im0xMiAzLTEuOTEyIDUuODEzYTIgMiAwIDAgMS0xLjI5NSAxLjI5NUwzIDEyIDguODEzIDEzLjkxMmEyIDIgMCAwIDEgMS4yOTUgMS4yOTVMMTIgMjEgMTMuOTEyIDE1LjE4N2EyIDIgMCAwIDEgMS4yOTUtMS4yOTVMMjEgMTIgMTUuMTg3IDEwLjA4OGEyIDIgMCAwIDEtMS4yOTUtMS.yOTVMMTIgMyIvPgo8L3N2Zz4KPC9zdmc+">
  <style>
    * {
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      margin: 0;
      padding: 1rem;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      color: white;
      padding-top: env(safe-area-inset-top);
      padding-bottom: env(safe-area-inset-bottom);
    }

    .container {
      width: 100%;
      max-width: 400px;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    h1 {
      font-size: 1.8rem;
      margin: 0;
      text-align: center;
      font-weight: 600;
      text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    .subtitle {
      font-size: 0.9rem;
      color: rgba(255,255,255,0.8);
      text-align: center;
      margin-bottom: 1rem;
    }

    .features {
      font-size: 0.8rem;
      color: rgba(255,255,255,0.7);
      text-align: center;
      margin-bottom: 1rem;
      padding: 8px 12px;
      background: rgba(255,255,255,0.1);
      border-radius: 8px;
    }

    .input-container {
      background: rgba(255,255,255,0.1);
      backdrop-filter: blur(10px);
      border-radius: 16px;
      padding: 1rem;
      border: 1px solid rgba(255,255,255,0.2);
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
      border: none;
      border-radius: 25px;
      background: rgba(255,255,255,0.9);
      outline: none;
      color: #333;
    }

    input::placeholder {
      color: #666;
    }

    button {
      padding: 12px 16px;
      font-size: 16px;
      border: none;
      border-radius: 25px;
      background: #007bff;
      color: white;
      cursor: pointer;
      font-weight: 600;
      min-width: 60px;
      transition: all 0.2s;
    }

    button:hover {
      background: #0056b3;
      transform: translateY(-1px);
    }

    button:active {
      transform: translateY(0);
    }

    .response-container {
      background: rgba(255,255,255,0.1);
      backdrop-filter: blur(10px);
      border-radius: 16px;
      padding: 1rem;
      border: 1px solid rgba(255,255,255,0.2);
      min-height: 200px;
      flex: 1;
    }

    .response-text {
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-wrap: break-word;
      color: rgba(255,255,255,0.9);
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    }

    .voice-controls {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 1rem;
      margin-top: 1rem;
    }

    .mic-button {
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: #dc3545;
      border: none;
      color: white;
      font-size: 24px;
      cursor: pointer;
      transition: all 0.3s;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      overflow: hidden;
    }

    .mic-button:hover {
      background: #c82333;
      transform: scale(1.05);
    }

    .mic-button.recording {
      background: #28a745;
      animation: pulse 1.5s infinite;
    }

    .mic-button.recording::before {
      content: '';
      position: absolute;
      top: 50%;
      left: 50%;
      width: 100%;
      height: 100%;
      background: rgba(255,255,255,0.3);
      border-radius: 50%;
      transform: translate(-50%, -50%) scale(0);
      animation: ripple 1.5s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(1); }
      50% { transform: scale(1.1); }
      100% { transform: scale(1); }
    }

    @keyframes ripple {
      0% { transform: translate(-50%, -50%) scale(0); opacity: 1; }
      100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }
    }

    .voice-status {
      font-size: 0.9rem;
      color: rgba(255,255,255,0.8);
      text-align: center;
      margin-top: 0.5rem;
      min-height: 20px;
    }

    .voice-not-supported {
      color: #ffc107;
      font-size: 0.8rem;
      text-align: center;
      margin-top: 0.5rem;
    }

    .install-prompt {
      position: fixed;
      bottom: 20px;
      left: 20px;
      right: 20px;
      background: #007bff;
      color: white;
      padding: 12px 16px;
      border-radius: 12px;
      display: none;
      align-items: center;
      justify-content: space-between;
      z-index: 1000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }

    .install-prompt button {
      background: rgba(255,255,255,0.2);
      border: none;
      color: white;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
    }

    @media (max-width: 480px) {
      .container {
        max-width: 100%;
      }
      
      body {
        padding: 0.5rem;
      }
      
      h1 {
        font-size: 1.5rem;
      }
      
      .mic-button {
        width: 55px;
        height: 55px;
        font-size: 20px;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🤖 Smart AI Agent</h1>
    <div class="subtitle">AI-powered task and appointment manager with voice input and SMS</div>
    <div class="features">✨ Now with SMS messaging via Twilio! Try: "Send SMS to +1234567890 saying Hello there!"</div>
    
    <div class="input-container">
      <div class="input-group">
        <input type="text" id="command" placeholder="What would you like me to do?" />
        <button onclick="sendCommand()">Send</button>
      </div>
    </div>

    <div class="response-container">
      <div class="response-text" id="response">Ready to help! Try saying something like:
• "Schedule a meeting with John tomorrow at 2pm"
• "Create a task to review the presentation"
• "Send SMS to +1234567890 saying Hello there!"
• "Send a message to John saying the meeting is confirmed"

You can also use voice input!</div>
    </div>

    <div class="voice-controls">
      <button class="mic-button" id="micButton" onclick="toggleVoiceRecording()">
        🎤
      </button>
    </div>
    <div class="voice-status" id="voiceStatus"></div>
  </div>

  <div class="install-prompt" id="installPrompt">
    <span>Install this app for the full experience!</span>
    <button onclick="installApp()">Install</button>
    <button onclick="hideInstallPrompt()">×</button>
  </div>

  <script>
    let deferredPrompt;
    let recognition;
    let isRecording = false;
    let voiceSupported = false;

    // Initialize speech recognition
    function initSpeechRecognition() {
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        
        recognition.onstart = function() {
          isRecording = true;
          document.getElementById('micButton').classList.add('recording');
          document.getElementById('voiceStatus').textContent = '🎤 Listening...';
        };
        
        recognition.onresult = function(event) {
          const transcript = event.results[0][0].transcript;
          document.getElementById('command').value = transcript;
          document.getElementById('voiceStatus').textContent = `📝 Heard: "${transcript}"`;
          
          // Auto-submit after voice input
          setTimeout(() => {
            sendCommand();
          }, 1000);
        };
        
        recognition.onerror = function(event) {
          console.error('Speech recognition error:', event.error);
          document.getElementById('voiceStatus').textContent = `❌ Error: ${event.error}`;
          stopRecording();
        };
        
        recognition.onend = function() {
          stopRecording();
        };
        
        voiceSupported = true;
        document.getElementById('voiceStatus').textContent = 'Tap microphone to speak';
      } else {
        document.getElementById('voiceStatus').innerHTML = '<div class="voice-not-supported">⚠️ Voice input not supported in this browser</div>';
        document.getElementById('micButton').style.display = 'none';
      }
    }

    function toggleVoiceRecording() {
      if (!voiceSupported) return;
      
      if (isRecording) {
        recognition.stop();
      } else {
        try {
          recognition.start();
        } catch (error) {
          console.error('Failed to start speech recognition:', error);
          document.getElementById('voiceStatus').textContent = '❌ Failed to start voice input';
        }
      }
    }

    function stopRecording() {
      isRecording = false;
      document.getElementById('micButton').classList.remove('recording');
      if (document.getElementById('voiceStatus').textContent.includes('Listening')) {
        document.getElementById('voiceStatus').textContent = 'Tap microphone to speak';
      }
    }

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
