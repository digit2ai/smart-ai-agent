# Enhanced Flask CMP Server with Multi-Recipient Professional Voice SMS & Email Processing
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
from datetime import datetime
from typing import Dict, Any, Optional, List
import re
import concurrent.futures

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
    # Email configuration - Network Solutions defaults
    "smtp_server": os.getenv("SMTP_SERVER", "mail.networksolutions.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "email_address": os.getenv("EMAIL_ADDRESS", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "email_name": os.getenv("EMAIL_NAME", "Smart AI Agent"),
    "email_provider": os.getenv("EMAIL_PROVIDER", "networksolutions").lower(),
}

INSTRUCTION_PROMPT = """
You are an intelligent assistant. Respond ONLY with valid JSON using one of the supported actions.

Supported actions:
- create_task
- create_appointment
- send_message (supports SMS via Twilio)
- send_message_multi (supports multiple recipients)
- send_email (supports email via SMTP)
- send_email_multi (supports multiple email recipients)
- log_conversation
- enhance_message (for making messages professional)

Each response must use this structure:
{
  "action": "create_task" | "create_appointment" | "send_message" | "send_message_multi" | "send_email" | "send_email_multi" | "log_conversation" | "enhance_message",
  "title": "...",               // for tasks, appointments, or email subject
  "due_date": "YYYY-MM-DDTHH:MM:SS", // or null
  "recipient": "Name, phone number, or email",    // for send_message/send_email (single recipient)
  "recipients": ["Name1", "Name2", "email@example.com"],       // for multi actions
  "message": "Body of the message/email",  // for send_message, send_email, or log
  "subject": "Email subject line",    // for email actions
  "original_message": "...",     // for enhance_message action
  "enhanced_message": "...",     // for enhance_message action
  "notes": "Optional details or transcript" // for CRM logs
}

For send_message action:
- If recipient looks like a phone number (starts with + or contains only digits), it will be sent as SMS
- Otherwise it will be logged as a regular message
- Phone numbers should be in E.164 format (e.g., +1234567890)

For send_email action:
- If recipient looks like an email (contains @), it will be sent as email
- Email addresses should be valid format (user@domain.com)
- Subject is optional, will auto-generate if not provided

For send_message_multi and send_email_multi actions:
- Recipients can be a mix of phone numbers, emails, and names
- Phone numbers will receive SMS, emails will receive email, names will be logged
- Message will be enhanced once and sent to all recipients

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
- Keep it appropriate for SMS/text messaging and email

Original message: "{original_message}"

Respond with ONLY the enhanced message, nothing else.
"""

EMAIL_SUBJECT_PROMPT = """
Generate a professional, concise email subject line for the following message content. The subject should be clear, specific, and under 50 characters.

Message content: "{message_content}"

Respond with ONLY the subject line, nothing else.
"""

class EmailClient:
    """SMTP Email client for sending emails with Network Solutions support"""
    
    def __init__(self):
        self.smtp_server = CONFIG["smtp_server"]
        self.smtp_port = CONFIG["smtp_port"]
        self.email_address = CONFIG["email_address"]
        self.email_password = CONFIG["email_password"]
        self.email_name = CONFIG["email_name"]
        self.email_provider = CONFIG["email_provider"]
        
        # Set defaults based on provider
        self._configure_provider_defaults()
        
        if self.email_address and self.email_password:
            print(f"✅ Email client configured successfully for {self.email_provider.title()}")
            print(f"📧 SMTP Server: {self.smtp_server}:{self.smtp_port}")
        else:
            print("⚠️ Email not configured - missing email address or password")
    
    def _configure_provider_defaults(self):
        """Configure default settings based on email provider"""
        if self.email_provider == "networksolutions":
            # Network Solutions specific settings
            if self.smtp_server == "smtp.gmail.com":  # If still using default
                self.smtp_server = "mail.networksolutions.com"
            if self.smtp_port == 587:  # Common for Network Solutions
                self.smtp_port = 587
        elif self.email_provider == "gmail":
            self.smtp_server = "smtp.gmail.com"
            self.smtp_port = 587
        elif self.email_provider == "outlook" or self.email_provider == "hotmail":
            self.smtp_server = "smtp-mail.outlook.com"
            self.smtp_port = 587
        elif self.email_provider == "yahoo":
            self.smtp_server = "smtp.mail.yahoo.com"
            self.smtp_port = 587
        
        print(f"🔧 Email provider: {self.email_provider.title()}")
        print(f"🔧 SMTP settings: {self.smtp_server}:{self.smtp_port}")
    
    def send_email(self, to: str, subject: str, message: str, is_html: bool = False) -> Dict[str, Any]:
        """Send email via SMTP with Network Solutions support"""
        if not self.email_address or not self.email_password:
            return {"error": "Email client not configured"}
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.email_name} <{self.email_address}>"
            msg['To'] = to
            msg['Subject'] = subject
            
            # Add body to email
            body_type = "html" if is_html else "plain"
            msg.attach(MIMEText(message, body_type))
            
            # Create SMTP session with provider-specific handling
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.set_debuglevel(0)  # Set to 1 for debugging
                
                # Enable TLS encryption
                server.starttls()
                
                # Login with provider-specific handling
                if self.email_provider == "networksolutions":
                    # Network Solutions may require full email as username
                    username = self.email_address
                else:
                    username = self.email_address
                
                server.login(username, self.email_password)
                
                # Send email
                text = msg.as_string()
                server.sendmail(self.email_address, to, text)
            
            return {
                "success": True,
                "to": to,
                "from": self.email_address,
                "subject": subject,
                "body": message,
                "timestamp": datetime.now().isoformat(),
                "provider": self.email_provider
            }
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Authentication failed for {self.email_provider.title()}: {str(e)}"
            if self.email_provider == "networksolutions":
                error_msg += "\n💡 For Network Solutions: Ensure you're using your full email address and correct password. Check if 2FA is enabled."
            return {"error": error_msg}
        except smtplib.SMTPServerDisconnected as e:
            return {"error": f"SMTP server disconnected: {str(e)}. Check server settings for {self.email_provider.title()}"}
        except smtplib.SMTPRecipientsRefused as e:
            return {"error": f"Recipient refused: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to send email via {self.email_provider.title()}: {str(e)}"}
    
    def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection with provider-specific troubleshooting"""
        if not self.email_address or not self.email_password:
            return {"error": "Email client not configured"}
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                
                # Use appropriate username for provider
                username = self.email_address
                server.login(username, self.email_password)
            
            return {
                "success": True,
                "server": self.smtp_server,
                "port": self.smtp_port,
                "email": self.email_address,
                "provider": self.email_provider,
                "message": f"Successfully connected to {self.email_provider.title()} SMTP server"
            }
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Authentication failed for {self.email_provider.title()}: {str(e)}"
            troubleshooting = ""
            
            if self.email_provider == "networksolutions":
                troubleshooting = """
💡 Network Solutions Troubleshooting:
- Use your full email address as username
- Use your email account password (not cPanel password)
- Ensure your domain's email is properly set up
- Check if your hosting plan includes email services
- Try mail.yourdomain.com as SMTP server if mail.networksolutions.com fails
- Verify port 587 or try port 25/465
- Ensure your IP isn't blocked by Network Solutions
"""
            
            return {"error": error_msg + troubleshooting}
        except Exception as e:
            return {"error": f"Email connection failed for {self.email_provider.title()}: {str(e)}"}
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider-specific configuration information"""
        provider_configs = {
            "networksolutions": {
                "smtp_server": "mail.networksolutions.com",
                "smtp_port": 587,
                "alternative_servers": [
                    "mail.yourdomain.com",  # Replace with actual domain
                    "secure.emailsrvr.com"  # Alternative Network Solutions server
                ],
                "alternative_ports": [25, 465, 587],
                "notes": [
                    "Use full email address as username",
                    "Use email account password, not cPanel password",
                    "Ensure email hosting is active on your plan",
                    "Some Network Solutions accounts use domain-specific SMTP servers"
                ]
            },
            "gmail": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "notes": [
                    "Requires App Password if 2FA is enabled",
                    "Must enable 'Less secure app access' if not using App Password"
                ]
            },
            "outlook": {
                "smtp_server": "smtp-mail.outlook.com",
                "smtp_port": 587,
                "notes": ["Works with Outlook.com, Hotmail, Live accounts"]
            }
        }
        
        return provider_configs.get(self.email_provider, {
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "notes": ["Custom configuration"]
        })

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

def call_claude(prompt, use_enhancement_prompt=False, use_subject_prompt=False, original_message="", message_content=""):
    """Call Claude API with different prompts based on use case"""
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        if use_enhancement_prompt:
            full_prompt = MESSAGE_ENHANCEMENT_PROMPT.format(original_message=original_message)
        elif use_subject_prompt:
            full_prompt = EMAIL_SUBJECT_PROMPT.format(message_content=message_content)
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
            
            if use_enhancement_prompt or use_subject_prompt:
                # For message enhancement or subject generation, return the raw text directly
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

def generate_email_subject(message: str) -> str:
    """Generate email subject using Claude AI"""
    try:
        result = call_claude("", use_subject_prompt=True, message_content=message)
        if "enhanced_message" in result:
            return result["enhanced_message"]
        else:
            # Fallback to simple subject
            return "Message from Smart AI Agent"
    except Exception as e:
        print(f"Error generating subject: {e}")
        return "Message from Smart AI Agent"

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
    # Simple email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, recipient.strip()))

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

def parse_recipients(recipients_text: str) -> List[str]:
    """Parse multiple recipients from text"""
    
    # Clean up the text
    recipients_text = recipients_text.strip()
    
    # Handle different separators and conjunctions
    # Replace common conjunctions with commas
    recipients_text = re.sub(r'\s+and\s+', ', ', recipients_text)
    recipients_text = re.sub(r'\s+&\s+', ', ', recipients_text)
    recipients_text = re.sub(r'\s*,\s*and\s+', ', ', recipients_text)
    
    # Split by comma and clean up
    recipients = [r.strip() for r in recipients_text.split(',')]
    
    # Remove empty strings
    recipients = [r for r in recipients if r]
    
    return recipients

def clean_voice_message(message: str) -> str:
    """Clean up voice recognition artifacts"""
    message = message.replace(" period", ".").replace(" comma", ",")
    message = message.replace(" question mark", "?").replace(" exclamation mark", "!")
    return message.strip()

def extract_email_command(text: str) -> Dict[str, Any]:
    """Extract email command from voice input"""
    # Common patterns for email commands
    patterns = [
        r'send (?:an )?email to (.+?) (?:with subject (.+?) )?saying (.+)',
        r'email (.+?) (?:with subject (.+?) )?saying (.+)',
        r'send (.+?) (?:an )?email (?:with subject (.+?) )?saying (.+)',
        r'email (.+?) that (.+)',
        r'send (?:an )?email to (.+?) (.+)',  # Simple pattern: "email john@example.com hello there"
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if len(groups) == 3 and groups[1]:  # Has subject
                recipient = groups[0].strip()
                subject = groups[1].strip()
                message = groups[2].strip()
            elif len(groups) == 3:  # No subject in middle
                recipient = groups[0].strip()
                subject = None
                message = groups[2].strip()
            else:  # Simple pattern
                recipient = groups[0].strip()
                subject = None
                message = groups[1].strip()
            
            # Clean up common voice recognition artifacts
            message = clean_voice_message(message)
            if subject:
                subject = clean_voice_message(subject)
            
            return {
                "action": "send_email",
                "recipient": recipient,
                "subject": subject,
                "message": message,
                "original_message": message
            }
    
    return None

def extract_sms_command(text: str) -> Dict[str, str]:
    """Extract SMS command from voice input using pattern matching (ORIGINAL WORKING VERSION)"""
    # Common patterns for SMS commands
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
            
            # Clean up common voice recognition artifacts
            message = clean_voice_message(message)
            
            return {
                "action": "send_message",
                "recipient": recipient,
                "message": message,
                "original_message": message
            }
    
    return None

def extract_sms_command_multi(text: str) -> Dict[str, Any]:
    """Enhanced SMS command extraction supporting multiple recipients"""
    
    # Patterns for multiple recipients
    multi_patterns = [
        # "send a text to John and Mary saying hello"
        r'send (?:a )?(?:text|message|sms) to (.+?) saying (.+)',
        # "text John, Mary, and Bob saying hello"
        r'text (.+?) saying (.+)',
        # "message John and Mary that we're running late"
        r'message (.+?) (?:that|saying) (.+)',
        # "tell John, Mary, and Bob that the meeting moved"
        r'tell (.+?) that (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in multi_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            recipients_text = match.group(1).strip()
            message = match.group(2).strip()
            
            # Parse multiple recipients
            recipients = parse_recipients(recipients_text)
            
            # Clean up voice recognition artifacts
            message = clean_voice_message(message)
            
            # Check if multiple recipients
            if len(recipients) > 1:
                return {
                    "action": "send_message_multi",
                    "recipients": recipients,
                    "message": message,
                    "original_message": message
                }
            else:
                # Single recipient - use original format
                return {
                    "action": "send_message",
                    "recipient": recipients[0] if recipients else recipients_text,
                    "message": message,
                    "original_message": message
                }
    
    return None

def extract_email_command_multi(text: str) -> Dict[str, Any]:
    """Enhanced email command extraction supporting multiple recipients"""
    
    # Patterns for multiple email recipients
    multi_patterns = [
        # "send an email to john@example.com and mary@example.com saying hello"
        r'send (?:an )?email to (.+?) (?:with subject (.+?) )?saying (.+)',
        # "email john@example.com, mary@example.com saying hello"
        r'email (.+?) saying (.+)',
        # "send john@example.com and mary@example.com an email saying hello"
        r'send (.+?) (?:an )?email saying (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in multi_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if len(groups) == 3 and groups[1]:  # Has subject
                recipients_text = groups[0].strip()
                subject = groups[1].strip()
                message = groups[2].strip()
            else:  # No subject
                recipients_text = groups[0].strip()
                subject = None
                message = groups[-1].strip()
            
            # Parse multiple recipients
            recipients = parse_recipients(recipients_text)
            
            # Clean up voice recognition artifacts
            message = clean_voice_message(message)
            if subject:
                subject = clean_voice_message(subject)
            
            # Check if multiple recipients
            if len(recipients) > 1:
                return {
                    "action": "send_email_multi",
                    "recipients": recipients,
                    "subject": subject,
                    "message": message,
                    "original_message": message
                }
            else:
                # Single recipient - use original format
                return {
                    "action": "send_email",
                    "recipient": recipients[0] if recipients else recipients_text,
                    "subject": subject,
                    "message": message,
                    "original_message": message
                }
    
    return None

def send_single_sms(recipient: str, message: str) -> Dict[str, Any]:
    """Send SMS to a single recipient"""
    
    if is_phone_number(recipient):
        formatted_phone = format_phone_number(recipient)
        result = twilio_client.send_sms(formatted_phone, message)
        result['formatted_recipient'] = formatted_phone
        result['original_recipient'] = recipient
        result['type'] = 'sms'
        return result
    else:
        return {
            "success": False,
            "error": f"Invalid phone number format: {recipient}",
            "original_recipient": recipient,
            "type": 'sms'
        }

def send_single_email(recipient: str, subject: str, message: str) -> Dict[str, Any]:
    """Send email to a single recipient"""
    
    if is_email_address(recipient):
        result = email_client.send_email(recipient, subject, message)
        result['original_recipient'] = recipient
        result['type'] = 'email'
        return result
    else:
        return {
            "success": False,
            "error": f"Invalid email address format: {recipient}",
            "original_recipient": recipient,
            "type": 'email'
        }

def send_sms_to_multiple(recipients: List[str], message: str, enhance: bool = True) -> Dict[str, Any]:
    """Send SMS to multiple recipients with threading for better performance"""
    
    if not recipients:
        return {"error": "No recipients provided"}
    
    # Enhance message once if requested
    enhanced_message = enhance_message_with_claude(message) if enhance else message
    
    results = []
    successful_sends = 0
    failed_sends = 0
    
    # Use ThreadPoolExecutor for concurrent SMS sending
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all SMS tasks
        future_to_recipient = {
            executor.submit(send_single_sms, recipient, enhanced_message): recipient 
            for recipient in recipients
        }
        
        # Collect results
        for future in concurrent.futures.as_completed(future_to_recipient):
            recipient = future_to_recipient[future]
            try:
                result = future.result()
                result['recipient'] = recipient
                results.append(result)
                
                if result.get('success'):
                    successful_sends += 1
                else:
                    failed_sends += 1
                    
            except Exception as exc:
                error_result = {
                    'recipient': recipient,
                    'success': False,
                    'error': f'Exception occurred: {exc}',
                    'type': 'sms'
                }
                results.append(error_result)
                failed_sends += 1
    
    return {
        "success": successful_sends > 0,
        "total_recipients": len(recipients),
        "successful_sends": successful_sends,
        "failed_sends": failed_sends,
        "original_message": message,
        "enhanced_message": enhanced_message,
        "results": results,
        "type": "sms_multi"
    }

def send_emails_to_multiple(recipients: List[str], subject: str, message: str, enhance: bool = True) -> Dict[str, Any]:
    """Send emails to multiple recipients with threading for better performance"""
    
    if not recipients:
        return {"error": "No recipients provided"}
    
    # Enhance message once if requested
    enhanced_message = enhance_message_with_claude(message) if enhance else message
    
    # Generate subject if not provided
    if not subject:
        subject = generate_email_subject(enhanced_message)
    
    results = []
    successful_sends = 0
    failed_sends = 0
    
    # Use ThreadPoolExecutor for concurrent email sending
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all email tasks
        future_to_recipient = {
            executor.submit(send_single_email, recipient, subject, enhanced_message): recipient 
            for recipient in recipients
        }
        
        # Collect results
        for future in concurrent.futures.as_completed(future_to_recipient):
            recipient = future_to_recipient[future]
            try:
                result = future.result()
                result['recipient'] = recipient
                results.append(result)
                
                if result.get('success'):
                    successful_sends += 1
                else:
                    failed_sends += 1
                    
            except Exception as exc:
                error_result = {
                    'recipient': recipient,
                    'success': False,
                    'error': f'Exception occurred: {exc}',
                    'type': 'email'
                }
                results.append(error_result)
                failed_sends += 1
    
    return {
        "success": successful_sends > 0,
        "total_recipients": len(recipients),
        "successful_sends": successful_sends,
        "failed_sends": failed_sends,
        "original_message": message,
        "enhanced_message": enhanced_message,
        "subject": subject,
        "results": results,
        "type": "email_multi"
    }

def send_mixed_messages(recipients: List[str], message: str, subject: str = None, enhance: bool = True) -> Dict[str, Any]:
    """Send messages to mixed recipients (SMS for phones, emails for email addresses)"""
    
    if not recipients:
        return {"error": "No recipients provided"}
    
    # Separate recipients by type
    phone_recipients = []
    email_recipients = []
    other_recipients = []
    
    for recipient in recipients:
        if is_phone_number(recipient):
            phone_recipients.append(recipient)
        elif is_email_address(recipient):
            email_recipients.append(recipient)
        else:
            other_recipients.append(recipient)
    
    # Enhance message once if requested
    enhanced_message = enhance_message_with_claude(message) if enhance else message
    
    results = []
    successful_sends = 0
    failed_sends = 0
    total_recipients = len(recipients)
    
    # Send SMS to phone numbers
    if phone_recipients:
        sms_result = send_sms_to_multiple(phone_recipients, message, enhance=False)  # Already enhanced
        results.extend(sms_result.get('results', []))
        successful_sends += sms_result.get('successful_sends', 0)
        failed_sends += sms_result.get('failed_sends', 0)
    
    # Send emails to email addresses
    if email_recipients:
        email_result = send_emails_to_multiple(email_recipients, subject, message, enhance=False)  # Already enhanced
        results.extend(email_result.get('results', []))
        successful_sends += email_result.get('successful_sends', 0)
        failed_sends += email_result.get('failed_sends', 0)
    
    # Log other recipients
    for recipient in other_recipients:
        results.append({
            'recipient': recipient,
            'success': False,
            'error': 'Unrecognized recipient format (not phone or email)',
            'type': 'unknown'
        })
        failed_sends += 1
    
    return {
        "success": successful_sends > 0,
        "total_recipients": total_recipients,
        "successful_sends": successful_sends,
        "failed_sends": failed_sends,
        "phone_recipients": len(phone_recipients),
        "email_recipients": len(email_recipients),
        "other_recipients": len(other_recipients),
        "original_message": message,
        "enhanced_message": enhanced_message,
        "subject": subject,
        "results": results,
        "type": "mixed_multi"
    }

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
    """Handle sending email to a single recipient"""
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    subject = data.get("subject", "")
    original_message = data.get("original_message", message)
    
    print(f"[CMP] Sending email to {recipient}")
    
    # Check if recipient is an email address
    if is_email_address(recipient):
        print(f"[CMP] Detected email address, processing email to {recipient}")
        
        # Enhance the message using Claude AI
        print(f"[CMP] Original message: {original_message}")
        enhanced_message = enhance_message_with_claude(original_message)
        print(f"[CMP] Enhanced message: {enhanced_message}")
        
        # Generate subject if not provided
        if not subject:
            subject = generate_email_subject(enhanced_message)
            print(f"[CMP] Generated subject: {subject}")
        
        # Send the enhanced email
        result = email_client.send_email(recipient, subject, enhanced_message)
        
        if "error" in result:
            return f"Failed to send email to {recipient}: {result['error']}"
        else:
            return f"✅ Professional email sent to {recipient}!\n\nSubject: {subject}\nOriginal: {original_message}\nEnhanced: {enhanced_message}\n\nSent at: {result.get('timestamp', 'N/A')}"
    else:
        # Not an email address
        enhanced_message = enhance_message_with_claude(message)
        return f"Enhanced message for {recipient}:\nOriginal: {message}\nEnhanced: {enhanced_message}\n\nNote: {recipient} is not a valid email address"

def handle_send_message_multi(data: Dict[str, Any]) -> str:
    """Handle sending messages to multiple recipients"""
    
    recipients = data.get("recipients", [])
    message = data.get("message", "")
    original_message = data.get("original_message", message)
    
    if not recipients:
        return "❌ No recipients specified"
    
    if not message:
        return "❌ No message specified"
    
    print(f"[CMP] Sending message to {len(recipients)} recipients: {recipients}")
    
    # Send to multiple recipients
    result = send_sms_to_multiple(recipients, original_message, enhance=True)
    
    if result["success"]:
        success_msg = f"✅ Message sent to {result['successful_sends']}/{result['total_recipients']} recipients!"
        success_msg += f"\n\nOriginal: {result['original_message']}"
        success_msg += f"\nEnhanced: {result['enhanced_message']}"
        
        if result["failed_sends"] > 0:
            success_msg += f"\n\n⚠️ {result['failed_sends']} messages failed to send"
            
        # Add details for each recipient
        success_msg += "\n\n📋 Delivery Details:"
        for res in result["results"]:
            status = "✅" if res.get("success") else "❌"
            recipient = res.get("original_recipient", res.get("recipient", "Unknown"))
            success_msg += f"\n{status} {recipient}"
            if not res.get("success"):
                success_msg += f" - {res.get('error', 'Unknown error')}"
        
        return success_msg
    else:
        return f"❌ Failed to send messages to all {result['total_recipients']} recipients"

def handle_send_email_multi(data: Dict[str, Any]) -> str:
    """Handle sending emails to multiple recipients"""
    
    recipients = data.get("recipients", [])
    message = data.get("message", "")
    subject = data.get("subject", "")
    original_message = data.get("original_message", message)
    
    if not recipients:
        return "❌ No recipients specified"
    
    if not message:
        return "❌ No message specified"
    
    print(f"[CMP] Sending email to {len(recipients)} recipients: {recipients}")
    
    # Send emails to multiple recipients
    result = send_emails_to_multiple(recipients, subject, original_message, enhance=True)
    
    if result["success"]:
        success_msg = f"✅ Email sent to {result['successful_sends']}/{result['total_recipients']} recipients!"
        success_msg += f"\n\nSubject: {result['subject']}"
        success_msg += f"\nOriginal: {result['original_message']}"
        success_msg += f"\nEnhanced: {result['enhanced_message']}"
        
        if result["failed_sends"] > 0:
            success_msg += f"\n\n⚠️ {result['failed_sends']} emails failed to send"
            
        # Add details for each recipient
        success_msg += "\n\n📋 Delivery Details:"
        for res in result["results"]:
            status = "✅" if res.get("success") else "❌"
            recipient = res.get("original_recipient", res.get("recipient", "Unknown"))
            success_msg += f"\n{status} {recipient}"
            if not res.get("success"):
                success_msg += f" - {res.get('error', 'Unknown error')}"
        
        return success_msg
    else:
        return f"❌ Failed to send emails to all {result['total_recipients']} recipients"

def handle_log_conversation(data):
    print("[CMP] Logging conversation:", data.get("notes"))
    return "Conversation log saved."

def dispatch_action(parsed):
    """Enhanced dispatch function with email and multi-recipient support"""
    action = parsed.get("action")
    if action == "create_task":
        return handle_create_task(parsed)
    elif action == "create_appointment":
        return handle_create_appointment(parsed)
    elif action == "send_message":
        return handle_send_message(parsed)
    elif action == "send_message_multi":
        return handle_send_message_multi(parsed)
    elif action == "send_email":
        return handle_send_email(parsed)
    elif action == "send_email_multi":
        return handle_send_email_multi(parsed)
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
        "description": "AI-powered task and appointment manager with professional voice SMS & Email",
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

# ----- Enhanced Mobile HTML Template -----
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
 <link rel="icon" type="image/png" href="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/687bba55e31a7722ec2593a8.png">
<link rel="apple-touch-icon" href="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/687bc4d4e36c15754e18b561.png">
  <title>Smart AI Agent</title>
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
      background: linear-gradient(to bottom, #2f2f2f 0%, #f9fafb 100%);
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
      color: #212529;
      text-align: center;
      margin-top: 0.75rem;
      min-height: 22px;
      font-weight: 500;
      text-shadow: none;
    }

    .voice-not-supported {
      color: #ffc107;
      font-size: 0.85rem;
      text-align: center;
      margin-top: 0.5rem;
      font-weight: 500;
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
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Smart AI Agent</h1>
    <div class="subtitle">Speak naturally - AI handles SMS & Email professionally</div>
    <div class="feature-badge">✨ Multi-Recipient Auto-Enhanced Messages & Emails</div>
    
    <div class="input-container">
      <div class="input-group">
        <input type="text" id="command" placeholder="Try: 'Text John saying hello' or 'Email john@example.com saying meeting at 3pm'" />
        <button onclick="sendCommand()">Send</button>
      </div>
    </div>

    <div class="response-container">
      <div class="response-text" id="response">🎯 Ready to send professional messages and emails! 

📱 SMS Examples:
• "Text 8136414177 saying hey how are you"
• "Text John and Mary saying the meeting moved to 3pm"

📧 Email Examples:
• "Email john@example.com saying the meeting is at 3pm"
• "Email john@example.com with subject meeting update saying the time changed"
• "Email john@example.com and mary@example.com saying hello everyone"

🔄 Mixed Examples:
• "Send a message to 8136414177 and john@example.com saying hello"
• "Message Mom and dad@example.com that I'll be home late"

Use the microphone button below or type your command.</div>
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

    // Initialize speech recognition (ORIGINAL MOBILE-WORKING VERSION)
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
              document.getElementById('voiceStatus').textContent = 'Processing with AI...';
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
        document.getElementById('voiceStatus').textContent = 'Tap microphone to speak your message';
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
      document.getElementById('command').placeholder = 'Try: "Text John saying hello" or "Email john@example.com saying meeting at 3pm"';
      
      if (document.getElementById('voiceStatus').textContent.includes('Listening')) {
        document.getElementById('voiceStatus').textContent = 'Tap microphone to speak your message';
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

      output.textContent = "Processing with AI and enhancing message...";

      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
      })
      .then(res => res.json())
      .then(data => {
        output.textContent = "✅ " + (data.response || "Done!") + "\\n\\n📋 Raw Response:\\n" + JSON.stringify(data.claude_output, null, 2);
        input.value = "";
        document.getElementById('voiceStatus').textContent = voiceSupported ? 'Tap microphone to speak your message' : '';
      })
      .catch(err => {
        output.textContent = "❌ Error: " + err.message;
        document.getElementById('voiceStatus').textContent = voiceSupported ? 'Tap microphone to speak your message' : '';
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

# Enhanced execute route with email support
@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        
        # FIRST: Try email commands
        email_command = extract_email_command(prompt)
        
        if email_command:
            print(f"[VOICE EMAIL] Detected email command: {email_command}")
            dispatch_result = handle_send_email(email_command)
            return jsonify({
                "response": dispatch_result,
                "claude_output": email_command
            })
        
        # SECOND: Try multi-recipient email commands
        multi_email_command = extract_email_command_multi(prompt)
        
        if multi_email_command:
            print(f"[VOICE EMAIL MULTI] Detected multi-recipient email: {multi_email_command}")
            if multi_email_command["action"] == "send_email_multi":
                dispatch_result = handle_send_email_multi(multi_email_command)
            else:
                dispatch_result = handle_send_email(multi_email_command)
            return jsonify({
                "response": dispatch_result,
                "claude_output": multi_email_command
            })
        
        # THIRD: Try the original SMS command (this was working on mobile before)
        sms_command = extract_sms_command(prompt)
        
        if sms_command:
            print(f"[VOICE SMS] Detected SMS command: {sms_command}")
            dispatch_result = handle_send_message(sms_command)
            return jsonify({
                "response": dispatch_result,
                "claude_output": sms_command
            })
        
        # FOURTH: Try multi-recipient SMS
        multi_sms_command = extract_sms_command_multi(prompt)
        
        if multi_sms_command:
            print(f"[VOICE SMS MULTI] Detected multi-recipient SMS: {multi_sms_command}")
            if multi_sms_command["action"] == "send_message_multi":
                dispatch_result = handle_send_message_multi(multi_sms_command)
            else:
                dispatch_result = handle_send_message(multi_sms_command)
            return jsonify({
                "response": dispatch_result,
                "claude_output": multi_sms_command
            })
        
        # FIFTH: Check for mixed message commands (phone numbers and emails together)
        if "message" in prompt.lower() or "send" in prompt.lower():
            # Look for patterns that might contain both phones and emails
            mixed_patterns = [
                r'(?:send|message) (.+?) (?:saying|that) (.+)',
                r'(?:tell|notify) (.+?) (?:that|about) (.+)',
            ]
            
            for pattern in mixed_patterns:
                match = re.search(pattern, prompt.lower(), re.IGNORECASE)
                if match:
                    recipients_text = match.group(1).strip()
                    message = match.group(2).strip()
                    recipients = parse_recipients(recipients_text)
                    
                    # Check if we have mixed recipient types
                    has_phone = any(is_phone_number(r) for r in recipients)
                    has_email = any(is_email_address(r) for r in recipients)
                    
                    if has_phone or has_email:
                        print(f"[MIXED MESSAGING] Detected mixed recipients: {recipients}")
                        result = send_mixed_messages(recipients, message, enhance=True)
                        
                        # Format response
                        if result["success"]:
                            response_msg = f"✅ Mixed messages sent to {result['successful_sends']}/{result['total_recipients']} recipients!"
                            response_msg += f"\n\n📱 SMS: {result['phone_recipients']} recipients"
                            response_msg += f"\n📧 Email: {result['email_recipients']} recipients"
                            if result['other_recipients'] > 0:
                                response_msg += f"\n❓ Other: {result['other_recipients']} recipients"
                            
                            response_msg += f"\n\nOriginal: {result['original_message']}"
                            response_msg += f"\nEnhanced: {result['enhanced_message']}"
                            
                            if result["failed_sends"] > 0:
                                response_msg += f"\n\n⚠️ {result['failed_sends']} messages failed"
                            
                            # Add delivery details
                            response_msg += "\n\n📋 Delivery Details:"
                            for res in result["results"]:
                                status = "✅" if res.get("success") else "❌"
                                recipient = res.get("original_recipient", res.get("recipient", "Unknown"))
                                msg_type = res.get("type", "unknown").upper()
                                response_msg += f"\n{status} {recipient} ({msg_type})"
                                if not res.get("success"):
                                    response_msg += f" - {res.get('error', 'Unknown error')}"
                            
                            return jsonify({
                                "response": response_msg,
                                "claude_output": {
                                    "action": "mixed_messaging",
                                    "recipients": recipients,
                                    "message": message,
                                    "result": result
                                }
                            })
        
        # SIXTH: Fall back to Claude for other commands
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
    email_status = "configured" if email_client.email_address and email_client.email_password else "not configured"
    
    return jsonify({
        "status": "healthy",
        "twilio_status": twilio_status,
        "email_status": email_status,
        "claude_configured": bool(CONFIG["claude_api_key"]),
        "twilio_account_sid": CONFIG["twilio_account_sid"][:8] + "..." if CONFIG["twilio_account_sid"] else "not set",
        "email_address": CONFIG["email_address"] if CONFIG["email_address"] else "not set",
        "features": ["voice_sms", "voice_email", "multi_recipient_sms", "multi_recipient_email", "mixed_messaging", "message_enhancement", "professional_formatting", "auto_subject_generation"]
    })

@app.route('/test_sms', methods=['POST'])
def test_sms():
    """Test single SMS endpoint"""
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
    """Test single email endpoint"""
    data = request.json
    to = data.get('to')
    subject = data.get('subject', '')
    message = data.get('message', 'Test email from Enhanced Flask AI Agent with Email Support')
    enhance = data.get('enhance', True)
    
    if not to:
        return jsonify({"error": "Email address 'to' is required"}), 400
    
    # Optionally enhance the message
    if enhance:
        enhanced_message = enhance_message_with_claude(message)
        if not subject:
            subject = generate_email_subject(enhanced_message)
        result = email_client.send_email(to, subject, enhanced_message)
        result['original_message'] = message
        result['enhanced_message'] = enhanced_message
        result['generated_subject'] = subject
    else:
        if not subject:
            subject = "Test Email from Smart AI Agent"
        result = email_client.send_email(to, subject, message)
    
    return jsonify(result)

@app.route('/test_multi_sms', methods=['POST'])
def test_multi_sms():
    """Test multi-recipient SMS endpoint"""
    data = request.json
    recipients = data.get('recipients', [])  # List of phone numbers
    message = data.get('message', 'Test multi-recipient message from Enhanced Flask AI Agent')
    enhance = data.get('enhance', True)
    
    if not recipients:
        return jsonify({"error": "Recipients list is required"}), 400
    
    if not isinstance(recipients, list):
        return jsonify({"error": "Recipients must be a list"}), 400
    
    result = send_sms_to_multiple(recipients, message, enhance)
    return jsonify(result)

@app.route('/test_multi_email', methods=['POST'])
def test_multi_email():
    """Test multi-recipient email endpoint"""
    data = request.json
    recipients = data.get('recipients', [])  # List of email addresses
    subject = data.get('subject', '')
    message = data.get('message', 'Test multi-recipient email from Enhanced Flask AI Agent')
    enhance = data.get('enhance', True)
    
    if not recipients:
        return jsonify({"error": "Recipients list is required"}), 400
    
    if not isinstance(recipients, list):
        return jsonify({"error": "Recipients must be a list"}), 400
    
    result = send_emails_to_multiple(recipients, subject, message, enhance)
    return jsonify(result)

@app.route('/test_mixed', methods=['POST'])
def test_mixed():
    """Test mixed messaging endpoint (SMS + Email)"""
    data = request.json
    recipients = data.get('recipients', [])  # Mix of phone numbers and email addresses
    subject = data.get('subject', '')
    message = data.get('message', 'Test mixed message from Enhanced Flask AI Agent')
    enhance = data.get('enhance', True)
    
    if not recipients:
        return jsonify({"error": "Recipients list is required"}), 400
    
    if not isinstance(recipients, list):
        return jsonify({"error": "Recipients must be a list"}), 400
    
    result = send_mixed_messages(recipients, message, subject, enhance)
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

@app.route('/generate_subject', methods=['POST'])
def generate_subject_endpoint():
    """Endpoint to test email subject generation"""
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    subject = generate_email_subject(message)
    
    return jsonify({
        "message": message,
        "generated_subject": subject
    })

@app.route('/twilio_info', methods=['GET'])
def twilio_info():
    """Get Twilio account information"""
    result = twilio_client.get_account_info()
    return jsonify(result)

@app.route('/email_config', methods=['GET'])
def email_config():
    """Get email provider configuration and troubleshooting info"""
    provider_info = email_client.get_provider_info()
    current_config = {
        "current_smtp_server": email_client.smtp_server,
        "current_smtp_port": email_client.smtp_port,
        "current_email": email_client.email_address,
        "current_provider": email_client.email_provider
    }
    
    return jsonify({
        "current_config": current_config,
        "provider_info": provider_info,
        "status": "configured" if email_client.email_address and email_client.email_password else "not configured"
    })

@app.route('/email_info', methods=['GET'])
def email_info():
    """Get email connection test results"""
    result = email_client.test_connection()
    return jsonify(result)

if __name__ == '__main__':
    print("🚀 Starting Enhanced Smart AI Agent Flask App with SMS & Email Support")
    print(f"📱 Twilio Status: {'✅ Connected' if twilio_client.client else '❌ Not configured'}")
    print(f"📧 Email Status: {'✅ Configured' if email_client.email_address and email_client.email_password else '❌ Not configured'}")
    print(f"🤖 Claude Status: {'✅ Configured' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    print("✨ Features: Multi-Recipient SMS, Multi-Recipient Email, Mixed Messaging, Professional Voice Processing, Message Enhancement, Auto-Subject Generation")
    print("🔧 Execution order: Email → Multi-Email → SMS → Multi-SMS → Mixed → Claude fallback")
    print("\\n📋 Voice Command Examples:")
    print("  📱 SMS Commands:")
    print("    • 'Text 8136414177 saying hey how are you'")
    print("    • 'Send a message to John saying the meeting moved'")
    print("    • 'Text John and Mary saying the meeting moved to 3pm'")
    print("  📧 Email Commands:")
    print("    • 'Email john@example.com saying the meeting is at 3pm'")
    print("    • 'Email john@example.com with subject meeting update saying the time changed'")
    print("    • 'Email john@example.com and mary@example.com saying hello everyone'")
    print("  🔄 Mixed Commands:")
    print("    • 'Send a message to 8136414177 and john@example.com saying hello'")
    print("    • 'Message Mom and dad@example.com that I'll be home late'")
    
    # Environment variable setup guide
    print("\\n🔧 Environment Variables Required:")
    print("  CLAUDE_API_KEY=your_claude_api_key")
    print("  TWILIO_ACCOUNT_SID=your_twilio_account_sid")
    print("  TWILIO_AUTH_TOKEN=your_twilio_auth_token")
    print("  TWILIO_PHONE_NUMBER=your_twilio_phone_number")
    print("  EMAIL_ADDRESS=your_email@yourdomain.com")
    print("  EMAIL_PASSWORD=your_email_password")
    print("  EMAIL_PROVIDER=networksolutions (optional, defaults to networksolutions)")
    print("  SMTP_SERVER=mail.networksolutions.com (optional, auto-configured)")
    print("  SMTP_PORT=587 (optional, auto-configured)")
    print("  EMAIL_NAME=Your Name (optional, defaults to 'Smart AI Agent')")
    print("\\n📧 Network Solutions Email Setup:")
    print("  - Use your full email address (user@yourdomain.com) as EMAIL_ADDRESS")
    print("  - Use your email account password (not cPanel password)")
    print("  - Ensure email hosting is active on your Network Solutions plan")
    print("  - Default SMTP: mail.networksolutions.com:587")
    print("  - Alternative: mail.yourdomain.com:587 (replace yourdomain.com)")
    print("  - Test connection with: curl http://localhost:10000/email_info")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
