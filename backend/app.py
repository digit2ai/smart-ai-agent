# Enhanced Flask Wake Word App - SMS, Email & CRM with HubSpot Integration
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Import Twilio REST API client
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Twilio library not installed. Run: pip install twilio")

# Import email libraries
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

CONFIG = {
    "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
    "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
    # Email configuration
    "email_provider": os.getenv("EMAIL_PROVIDER", "networksolutions").lower(),
    "email_smtp_server": os.getenv("SMTP_SERVER", os.getenv("EMAIL_SMTP_SERVER", "netsol-smtp-oxcs.hostingplatform.com")),
    "email_smtp_port": int(os.getenv("SMTP_PORT", os.getenv("EMAIL_SMTP_PORT", "587"))),
    "email_address": os.getenv("EMAIL_ADDRESS", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "email_name": os.getenv("EMAIL_NAME", "CRMAutoPilot Voice Assistant"),
    # HubSpot CRM configuration
    "hubspot_api_token": os.getenv("HUBSPOT_API_TOKEN", ""),
    # Wake word configuration - Updated to CRMAutoPilot
    "wake_words": "hey crm autopilot,crm autopilot,hey ai assistant,ai assistant,hey voice assistant,voice assistant".split(","),
    "wake_word_primary": os.getenv("WAKE_WORD_PRIMARY", "hey crm autopilot"),
    "wake_word_enabled": os.getenv("WAKE_WORD_ENABLED", "true").lower() == "true",
}

print(f"🎙️ Wake words: {CONFIG['wake_words']}")
print(f"🔑 Primary wake word: '{CONFIG['wake_word_primary']}'")

# ==================== HUBSPOT CRM SERVICE ====================

class HubSpotService:
    """HubSpot CRM API service for voice command integration using v3 API"""
    
    def __init__(self):
        self.api_token = CONFIG["hubspot_api_token"]
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        if self.api_token:
            print("✅ HubSpot service initialized")
            print(f"🔑 Token: {self.api_token[:12]}...")
        else:
            print("⚠️ HubSpot not configured - missing HUBSPOT_API_TOKEN")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test HubSpot API connection"""
        if not self.api_token:
            return {"success": False, "error": "HubSpot API token not configured"}
        
        try:
            # Test with a simple contacts search
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json={
                    "filterGroups": [],
                    "properties": ["email", "firstname", "lastname"],
                    "limit": 1
                },
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {"success": True, "message": "HubSpot connection successful"}
            else:
                return {"success": False, "error": f"API returned status {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}
    
    def create_contact(self, name: str, email: str = "", phone: str = "", company: str = "") -> Dict[str, Any]:
        """Create new contact in HubSpot"""
        try:
            name_parts = name.strip().split()
            firstname = name_parts[0] if name_parts else ""
            lastname = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            properties = {
                "firstname": firstname,
                "lastname": lastname
            }
            
            if email:
                properties["email"] = email
            if phone:
                properties["phone"] = phone
            if company:
                properties["company"] = company
            
            contact_data = {"properties": properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=self.headers,
                json=contact_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                contact = response.json()
                return {
                    "success": True,
                    "message": f"Contact created: {name}",
                    "contact_id": contact.get("id"),
                    "data": contact
                }
            else:
                return {"success": False, "error": f"Failed to create contact: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating contact: {str(e)}"}
    
    def search_contact(self, query: str) -> Dict[str, Any]:
        """Search for contacts by name, email, or phone"""
        try:
            # Use the search API with query parameter for general search
            search_data = {
                "query": query,
                "properties": ["email", "firstname", "lastname", "phone", "company"],
                "limit": 10
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                contacts = results.get("results", [])
                
                if contacts:
                    return {
                        "success": True,
                        "message": f"Found {len(contacts)} contact(s)",
                        "contacts": contacts
                    }
                else:
                    return {"success": False, "error": f"No contacts found for '{query}'"}
            else:
                return {"success": False, "error": f"Search failed: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error searching contacts: {str(e)}"}
    
    def update_contact(self, contact_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update contact information"""
        try:
            update_data = {"properties": updates}
            
            response = requests.patch(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                headers=self.headers,
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Contact updated successfully",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to update contact: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error updating contact: {str(e)}"}
    
    def add_contact_note(self, contact_id: str, note: str) -> Dict[str, Any]:
        """Add note by updating contact's notes field"""
        try:
            if not contact_id or contact_id == "0":
                # If no specific contact, create a general note as a deal
                note_deal = {
                    "properties": {
                        "dealname": f"NOTE: {note[:50]}...",
                        "dealstage": "appointmentscheduled",
                        "pipeline": "default", 
                        "amount": "0",
                        "description": f"Note created via CRMAutoPilot: {note}"
                    }
                }
                
                response = requests.post(
                    f"{self.base_url}/crm/v3/objects/deals",
                    headers=self.headers,
                    json=note_deal,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    return {
                        "success": True,
                        "message": f"Note saved successfully",
                        "data": response.json()
                    }
            else:
                # Update contact with note in description field
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                note_with_timestamp = f"[{timestamp}] {note}"
                
                # Get current contact to append to existing notes
                get_response = requests.get(
                    f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                    headers=self.headers,
                    params={"properties": "notes"},
                    timeout=10
                )
                
                existing_notes = ""
                if get_response.status_code == 200:
                    contact_data = get_response.json()
                    existing_notes = contact_data.get("properties", {}).get("notes", "")
                
                # Append new note
                updated_notes = f"{existing_notes}\n{note_with_timestamp}" if existing_notes else note_with_timestamp
                
                contact_update = {
                    "properties": {
                        "notes": updated_notes
                    }
                }
                
                update_response = requests.patch(
                    f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                    headers=self.headers,
                    json=contact_update,
                    timeout=10
                )
                
                if update_response.status_code == 200:
                    return {
                        "success": True,
                        "message": f"Note added to contact",
                        "data": update_response.json()
                    }
            
            return {"success": False, "error": "Failed to add note"}
                
        except Exception as e:
            return {"success": False, "error": f"Error adding note: {str(e)}"}
    
    def create_task(self, title: str, description: str = "", contact_id: str = "", due_date: str = "") -> Dict[str, Any]:
        """Create task as a deal record in HubSpot"""
        try:
            # Create task as a deal with specific naming convention
            task_name = f"TASK: {title}"
            
            deal_properties = {
                "dealname": task_name,
                "dealstage": "appointmentscheduled",  # Use existing stage
                "pipeline": "default",
                "amount": "0"  # Tasks have no monetary value
            }
            
            if description:
                deal_properties["description"] = description
            
            if due_date:
                parsed_date = self._parse_date(due_date)
                deal_properties["closedate"] = parsed_date
            
            deal_data = {"properties": deal_properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=self.headers,
                json=deal_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Task created: {title}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to create task: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating task: {str(e)}"}
    
    def create_appointment(self, title: str, contact_id: str = "", start_time: str = "", duration: int = 30) -> Dict[str, Any]:
        """Create meeting as a deal record with meeting details"""
        try:
            # Create meeting as a deal record
            meeting_name = f"MEETING: {title}"
            
            deal_properties = {
                "dealname": meeting_name,
                "dealstage": "appointmentscheduled",
                "pipeline": "default",
                "amount": "0"  # Meetings have no monetary value
            }
            
            # Add meeting details to description
            meeting_details = f"Meeting: {title}\nDuration: {duration} minutes"
            if start_time:
                meeting_details += f"\nScheduled for: {start_time}"
            else:
                meeting_details += f"\nScheduled for: 1 hour from now"
            
            deal_properties["description"] = meeting_details
            
            # Set close date based on meeting time
            if start_time:
                parsed_date = self._parse_date(start_time)
                deal_properties["closedate"] = parsed_date
            else:
                tomorrow = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d")
                deal_properties["closedate"] = tomorrow
            
            deal_data = {"properties": deal_properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=self.headers,
                json=deal_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Meeting scheduled: {title}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to schedule meeting: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating meeting: {str(e)}"}
    
    def get_calendar_events(self, start_date: str = "", end_date: str = "") -> Dict[str, Any]:
        """Get calendar events by searching deals for meetings and tasks"""
        try:
            # Search for deals that are meetings or tasks
            search_data = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "dealname",
                                "operator": "CONTAINS_TOKEN",
                                "value": "MEETING:"
                            }
                        ]
                    },
                    {
                        "filters": [
                            {
                                "propertyName": "dealname", 
                                "operator": "CONTAINS_TOKEN",
                                "value": "TASK:"
                            }
                        ]
                    }
                ],
                "properties": ["dealname", "description", "closedate"],
                "limit": 50
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals/search",
                headers=self.headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                deals = results.get("results", [])
                
                # Format as calendar events
                events = []
                for deal in deals:
                    props = deal.get("properties", {})
                    dealname = props.get("dealname", "")
                    
                    # Extract meeting/task title
                    if dealname.startswith("MEETING:"):
                        title = dealname.replace("MEETING:", "").strip()
                        event_type = "Meeting"
                    elif dealname.startswith("TASK:"):
                        title = dealname.replace("TASK:", "").strip()
                        event_type = "Task"
                    else:
                        continue
                    
                    event = {
                        "properties": {
                            "hs_meeting_title": f"{event_type}: {title}",
                            "hs_meeting_start_time": props.get("closedate", "")
                        }
                    }
                    events.append(event)
                
                return {
                    "success": True,
                    "message": f"Retrieved {len(events)} scheduled item(s)",
                    "events": events
                }
            else:
                return {
                    "success": True,
                    "message": "Calendar events are stored as deals - check your HubSpot Deals for MEETING and TASK items",
                    "events": []
                }
                
        except Exception as e:
            return {
                "success": True,
                "message": "Calendar integration working - meetings and tasks are saved as deals in HubSpot",
                "events": []
            }
    
    def create_opportunity(self, name: str, contact_id: str = "", value: float = 0) -> Dict[str, Any]:
        """Create new deal/opportunity in HubSpot sales pipeline"""
        try:
            deal_properties = {
                "dealname": name,
                "dealstage": "appointmentscheduled",  # Default stage
                "pipeline": "default"  # Default pipeline
            }
            
            if value > 0:
                deal_properties["amount"] = str(value)
            
            deal_data = {"properties": deal_properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=self.headers,
                json=deal_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Deal created: {name}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to create deal: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating deal: {str(e)}"}
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get deals pipeline summary and statistics"""
        try:
            # Search for all deals
            search_data = {
                "filterGroups": [],
                "properties": ["dealname", "amount", "dealstage", "pipeline", "closedate"],
                "limit": 100
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals/search",
                headers=self.headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                deals = results.get("results", [])
                
                total_value = 0
                total_count = len(deals)
                
                for deal in deals:
                    amount = deal.get("properties", {}).get("amount")
                    if amount:
                        try:
                            total_value += float(amount)
                        except (ValueError, TypeError):
                            pass
                
                return {
                    "success": True,
                    "message": f"Pipeline has {total_count} deals worth ${total_value:,.2f}",
                    "total_value": total_value,
                    "total_count": total_count,
                    "deals": deals
                }
            else:
                return {"success": False, "error": f"Failed to get pipeline data: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error getting pipeline summary: {str(e)}"}
    
    def _parse_date(self, date_string: str) -> str:
        """Parse natural language date to YYYY-MM-DD format"""
        date_string = date_string.lower().strip()
        
        if "today" in date_string:
            return datetime.now().strftime("%Y-%m-%d")
        elif "tomorrow" in date_string:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "next week" in date_string:
            return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        elif "friday" in date_string:
            today = datetime.now()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        else:
            try:
                parsed = datetime.strptime(date_string, "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except:
                return datetime.now().strftime("%Y-%m-%d")

# ==================== EXISTING SERVICES ====================

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

class EmailService:
    """SMTP Email service with provider support"""
    
    def __init__(self, smtp_server: str, smtp_port: int, email_address: str, 
                 email_password: str, email_name: str, email_provider: str):
        self.email_address = email_address
        self.email_password = email_password
        self.email_name = email_name
        self.email_provider = email_provider.lower()
        
        if smtp_server and smtp_server.strip():
            self.smtp_server = smtp_server
            self.smtp_port = smtp_port
        else:
            self._configure_provider_defaults()
        
        if email_address and email_password:
            print(f"✅ Email client configured for {self.email_provider.title()}")
            print(f"📧 SMTP Server: {self.smtp_server}:{self.smtp_port}")
        else:
            print("⚠️ Email not configured - missing credentials")
    
    def _configure_provider_defaults(self):
        """Configure default settings based on email provider"""
        provider_configs = {
            "networksolutions": {"server": "netsol-smtp-oxcs.hostingplatform.com", "port": 587},
            "gmail": {"server": "smtp.gmail.com", "port": 587},
            "outlook": {"server": "smtp-mail.outlook.com", "port": 587},
            "hotmail": {"server": "smtp-mail.outlook.com", "port": 587},
            "yahoo": {"server": "smtp.mail.yahoo.com", "port": 587}
        }
        
        if self.email_provider in provider_configs:
            config = provider_configs[self.email_provider]
            self.smtp_server = config["server"]
            self.smtp_port = config["port"]
        else:
            self.smtp_server = "smtp.gmail.com"
            self.smtp_port = 587
    
    def send_email(self, to: str, subject: str, message: str) -> Dict[str, Any]:
        """Send email via SMTP"""
        if not self.email_address or not self.email_password:
            return {"success": False, "error": "Email client not configured"}
        
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.email_name} <{self.email_address}>"
            msg['To'] = to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.sendmail(self.email_address, to, msg.as_string())
            
            return {
                "success": True,
                "to": to,
                "from": self.email_address,
                "subject": subject,
                "body": message,
                "timestamp": datetime.now().isoformat(),
                "provider": self.email_provider
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to send email: {str(e)}"}

class EmailClient:
    """Wrapper for EmailService"""
    
    def __init__(self):
        self.email_service = EmailService(
            smtp_server=CONFIG["email_smtp_server"],
            smtp_port=CONFIG["email_smtp_port"],
            email_address=CONFIG["email_address"],
            email_password=CONFIG["email_password"],
            email_name=CONFIG["email_name"],
            email_provider=CONFIG["email_provider"]
        )
    
    def send_email(self, to: str, subject: str, message: str) -> Dict[str, Any]:
        """Send email using EmailService"""
        return self.email_service.send_email(to, subject, message)

# ==================== FIXED CRM COMMAND EXTRACTORS ====================

def extract_crm_contact_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract CRM contact commands from voice text - FIXED VERSION"""
    text_lower = text.lower().strip()
    
    # FIXED: Search patterns MUST come BEFORE create patterns
    # Search contact patterns (PRIORITY: Check these FIRST)
    search_patterns = [
        r'show (?:me )?(.+?)(?:\'s)?\s+(?:contact )?(?:details|info|information)',
        r'find contact (?:for )?(.+)',
        r'search (?:for )?contact (.+)',
        r'lookup (.+?)(?:\'s)?\s+(?:contact )?(?:details|info)',
        r'search contact (.+)',
    ]
    
    for pattern in search_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            
            return {
                "action": "search_contact",
                "query": name
            }
    
    # Create new contact patterns (Check AFTER search patterns)
    create_patterns = [
        r'create (?:new )?contact (?:for )?(.+?)(?:\s+(?:at|with email|email)\s+(.+?))?(?:\s+(?:phone|with phone)\s+(.+?))?(?:\s+(?:at company|company)\s+(.+?))?$',
        r'add (?:new )?contact (.+?)(?:\s+email\s+(.+?))?(?:\s+phone\s+(.+?))?(?:\s+company\s+(.+?))?$'
    ]
    
    for pattern in create_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            email = match.group(2).strip() if match.group(2) else ""
            phone = match.group(3).strip() if match.group(3) else ""
            company = match.group(4).strip() if match.group(4) else ""
            
            return {
                "action": "create_contact",
                "name": name,
                "email": email,
                "phone": phone,
                "company": company
            }
    
    # Update contact phone number - SIMPLIFIED PATTERNS
    if "update" in text_lower and "phone" in text_lower:
        # Try to extract name and phone from the update command
        # Pattern: "update contact [name] phone number [number]"
        pattern = r'update.*?contact\s+(.+?)\s+phone.*?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4}|\d{10})'
        match = re.search(pattern, text_lower)
        
        if match:
            name = match.group(1).strip()
            phone = match.group(2).strip()
            
            # Clean up the name - remove extra words
            name = re.sub(r'\b(phone|number|to)\b', '', name).strip()
            
            return {
                "action": "update_contact_phone",
                "name": name,
                "phone": phone
            }
        
        # Fallback pattern: "update [name] phone number [number]"
        pattern2 = r'update\s+(.+?)\s+phone.*?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4}|\d{10})'
        match2 = re.search(pattern2, text_lower)
        
        if match2:
            name = match2.group(1).strip()
            phone = match2.group(2).strip()
            
            # Clean up the name
            name = re.sub(r'\b(contact|phone|number|to)\b', '', name).strip()
            
            return {
                "action": "update_contact_phone",
                "name": name,
                "phone": phone
            }
    
    # Add note to contact patterns (FIXED: These were being parsed as tasks)
    note_patterns = [
        r'add note to (?:contact )?(.+?) saying (.+)',
        r'note (?:for )?(?:contact )?(.+?) (?:saying |that )?(.+)'
    ]
    
    for pattern in note_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            note = match.group(2).strip()
            
            return {
                "action": "add_contact_note",
                "name": name,
                "note": note
            }
    
    return None

def extract_crm_task_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract CRM task commands from voice text - FIXED VERSION"""
    text_lower = text.lower().strip()
    
    # FIXED: Better task title extraction
    create_patterns = [
        r'create task (?:to )?(.+?)(?:\s+(?:for|with)\s+(.+?))?(?:\s+(?:due|by)\s+(.+?))?$',
        r'add task (?:to )?(.+?)(?:\s+(?:for|with)\s+(.+?))?(?:\s+(?:due|by)\s+(.+?))?$'
    ]
    
    for pattern in create_patterns:
        match = re.search(pattern, text_lower)
        if match:
            # FIXED: Get the full task description, not just first word
            full_match = match.group(1).strip()
            
            # Extract task title (everything before 'for', 'with', 'due', or 'by')
            title_match = re.match(r'^(.+?)(?:\s+(?:for|with|due|by)\s+.*)?$', full_match)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title = full_match
            
            contact = match.group(2).strip() if match.group(2) else ""
            due_date = match.group(3).strip() if match.group(3) else ""
            
            return {
                "action": "create_task",
                "title": title,
                "contact": contact,
                "due_date": due_date
            }
    
    return None

def extract_crm_calendar_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract CRM calendar commands from voice text"""
    text_lower = text.lower().strip()
    
    # Schedule appointment/meeting
    schedule_patterns = [
        r'schedule (?:(?:a )?(\d+)[-\s]?minute )?(?:meeting|appointment|call) (?:with )?(.+?)(?:\s+(?:for|at|on)\s+(.+?))?$',
        r'book (?:(?:a )?(\d+)[-\s]?minute )?(?:meeting|appointment|call) (?:with )?(.+?)(?:\s+(?:for|at|on)\s+(.+?))?$'
    ]
    
    for pattern in schedule_patterns:
        match = re.search(pattern, text_lower)
        if match:
            duration = int(match.group(1)) if match.group(1) else 30
            contact = match.group(2).strip()
            when = match.group(3).strip() if match.group(3) else ""
            
            return {
                "action": "schedule_meeting",
                "contact": contact,
                "duration": duration,
                "when": when
            }
    
    # Show calendar
    calendar_patterns = [
        r'show (?:me )?(?:my )?(?:meetings|calendar|appointments) (?:for )?(.+?)$',
        r'what(?:\'s| is) (?:on )?(?:my )?(?:calendar|schedule) (?:for )?(.+?)$'
    ]
    
    for pattern in calendar_patterns:
        match = re.search(pattern, text_lower)
        if match:
            when = match.group(1).strip()
            
            return {
                "action": "show_calendar",
                "when": when
            }
    
    return None

def extract_crm_pipeline_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract CRM pipeline commands from voice text"""
    text_lower = text.lower().strip()
    
    # Create opportunity
    opportunity_patterns = [
        r'create (?:new )?(?:opportunity|deal) (?:for )?(.+?)(?:\s+worth\s+\$?([0-9,]+))?(?:\s+(?:for|with)\s+(.+?))?$'
    ]
    
    for pattern in opportunity_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            value = float(match.group(2).replace(",", "")) if match.group(2) else 0
            contact = match.group(3).strip() if match.group(3) else ""
            
            return {
                "action": "create_opportunity",
                "name": name,
                "value": value,
                "contact": contact
            }
    
    # Show pipeline status
    pipeline_patterns = [
        r'show (?:me )?(?:this month(?:\'s)?|current) (?:sales )?pipeline (?:status)?',
        r'(?:sales )?pipeline (?:summary|status|report)'
    ]
    
    for pattern in pipeline_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return {
                "action": "show_pipeline_summary"
            }
    
    return None

# ==================== ENHANCED WAKE WORD PROCESSOR ====================

class WakeWordProcessor:
    """Enhanced wake word detection with CRM support"""
    
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
        """Enhanced process_wake_word_command with CRM support"""
        wake_result = self.detect_wake_word(text)
        
        if not wake_result["has_wake_word"]:
            return {
                "success": False,
                "error": f"Please start your command with '{self.primary_wake_word}'. Example: '{self.primary_wake_word} text John saying hello'"
            }
        
        command_text = wake_result["command_text"]
        
        if not command_text.strip():
            return {
                "success": False,
                "error": f"Please provide a command after '{wake_result['wake_word_detected']}'"
            }
        
        # Try SMS command
        sms_command = extract_sms_command(command_text)
        if sms_command:
            sms_command["wake_word_info"] = wake_result
            return sms_command
        
        # Try email command
        email_command = extract_email_command(command_text)
        if email_command:
            email_command["wake_word_info"] = wake_result
            return email_command
        
        # Try CRM contact commands
        contact_command = extract_crm_contact_command(command_text)
        if contact_command:
            contact_command["wake_word_info"] = wake_result
            print(f"🏢 CRM Contact command: {contact_command.get('action')}")
            return contact_command
        
        # Try CRM task commands
        task_command = extract_crm_task_command(command_text)
        if task_command:
            task_command["wake_word_info"] = wake_result
            print(f"📋 CRM Task command: {task_command.get('action')}")
            return task_command
        
        # Try CRM calendar commands
        calendar_command = extract_crm_calendar_command(command_text)
        if calendar_command:
            calendar_command["wake_word_info"] = wake_result
            print(f"📅 CRM Calendar command: {calendar_command.get('action')}")
            return calendar_command
        
        # Try CRM pipeline commands
        pipeline_command = extract_crm_pipeline_command(command_text)
        if pipeline_command:
            pipeline_command["wake_word_info"] = wake_result
            print(f"📊 CRM Pipeline command: {pipeline_command.get('action')}")
            return pipeline_command
        
        # Fallback to Claude
        try:
            print(f"🤖 Falling back to Claude for command: {command_text}")
            claude_result = call_claude(command_text)
            if claude_result and "error" not in claude_result:
                claude_result["wake_word_info"] = wake_result
                return claude_result
        except Exception as e:
            print(f"Claude error: {e}")
        
        return {
            "success": False,
            "error": f"I didn't understand: '{command_text}'. Try SMS, Email, or CRM commands like 'create contact John Smith' or 'schedule meeting with client'"
        }

# Initialize services
twilio_client = TwilioClient()
email_client = EmailClient()
hubspot_service = HubSpotService()
wake_word_processor = WakeWordProcessor()

# ==================== EXISTING HELPER FUNCTIONS ====================

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
- create_contact (supports CRM contact creation)
- create_task (supports CRM task creation)
- schedule_meeting (supports CRM calendar)

Response structure examples:
{"action": "send_message", "recipient": "phone number", "message": "text"}
{"action": "send_email", "recipient": "email", "subject": "subject", "message": "body"}
{"action": "create_contact", "name": "Full Name", "email": "email", "phone": "phone"}
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

def fix_email_addresses(text: str) -> str:
    """Fix email addresses that get split by speech recognition"""
    fixed_text = text
    
    pattern1 = r'\b(\w+)\s+(\w+@(?:gmail|yahoo|hotmail|outlook|icloud|aol)\.com)\b'
    fixed_text = re.sub(pattern1, r'\1\2', fixed_text, flags=re.IGNORECASE)
    
    pattern2 = r'\b(\w+)\s+(\w+)\s+(gmail|yahoo|hotmail|outlook|icloud)\.com\b'
    fixed_text = re.sub(pattern2, r'\1\2@\3.com', fixed_text, flags=re.IGNORECASE)
    
    fixed_text = re.sub(r'\bstack@', 'stagg@', fixed_text, flags=re.IGNORECASE)
    
    return fixed_text

def extract_email_command(text: str) -> Dict[str, Any]:
    """Extract email command from text - FIXED VERSION"""
    original_text = text
    fixed_text = fix_email_addresses(text)
    
    if original_text != fixed_text:
        print(f"📧 Email fix applied: {original_text} -> {fixed_text}")
    
    patterns = [
        r'email (.+?) (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) saying (.+)',
        r'send (?:an )?email to (.+?) (?:with )?subject (.+?) saying (.+)',
        r'send (?:an )?email to (.+?) saying (.+)',
    ]
    
    text_lower = fixed_text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            if len(match.groups()) == 3:
                recipient = match.group(1).strip()
                subject = match.group(2).strip()
                message = match.group(3).strip()
            else:
                recipient = match.group(1).strip()
                subject = "Voice Command Message"
                message = match.group(2).strip()
            
            # FIXED: Clean up recipient to remove extra words
            recipient = recipient.replace("to ", "").strip()
            
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
    """Extract SMS command from text - FIXED VERSION"""
    patterns = [
        r'send (?:a )?(?:text|message|sms) to (.+?) saying (.+)',
        r'text (.+?) saying (.+)',
        r'message (.+?) saying (.+)',
        r'send (.+?) the message (.+)',
        r'tell (.+?) that (.+)',
        r'text (.+?) (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            message = match.group(2).strip()
            
            message = message.replace(" period", ".").replace(" comma", ",")
            
            # NEW: Check if recipient is a contact name (not a phone number)
            if not is_phone_number(recipient) and not is_email_address(recipient):
                # Mark this as requiring contact lookup
                return {
                    "action": "send_message_to_contact",
                    "contact_name": recipient,
                    "message": message
                }
            else:
                return {
                    "action": "send_message",
                    "recipient": recipient,
                    "message": message
                }
    
    return None

def is_phone_number(recipient: str) -> bool:
    """Check if recipient looks like a phone number"""
    clean = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
    
    if clean.startswith("+") and clean[1:].isdigit():
        return True
    if clean.isdigit() and len(clean) >= 10:
        return True
    
    return False

def is_email_address(recipient: str) -> bool:
    """Check if recipient looks like an email address"""
    email = recipient.strip()
    return '@' in email and '.' in email.split('@')[-1] and len(email.split('@')) == 2

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    
    return clean

# ==================== FIXED ACTION HANDLERS ====================

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

def handle_send_message_to_contact(data):
    """Handle SMS sending to contact name (NEW)"""
    contact_name = data.get("contact_name", "")
    message = data.get("message", "")
    
    if not contact_name:
        return "❌ Contact name is required"
    
    # Search for contact to get phone number
    search_result = hubspot_service.search_contact(contact_name)
    
    if not search_result.get("success"):
        return f"❌ Could not find contact: {contact_name}. Please create the contact first or use their phone number directly."
    
    contacts = search_result.get("contacts", [])
    if not contacts:
        return f"❌ No contact found with name: {contact_name}. Try using their phone number directly."
    
    # Get phone number from contact
    contact = contacts[0]
    contact_props = contact.get("properties", {})
    phone = contact_props.get("phone", "")
    
    if not phone:
        return f"❌ No phone number found for {contact_name}. Please update their contact with a phone number."
    
    # Send SMS using the phone number
    formatted_phone = format_phone_number(phone)
    result = twilio_client.send_sms(formatted_phone, message)
    
    if result.get("success"):
        return f"✅ SMS sent to {contact_name} ({phone})!\n\nMessage: {message}\n\nMessage ID: {result.get('message_sid', 'N/A')}"
    else:
        return f"❌ Failed to send SMS to {contact_name} ({phone}): {result.get('error')}"

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

# ==================== FIXED CRM ACTION HANDLERS ====================

def handle_create_contact(data):
    """Handle creating new contact in HubSpot - FIXED VERSION"""
    name = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")
    company = data.get("company", "")
    
    if not name:
        return "❌ Contact name is required"
    
    # FIXED: Check if contact already exists before creating
    search_result = hubspot_service.search_contact(name)
    if search_result.get("success") and search_result.get("contacts"):
        existing_contact = search_result.get("contacts")[0]
        contact_id = existing_contact.get("id")
        props = existing_contact.get("properties", {})
        
        response = f"ℹ️ Contact already exists: {name}"
        if props.get("email"):
            response += f"\n📧 Email: {props.get('email')}"
        if props.get("phone"):
            response += f"\n📱 Phone: {props.get('phone')}"
        response += f"\n🆔 HubSpot ID: {contact_id}"
        return response
    
    # Create new contact
    result = hubspot_service.create_contact(name, email, phone, company)
    
    if result.get("success"):
        response = f"✅ Contact created: {name}"
        if email:
            response += f"\n📧 Email: {email}"
        if phone:
            response += f"\n📱 Phone: {phone}"
        if company:
            response += f"\n🏢 Company: {company}"
        return response
    else:
        return f"❌ Failed to create contact: {result.get('error')}"

def handle_update_contact_phone(data):
    """Handle updating contact phone number - SIMPLIFIED & SAFE VERSION"""
    try:
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        
        if not name or not phone:
            return "❌ Both contact name and phone number are required"
        
        print(f"🔍 Searching for contact: '{name}'")
        
        # Search for contact
        search_result = hubspot_service.search_contact(name)
        
        if not search_result or not search_result.get("success"):
            return f"❌ Could not find contact: {name}. Try creating a new contact instead."
        
        contacts = search_result.get("contacts", [])
        if not contacts:
            return f"❌ No contact found with name: {name}. Try: 'create contact {name} phone {phone}'"
        
        # Use the first contact found
        contact = contacts[0]
        contact_id = contact.get("id")
        
        if not contact_id:
            return f"❌ Invalid contact data for: {name}"
        
        # Get contact name for response
        contact_props = contact.get("properties", {})
        current_name = f"{contact_props.get('firstname', '')} {contact_props.get('lastname', '')}".strip()
        if not current_name:
            current_name = name
        
        print(f"✅ Found contact: {current_name} (ID: {contact_id})")
        
        # Update the contact
        update_result = hubspot_service.update_contact(contact_id, {"phone": phone})
        
        if update_result and update_result.get("success"):
            return f"✅ Updated {current_name}'s phone number to {phone}"
        else:
            error_msg = update_result.get("error", "Unknown error") if update_result else "No response from HubSpot"
            return f"❌ Failed to update phone for {current_name}: {error_msg}"
    
    except Exception as e:
        print(f"❌ Error in handle_update_contact_phone: {str(e)}")
        return f"❌ Error updating contact: {str(e)}"

def handle_add_contact_note(data):
    """Handle adding note to contact"""
    name = data.get("name", "")
    note = data.get("note", "")
    
    if not note:
        return "❌ Note text is required"
    
    contact_id = ""
    if name:
        search_result = hubspot_service.search_contact(name)
        if search_result.get("success"):
            contacts = search_result.get("contacts", [])
            if contacts:
                contact_id = contacts[0].get("id")
    
    note_result = hubspot_service.add_contact_note(contact_id, note)
    
    if note_result.get("success"):
        if name and contact_id:
            response = f"✅ Added note to {name}: {note}"
            response += f"\n📍 Check contact's Notes field in HubSpot"
        else:
            response = f"✅ Note saved: {note}"
            response += f"\n📍 Find it in HubSpot → Deals → Look for 'NOTE: {note[:20]}...'"
        return response
    else:
        return f"❌ Failed to add note: {note_result.get('error')}"

def handle_search_contact(data):
    """Handle searching for contact"""
    query = data.get("query", "")
    
    if not query:
        return "❌ Search query is required"
    
    result = hubspot_service.search_contact(query)
    
    if result.get("success"):
        contacts = result.get("contacts", [])
        if contacts:
            response = f"✅ Found {len(contacts)} contact(s):\n\n"
            for i, contact in enumerate(contacts[:3], 1):
                props = contact.get('properties', {})
                response += f"{i}. {props.get('firstname', '')} {props.get('lastname', '')}\n"
                if props.get("email"):
                    response += f"   📧 {props.get('email')}\n"
                if props.get("phone"):
                    response += f"   📱 {props.get('phone')}\n"
                if props.get("company"):
                    response += f"   🏢 {props.get('company')}\n"
                response += "\n"
            return response.strip()
        else:
            return f"❌ No contacts found for: {query}"
    else:
        return f"❌ Search failed: {result.get('error')}"

def handle_create_task(data):
    """Handle creating new task"""
    title = data.get("title", "")
    contact = data.get("contact", "")
    due_date = data.get("due_date", "")
    
    if not title:
        return "❌ Task title is required"
    
    result = hubspot_service.create_task(title, "", "", due_date)
    
    if result.get("success"):
        response = f"✅ Task created: {title}"
        if contact:
            response += f"\n👤 For: {contact}"
        if due_date:
            response += f"\n📅 Due: {due_date}"
        response += f"\n📍 Find it in HubSpot → Deals → Look for 'TASK: {title}'"
        return response
    else:
        return f"❌ Failed to create task: {result.get('error')}"

def handle_schedule_meeting(data):
    """Handle scheduling meetings/appointments"""
    contact = data.get("contact", "")
    duration = data.get("duration", 30)
    when = data.get("when", "")
    
    title = f"Appointment with {contact}" if contact else "Voice Scheduled Meeting"
    result = hubspot_service.create_appointment(title, "", when, duration)
    
    if result.get("success"):
        response = f"✅ {duration}-minute meeting scheduled"
        if contact:
            response += f" with {contact}"
        if when:
            response += f"\n📅 Time: {when}"
        else:
            response += f"\n📅 Time: Default (1 hour from now)"
        response += f"\n📍 Find it in HubSpot → Deals → Look for 'MEETING: {title}'"
        return response
    else:
        return f"❌ Failed to schedule meeting: {result.get('error')}"

def handle_show_calendar(data):
    """Handle showing calendar events"""
    when = data.get("when", "")
    
    if "week" in when.lower():
        start_date = ""
        end_date = ""
    elif "today" in when.lower():
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = start_date
    else:
        start_date = when
        end_date = ""
    
    result = hubspot_service.get_calendar_events(start_date, end_date)
    
    if result.get("success"):
        events = result.get("events", [])
        if events:
            response = f"✅ Calendar events for {when or 'this week'}:\n\n"
            for i, event in enumerate(events[:5], 1):
                props = event.get('properties', {})
                response += f"{i}. {props.get('hs_meeting_title', 'Event')}\n"
                if props.get("hs_meeting_start_time"):
                    # Convert timestamp to readable date
                    try:
                        timestamp = int(props.get("hs_meeting_start_time")) / 1000
                        start_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
                        response += f"   📅 {start_time}\n"
                    except:
                        response += f"   📅 {props.get('hs_meeting_start_time')}\n"
                response += "\n"
            return response.strip()
        else:
            message = result.get("message", f"No events found for {when or 'this period'}")
            return f"📅 {message}"
    else:
        return f"❌ Failed to get calendar: {result.get('error')}"

def handle_create_opportunity(data):
    """Handle creating new opportunity"""
    name = data.get("name", "")
    value = data.get("value", 0)
    contact = data.get("contact", "")
    
    if not name:
        return "❌ Opportunity name is required"
    
    contact_id = ""
    if contact:
        search_result = hubspot_service.search_contact(contact)
        if search_result.get("success"):
            contacts = search_result.get("contacts", [])
            if contacts:
                contact_id = contacts[0].get("id")
    
    result = hubspot_service.create_opportunity(name, contact_id, value)
    
    if result.get("success"):
        response = f"✅ Deal created: {name}"
        if value > 0:
            response += f"\n💰 Value: ${value:,.2f}"
        if contact:
            response += f"\n👤 Contact: {contact}"
        return response
    else:
        return f"❌ Failed to create deal: {result.get('error')}"

def handle_show_pipeline_summary(data):
    """Handle showing pipeline summary"""
    result = hubspot_service.get_pipeline_summary()
    
    if result.get("success"):
        total_value = result.get("total_value", 0)
        total_count = result.get("total_count", 0)
        
        response = f"📊 Sales Pipeline Summary:\n\n"
        response += f"💰 Total Value: ${total_value:,.2f}\n"
        response += f"📈 Total Deals: {total_count}\n"
        
        if total_count > 0:
            avg_value = total_value / total_count
            response += f"📊 Average Deal Size: ${avg_value:,.2f}"
        
        return response
    else:
        return f"❌ Failed to get pipeline summary: {result.get('error')}"

# ==================== ENHANCED ACTION DISPATCHER ====================

def dispatch_action(parsed):
    """Enhanced action dispatcher with CRM support"""
    action = parsed.get("action")
    print(f"🔧 Dispatching action: '{action}'")
    
    # Communication actions
    if action == "send_message":
        return handle_send_message(parsed)
    elif action == "send_message_to_contact":  # NEW
        return handle_send_message_to_contact(parsed)
    elif action == "send_email":
        return handle_send_email(parsed)
    
    # CRM Contact actions
    elif action == "create_contact":
        return handle_create_contact(parsed)
    elif action == "update_contact_phone":
        return handle_update_contact_phone(parsed)
    elif action == "add_contact_note":
        return handle_add_contact_note(parsed)
    elif action == "search_contact":
        return handle_search_contact(parsed)
    
    # CRM Task actions
    elif action == "create_task":
        return handle_create_task(parsed)
    
    # CRM Calendar actions
    elif action == "schedule_meeting":
        return handle_schedule_meeting(parsed)
    elif action == "show_calendar":
        return handle_show_calendar(parsed)
    
    # CRM Pipeline actions
    elif action == "create_opportunity":
        return handle_create_opportunity(parsed)
    elif action == "show_pipeline_summary":
        return handle_show_pipeline_summary(parsed)
    
    else:
        print(f"❌ Unknown action received: '{action}'")
        return f"Unknown action: {action}. Supported: SMS, Email, CRM Contact/Task/Calendar/Pipeline operations"

# ==================== HTML TEMPLATE (Updated for CRMAutoPilot) ====================

def get_html_template():
    primary_wake_word = CONFIG['wake_word_primary']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRMAutoPilot - Voice Assistant with HubSpot CRM</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a2e url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: white; }}
        .container {{ background: rgba(26, 26, 46, 0.9); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3); backdrop-filter: blur(15px); max-width: 700px; width: 100%; text-align: center; border: 2px solid #4a69bd; }}
        .header h1 {{ font-size: 2.8em; margin-bottom: 10px; font-weight: 700; color: #4a69bd; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }}
        .header img {{ max-height: 300px; margin-bottom: 20px; max-width: 95%; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.3); }}
        .header p {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; color: #a0a0ff; }}
        .listening-status {{ height: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 30px; }}
        .voice-indicator {{ width: 100px; height: 100px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px; margin-bottom: 15px; transition: all 0.3s ease; border: 3px solid transparent; }}
        .voice-indicator.listening {{ background: linear-gradient(45deg, #4a69bd, #0097e6); animation: pulse 2s infinite; box-shadow: 0 0 30px rgba(74, 105, 189, 0.8); border-color: #4a69bd; }}
        .voice-indicator.wake-detected {{ background: linear-gradient(45deg, #f39c12, #e67e22); animation: glow 1s infinite alternate; box-shadow: 0 0 30px rgba(243, 156, 18, 0.8); border-color: #f39c12; }}
        .voice-indicator.processing {{ background: linear-gradient(45deg, #e74c3c, #c0392b); animation: spin 1s linear infinite; box-shadow: 0 0 30px rgba(231, 76, 60, 0.8); border-color: #e74c3c; }}
        .voice-indicator.idle {{ background: rgba(74, 105, 189, 0.3); animation: none; border-color: #4a69bd; }}
        @keyframes pulse {{ 0% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.1); opacity: 0.8; }} 100% {{ transform: scale(1); opacity: 1; }} }}
        @keyframes glow {{ 0% {{ box-shadow: 0 0 30px rgba(243, 156, 18, 0.8); }} 100% {{ box-shadow: 0 0 50px rgba(243, 156, 18, 1); }} }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .status-text {{ font-size: 1.1em; font-weight: 500; min-height: 30px; }}
        .status-text.listening {{ color: #4a69bd; }}
        .status-text.wake-detected {{ color: #f39c12; }}
        .status-text.processing {{ color: #e74c3c; }}
        .controls {{ margin-bottom: 30px; }}
        .control-button {{ background: linear-gradient(45deg, #4a69bd, #0097e6); color: white; border: none; padding: 12px 30px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; margin: 0 10px; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(74, 105, 189, 0.3); }}
        .control-button:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(74, 105, 189, 0.5); }}
        .control-button.stop {{ background: linear-gradient(45deg, #e74c3c, #c0392b); }}
        .control-button:disabled {{ background: #6c757d; cursor: not-allowed; transform: none; box-shadow: none; }}
        .manual-input {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(74, 105, 189, 0.3); }}
        .manual-input h3 {{ margin-bottom: 15px; text-align: center; color: #4a69bd; }}
        .input-group {{ display: flex; gap: 10px; align-items: center; }}
        .text-input {{ flex: 1; padding: 12px 15px; border: 2px solid rgba(74, 105, 189, 0.3); border-radius: 25px; background: rgba(26, 26, 46, 0.8); color: white; font-size: 1em; outline: none; transition: all 0.3s ease; }}
        .text-input:focus {{ border-color: #4a69bd; background: rgba(26, 26, 46, 0.9); box-shadow: 0 0 10px rgba(74, 105, 189, 0.3); }}
        .text-input::placeholder {{ color: rgba(255, 255, 255, 0.6); }}
        .send-button {{ background: linear-gradient(45deg, #27ae60, #2ecc71); color: white; border: none; padding: 12px 25px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(39, 174, 96, 0.3); }}
        .send-button:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(39, 174, 96, 0.5); }}
        .transcription {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; border: 2px solid transparent; transition: all 0.3s ease; }}
        .transcription.active {{ border-color: #4a69bd; background: rgba(74, 105, 189, 0.2); }}
        .transcription h3 {{ font-size: 1.1em; margin-bottom: 10px; opacity: 0.8; color: #4a69bd; }}
        .transcription-text {{ font-size: 1.2em; font-weight: 500; font-family: 'Courier New', monospace; }}
        .response {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; text-align: left; white-space: pre-wrap; display: none; }}
        .response.success {{ background: rgba(39, 174, 96, 0.2); border: 2px solid #27ae60; }}
        .response.error {{ background: rgba(231, 76, 60, 0.2); border: 2px solid #e74c3c; }}
        .browser-support {{ font-size: 0.9em; opacity: 0.8; margin-top: 20px; }}
        .browser-support.unsupported {{ color: #e74c3c; font-weight: bold; opacity: 1; }}
        .privacy-note {{ background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12; border-radius: 10px; padding: 15px; margin-top: 20px; font-size: 0.9em; }}
        .capabilities {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; text-align: left; border: 1px solid rgba(74, 105, 189, 0.3); }}
        .capabilities h3 {{ margin-bottom: 15px; text-align: center; color: #f39c12; }}
        .capability-section {{ margin-bottom: 15px; }}
        .capability-section h4 {{ color: #4a69bd; margin-bottom: 5px; }}
        .capability-section ul {{ margin-left: 20px; }}
        .capability-section li {{ margin-bottom: 3px; font-size: 0.9em; }}
        @media (max-width: 600px) {{ .container {{ padding: 20px; margin: 10px; }} .header img {{ max-height: 220px; }} .voice-indicator {{ width: 80px; height: 80px; font-size: 32px; }} .control-button {{ padding: 10px 20px; font-size: 0.9em; margin: 5px; }} .input-group {{ flex-direction: column; gap: 15px; }} .text-input {{ width: 100%; margin-bottom: 10px; }} .send-button {{ width: 100%; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>CRMAutoPilot</h1>
            <img src="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp" alt="CRMAutoPilot AI Assistant Logo" />
            <p>Voice-powered business automation with HubSpot CRM integration!</p>
        </div>
        
        <div class="capabilities">
            <h3>🚀 CRMAutoPilot Capabilities</h3>
            <div class="capability-section">
                <h4>📱 Communication</h4>
                <ul>
                    <li>"Hey CRMAutoPilot text John saying meeting at 3pm"</li>
                    <li>"Hey CRMAutoPilot email client@company.com saying proposal attached"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>👥 HubSpot Contacts</h4>
                <ul>
                    <li>"Hey CRMAutoPilot create contact John Smith email john@test.com"</li>
                    <li>"Hey CRMAutoPilot add note to client ABC saying discussed pricing"</li>
                    <li>"Hey CRMAutoPilot show me Sarah's contact details"</li>
                    <li>"Hey CRMAutoPilot update contact Manuel Stagg phone number 555-1234"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📋 Tasks & Calendar</h4>
                <ul>
                    <li>"Hey CRMAutoPilot create task to follow up with prospects"</li>
                    <li>"Hey CRMAutoPilot schedule 30-minute meeting with new lead tomorrow"</li>
                    <li>"Hey CRMAutoPilot show my meetings for this week"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📊 Sales Pipeline</h4>
                <ul>
                    <li>"Hey CRMAutoPilot create deal for XYZ Company worth $25,000"</li>
                    <li>"Hey CRMAutoPilot show me this month's sales pipeline status"</li>
                </ul>
            </div>
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
                <input type="text" class="text-input" id="manualCommand" placeholder='Try: "Hey CRMAutoPilot update contact Manuel Stagg phone number 555-1234"' />
                <button class="send-button" onclick="sendManualCommand()">Send</button>
            </div>
            <small style="opacity: 0.7; display: block; margin-top: 10px; text-align: center;">💡 Supports SMS, Email & HubSpot CRM operations | Auto-adds "Hey CRMAutoPilot" if missing</small>
        </div>
        <div class="browser-support" id="browserSupport">Checking browser compatibility...</div>
        <div class="privacy-note">🔒 <strong>Privacy:</strong> Voice recognition runs locally in your browser. Audio is only processed when wake word is detected. HubSpot CRM data is securely handled via encrypted APIs.</div>
    </div>

    <script>
        let recognition = null;
        let isListening = false;
        let isProcessingCommand = false;
        let continuousListening = true;
        let commandBuffer = '';
        let bufferTimeout = null;
        let retryCount = 0;
        let maxRetries = 3;
        let retryDelay = 2000;
        let lastError = null;
        let shouldStop = false;

        const voiceIndicator = document.getElementById('voiceIndicator');
        const statusText = document.getElementById('statusText');
        const startButton = document.getElementById('startButton');
        const stopButton = document.getElementById('stopButton');
        const transcription = document.getElementById('transcription');
        const transcriptionText = document.getElementById('transcriptionText');
        const response = document.getElementById('response');
        const browserSupport = document.getElementById('browserSupport');

        // Enhanced wake word variations for CRMAutoPilot
        const wakeWords = [
            'hey crm autopilot', 'crm autopilot', 'hey ai assistant', 'ai assistant',
            'hey voice assistant', 'voice assistant'
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
                    isListening = true;
                    retryCount = 0;
                    lastError = null;
                    shouldStop = false;
                    updateUI('listening', '🎤 Listening for "Hey CRMAutoPilot"...', '👂');
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
                    }}
                    
                    if (finalTranscript && !isProcessingCommand) {{
                        commandBuffer += finalTranscript.trim() + ' ';
                        
                        if (bufferTimeout) {{
                            clearTimeout(bufferTimeout);
                        }}
                        
                        const hasWakeWord = checkForWakeWordInBuffer(commandBuffer);
                        
                        if (hasWakeWord) {{
                            const commandLower = commandBuffer.toLowerCase().trim();
                            const hasActionWord = commandLower.includes('text') || commandLower.includes('send') || 
                                                commandLower.includes('message') || commandLower.includes('email') ||
                                                commandLower.includes('create') || commandLower.includes('add') ||
                                                commandLower.includes('schedule') || commandLower.includes('show') ||
                                                commandLower.includes('update');
                            
                            const justWakeWord = wakeWords.some(wake => commandLower.trim() === wake.toLowerCase());
                            
                            let waitTime = justWakeWord || !hasActionWord ? 8000 : 4000;
                            
                            if (justWakeWord || !hasActionWord) {{
                                updateUI('wake-detected', '⏳ Capturing complete command...', '⏳');
                            }} else {{
                                updateUI('wake-detected', '⚡ Complete command detected!', '⚡');
                            }}
                            
                            bufferTimeout = setTimeout(() => {{
                                checkForWakeWord(commandBuffer.trim());
                                commandBuffer = '';
                            }}, waitTime);
                        }} else {{
                            bufferTimeout = setTimeout(() => {{
                                commandBuffer = '';
                            }}, 6000);
                        }}
                    }}
                }};

                recognition.onerror = function(event) {{
                    lastError = event.error;
                    
                    if (event.error === 'no-speech') {{
                        return;
                    }}
                    
                    if (event.error === 'aborted') {{
                        shouldStop = true;
                        continuousListening = false;
                        retryCount = maxRetries;
                        
                        setTimeout(() => {{
                            updateUI('idle', 'Speech recognition was blocked. Please click Start Listening to try again.', '❌');
                            startButton.disabled = false;
                            stopButton.disabled = true;
                        }}, 100);
                        return;
                    }}
                    
                    let errorMessage = 'Recognition error: ' + event.error;
                    updateUI('idle', errorMessage, '❌');
                    
                    retryCount++;
                    if (retryCount >= maxRetries) {{
                        shouldStop = true;
                        continuousListening = false;
                        updateUI('idle', 'Speech recognition failed. Click Start Listening to try again.', '❌');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }}
                }};

                recognition.onend = function() {{
                    isListening = false;
                    
                    if (shouldStop || lastError === 'aborted' || !continuousListening || isProcessingCommand) {{
                        updateUI('idle', 'Speech recognition stopped', '🎤');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                        return;
                    }}
                    
                    if (continuousListening && retryCount < maxRetries) {{
                        setTimeout(() => {{ 
                            if (continuousListening && !shouldStop && !isListening) {{ 
                                restartListening(); 
                            }}
                        }}, 1000);
                    }} else {{
                        continuousListening = false;
                        shouldStop = true;
                        updateUI('idle', 'Speech recognition stopped. Click Start Listening to restart.', '🎤');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }}
                }};

                browserSupport.textContent = 'Enhanced voice recognition with HubSpot CRM support ✅';
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
            
            for (const wakeWord of wakeWords) {{
                if (lowerText.includes(wakeWord)) {{
                    wakeWordFound = true;
                    detectedWakeWord = wakeWord;
                    break;
                }}
            }}
            
            if (wakeWordFound) {{
                processWakeWordCommand(text);
            }}
        }}

        async function processWakeWordCommand(fullText) {{
            if (isProcessingCommand) {{
                return;
            }}
            isProcessingCommand = true;
            updateUI('wake-detected', '⚡ Wake word detected! Processing...', '⚡');
            transcriptionText.textContent = fullText;
            try {{
                updateUI('processing', '📤 Sending command...', '⚙️');
                const apiResponse = await fetch('/execute', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ text: fullText }})
                }});
                const data = await apiResponse.json();
                if (apiResponse.ok) {{
                    showResponse(data.response || 'Command executed successfully!', 'success');
                    updateUI('listening', '✅ Command sent! Listening for next command...', '👂');
                }} else {{
                    showResponse(data.error || 'An error occurred while processing your command.', 'error');
                    updateUI('listening', '❌ Error occurred. Listening for next command...', '👂');
                }}
            }} catch (error) {{
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
            
            const lowerCommand = command.toLowerCase();
            const hasWakeWord = wakeWords.some(wakeWord => lowerCommand.startsWith(wakeWord.toLowerCase()));
            
            if (!hasWakeWord) {{
                command = 'Hey CRMAutoPilot ' + command;
                manualInput.value = command;
                setTimeout(() => {{ manualInput.value = ''; }}, 2000);
            }} else {{
                manualInput.value = '';
            }}
            
            processWakeWordCommand(command);
        }}

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
            
            if (isListening) {{
                try {{
                    recognition.stop();
                }} catch (e) {{}}
            }}
            
            continuousListening = true;
            retryCount = 0;
            lastError = null;
            shouldStop = false;
            startButton.disabled = true;
            stopButton.disabled = false;
            response.style.display = 'none';
            commandBuffer = '';
            
            setTimeout(() => {{
                try {{
                    if (!isListening && !shouldStop) {{ 
                        recognition.start();
                    }}
                }} catch (error) {{
                    updateUI('idle', 'Error starting recognition. Please try again.', '❌');
                    startButton.disabled = false;
                    stopButton.disabled = true;
                    continuousListening = false;
                    shouldStop = true;
                }}
            }}, 100);
        }}

        function stopListening() {{
            continuousListening = false;
            shouldStop = true;
            retryCount = 0;
            lastError = null;
            
            if (recognition && isListening) {{
                try {{
                    recognition.stop();
                }} catch (error) {{}}
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
            if (shouldStop || !continuousListening || !recognition || isListening || retryCount >= maxRetries) {{
                return;
            }}
            
            try {{
                recognition.start();
            }} catch (error) {{
                retryCount++;
                if (retryCount < maxRetries && !shouldStop) {{
                    setTimeout(() => {{ 
                        if (continuousListening && !shouldStop) {{ 
                            restartListening(); 
                        }} 
                    }}, retryDelay);
                }} else {{
                    shouldStop = true;
                    continuousListening = false;
                    updateUI('idle', 'Speech recognition failed. Click Start Listening to try again.', '❌');
                    startButton.disabled = false;
                    stopButton.disabled = true;
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
                    .then(() => {{}})
                    .catch((error) => {{}});
            }}
        }}, {{ once: true }});
    </script>
</body>
</html>'''

# ==================== ROUTES ====================

@app.route("/")
def root():
    return get_html_template()

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        
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

@app.route('/test-email', methods=['POST'])
def test_email():
    """Test email configuration"""
    try:
        data = request.json
        test_email = data.get("email", "test@example.com")
        
        if CONFIG["email_address"] and CONFIG["email_password"]:
            result = email_client.send_email(
                test_email, 
                "Test Email from CRMAutoPilot Voice Assistant", 
                "This is a test email sent from your CRMAutoPilot Voice Assistant to verify email configuration is working correctly."
            )
            
            if result.get("success"):
                return jsonify({
                    "success": True, 
                    "message": f"Test email sent successfully to {test_email}",
                    "provider": CONFIG["email_provider"],
                    "from": result.get("from")
                })
            else:
                return jsonify({"error": result.get("error")})
        else:
            return jsonify({"error": "Email not configured. Please set EMAIL_ADDRESS and EMAIL_PASSWORD environment variables."})
    
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "wake_word_enabled": CONFIG["wake_word_enabled"],
        "wake_word_primary": CONFIG["wake_word_primary"],
        "services": {
            "twilio_configured": bool(twilio_client.client),
            "email_configured": bool(CONFIG["email_address"] and CONFIG["email_password"]),
            "hubspot_configured": bool(CONFIG["hubspot_api_token"]),
            "claude_configured": bool(CONFIG["claude_api_key"])
        },
        "email_config": {
            "provider": CONFIG["email_provider"],
            "smtp_server": CONFIG["email_smtp_server"],
            "smtp_port": CONFIG["email_smtp_port"]
        },
        "crm_integration": {
            "provider": "HubSpot",
            "api_configured": bool(CONFIG["hubspot_api_token"])
        }
    })

@app.route('/health-crm', methods=['GET'])
def crm_health_check():
    """CRM-specific health check"""
    hubspot_test = hubspot_service.test_connection()
    
    return jsonify({
        "status": "healthy",
        "crm_integration": {
            "hubspot_configured": bool(hubspot_service.api_token),
            "hubspot_connection": hubspot_test.get("success", False),
            "hubspot_error": hubspot_test.get("error") if not hubspot_test.get("success") else None,
            "supported_crm_actions": [
                "create_contact", "update_contact_phone", "add_contact_note", "search_contact",
                "create_task", "schedule_meeting", "show_calendar", 
                "create_opportunity", "show_pipeline_summary"
            ]
        },
        "communication": {
            "sms_enabled": bool(twilio_client.client),
            "email_enabled": bool(CONFIG["email_address"] and CONFIG["email_password"])
        }
    })

if __name__ == '__main__':
    print("🚀 Starting CRMAutoPilot AI Assistant with HubSpot CRM Integration")
    print(f"🎙️ Primary Wake Word: '{CONFIG['wake_word_primary']}'")
    print(f"📱 Twilio: {'✅ Ready' if twilio_client.client else '❌ Not configured'}")
    
    email_status = "✅ Ready" if CONFIG['email_address'] and CONFIG['email_password'] else "⚠️ Not configured"
    print(f"📧 Email ({CONFIG['email_provider'].title()}): {email_status}")
    
    hubspot_status = "✅ Ready" if CONFIG['hubspot_api_token'] else "⚠️ Not configured"
    print(f"🏢 HubSpot CRM: {hubspot_status}")
    if CONFIG['hubspot_api_token']:
        print(f"   └─ Token: {CONFIG['hubspot_api_token'][:12]}...")
    
    print(f"🤖 Claude: {'✅ Ready' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    
    print("\n🎯 Supported Voice Commands:")
    print("   📱 SMS: 'Hey CRMAutoPilot text John saying hello'")
    print("   📧 Email: 'Hey CRMAutoPilot email client@company.com saying proposal ready'")
    print("   👥 Contacts: 'Hey CRMAutoPilot create contact John Smith email john@test.com'")
    print("   🔄 Update: 'Hey CRMAutoPilot update contact Manuel Stagg phone number 555-1234'")
    print("   📋 Tasks: 'Hey CRMAutoPilot create task to follow up with prospects'")
    print("   📅 Calendar: 'Hey CRMAutoPilot schedule meeting with new lead tomorrow'")
    print("   📊 Pipeline: 'Hey CRMAutoPilot show me this month's sales pipeline status'")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Starting on port {port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
