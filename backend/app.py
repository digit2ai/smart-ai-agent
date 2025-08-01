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

# Import email libraries
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

CONFIG = {
    "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
    "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
    "email_smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"),
    "email_smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
    "email_address": os.getenv("EMAIL_ADDRESS", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "wake_words": "hey ringly,ringly,hey ring,ring,hey wrinkly,wrinkly,hey wrinkle,hey wrigley,wrigley,hey ringley,ringley,hey ringling,ringling,hey wrigly,wrigly,cimanka, seemahnkah".split(","),
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

class EmailClient:
    """Simple Email client for sending emails"""
    
    def __init__(self):
        self.smtp_server = CONFIG["email_smtp_server"]
        self.smtp_port = CONFIG["email_smtp_port"]
        self.email_address = CONFIG["email_address"]
        self.email_password = CONFIG["email_password"]
        
        if self.email_address and self.email_password:
            print("✅ Email client initialized")
        else:
            print("⚠️ Email not configured")
    
    def send_email(self, to: str, subject: str, message: str) -> Dict[str, Any]:
        """Send email via SMTP"""
        if not self.email_address or not self.email_password:
            return {"error": "Email not configured"}
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to
            msg['Subject'] = subject
            
            # Add body to email
            msg.attach(MIMEText(message, 'plain'))
            
            # Create SMTP session
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Enable security
            server.login(self.email_address, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_address, to, text)
            server.quit()
            
            return {
                "success": True,
                "to": to,
                "from": self.email_address,
                "subject": subject,
                "body": message
            }
            
        except Exception as e:
            return {"error": f"Failed to send email: {str(e)}"}

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
        
        # Try to extract email command
        email_command = extract_email_command(command_text)
        if email_command:
            email_command["wake_word_info"] = wake_result
            return email_command
        
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
email_client = EmailClient()
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
- send_email (supports email via SMTP)

Response structure for SMS:
{
  "action": "send_message",
  "recipient": "phone number or name",
  "message": "message text"
}

Response structure for Email:
{
  "action": "send_email",
  "recipient": "email address",
  "subject": "email subject",
  "message": "email body"
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

def is_email_address(recipient: str) -> bool:
    """Check if recipient looks like an email address"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    
    return clean

def fix_email_addresses(text: str) -> str:
    """Fix email addresses that get split by speech recognition"""
    fixed_text = text
    
    # Most aggressive fix first: any words before @domain.com
    # This handles "Manuel stagg@gmail.com" -> "Manuelstagg@gmail.com"
    aggressive_patterns = [
        r'\b(\w+)\s+(\w+)@(gmail|yahoo|hotmail|outlook|icloud|aol)\.com\b',
        r'\b(\w+)\s+(\w+)\s+(\w+)@(gmail|yahoo|hotmail|outlook|icloud|aol)\.com\b',  # 3 words
        r'\b(\w+)\s+(\w+)@(\w+)\.com\b',  # Generic .com domains
    ]
    
    # Apply aggressive fixes first
    for pattern in aggressive_patterns:
        if r'\w+' in pattern and pattern.count(r'(\w+)') == 4:  # 3 words + domain
            fixed_text = re.sub(pattern, r'\1\2\3@\4.com', fixed_text, flags=re.IGNORECASE)
        else:  # 2 words + domain
            if r'(\w+)\.com' in pattern:
                fixed_text = re.sub(pattern, r'\1\2@\3.com', fixed_text, flags=re.IGNORECASE)
            else:
                fixed_text = re.sub(pattern, r'\1\2@\3.com', fixed_text, flags=re.IGNORECASE)
    
    # Handle other speech recognition patterns
    other_patterns = [
        r'\b(\w+)\s+(\w+)\s+(gmail|yahoo|hotmail|outlook|icloud)\.com\b',
        r'\b(\w+)\s+(\w+)\s+at\s+(gmail|yahoo|hotmail|outlook|icloud)\.com\b',
        r'\b(\w+)\s+(\w+)\s+(gmail|yahoo|hotmail|outlook|icloud)\s+dot\s+com\b',
        r'\b(\w+)\s+@(\w+\.\w+)\b',
    ]
    
    # Apply other fixes
    for pattern in other_patterns:
        if 'dot\s+com' in pattern:
            fixed_text = re.sub(pattern, r'\1\2@\3.com', fixed_text, flags=re.IGNORECASE)
        elif 'at\s+' in pattern:
            fixed_text = re.sub(pattern, r'\1\2@\3.com', fixed_text, flags=re.IGNORECASE)
        elif '@' in pattern:
            fixed_text = re.sub(pattern, r'\1@\2', fixed_text, flags=re.IGNORECASE)
        else:
            fixed_text = re.sub(pattern, r'\1\2@\3.com', fixed_text, flags=re.IGNORECASE)
    
    # Clean up common speech recognition substitutions
    speech_fixes = {
        r'\bstack@': 'stagg@',  # "stack" -> "stagg"
        r'\bstag@': 'stagg@',   # "stag" -> "stagg"  
        r'\bstac@': 'stagg@',   # "stac" -> "stagg"
    }
    
    for pattern, replacement in speech_fixes.items():
        fixed_text = re.sub(pattern, replacement, fixed_text, flags=re.IGNORECASE)
    
    return fixed_text

def extract_email_command(text: str) -> Dict[str, Any]:
    """Extract email command from text"""
    # Fix email addresses first
    fixed_text = fix_email_addresses(text)
    
    patterns = [
        r'send (?:an )?email to (.+?) (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) (?:with )?subject (.+?) saying (.+)',
        r'send (.+?) an email (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) saying (.+)',  # Simple pattern without subject
        r'send (?:an )?email to (.+?) saying (.+)',  # Simple pattern without subject
    ]
    
    text_lower = fixed_text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            if len(match.groups()) == 3:  # Has subject
                recipient = match.group(1).strip()
                subject = match.group(2).strip()
                message = match.group(3).strip()
            else:  # No subject
                recipient = match.group(1).strip()
                subject = "Voice Command Message"
                message = match.group(2).strip()
            
            # Clean up voice artifacts
            message = message.replace(" period", ".").replace(" comma", ",")
            subject = subject.replace(" period", ".").replace(" comma", ",")
            
            return {
                "action": "send_email",
                "recipient": recipient,
                "subject": subject,
                "message": message
            }
    
    return None

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

def handle_send_email(data):
    """Handle email sending"""
    recipient = data.get("recipient", "")
    subject = data.get("subject", "Voice Command Message")
    message = data.get("message", "")
    
    if is_email_address(recipient):
        result = email_client.send_email(recipient, subject, message)
        
        if result.get("success"):
            return f"✅ Email sent to {recipient}!\n\nSubject: {subject}\nMessage: {message}"
        else:
            return f"❌ Failed to send email to {recipient}: {result.get('error')}"
    else:
        return f"❌ Invalid email address: {recipient}"

def dispatch_action(parsed):
    """Simple action dispatcher"""
    action = parsed.get("action")
    if action == "send_message":
        return handle_send_message(parsed)
    elif action == "send_email":
        return handle_send_email(parsed)
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
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #2d2d2d url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: white; }}
        .container {{ background: rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2); backdrop-filter: blur(15px); max-width: 700px; width: 100%; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; font-weight: 700; }}
        .header img {{ max-height: 300px; margin-bottom: 20px; max-width: 95%; }}
        .header p {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; }}

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
        .control-button:disabled {{ background: #6c757d; cursor: not-allowed; transform: none; box-shadow: none; }}
        .manual-input {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; }}
        .manual-input h3 {{ margin-bottom: 15px; text-align: center; }}
        .input-group {{ display: flex; gap: 10px; align-items: center; }}
        .text-input {{ flex: 1; padding: 12px 15px; border: 2px solid rgba(255, 255, 255, 0.2); border-radius: 25px; background: rgba(255, 255, 255, 0.1); color: white; font-size: 1em; outline: none; transition: all 0.3s ease; }}
        .text-input:focus {{ border-color: #007bff; background: rgba(255, 255, 255, 0.15); }}
        .text-input::placeholder {{ color: rgba(255, 255, 255, 0.6); }}
        .send-button {{ background: linear-gradient(45deg, #28a745, #20c997); color: white; border: none; padding: 12px 25px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; transition: all 0.3s ease; }}
        .send-button:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(40, 167, 69, 0.4); }}
        .transcription {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; border: 2px solid transparent; transition: all 0.3s ease; }}
        .transcription.active {{ border-color: #28a745; background: rgba(40, 167, 69, 0.1); }}
        .transcription h3 {{ font-size: 1.1em; margin-bottom: 10px; opacity: 0.8; }}
        .transcription-text {{ font-size: 1.2em; font-weight: 500; font-family: 'Courier New', monospace; }}
        .response {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; text-align: left; white-space: pre-wrap; display: none; }}
        .response.success {{ background: rgba(40, 167, 69, 0.2); border: 2px solid #28a745; }}
        .response.error {{ background: rgba(220, 53, 69, 0.2); border: 2px solid #dc3545; }}

        .browser-support {{ font-size: 0.9em; opacity: 0.8; margin-top: 20px; }}
        .browser-support.unsupported {{ color: #dc3545; font-weight: bold; opacity: 1; }}
        .privacy-note {{ background: rgba(255, 193, 7, 0.2); border: 1px solid #ffc107; border-radius: 10px; padding: 15px; margin-top: 20px; font-size: 0.9em; }}
        @media (max-width: 600px) {{ .container {{ padding: 20px; margin: 10px; }} .header img {{ max-height: 220px; }} .voice-indicator {{ width: 80px; height: 80px; font-size: 32px; }} .control-button {{ padding: 10px 20px; font-size: 0.9em; margin: 5px; }} .input-group {{ flex-direction: column; gap: 15px; }} .text-input {{ width: 100%; margin-bottom: 10px; }} .send-button {{ width: 100%; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp" alt="Wake Word SMS Logo" />
            <p>Enhanced voice recognition - adapts to your pronunciation!</p>
        </div>

        <div class="listening-status">
            <div class="voice-indicator idle" id="voiceIndicator">🎤</div>
            <div class="status-text" id="statusText">Click "Start Listening" to begin</div>
        </div>
        <div class="controls">
            <button class="control-button" id="startButton" onclick="startListening()">Start Listening</button>
            <button class="control-button stop" id="stopButton" onclick="stopListening()" disabled>Stop Listening</button>
        </div>
        <div class="transcription" id="transcription">
            <h3>🎤 Voice Transcription</h3>
            <div class="transcription-text" id="transcriptionText">Waiting for wake word command...</div>
        </div>
        <div id="response" class="response"></div>
        <div class="manual-input">
            <h3>⌨️ Type Command Manually</h3>
            <div class="input-group">
                <input type="text" class="text-input" id="manualCommand" placeholder='MUST start with "Hey Ringly" - Try: "Hey Ringly text 6566001400 saying hello" or "Hey Ringly email john@gmail.com saying test"' />
                <button class="send-button" onclick="sendManualCommand()">Send</button>
            </div>
            <small style="opacity: 0.7; display: block; margin-top: 10px; text-align: center;">💡 Both voice and text commands require "Hey Ringly" wake word | Supports SMS & Email</small>
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
                            
                            // Check if it's just a wake word with no meaningful content
                            const justWakeWord = wakeWords.some(wake => commandLower.trim() === wake.toLowerCase());
                            
                            let waitTime = 4000; // Default 4 seconds (increased from 2)
                            
                            // If it's just a wake word OR missing essential parts, wait much longer
                            if (justWakeWord || !hasActionWord || (!hasPhoneNumber || !hasSaying)) {{
                                waitTime = 8000; // Wait 8 seconds for complete command (increased from 5)
                                console.log('Command incomplete - waiting longer for full command...');
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
                            }}, 6000); // Increased from 3 seconds to 6 seconds
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

        function sendManualCommand() {{
            const manualInput = document.getElementById('manualCommand');
            let command = manualInput.value.trim();
            
            if (!command) {{
                alert('Please enter a command');
                return;
            }}
            
            // Auto-add wake word if missing
            const lowerCommand = command.toLowerCase();
            const hasWakeWord = wakeWords.some(wakeWord => lowerCommand.startsWith(wakeWord.toLowerCase()));
            
            if (!hasWakeWord) {{
                command = 'Hey Ringly ' + command;
                console.log('Auto-added wake word. Final command:', command);
                // Update the input to show what was actually sent
                manualInput.value = command;
                setTimeout(() => {{ manualInput.value = ''; }}, 2000); // Clear after 2 seconds
            }} else {{
                manualInput.value = ''; // Clear input after sending
            }}
            
            console.log('Sending manual command:', command);
            processWakeWordCommand(command);
        }}

        // Allow Enter key to send manual command
        document.addEventListener('DOMContentLoaded', function() {{
            const manualInput = document.getElementById('manualCommand');
            if (manualInput) {{
                manualInput.addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') {{
                        sendManualCommand();
                    }}
                }});
            }}
        }});

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
        "email_configured": bool(CONFIG["email_address"] and CONFIG["email_password"]),
        "claude_configured": bool(CONFIG["claude_api_key"])
    })

if __name__ == '__main__':
    print("🚀 Starting Enhanced Wake Word SMS & Email App")
    print(f"🎙️ Primary Wake Word: '{CONFIG['wake_word_primary']}'")
    print(f"📱 Twilio: {'✅ Ready' if twilio_client.client else '❌ Not configured'}")
    print(f"📧 Email: {'✅ Ready' if CONFIG['email_address'] and CONFIG['email_password'] else '❌ Not configured'}")
    print(f"🤖 Claude: {'✅ Ready' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting on port {port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
    return bool(re.match(email_pattern, recipient.strip()))

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    
    return clean

def fix_email_addresses(text: str) -> str:
    """Fix email addresses that get split by speech recognition"""
    # Common patterns where speech recognition splits emails
    patterns = [
        r'\b(\w+)\s+(@gmail\.com)\b',
        r'\b(\w+)\s+(@yahoo\.com)\b', 
        r'\b(\w+)\s+(@hotmail\.com)\b',
        r'\b(\w+)\s+(@outlook\.com)\b',
        r'\b(\w+)\s+(@icloud\.com)\b',
        r'\b(\w+)\s+(@\w+\.com)\b',  # Generic pattern
    ]
    
    fixed_text = text
    for pattern in patterns:
        fixed_text = re.sub(pattern, r'\1\2', fixed_text, flags=re.IGNORECASE)
    
    return fixed_text

def extract_email_command(text: str) -> Dict[str, Any]:
    """Extract email command from text"""
    # Fix email addresses first
    fixed_text = fix_email_addresses(text)
    
    patterns = [
        r'send (?:an )?email to (.+?) (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) (?:with )?subject (.+?) saying (.+)',
        r'send (.+?) an email (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) saying (.+)',  # Simple pattern without subject
        r'send (?:an )?email to (.+?) saying (.+)',  # Simple pattern without subject
    ]
    
    text_lower = fixed_text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            if len(match.groups()) == 3:  # Has subject
                recipient = match.group(1).strip()
                subject = match.group(2).strip()
                message = match.group(3).strip()
            else:  # No subject
                recipient = match.group(1).strip()
                subject = "Voice Command Message"
                message = match.group(2).strip()
            
            # Clean up voice artifacts
            message = message.replace(" period", ".").replace(" comma", ",")
            subject = subject.replace(" period", ".").replace(" comma", ",")
            
            return {
                "action": "send_email",
                "recipient": recipient,
                "subject": subject,
                "message": message
            }
    
    return None

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

def handle_send_email(data):
    """Handle email sending"""
    recipient = data.get("recipient", "")
    subject = data.get("subject", "Voice Command Message")
    message = data.get("message", "")
    
    if is_email_address(recipient):
        result = email_client.send_email(recipient, subject, message)
        
        if result.get("success"):
            return f"✅ Email sent to {recipient}!\n\nSubject: {subject}\nMessage: {message}"
        else:
            return f"❌ Failed to send email to {recipient}: {result.get('error')}"
    else:
        return f"❌ Invalid email address: {recipient}"

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
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #2d2d2d url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: white; }}
        .container {{ background: rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2); backdrop-filter: blur(15px); max-width: 700px; width: 100%; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; font-weight: 700; }}
        .header img {{ max-height: 300px; margin-bottom: 20px; max-width: 95%; }}
        .header p {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; }}

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
        .control-button:disabled {{ background: #6c757d; cursor: not-allowed; transform: none; box-shadow: none; }}
        .manual-input {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; }}
        .manual-input h3 {{ margin-bottom: 15px; text-align: center; }}
        .input-group {{ display: flex; gap: 10px; align-items: center; }}
        .text-input {{ flex: 1; padding: 12px 15px; border: 2px solid rgba(255, 255, 255, 0.2); border-radius: 25px; background: rgba(255, 255, 255, 0.1); color: white; font-size: 1em; outline: none; transition: all 0.3s ease; }}
        .text-input:focus {{ border-color: #007bff; background: rgba(255, 255, 255, 0.15); }}
        .text-input::placeholder {{ color: rgba(255, 255, 255, 0.6); }}
        .send-button {{ background: linear-gradient(45deg, #28a745, #20c997); color: white; border: none; padding: 12px 25px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; transition: all 0.3s ease; }}
        .send-button:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(40, 167, 69, 0.4); }}
        .transcription {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; border: 2px solid transparent; transition: all 0.3s ease; }}
        .transcription.active {{ border-color: #28a745; background: rgba(40, 167, 69, 0.1); }}
        .transcription h3 {{ font-size: 1.1em; margin-bottom: 10px; opacity: 0.8; }}
        .transcription-text {{ font-size: 1.2em; font-weight: 500; font-family: 'Courier New', monospace; }}
        .response {{ background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; text-align: left; white-space: pre-wrap; display: none; }}
        .response.success {{ background: rgba(40, 167, 69, 0.2); border: 2px solid #28a745; }}
        .response.error {{ background: rgba(220, 53, 69, 0.2); border: 2px solid #dc3545; }}

        .browser-support {{ font-size: 0.9em; opacity: 0.8; margin-top: 20px; }}
        .browser-support.unsupported {{ color: #dc3545; font-weight: bold; opacity: 1; }}
        .privacy-note {{ background: rgba(255, 193, 7, 0.2); border: 1px solid #ffc107; border-radius: 10px; padding: 15px; margin-top: 20px; font-size: 0.9em; }}
        @media (max-width: 600px) {{ .container {{ padding: 20px; margin: 10px; }} .header img {{ max-height: 220px; }} .voice-indicator {{ width: 80px; height: 80px; font-size: 32px; }} .control-button {{ padding: 10px 20px; font-size: 0.9em; margin: 5px; }} .input-group {{ flex-direction: column; gap: 15px; }} .text-input {{ width: 100%; margin-bottom: 10px; }} .send-button {{ width: 100%; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp" alt="Wake Word SMS Logo" />
            <p>Enhanced voice recognition - adapts to your pronunciation!</p>
        </div>

        <div class="listening-status">
            <div class="voice-indicator idle" id="voiceIndicator">🎤</div>
            <div class="status-text" id="statusText">Click "Start Listening" to begin</div>
        </div>
        <div class="controls">
            <button class="control-button" id="startButton" onclick="startListening()">Start Listening</button>
            <button class="control-button stop" id="stopButton" onclick="stopListening()" disabled>Stop Listening</button>
        </div>
        <div class="transcription" id="transcription">
            <h3>🎤 Voice Transcription</h3>
            <div class="transcription-text" id="transcriptionText">Waiting for wake word command...</div>
        </div>
        <div id="response" class="response"></div>
        <div class="manual-input">
            <h3>⌨️ Type Command Manually</h3>
            <div class="input-group">
                <input type="text" class="text-input" id="manualCommand" placeholder='MUST start with "Hey Ringly" - Try: "Hey Ringly text 6566001400 saying hello"' />
                <button class="send-button" onclick="sendManualCommand()">Send</button>
            </div>
            <small style="opacity: 0.7; display: block; margin-top: 10px; text-align: center;">💡 Both voice and text commands require "Hey Ringly" wake word</small>
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
                            
                            // Check if it's just a wake word with no meaningful content
                            const justWakeWord = wakeWords.some(wake => commandLower.trim() === wake.toLowerCase());
                            
                            let waitTime = 4000; // Default 4 seconds (increased from 2)
                            
                            // If it's just a wake word OR missing essential parts, wait much longer
                            if (justWakeWord || !hasActionWord || (!hasPhoneNumber || !hasSaying)) {{
                                waitTime = 8000; // Wait 8 seconds for complete command (increased from 5)
                                console.log('Command incomplete - waiting longer for full command...');
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
                            }}, 6000); // Increased from 3 seconds to 6 seconds
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

        function sendManualCommand() {{
            const manualInput = document.getElementById('manualCommand');
            let command = manualInput.value.trim();
            
            if (!command) {{
                alert('Please enter a command');
                return;
            }}
            
            // Auto-add wake word if missing
            const lowerCommand = command.toLowerCase();
            const hasWakeWord = wakeWords.some(wakeWord => lowerCommand.startsWith(wakeWord.toLowerCase()));
            
            if (!hasWakeWord) {{
                command = 'Hey Ringly ' + command;
                console.log('Auto-added wake word. Final command:', command);
                // Update the input to show what was actually sent
                manualInput.value = command;
                setTimeout(() => {{ manualInput.value = ''; }}, 2000); // Clear after 2 seconds
            }} else {{
                manualInput.value = ''; // Clear input after sending
            }}
            
            console.log('Sending manual command:', command);
            processWakeWordCommand(command);
        }}

        // Allow Enter key to send manual command
        document.addEventListener('DOMContentLoaded', function() {{
            const manualInput = document.getElementById('manualCommand');
            if (manualInput) {{
                manualInput.addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') {{
                        sendManualCommand();
                    }}
                }});
            }}
        }});

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
