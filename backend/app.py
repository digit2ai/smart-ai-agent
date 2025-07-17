# Flask CMP Server with PWA capabilities for mobile app experience
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

# ----- PWA Manifest -----
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Smart AI Agent",
        "short_name": "AI Agent",
        "description": "AI-powered task and appointment manager",
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

# ----- Mobile-Optimized HTML Template -----
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
  <link rel="apple-touch-icon" href="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTkyIiBoZWlnaHQ9IjE5MiIgdmlld0JveD0iMCAwIDE5MiAxOTIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxOTIiIGhlaWdodD0iMTkyIiByeD0iMjQiIGZpbGw9IiMwMDdiZmYiLz4KPHN2ZyB4PSI0OCIgeT0iNDgiIHdpZHRoPSI5NiIgaGVpZ2h0PSI5NiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CjxwYXRoIGQ9Im0xMiAzLTEuOTEyIDUuODEzYTIgMiAwIDAgMS0xLjI5NSAxLjI5NUwzIDEyIDguODEzIDEzLjkxMmEyIDIgMCAwIDEgMS4yOTUgMS4yOTVMMTIgMjEgMTMuOTEyIDE1LjE4N2EyIDIgMCAwIDEgMS4yOTUtMS4yOTVMMjEgMTIgMTUuMTg3IDEwLjA4OGEyIDIgMCAwIDEtMS4yOTUtMS4yOTVMMTIgMyIvPgo8L3N2Zz4KPC9zdmc+">
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
      min-width: 50px;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    button:hover {
      background: #0056b3;
      transform: translateY(-1px);
    }

    button:active {
      transform: translateY(0);
    }

    .voice-btn {
      background: #28a745;
      border-radius: 50%;
      width: 50px;
      height: 50px;
      padding: 0;
      font-size: 18px;
    }

    .voice-btn:hover {
      background: #1e7e34;
    }

    .voice-btn.listening {
      background: #dc3545;
      animation: pulse 1s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(1); }
      50% { transform: scale(1.1); }
      100% { transform: scale(1); }
    }

    .voice-status {
      margin-top: 0.5rem;
      font-size: 0.85rem;
      color: rgba(255,255,255,0.8);
      text-align: center;
      min-height: 20px;
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
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🤖 Smart AI Agent</h1>
    <div class="subtitle">AI-powered task and appointment manager</div>
    
    <div class="input-container">
      <div class="input-group">
        <input type="text" id="command" placeholder="Type or speak your command..." />
        <button class="voice-btn" id="voiceBtn" onclick="toggleVoice()">🎤</button>
        <button onclick="sendCommand()">Send</button>
      </div>
      <div class="voice-status" id="voiceStatus"></div>
    </div>

    <div class="response-container">
      <div class="response-text" id="response">Ready to help! Try saying something like "Schedule a meeting with John tomorrow at 2pm" or "Create a task to review the presentation"</div>
    </div>
  </div>

  <div class="install-prompt" id="installPrompt">
    <span>Install this app for the full experience!</span>
    <button onclick="installApp()">Install</button>
    <button onclick="hideInstallPrompt()">×</button>
  </div>

  <script>
    let deferredPrompt;
    let recognition;
    let isListening = false;
    let speechSynthesis = window.speechSynthesis;

    // Initialize speech recognition
    function initSpeechRecognition() {
      if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
      } else if ('SpeechRecognition' in window) {
        recognition = new SpeechRecognition();
      } else {
        console.log('Speech recognition not supported');
        document.getElementById('voiceBtn').style.display = 'none';
        return;
      }

      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = function() {
        isListening = true;
        document.getElementById('voiceBtn').classList.add('listening');
        document.getElementById('voiceStatus').textContent = '🔴 Listening... Speak now';
      };

      recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        document.getElementById('command').value = transcript;
        document.getElementById('voiceStatus').textContent = `✅ Heard: "${transcript}"`;
        
        // Auto-send after voice input
        setTimeout(() => {
          sendCommand();
        }, 1000);
      };

      recognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        document.getElementById('voiceStatus').textContent = `❌ Error: ${event.error}`;
        stopListening();
      };

      recognition.onend = function() {
        stopListening();
      };
    }

    function toggleVoice() {
      if (!recognition) {
        alert('Speech recognition is not supported in this browser');
        return;
      }

      if (isListening) {
        recognition.stop();
      } else {
        recognition.start();
      }
    }

    function stopListening() {
      isListening = false;
      document.getElementById('voiceBtn').classList.remove('listening');
      if (document.getElementById('voiceStatus').textContent.includes('Listening')) {
        document.getElementById('voiceStatus').textContent = '🎤 Tap microphone to speak';
      }
    }

    function speakResponse(text) {
      if (!speechSynthesis) return;
      
      // Cancel any ongoing speech
      speechSynthesis.cancel();
      
      // Clean up the text for speech
      const cleanText = text.replace(/[📋✅❌🤔⚠️🔴]/g, '').replace(/\n/g, ' ');
      
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 0.8;
      
      speechSynthesis.speak(utterance);
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

    // Initialize speech recognition when page loads
    window.addEventListener('load', initSpeechRecognition);

    function sendCommand() {
      const input = document.getElementById('command');
      const output = document.getElementById('response');
      const userText = input.value.trim();

      if (!userText) {
        output.textContent = "⚠️ Please enter a command.";
        document.getElementById('voiceStatus').textContent = '';
        return;
      }

      output.textContent = "🤔 Processing...";
      document.getElementById('voiceStatus').textContent = '';

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        const responseText = "✅ " + (data.response || "Done!") + "\\n\\n📋 Details:\\n" + JSON.stringify(data.claude_output, null, 2);
        output.textContent = responseText;
        input.value = "";
        
        // Speak the response (just the main response, not the JSON details)
        speakResponse(data.response || "Task completed");
      })
      .catch(err => {
        const errorText = "❌ Error: " + err.message;
        output.textContent = errorText;
        speakResponse("Sorry, there was an error processing your request");
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

    // Voice commands shortcuts
    document.addEventListener('keydown', function(e) {
      // Press Space to activate voice (when not typing)
      if (e.code === 'Space' && document.activeElement !== document.getElementById('command')) {
        e.preventDefault();
        toggleVoice();
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
