# Enhanced Flask CMP Server with PWA capabilities, Voice Input, and Bilingual Support
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

CONFIG = {
    "provider": "claude",
    "claude_api_key": os.getenv("CLAUDE_API_KEY", "")
}

# Enhanced instruction prompt with bilingual support and business Q&A
INSTRUCTION_PROMPT = """
You are an intelligent bilingual assistant that can respond in both English and Spanish. 
Detect the language of the user's input and respond in the same language.

You can handle two types of requests:

1. GENERAL BUSINESS QUESTIONS: For general questions, advice, or information requests, respond with helpful information in a conversational manner. Use this JSON structure:
{
  "action": "general_response",
  "response": "Your helpful response here",
  "language": "en" or "es"
}

2. SPECIFIC ACTIONS: For requests that require specific actions, use one of these structures:

For tasks:
{
  "action": "create_task",
  "title": "Task title",
  "due_date": "YYYY-MM-DDTHH:MM:SS" or null,
  "notes": "Additional details",
  "language": "en" or "es"
}

For appointments:
{
  "action": "create_appointment", 
  "title": "Appointment title",
  "due_date": "YYYY-MM-DDTHH:MM:SS" or null,
  "notes": "Additional details",
  "language": "en" or "es"
}

For messages:
{
  "action": "send_message",
  "recipient": "Name or contact",
  "message": "Message content",
  "language": "en" or "es"
}

For conversation logs:
{
  "action": "log_conversation",
  "notes": "Conversation transcript or summary",
  "language": "en" or "es"
}

Examples of general business questions to answer directly:
- "What is market research?" / "¿Qué es investigación de mercado?"
- "How do I improve customer service?" / "¿Cómo mejoro el servicio al cliente?"
- "What are the best marketing strategies?" / "¿Cuáles son las mejores estrategias de marketing?"
- "How do I write a business plan?" / "¿Cómo escribo un plan de negocios?"

Examples of action requests:
- "Schedule a meeting with John tomorrow at 2pm" / "Programa una reunión con Juan mañana a las 2pm"
- "Create a task to review the presentation" / "Crea una tarea para revisar la presentación"
- "Send a message to Maria about the project" / "Envía un mensaje a María sobre el proyecto"

Always respond with valid JSON only. No extra commentary outside the JSON structure.
"""

def detect_language(text):
    """Simple language detection based on common Spanish words and patterns"""
    spanish_indicators = [
        'qué', 'cómo', 'cuál', 'cuáles', 'dónde', 'cuándo', 'por qué', 'para qué',
        'es', 'son', 'está', 'están', 'soy', 'eres', 'somos', 'fue', 'fueron',
        'con', 'sin', 'para', 'por', 'de', 'del', 'la', 'las', 'el', 'los',
        'una', 'unas', 'un', 'unos', 'y', 'o', 'pero', 'si', 'no', 'sí',
        'muy', 'más', 'menos', 'también', 'tampoco', 'ahora', 'después',
        'antes', 'siempre', 'nunca', 'aquí', 'allí', 'esto', 'eso', 'ese',
        'esta', 'esa', 'estos', 'esos', 'estas', 'esas', 'me', 'te', 'se',
        'nos', 'les', 'le', 'lo', 'la', 'mi', 'tu', 'su', 'nuestro', 'vuestro'
    ]
    
    text_lower = text.lower()
    spanish_count = sum(1 for word in spanish_indicators if word in text_lower)
    
    # Check for Spanish accents
    spanish_accents = re.findall(r'[áéíóúüñ¿¡]', text_lower)
    
    return 'es' if spanish_count >= 2 or len(spanish_accents) > 0 else 'en'

def call_claude(prompt):
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Detect language and add context
        detected_lang = detect_language(prompt)
        lang_context = "Respond in Spanish." if detected_lang == 'es' else "Respond in English."
        
        full_prompt = f"{INSTRUCTION_PROMPT}\n\n{lang_context}\n\nUser: {prompt}"

        body = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1500,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": full_prompt}]
        }

        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, data=json.dumps(body))
        response_json = res.json()
        
        if "content" in response_json:
            raw_text = response_json["content"][0]["text"]
            # Clean up the response to extract JSON
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return parsed
            else:
                return {"error": "Could not parse JSON response from Claude."}
        else:
            return {"error": "Claude response missing content."}
    except Exception as e:
        return {"error": str(e)}

# ----- Enhanced Action Handlers -----

def handle_general_response(data):
    """Handle general business questions and advice"""
    response = data.get("response", "I'm here to help!")
    language = data.get("language", "en")
    
    if language == "es":
        print(f"[AI Assistant] Respuesta general: {response}")
    else:
        print(f"[AI Assistant] General response: {response}")
    
    return response

def handle_create_task(data):
    language = data.get("language", "en")
    title = data.get("title", "")
    due_date = data.get("due_date", "")
    notes = data.get("notes", "")
    
    print(f"[CMP] Creating task: {title}, due: {due_date}")
    
    if language == "es":
        return f"Tarea '{title}' programada para {due_date if due_date else 'fecha por determinar'}."
    else:
        return f"Task '{title}' scheduled for {due_date if due_date else 'no specific date'}."

def handle_create_appointment(data):
    language = data.get("language", "en")
    title = data.get("title", "")
    due_date = data.get("due_date", "")
    notes = data.get("notes", "")
    
    print(f"[CMP] Creating appointment: {title}, date: {due_date}")
    
    if language == "es":
        return f"Cita '{title}' programada para {due_date if due_date else 'fecha por determinar'}."
    else:
        return f"Appointment '{title}' booked for {due_date if due_date else 'no specific date'}."

def handle_send_message(data):
    language = data.get("language", "en")
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    
    print(f"[CMP] Sending message to {recipient}: {message}")
    
    if language == "es":
        return f"Mensaje enviado a {recipient}."
    else:
        return f"Message sent to {recipient}."

def handle_log_conversation(data):
    language = data.get("language", "en")
    notes = data.get("notes", "")
    
    print(f"[CMP] Logging conversation: {notes}")
    
    if language == "es":
        return "Conversación guardada en el registro."
    else:
        return "Conversation log saved."

def dispatch_action(parsed):
    action = parsed.get("action")
    
    if action == "general_response":
        return handle_general_response(parsed)
    elif action == "create_task":
        return handle_create_task(parsed)
    elif action == "create_appointment":
        return handle_create_appointment(parsed)
    elif action == "send_message":
        return handle_send_message(parsed)
    elif action == "log_conversation":
        return handle_log_conversation(parsed)
    else:
        language = parsed.get("language", "en")
        if language == "es":
            return f"Acción desconocida: {action}"
        else:
            return f"Unknown action: {action}"

# ----- PWA Manifest -----
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Smart AI Business Assistant",
        "short_name": "AI Assistant",
        "description": "Bilingual AI-powered business assistant with voice input (English/Spanish)",
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
        "categories": ["business", "productivity", "utilities"],
        "orientation": "portrait",
        "lang": "en"
    })

# ----- Service Worker -----
@app.route('/sw.js')
def service_worker():
    return '''
const CACHE_NAME = 'ai-assistant-v2';
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

# ----- Enhanced Mobile-Optimized HTML Template -----
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>Smart AI Business Assistant</title>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#007bff">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="AI Assistant">
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
      max-width: 450px;
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

    .language-toggle {
      display: flex;
      justify-content: center;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }

    .lang-btn {
      padding: 8px 16px;
      border: 2px solid rgba(255,255,255,0.3);
      border-radius: 20px;
      background: rgba(255,255,255,0.1);
      color: rgba(255,255,255,0.8);
      cursor: pointer;
      transition: all 0.3s;
      font-size: 0.9rem;
    }

    .lang-btn.active {
      background: rgba(255,255,255,0.3);
      color: white;
      border-color: rgba(255,255,255,0.6);
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
      font-size: 15px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-wrap: break-word;
      color: rgba(255,255,255,0.95);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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

    .examples {
      background: rgba(255,255,255,0.05);
      border-radius: 12px;
      padding: 1rem;
      margin-top: 1rem;
    }

    .examples h3 {
      font-size: 1rem;
      margin: 0 0 0.5rem 0;
      color: rgba(255,255,255,0.9);
    }

    .examples p {
      font-size: 0.8rem;
      color: rgba(255,255,255,0.7);
      margin: 0.3rem 0;
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
    <h1>🤖 Smart AI Business Assistant</h1>
    <div class="subtitle">Bilingual AI assistant for business tasks and general questions</div>
    
    <div class="language-toggle">
      <button class="lang-btn active" onclick="setLanguage('en')">🇺🇸 English</button>
      <button class="lang-btn" onclick="setLanguage('es')">🇪🇸 Español</button>
    </div>
    
    <div class="input-container">
      <div class="input-group">
        <input type="text" id="command" placeholder="What would you like me to help you with?" />
        <button onclick="sendCommand()">Send</button>
      </div>
    </div>

    <div class="response-container">
      <div class="response-text" id="response">Ready to help! Ask me about business topics, schedule appointments, create tasks, or send messages. I can respond in English or Spanish!</div>
    </div>

    <div class="voice-controls">
      <button class="mic-button" id="micButton" onclick="toggleVoiceRecording()">
        🎤
      </button>
    </div>
    <div class="voice-status" id="voiceStatus"></div>

    <div class="examples">
      <h3 id="examplesTitle">Examples:</h3>
      <div id="examplesContent">
        <p>• "What is digital marketing?" / "¿Qué es el marketing digital?"</p>
        <p>• "How do I improve customer retention?" / "¿Cómo mejoro la retención de clientes?"</p>
        <p>• "Schedule a meeting tomorrow at 3pm" / "Programa una reunión mañana a las 3pm"</p>
        <p>• "Create a task to review quarterly reports" / "Crea una tarea para revisar informes trimestrales"</p>
      </div>
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
    let isRecording = false;
    let voiceSupported = false;
    let currentLanguage = 'en';

    const translations = {
      en: {
        placeholder: "What would you like me to help you with?",
        ready: "Ready to help! Ask me about business topics, schedule appointments, create tasks, or send messages. I can respond in English or Spanish!",
        processing: "🤔 Processing...",
        error: "❌ Error: ",
        warning: "⚠️ Please enter a command or use voice input.",
        listening: "🎤 Listening...",
        heard: "📝 Heard: ",
        micStatus: "Tap microphone to speak",
        examplesTitle: "Examples:",
        send: "Send"
      },
      es: {
        placeholder: "¿En qué puedo ayudarte?",
        ready: "¡Listo para ayudar! Pregúntame sobre temas de negocios, programa citas, crea tareas, o envía mensajes. ¡Puedo responder en inglés o español!",
        processing: "🤔 Procesando...",
        error: "❌ Error: ",
        warning: "⚠️ Por favor ingresa un comando o usa entrada de voz.",
        listening: "🎤 Escuchando...",
        heard: "📝 Escuché: ",
        micStatus: "Toca el micrófono para hablar",
        examplesTitle: "Ejemplos:",
        send: "Enviar"
      }
    };

    function setLanguage(lang) {
      currentLanguage = lang;
      
      // Update active language button
      document.querySelectorAll('.lang-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      
      // Update UI text
      const t = translations[lang];
      document.getElementById('command').placeholder = t.placeholder;
      document.getElementById('response').textContent = t.ready;
      document.getElementById('examplesTitle').textContent = t.examplesTitle;
      document.querySelector('button[onclick="sendCommand()"]').textContent = t.send;
      
      if (voiceSupported) {
        document.getElementById('voiceStatus').textContent = t.micStatus;
      }
      
      // Update speech recognition language
      if (recognition) {
        recognition.lang = lang === 'es' ? 'es-ES' : 'en-US';
      }
    }

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
          document.getElementById('voiceStatus').textContent = translations[currentLanguage].listening;
        };
        
        recognition.onresult = function(event) {
          const transcript = event.results[0][0].transcript;
          document.getElementById('command').value = transcript;
          document.getElementById('voiceStatus').textContent = translations[currentLanguage].heard + `"${transcript}"`;
          
          // Auto-submit after voice input
          setTimeout(() => {
            sendCommand();
          }, 1000);
        };
        
        recognition.onerror = function(event) {
          console.error('Speech recognition error:', event.error);
          document.getElementById('voiceStatus').textContent = translations[currentLanguage].error + event.error;
          stopRecording();
        };
        
        recognition.onend = function() {
          stopRecording();
        };
        
        voiceSupported = true;
        document.getElementById('voiceStatus').textContent = translations[currentLanguage].micStatus;
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
          document.getElementById('voiceStatus').textContent = translations[currentLanguage].error + 'Failed to start voice input';
        }
      }
    }

    function stopRecording() {
      isRecording = false;
      document.getElementById('micButton').classList.remove('recording');
      if (document.getElementById('voiceStatus').textContent.includes('Listening') || 
          document.getElementById('voiceStatus').textContent.includes('Escuchando')) {
        document.getElementById('voiceStatus').textContent = translations[currentLanguage].micStatus;
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
        output.textContent = translations[currentLanguage].warning;
        return;
      }

      output.textContent = translations[currentLanguage].processing;

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        if (data.claude_output && data.claude_output.action === 'general_response') {
          // For general responses, show the response directly
          output.textContent = data.claude_output.response;
        } else {
          // For actions, show confirmation + details
          output.textContent = "✅ " + (data.response || "Done!") + "\n\n📋 Details:\n" + JSON.stringify(data.claude_output, null, 2);
        }
        input.value = "";
        if (voiceSupported) {
          document.getElementById('voiceStatus').textContent = translations[currentLanguage].micStatus;
        }
      })
      .catch(err => {
        output.textContent = translations[currentLanguage].error + err.message;
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

    // Initialize speech recognition and set default language when page loads
    window.addEventListener('load', function() {
      initSpeechRecognition();
      setLanguage('en'); // Set default language
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
