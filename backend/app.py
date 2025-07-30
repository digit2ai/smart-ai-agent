# Enhanced Flask CMP Server with Wake Word Activation
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import re
import concurrent.futures
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from enum import Enum

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
    "provider": "claude",
    "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
    "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
    "smtp_server": os.getenv("SMTP_SERVER", "mail.networksolutions.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "email_address": os.getenv("EMAIL_ADDRESS", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "email_name": os.getenv("EMAIL_NAME", "Smart AI Agent"),
    "email_provider": os.getenv("EMAIL_PROVIDER", "networksolutions").lower(),
    # Wake word configuration
    "wake_words": ["hey ringly", "ringly", "hey ring", "ring"],
    "wake_word_primary": "hey ringly",
    "wake_word_enabled": True,
    "wake_word_case_sensitive": False,
}

print(f"🎙️ Wake words configured: {CONFIG['wake_words']}")
print(f"🔑 Primary wake word: '{CONFIG['wake_word_primary']}'")

# Service Reminder Enums and Data Classes
class ServiceType(Enum):
    OIL_CHANGE = "oil_change"
    TIRE_ROTATION = "tire_rotation"
    BRAKE_INSPECTION = "brake_inspection"
    AIR_FILTER = "air_filter"
    TRANSMISSION = "transmission"
    COOLANT = "coolant"
    TUNE_UP = "tune_up"
    INSPECTION = "inspection"
    REGISTRATION = "registration"
    INSURANCE = "insurance"
    CUSTOM = "custom"

class ReminderStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

@dataclass
class ServiceReminder:
    id: Optional[int] = None
    service_type: str = ""
    vehicle_info: str = ""
    description: str = ""
    due_date: str = ""
    due_mileage: Optional[int] = None
    current_mileage: Optional[int] = None
    contact_method: str = "sms"
    contact_info: str = ""
    notification_days: int = 7
    status: str = ReminderStatus.ACTIVE.value
    created_at: str = ""
    last_notified: Optional[str] = None
    notes: str = ""

# Wake Word Processor Class
class WakeWordProcessor:
    def __init__(self):
        self.wake_words = CONFIG["wake_words"]
        self.primary_wake_word = CONFIG["wake_word_primary"]
        self.enabled = CONFIG["wake_word_enabled"]
        self.case_sensitive = CONFIG["wake_word_case_sensitive"]
        print(f"🎙️ WakeWordProcessor initialized with {len(self.wake_words)} wake words")
    
    def detect_wake_word(self, text: str) -> Dict[str, Any]:
        original_text = text.strip()
        print(f"[WAKE WORD] Checking: '{original_text[:50]}{'...' if len(original_text) > 50 else ''}'")
        
        if not self.enabled:
            return {
                "has_wake_word": True,
                "wake_word_detected": "disabled",
                "command_text": original_text,
                "original_text": original_text,
                "confidence": 1.0
            }
        
        search_text = original_text if self.case_sensitive else original_text.lower()
        
        for wake_word in self.wake_words:
            compare_word = wake_word if self.case_sensitive else wake_word.lower()
            
            if search_text.startswith(compare_word):
                next_char_index = len(compare_word)
                if (next_char_index >= len(search_text) or 
                    search_text[next_char_index] in [' ', ',', ':', ';', '!', '?', '.']):
                    
                    command_text = original_text[len(wake_word):].strip()
                    command_text = re.sub(r'^[,:;!?.]\s*', '', command_text)
                    confidence = 0.8
                    
                    print(f"[WAKE WORD] ✅ Detected: '{wake_word}' | Command: '{command_text[:30]}...'")
                    
                    return {
                        "has_wake_word": True,
                        "wake_word_detected": wake_word,
                        "command_text": command_text,
                        "original_text": original_text,
                        "confidence": confidence
                    }
        
        print(f"[WAKE WORD] ❌ No wake word detected")
        return {
            "has_wake_word": False,
            "wake_word_detected": None,
            "command_text": original_text,
            "original_text": original_text,
            "confidence": 0.0
        }
    
    def process_wake_word_command(self, text: str) -> Dict[str, Any]:
        print(f"[WAKE WORD] Processing command: '{text[:100]}...'")
        
        wake_result = self.detect_wake_word(text)
        
        if not wake_result["has_wake_word"]:
            print(f"[WAKE WORD] Command rejected - no wake word detected")
            return {
                "success": False,
                "error": f"Please start your command with '{self.primary_wake_word}'. For example: '{self.primary_wake_word}: text John saying hello'",
                "wake_word_required": True,
                "suggested_wake_words": self.wake_words
            }
        
        command_text = wake_result["command_text"]
        
        if not command_text.strip():
            return {
                "success": False,
                "error": f"Please provide a command after '{wake_result['wake_word_detected']}'",
                "wake_word_detected": wake_result["wake_word_detected"]
            }
        
        # Try to extract SMS command
        sms_result = extract_sms_command(command_text)
        if sms_result:
            print("[WAKE WORD] ✅ SMS command extracted")
            sms_result["wake_word_info"] = wake_result
            return sms_result
        
        # Try to extract email command
        email_result = extract_email_command(command_text)
        if email_result:
            print("[WAKE WORD] ✅ Email command extracted")
            email_result["wake_word_info"] = wake_result
            return email_result
        
        # Fall back to Claude AI
        print("[WAKE WORD] 🤖 Falling back to Claude AI")
        try:
            claude_result = call_claude(command_text)
            if claude_result and "error" not in claude_result:
                claude_result["wake_word_info"] = wake_result
                return claude_result
        except Exception as e:
            print(f"[WAKE WORD] Claude AI failed: {e}")
        
        return {
            "success": False,
            "error": f"I didn't understand the command: '{command_text}'. Try: '{self.primary_wake_word}: text John saying hello'",
            "wake_word_detected": wake_result["wake_word_detected"],
            "unrecognized_command": command_text
        }

# Initialize wake word processor
wake_word_processor = WakeWordProcessor()

# Twilio Client
class TwilioClient:
    def __init__(self):
        self.account_sid = CONFIG["twilio_account_sid"]
        self.auth_token = CONFIG["twilio_auth_token"]
        self.from_number = CONFIG["twilio_phone_number"]
        self.client = None
        
        if TWILIO_AVAILABLE and self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ Twilio client initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize Twilio client: {e}")
        else:
            print("⚠️ Twilio not configured")
    
    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Twilio client not initialized"}
        
        if not self.from_number:
            return {"error": "Twilio phone number not configured"}
        
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

# Email Client
class EmailClient:
    def __init__(self):
        self.smtp_server = CONFIG["smtp_server"]
        self.smtp_port = CONFIG["smtp_port"]
        self.email_address = CONFIG["email_address"]
        self.email_password = CONFIG["email_password"]
        self.email_name = CONFIG["email_name"]
        
        if self.email_address and self.email_password:
            print(f"✅ Email client configured successfully")
        else:
            print("⚠️ Email not configured")
    
    def send_email(self, to: str, subject: str, message: str) -> Dict[str, Any]:
        if not self.email_address or not self.email_password:
            return {"error": "Email client not configured"}
        
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.email_name} <{self.email_address}>"
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                text = msg.as_string()
                server.sendmail(self.email_address, to, text)
            
            return {
                "success": True,
                "to": to,
                "from": self.email_address,
                "subject": subject,
                "body": message,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": f"Failed to send email: {str(e)}"}

# Global client instances
twilio_client = TwilioClient()
email_client = EmailClient()

# Claude API functions
def call_claude(prompt):
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        instruction_prompt = """
You are an intelligent assistant. Respond ONLY with valid JSON using one of the supported actions:
- send_message (for SMS)
- send_email (for email)
- create_task
- create_appointment
- log_conversation

Structure:
{
  "action": "send_message" | "send_email" | "create_task" | "create_appointment" | "log_conversation",
  "recipient": "phone number or email",
  "message": "message content",
  "subject": "email subject (for emails)",
  "title": "task/appointment title",
  "due_date": "YYYY-MM-DD"
}
"""
        
        full_prompt = f"{instruction_prompt}\n\nUser: {prompt}"

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
            return {"error": "Claude response missing content"}
    except Exception as e:
        return {"error": str(e)}

def enhance_message_with_claude(message: str) -> str:
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        prompt = f"Make this message professional and clear while preserving the meaning: {message}"

        body = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 500,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}]
        }

        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, data=json.dumps(body))
        response_json = res.json()
        
        if "content" in response_json:
            return response_json["content"][0]["text"].strip()
        else:
            return message
    except Exception as e:
        print(f"Error enhancing message: {e}")
        return message

# Utility functions
def is_phone_number(recipient: str) -> bool:
    clean = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if clean.startswith("+") and clean[1:].isdigit():
        return True
    if clean.isdigit() and len(clean) >= 10:
        return True
    return False

def is_email_address(recipient: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, recipient.strip()))

def format_phone_number(phone: str) -> str:
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    return clean

# Command extraction functions
def extract_sms_command(text: str) -> Dict[str, str]:
    patterns = [
        r'send (?:a )?(?:text|message|sms) to (.+?) saying (.+)',
        r'text (.+?) saying (.+)',
        r'message (.+?) saying (.+)',
        r'text (.+?) (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            message = match.group(2).strip()
            
            return {
                "action": "send_message",
                "recipient": recipient,
                "message": message,
                "original_message": message
            }
    
    return None

def extract_email_command(text: str) -> Dict[str, Any]:
    patterns = [
        r'send (?:an )?email to (.+?) (?:with subject (.+?) )?saying (.+)',
        r'email (.+?) (?:with subject (.+?) )?saying (.+)',
        r'email (.+?) that (.+)',
        r'send (?:an )?email to (.+?) (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if len(groups) == 3 and groups[1]:
                recipient = groups[0].strip()
                subject = groups[1].strip()
                message = groups[2].strip()
            elif len(groups) == 3:
                recipient = groups[0].strip()
                subject = None
                message = groups[2].strip()
            else:
                recipient = groups[0].strip()
                subject = None
                message = groups[1].strip()
            
            return {
                "action": "send_email",
                "recipient": recipient,
                "subject": subject or "Message from Smart AI Agent",
                "message": message,
                "original_message": message
            }
    
    return None

# Action handlers
def handle_send_message(data):
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    
    if is_phone_number(recipient):
        formatted_phone = format_phone_number(recipient)
        enhanced_message = enhance_message_with_claude(message)
        result = twilio_client.send_sms(formatted_phone, enhanced_message)
        
        if "error" in result:
            return f"Failed to send SMS to {recipient}: {result['error']}"
        else:
            return f"✅ SMS sent to {recipient}!\n\nOriginal: {message}\nEnhanced: {enhanced_message}\n\nMessage ID: {result.get('message_sid', 'N/A')}"
    else:
        return f"Invalid phone number: {recipient}"

def handle_send_email(data):
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    subject = data.get("subject", "Message from Smart AI Agent")
    
    if is_email_address(recipient):
        enhanced_message = enhance_message_with_claude(message)
        result = email_client.send_email(recipient, subject, enhanced_message)
        
        if "error" in result:
            return f"Failed to send email to {recipient}: {result['error']}"
        else:
            return f"✅ Email sent to {recipient}!\n\nSubject: {subject}\nOriginal: {message}\nEnhanced: {enhanced_message}"
    else:
        return f"Invalid email address: {recipient}"

def handle_create_task(data):
    title = data.get("title", "Untitled Task")
    due_date = data.get("due_date", "No due date")
    return f"Task '{title}' scheduled for {due_date}."

def handle_create_appointment(data):
    title = data.get("title", "Untitled Appointment")
    due_date = data.get("due_date", "No due date")
    return f"Appointment '{title}' booked for {due_date}."

def handle_log_conversation(data):
    return "Conversation log saved."

def dispatch_action(parsed):
    action = parsed.get("action")
    if action == "send_message":
        return handle_send_message(parsed)
    elif action == "send_email":
        return handle_send_email(parsed)
    elif action == "create_task":
        return handle_create_task(parsed)
    elif action == "create_appointment":
        return handle_create_appointment(parsed)
    elif action == "log_conversation":
        return handle_log_conversation(parsed)
    else:
        return f"Unknown action: {action}"

# HTML Template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart AI Agent with Wake Word</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      background: linear-gradient(to bottom, #000b1f 0%, #f0f8ff 100%);
      margin: 0;
      padding: 2rem;
      min-height: 100vh;
      color: white;
    }
    .container {
      max-width: 600px;
      margin: 0 auto;
    }
    h1 {
      text-align: center;
      margin-bottom: 2rem;
    }
    .wake-word-info {
      background: rgba(40, 167, 69, 0.2);
      padding: 1rem;
      border-radius: 8px;
      margin-bottom: 2rem;
      text-align: center;
    }
    .input-group {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 2rem;
    }
    input {
      flex: 1;
      padding: 1rem;
      font-size: 16px;
      border: 2px solid #007bff;
      border-radius: 8px;
      background: white;
      color: black;
    }
    button {
      padding: 1rem 2rem;
      font-size: 16px;
      background: #007bff;
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
    }
    button:hover {
      background: #0056b3;
    }
    .response {
      background: rgba(255,255,255,0.95);
      color: black;
      padding: 1.5rem;
      border-radius: 8px;
      min-height: 200px;
      white-space: pre-wrap;
      font-family: monospace;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🎙️ Smart AI Agent with Wake Word</h1>
    <div class="wake-word-info">
      <strong>Wake Word Active: "hey ringly"</strong><br>
      Start all commands with "hey ringly:"
    </div>
    
    <div class="input-group">
      <input type="text" id="command" placeholder="hey ringly: text Ron saying MVP is ready" />
      <button onclick="sendCommand()">Send</button>
    </div>

    <div class="response" id="response">
🎙️ Wake Word System Active! Start commands with "hey ringly:"

Examples:
• "hey ringly: text 8136414177 saying hello"
• "hey ringly: email john@email.com saying meeting at 3pm"
• "hey ringly: text Ron saying MVP is ready"
    </div>
  </div>

  <script>
    function sendCommand() {
      const input = document.getElementById('command');
      const output = document.getElementById('response');
      const userText = input.value.trim();

      if (!userText) {
        output.textContent = 'Please enter a command starting with "hey ringly:"';
        return;
      }

      output.textContent = 'Processing wake word command...';

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        let responseText = data.response || "Done!";
        
        if (data.claude_output && data.claude_output.wake_word_info) {
          const wakeInfo = data.claude_output.wake_word_info;
          responseText += `\\n\\n🎙️ Wake Word: "${wakeInfo.wake_word_detected}"`;
        }
        
        output.textContent = responseText;
        input.value = "";
      })
      .catch(err => {
        output.textContent = "Error: " + err.message;
      });
    }

    document.getElementById('command').addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        sendCommand();
      }
    });
  </script>
</body>
</html>"""

# Routes
@app.route("/")
def root():
    return HTML_TEMPLATE

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        
        print(f"[EXECUTE] Received: '{prompt}'")
        
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
        
        # Fallback to Claude
        result = call_claude(wake_result.get("command_text", prompt))
        
        if "error" in result:
            return jsonify({"response": result["error"]}), 500

        dispatch_result = dispatch_action(result)
        return jsonify({
            "response": dispatch_result,
            "claude_output": result
        })

    except Exception as e:
        print(f"[EXECUTE] Error: {e}")
        return jsonify({"response": f"Error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "wake_word_enabled": CONFIG["wake_word_enabled"],
        "wake_word_primary": CONFIG["wake_word_primary"],
        "twilio_configured": bool(twilio_client.client),
        "email_configured": bool(CONFIG["email_address"]),
        "claude_configured": bool(CONFIG["claude_api_key"])
    })

if __name__ == '__main__':
    print("🚀 Starting Smart AI Agent with Wake Word")
    print(f"🎙️ Primary wake word: '{CONFIG['wake_word_primary']}'")
    print(f"📱 Twilio: {'✅' if twilio_client.client else '❌'}")
    print(f"📧 Email: {'✅' if CONFIG['email_address'] else '❌'}")
    print(f"🤖 Claude: {'✅' if CONFIG['claude_api_key'] else '❌'}")
    print(f"💬 Try: '{CONFIG['wake_word_primary']}: text Ron saying MVP is ready!'")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
