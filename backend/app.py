# Minimal Flask Wake Word App - SMS Focus
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
    "wake_words": os.getenv("WAKE_WORDS", "hey ringly,ringly,hey ring,ring").split(","),
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

# Simple HTML template
def get_html_template():
    primary_wake_word = CONFIG['wake_word_primary']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wake Word SMS App</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      color: white;
    }}
    .container {{
      background: rgba(255,255,255,0.1);
      padding: 30px;
      border-radius: 15px;
      backdrop-filter: blur(10px);
    }}
    h1 {{
      text-align: center;
      margin-bottom: 30px;
    }}
    .wake-word {{
      background: #28a745;
      padding: 10px 20px;
      border-radius: 25px;
      text-align: center;
      margin-bottom: 20px;
      font-weight: bold;
    }}
    input {{
      width: 100%;
      padding: 15px;
      font-size: 16px;
      border: none;
      border-radius: 10px;
      margin-bottom: 15px;
      box-sizing: border-box;
    }}
    button {{
      width: 100%;
      padding: 15px;
      font-size: 16px;
      background: #007bff;
      color: white;
      border: none;
      border-radius: 10px;
      cursor: pointer;
    }}
    button:hover {{
      background: #0056b3;
    }}
    .response {{
      background: rgba(255,255,255,0.2);
      padding: 20px;
      border-radius: 10px;
      margin-top: 20px;
      min-height: 100px;
      white-space: pre-wrap;
    }}
    .examples {{
      background: rgba(255,255,255,0.1);
      padding: 15px;
      border-radius: 10px;
      margin-bottom: 20px;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>🎙️ Wake Word SMS App</h1>
    <div class="wake-word">🎯 Wake Word: "{primary_wake_word}"</div>
    
    <div class="examples">
      📱 SMS Examples:<br>
      • "{primary_wake_word}: text 8136414177 saying hey how are you"<br>
      • "{primary_wake_word}: send message to John saying meeting at 3pm"<br>
      • "{primary_wake_word}: text Mom saying I'll be home late"
    </div>
    
    <input type="text" id="command" placeholder="Type: '{primary_wake_word}: text John saying hello'" />
    <button onclick="sendCommand()">Send Command</button>
    
    <div class="response" id="response">
      🎙️ Wake Word System Ready!<br><br>
      Start commands with "{primary_wake_word}"<br><br>
      Example: "{primary_wake_word}: text John saying hello"
    </div>
  </div>

  <script>
    function sendCommand() {{
      const input = document.getElementById('command');
      const output = document.getElementById('response');
      const userText = input.value.trim();

      if (!userText) {{
        output.textContent = '⚠️ Please enter a command starting with "{primary_wake_word}"';
        return;
      }}

      output.textContent = "🎙️ Processing wake word command...";

      fetch("/execute", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ text: userText }})
      }})
      .then(res => res.json())
      .then(data => {{
        let responseText = "✅ " + (data.response || "Done!");
        
        if (data.claude_output && data.claude_output.wake_word_info) {{
          const wakeInfo = data.claude_output.wake_word_info;
          responseText += "\\n\\n🎙️ Wake Word: " + wakeInfo.wake_word_detected;
        }}
        
        output.textContent = responseText;
        input.value = "";
      }})
      .catch(err => {{
        output.textContent = "❌ Error: " + err.message;
      }});
    }}

    document.getElementById('command').addEventListener('keypress', function(e) {{
      if (e.key === 'Enter') {{
        sendCommand();
      }}
    }});
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
    print("🚀 Starting Minimal Wake Word SMS App")
    print(f"🎙️ Primary Wake Word: '{CONFIG['wake_word_primary']}'")
    print(f"📱 Twilio: {'✅ Ready' if twilio_client.client else '❌ Not configured'}")
    print(f"🤖 Claude: {'✅ Ready' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting on port {port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
