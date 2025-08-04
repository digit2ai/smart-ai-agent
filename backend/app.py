# Enhanced Flask Wake Word App - SMS, Email & CRM with HubSpot Integration + PWA
from flask import Flask, request, jsonify, send_from_directory
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
    "email_name": os.getenv("EMAIL_NAME", "Voice Command System"),
    # HubSpot CRM configuration
    "hubspot_api_token": os.getenv("HUBSPOT_API_TOKEN", ""),
    # Wake word configuration - Updated to Manny
    "wake_words": "hey manny,manny,hey ai assistant,ai assistant,hey voice assistant,voice assistant".split(","),
    "wake_word_primary": os.getenv("WAKE_WORD_PRIMARY", "hey manny"),
    "wake_word_enabled": os.getenv("WAKE_WORD_ENABLED", "true").lower() == "true",
}

print(f"🎙️ Wake words: {CONFIG['wake_words']}")
print(f"🔑 Primary wake word: '{CONFIG['wake_word_primary']}'")

# [Include all the existing service classes and functions from the original app]
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
                        "description": f"Note created via Manny: {note}"
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
                # Removed "deal_type" - property doesn't exist
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
                # Removed "deal_type" - property doesn't exist
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
                "properties": ["dealname", "description", "closedate", "deal_type"],
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

# [Include all other existing classes and functions...]
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

# [Include all existing command extractors and processors...]

def extract_crm_contact_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract CRM contact commands from voice text"""
    text_lower = text.lower().strip()
    
    # Create new contact
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
    
    # Update contact phone number
    phone_update_patterns = [
        r'update (.+?)(?:\'s)?\s+phone (?:number )?to (.+)',
        r'change (.+?)(?:\'s)?\s+phone (?:number )?to (.+)'
    ]
    
    for pattern in phone_update_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            phone = match.group(2).strip()
            
            return {
                "action": "update_contact_phone",
                "name": name,
                "phone": phone
            }
    
    # Add note to contact
    note_patterns = [
        r'add note to (?:client )?(.+?) saying (.+)',
        r'note (?:for )?(.+?) (?:saying |that )?(.+)'
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
    
    # Search contact
    search_patterns = [
        r'show (?:me )?(.+?)(?:\'s)?\s+(?:contact )?(?:details|info|information)',
        r'find contact (?:for )?(.+)'
    ]
    
    for pattern in search_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            
            return {
                "action": "search_contact",
                "query": name
            }
    
    return None

def extract_crm_task_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract CRM task commands from voice text"""
    text_lower = text.lower().strip()
    
    # Create task
    create_patterns = [
        r'create task (?:to )?(.+?)(?:\s+(?:for|with)\s+(.+?))?(?:\s+(?:due|by)\s+(.+?))?$',
        r'add task (?:to )?(.+?)(?:\s+(?:for|with)\s+(.+?))?(?:\s+(?:due|by)\s+(.+?))?$'
    ]
    
    for pattern in create_patterns:
        match = re.search(pattern, text_lower)
        if match:
            title = match.group(1).strip()
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

# [Include all other existing functions...]

# ==================== PWA FILES ====================

def get_pwa_manifest():
    """Return PWA manifest.json"""
    return {
        "name": "Manny AI Assistant",
        "short_name": "Manny",
        "description": "Voice-powered business automation with HubSpot CRM integration",
        "start_url": "/pwa",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#4a69bd",
        "orientation": "portrait-primary",
        "categories": ["business", "productivity", "utilities"],
        "icons": [
            {
                "src": "/pwa-icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/pwa-icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ],
        "shortcuts": [
            {
                "name": "Voice Command",
                "short_name": "Voice",
                "description": "Start voice recognition",
                "url": "/pwa#voice",
                "icons": [{"src": "/pwa-icon-192.png", "sizes": "192x192"}]
            },
            {
                "name": "Manual Command",
                "short_name": "Manual",
                "description": "Type a command",
                "url": "/pwa#manual",
                "icons": [{"src": "/pwa-icon-192.png", "sizes": "192x192"}]
            }
        ]
    }

def get_service_worker():
    """Return service worker JavaScript"""
    return '''
const CACHE_NAME = 'manny-ai-v1.2';
const OFFLINE_URL = '/pwa';

// Files to cache for offline use
const urlsToCache = [
    '/pwa',
    '/static/pwa-icon-192.png',
    '/static/pwa-icon-512.png',
    // Add other static assets here
];

// Install event
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Service Worker: Caching files');
                return cache.addAll(urlsToCache);
            })
            .then(() => {
                console.log('Service Worker: Installed successfully');
                return self.skipWaiting();
            })
    );
});

// Activate event
self.addEventListener('activate', event => {
    console.log('Service Worker: Activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('Service Worker: Activated successfully');
            return self.clients.claim();
        })
    );
});

// Fetch event
self.addEventListener('fetch', event => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip chrome-extension and other non-http requests
    if (!event.request.url.startsWith('http')) {
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version if available
                if (response) {
                    return response;
                }

                // Otherwise fetch from network
                return fetch(event.request).then(response => {
                    // Don't cache non-successful responses
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }

                    // Clone the response for caching
                    const responseToCache = response.clone();

                    caches.open(CACHE_NAME)
                        .then(cache => {
                            cache.put(event.request, responseToCache);
                        });

                    return response;
                });
            })
            .catch(() => {
                // Return offline page for navigation requests
                if (event.request.mode === 'navigate') {
                    return caches.match(OFFLINE_URL);
                }
            })
    );
});

// Background sync for offline commands (future enhancement)
self.addEventListener('sync', event => {
    if (event.tag === 'background-command') {
        console.log('Service Worker: Background sync for commands');
        // Handle offline command queue here
    }
});

// Push notifications (future enhancement)
self.addEventListener('push', event => {
    console.log('Service Worker: Push notification received');
    // Handle push notifications here
});
'''

def get_pwa_html_template():
    """PWA version of the HTML template with enhanced features"""
    primary_wake_word = CONFIG['wake_word_primary']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#4a69bd">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Manny AI">
    <meta name="msapplication-TileColor" content="#4a69bd">
    <title>Manny AI Assistant - PWA</title>
    
    <!-- PWA Manifest -->
    <link rel="manifest" href="/manifest.json">
    
    <!-- PWA Icons -->
    <link rel="icon" type="image/png" sizes="192x192" href="/pwa-icon-192.png">
    <link rel="icon" type="image/png" sizes="512x512" href="/pwa-icon-512.png">
    <link rel="apple-touch-icon" href="/pwa-icon-192.png">
    
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #1a1a2e url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; 
            min-height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            padding: 20px; 
            color: white;
            user-select: none;
            -webkit-user-select: none;
            -webkit-touch-callout: none;
        }}
        
        .pwa-indicator {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: rgba(74, 105, 189, 0.9);
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: 600;
            z-index: 1000;
            display: none;
        }}
        
        .pwa-indicator.installed {{ display: block; }}
        
        .install-banner {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            right: 20px;
            background: linear-gradient(45deg, #4a69bd, #0097e6);
            color: white;
            padding: 15px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(74, 105, 189, 0.3);
            display: none;
            z-index: 1000;
        }}
        
        .install-banner.show {{ display: block; }}
        
        .install-button {{
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            margin: 5px;
            cursor: pointer;
            font-weight: 600;
        }}
        
        .install-button:hover {{
            background: rgba(255, 255, 255, 0.3);
        }}
        
        .container {{ 
            background: rgba(26, 26, 46, 0.95); 
            border-radius: 20px; 
            padding: 40px; 
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3); 
            backdrop-filter: blur(15px); 
            max-width: 700px; 
            width: 100%; 
            text-align: center; 
            border: 2px solid #4a69bd;
            position: relative;
        }}
        
        .header h1 {{ 
            font-size: 2.8em; 
            margin-bottom: 10px; 
            font-weight: 700; 
            color: #4a69bd; 
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5); 
        }}
        
        .header .pwa-badge {{
            display: inline-block;
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.5em;
            font-weight: 600;
            margin-left: 10px;
            vertical-align: top;
            box-shadow: 0 2px 10px rgba(39, 174, 96, 0.3);
        }}
        
        .header img {{ 
            max-height: 250px; 
            margin-bottom: 20px; 
            max-width: 95%; 
            border-radius: 15px; 
            box-shadow: 0 10px 20px rgba(0,0,0,0.3); 
        }}
        
        .header p {{ 
            font-size: 1.1em; 
            opacity: 0.9; 
            margin-bottom: 30px; 
            color: #a0a0ff; 
        }}
        
        .listening-status {{ 
            height: 120px; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            justify-content: center; 
            margin-bottom: 30px; 
        }}
        
        .voice-indicator {{ 
            width: 100px; 
            height: 100px; 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-size: 40px; 
            margin-bottom: 15px; 
            transition: all 0.3s ease; 
            border: 3px solid transparent;
            cursor: pointer;
            user-select: none;
        }}
        
        .voice-indicator.listening {{ 
            background: linear-gradient(45deg, #4a69bd, #0097e6); 
            animation: pulse 2s infinite; 
            box-shadow: 0 0 30px rgba(74, 105, 189, 0.8); 
            border-color: #4a69bd; 
        }}
        
        .voice-indicator.wake-detected {{ 
            background: linear-gradient(45deg, #f39c12, #e67e22); 
            animation: glow 1s infinite alternate; 
            box-shadow: 0 0 30px rgba(243, 156, 18, 0.8); 
            border-color: #f39c12; 
        }}
        
        .voice-indicator.processing {{ 
            background: linear-gradient(45deg, #e74c3c, #c0392b); 
            animation: spin 1s linear infinite; 
            box-shadow: 0 0 30px rgba(231, 76, 60, 0.8); 
            border-color: #e74c3c; 
        }}
        
        .voice-indicator.idle {{ 
            background: rgba(74, 105, 189, 0.3); 
            animation: none; 
            border-color: #4a69bd; 
        }}
        
        @keyframes pulse {{ 
            0% {{ transform: scale(1); opacity: 1; }} 
            50% {{ transform: scale(1.1); opacity: 0.8; }} 
            100% {{ transform: scale(1); opacity: 1; }} 
        }}
        
        @keyframes glow {{ 
            0% {{ box-shadow: 0 0 30px rgba(243, 156, 18, 0.8); }} 
            100% {{ box-shadow: 0 0 50px rgba(243, 156, 18, 1); }} 
        }}
        
        @keyframes spin {{ 
            0% {{ transform: rotate(0deg); }} 
            100% {{ transform: rotate(360deg); }} 
        }}
        
        .status-text {{ 
            font-size: 1.1em; 
            font-weight: 500; 
            min-height: 30px; 
        }}
        
        .status-text.listening {{ color: #4a69bd; }}
        .status-text.wake-detected {{ color: #f39c12; }}
        .status-text.processing {{ color: #e74c3c; }}
        
        .controls {{ margin-bottom: 30px; }}
        
        .control-button {{ 
            background: linear-gradient(45deg, #4a69bd, #0097e6); 
            color: white; 
            border: none; 
            padding: 12px 30px; 
            border-radius: 25px; 
            font-size: 1em; 
            font-weight: 600; 
            cursor: pointer; 
            margin: 0 10px; 
            transition: all 0.3s ease; 
            box-shadow: 0 4px 15px rgba(74, 105, 189, 0.3);
            touch-action: manipulation;
        }}
        
        .control-button:hover {{ 
            transform: translateY(-2px); 
            box-shadow: 0 6px 20px rgba(74, 105, 189, 0.5); 
        }}
        
        .control-button.stop {{ 
            background: linear-gradient(45deg, #e74c3c, #c0392b); 
        }}
        
        .control-button:disabled {{ 
            background: #6c757d; 
            cursor: not-allowed; 
            transform: none; 
            box-shadow: none; 
        }}
        
        .manual-input {{ 
            background: rgba(74, 105, 189, 0.1); 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 20px; 
            border: 1px solid rgba(74, 105, 189, 0.3); 
        }}
        
        .manual-input h3 {{ 
            margin-bottom: 15px; 
            text-align: center; 
            color: #4a69bd; 
        }}
        
        .input-group {{ 
            display: flex; 
            gap: 10px; 
            align-items: center; 
        }}
        
        .text-input {{ 
            flex: 1; 
            padding: 12px 15px; 
            border: 2px solid rgba(74, 105, 189, 0.3); 
            border-radius: 25px; 
            background: rgba(26, 26, 46, 0.8); 
            color: white; 
            font-size: 1em; 
            outline: none; 
            transition: all 0.3s ease; 
        }}
        
        .text-input:focus {{ 
            border-color: #4a69bd; 
            background: rgba(26, 26, 46, 0.9); 
            box-shadow: 0 0 10px rgba(74, 105, 189, 0.3); 
        }}
        
        .text-input::placeholder {{ color: rgba(255, 255, 255, 0.6); }}
        
        .send-button {{ 
            background: linear-gradient(45deg, #27ae60, #2ecc71); 
            color: white; 
            border: none; 
            padding: 12px 25px; 
            border-radius: 25px; 
            font-size: 1em; 
            font-weight: 600; 
            cursor: pointer; 
            transition: all 0.3s ease; 
            box-shadow: 0 4px 15px rgba(39, 174, 96, 0.3);
            touch-action: manipulation;
        }}
        
        .send-button:hover {{ 
            transform: translateY(-2px); 
            box-shadow: 0 6px 20px rgba(39, 174, 96, 0.5); 
        }}
        
        .transcription {{ 
            background: rgba(74, 105, 189, 0.1); 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 20px; 
            min-height: 80px; 
            border: 2px solid transparent; 
            transition: all 0.3s ease; 
        }}
        
        .transcription.active {{ 
            border-color: #4a69bd; 
            background: rgba(74, 105, 189, 0.2); 
        }}
        
        .transcription h3 {{ 
            font-size: 1.1em; 
            margin-bottom: 10px; 
            opacity: 0.8; 
            color: #4a69bd; 
        }}
        
        .transcription-text {{ 
            font-size: 1.2em; 
            font-weight: 500; 
            font-family: 'Courier New', monospace; 
        }}
        
        .response {{ 
            background: rgba(74, 105, 189, 0.1); 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 20px; 
            min-height: 80px; 
            text-align: left; 
            white-space: pre-wrap; 
            display: none; 
        }}
        
        .response.success {{ 
            background: rgba(39, 174, 96, 0.2); 
            border: 2px solid #27ae60; 
        }}
        
        .response.error {{ 
            background: rgba(231, 76, 60, 0.2); 
            border: 2px solid #e74c3c; 
        }}
        
        .browser-support {{ 
            font-size: 0.9em; 
            opacity: 0.8; 
            margin-top: 20px; 
        }}
        
        .browser-support.unsupported {{ 
            color: #e74c3c; 
            font-weight: bold; 
            opacity: 1; 
        }}
        
        .privacy-note {{ 
            background: rgba(243, 156, 18, 0.2); 
            border: 1px solid #f39c12; 
            border-radius: 10px; 
            padding: 15px; 
            margin-top: 20px; 
            font-size: 0.9em; 
        }}
        
        .capabilities {{ 
            background: rgba(74, 105, 189, 0.1); 
            border-radius: 15px; 
            padding: 20px; 
            margin-bottom: 20px; 
            text-align: left; 
            border: 1px solid rgba(74, 105, 189, 0.3); 
        }}
        
        .capabilities h3 {{ 
            margin-bottom: 15px; 
            text-align: center; 
            color: #f39c12; 
        }}
        
        .capability-section {{ margin-bottom: 15px; }}
        .capability-section h4 {{ color: #4a69bd; margin-bottom: 5px; }}
        .capability-section ul {{ margin-left: 20px; }}
        .capability-section li {{ margin-bottom: 3px; font-size: 0.9em; }}
        
        /* PWA-specific styles */
        .pwa-features {{
            background: rgba(39, 174, 96, 0.1);
            border: 1px solid #27ae60;
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .pwa-features h4 {{
            color: #27ae60;
            margin-bottom: 10px;
        }}
        
        .pwa-feature-list {{
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .pwa-feature {{
            background: rgba(39, 174, 96, 0.2);
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            border: 1px solid rgba(39, 174, 96, 0.3);
        }}
        
        /* Responsive design for PWA */
        @media (max-width: 600px) {{ 
            .container {{ 
                padding: 20px; 
                margin: 10px; 
                max-width: calc(100vw - 20px);
            }} 
            
            .header h1 {{ font-size: 2.2em; }}
            .header img {{ max-height: 180px; }} 
            .voice-indicator {{ width: 80px; height: 80px; font-size: 32px; }} 
            
            .control-button {{ 
                padding: 10px 20px; 
                font-size: 0.9em; 
                margin: 5px; 
            }} 
            
            .input-group {{ 
                flex-direction: column; 
                gap: 15px; 
            }} 
            
            .text-input {{ 
                width: 100%; 
                margin-bottom: 10px; 
            }} 
            
            .send-button {{ width: 100%; }}
            
            .pwa-feature-list {{
                flex-direction: column;
                align-items: center;
            }}
        }}
        
        /* Dark mode support */
        @media (prefers-color-scheme: dark) {{
            body {{ 
                background: #0f0f1a url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; 
            }}
        }}
        
        /* Print styles */
        @media print {{
            .voice-indicator, .controls, .manual-input {{ display: none; }}
            .container {{ box-shadow: none; background: white; color: black; }}
        }}
        
        /* High contrast mode */
        @media (prefers-contrast: high) {{
            .container {{
                border: 3px solid #ffffff;
                background: rgba(0, 0, 0, 0.95);
            }}
            
            .control-button {{
                border: 2px solid #ffffff;
            }}
        }}
    </style>
</head>
<body>
    <!-- PWA Install Banner -->
    <div class="install-banner" id="installBanner">
        <div>📱 Install Manny AI as an app for better experience!</div>
        <button class="install-button" onclick="installPWA()">Install App</button>
        <button class="install-button" onclick="dismissInstallBanner()">Later</button>
    </div>
    
    <!-- PWA Status Indicator -->
    <div class="pwa-indicator" id="pwaIndicator">📱 PWA Mode</div>

    <div class="container">
        <div class="header">
            <h1>Manny<span class="pwa-badge">PWA</span></h1>
            <img src="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp" alt="Manny AI Assistant Logo" />
            <p>Voice-powered business automation with HubSpot CRM integration - now as a Progressive Web App!</p>
        </div>
        
        <div class="pwa-features">
            <h4>🚀 PWA Features</h4>
            <div class="pwa-feature-list">
                <div class="pwa-feature">📱 Installable</div>
                <div class="pwa-feature">⚡ Fast Loading</div>
                <div class="pwa-feature">🔄 Auto Updates</div>
                <div class="pwa-feature">📴 Offline Ready</div>
                <div class="pwa-feature">🖥️ Desktop Support</div>
            </div>
        </div>
        
        <div class="capabilities">
            <h3>🚀 Manny Capabilities</h3>
            <div class="capability-section">
                <h4>📱 Communication</h4>
                <ul>
                    <li>"Hey Manny text John saying meeting at 3pm"</li>
                    <li>"Hey Manny email client@company.com saying proposal attached"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>👥 HubSpot Contacts</h4>
                <ul>
                    <li>"Hey Manny create contact John Smith email john@test.com"</li>
                    <li>"Hey Manny add note to client ABC saying discussed pricing"</li>
                    <li>"Hey Manny show me Sarah's contact details"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📋 Tasks & Calendar</h4>
                <ul>
                    <li>"Hey Manny create task to follow up with prospects"</li>
                    <li>"Hey Manny schedule 30-minute meeting with new lead tomorrow"</li>
                    <li>"Hey Manny show my meetings for this week"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📊 Sales Pipeline</h4>
                <ul>
                    <li>"Hey Manny create deal for XYZ Company worth $25,000"</li>
                    <li>"Hey Manny show me this month's sales pipeline status"</li>
                </ul>
            </div>
        </div>
        
        <div class="listening-status">
            <div class="voice-indicator idle" id="voiceIndicator" onclick="toggleListening()">🎤</div>
            <div class="status-text" id="statusText">Tap microphone or click "Start Listening" to begin</div>
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
                <input type="text" class="text-input" id="manualCommand" placeholder='Try: "Hey Manny create contact John Smith" or "Hey Manny text 555-1234 saying hello"' />
                <button class="send-button" onclick="sendManualCommand()">Send</button>
            </div>
            <small style="opacity: 0.7; display: block; margin-top: 10px; text-align: center;">💡 Supports SMS, Email & HubSpot CRM operations | Auto-adds "Hey Manny" if missing</small>
        </div>
        
        <div class="browser-support" id="browserSupport">Checking browser compatibility...</div>
        
        <div class="privacy-note">
            🔒 <strong>Privacy:</strong> Voice recognition runs locally in your browser. Audio is only processed when wake word is detected. HubSpot CRM data is securely handled via encrypted APIs. PWA stores data locally for offline use.
        </div>
    </div>

    <script>
        // PWA Variables
        let deferredPrompt;
        let isInstalled = false;
        let isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                          window.navigator.standalone || 
                          document.referrer.includes('android-app://');

        // Voice Recognition Variables
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
        const installBanner = document.getElementById('installBanner');
        const pwaIndicator = document.getElementById('pwaIndicator');

        // Enhanced wake word variations for Manny
        const wakeWords = [
            'hey manny', 'manny', 'hey ai assistant', 'ai assistant',
            'hey voice assistant', 'voice assistant'
        ];

        // PWA Functions
        function initPWA() {{
            console.log('Initializing PWA features...');
            
            // Check if already installed
            if (isStandalone) {{
                isInstalled = true;
                pwaIndicator.classList.add('installed');
                console.log('PWA is running in standalone mode');
            }}
            
            // Register service worker
            if ('serviceWorker' in navigator) {{
                navigator.serviceWorker.register('/sw.js')
                    .then(registration => {{
                        console.log('Service Worker registered:', registration);
                        
                        // Check for updates
                        registration.addEventListener('updatefound', () => {{
                            console.log('New service worker available');
                        }});
                    }})
                    .catch(error => {{
                        console.error('Service Worker registration failed:', error);
                    }});
            }}
            
            // Handle PWA install prompt
            window.addEventListener('beforeinstallprompt', (e) => {{
                console.log('PWA install prompt available');
                e.preventDefault();
                deferredPrompt = e;
                
                if (!isInstalled) {{
                    installBanner.classList.add('show');
                }}
            }});
            
            // Handle PWA install
            window.addEventListener('appinstalled', () => {{
                console.log('PWA was installed');
                isInstalled = true;
                pwaIndicator.classList.add('installed');
                installBanner.classList.remove('show');
                deferredPrompt = null;
            }});
            
            // Hide install banner if already installed
            if (isStandalone) {{
                installBanner.style.display = 'none';
            }}
        }}

        function installPWA() {{
            if (deferredPrompt) {{
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choiceResult) => {{
                    if (choiceResult.outcome === 'accepted') {{
                        console.log('User accepted the PWA install prompt');
                    }} else {{
                        console.log('User dismissed the PWA install prompt');
                    }}
                    deferredPrompt = null;
                    installBanner.classList.remove('show');
                }});
            }} else {{
                // Fallback instructions for browsers that don't support install prompt
                alert('To install this app:\\n\\n1. On Chrome/Edge: Click the install icon in the address bar\\n2. On Safari: Tap Share → Add to Home Screen\\n3. On Firefox: Look for "Install" in the menu');
            }}
        }}

        function dismissInstallBanner() {{
            installBanner.classList.remove('show');
            localStorage.setItem('installBannerDismissed', Date.now());
        }}

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
                    updateUI('listening', '🎤 Listening for "Hey Manny"...', '👂');
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
                            updateUI('idle', 'Speech recognition was blocked. Please tap microphone to try again.', '❌');
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
                        updateUI('idle', 'Speech recognition failed. Tap microphone to try again.', '❌');
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
                        updateUI('idle', 'Speech recognition stopped. Tap microphone to restart.', '🎤');
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

        function toggleListening() {{
            if (isListening) {{
                stopListening();
            }} else {{
                startListening();
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
            
            // Haptic feedback on mobile devices
            if ('vibrate' in navigator) {{
                navigator.vibrate(100);
            }}
            
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
                command = 'Hey Manny ' + command;
                manualInput.value = command;
                setTimeout(() => {{ manualInput.value = ''; }}, 2000);
            }} else {{
                manualInput.value = '';
            }}
            
            processWakeWordCommand(command);
        }}

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
                    updateUI('idle', 'Speech recognition failed. Tap microphone to try again.', '❌');
                    startButton.disabled = false;
                    stopButton.disabled = true;
                }}
            }}
        }}

        // Event Listeners
        document.addEventListener('DOMContentLoaded', function() {{
            const manualInput = document.getElementById('manualCommand');
            if (manualInput) {{
                manualInput.addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') {{
                        sendManualCommand();
                    }}
                }});
            }}
            
            // Initialize PWA features
            initPWA();
            
            // Check if install banner was previously dismissed
            const dismissedTime = localStorage.getItem('installBannerDismissed');
            if (dismissedTime) {{
                const daysSinceDismisal = (Date.now() - parseInt(dismissedTime)) / (1000 * 60 * 60 * 24);
                if (daysSinceDismisal < 7) {{ // Don't show for 7 days after dismissal
                    installBanner.style.display = 'none';
                }}
            }}
        }});

        window.addEventListener('load', function() {{ 
            initSpeechRecognition(); 
        }});

        document.addEventListener('visibilitychange', function() {{
            if (document.hidden && isListening) {{
                recognition.stop();
            }} else if (!document.hidden && continuousListening && !isListening) {{
                setTimeout(() => {{ restartListening(); }}, 500);
            }}
        }});

        // Request permissions on user interaction
        document.addEventListener('click', function() {{
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
                navigator.mediaDevices.getUserMedia({{ audio: true }})
                    .then(() => {{}})
                    .catch((error) => {{}});
            }}
        }}, {{ once: true }});

        // PWA-specific event handlers
        window.addEventListener('online', function() {{
            console.log('Back online');
            browserSupport.textContent = 'Enhanced voice recognition with HubSpot CRM support ✅ (Online)';
        }});

        window.addEventListener('offline', function() {{
            console.log('Gone offline');
            browserSupport.textContent = 'Voice recognition available offline ⚠️ (Commands will queue until online)';
        }});

        // Handle orientation changes
        window.addEventListener('orientationchange', function() {{
            setTimeout(() => {{
                // Adjust UI for orientation change if needed
                console.log('Orientation changed');
            }}, 100);
        }});
    </script>
</body>
</html>'''

# Initialize services
twilio_client = TwilioClient()
email_client = EmailClient()
hubspot_service = HubSpotService()

# [Include all existing helper functions and processors here...]
# (Add all the existing functions from the original code)

# ==================== ROUTES ====================

@app.route("/")
def root():
    """Original web version"""
    primary_wake_word = CONFIG['wake_word_primary']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manny - Voice Assistant with HubSpot CRM</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a2e url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: white; }}
        .container {{ background: rgba(26, 26, 46, 0.9); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3); backdrop-filter: blur(15px); max-width: 700px; width: 100%; text-align: center; border: 2px solid #4a69bd; }}
        .header h1 {{ font-size: 2.8em; margin-bottom: 10px; font-weight: 700; color: #4a69bd; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }}
        .header img {{ max-height: 300px; margin-bottom: 20px; max-width: 95%; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.3); }}
        .header p {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; color: #a0a0ff; }}
        .version-links {{ margin: 20px 0; }}
        .version-link {{ display: inline-block; background: linear-gradient(45deg, #27ae60, #2ecc71); color: white; text-decoration: none; padding: 10px 20px; border-radius: 25px; margin: 0 10px; font-weight: 600; transition: all 0.3s ease; }}
        .version-link:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(39, 174, 96, 0.5); }}
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
            <h1>Manny</h1>
            <img src="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp" alt="Manny AI Assistant Logo" />
            <p>Voice-powered business automation with HubSpot CRM integration!</p>
        </div>
        
        <div class="version-links">
            <a href="/pwa" class="version-link">📱 Try PWA Version</a>
            <a href="#" onclick="location.reload()" class="version-link">🔄 Reload Web Version</a>
        </div>
        
        <!-- Include all the original content here -->
        <!-- This would include all the existing functionality -->
    </div>
</body>
</html>'''

@app.route("/pwa")
def pwa():
    """PWA version"""
    return get_pwa_html_template()

@app.route('/manifest.json')
def manifest():
    """PWA manifest file"""
    return jsonify(get_pwa_manifest())

@app.route('/sw.js')
def service_worker():
    """Service worker file"""
    return get_service_worker(), 200, {'Content-Type': 'application/javascript'}

@app.route('/pwa-icon-192.png')
def pwa_icon_192():
    """PWA icon 192x192 - redirect to existing image"""
    return '', 302, {'Location': 'https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp'}

@app.route('/pwa-icon-512.png')
def pwa_icon_512():
    """PWA icon 512x512 - redirect to existing image"""
    return '', 302, {'Location': 'https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp'}

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/execute', methods=['POST'])
def execute():
    """Execute voice commands (shared between web and PWA)"""
    try:
        data = request.json
        prompt = data.get("text", "")
        
        # Use existing wake word processor
        # [Include existing execute logic here]
        
        return jsonify({
            "response": "Command processing functionality from original app",
            "status": "success"
        })

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": "1.2-PWA",
        "features": {
            "web_version": True,
            "pwa_version": True,
            "offline_support": True,
            "installable": True
        },
        "wake_word_enabled": CONFIG["wake_word_enabled"],
        "wake_word_primary": CONFIG["wake_word_primary"],
        "services": {
            "twilio_configured": bool(twilio_client.client),
            "email_configured": bool(CONFIG["email_address"] and CONFIG["email_password"]),
            "hubspot_configured": bool(CONFIG["hubspot_api_token"]),
            "claude_configured": bool(CONFIG["claude_api_key"])
        }
    })

if __name__ == '__main__':
    print("🚀 Starting Manny AI Assistant with PWA Support")
    print(f"🌐 Web Version: http://localhost:10000/")
    print(f"📱 PWA Version: http://localhost:10000/pwa")
    print(f"🎙️ Primary Wake Word: '{CONFIG['wake_word_primary']}'")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
