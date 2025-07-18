# Enhanced Flask CMP Server with Professional Voice SMS and Email Processing
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

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
    # Email configuration
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "email_username": os.getenv("EMAIL_USERNAME", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),  # Use app password for Gmail
    "sender_name": os.getenv("SENDER_NAME", "AI Assistant"),
}

INSTRUCTION_PROMPT = """
You are an intelligent assistant. Respond ONLY with valid JSON using one of the supported actions.

Supported actions:
- create_task
- create_appointment
- send_message (supports SMS via Twilio)
- send_email (supports professional email sending)
- log_conversation
- enhance_message (for making messages professional)
- enhance_email (for making emails professional with subject and body)

Each response must use this structure:
{
  "action": "create_task" | "create_appointment" | "send_message" | "send_email" | "log_conversation" | "enhance_message" | "enhance_email",
  "title": "...",               // for tasks or appointments
  "due_date": "YYYY-MM-DDTHH:MM:SS", // or null
  "recipient": "Name or phone number or email",    // for send_message/send_email
  "message": "Body of the message",  // for send_message or log
  "email_to": "email@example.com",   // for send_email
  "email_subject": "Email subject",  // for send_email
  "email_body": "Email content",     // for send_email
  "original_message": "...",     // for enhance_message/enhance_email action
  "enhanced_message": "...",     // for enhance_message action
  "enhanced_subject": "...",     // for enhance_email action
  "enhanced_body": "...",        // for enhance_email action
  "notes": "Optional details or transcript" // for CRM logs
}

For send_message action:
- If recipient looks like a phone number (starts with + or contains only digits), it will be sent as SMS
- Otherwise it will be logged as a regular message
- Phone numbers should be in E.164 format (e.g., +1234567890)

For send_email action:
- Recipient should be a valid email address
- Include both subject and body
- Email will be professionally formatted

For enhance_message action:
- Fix grammar, spelling, and punctuation
- Make the tone professional and clear
- Preserve the original meaning and intent
- Keep it concise but polished

For enhance_email action:
- Create professional subject line
- Fix grammar, spelling, and punctuation in body
- Make the tone professional but friendly
- Preserve the original meaning and intent
- Format appropriately for email

Only include fields relevant to the action.
Do not add extra commentary.
"""

MESSAGE_ENHANCEMENT_PROMPT = """
You are a professional communication assistant. Your task is to enhance messages to make them clear, professional, and grammatically correct while preserving the original meaning and intent.

Please take the following message and improve it:
- Fix any grammar, spelling, or punctuation errors
- Make the tone professional but friendly
- Ensure clarity and conciseness
- Preserve the original meaning completely
- Keep it appropriate for SMS/text messaging

Original message: "{original_message}"

Respond with ONLY the enhanced message, nothing else.
"""

EMAIL_ENHANCEMENT_PROMPT = """
You are a professional email communication assistant. Your task is to enhance email content to make it clear, professional, and well-formatted while preserving the original meaning and intent.

Please take the following email content and improve it:
- Create a clear, professional subject line
- Fix any grammar, spelling, or punctuation errors
- Make the tone professional but friendly
- Ensure proper email structure and formatting
- Preserve the original meaning completely
- Make it appropriate for professional email communication

Original email content: "{original_message}"

Respond with ONLY a JSON object in this format:
{
  "subject": "Professional subject line",
  "body": "Enhanced email body with proper formatting"
}
"""

class EmailClient:
    """SMTP Email client for sending professional emails"""
    
    def __init__(self):
        self.smtp_server = CONFIG["smtp_server"]
        self.smtp_port = CONFIG["smtp_port"]
        self.username = CONFIG["email_username"]
        self.password = CONFIG["email_password"]
        self.sender_name = CONFIG["sender_name"]
        
        # Test connection on initialization
        self.is_configured = bool(self.username and self.password)
        if self.is_configured:
            try:
                self.test_connection()
                print("✅ Email client initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize email client: {e}")
                self.is_configured = False
        else:
            print("⚠️ Email not configured - missing credentials")
    
    def test_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.quit()
            return True
        except Exception as e:
            print(f"Email connection test failed: {e}")
            return False
    
    def send_email(self, to: str, subject: str, body: str, html_body: str = None) -> Dict[str, Any]:
        """Send email via SMTP"""
        if not self.is_configured:
            return {"error": "Email client not configured"}
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.sender_name} <{self.username}>"
            msg['To'] = to
            msg['Subject'] = subject
            
            # Add plain text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            text = msg.as_string()
            server.sendmail(self.username, to, text)
            server.quit()
            
            return {
                "success": True,
                "to": to,
                "subject": subject,
                "from": f"{self.sender_name} <{self.username}>",
                "body": body,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Failed to send email: {str(e)}"}
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get email configuration information"""
        return {
            "configured": self.is_configured,
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "username": self.username[:5] + "..." if self.username else "not set",
            "sender_name": self.sender_name
        }

class TwilioClient:
    """Direct Twilio REST API client"""
    
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
            print("⚠️ Twilio not configured or library missing")
    
    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio REST API"""
        if not self.client:
            return {"error": "Twilio client not initialized"}
        
        if not self.from_number:
            return {"error": "Twilio phone number not configured"}
        
        try:
            # Send the message
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
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get Twilio account information"""
        if not self.client:
            return {"error": "Twilio client not initialized"}
        
        try:
            account = self.client.api.accounts(self.account_sid).fetch()
            return {
                "account_sid": account.sid,
                "friendly_name": account.friendly_name,
                "status": account.status,
                "type": account.type
            }
        except Exception as e:
            return {"error": f"Failed to get account info: {str(e)}"}

# Global client instances
twilio_client = TwilioClient()
email_client = EmailClient()

def call_claude(prompt, use_enhancement_prompt=False, use_email_prompt=False, original_message=""):
    """Call Claude API with different prompts based on use case"""
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        if use_email_prompt:
            full_prompt = EMAIL_ENHANCEMENT_PROMPT.format(original_message=original_message)
        elif use_enhancement_prompt:
            full_prompt = MESSAGE_ENHANCEMENT_PROMPT.format(original_message=original_message)
        else:
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
            
            if use_email_prompt:
                # For email enhancement, parse as JSON
                try:
                    parsed = json.loads(raw_text)
                    return parsed
                except:
                    return {"error": "Failed to parse email enhancement response"}
            elif use_enhancement_prompt:
                # For message enhancement, return the raw text directly
                return {"enhanced_message": raw_text.strip()}
            else:
                # For regular commands, parse as JSON
                parsed = json.loads(raw_text)
                return parsed
        else:
            return {"error": "Claude response missing content."}
    except Exception as e:
        return {"error": str(e)}

def enhance_message_with_claude(message: str) -> str:
    """Enhance a message using Claude AI"""
    try:
        result = call_claude("", use_enhancement_prompt=True, original_message=message)
        if "enhanced_message" in result:
            return result["enhanced_message"]
        else:
            print(f"Enhancement failed: {result}")
            return message  # Return original if enhancement fails
    except Exception as e:
        print(f"Error enhancing message: {e}")
        return message  # Return original if enhancement fails

def enhance_email_with_claude(message: str) -> Dict[str, str]:
    """Enhance an email using Claude AI"""
    try:
        result = call_claude("", use_email_prompt=True, original_message=message)
        if "subject" in result and "body" in result:
            return {"subject": result["subject"], "body": result["body"]}
        else:
            print(f"Email enhancement failed: {result}")
            return {"subject": "Message from AI Assistant", "body": message}
    except Exception as e:
        print(f"Error enhancing email: {e}")
        return {"subject": "Message from AI Assistant", "body": message}

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

def is_email_address(recipient: str) -> bool:
    """Check if recipient looks like an email address"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, recipient.strip()) is not None

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

def extract_communication_command(text: str) -> Dict[str, str]:
    """Extract SMS or email command from voice input using pattern matching"""
    # SMS patterns
    sms_patterns = [
        r'send (?:a )?(?:text|message|sms) to (.+?) saying (.+)',
        r'text (.+?) saying (.+)',
        r'message (.+?) saying (.+)',
        r'send (.+?) the message (.+)',
        r'tell (.+?) that (.+)',
        r'text (.+?) (.+)',  # Simple pattern: "text John hello there"
    ]
    
    # Email patterns
    email_patterns = [
        r'send (?:an )?email to (.+?) saying (.+)',
        r'email (.+?) saying (.+)',
        r'send (.+?) an email saying (.+)',
        r'email (.+?) that (.+)',
        r'send (?:an )?email to (.+?) with subject (.+?) saying (.+)',
        r'email (.+?) about (.+?) saying (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    # Try email patterns first
    for pattern in email_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2:  # Standard email pattern
                recipient = groups[0].strip()
                message = groups[1].strip()
                subject = None
            elif len(groups) == 3:  # Email with subject
                recipient = groups[0].strip()
                subject = groups[1].strip()
                message = groups[2].strip()
            
            # Clean up common voice recognition artifacts
            message = message.replace(" period", ".").replace(" comma", ",")
            message = message.replace(" question mark", "?").replace(" exclamation mark", "!")
            
            result = {
                "action": "send_email",
                "recipient": recipient,
                "message": message,
                "original_message": message
            }
            
            if subject:
                result["subject"] = subject
            
            return result
    
    # Try SMS patterns
    for pattern in sms_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            message = match.group(2).strip()
            
            # Clean up common voice recognition artifacts
            message = message.replace(" period", ".").replace(" comma", ",")
            message = message.replace(" question mark", "?").replace(" exclamation mark", "!")
            
            return {
                "action": "send_message",
                "recipient": recipient,
                "message": message,
                "original_message": message
            }
    
    return None

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
    original_message = data.get("original_message", message)
    
    print(f"[CMP] Sending message to {recipient}")
    
    # Check if recipient is a phone number
    if is_phone_number(recipient):
        # Format phone number
        formatted_phone = format_phone_number(recipient)
        print(f"[CMP] Detected phone number, processing SMS to {formatted_phone}")
        
        # Enhance the message using Claude AI
        print(f"[CMP] Original message: {original_message}")
        enhanced_message = enhance_message_with_claude(original_message)
        print(f"[CMP] Enhanced message: {enhanced_message}")
        
        # Send the enhanced message
        result = twilio_client.send_sms(formatted_phone, enhanced_message)
        
        if "error" in result:
            return f"Failed to send SMS to {recipient}: {result['error']}"
        else:
            return f"✅ Professional SMS sent to {recipient}!\n\nOriginal: {original_message}\nEnhanced: {enhanced_message}\n\nMessage ID: {result.get('message_sid', 'N/A')}"
    else:
        # Regular message (not SMS)
        enhanced_message = enhance_message_with_claude(message)
        return f"Enhanced message for {recipient}:\nOriginal: {message}\nEnhanced: {enhanced_message}"

def handle_send_email(data):
    recipient = data.get("recipient", "")
    email_to = data.get("email_to", recipient)
    message = data.get("message", "")
    original_message = data.get("original_message", message)
    provided_subject = data.get("email_subject") or data.get("subject")
    
    print(f"[CMP] Sending email to {email_to}")
    
    # Validate email address
    if not is_email_address(email_to):
        return f"❌ Invalid email address: {email_to}"
    
    # Enhance the email using Claude AI
    print(f"[CMP] Original email content: {original_message}")
    enhanced_email = enhance_email_with_claude(original_message)
    
    # Use provided subject or enhanced subject
    final_subject = provided_subject or enhanced_email["subject"]
    final_body = enhanced_email["body"]
    
    print(f"[CMP] Enhanced email - Subject: {final_subject}")
    print(f"[CMP] Enhanced email - Body: {final_body}")
    
    # Create HTML version of the email
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            {final_body.replace('\n', '<br>')}
            <br><br>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888;">
                Sent via AI Assistant
            </p>
        </body>
    </html>
    """
    
    # Send the enhanced email
    result = email_client.send_email(email_to, final_subject, final_body, html_body)
    
    if "error" in result:
        return f"Failed to send email to {email_to}: {result['error']}"
    else:
        return f"✅ Professional email sent to {email_to}!\n\nSubject: {final_subject}\n\nOriginal: {original_message}\nEnhanced: {final_body}\n\nSent at: {result.get('timestamp', 'N/A')}"

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
    elif action == "send_email":
        return handle_send_email(parsed)
    elif action == "log_conversation":
        return handle_log_conversation(parsed)
    else:
        return f"Unknown action: {action}"

# ----- PWA Manifest -----
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Smart AI Agent - Voice SMS & Email",
        "short_name": "AI Agent",
        "description": "AI-powered assistant with professional voice SMS and email capabilities",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f8f9fa",
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
const CACHE_NAME = 'ai-agent-v2';
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

# ----- Enhanced Mobile HTML Template -----
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>Smart AI Agent - Voice SMS & Email</title>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#007bff">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="AI Agent">
  <link rel="apple-touch-icon" href="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTkyIiBoZWlnaHQ9IjE5MiIgdmlld0JveD0iMCAwIDE5MiAxOTIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxOTIiIGhlaWdodD0iMTkyIiByeD0iMjQiIGZpbGw9IiMwMDdiZmYiLz4KPHN2ZyB4PSI0OCIgeT0iNDgiIHdpZHRoPSI5NiIgaGVpZ2h0PSI5NiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+CjxwYXRoIGQ9Im0xMiAzLTEuOTEyIDUuODEzYTIgMiAwIDAgMS0xLjI5NSAxLjI5NUwzIDEyIDguODEzIDEzLjkxMmEyIDIgMCAwIDEgMS4yOTUgMS4yOTVMMTIgMjEgMTMuOTEyIDE1LjE4N2EyIDIgMCAwIDEgMS4yOTUtMS4yOTVMMjEgMTIgMTUuMTg3IDEwLjA4OGEyIDIgMCAwIDEtMS4yOTUtMS4yOTVMMTIgMyIvPgo8L3N2Zz4KPC9zdmc+">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
    }
    
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      margin: 0;
      padding: 1rem;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      color: #212529;
      padding-top: env(safe-area-inset-top);
      padding-bottom: env(safe-area-inset-bottom);
    }

    .container {
      width: 100%;
      max-width: 600px;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
      margin-top: 2rem;
    }

    h1 {
      font-size: 2.2rem;
      margin: 0;
      text-align: center;
      font-weight: 700;
      color: white;
      letter-spacing: -0.025em;
      text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .subtitle {
      font-size: 1rem;
      color: rgba(255,255,255,0.9);
      text-align: center;
      margin-bottom: 2rem;
      font-weight: 400;
      line-height: 1.5;
    }

    .feature-badge {
      background: rgba(255,255,255,0.2);
      color: white;
      padding: 0.5rem 1rem;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 500;
      display: inline-block;
      margin: 0 auto 1rem;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.3);
    }

    .feature-badges {
      display: flex;
      gap: 0.5rem;
      justify-content: center;
      flex-wrap: wrap;
      margin-bottom: 1.5rem;
    }

    .input-container {
      background: rgba(255,255,255,0.95);
      border-radius: 16px;
      padding: 1.5rem;
      border: 1px solid rgba(255,255,255,0.2);
      box-shadow: 0 8px 32px rgba(0,0,0,0.1);
      backdrop-filter: blur(10px);
    }

    .input-group {
      display: flex;
      gap: 0.75rem;
      align-items: center;
    }

    input {
      flex: 1;
      padding: 16px 20px;
      font-size: 16px;
      border: 2px solid #e9ecef;
      border-radius: 12px;
      background: white;
      outline: none;
      color: #212529;
      font-family: 'Inter', sans-serif;
      transition: all 0.3s ease;
    }

    input:focus {
      border-color: #007bff;
      box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
      transform: translateY(-1px);
    }

    input::placeholder {
      color: #6c757d;
      font-weight: 400;
    }

    button {
      padding: 16px 28px;
      font-size: 16px;
      font-weight: 600;
      border: none;
      border-radius: 12px;
      background: linear-gradient(45deg, #007bff, #0056b3);
      color: white;
      cursor: pointer;
      min-width: 90px;
      transition: all 0.3s ease;
      font-family: 'Inter', sans-serif;
      box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
    }

    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0, 123, 255, 0.4);
    }

    button:active {
      transform: translateY(0);
    }

    .response-container {
      background: rgba(255,255,255,0.95);
      border-radius: 16px;
      padding: 1.5rem;
      border: 1px solid rgba(255,255,255,0.2);
      min-height: 300px;
      flex: 1;
      box-shadow: 0 8px 32px rgba(0,0,0,0.1);
      backdrop-filter: blur(10px);
    }

    .response-text {
      font-size: 14px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-wrap: break-word;
      color: #495057;
      font-family: 'Inter', sans-serif;
      font-weight: 400;
    }

    .voice-controls {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 1rem;
      margin-top: 1rem;
    }

    .mic-button {
      width: 72px;
      height: 72px;
      border-radius: 50%;
      background: linear-gradient(45deg, #dc3545, #c82333);
      border: none;
      color: white;
      font-size: 28px;
      cursor: pointer;
      transition: all 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      overflow: hidden;
      box-shadow: 0 6px 20px rgba(220, 53, 69, 0.4);
    }

    .mic-button:hover {
      transform: scale(1.05);
      box-shadow: 0 8px 24px rgba(220, 53, 69, 0.5);
    }

    .mic-button.recording {
      background: linear-gradient(45deg, #28a745, #20c997);
      animation: pulse 1.5s infinite;
      box-shadow: 0 6px 20px rgba(40, 167, 69, 0.5);
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
      50% { transform: scale(1.05); }
      100% { transform: scale(1); }
    }

    @keyframes ripple {
      0% { transform: translate(-50%, -50%) scale(0); opacity: 1; }
      100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }
    }

    .voice-status {
      font-size: 0.9rem;
      color: rgba(255,255,255,0.9);
      text-align: center;
      margin-top: 0.75rem;
      min-height: 22px;
      font-weight: 500;
      text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }

    .voice-not-supported {
      color: #ffc107;
      font-size: 0.85rem;
      text-align: center;
      margin-top: 0.5rem;
      font-weight: 500;
    }

    .examples {
      background: rgba(255,255,255,0.1);
      border-radius: 12px;
      padding: 1rem;
      margin-top: 1rem;
      border: 1px solid rgba(255,255,255,0.2);
    }

    .examples h3 {
      color: white;
      margin: 0 0 0.5rem 0;
      font-size: 1rem;
      font-weight: 600;
    }

    .examples ul {
      color: rgba(255,255,255,0.9);
      margin: 0;
      padding-left: 1.2rem;
      font-size: 0.9rem;
      line-height: 1.4;
    }

    .examples li {
      margin-bottom: 0.3rem;
    }

    .install-prompt {
      position: fixed;
      bottom: 20px;
      left: 20px;
      right: 20px;
      background: #007bff;
      color: white;
      padding: 16px 20px;
      border-radius: 12px;
      display: none;
      align-items: center;
      justify-content: space-between;
      z-index: 1000;
      box-shadow: 0 8px 24px rgba(0, 123, 255, 0.3);
      font-weight: 500;
    }

    .install-prompt button {
      background: rgba(255,255,255,0.2);
      border: none;
      color: white;
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.2s ease;
    }

    .install-prompt button:hover {
      background: rgba(255,255,255,0.3);
    }

    @media (max-width: 480px) {
      .container {
        max-width: 100%;
        margin-top: 1rem;
        gap: 1rem;
      }
      
      body {
        padding: 0.75rem;
      }
      
      h1 {
        font-size: 1.8rem;
      }
      
      .subtitle {
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
      }
      
      .mic-button {
        width: 64px;
        height: 64px;
        font-size: 24px;
      }
      
      .input-container, .response-container {
        padding: 1.25rem;
      }
      
      .feature-badges {
        flex-direction: column;
        align-items: center;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🎤📧 Voice SMS & Email</h1>
    <div class="subtitle">Speak naturally - AI makes it professional</div>
    
    <div class="feature-badges">
      <div class="feature-badge">📱 SMS Messages</div>
      <div class="feature-badge">📧 Email Support</div>
      <div class="feature-badge">✨ Auto-Enhanced</div>
    </div>
    
    <div class="input-container">
      <div class="input-group">
        <input type="text" id="command" placeholder="Try: 'Email john@email.com saying hey how are you doing'" />
        <button onclick="sendCommand()">Send</button>
      </div>
    </div>

    <div class="response-container">
      <div class="response-text" id="response">🎯 Ready to send professional messages and emails! Use the microphone button below or type your command.</div>
    </div>

    <div class="voice-controls">
      <button class="mic-button" id="micButton" onclick="toggleVoiceRecording()">
        🎤
      </button>
    </div>
    <div class="voice-status" id="voiceStatus"></div>

    <div class="examples">
      <h3>💬 SMS Examples:</h3>
      <ul>
        <li>"Text mom saying hey mom how are you doing today"</li>
        <li>"Send a message to +1234567890 saying thanks for the meeting"</li>
        <li>"Text Sarah saying can we reschedule our meeting"</li>
      </ul>
      
      <h3>📧 Email Examples:</h3>
      <ul>
        <li>"Email john@company.com saying thanks for the great meeting today"</li>
        <li>"Send an email to sarah@email.com saying can we reschedule our meeting"</li>
        <li>"Email boss@work.com about project update saying the project is going well"</li>
      </ul>
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

    // Initialize speech recognition
    function initSpeechRecognition() {
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        recognition.maxAlternatives = 3;
        
        recognition.onstart = function() {
          isRecording = true;
          document.getElementById('micButton').classList.add('recording');
          document.getElementById('voiceStatus').textContent = '🎤 Listening... Speak naturally!';
          document.getElementById('command').placeholder = 'Listening...';
        };
        
        recognition.onresult = function(event) {
          let transcript = '';
          let isFinal = false;
          
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              transcript += event.results[i][0].transcript;
              isFinal = true;
            } else {
              // Show interim results
              document.getElementById('command').value = event.results[i][0].transcript;
            }
          }
          
          if (isFinal) {
            document.getElementById('command').value = transcript.trim();
            document.getElementById('voiceStatus').textContent = `📝 Captured: "${transcript.trim()}"`;
            
            // Auto-submit after voice input with a delay
            setTimeout(() => {
              document.getElementById('voiceStatus').textContent = '🤖 Processing with AI...';
              sendCommand();
            }, 1500);
          }
        };
        
        recognition.onerror = function(event) {
          console.error('Speech recognition error:', event.error);
          let errorMessage = '❌ ';
          switch(event.error) {
            case 'no-speech':
              errorMessage += 'No speech detected. Try speaking louder.';
              break;
            case 'audio-capture':
              errorMessage += 'Microphone not accessible.';
              break;
            case 'not-allowed':
              errorMessage += 'Microphone permission denied.';
              break;
            case 'network':
              errorMessage += 'Network error. Check connection.';
              break;
            default:
              errorMessage += `Error: ${event.error}`;
          }
          document.getElementById('voiceStatus').textContent = errorMessage;
          stopRecording();
        };
        
        recognition.onend = function() {
          stopRecording();
        };
        
        voiceSupported = true;
        document.getElementById('voiceStatus').textContent = '🎤 Tap microphone to speak your message';
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
          // Clear previous input
          document.getElementById('command').value = '';
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
      document.getElementById('command').placeholder = 'Try: "Email john@email.com saying hey how are you doing"';
      
      if (document.getElementById('voiceStatus').textContent.includes('Listening')) {
        document.getElementById('voiceStatus').textContent = '🎤 Tap microphone to speak your message';
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

      output.textContent = "🤖 Processing with AI and enhancing message...";

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        output.textContent = "✅ " + (data.response || "Done!") + "\\n\\n📋 Raw Response:\\n" + JSON.stringify(data.claude_output, null, 2);
        input.value = "";
        document.getElementById('voiceStatus').textContent = voiceSupported ? '🎤 Tap microphone to speak your message' : '';
      })
      .catch(err => {
        output.textContent = "❌ Error: " + err.message;
        document.getElementById('voiceStatus').textContent = voiceSupported ? '🎤 Tap microphone to speak your message' : '';
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

    // Request microphone permission on first interaction
    document.getElementById('micButton').addEventListener('click', function() {
      if (!voiceSupported) return;
      
      // Request microphone permission
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function(stream) {
          // Permission granted, stop the stream
          stream.getTracks().forEach(track => track.stop());
        })
        .catch(function(err) {
          console.log('Microphone permission denied:', err);
          document.getElementById('voiceStatus').textContent = '❌ Microphone permission required';
        });
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
        
        # First, try to extract SMS or email command using pattern matching
        communication_command = extract_communication_command(prompt)
        
        if communication_command:
            # Direct processing with enhanced message/email
            print(f"[VOICE COMM] Detected command: {communication_command}")
            
            if communication_command["action"] == "send_email":
                dispatch_result = handle_send_email(communication_command)
            else:
                dispatch_result = handle_send_message(communication_command)
                
            return jsonify({
                "response": dispatch_result,
                "claude_output": communication_command
            })
        else:
            # Fall back to Claude for other commands
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
    twilio_status = "configured" if twilio_client.client else "not configured"
    email_status = "configured" if email_client.is_configured else "not configured"
    
    return jsonify({
        "status": "healthy",
        "twilio_status": twilio_status,
        "email_status": email_status,
        "claude_configured": bool(CONFIG["claude_api_key"]),
        "twilio_account_sid": CONFIG["twilio_account_sid"][:8] + "..." if CONFIG["twilio_account_sid"] else "not set",
        "email_username": CONFIG["email_username"][:5] + "..." if CONFIG["email_username"] else "not set",
        "features": ["voice_sms", "voice_email", "message_enhancement", "email_enhancement", "professional_formatting"]
    })

@app.route('/test_sms', methods=['POST'])
def test_sms():
    """Test SMS endpoint"""
    data = request.json
    to = data.get('to')
    message = data.get('message', 'Test message from Enhanced Flask AI Agent')
    enhance = data.get('enhance', True)
    
    if not to:
        return jsonify({"error": "Phone number 'to' is required"}), 400
    
    # Optionally enhance the message
    if enhance:
        enhanced_message = enhance_message_with_claude(message)
        result = twilio_client.send_sms(to, enhanced_message)
        result['original_message'] = message
        result['enhanced_message'] = enhanced_message
    else:
        result = twilio_client.send_sms(to, message)
    
    return jsonify(result)

@app.route('/test_email', methods=['POST'])
def test_email():
    """Test email endpoint"""
    data = request.json
    to = data.get('to')
    message = data.get('message', 'Test email from Enhanced Flask AI Agent with voice capabilities')
    subject = data.get('subject')
    enhance = data.get('enhance', True)
    
    if not to:
        return jsonify({"error": "Email address 'to' is required"}), 400
    
    if not is_email_address(to):
        return jsonify({"error": "Invalid email address"}), 400
    
    # Optionally enhance the email
    if enhance:
        enhanced_email = enhance_email_with_claude(message)
        final_subject = subject or enhanced_email["subject"]
        final_body = enhanced_email["body"]
        
        # Create HTML version
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                {final_body.replace('\n', '<br>')}
                <br><br>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">
                    Sent via AI Assistant
                </p>
            </body>
        </html>
        """
        
        result = email_client.send_email(to, final_subject, final_body, html_body)
        result['original_message'] = message
        result['enhanced_subject'] = final_subject
        result['enhanced_body'] = final_body
    else:
        final_subject = subject or "Message from AI Assistant"
        result = email_client.send_email(to, final_subject, message)
    
    return jsonify(result)

@app.route('/enhance_message', methods=['POST'])
def enhance_message_endpoint():
    """Endpoint to test message enhancement"""
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    enhanced = enhance_message_with_claude(message)
    
    return jsonify({
        "original": message,
        "enhanced": enhanced
    })

@app.route('/enhance_email', methods=['POST'])
def enhance_email_endpoint():
    """Endpoint to test email enhancement"""
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    enhanced = enhance_email_with_claude(message)
    
    return jsonify({
        "original": message,
        "enhanced_subject": enhanced["subject"],
        "enhanced_body": enhanced["body"]
    })

@app.route('/twilio_info', methods=['GET'])
def twilio_info():
    """Get Twilio account information"""
    result = twilio_client.get_account_info()
    return jsonify(result)

@app.route('/email_info', methods=['GET'])
def email_info():
    """Get email configuration information"""
    result = email_client.get_config_info()
    return jsonify(result)

if __name__ == '__main__':
    print("🚀 Starting Enhanced Smart AI Agent Flask App")
    print(f"📱 Twilio Status: {'✅ Connected' if twilio_client.client else '❌ Not configured'}")
    print(f"📧 Email Status: {'✅ Connected' if email_client.is_configured else '❌ Not configured'}")
    print(f"🤖 Claude Status: {'✅ Configured' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    print("✨ Features: Professional Voice SMS, Professional Voice Email, Message Enhancement, Auto-formatting")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
