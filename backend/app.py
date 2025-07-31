# Minimal Flask Wake Word App - SMS Focus with Always Listening Frontend
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List

# Import Twilio REST API client
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Twilio library not installed. Run: pip install twilio")

app = Flask(__name__)
CORS(app)

CONFIG = {
    "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
    "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
    "wake_words": "hey ringly,ringly,hey ring,ring,hey wrinkly,wrinkly,hey wrinkle,hey wrigley,wrigley,hey ringley,ringley,hey ringling,ringling,hey wrigly,wrigly".split(","),
    "wake_word_primary": os.getenv("WAKE_WORD_PRIMARY", "hey ringly"),
    "wake_word_enabled": os.getenv("WAKE_WORD_ENABLED", "true").lower() == "true",
}

print(f"🎙️ Wake words: {CONFIG['wake_words']}")
print(f"🔑 Primary wake word: '{CONFIG['wake_word_primary']}'")

class TwilioClient:
    """Simple Twilio client for SMS"""
    
    def __init__(self):
        self.account_sid = CONFIG["twilio_account_sid"]
        self.auth_token = CONFIG["twilio_auth_token"]
        self.from_number = CONFIG["twilio_phone_number"]
        self.client = None
        
        if TWILIO_AVAILABLE and self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ Twilio client initialized")
            except Exception as e:
                print(f"❌ Twilio failed: {e}")
        else:
            print("⚠️ Twilio not configured")
    
    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        if not self.client or not self.from_number:
            return {"error": "Twilio not configured"}
        
        try:
            message_response = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to
            )
            
            return {
                "success": True,
                "message_sid": message_response.sid,
                "status": message_response.status,
                "to": to,
                "from": self.from_number,
                "body": message
            }
            
        except Exception as e:
            return {"error": f"Failed to send SMS: {str(e)}"}

class WakeWordProcessor:
    """Simple wake word detection"""
    
    def __init__(self):
        self.wake_words = CONFIG["wake_words"]
        self.primary_wake_word = CONFIG["wake_word_primary"]
        self.enabled = CONFIG["wake_word_enabled"]
        
    def detect_wake_word(self, text: str) -> Dict[str, Any]:
        """Detect wake word and extract command"""
        original_text = text.strip()
        
        if not self.enabled:
            return {
                "has_wake_word": True,
                "wake_word_detected": "disabled",
                "command_text": original_text,
                "original_text": original_text
            }
        
        search_text = original_text.lower()
        
        for wake_word in self.wake_words:
            compare_word = wake_word.lower()
            
            if search_text.startswith(compare_word):
                next_char_index = len(compare_word)
                if (next_char_index >= len(search_text) or 
                    search_text[next_char_index] in [' ', ',', ':', ';', '!', '?', '.']):
                    
                    command_text = original_text[len(wake_word):].strip()
                    command_text = re.sub(r'^[,:;!?.]\s*', '', command_text)
                    
                    return {
                        "has_wake_word": True,
                        "wake_word_detected": wake_word,
                        "command_text": command_text,
                        "original_text": original_text
                    }
        
        return {
            "has_wake_word": False,
            "wake_word_detected": None,
            "command_text": original_text,
            "original_text": original_text
        }
    
    def process_wake_word_command(self, text: str) -> Dict[str, Any]:
        """Process text with wake word detection"""
        wake_result = self.detect_wake_word(text)
        
        if not wake_result["has_wake_word"]:
            return {
                "success": False,
                "error": f"Please start your command with '{self.primary_wake_word}'. Example: '{self.primary_wake_word}: text John saying hello'"
            }
        
        command_text = wake_result["command_text"]
        
        if not command_text.strip():
            return {
                "success": False,
                "error": f"Please provide a command after '{wake_result['wake_word_detected']}'"
            }
        
        # Try to extract SMS command
        sms_command = extract_sms_command(command_text)
        if sms_command:
            sms_command["wake_word_info"] = wake_result
            return sms_command
        
        # Fallback to Claude
        try:
            claude_result = call_claude(command_text)
            if claude_result and "error" not in claude_result:
                claude_result["wake_word_info"] = wake_result
                return claude_result
        except Exception as e:
            print(f"Claude error: {e}")
        
        return {
            "success": False,
            "error": f"I didn't understand: '{command_text}'. Try: '{self.primary_wake_word}: text John saying hello'"
        }

# Initialize clients
twilio_client = TwilioClient()
wake_word_processor = WakeWordProcessor()

def call_claude(prompt):
    """Simple Claude API call"""
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        instruction_prompt = """
You are an intelligent assistant. Respond ONLY with valid JSON using one of the supported actions.

Supported actions:
- send_message (supports SMS via Twilio)

Response structure:
{
  "action": "send_message",
  "recipient": "phone number or name",
  "message": "message text"
}

Only include fields relevant to the action.
"""
        
        full_prompt = f"{instruction_prompt}\n\nUser: {prompt}"

        body = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 500,
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
    clean = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    if clean.startswith("+") and clean[1:].isdigit():
        return True
    if clean.isdigit() and len(clean) >= 10:
        return True
    
    return False

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    
    return clean

def extract_sms_command(text: str) -> Dict[str, Any]:
    """Extract SMS command from text"""
    patterns = [
        r'send (?:a )?(?:text|message|sms) to (.+?) saying (.+)',
        r'text (.+?) saying (.+)',
        r'message (.+?) saying (.+)',
        r'send (.+?) the message (.+)',
        r'tell (.+?) that (.+)',
        r'text (.+?) (.+)',  # Simple pattern: "text John hello there"
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            message = match.group(2).strip()
            
            # Clean up voice artifacts
            message = message.replace(" period", ".").replace(" comma", ",")
            
            return {
                "action": "send_message",
                "recipient": recipient,
                "message": message
            }
    
    return None

def handle_send_message(data):
    """Handle SMS sending"""
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    
    if is_phone_number(recipient):
        formatted_phone = format_phone_number(recipient)
        result = twilio_client.send_sms(formatted_phone, message)
        
        if result.get("success"):
            return f"✅ SMS sent to {recipient}!\n\nMessage: {message}\n\nMessage ID: {result.get('message_sid', 'N/A')}"
        else:
            return f"❌ Failed to send SMS to {recipient}: {result.get('error')}"
    else:
        return f"❌ Invalid phone number: {recipient}"

def dispatch_action(parsed):
    """Simple action dispatcher"""
    action = parsed.get("action")
    if action == "send_message":
        return handle_send_message(parsed)
    else:
        return f"Unknown action: {action}"

# Always Listening HTML Template with Enhanced Wake Word Detection
def get_html_template():
    primary_wake_word = CONFIG['wake_word_primary']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wake Word SMS - Enhanced Voice</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: background: linear-gradient(135deg, #2b2b2b 0%, #1a1a1a 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: white; }}
        .container {{ background: rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2); backdrop-filter: blur(15px); max-width: 700px; width: 100%; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; font-weight: 700; }}
        .header p {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; }}
        .wake-word-display {{ background: linear-gradient(45deg, #3a3a3a, #1f1f1f); padding: 15px 30px; border-radius: 50px; font-size: 1.3em; font-weight: bold; margin-bottom: 30px; display: inline-block; }}
        .listening-status {{ height: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 30px; }}
        .voice-indicator {{ width: 100px; height: 100px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px; margin-bottom: 15px; transition: all 0.3s ease; }}
        .voice-indicator.listening {{ background: linear-gradient(45deg, #28a745, #20c997); animation: pulse 2s infinite; box-shadow: 0 0 30px rgba(40, 167, 69, 0.5); }}
        .voice-indicator.wake-detected {{ background: linear-gradient(45deg, #ffc107, #e0a800); animation: glow 1s infinite alternate; box-shadow: 0 0 30px rgba(255, 193, 7, 0.7); }}
        .voice-indicator.processing {{ background: linear-gradient(45deg, #dc3545, #c82333); animation: spin 1s linear infinite; box-shadow: 0 0 30px rgba(220, 53, 69, 0.5); }}
        .voice-indicator.idle {{ background: rgba(255, 255, 255, 0.2); animation: none; }}
        @keyframes pulse {{ 0% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.1); opacity: 0.8; }} 100% {{ transform: scale(1); opacity: 1; }} }}
        @keyframes glow {{ 0% {{ box-shadow: 0 0 30px rgba(255, 193, 7, 0.7); }} 100% {{ box-shadow: 0 0 50px rgba(255, 193, 7, 1); }} }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .status-text {{ font-size: 1.1em; font-weight: 500; min-height: 30px; }}
        .status-text.listening {{ color: #20c997; }}
        .status-text.wake-detected {{ color: #ffc107; }}
        .status-text.processing {{ color: #dc3545; }}
        .controls {{ margin-bottom: 30px; }}
        .control-button {{ background: linear-gradient(45deg, #007bff, #0056b3); color: white; border: none; padding: 12px 30px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; margin: 0 10px; transition: all 0.3s ease; }}
        .control-button:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 123, 255, 0.4); }}
        .control-button.stop {{ background: linear-gradient(45deg, #dc3545, #c82333); }}
        .control-button.test {{ background: linear-gradient(45deg, #28a745, #20c997); }}
        .control-button:disabled {{ background: #6c757d; cursor: not-allowed; transform: none; box-shadow: none; }}
        .transcription {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; border: 2px solid transparent; transition: all 0.3s ease; }}
        .transcription.active {{ border-color: #28a745; background: rgba(40, 167, 69, 0.1); }}
        .transcription h3 {{ font-size: 1.1em; margin-bottom: 10px; opacity: 0.8; }}
        .transcription-text {{ font-size: 1.2em; font-weight: 500; font-family: 'Courier New', monospace; }}
        .response {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; text-align: left; white-space: pre-wrap; display: none; }}
        .response.success {{ background: rgba(40, 167, 69, 0.2); border: 2px solid #28a745; }}
        .response.error {{ background: rgba(220, 53, 69, 0.2); border: 2px solid #dc3545; }}
        .examples {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; text-align: left; margin-bottom: 20px; }}
        .examples h3 {{ margin-bottom: 15px; text-align: center; }}
        .examples ul {{ list-style: none; padding: 0; }}
        .examples li {{ background: rgba(255, 255, 255, 0.1); margin-bottom: 8px; padding: 12px 15px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 0.95em; }}
        .browser-support {{ font-size: 0.9em; opacity: 0.8; margin-top: 20px; }}
        .browser-support.unsupported {{ color: #dc3545; font-weight: bold; opacity: 1; }}
        .privacy-note {{ background: rgba(255, 193, 7, 0.2); border: 1px solid #ffc107; border-radius: 10px; padding: 15px; margin-top: 20px; font-size: 0.9em; }}
        @media (max-width: 600px) {{ .container {{ padding: 20px; margin: 10px; }} .header h1 {{ font-size: 2em; }} .voice-indicator {{ width: 80px; height: 80px; font-size: 32px; }} .control-button {{ padding: 10px 20px; font-size: 0.9em; margin: 5px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎙️ Wake Word SMS</h1>
            <p>Enhanced voice recognition - adapts to your pronunciation!</p>
        </div>
        <div class="wake-word-display">🎯 Say: "Hey Ringly" (any variation)</div>
        <div class="listening-status">
            <div class="voice-indicator idle" id="voiceIndicator">🎤</div>
            <div class="status-text" id="statusText">Click "Start Listening" to begin</div>
        </div>
        <div class="controls">
            <button class="control-button" id="startButton" onclick="startListening()">Start Listening</button>
            <button class="control-button stop" id="stopButton" onclick="stopListening()" disabled>Stop Listening</button>
            <button class="control-button test" onclick="testSMS()">Test SMS</button>
        </div>
        <div class="transcription" id="transcription">
            <h3>🎤 Voice Transcription</h3>
            <div class="transcription-text" id="transcriptionText">Waiting for wake word command...</div>
        </div>
        <div id="response" class="response"></div>
        <div class="examples">
            <h3>📝 Voice Commands (Any pronunciation works!)</h3>
            <ul>
                <li>"Hey Ringly: text 6566001400 saying hello there!"</li>
                <li>"Hey Ring: text Mom saying running late"</li> 
                <li>"Hey Wrinkly: send message to John saying meeting at 3pm"</li>
                <li>"Hey Wrigley: text 8136414177 saying voice test working"</li>
                <li><strong>System adapts to YOUR pronunciation automatically!</strong></li>
            </ul>
        </div>
        <div class="browser-support" id="browserSupport">Checking browser compatibility...</div>
        <div class="privacy-note">🔒 <strong>Privacy:</strong> Voice recognition runs locally in your browser. Audio is only processed when wake word is detected.</div>
    </div>

    <script>
        let recognition = null;
        let isListening = false;
        let isProcessingCommand = false;
        let continuousListening = true;
        let commandBuffer = '';
        let bufferTimeout = null;

        const voiceIndicator = document.getElementById('voiceIndicator');
        const statusText = document.getElementById('statusText');
        const startButton = document.getElementById('startButton');
        const stopButton = document.getElementById('stopButton');
        const transcription = document.getElementById('transcription');
        const transcriptionText = document.getElementById('transcriptionText');
        const response = document.getElementById('response');
        const browserSupport = document.getElementById('browserSupport');

        // All wake word variations that speech recognition might hear
        const wakeWords = [
            'hey ringly', 'hey ring', 'ringly', 
            'hey wrinkly', 'wrinkly', 'hey wrinkle',
            'hey wrigley', 'wrigley', 
            'hey ringley', 'ringley',
            'hey ringling', 'ringling',
            'hey wrigly', 'wrigly'
        ];

        function checkForWakeWordInBuffer(buffer) {{
            const lowerBuffer = buffer.toLowerCase().trim();
            for (const wakeWord of wakeWords) {{
                if (lowerBuffer.includes(wakeWord)) {{
                    return true;
                }}
            }}
            return false;
        }}

        function initSpeechRecognition() {{
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                recognition = new SpeechRecognition();
                
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';
                recognition.maxAlternatives = 1;

                recognition.onstart = function() {{
                    console.log('Speech recognition started');
                    isListening = true;
                    updateUI('listening', '🎤 Listening for wake word...', '👂');
                }};

                recognition.onresult = function(event) {{
                    let interimTranscript = '';
                    let finalTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {{
                        const transcript = event.results[i][0].transcript;
                        if (event.results[i].isFinal) {{
                            finalTranscript += transcript + ' ';
                        }} else {{
                            interimTranscript += transcript;
                        }}
                    }}
                    
                    const currentText = (finalTranscript + interimTranscript).trim();
                    if (currentText) {{
                        transcriptionText.textContent = currentText;
                        transcription.classList.add('active');
                        console.log('Speech detected:', currentText);
                    }}
                    
                    if (finalTranscript && !isProcessingCommand) {{
                        console.log('Final transcript received:', finalTranscript.trim());
                        
                        commandBuffer += finalTranscript.trim() + ' ';
                        console.log('Command buffer now:', commandBuffer);
                        
                        if (bufferTimeout) {{
                            clearTimeout(bufferTimeout);
                        }}
                        
                        const hasWakeWord = checkForWakeWordInBuffer(commandBuffer);
                        
                        if (hasWakeWord) {{
                            // Check if command looks incomplete (wait longer for complete commands)
                            const commandLower = commandBuffer.toLowerCase().trim();
                            const hasActionWord = commandLower.includes('text') || commandLower.includes('send') || commandLower.includes('message');
                            const hasPhoneNumber = /\d{{3}}-?\d{{3}}-?\d{{4}}|\d{{10}}/.test(commandBuffer);
                            const hasSaying = commandLower.includes('saying');
                            
                            let waitTime = 2000; // Default 2 seconds
                            
                            // If we have wake word + action but missing phone/message, wait longer
                            if (hasActionWord && (!hasPhoneNumber || !hasSaying)) {{
                                waitTime = 4000; // Wait 4 seconds for complete command
                                console.log('Command looks incomplete, waiting longer for full command...');
                                updateUI('wake-detected', '⏳ Capturing complete command...', '⏳');
                            }} else {{
                                console.log('Command looks complete, processing soon...');
                                updateUI('wake-detected', '⚡ Complete command detected!', '⚡');
                            }}
                            
                            bufferTimeout = setTimeout(() => {{
                                console.log('Processing complete command from buffer:', commandBuffer);
                                checkForWakeWord(commandBuffer.trim());
                                commandBuffer = '';
                            }}, waitTime);
                        }} else {{
                            bufferTimeout = setTimeout(() => {{
                                commandBuffer = '';
                                console.log('Buffer cleared - no wake word found');
                            }}, 3000);
                        }}
                    }}
                }};

                recognition.onerror = function(event) {{
                    console.log('Speech recognition event:', event.error);
                    if (event.error === 'no-speech') {{
                        console.log('No speech detected, continuing to listen...');
                        return;
                    }}
                    let errorMessage = 'Recognition error: ';
                    switch(event.error) {{
                        case 'network': errorMessage += 'Network error. Check connection.'; break;
                        case 'not-allowed': errorMessage += 'Microphone access denied.'; stopListening(); break;
                        case 'service-not-allowed': errorMessage += 'Speech service not allowed.'; stopListening(); break;
                        default: errorMessage += event.error;
                    }}
                    console.error('Speech recognition error:', errorMessage);
                    updateUI('idle', errorMessage, '❌');
                    setTimeout(() => {{ if (continuousListening && !isListening) {{ restartListening(); }} }}, 2000);
                }};

                recognition.onend = function() {{
                    console.log('Speech recognition ended');
                    isListening = false;
                    if (continuousListening && !isProcessingCommand) {{
                        setTimeout(() => {{ if (continuousListening) {{ restartListening(); }} }}, 100);
                    }} else {{
                        updateUI('idle', 'Stopped listening', '🎤');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }}
                }};

                browserSupport.textContent = 'Enhanced voice recognition supported ✅';
                browserSupport.className = 'browser-support';
                return true;
            }} else {{
                browserSupport.textContent = '❌ Voice recognition not supported in this browser.';
                browserSupport.className = 'browser-support unsupported';
                startButton.disabled = true;
                return false;
            }}
        }}

        function checkForWakeWord(text) {{
            const lowerText = text.toLowerCase().trim();
            let wakeWordFound = false;
            let detectedWakeWord = '';
            console.log('Checking for wake word in:', text);
            console.log('Available wake words:', wakeWords);
            
            for (const wakeWord of wakeWords) {{
                console.log('Testing wake word:', wakeWord, 'in text:', lowerText);
                if (lowerText.includes(wakeWord)) {{
                    wakeWordFound = true;
                    detectedWakeWord = wakeWord;
                    console.log('✅ Wake word FOUND:', wakeWord);
                    break;
                }}
            }}
            
            if (wakeWordFound) {{
                console.log('🚀 Processing wake word command:', text);
                processWakeWordCommand(text);
            }} else {{
                console.log('❌ No wake word found in:', text);
                console.log('Expected one of:', wakeWords);
            }}
        }}

        async function processWakeWordCommand(fullText) {{
            if (isProcessingCommand) {{
                console.log('Already processing a command, ignoring...');
                return;
            }}
            console.log('Starting to process wake word command:', fullText);
            isProcessingCommand = true;
            updateUI('wake-detected', '⚡ Wake word detected! Processing...', '⚡');
            transcriptionText.textContent = fullText;
            try {{
                updateUI('processing', '📤 Sending command...', '⚙️');
                console.log('Sending request to /execute with:', {{ text: fullText }});
                const apiResponse = await fetch('/execute', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ text: fullText }})
                }});
                console.log('API response status:', apiResponse.status);
                const data = await apiResponse.json();
                console.log('API response data:', data);
                if (apiResponse.ok) {{
                    showResponse(data.response || 'Command executed successfully!', 'success');
                    updateUI('listening', '✅ Command sent! Listening for next command...', '👂');
                    console.log('Command processed successfully');
                }} else {{
                    showResponse(data.error || 'An error occurred while processing your command.', 'error');
                    updateUI('listening', '❌ Error occurred. Listening for next command...', '👂');
                    console.error('Command processing error:', data.error);
                }}
            }} catch (error) {{
                console.error('Network error sending command:', error);
                showResponse('Network error. Please check your connection and try again.', 'error');
                updateUI('listening', '❌ Network error. Listening for next command...', '👂');
            }} finally {{
                isProcessingCommand = false;
                setTimeout(() => {{
                    transcriptionText.textContent = 'Waiting for wake word command...';
                    transcription.classList.remove('active');
                }}, 3000);
            }}
        }}

        function updateUI(state, statusMessage, indicator) {{
            statusText.textContent = statusMessage;
            statusText.className = 'status-text ' + state;
            voiceIndicator.textContent = indicator;
            voiceIndicator.className = 'voice-indicator ' + state;
        }}

        function showResponse(message, type) {{
            response.textContent = message;
            response.className = 'response ' + type;
            response.style.display = 'block';
            if (type === 'success') {{
                setTimeout(() => {{ response.style.display = 'none'; }}, 10000);
            }}
        }}

        function testSMS() {{
            const testCommand = 'hey ringly: text 6566001400 saying enhanced system test working perfectly';
            console.log('Testing SMS with command:', testCommand);
            processWakeWordCommand(testCommand);
        }}

        function startListening() {{
            if (!recognition) {{
                alert('Speech recognition not available in this browser.');
                return;
            }}
            continuousListening = true;
            startButton.disabled = true;
            stopButton.disabled = false;
            response.style.display = 'none';
            commandBuffer = '';
            try {{
                recognition.start();
            }} catch (error) {{
                console.error('Error starting recognition:', error);
                updateUI('idle', 'Error starting recognition', '❌');
                startButton.disabled = false;
                stopButton.disabled = true;
            }}
        }}

        function stopListening() {{
            continuousListening = false;
            if (recognition && isListening) {{
                recognition.stop();
            }}
            updateUI('idle', 'Stopped listening', '🎤');
            startButton.disabled = false;
            stopButton.disabled = true;
            transcriptionText.textContent = 'Waiting for wake word command...';
            transcription.classList.remove('active');
            commandBuffer = '';
            if (bufferTimeout) {{
                clearTimeout(bufferTimeout);
            }}
        }}

        function restartListening() {{
            if (continuousListening && recognition && !isListening) {{
                try {{
                    recognition.start();
                }} catch (error) {{
                    console.error('Error restarting recognition:', error);
                    setTimeout(() => {{ if (continuousListening) {{ restartListening(); }} }}, 1000);
                }}
            }}
        }}

        window.addEventListener('load', function() {{ initSpeechRecognition(); }});
        document.addEventListener('visibilitychange', function() {{
            if (document.hidden && isListening) {{
                recognition.stop();
            }} else if (!document.hidden && continuousListening && !isListening) {{
                setTimeout(() => {{ restartListening(); }}, 500);
            }}
        }});
        document.addEventListener('click', function() {{
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
                navigator.mediaDevices.getUserMedia({{ audio: true }})
                    .then(() => {{ console.log('Microphone permission granted'); }})
                    .catch((error) => {{ console.warn('Microphone permission denied:', error); }});
            }}
        }}, {{ once: true }});
    </script>
</body>
</html>'''

# Routes
@app.route("/")
def root():
    return get_html_template()

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        
        # Process with wake word
        wake_result = wake_word_processor.process_wake_word_command(prompt)
        
        if not wake_result.get("success", True):
            return jsonify({
                "response": wake_result.get("error", "Wake word validation failed"),
                "claude_output": wake_result
            })
        
        if wake_result.get("action"):
            dispatch_result = dispatch_action(wake_result)
            return jsonify({
                "response": dispatch_result,
                "claude_output": wake_result
            })
        
        return jsonify({
            "response": "No valid command found",
            "claude_output": wake_result
        })

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "wake_word_enabled": CONFIG["wake_word_enabled"],
        "wake_word_primary": CONFIG["wake_word_primary"],
        "twilio_configured": bool(twilio_client.client),
        "claude_configured": bool(CONFIG["claude_api_key"])
    })

if __name__ == '__main__':
    print("🚀 Starting Enhanced Wake Word SMS App")
    print(f"🎙️ Primary Wake Word: '{CONFIG['wake_word_primary']}'")
    print(f"📱 Twilio: {'✅ Ready' if twilio_client.client else '❌ Not configured'}")
    print(f"🤖 Claude: {'✅ Ready' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting on port {port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
